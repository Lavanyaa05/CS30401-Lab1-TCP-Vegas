#!/usr/bin/env bash
set -euo pipefail

: "${STATE_EXAMPLE:?STATE_EXAMPLE is not set. Run inside the course container.}"
STATE_500=${1:-/work/state_500/state}
STATE_2160=${2:-/work/state_2160/state}
RUNS=${3:-/work/runs_repro}
ANALYSIS=${4:-/work/analysis_generated}
mkdir -p "$RUNS" "$ANALYSIS"

# Adaptive Vegas, 2160 satellites
make_run.sh "$RUNS/vegas_2160_adaptive" "$STATE_2160" TcpVegas 100 1000 200 2160 2161
run_sim.sh "$RUNS/vegas_2160_adaptive" 2>&1 | tee "$ANALYSIS/vegas_2160_adaptive_console.txt"

# Adaptive Vegas, 1584 satellites
make_run.sh "$RUNS/vegas_1584_adaptive" "$STATE_EXAMPLE" TcpVegas 100 1000 200 1584 1585
run_sim.sh "$RUNS/vegas_1584_adaptive" 2>&1 | tee "$ANALYSIS/vegas_1584_adaptive_console.txt"

# Adaptive Vegas, 500 satellites
make_run.sh "$RUNS/vegas_500_adaptive" "$STATE_500" TcpVegas 100 1000 200 500 501
run_sim.sh "$RUNS/vegas_500_adaptive" 2>&1 | tee "$ANALYSIS/vegas_500_adaptive_console.txt"

# Congestion safety: 1584 satellites, five flows, 60 s.
# Flow 0 starts at 0 s; the other four start at 35 s.
FLOWS="1584>1585,1584>1585,1584>1585,1584>1585,1584>1585" \
make_run.sh "$RUNS/vegas_1584_congestion_safety" "$STATE_EXAMPLE" TcpVegas 100 1000 60 0 0

cp "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/congestion_schedule.csv" \
   "$RUNS/vegas_1584_congestion_safety/schedule.csv"

run_sim.sh "$RUNS/vegas_1584_congestion_safety" 2>&1 | tee "$ANALYSIS/vegas_1584_congestion_safety_console.txt"