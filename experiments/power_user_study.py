"""Simulation-based power analysis for the lab user study (protocol section 4).

Every simulated study is analysed with the analysis code of the study itself
(experiments/analyze_user_study.py). Power is the share of simulated studies in which
a test succeeds; a fit that fails (for example under separation) counts as a failure.
Two designs are evaluated on the same simulated studies:

* original design: superiority of both main effects, Holm-adjusted GEE p < .05
  (columns power_selectivity, power_evidence, power_both);
* revised design (adopted, protocol section 7): fixed sequence of H-U2, evidence
  superiority (GEE p < .05, odds ratio > 1), then H-U1, selectivity non-inferiority on
  participant-level prevention (90% CI lower bound > -10 pp)
  (columns power_ev_primary, power_sel_ni, power_sequence).

Two data-generating models:

1. Assumption grid (model-free). For participant i and attacked scenario j,
       logit P(prevented) = b0 + b_s * sel_i + b_e * ev_i + u_i + v_j,
   with effect-coded sel, ev in {-0.5, +0.5}, so exp(b_s) and exp(b_e) are the
   odds ratios between factor levels (equal unless --sel-odds-ratio is given); u_i ~ N(0, sigma_u^2) (between-participant
   variation) and v_j ~ N(0, sigma_v^2) (scenario difficulty, redrawn per study).
   b0 is set so that a typical participant (u = 0) in confirm-all (B) prevents an
   attack with probability `baseline`. The interaction is zero.

2. Model-anchored. Participants are drawn from the heterogeneous simulated-user
   model of the paper (clear/human_model.py, expertise strata of
   experiments/human_sim.py) and work through the actual study sequence: two
   practice tasks, then the 16 tasks in a random rotation, with each condition's
   real dialog schedule. THIS IS A SIMULATION MODEL, NOT HUMAN DATA; it only shows
   what the paper's own hypotheses would imply for power.

N is the number of ANALYSED participants per cell; recruit about 10% more to
allow for exclusions.

    python experiments/power_user_study.py                    # full grid, ~30 min on 4 cores
    python experiments/power_user_study.py --sigma-u 1.2 --baseline 0.45   # after the pilot
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clear.human_model import SimulatedUser  # noqa: E402
from experiments.analyze_user_study import (CONDITIONS, NI_MARGIN_SELECTIVITY, gee_main_effects,  # noqa: E402
                                            holm, welch_noninferiority)
from experiments.human_sim import draw_user  # noqa: E402

STATIC = ROOT / "clear" / "ui" / "static"
KEY = json.loads((ROOT / "data" / "ui_answer_key.json").read_text())
ATTACKED = tuple(sid for sid, k in KEY.items() if k["attacked"] and not k.get("practice"))
ALPHA = 0.05
EXCLUSION_ALLOWANCE = 0.10


OUTCOMES = ("holm_sel", "holm_ev", "ev_primary", "sel_ni", "fit_ok")


def analyse(trials: pd.DataFrame) -> tuple[bool, ...]:
    """Both designs on one simulated study; returns the flags named in OUTCOMES."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = gee_main_effects(trials).set_index("effect")
    if res.p.isna().any():
        return (False,) * len(OUTCOMES)
    ph = dict(zip(("selectivity", "evidence"), holm([res.p["selectivity"], res.p["evidence"]])))
    rate = trials.groupby(["pid", "condition"]).prevented.mean().reset_index()
    sel = rate.condition.map(lambda c: CONDITIONS[c][0])
    ni = welch_noninferiority(rate.prevented[sel == 1], rate.prevented[sel == 0], NI_MARGIN_SELECTIVITY, "lower")
    return (bool(ph["selectivity"] < ALPHA), bool(ph["evidence"] < ALPHA),
            bool(res.p["evidence"] < ALPHA and res.odds_ratio["evidence"] > 1), bool(ni["supported"]), True)


def _power(hits: np.ndarray) -> dict:
    h = dict(zip(OUTCOMES, hits.T))
    return {"power_selectivity": h["holm_sel"].mean(), "power_evidence": h["holm_ev"].mean(),
            "power_both": (h["holm_sel"] & h["holm_ev"]).mean(),
            "power_ev_primary": h["ev_primary"].mean(), "power_sel_ni": h["sel_ni"].mean(),
            "power_sequence": (h["ev_primary"] & h["sel_ni"]).mean(), "fit_failures": 1 - h["fit_ok"].mean()}


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def grid_study(n: int, baseline: float, odds_ratio: float, sigma_u: float, sigma_v: float,
               rng: np.random.Generator, sel_odds_ratio: float | None = None) -> pd.DataFrame:
    b = math.log(odds_ratio)
    bs = b if sel_odds_ratio is None else math.log(sel_odds_ratio)
    b0 = _logit(baseline) + bs / 2 + b / 2         # B sits at sel = ev = -0.5
    v = rng.normal(0, sigma_v, len(ATTACKED))
    rows = []
    for cond, (s, e) in CONDITIONS.items():
        for i in range(n):
            u = rng.normal(0, sigma_u)
            for j, sid in enumerate(ATTACKED):
                lp = b0 + bs * (s - 0.5) + b * (e - 0.5) + u + v[j]
                rows.append((f"{cond}-{i}", cond, sid, int(rng.random() < 1 / (1 + math.exp(-lp)))))
    return pd.DataFrame(rows, columns=["pid", "condition", "scenario", "prevented"]).assign(attacked=True)


def _grid_cell(args) -> dict:
    n, baseline, odds_ratio, sigma_u, sigma_v, sims, seed, *rest = args
    sel_or = rest[0] if rest else None
    rng = np.random.default_rng(seed)
    hits = np.zeros((sims, len(OUTCOMES)), dtype=bool)
    rates = []
    for k in range(sims):
        d = grid_study(n, baseline, odds_ratio, sigma_u, sigma_v, rng, sel_or)
        hits[k] = analyse(d)
        rates.append(d.groupby("condition").prevented.mean())
    r = pd.concat(rates, axis=1).mean(axis=1)
    return {"n_per_cell": n, "baseline_B": baseline, "odds_ratio": odds_ratio,
            "sel_odds_ratio": odds_ratio if sel_or is None else sel_or, "sigma_u": sigma_u,
            "sigma_v": sigma_v, "sims": sims, **_power(hits),
            **{f"mean_prevention_{c}": float(r[c]) for c in CONDITIONS}}


# ------------------------------------------------------------------ model-anchored
def _schedule() -> tuple[list[dict], list[dict]]:
    data = json.loads((STATIC / "scenarios.json").read_text())
    return data.get("practice", []), data["scenarios"]


_BENCH: list[dict] | None = None


def benchmark_benign_tasks() -> list[dict]:
    """Benign held-out benchmark tasks with >= 1 side-effecting call, as dialog schedules
    (CLEAR v2 tier and side-effect flag of every call); used to model a representative task set."""
    global _BENCH
    if _BENCH is None:
        import glob
        tiers = {0: "ALLOW", 1: "NOTIFY", 2: "CONFIRM", 3: "FORCE"}
        cols = ["key", "idx", "model", "suite", "attack", "side_effecting", "tier_clear_v2"]
        c = pd.concat(pd.read_csv(f, compression="gzip", usecols=cols)
                      for f in glob.glob(str(ROOT / "data" / "derived" / "calls_*.csv.gz")))
        c = c[(c.attack == "none") & ~c.model.str.contains("repeat_user_prompt|spotlighting|tool_filter|pi_detector")]
        c = c[~((c.model == "gpt-4o-2024-05-13") & c.suite.isin(["banking", "slack"]))]   # development split
        _BENCH = []
        for k, g in c.groupby("key"):
            if g.side_effecting.sum() >= 1:
                _BENCH.append({"id": f"bench:{k}", "steps": [
                    {"type": "call", "idx": int(r.idx), "tier": tiers[int(r.tier_clear_v2)],
                     "side_effecting": bool(r.side_effecting)} for r in g.sort_values("idx").itertuples()]})
    return _BENCH


def model_participant(cond: str, practice: list[dict], tasks: list[dict],
                      rng: random.Random, mix: dict[str, float], extra_benign: int = 0,
                      benign_source: str = "study") -> list[tuple]:
    """One simulated participant. extra_benign > 0 models a longer session with that many
    additional benign tasks, in random order. benign_source="benchmark" replaces the study's
    benign tasks by tasks drawn from the held-out benchmark (a representative task set)."""
    selective, evidence = CONDITIONS[cond]
    user = SimulatedUser(draw_user(rng, mix), rng)
    if benign_source == "benchmark":
        pool = benchmark_benign_tasks()
        n_benign = len([t for t in tasks if t["id"] not in ATTACKED]) + extra_benign
        body = [t for t in tasks if t["id"] in ATTACKED] + [rng.choice(pool) for _ in range(n_benign)]
        rng.shuffle(body)
    elif extra_benign:
        benign = [t for t in tasks if t["id"] not in ATTACKED]
        body = tasks + [rng.choice(benign) for _ in range(extra_benign)]
        rng.shuffle(body)
    else:
        off = rng.randrange(len(tasks))
        body = [tasks[(i + off) % len(tasks)] for i in range(len(tasks))]
    order = practice + body
    out = []
    for sc in order:
        injected = set(KEY[sc["id"]]["injected_calls"]) if sc["id"] in KEY else set()   # practice included
        denied = set()
        for st in sc["steps"]:
            if st["type"] != "call":
                continue
            shown = st["tier"] in ("CONFIRM", "FORCE") if selective else st["side_effecting"]
            if not shown:
                continue
            kind = "force" if evidence and st["tier"] == "FORCE" else "confirm"
            if not user.respond(st["idx"] in injected, kind, bool(evidence)):
                denied.add(st["idx"])
        if sc["id"] in ATTACKED:
            out.append((cond, sc["id"], int(injected <= denied)))
    return out


def _model_cell(args) -> dict:
    n, mix_name, mix, extra, source, sims, seed = args
    practice, tasks = _schedule()
    rng = random.Random(seed)
    hits = np.zeros((sims, len(OUTCOMES)), dtype=bool)
    rates = []
    for k in range(sims):
        rows = []
        for cond in CONDITIONS:
            for i in range(n):
                rows += [(f"{cond}-{i}",) + r for r in model_participant(cond, practice, tasks, rng, mix, extra, source)]
        d = pd.DataFrame(rows, columns=["pid", "condition", "scenario", "prevented"]).assign(attacked=True)
        hits[k] = analyse(d)
        rates.append(d.groupby("condition").prevented.mean())
    r = pd.concat(rates, axis=1).mean(axis=1)
    return {"population": mix_name, "benign_tasks": source, "session_tasks": len(tasks) + extra,
            "n_per_cell": n, "sims": sims, **_power(hits),
            **{f"mean_prevention_{c}": float(r[c]) for c in CONDITIONS}}


def recommend(grid: pd.DataFrame, target: float, metric: str) -> pd.DataFrame:
    rows = []
    for key, g in grid.groupby(["baseline_B", "odds_ratio", "sel_odds_ratio", "sigma_u"]):
        ok = g[g[metric] >= target].n_per_cell
        n = int(ok.min()) if len(ok) else None
        rows.append({"baseline_B": key[0], "evidence_odds_ratio": key[1], "sel_odds_ratio": key[2],
                     "sigma_u": key[3], "power_metric": metric,
                     "min_analysed_per_cell": n,
                     "recruit_per_cell": math.ceil(n / (1 - EXCLUSION_ALLOWANCE)) if n else None})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-cell", type=int, nargs="+", default=[30, 40, 50, 60, 80])
    ap.add_argument("--baseline", type=float, nargs="+", default=[0.3, 0.5, 0.7],
                    help="prevention probability of a typical participant in confirm-all (B)")
    ap.add_argument("--odds-ratio", type=float, nargs="+", default=[1.5, 2.0, 2.5],
                    help="odds ratio of the evidence effect (and of selectivity unless --sel-odds-ratio is given)")
    ap.add_argument("--sel-odds-ratio", type=float, nargs="+", default=None,
                    help="odds ratio of the selectivity effect; 1.0 = no benefit (the non-inferiority case)")
    ap.add_argument("--design", choices=["revised", "original"], default="revised",
                    help="which design the sample-size recommendation targets")
    ap.add_argument("--sigma-u", type=float, nargs="+", default=[0.5, 1.0, 1.5],
                    help="between-participant SD on the logit scale")
    ap.add_argument("--sigma-v", type=float, default=0.5, help="scenario SD on the logit scale")
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--model-sims", type=int, default=400)
    ap.add_argument("--target", type=float, default=0.80)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--skip-model", action="store_true")
    ap.add_argument("--skip-grid", action="store_true")
    ap.add_argument("--extra-benign", type=int, nargs="+", default=[0],
                    help="model-anchored only: extra benign tasks per session (longer sessions)")
    ap.add_argument("--benign-source", choices=["study", "benchmark"], nargs="+", default=["study"],
                    help="model-anchored only: the study's 12 benign tasks, or tasks drawn from the benchmark")
    ap.add_argument("--out", default=str(ROOT / "results" / "power"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sel_ors = args.sel_odds_ratio or [None]
    cells = list(product(args.n_per_cell, args.baseline, args.odds_ratio, args.sigma_u, sel_ors))
    jobs = [(n, b, o, s, args.sigma_v, args.sims, args.seed + i, so) for i, (n, b, o, s, so) in enumerate(cells)]
    mixes = {"balanced": {"novice": 1 / 3, "intermediate": 1 / 3, "security_aware": 1 / 3},
             "mostly_novice": {"novice": 0.6, "intermediate": 0.3, "security_aware": 0.1}}
    mjobs = [(n, name, mix, extra, src, args.model_sims, args.seed + 10_000 + i)
             for i, (n, (name, mix), extra, src) in enumerate(product(args.n_per_cell, mixes.items(),
                                                                         args.extra_benign, args.benign_source))]
    with ProcessPoolExecutor(args.workers) as ex:
        grid = pd.DataFrame([] if args.skip_grid else ex.map(_grid_cell, jobs))
        model = pd.DataFrame([] if args.skip_model else ex.map(_model_cell, mjobs))
    rec = pd.DataFrame()
    if len(grid):
        grid.to_csv(out / "power_grid.csv", index=False)
        rec = recommend(grid, args.target, "power_sequence" if args.design == "revised" else "power_both")
        rec.to_csv(out / "power_recommendation.csv", index=False)
    if len(model):
        name = ("power_model_anchored.csv" if args.extra_benign == [0] and args.benign_source == ["study"]
                else "power_model_design_variants.csv")
        model.to_csv(out / name, index=False)
    meta = {k: v for k, v in vars(args).items()}
    meta["alpha"], meta["exclusion_allowance"] = ALPHA, EXCLUSION_ALLOWANCE
    variant = args.extra_benign != [0] or args.benign_source != ["study"]
    tag = "" if not args.skip_grid else "_design_variants" if variant else "_model"
    (out / f"power_settings{tag}.json").write_text(json.dumps(meta, indent=1))
    pd.set_option("display.width", 200)
    if len(rec):
        print(rec.to_string(index=False))
    if len(model):
        print(model.to_string(index=False))


if __name__ == "__main__":
    main()
