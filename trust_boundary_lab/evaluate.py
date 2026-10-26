"""Reproducible scripted evaluation; results are not human-subject evidence."""

import argparse
import csv
import json
from pathlib import Path

from .core import make_decision
from .scenarios import SCENARIOS

CONDITIONS = ("baseline", "risk_badge", "provenance_consent", "combined")


def run_evaluation() -> tuple[list[dict], list[dict]]:
    rows = [make_decision(s, c) for s in SCENARIOS for c in CONDITIONS]
    summaries = []
    for condition in CONDITIONS:
        subset = [r for r in rows if r["condition"] == condition]
        malicious = [r for r in subset if r["scenario_id"] in {s.id for s in SCENARIOS if s.attack}]
        benign = [r for r in subset if r["scenario_id"] in {s.id for s in SCENARIOS if not s.attack}]
        summaries.append({"condition": condition, "n": len(subset), "attack_success_rate": sum(r["attack_success"] for r in malicious) / max(1, len(malicious)),
                          "defense_effectiveness": sum(not r["attack_success"] for r in malicious) / max(1, len(malicious)),
                          "benign_block_rate": sum(not r["tool_executed"] for r in benign) / max(1, len(benign)),
                          "decision_accuracy": sum(r["decision"] == r["expected_decision"] for r in subset) / max(1, len(subset))})
    return rows, summaries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    rows, summaries = run_evaluation()
    with (out / "scenario_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario_id", "condition", "decision", "tool_executed", "attack_success", "safe_outcome", "risk_score", "risk_level", "decision_reason"])
        writer.writeheader()
        for r in rows:
            writer.writerow({**{k: r[k] for k in writer.fieldnames if k not in {"risk_score", "risk_level"}}, "risk_score": r["risk"]["score"], "risk_level": r["risk"]["level"]})
    (out / "summary.json").write_text(json.dumps({"evidence_type": "deterministic scripted scenario evaluation; not user-study data", "summaries": summaries}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))

if __name__ == "__main__":
    main()
