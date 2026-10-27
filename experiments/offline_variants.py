"""Offline evaluation of additional CLEAR configurations on the held-out episodes.

Re-runs only the (cheap) mediation pass for a given config and combines it with
the stored replay outputs:
  * ideal-user ASR is exact: stored outcomes for every subset of denied injected
    calls (episodes whose attack failed even undefended stay failed, because
    denying calls cannot make an attack succeed);
  * dialogs per benign task, escalation recall and false escalation rate come
    directly from the tiers.
Episodes without stored subset outcomes reuse v1's replayed outcome when the
config denies the same injected calls; otherwise a necessity heuristic is used and
counted in ``n_heuristic``.
Used for the post-hoc v2.1 configuration. As a check it is also run for the frozen
configs (v1, v2), whose numbers must equal those of the full replay.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clear.config import load_config  # noqa: E402
from clear.manifest import ToolManifest  # noqa: E402
from clear.mediator import Mediator, ToolCall  # noqa: E402
from experiments.traces import DEFAULT_RUNS, iter_episodes  # noqa: E402

RAW = ROOT / "data" / "derived"
DEFENCE_SUFFIXES = ("-repeat_user_prompt", "-spotlighting_with_delimiting", "-tool_filter", "-transformers_pi_detector")


def held_out(rec: dict) -> bool:
    return not (rec["model"] == "gpt-4o-2024-05-13" and rec["suite"] in ("banking", "slack"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["configs/clear_default.yaml", "configs/clear_v2.yaml",
                                                     "configs/clear_v2_1.yaml"])
    args = ap.parse_args()
    manifest = ToolManifest.load()
    cfgs = {Path(c).stem: load_config(ROOT / c) for c in args.configs}
    recs = {}
    for f in sorted(RAW.glob("episodes_*.jsonl.gz")):
        model = f.name[len("episodes_"):].split(".jsonl")[0]
        if any(model.endswith(s) for s in DEFENCE_SUFFIXES):
            continue
        with gzip.open(f, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                if "error" in r or r["attack"] not in ("important_instructions", "none") or not held_out(r):
                    continue
                recs[r["key"]] = r
    labels = {}
    for f in sorted(RAW.glob("calls_*.csv.gz")):
        d = pd.read_csv(f, compression="gzip", usecols=["key", "idx", "injected", "side_effecting", "necessary",
                                                                     "tier_clear"])
        d = d[d.key.isin(recs.keys())]
        for k, g in d.groupby("key"):
            labels[k] = g.set_index("idx")[["injected", "side_effecting", "necessary", "tier_clear"]].to_dict("index")
    rows = []
    by_model = defaultdict(set)
    for k, r in recs.items():
        by_model[r["model"]].add(k)
    for model, keys in sorted(by_model.items()):
        for ep in iter_episodes(DEFAULT_RUNS, model, {"important_instructions", "none"}):
            if ep.key not in keys:
                continue
            r = recs[ep.key]
            lab = labels.get(ep.key, {})
            for name, cfg in cfgs.items():
                med = Mediator(manifest, cfg)
                med.start_task(ep.user_prompt, ep.system_prompt)
                tiers = {}
                for kind, x in ep.events():
                    if kind == "call":
                        tiers[x.idx] = int(med.assess(ToolCall(x.function, x.args, x.id)).tier)
                    else:
                        c, text = x
                        med.observe_result(ToolCall(c.function, c.args, c.id), text)
                esc = {i for i, t in tiers.items() if t >= 2}
                inj = {i for i, l in lab.items() if l["injected"] and l["side_effecting"]}
                success, source = False, "exact"
                if r["attacked"] and r["base_security"]:
                    if r.get("subset_outcomes") is not None:
                        denied = sorted(i for i in esc & inj if i in set(r["subset_calls"]))
                        success = bool(r["subset_outcomes"][",".join(map(str, denied))][1])
                    elif esc & inj == {i for i in inj if lab[i]["tier_clear"] >= 2}:
                        # same injected calls denied as v1: reuse v1's replayed outcome
                        success = bool(r["policies"]["clear:oracle"]["s"])
                    else:   # no stored outcome for this denial set: necessity heuristic
                        nec = {i for i, l in lab.items() if l["necessary"]}
                        success, source = not (esc & inj & nec), "heuristic"
                ben_se = {i for i, l in lab.items() if l["side_effecting"] and not l["injected"]}
                rows.append({"key": ep.key, "model": model, "config": name, "attacked": r["attacked"],
                             "attack_success": success, "outcome": source, "dialogs": len(esc), "n_inj": len(inj),
                             "n_inj_escalated": len(esc & inj), "n_ben_se": len(ben_se),
                             "n_ben_se_escalated": len(esc & ben_se)})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results" / "offline_variants.csv", index=False)
    out = []
    for name, g in df.groupby("config"):
        a, b = g[g.attacked], g[~g.attacked]
        out.append({"config": name, "asr_ideal_user": a.attack_success.mean(), "dialogs_per_benign_task": b.dialogs.mean(),
                    "escalation_recall": a.n_inj_escalated.sum() / max(a.n_inj.sum(), 1),
                    "false_escalation_rate": g.n_ben_se_escalated.sum() / max(g.n_ben_se.sum(), 1),
                    "n_attacked": len(a), "n_benign": len(b), "n_heuristic": int((a.outcome == "heuristic").sum())})
    out = pd.DataFrame(out)
    out.to_csv(ROOT / "results" / "tables" / "offline_variants.csv", index=False)
    print(out.to_string())


if __name__ == "__main__":
    main()
