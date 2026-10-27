#!/usr/bin/env bash
# Full reproduction: fetch traces -> replay -> simulate -> analyse -> UI scenarios -> paper.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WORKERS="${WORKERS:-4}"
scripts/fetch_agentdojo.sh external/agentdojo
export AGENTDOJO_RUNS="$ROOT/external/agentdojo/runs"
python experiments/evaluate.py --workers 1 --models gpt-4o-2024-05-13 \
  --attacks important_instructions,tool_knowledge,ignore_previous,direct,injecagent,none &
python experiments/evaluate.py --workers "$WORKERS" --models \
  claude-3-5-sonnet-20240620 claude-3-5-sonnet-20241022 claude-3-7-sonnet-20250219 claude-3-haiku-20240307 \
  claude-3-opus-20240229 claude-3-sonnet-20240229 command-r command-r-plus gemini-1.5-flash-001 gemini-1.5-flash-002 \
  gemini-1.5-pro-001 gemini-1.5-pro-002 gemini-2.0-flash-001 gemini-2.0-flash-exp gpt-3.5-turbo-0125 gpt-4-0125-preview \
  gpt-4-turbo-2024-04-09 gpt-4o-mini-2024-07-18 meta-llama_Llama-3-70b-chat-hf meta-llama_Llama-3.3-70B-Instruct \
  Meta-SecAlign-70B gpt-4o-2024-05-13-repeat_user_prompt gpt-4o-2024-05-13-spotlighting_with_delimiting \
  gpt-4o-2024-05-13-tool_filter gpt-4o-2024-05-13-transformers_pi_detector claude-3-sonnet-20240229-repeat_user_prompt \
  meta-llama_Llama-3.3-70B-Instruct-repeat_user_prompt Meta-SecAlign-70B-repeat_user_prompt
wait
python experiments/human_sim.py --sessions 1000
python experiments/analyze.py
python experiments/build_ui_scenarios.py
# combined-version experiments
python experiments/laundering.py
python experiments/cross_benchmark.py
python experiments/offline_variants.py
python experiments/analyze_v2.py
scripts/build_paper.sh
