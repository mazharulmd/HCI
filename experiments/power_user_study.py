"""Simulation-based power analysis for the lab user study (protocol section 4).

Every simulated study is analysed with the pre-registered primary analysis itself
(experiments/analyze_user_study.gee_main_effects: logistic GEE clustered by
participant, scenario as a fixed effect, Holm over the two main effects). Power is
the share of simulated studies in which a main effect has Holm-adjusted p < .05.
A fit that fails (for example under separation) counts as a non-rejection.

Two data-generating models:

1. Assumption grid (model-free). For participant i and attacked scenario j,
       logit P(prevented) = b0 + b_s * sel_i + b_e * ev_i + u_i + v_j,
   with effect-coded sel, ev in {-0.5, +0.5}, so exp(b_s) and exp(b_e) are the
   odds ratios between factor levels; u_i ~ N(0, sigma_u^2) (between-participant
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
from experiments.analyze_user_study import CONDITIONS, gee_main_effects  # noqa: E402
from experiments.human_sim import draw_user  # noqa: E402

STATIC = ROOT / "clear" / "ui" / "static"
KEY = json.loads((ROOT / "data" / "ui_answer_key.json").read_text())
ATTACKED = tuple(sid for sid, k in KEY.items() if k["attacked"] and not k.get("practice"))
ALPHA = 0.05
EXCLUSION_ALLOWANCE = 0.10


def analyse(trials: pd.DataFrame) -> tuple[bool, bool, bool]:
    """Pre-registered primary analysis; returns (selectivity rejected, evidence rejected, fit ok)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = gee_main_effects(trials)
    if "p_holm" not in res or res.p_holm.isna().all():
        return False, False, False
    p = dict(zip(res.effect, res.p_holm))
    return bool(p["selectivity (H-U1)"] < ALPHA), bool(p["evidence (H-U2)"] < ALPHA), True


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def grid_study(n: int, baseline: float, odds_ratio: float, sigma_u: float, sigma_v: float,
               rng: np.random.Generator) -> pd.DataFrame:
    b = math.log(odds_ratio)
    b0 = _logit(baseline) + b / 2 + b / 2          # B sits at sel = ev = -0.5
    v = rng.normal(0, sigma_v, len(ATTACKED))
    rows = []
    for cond, (s, e) in CONDITIONS.items():
        for i in range(n):
            u = rng.normal(0, sigma_u)
            for j, sid in enumerate(ATTACKED):
                lp = b0 + b * (s - 0.5) + b * (e - 0.5) + u + v[j]
                rows.append((f"{cond}-{i}", cond, sid, int(rng.random() < 1 / (1 + math.exp(-lp)))))
    return pd.DataFrame(rows, columns=["pid", "condition", "scenario", "prevented"]).assign(attacked=True)


def _grid_cell(args) -> dict:
    n, baseline, odds_ratio, sigma_u, sigma_v, sims, seed = args
    rng = np.random.default_rng(seed)
    hits = np.zeros((sims, 3), dtype=bool)
    rates = []
    for k in range(sims):
        d = grid_study(n, baseline, odds_ratio, sigma_u, sigma_v, rng)
        hits[k] = analyse(d)
        rates.append(d.groupby("condition").prevented.mean())
    r = pd.concat(rates, axis=1).mean(axis=1)
    return {"n_per_cell": n, "baseline_B": baseline, "odds_ratio": odds_ratio, "sigma_u": sigma_u,
            "sigma_v": sigma_v, "sims": sims,
            "power_selectivity": hits[:, 0].mean(), "power_evidence": hits[:, 1].mean(),
            "power_both": (hits[:, 0] & hits[:, 1]).mean(), "fit_failures": 1 - hits[:, 2].mean(),
            **{f"mean_prevention_{c}": float(r[c]) for c in CONDITIONS}}


# ------------------------------------------------------------------ model-anchored
def _schedule() -> tuple[list[dict], list[dict]]:
    data = json.loads((STATIC / "scenarios.json").read_text())
    return data.get("practice", []), data["scenarios"]


def model_participant(cond: str, practice: list[dict], tasks: list[dict],
                      rng: random.Random, mix: dict[str, float]) -> list[tuple]:
    selective, evidence = CONDITIONS[cond]
    user = SimulatedUser(draw_user(rng, mix), rng)
    off = rng.randrange(len(tasks))
    order = practice + [tasks[(i + off) % len(tasks)] for i in range(len(tasks))]
    out = []
    for sc in order:
        injected = set(KEY[sc["id"]]["injected_calls"])   # practice tasks included
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
    n, mix_name, mix, sims, seed = args
    practice, tasks = _schedule()
    rng = random.Random(seed)
    hits = np.zeros((sims, 3), dtype=bool)
    rates = []
    for k in range(sims):
        rows = []
        for cond in CONDITIONS:
            for i in range(n):
                rows += [(f"{cond}-{i}",) + r for r in model_participant(cond, practice, tasks, rng, mix)]
        d = pd.DataFrame(rows, columns=["pid", "condition", "scenario", "prevented"]).assign(attacked=True)
        hits[k] = analyse(d)
        rates.append(d.groupby("condition").prevented.mean())
    r = pd.concat(rates, axis=1).mean(axis=1)
    return {"population": mix_name, "n_per_cell": n, "sims": sims,
            "power_selectivity": hits[:, 0].mean(), "power_evidence": hits[:, 1].mean(),
            "power_both": (hits[:, 0] & hits[:, 1]).mean(), "fit_failures": 1 - hits[:, 2].mean(),
            **{f"mean_prevention_{c}": float(r[c]) for c in CONDITIONS}}


def recommend(grid: pd.DataFrame, target: float) -> pd.DataFrame:
    rows = []
    for key, g in grid.groupby(["baseline_B", "odds_ratio", "sigma_u"]):
        ok = g[g.power_both >= target].n_per_cell
        n = int(ok.min()) if len(ok) else None
        rows.append({"baseline_B": key[0], "odds_ratio": key[1], "sigma_u": key[2],
                     "min_analysed_per_cell": n,
                     "recruit_per_cell": math.ceil(n / (1 - EXCLUSION_ALLOWANCE)) if n else None})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-cell", type=int, nargs="+", default=[30, 40, 50, 60, 80])
    ap.add_argument("--baseline", type=float, nargs="+", default=[0.3, 0.5, 0.7],
                    help="prevention probability of a typical participant in confirm-all (B)")
    ap.add_argument("--odds-ratio", type=float, nargs="+", default=[1.5, 2.0, 2.5],
                    help="odds ratio of each main effect (selectivity and evidence)")
    ap.add_argument("--sigma-u", type=float, nargs="+", default=[0.5, 1.0, 1.5],
                    help="between-participant SD on the logit scale")
    ap.add_argument("--sigma-v", type=float, default=0.5, help="scenario SD on the logit scale")
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--model-sims", type=int, default=400)
    ap.add_argument("--target", type=float, default=0.80)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--skip-model", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results" / "power"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cells = list(product(args.n_per_cell, args.baseline, args.odds_ratio, args.sigma_u))
    jobs = [(n, b, o, s, args.sigma_v, args.sims, args.seed + i) for i, (n, b, o, s) in enumerate(cells)]
    mixes = {"balanced": {"novice": 1 / 3, "intermediate": 1 / 3, "security_aware": 1 / 3},
             "mostly_novice": {"novice": 0.6, "intermediate": 0.3, "security_aware": 0.1}}
    mjobs = [(n, name, mix, args.model_sims, args.seed + 10_000 + i)
             for i, (n, (name, mix)) in enumerate(product(args.n_per_cell, mixes.items()))]
    with ProcessPoolExecutor(args.workers) as ex:
        grid = pd.DataFrame(ex.map(_grid_cell, jobs))
        model = pd.DataFrame([] if args.skip_model else ex.map(_model_cell, mjobs))
    grid.to_csv(out / "power_grid.csv", index=False)
    rec = recommend(grid, args.target)
    rec.to_csv(out / "power_recommendation.csv", index=False)
    if len(model):
        model.to_csv(out / "power_model_anchored.csv", index=False)
    meta = {k: v for k, v in vars(args).items()}
    meta["alpha"], meta["exclusion_allowance"] = ALPHA, EXCLUSION_ALLOWANCE
    (out / "power_settings.json").write_text(json.dumps(meta, indent=1))
    pd.set_option("display.width", 200)
    print(rec.to_string(index=False))
    if len(model):
        print(model.to_string(index=False))


if __name__ == "__main__":
    main()
