"""Hypothesis-generating simulation of human confirmation decisions (RQ4).

Combines the *real* per-call escalation decisions and *ground-truth*
outcomes from the trace replay with the parametric human model in
``clear.human_model``. A simulated person works through sessions of agent
tasks (a fraction ``prevalence`` of which contain a prompt injection) and
answers every confirmation dialog the mediation policy raises. We report the
end-to-end attack success rate (ASR), benign utility, and dialogs per task.

Results of this script are model-based what-if analyses and are labelled as
such everywhere they are reported.
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clear.human_model import HumanParams, SimulatedUser  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE_MODELS_EXCLUDE = ("-repeat_user_prompt", "-spotlighting", "-tool_filter", "-transformers_pi_detector")

# policy -> how dialogs are presented
POLICIES = {
    "confirm_all": {"evidence": False, "tiers": False},
    "confirm_all_evidence": {"evidence": True, "tiers": False},
    "clear_no_evidence": {"evidence": False, "tiers": False},
    "clear": {"evidence": True, "tiers": True},
}


def load_pool(raw: Path, attacks=("important_instructions", "none"), suites=None) -> list[dict]:
    pool = []
    if not any(raw.glob("episodes_*.jsonl*")):
        raw = ROOT / "data" / "derived"
    for ep_file in sorted(raw.glob("episodes_*.jsonl*")):
        model = ep_file.name[len("episodes_"):].split(".jsonl")[0]
        if any(x in model for x in BASE_MODELS_EXCLUDE):
            continue
        calls_file = raw / f"calls_{model}.csv.gz"
        if not calls_file.exists():
            continue
        calls = pd.read_csv(calls_file, compression="gzip")
        by_key = {k: g.sort_values("idx") for k, g in calls.groupby("key")}
        with (gzip.open(ep_file, "rt") if ep_file.suffix == ".gz" else open(ep_file)) as fh:
            for line in fh:
                rec = json.loads(line)
                if "error" in rec or rec["attack"] not in attacks:
                    continue
                if suites and rec["suite"] not in suites:
                    continue
                g = by_key.get(rec["key"])
                rows = [] if g is None else g.to_dict("records")
                dialogs = {}
                for pol in POLICIES:
                    dl = []
                    for r in rows:
                        if pol.startswith("confirm_all"):
                            if r["dec_confirm_all"] == "confirm":
                                dl.append((r["idx"], bool(r["injected"]), "confirm"))
                        else:
                            if r["tier_clear"] >= 2:
                                kind = "force" if (r["tier_clear"] == 3 and POLICIES[pol]["tiers"]) else "confirm"
                                dl.append((r["idx"], bool(r["injected"]), kind))
                    dialogs[pol] = dl
                pool.append({
                    "key": rec["key"], "model": model, "suite": rec["suite"], "attacked": rec["attacked"],
                    "base_u": bool(rec["base_utility"]), "base_s": bool(rec["base_security"]) if rec["attacked"] else False,
                    "subset_calls": rec.get("subset_calls"), "subset_outcomes": rec.get("subset_outcomes"),
                    "necessary": {int(r["idx"]) for r in rows if r["necessary"]},
                    "dialogs": dialogs,
                })
    return pool


def episode_outcome(ep: dict, denied: list[tuple[int, bool]]) -> tuple[bool, bool]:
    """(utility, security) after the user denied the given (idx, injected) calls."""
    benign_denied = any(not inj for _, inj in denied)
    if not ep["attacked"]:
        return ep["base_u"] and not benign_denied, False
    inj_denied = sorted(i for i, inj in denied if inj)
    if ep["subset_outcomes"] is not None:
        allowed = set(ep["subset_calls"])
        key = ",".join(str(i) for i in inj_denied if i in allowed)
        u, s = ep["subset_outcomes"][key]
        u, s = bool(u), bool(s)
    else:  # fall back to causal-necessity approximation
        s = ep["base_s"] and not (set(inj_denied) & ep["necessary"])
        u = ep["base_u"]
    return u and not benign_denied, s


# Heterogeneous population (E3): three expertise strata. The idea of strata comes from the
# PROV-Guard iteration; here each stratum is a *distribution* of SDT/habituation parameters,
# and conclusions are checked across the whole mixture rather than asserted per stratum.
STRATA = {
    "novice":         HumanParams(d0=0.6, d_prov=0.8, d_force=0.5, criterion=-0.3, a_min=0.2, lam=7.0),
    "intermediate":   HumanParams(d0=1.0, d_prov=1.0, d_force=0.5, criterion=0.0, a_min=0.3, lam=15.0),
    "security_aware": HumanParams(d0=1.5, d_prov=1.2, d_force=0.5, criterion=0.3, a_min=0.45, lam=30.0),
}


def draw_user(rng: random.Random, mix: dict[str, float], jitter: float = 0.15) -> HumanParams:
    name = rng.choices(list(mix), weights=list(mix.values()))[0]
    b = STRATA[name]
    j = lambda v: max(0.0, v * (1 + rng.gauss(0, jitter)))  # noqa: E731
    return HumanParams(d0=j(b.d0), d_prov=j(b.d_prov), d_force=j(b.d_force),
                       criterion=b.criterion + rng.gauss(0, jitter * 0.5),
                       a_min=min(1.0, j(b.a_min)), lam=max(1.0, j(b.lam)))


def simulate(pool: list[dict], policy: str, params: HumanParams, prevalence: float,
             sessions: int, session_len: int, seed: int, mix: dict[str, float] | None = None) -> dict:
    rng = random.Random(seed)
    attacked = [e for e in pool if e["attacked"]]
    benign = [e for e in pool if not e["attacked"]]
    evidence = POLICIES[policy]["evidence"]
    acc = defaultdict(float)
    cnt = defaultdict(int)
    for _ in range(sessions):
        p = draw_user(rng, mix) if mix else params
        user = SimulatedUser(p, random.Random(rng.random()))
        for _ in range(session_len):
            is_att = rng.random() < prevalence
            ep = rng.choice(attacked if is_att else benign)
            denied = []
            n_dialogs = 0
            correct = 0
            for idx, inj, kind in ep["dialogs"][policy]:
                approve = user.respond(inj, kind, evidence)
                n_dialogs += 1
                correct += (approve != inj)
                if not approve:
                    denied.append((idx, inj))
            u, s = episode_outcome(ep, denied)
            g = "att" if is_att else "ben"
            acc[f"{g}_u"] += u
            acc[f"{g}_dialogs"] += n_dialogs
            acc["dialogs"] += n_dialogs
            acc["correct"] += correct
            cnt[g] += 1
            if is_att:
                acc["asr"] += s
    out = {
        "e2e_asr": acc["asr"] / max(cnt["att"], 1),
        "utility_under_attack": acc["att_u"] / max(cnt["att"], 1),
        "benign_utility": acc["ben_u"] / max(cnt["ben"], 1),
        "dialogs_per_benign_task": acc["ben_dialogs"] / max(cnt["ben"], 1),
        "dialogs_per_task": acc["dialogs"] / max(cnt["att"] + cnt["ben"], 1),
        "dialog_accuracy": acc["correct"] / max(acc["dialogs"], 1),
        "n_attacked": cnt["att"], "n_benign": cnt["ben"],
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--out", default=str(ROOT / "results" / "human_sim.csv"))
    ap.add_argument("--sessions", type=int, default=300)
    ap.add_argument("--session-len", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261026)
    args = ap.parse_args()
    pool = load_pool(Path(args.raw))
    print(f"pool: {len(pool)} episodes ({sum(e['attacked'] for e in pool)} attacked)")
    base = HumanParams()
    rows = []

    def run(tag, params, prevalence=0.1):
        for pol in POLICIES:
            r = simulate(pool, pol, params, prevalence, args.sessions, args.session_len, args.seed)
            rows.append({"sweep": tag, "policy": pol, "prevalence": prevalence, **asdict(params), **r})

    # 1) default point
    run("default", base)
    # 2) one-at-a-time sweeps
    for lam in (3.0, 7.0, 15.0, 30.0, 60.0, float("inf")):
        run("lam", replace(base, lam=lam))
    for d_prov in (0.0, 0.5, 1.0, 1.5):
        run("d_prov", replace(base, d_prov=d_prov))
    for d0 in (0.5, 1.0, 1.5, 2.0):
        run("d0", replace(base, d0=d0))
    for a_min in (0.0, 0.1, 0.3, 0.6, 1.0):
        run("a_min", replace(base, a_min=a_min))
    for c in (-1.0, -0.5, 0.0, 0.5, 1.0):
        run("criterion", replace(base, criterion=c))
    for prev in (0.02, 0.05, 0.1, 0.25, 0.5):
        run("prevalence", base, prevalence=prev)
    # 2b) heterogeneous populations (E3)
    for mix_name, mix in {"balanced": {"novice": 1, "intermediate": 1, "security_aware": 1},
                          "mostly_novice": {"novice": 3, "intermediate": 1, "security_aware": 0.5},
                          "mostly_expert": {"novice": 0.5, "intermediate": 1, "security_aware": 3}}.items():
        for pol in POLICIES:
            r = simulate(pool, pol, base, 0.1, args.sessions, args.session_len, args.seed, mix=mix)
            rows.append({"sweep": "population", "population": mix_name, "policy": pol, "prevalence": 0.1,
                         **asdict(base), **r})
    # 3) full factorial robustness grid
    for d0, d_prov, lam, a_min, c in itertools.product((0.5, 1.0, 1.5), (0.0, 0.5, 1.0),
                                                       (5.0, 15.0, 50.0), (0.1, 0.3, 0.6), (-0.5, 0.0, 0.5)):
        run("grid", HumanParams(d0=d0, d_prov=d_prov, lam=lam, a_min=a_min, criterion=c))
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(df[df.sweep == "default"].to_string())


if __name__ == "__main__":
    main()
