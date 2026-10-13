#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REFRESH="$ROOT/recurring_refresh/code"
MODE=all
if [[ ${1:-} == --help ]]; then
  cat <<'HELP'
Usage: bash code/run_all.sh [--refresh-only] [refresh runner options]
Default: original Vegas/CUBIC (500/1584/2160), adaptive/safety, cross-traffic, 12 refresh cases.
--refresh-only resumes just the refresh stage using REFRESH_NS3_DIR.
Options such as --threads 4 and --retry-incomplete are forwarded to refresh.
Required: NS3_DIR, LAB, STATE_EXAMPLE; see README.md for clean-tree setup.
Optional: REPRO_WORK (default /work), REFRESH_NS3_DIR, UV_PROJECT_ENVIRONMENT.
HELP
  exit 0
fi
if [[ ${1:-} == --refresh-only ]]; then MODE=refresh; shift; fi
: "${NS3_DIR:?Set NS3_DIR to the course ns-3.48 tree; see README.md.}"
: "${LAB:?Set LAB to the course environment repository; see README.md.}"
: "${STATE_EXAMPLE:?Set STATE_EXAMPLE to the course Seoul-London state.}"
command -v uv >/dev/null || { echo 'uv is required; see README.md.' >&2; exit 1; }
export NS3_DIR=$(cd "$NS3_DIR" && pwd)
export LAB=$(cd "$LAB" && pwd)
export STATE_EXAMPLE=$(cd "$STATE_EXAMPLE" && pwd)
export PATH="$LAB/scripts:$PATH"
WORK=${REPRO_WORK:-/work}
mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)
RUNS="$WORK/runs_repro"
ANALYSIS="$WORK/analysis_generated"
FIGURES="$WORK/figures_generated"
STATE2160="$WORK/state_2160"
STATE500="$WORK/state_500"
REFRESH_OUTPUT="$WORK/refresh_generated"
REFRESH_NS3_DIR=${REFRESH_NS3_DIR:-$WORK/ns3_refresh}
export UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-$WORK/repro_venv}
# Reject unsafe overlaps and whitespace unsupported by course configs.
python3 - "$NS3_DIR" "$REFRESH_NS3_DIR" "$WORK" "$ROOT" <<'PY'
from pathlib import Path
import sys
src, dst, work, code = map(lambda s: Path(s).resolve(), sys.argv[1:])
if any(any(c.isspace() for c in str(p)) for p in (src, dst, work, code)):
    raise SystemExit('Paths must not contain whitespace (course launcher limitation).')
if src == dst or src.is_relative_to(dst) or dst.is_relative_to(src):
    raise SystemExit('Original/adaptive and refresh simulator trees must be separate.')
if work == src or work.is_relative_to(src) or work == code or code.is_relative_to(work) or work.is_relative_to(code):
    raise SystemExit('Choose an output directory separate from simulator/package sources.')
PY
if [[ $MODE == all ]]; then
  echo '[1/9] Check clean baseline and preserve a separate refresh simulator'
  git -C "$NS3_DIR" apply --ignore-space-change --ignore-whitespace --check "$ROOT/adaptive-vegas.patch"
  python3 - "$NS3_DIR" "$REFRESH/provenance/implementation.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for rel, expected in json.loads(Path(sys.argv[2]).read_text())['baseline_file_sha256'].items():
    p = root / rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Baseline source differs: {rel}. Use a fresh course ns-3 tree.')
PY
  for output in "$RUNS" "$ANALYSIS" "$FIGURES" "$STATE2160" "$STATE500" "$REFRESH_OUTPUT"; do
    [[ ! -e $output ]] || { echo "Existing output: $output. Use a new REPRO_WORK; see README.md." >&2; exit 1; }
  done
  if [[ ! -e $REFRESH_NS3_DIR ]]; then
    mkdir -p "$REFRESH_NS3_DIR"
    # Build/cache paths embed absolute locations and cannot be reused after copying.
    tar -C "$NS3_DIR" --exclude='./build' --exclude='./cmake-cache' \
      --exclude='./.git' --exclude='./.venv' --exclude='./.lock-ns3*' -cf - . | \
      tar -C "$REFRESH_NS3_DIR" -xf -
    (cd "$REFRESH_NS3_DIR" && ./ns3 configure --build-profile=release \
      --enable-modules='satellite-network;flow-monitor' --disable-tests --disable-examples)
  fi
fi
# Hash-guarded install checks the refresh tree before expensive experiments.
python3 "$REFRESH/experiments.py" install --ns3 "$REFRESH_NS3_DIR" --output "$REFRESH_OUTPUT"
echo '[2/9] Install locked Python dependencies'
uv sync --frozen --project "$ROOT"
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"
export MPLBACKEND=Agg
unset VEGAS_WINDOW_S VEGAS_TRACE VEGAS_EXTRA_TRACE FLOWS
export PACING=false
if [[ $MODE == all ]]; then
  mkdir -p "$RUNS" "$ANALYSIS" "$FIGURES"
  echo '[3/9] Generate the 500- and 2160-satellite states'
  bash "$ROOT/generate_state.sh" "$STATE2160" 72 30
  bash "$ROOT/generate_state.sh" "$STATE500" 25 20
  echo '[4/9] Run original Vegas and CUBIC controls on the unmodified tree'
  bash "$ROOT/experiments/standard_baselines.sh" "$STATE500/state" "$STATE2160/state" "$RUNS" "$ANALYSIS"
  echo '[5/9] Apply and build adaptive Vegas'
  git -C "$NS3_DIR" apply --ignore-space-change --ignore-whitespace "$ROOT/adaptive-vegas.patch"
  (cd "$NS3_DIR" && ./ns3 build main_satnet)
  echo '[6/9] Run adaptive Vegas, safety, dense five-flow and UDP cases'
  bash "$ROOT/experiments/adaptive_runs.sh" "$STATE500/state" "$STATE2160/state" "$RUNS" "$ANALYSIS"
  bash "$ROOT/experiments/dense_cross_traffic.sh" "$STATE2160/state" "$RUNS" "$ANALYSIS"
  echo '[7/9] Extract baseline/adaptive results and figures'
  python3 "$ROOT/analysis/extract_summary.py" "$RUNS" "$ANALYSIS" "$ANALYSIS/summary.csv"
  python3 "$ROOT/analysis/extract_detailed_summary.py" "$RUNS" "$ANALYSIS"
  python3 "$ROOT/plots/make_figures.py" "$ANALYSIS" "$FIGURES"
  python3 "$ROOT/plots/make_figures2.py" "$ANALYSIS" "$FIGURES"
  python3 "$ROOT/plots/make_figures3.py" "$ANALYSIS" "$FIGURES"
fi
echo '[8/9] Run original and 1/5/10 s histories in the separate refresh tree'
uv run --frozen --project "$ROOT" python "$REFRESH/experiments.py" run \
  --ns3 "$REFRESH_NS3_DIR" --output "$REFRESH_OUTPUT" "$@"
echo '[9/9] Generate the report comparison, Table III and dense queue/delay figure'
REPORT_ARGS=()
if [[ -f $ANALYSIS/summary.csv ]]; then
  REPORT_ARGS+=(--adaptive-summary "$ANALYSIS/summary.csv")
fi
python3 "$ROOT/plots/make_report_figures.py" \
  --refresh-summary "$REFRESH_OUTPUT/analysis/summary.csv" \
  "${REPORT_ARGS[@]}" --outdir "$FIGURES" --analysisdir "$ANALYSIS"
echo "Baseline/adaptive summary: $ANALYSIS/summary.csv"
echo "Detailed metrics: $ANALYSIS/run_summary.csv and $ANALYSIS/flow_metrics.csv"
echo "Report comparison: $ANALYSIS/table_iii.csv"
echo "Baseline/adaptive figures: $FIGURES"
echo "Refresh summaries and figures: $REFRESH_OUTPUT/analysis"
