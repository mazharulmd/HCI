# Trust Boundary Lab

An early, local HCI security prototype for studying how people review AI-agent tool calls when the proposed action is influenced by external content. It currently uses a deterministic simulator, not a production AI agent or real integrations. No real files, messages, credentials, or services are accessed by the demo.

## Research framing

**Research gap to investigate.** Prompt-injection defenses are commonly framed as model or application robustness problems. That leaves a human-factors question: can an interface help people connect *where an instruction came from* with *what the agent is about to do*, and intervene before a consequential tool call? This project tests a review surface that combines source provenance, requested permission, risk rationale, and an explicit approval gate. This is a candidate gap, not a completed systematic review or a claim that no prior interface has studied it. See [`docs/research_plan.md`](docs/research_plan.md) for the search protocol and hypotheses.

**Proposed contribution.** (1) a source-to-action review interaction pattern, (2) a small, documented set of paired benign and injection scenarios, and (3) an evaluation protocol comparing visibility and permission controls. Novelty remains provisional pending the literature review.

## Architecture

```text
Scenario fixture (user request + source + proposed tool call)
                         |
                         v
      Risk features + provenance + permission scope
                         |
                         v
    Review UI (approve / reject) -- POST /api/review
                         |
                         v
       Simulated execution outcome (no real tool)

Scenario fixtures --> evaluation conditions --> CSV + JSON summary
```

The risk score is an explainable rule-based prototype, not a calibrated probability or learned detector. Four scripted conditions are implemented: automatic baseline, risk threshold, provenance-aware consent, and combined gate. They are deterministic decision policies and cannot establish effects on people.

## Setup

Requires Python 3.11 or newer. In `/workspace/HCI` (or the repository root):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Run

```bash
.venv/bin/uvicorn trust_boundary_lab.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in the same environment. The local UI shows a scenario, source text, proposed tool and permission, risk reasons, then records a simulated approve/reject outcome. The API schema is at `/docs` while the server runs.

## Evaluation and tests

```bash
.venv/bin/trust-boundary-evaluate --output results
.venv/bin/pytest
```

The evaluation emits one row per scenario/condition in `results/scenario_results.csv` and aggregate measures in `results/summary.json`. These are **scripted fixture results**, not human performance or empirical attack prevalence. The dataset has eight hand-authored cases and is not representative of deployment traffic. No inferential statistics are appropriate for this demonstration set.

## Research artifacts

- [`data/scenarios.jsonl`](data/scenarios.jsonl): documented constructed fixtures.
- [`docs/research_plan.md`](docs/research_plan.md): scoped review protocol, gap, RQs, hypotheses, and planned analysis.
- [`docs/user_study_protocol.md`](docs/user_study_protocol.md): proposed protocol, requiring ethics review before recruitment.
- [`paper/main.tex`](paper/main.tex): research manuscript draft; claims and evidence status are explicitly limited.

## Safety, privacy, and limitations

The simulator never executes a proposed tool. Its fixed scenario data uses example domains and has no live agent/model connection. Risk rules use fixture labels and text cues; they can be bypassed and are not an effective security boundary. The UI is for controlled research and must not be used to authorize real actions. Do not put real secrets or personal data into fixtures. The draft study has not been submitted to an ethics board and has no participants or human-subject results.
