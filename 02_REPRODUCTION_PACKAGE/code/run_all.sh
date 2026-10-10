#!/usr/bin/env bash
set -euo pipefail

# Run inside the official CS30401 Lab 1 container from the repository mounted at /work/repo.
: "${NS3_DIR:?NS3_DIR is not set. Run inside the official course container.}"
: "${LAB:?LAB is not set. Run inside the official course container.}"
: "${STATE_EXAMPLE:?STATE_EXAMPLE is not set. Run inside the official course container.}"

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RUNS=/work/runs_repro
ANALYSIS=/work/analysis_generated
FIGURES=/work/figures_generated
STATE2160=/work/state_2160

mkdir -p "$RUNS" "$ANALYSIS" "$FIGURES"

echo "[1/6] Generate the 2160-satellite state"
"$ROOT/generate_state.sh" "$STATE2160"

echo "[2/6] Run unmodified standard Vegas and CUBIC baselines"
"$ROOT/experiments/standard_baselines.sh" "$STATE2160/state" "$RUNS"

echo "[3/6] Apply Adaptive Vegas patch"
cd "$NS3_DIR"
if ! git apply --check "$ROOT/adaptive-vegas.patch"; then
  echo "ERROR: patch cannot be cleanly applied. Start from a fresh course container/ns-3 tree." >&2
  exit 1
fi
git apply "$ROOT/adaptive-vegas.patch"

echo "[4/6] Run adaptive and congestion-safety experiments"
"$ROOT/experiments/adaptive_runs.sh" "$STATE2160/state" "$RUNS" "$ANALYSIS"

echo "[5/6] Extract quantitative summary"
python3 "$ROOT/analysis/extract_summary.py" "$RUNS" "$ANALYSIS" "$ANALYSIS/summary.csv"

echo "[6/6] Generate figures"
python3 "$ROOT/plots/make_figures.py" "$ANALYSIS/summary.csv" "$FIGURES"

echo
cat "$ANALYSIS/summary.csv"
echo
echo "Generated:"
echo "  Runs:     $RUNS"
echo "  Summary:  $ANALYSIS/summary.csv"
echo "  Figures:  $FIGURES"
