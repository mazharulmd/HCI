# Dataset Documentation: PROV-Guard 250-Scenario Multi-Domain IPI Benchmark

## 1. Dataset Summary
`benchmarks/prov_guard_benchmark_250.json` (generated deterministically by `benchmarks/benchmark_suite.py`) contains **250 structured AI agent tool-use scenarios** modeled on real-world Model Context Protocol (MCP) workflows, extending the threat taxonomies of AgentDojo (Debenedetti et al., 2024), InjecAgent (Zhan et al., 2024), and BIPIA (Yi et al., 2023).

## 2. Domain & Attack Taxonomy Matrix

| Enterprise Domain | Benign Scenarios | A1: Direct Override | A2: Context Framing | A3: Obfuscated Payload | A4: Cross-Tool Chaining | A5: Semantic Goal-Mimicry | Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Email & Workspace (`email_workspace`)** | 20 | 6 | 6 | 6 | 6 | 6 | **50** |
| **2. Cloud Drive & Docs (`cloud_drive`)** | 20 | 6 | 6 | 6 | 6 | 6 | **50** |
| **3. Banking & Finance (`banking_finance`)** | 20 | 6 | 6 | 6 | 6 | 6 | **50** |
| **4. Developer IDE & Git (`code_ide`)** | 20 | 6 | 6 | 6 | 6 | 6 | **50** |
| **5. Calendar & Scheduling (`calendar_sched`)** | 20 | 6 | 6 | 6 | 6 | 6 | **50** |
| **Total Scenarios** | **100** | **30** | **30** | **30** | **30** | **30** | **250** |

## 3. JSON Record Schema
Each entry in `benchmarks/prov_guard_benchmark_250.json` follows this schema:
- `scenario_id` (`string`): Unique deterministic identifier (e.g., `SCEN_BANKING_FINANCE_A5_MIMICRY_01`).
- `domain` (`string`): Enterprise domain key.
- `user_prompt` (`string`): Trusted instruction issued by the authenticated human user.
- `tool_name` (`string`): The function name proposed by the AI agent.
- `capability_tier` (`enum`): `READ_ONLY`, `INTERNAL_MUTATION`, `EXTERNAL_COMMUNICATION`, or `HIGH_PRIVILEGE_EXEC`.
- `is_malicious_ground_truth` (`boolean`): `true` if the proposed tool call is hijacked by an indirect prompt injection; `false` if benign.
- `attack_category` (`enum`): `BENIGN`, `DIRECT_OVERRIDE`, `CONTEXT_FRAMING`, `OBFUSCATED_PAYLOAD`, `CROSS_TOOL_CHAIN`, or `GOAL_MIMICRY`.
- `expected_safe_tool` (`string`): Ground-truth safe tool corresponding to the user's explicit intent.
- `expected_safe_params` (`object`): Ground-truth safe argument map.
- `parameters` (`array`): List of `{name, value, is_critical_sink}` argument objects passed to `tool_name`.
- `context_chunks` (`array`): List of `{chunk_id, source_name, trust_level, source_uri, content}` external or workspace data segments ingested by the agent.
