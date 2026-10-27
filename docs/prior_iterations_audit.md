# Audit of the three research iterations and how they were combined

This project was attempted three times, with three different AI assistants.
All three outputs are preserved as branches of this repository:

| Branch | Produced with | Name of the artefact |
|---|---|---|
| `research/source-to-action-review` | ChatGPT | *Trust Boundary Lab* |
| `research/prov-guard-hci-defense` | Gemini (pushed unchanged from the uploaded archive, commit `5bfbe43`) | *PROV-Guard* |
| `main` / `claude/upbeat-davinci-2p754q` | Claude | *CLEAR*, now the combined version |

This document records what each iteration contributes, which limitations were
found (with reproducible evidence), and how the combined version fixes them.
Audit artefacts are in `results/audit/`.

---

## 1. Trust Boundary Lab (ChatGPT)

**Contributions worth keeping**
* *Source-to-action review* framing. A reviewer must connect where an
  instruction came from with what the agent is about to do. This is the
  interaction CLEAR's provenance chips implement.
* A requested-permission scope shown alongside the action. In CLEAR this
  corresponds to the intent envelope.
* Methodological caution. The README and plan state explicitly that the
  results are scripted fixtures, that the review was incomplete, and that
  novelty is provisional.
* A **2×2 factorial** user-study recommendation: provenance present/absent ×
  rationale/authorization present/absent.
* Clear operational metric definitions (ASR, defense effectiveness, benign
  block rate, decision accuracy).

**Limitations (with evidence)**
| # | Limitation | Evidence |
|---|---|---|
| C1 | 8 hand-authored fixtures, one proposed call each, no agent | `data/scenarios.jsonl` |
| C2 | Earlier version leaked the label into the risk score (`if s.attack: score += 30`) | commit `31bdb7a` diff, fixed by ChatGPT itself |
| C3 | The keyword list that replaced the leak mirrors the wording of the 8 fixtures ("ignore the user's request", "system prompt", ...), so the 0% ASR is in-sample | `trust_boundary_lab/core.py` |
| C4 | Systematic review not performed (indexes unreachable) | `docs/research_plan.md` |
| C5 | No statistics, no real attack data, no burden metric | `results/summary.json` |

## 2. PROV-Guard (Gemini)

**Contributions worth keeping**
* **Decoded-payload provenance (DLPA).** Attribution should survive encoding
  (base64), zero-width characters and other obfuscation.
* **Goal-alignment drift (CGASD).** A signal for actions that mimic the user's
  goal while diverting entities or escalating capability.
* **Counterfactual / blast-radius preview (ICSP).** Show the user what will
  change and whether it can be undone.
* A broader **attack taxonomy**: direct override, context framing,
  obfuscated payload, cross-tool chain, goal mimicry. It also adds a broader
  **domain scope**, including code/IDE and cloud sharing.
* The idea of **expertise strata** (novice / intermediate / security-aware) in
  user modelling.
* A deterministic, fully reproducible pipeline. Re-running it reproduced
  every reported number exactly.

**Limitations (with evidence)**
| # | Limitation | Evidence |
|---|---|---|
| G1 | **All "experimental" results are outputs of a simulator with hard-coded effect sizes**, but the manuscript presents them as findings ("we demonstrate ... 92.62% ASR", "d′ = 4.21", "NASA-TLX lowered by 22.9%", "p = 1.9×10⁻¹⁶", "Cohen's d = −49.37"). No human or agent data exist. | `src/hci_sec/user_model.py` encodes the effect of every design pattern directly, e.g. `if not ui.shows_provenance_lineage: cue_clarity *= 0.42`. |
| G2 | Ablation effects are artefacts of these constants. | Setting only the per-pattern cue multipliers and bonuses to neutral moves ASR without CGASD from 35.4% to 16.4%, without ICSP from 39.9% to 16.4%, without DLPA from 77.7% to 55.9%, and full PROV-Guard from 2.5% to 6.5%. See `results/audit/gemini_sim_*.json` (reproduce: `python -I run_audit.py <copy-of-gemini-repo> out.json` after neutralising lines 215-244 of `user_model.py`). |
| G3 | Baselines are not implemented. "Spotlighting" is a table of per-category catch probabilities (0.78, 0.62, ...), and "no defense" has 100% ASR by construction (every malicious scenario is a successful hijack). | `user_model.py` lines 99-150 |
| G4 | The benchmark is trivially separable by provenance. In all 150 malicious scenarios, and in none of the 100 benign ones, a critical argument appears in external content but not in the user prompt. Any provenance method scores perfectly by construction. | `results/audit/gemini_benchmark_separability.txt` |
| G5 | Template-generated benchmark (118 unique prompts for 250 scenarios); single proposed call per scenario, no agent trajectory; trust labels are given, not derived. | `benchmarks/benchmark_suite.py` |
| G6 | Citation errors against verified records. The CHI polymorphic-warning paper is dated 2016 (it is CHI 2015). StruQ is listed as USENIX Security 2024 (it is 2025). Meta SecAlign lists a non-existent co-author ("S. Mahalakshmi"). The *Fog of Warnings* first author differs from the record. Only 15 references in total. | `manuscript/main.tex` bibliography; `docs/literature/verification_log.md` |
| G7 | Statistical tests on simulated participants (N = 48 parameter draws) produce p-values that measure Monte-Carlo noise, not evidence. Effect sizes such as d = −49 are not meaningful. | `experiments/run_experiments.py` |
| G8 | "IRB protocol" and "user-study app" exist, but no ethics approval or data. | `docs/IRB_USER_STUDY_PROTOCOL.md` |

## 3. CLEAR (Claude), first version: self-audit

| # | Limitation | Fixed in combined version? |
|---|---|---|
| L1 | Lexical attribution could be laundered by encoding the attacker's value (a gap DLPA addressed) | **Yes**: decoding-aware attribution + experiment E1 |
| L2 | Only AgentDojo's four domains; no code/IDE or cloud-sharing tasks; attack families limited to templates | **Partly**: cross-benchmark call-level stress test E2 on the PROV-Guard and Trust Boundary scenarios (with G4/G5 caveats) |
| L3 | Dialog showed provenance but not *consequences* | **Yes**: real sandbox state-diff preview computed by executing the call on a copy of the AgentDojo environment (ICSP idea, but real) |
| L4 | User-study design was three groups and did not cross the factors | **Yes**: 2×2 factorial (selectivity × evidence), per ChatGPT's recommendation |
| L5 | Human simulation used one homogeneous user type | **Yes**: E3 heterogeneous population with expertise strata (PROV-Guard idea, but parameters swept rather than asserted) |
| L6 | No human-subject data | No. This still requires ethics approval and participants. |

## 4. Rules adopted for the combined version
1. **Only real measurements are reported as results.** Agent behaviour comes from recorded LLM trajectories; outcomes come from the benchmark's own predicates.
2. Simulations appear only as *hypothesis-generating* analyses, with every parameter swept and labelled "not human data".
3. Every borrowed idea is re-implemented, evaluated and ablated on held-out data. A borrowed idea that does not help is reported as a negative result rather than dropped.
4. Synthetic benchmarks are used only for call-level stress tests, with their separability disclosed.
