#!/usr/bin/env bash
# Fetch the AgentDojo repository (MIT licence) at the pinned commit used in the
# paper. Its runs/ directory contains the real LLM agent traces we replay.
set -euo pipefail
DEST="${1:-external/agentdojo}"
COMMIT="089ed468cf3ed0322acc66b0211f26d9d90dbf60"
if [ ! -d "$DEST/.git" ]; then
  git clone https://github.com/ethz-spylab/agentdojo.git "$DEST"
fi
git -C "$DEST" fetch --depth 1 origin "$COMMIT" 2>/dev/null || true
git -C "$DEST" checkout -q "$COMMIT"
echo "AgentDojo traces at $DEST/runs ($(ls "$DEST/runs" | wc -l) pipelines)"
