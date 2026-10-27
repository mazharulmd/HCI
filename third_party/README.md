# Third-party baselines (earlier iterations of this project)

These files are copied **unchanged** (except as noted) from the two earlier
iterations of this project, so that they can be run as baselines and their
benchmarks used as call-level stress tests (`experiments/cross_benchmark.py`).

| Directory | Source | Notes |
|---|---|---|
| `provguard/` | branch `research/prov-guard-hci-defense` (Gemini), `src/hci_sec/{models,provenance,drift,risk_gate}.py` and `benchmarks/prov_guard_benchmark_250.json` | `__init__.py`: the import of the simulated-user module was removed. The simulator is *not* used, because its outputs are hard-coded effect sizes (see `docs/prior_iterations_audit.md`). |
| `trust_boundary_lab/` | branch `research/source-to-action-review` (ChatGPT), `trust_boundary_lab/core.py`, `data/scenarios.jsonl` | unchanged |

When used as baselines, these engines are **blinded**: the ground-truth fields
of each scenario (`is_malicious_ground_truth`, `attack_category`,
`expected_safe_*`, `attack`, `expected`) are replaced by neutral values before
the engine sees them.
