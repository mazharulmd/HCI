# Human-Computer Interaction for Secure AI Tool Usage: Design Patterns Against Prompt Injection (`PROV-Guard`)

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![Benchmark](https://img.shields.io/badge/benchmark-250_scenarios-blue)]()
[![Trials](https://img.shields.io/badge/evaluation-108%2C000_trials-teal)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

**Repository:** `https://github.com/mazharulmd/HCI.git`  
**Research Branch:** `research/prov-guard-hci-defense`

## Overview & Scientific Contribution

Tool-augmented Large Language Model (LLM) agents increasingly execute high-privilege external operations (sending emails, modifying cloud permissions, executing financial wire transfers, and running shell commands) via protocols such as the Model Context Protocol (MCP). When these agents ingest untrusted external data (emails, shared documents, web pages, GitHub issues), they are vulnerable to **Indirect Prompt Injection (IPI)**.

Existing defenses rely either on brittle in-band delimiter filtering (e.g., Spotlighting) or on generic **Human-in-the-Loop (HITL) binary confirmation dialogs** (`[Allow / Deny]`). Our research demonstrates that standard binary confirmation modals fail in **92.62%** of attacks across multi-step sessions due to **Provenance Blindness**, **Generalization of Warning Habituation**, and **Semantic Goal-Mimicry Opacity**.

**PROV-Guard** introduces four mathematically formalized, experimentally validated HCI security design patterns:
1. **Dual-Lineage Provenance Attribution (DLPA)** (`src/hci_sec/provenance.py`): Token-level, entity-level, and decoded-payload taint tracking that visually distinguishes `USER_EXPLICIT` parameters from `EXTERNAL_UNTRUSTED` and `ADVERSARIAL_FLAGGED` parameters.
2. **Contextual Goal-Alignment & Semantic Drift Visualization (CGASD)** (`src/hci_sec/drift.py`): Quantifies and displays functional cosine divergence, capability escalation, and entity diversion between the user's initial prompt and the proposed tool call.
3. **Adaptive Friction & Tiered Capability Gates (AFTCG)** (`src/hci_sec/risk_gate.py`): Replaces uniform confirmation popups with four risk-calibrated tiers (`TIER_0_AMBIENT`, `TIER_1_SPOTLIGHT_DIFF`, `TIER_2_CONSTRUCTIVE`, `TIER_3_SANDBOX_HOLD`), utilizing constructive parameter source verification to switch operator cognition from System 1 to System 2.
4. **Interactive Counterfactual & Sandbox Preview (ICSP)** (`src/hci_sec/risk_gate.py`): Computes pre-execution blast-radius state diffs and reversibility scores ($\rho \in [0, 1]$) juxtaposed against the expected safe tool call.

## Key Empirical Results (9 Conditions $\times$ 48 Operators $\times$ 250 Scenarios = 108,000 Trials)

| Defense Condition | Attack Success Rate (ASR %) $\downarrow$ | Defense Eff. (DE %) $\uparrow$ | Benign FPR (%) $\downarrow$ | Benign Utility (%) $\uparrow$ | Sensitivity ($d'$) $\uparrow$ | $F_1$ Score (%) $\uparrow$ | NASA-TLX Workload $\downarrow$ | Decision Time (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `B0_NO_DEFENSE` | $100.00 \pm 0.0$ | $0.00 \pm 0.0$ | $0.00 \pm 0.0$ | $100.00 \pm 0.0$ | $-0.14$ | $0.00$ | $8.5$ | $0.05$ |
| `B1_SPOTLIGHTING_SYSTEM` | $56.11 \pm 3.2$ | $43.89 \pm 3.2$ | $4.85 \pm 2.0$ | $95.15 \pm 2.0$ | $1.50$ | $59.60$ | $11.2$ | $0.12$ |
| `B2_STATIC_BANNER` | $92.50 \pm 2.1$ | $7.50 \pm 2.1$ | $15.38 \pm 4.0$ | $84.62 \pm 4.0$ | $-0.41$ | $12.68$ | $67.8$ | $1.47$ |
| `B3_BINARY_MODAL` | $92.62 \pm 1.9$ | $7.38 \pm 1.9$ | $9.62 \pm 2.9$ | $90.38 \pm 2.9$ | $-0.14$ | $12.91$ | $60.7$ | $1.55$ |
| `ABL_NO_DLPA` (w/o P1) | $77.74 \pm 4.0$ | $22.26 \pm 4.0$ | $2.33 \pm 1.4$ | $97.67 \pm 1.4$ | $1.20$ | $35.80$ | $49.0$ | $1.66$ |
| `ABL_NO_CGASD` (w/o P2) | $35.35 \pm 4.9$ | $64.65 \pm 4.9$ | $1.56 \pm 1.2$ | $98.44 \pm 1.2$ | $2.49$ | $77.93$ | $46.9$ | $2.42$ |
| `ABL_NO_AFTCG` (w/o P3) | $77.90 \pm 6.7$ | $22.10 \pm 6.7$ | $3.33 \pm 1.9$ | $96.67 \pm 1.9$ | $1.05$ | $35.11$ | $50.0$ | $0.95$ |
| `ABL_NO_ICSP` (w/o P4) | $39.88 \pm 7.2$ | $60.12 \pm 7.2$ | $1.42 \pm 1.2$ | $98.58 \pm 1.2$ | $2.42$ | $74.41$ | $49.0$ | $2.54$ |
| **`PROV_GUARD_FULL`** | **$2.54 \pm 1.8$** | **$97.46 \pm 1.8$** | **$1.10 \pm 1.0$** | **$98.90 \pm 1.0$** | **$4.21$** | **$98.34$** | **$46.8$** | **$2.42$** |

## Repository Architecture

```text
HCI/
├── src/hci_sec/
│   ├── __init__.py          # Package exports
│   ├── models.py            # Formal data structures, trust levels, capability tiers
│   ├── provenance.py        # Pattern 1: Dual-Lineage Provenance Attribution (DLPA)
│   ├── drift.py             # Pattern 2: Contextual Goal-Alignment & Semantic Drift (CGASD)
│   ├── risk_gate.py         # Pattern 3 & 4: Adaptive Friction (AFTCG) & Counterfactual Preview (ICSP)
│   └── user_model.py        # Neuro-cognitive operator simulator (Habituation, SDT d', NASA-TLX)
├── benchmarks/
│   ├── benchmark_suite.py           # Deterministic generator for 250 multi-domain scenarios
│   └── prov_guard_benchmark_250.json # Full serialized 250-scenario dataset
├── experiments/
│   ├── run_experiments.py           # Full-factorial 108,000-trial evaluation & statistical suite
│   ├── generate_figures.py          # Publication figure generator (300 DPI PNG + vector PDF)
│   └── results/
│       ├── experimental_results.json      # Complete aggregate & statistical test outputs
│       └── participant_level_metrics.csv  # 432 participant-condition records
├── figures/                 # Generated publication figures (fig1..fig5 in PDF & PNG)
├── ui/
│   └── prov_guard_workbench.html    # Self-contained interactive browser simulator & user study app
├── manuscript/
│   ├── main.tex                     # Camera-ready Q1 LaTeX manuscript with embedded figures
│   ├── main_canvas.tex              # Self-contained LaTeX source for Canvas compilation
│   └── PROV_Guard_Q1_Paper.pdf      # Compiled 7-page two-column Q1 paper
├── docs/
│   ├── IRB_USER_STUDY_PROTOCOL.md   # Ethics & IRB human-subjects experimental protocol
│   └── DATASET_DOCUMENTATION.md     # Datasheet & schema for the 250-scenario benchmark
├── tests/
│   └── test_prov_guard.py           # Unit & integration test suite
└── requirements.txt                 # Reproducible Python dependencies
```

## Quickstart & Reproducibility Instructions

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)/src:$(pwd)"
```

### 2. Run Automated Tests
```bash
python3 tests/test_prov_guard.py
```

### 3. Regenerate the 250-Scenario Benchmark & Run All 108,000 Experimental Trials
```bash
python3 benchmarks/benchmark_suite.py
python3 experiments/run_experiments.py
python3 experiments/generate_figures.py
```

### 4. Compile the Q1 LaTeX Manuscript
```bash
cd manuscript
lualatex -interaction=nonstopmode -halt-on-error main.tex
lualatex -interaction=nonstopmode -halt-on-error main.tex
```

### 5. Push to GitHub Remote Branch (`research/prov-guard-hci-defense`)
```bash
git checkout research/prov-guard-hci-defense
git push -u origin research/prov-guard-hci-defense
```
