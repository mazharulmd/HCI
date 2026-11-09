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
        writer = csv.DictWriter(f, fieldnames=["scenario_id", "condition", "decision", "tool_executed", "attack_success", "safe_outcome", "risk_score", "risk_level", "decision_reason"], lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({**{k: r[k] for k in writer.fieldnames if k not in {"risk_score", "risk_level"}}, "risk_score": r["risk"]["score"], "risk_level": r["risk"]["level"]})
    (out / "summary.json").write_text(json.dumps({"evidence_type": "deterministic scripted scenario evaluation; not user-study data", "summaries": summaries}, indent=2) + "\n", encoding="utf-8")
    # Keep the output dependency-free and explicitly label it as fixture-only.
    colors = {"attack_success_rate": "#b64242", "benign_block_rate": "#356a9a"}
    labels = {"attack_success_rate": "Attack success", "benign_block_rate": "Benign blocks"}
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="410" viewBox="0 0 900 410">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#172235}.small{font-size:13px}.title{font-size:20px;font-weight:bold}.axis{stroke:#aab6c2;stroke-width:1}</style>',
           '<text x="30" y="32" class="title">Scripted policy outcomes on constructed fixtures only</text>',
           '<text x="30" y="54" class="small">n=8 scenarios per condition; three attack-labeled fixtures; not user-study or deployment evidence</text>']
    x0, chart_w, top, row_h = 245, 480, 95, 70
    for tick in range(0, 101, 20):
        x = x0 + chart_w * tick / 100
        svg.append(f'<line x1="{x:.1f}" y1="80" x2="{x:.1f}" y2="355" class="axis"/>')
        svg.append(f'<text x="{x:.1f}" y="376" class="small" text-anchor="middle">{tick}%</text>')
    for i, summary in enumerate(summaries):
        y = top + i * row_h
        svg.append(f'<text x="{x0-14}" y="{y+23}" class="small" text-anchor="end">{summary["condition"]}</text>')
        for j, metric in enumerate(("attack_success_rate", "benign_block_rate")):
            value = summary[metric]
            yy = y + j * 22
            width = chart_w * value
            svg.append(f'<rect x="{x0}" y="{yy}" width="{width:.1f}" height="16" rx="3" fill="{colors[metric]}"/>')
            svg.append(f'<text x="{x0+chart_w+12}" y="{yy+13}" class="small">{value:.0%} {labels[metric]}</text>')
    svg.append('<text x="450" y="401" class="small" text-anchor="middle">Metric value</text></svg>')
    (out / "scripted_fixture_metrics.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))

if __name__ == "__main__":
    main()
