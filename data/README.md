# Datasheet: CLEAR trace-replay dataset

## Motivation
This dataset supports a reproducible evaluation of tool-call mediation against
indirect prompt injection. It records security, utility and user-burden
outcomes for many policies on the *same* real agent trajectories.

## Source data
* **AgentDojo** run traces (Debenedetti et al., NeurIPS 2024 D&B). Repository `ethz-spylab/agentdojo`, commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, directory `runs/`, MIT licence. The traces were produced by the AgentDojo authors and contributors with real LLM APIs.
* **Pipelines used (29).** 22 base models (GPT-3.5/4/4-turbo/4o/4o-mini; Claude 3 Haiku/Sonnet/Opus, 3.5 Sonnet ×2, 3.7 Sonnet; Gemini 1.5 Flash/Pro ×2 each, 2.0 Flash ×2; Llama-3-70B, Llama-3.3-70B; Command-R, Command-R+; Meta-SecAlign-70B) plus 7 defended pipelines (sandwich, spotlighting, tool filter, DeBERTa detector on GPT-4o; sandwich on Llama-3.3-70B, Claude-3-Sonnet and Meta-SecAlign-70B).
* **Attacks.** `important_instructions` for all pipelines, plus `tool_knowledge`, `ignore_previous`, `direct` and `injecagent` for GPT-4o. Benign runs (no attack) for all pipelines.
* The raw traces are **not redistributed** here. `scripts/fetch_agentdojo.sh` downloads them.

## Composition (`data/derived/`)

| File | One row per | Key fields |
|---|---|---|
| `episodes_<pipeline>.jsonl.gz` | episode (pipeline × suite × user task × attack × injection task) | stored and replayed utility/security; numbers of calls, side-effecting calls and injected calls (signature / necessity); for every policy-mode (e.g. `clear:oracle`, `confirm_all:auto`, `strict_ifc:auto`, ablations) the replayed utility `u`, security `s`, number of CONFIRM+FORCE dialogs, FORCE and NOTIFY counts; `subset_outcomes` (utility/security for every subset of denied injected calls, used for exact simulation and operating curves); benchmark version |
| `calls_<pipeline>.csv.gz` | proposed tool call | function, capability, sensitivity, reversibility; CLEAR features (`f_s`, `f_tau`, `f_kappa`, `f_delta`, `f_iota`, `f_iota_attr`, `f_iota_ctx`); tier and risk for each CLEAR variant; baseline decisions; labels `injected`, `sig`, `necessary`; assessment latency (ms) |
| `summary_<pipeline>.json` | pipeline | benchmark version chosen by probe, version-probe agreement, episode and error counts |

Totals: 24,648 episodes (21,893 attacked, 2,755 benign) and 90,248 tool calls (23,793 side-effecting; 5,234 labelled injected). Five episodes (Claude-3.5-Sonnet-0620, slack `user_task_4`) could not be replayed. Re-executing them raised an environment `KeyError`, because a web page referenced in the trace (`www.our-company.com`) is absent from the selected benchmark version's environment. They are recorded with an `error` field and excluded.

## Collection / processing
`experiments/evaluate.py` streams each trace through CLEAR, its ablations and the baselines. Each call is assessed *before* its result is seen. The script then re-executes the non-blocked calls in AgentDojo's environment and evaluates the benchmark's own utility and security predicates. Labels are described in the paper (Sec. 5.3). Inter-criterion agreement: Cohen's κ = 0.91.

## Splits
* **Development**: GPT-4o × {banking, slack}.
* **Held-out**: everything else. Main results use held-out data only.

## Known limitations
* Replay cannot observe agent adaptation after a blocked call.
* Utility is scored conservatively: any stopped benign call means task failure.
* Replay agreement with the stored AgentDojo labels is 99.1 % (utility) and 99.4 % (security) overall. It is lower for Claude-3-Opus (84.3 % utility) and Llama-3-70B (94.1 % security).

## Other files
* `ui_answer_key.json`: ground-truth labels of the 16 user-study scenarios, kept separate from the participant-facing `clear/ui/static/scenarios.json`.

## Personal data
None. All environments are synthetic AgentDojo data.
