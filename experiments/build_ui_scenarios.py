"""Build interactive UI / user-study scenarios from real AgentDojo agent traces.

Each scenario is a recorded agent run (prompt, tool calls, tool outputs, final
answer) annotated with CLEAR's assessment of every tool call *as computed
online* (before the call's result is seen). Ground-truth labels (whether a
call was injected) are written to a separate answer-key file so that the
participant-facing payload never contains them.

Selection is deterministic (seeded) and restricted to the held-out suites
(travel, workspace) plus banking, drawn from GPT-4o runs:
  * benign scenarios: benign runs that contain >= 1 side-effecting call
  * attacked scenarios: important_instructions runs in which the agent
    actually executed the injected action (AgentDojo security == True)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clear.mediator import Mediator, ToolCall  # noqa: E402
from clear.risk import Tier  # noqa: E402
from experiments.evaluate import necessity_labels, signature_labels  # noqa: E402
from experiments.traces import DEFAULT_RUNS, Replayer, iter_episodes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def annotate(ep, rep, med: Mediator) -> tuple[dict, dict]:
    env = med.start_task(ep.user_prompt, ep.system_prompt)
    steps = []
    for kind, x in ep.events():
        if kind == "call":
            a = med.assess(ToolCall(x.function, x.args, x.id))
            prov = {}
            for arg, atts in a.arg_provenance.items():
                prov[arg] = [{
                    "value": at.value, "origin": at.origin,
                    "sources": [med.ledger.sources[i].label for i in at.sources[:3]],
                    "snippet": med.ledger.sources[at.sources[0]].snippet(at.value) if at.sources else "",
                } for at in atts]
            steps.append({"type": "call", "idx": x.idx, "function": x.function, "args": x.args,
                          "tier": a.tier.name, "risk": round(a.risk, 3), "features": a.features,
                          "reasons": a.reasons, "provenance": prov, "capability": a.spec.capability,
                          "sensitivity": a.spec.sensitivity, "reversible": a.spec.reversible,
                          "side_effecting": a.spec.is_side_effecting})
        else:
            c, text = x
            med.observe_result(ToolCall(c.function, c.args, c.id), text)
            s = med.ledger.sources[-1]
            steps.append({"type": "result", "idx": c.idx, "function": c.function, "text": text[:4000],
                          "trust": s.trust, "source_label": s.label,
                          "injection_score": round(s.injection_score, 3),
                          "spans": [{"start": sp.start, "end": sp.end, "label": sp.label}
                                    for sp in s.injection_spans if sp.end <= 4000]})
    final = ep.final_output()
    steps.append({"type": "final", "text": "\n".join(str(b.get("content") or "") for b in final)})
    calls = ep.calls()
    injected: set[int] = set()
    if ep.attacked:
        _, base_s = rep.run(ep)
        injected = signature_labels(ep, calls, rep, med.manifest) | necessity_labels(ep, calls, rep, med.manifest, bool(base_s))
    scenario = {"suite": ep.suite, "user_task": ep.user_task, "model": ep.model, "prompt": ep.user_prompt,
                "envelope": env.to_dict(), "steps": steps}
    key = {"attacked": ep.attacked, "injection_task": ep.injection_task, "attack": ep.attack,
           "injected_calls": sorted(injected)}
    return scenario, key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=DEFAULT_RUNS)
    ap.add_argument("--model", default="gpt-4o-2024-05-13")
    ap.add_argument("--n-benign", type=int, default=12)
    ap.add_argument("--n-attacked", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "clear" / "ui" / "static" / "scenarios.json"))
    ap.add_argument("--key-out", default=str(ROOT / "data" / "ui_answer_key.json"))
    args = ap.parse_args()
    rng = random.Random(args.seed)
    rep = Replayer("v1")
    suites = {"banking", "travel", "workspace"}
    benign, attacked = [], []
    med = Mediator.default()
    for ep in iter_episodes(args.runs, args.model, {"important_instructions", "none"}):
        if ep.suite not in suites:
            continue
        side = [c for c in ep.calls() if med.manifest.get(c.function).is_side_effecting]
        if not side:
            continue
        if ep.attacked:
            if ep.security:
                attacked.append(ep)
        elif ep.utility:
            benign.append(ep)
    rng.shuffle(benign)
    rng.shuffle(attacked)
    # at most one attacked scenario per injection task, for variety
    chosen_att, seen = [], set()
    for ep in attacked:
        if (ep.suite, ep.injection_task) in seen:
            continue
        seen.add((ep.suite, ep.injection_task))
        chosen_att.append(ep)
        if len(chosen_att) == args.n_attacked:
            break
    chosen = benign[: args.n_benign] + chosen_att
    rng.shuffle(chosen)
    scenarios, keys = [], {}
    for i, ep in enumerate(chosen):
        sc, key = annotate(ep, rep, Mediator.default())
        sc["id"] = f"S{i + 1:02d}"
        scenarios.append(sc)
        keys[sc["id"]] = {**key, "source": ep.key}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        cfg = Mediator.default().cfg
        json.dump({"version": 1, "config": {k: cfg[k] for k in ("risk", "tiers", "injection_signal")},
                   "scenarios": scenarios}, fh, indent=1)
    Path(args.key_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.key_out, "w") as fh:
        json.dump(keys, fh, indent=1)
    print(f"wrote {len(scenarios)} scenarios ({sum(k['attacked'] for k in keys.values())} attacked)")
    for sc in scenarios:
        tiers = [s["tier"] for s in sc["steps"] if s["type"] == "call"]
        print(sc["id"], sc["suite"], keys[sc["id"]]["attacked"], tiers)


if __name__ == "__main__":
    main()
