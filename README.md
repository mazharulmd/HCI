# CLEAR: Human-Centred, Provenance-Aware Mediation of AI-Agent Tool Calls Against Prompt Injection

> **Combined version (v2).** This branch merges the three iterations of the project:
> *Trust Boundary Lab* (ChatGPT, branch `research/source-to-action-review`),
> *PROV-Guard* (Gemini, branch `research/prov-guard-hci-defense`) and *CLEAR* (Claude).
> Each borrowed idea was re-implemented and evaluated on real agent trajectories.
> Limitations of the earlier iterations are documented with reproducible evidence in
> [`docs/prior_iterations_audit.md`](docs/prior_iterations_audit.md).
>
> | Idea | From | Status in CLEAR v2 |
> |---|---|---|
> | Source-to-action review (quoted source passage in the dialog) | Trust Boundary Lab | adopted (P2 excerpt) |
> | 2×2 factorial study (provenance × authorization) | Trust Boundary Lab | adopted: selectivity × evidence protocol |
> | Decoded-payload provenance (DLPA) | PROV-Guard | adopted and generalised: decoding-aware lineage; evaluated against a provenance-laundering attacker (E1) |
> | Counterfactual / blast-radius preview (ICSP) | PROV-Guard | adopted as **P7**: consequence preview *computed* by executing the call on an environment copy |
> | Five attack families / code & cloud domains | PROV-Guard | used as a call-level stress benchmark (E2), with separability disclosed |
> | Expertise strata | PROV-Guard | used for heterogeneous simulated populations (E3) |
> | Goal-drift scoring (CGASD) | PROV-Guard | **rejected**: +22 % dialogs, no security gain on dev split |
> | Simulated "108,000-trial user study" | PROV-Guard | **not used**: effect sizes are hard-coded in the simulator |

**Human-Computer Interaction for Secure AI Tool Usage: Design Patterns Against Prompt Injection.** This repository holds the research code, data, experiments and manuscript.

CLEAR (*Contextual, Lineage-aware, Escalating Agent-action Review*) sits between an LLM agent and its tools. It:

* records the **provenance** of everything the agent reads and attributes **every argument** of every proposed tool call to *your request*, *a trusted record*, *specific external content* or *nothing*;
* scores **contextual risk** from interpretable features: harm potential, taint, private-data egress, deviation from a user-editable **intent envelope**, and instruction-likeness of untrusted content;
* escalates through four tiers: **ALLOW → NOTIFY → CONFIRM → FORCE**. It asks the user only when needed and shows *where each value came from*. For the rarest, highest-risk tier it uses a differently shaped **cognitive-forcing** dialog;
* has an **escalation floor**: no attacker-controlled text can stop an externally sourced payment, e-mail, share or post from reaching a confirmation (Proposition 1 in the paper, property-tested in `tests/test_risk.py`). In v2 the floor extends to values **laundered** through base64, hex, homoglyphs, zero-width characters and similar encodings (Proposition 2);
* shows a **computed consequence preview** for every escalated action (P7): the call is executed on a copy of the environment and the state change is described in plain language.

![CLEAR forcing dialog](figures/ui_force_dialog.png)

## Headline results (held-out, real agent trajectories)

Replaying **24,648 recorded AgentDojo trajectories** of **22 LLM agents** and five published defences:

| Policy | Attack success | Benign utility | Dialogs / benign task |
|---|---|---|---|
| No defence | 16.5 % | 54.4 % | 0 |
| Lexical injection detector (abort) | 0.1 % (utility under attack 5.2 %) | 54.4 % | 0 |
| Strict information-flow policy (auto) | 2.6 % | 31.8 % | 0 |
| Confirm every action (ideal user) | 0.5 % | 54.4 % | 0.79 |
| **CLEAR (ideal user)** | **0.7 %** | **54.4 %** | **0.38** |
| **CLEAR (no human, escalations denied)** | **0.7 %** | 35.2 % | 0.38 |

* 51 % fewer dialogs than confirm-all in this trace replay; 74 % of benign tasks need no dialog at all. Inferential comparisons are clustered by benchmark task.
* Against a **detector-evading attacker**, CLEAR stays at 0.9 % ASR. A provenance-free mediator cannot get below 9.3 % at any threshold, and the lexical detector reverts to 16.5 %.
* A parametric, habituation-aware user model (**simulation, not human data**) predicts lower end-to-end compromise than confirm-all in 100 % of 243 parameter settings.

Combined-version experiments:
* **E1, provenance laundering.** Encoding the attacker's value lets lexical lineage (v1) be evaded by 6–8 % of previously successful attacks; decoding-aware lineage (v2) restores 0.6 %. Base64-encoding the whole injection block is closed only by the post-hoc v2.1 fix (4.1 %, equal to the plain block), which is reported separately. See `results/tables/laundering_summary.csv`.
* **E2, cross-benchmark stress test** on the PROV-Guard-250 and Trust-Boundary-8 scenarios. On the 250 template scenarios, CLEAR keeps full recall while falsely escalating far fewer benign high-privilege calls (20 %) than the Trust-Boundary gate (60 %) and the PROV-Guard engine (100 %). On the 8 argument-free Trust-Boundary fixtures it misses 2 of 4 attacks. See `results/tables/cross_benchmark.csv`.
* **E3, heterogeneous users** (simulation). The ordering holds in novice-heavy and expert-heavy populations.

All numbers are produced by the code in this repository: see `results/stats.json`, `results/tables/` and the manuscript in `paper/main.pdf`.

> **What was *not* done.** No human-subject data were collected. The proposed user-study protocol (`docs/user_study/`, `clear/ui/`) has not been submitted for ethics review, preregistered, or run. The evaluation replays recorded trajectories. No new live LLM runs were made (no API budget or GPU was available in the research environment).

## Repository layout

```
clear/                      the framework (pip-installable, dependency: pyyaml)
  provenance.py               provenance ledger, argument attribution, URL canonicalisation
  envelope.py                 intent-envelope compiler (LLM-free, injection-proof)
  signals.py                  transparent instruction-likeness scorer
  risk.py                     features, noisy-OR risk, escalation tiers (Proposition 1)
  mediator.py                 the interposition API: start_task / observe_result / assess / decide
  baselines.py                confirm-all, strict IFC, task-scoped allowlist, injection detector
  human_model.py              SDT + habituation model of confirmation decisions (simulation)
  deobfuscate.py              decoding-aware canonicalisation (v2)
  ui/                         agent console + user-study apparatus (stdlib server, vanilla JS)
configs/
  clear_default.yaml          v1, frozen weights and thresholds
  clear_v2.yaml               v2 (combined version, frozen): + decoding-aware lineage
  clear_v2_1.yaml             v2.1: post-hoc decoder robustness fix (reported separately)
  tool_manifest_stress.yaml   manifest for the stress-benchmark tools
  tool_manifest.yaml          declared tool capabilities (P0)
experiments/
  traces.py                   AgentDojo trace loader + environment replayer
  evaluate.py                 trace-replay evaluation of all policies, ablations, labels
  human_sim.py                simulated human-in-the-loop analysis
  analyze.py                  statistics, tables, figures, LaTeX macros
  build_ui_scenarios.py       builds UI/user-study scenarios (with computed consequence previews)
  laundering.py               E1 provenance-laundering attack
  cross_benchmark.py          E2 stress test vs. PROV-Guard and Trust-Boundary engines
  offline_variants.py         exact offline evaluation of extra configurations (v2.1)
  analyze_v2.py               tables, figures and macros for E1-E3 and the audit
third_party/                earlier iterations' engines and benchmarks (blinded baselines)
data/
  derived/                    compressed per-episode and per-call results (see data/README.md)
  ui_answer_key.json          ground truth for the 16 study scenarios (never sent to the browser)
results/                    stats.json, tables/*.csv|tex, human_sim.csv, logs
figures/                    all figures (PDF + PNG) and UI screenshots
paper/                      LaTeX manuscript (main.tex, references.bib, generated/ tables)
docs/
  research_design.md          gap, contributions, RQs, hypotheses, architecture
  development_log.md          development and configuration-freeze log
  literature/                 structured review + reference verification log
  user_study/                 protocol, consent form, debriefing
tests/                      57 automated tests (unit, property, laundering, label-blindness, UI, integration)
scripts/                    fetch_agentdojo.sh, run_all.sh, build_paper.sh
```

## Installation

Requires Python ≥ 3.10.

```bash
git clone https://github.com/mazharulmd/HCI.git && cd HCI
python -m pip install -r requirements.txt     # agentdojo==0.1.35, numpy, pandas, scipy, statsmodels, matplotlib, pytest
python -m pytest -q                           # 57 tests (the integration tests skip if traces are absent)
```

LaTeX (for the paper): `texlive-latex-extra`, `texlive-science`, `latexmk`.

## Reproducing the paper

**Fast path (minutes)** uses the shipped derived data:
```bash
python experiments/human_sim.py --sessions 1000   # simulated users (~1 min)
python experiments/analyze.py                     # statistics, tables, figures, LaTeX macros
scripts/build_paper.sh                            # -> paper/main.pdf
```

**Full path (≈1 h on 4 cores)** re-runs the trace replay from the raw AgentDojo trajectories:
```bash
scripts/run_all.sh
```
This fetches AgentDojo at the pinned commit `089ed468…`, replays all 29 pipelines (`experiments/evaluate.py`), then runs the simulation, analysis and paper build. Each stage is deterministic: bootstraps and simulations are seeded.

## Using CLEAR in your own agent

```python
from clear import Mediator, ToolCall

m = Mediator.default(config="configs/clear_v2.yaml")   # combined version (v1: omit config)
m.start_task(user_prompt, system_prompt)
for call in agent_loop():                    # each proposed tool call, before execution
    a = m.assess(ToolCall(call.name, call.args))
    d = m.decide(a, human=my_dialog)         # my_dialog(assessment, mediator) -> bool
    if d.execute:
        out = run_tool(call)
        m.observe_result(ToolCall(call.name, call.args), out)
```
`a.tier`, `a.risk`, `a.reasons` and `a.arg_provenance` carry everything needed to render a dialog. Tools not in the manifest fail closed.

## Interactive console / user-study apparatus

```bash
python -m clear.ui.server --port 8765
# open http://127.0.0.1:8765/?condition=clear&pid=P001
# conditions (2x2 selectivity x evidence): clear | clear_generic | confirm_all_evidence | confirm_all ; plus none
```
Decisions, response times, forcing answers, envelope edits and undo events are logged to `user_study_logs/<pid>.jsonl`. The post-task questionnaire (SUS, NASA-TLX raw, trust in automation) is at `questionnaire.html`.

## Citing

See `CITATION.cff`. Third-party data: AgentDojo traces and environments (MIT licence, © ETH Zurich SPY Lab) are fetched, not redistributed.

## Licence

MIT (see `LICENSE`).
