#!/usr/bin/env bash
set -euo pipefail

: "${STATE_EXAMPLE:?STATE_EXAMPLE is not set. Run inside the course container.}"
STATE_2160=${1:-/work/state_2160/state}
RUNS=${2:-/work/runs_repro}
mkdir -p "$RUNS"

# Standard TCP Vegas, 1584-satellite example topology
make_run.sh "$RUNS/vegas_1584_standard" "$STATE_EXAMPLE" TcpVegas 100 1000 200 1584 1585
run_sim.sh "$RUNS/vegas_1584_standard"

# Standard TCP Vegas, 2160-satellite controlled density topology
make_run.sh "$RUNS/vegas_2160_standard" "$STATE_2160" TcpVegas 100 1000 200 2160 2161
run_sim.sh "$RUNS/vegas_2160_standard"

# CUBIC controls showing that the path still supports near-link-rate throughput
make_run.sh "$RUNS/cubic_1584_control" "$STATE_EXAMPLE" TcpCubic 100 1000 200 1584 1585
run_sim.sh "$RUNS/cubic_1584_control"

make_run.sh "$RUNS/cubic_2160_control" "$STATE_2160" TcpCubic 100 1000 200 2160 2161
run_sim.sh "$RUNS/cubic_2160_control"
