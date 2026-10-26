#!/usr/bin/env bash
# Copy generated tables/figures into paper/ and compile the manuscript.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/paper/generated" "$ROOT/paper/figures"
cp "$ROOT"/results/tables/*.tex "$ROOT/paper/generated/"
for f in fig_tradeoff fig_curves fig_tiers fig_per_model fig_roc fig_human_sim; do
  cp "$ROOT/figures/$f.pdf" "$ROOT/paper/figures/"
done
cp "$ROOT"/figures/ui_force_dialog.png "$ROOT"/figures/ui_confirm_dialog.png "$ROOT"/figures/ui_generic_dialog.png "$ROOT/paper/figures/"
cd "$ROOT/paper"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >/dev/null
echo "built paper/main.pdf"
