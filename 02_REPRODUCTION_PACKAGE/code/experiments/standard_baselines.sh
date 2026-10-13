
#!/usr/bin/env bash
set -euo pipefail

: "${STATE_EXAMPLE:?STATE_EXAMPLE is not set. Run inside the course container.}"

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

STATE_500=${1:-/work/state_500/state}
STATE_2160=${2:-/work/state_2160/state}
RUNS=${3:-/work/runs_repro}
ANALYSIS=/work/analysis_generated

mkdir -p "$RUNS"

# Standard TCP Vegas: 1584 satellites
make_run.sh "$RUNS/vegas_1584_standard" "$STATE_EXAMPLE" TcpVegas 100 1000 200 1584 1585
run_sim.sh "$RUNS/vegas_1584_standard"

# Standard TCP Vegas: 500 satellites
make_run.sh "$RUNS/vegas_500_standard" "$STATE_500" TcpVegas 100 1000 200 500 501
run_sim.sh "$RUNS/vegas_500_standard"

# Standard TCP Vegas: 2160 satellites
make_run.sh "$RUNS/vegas_2160_standard" "$STATE_2160" TcpVegas 100 1000 200 2160 2161
run_sim.sh "$RUNS/vegas_2160_standard"

# TCP CUBIC controls: 1584 satellites
make_run.sh "$RUNS/cubic_1584_control" "$STATE_EXAMPLE" TcpCubic 100 1000 200 1584 1585
run_sim.sh "$RUNS/cubic_1584_control"

# TCP CUBIC controls: 500 satellites
make_run.sh "$RUNS/cubic_500_control" "$STATE_500" TcpCubic 100 1000 200 500 501
run_sim.sh "$RUNS/cubic_500_control"

# TCP CUBIC controls: 2160 satellites
make_run.sh "$RUNS/cubic_2160_control" "$STATE_2160" TcpCubic 100 1000 200 2160 2161
run_sim.sh "$RUNS/cubic_2160_control"

# Standard Vegas: 2160 satellites, five flows, 200 s.
# Flows start at 0, 1, 2, 3, and 4 s.
FLOWS="2160>2161,2160>2161,2160>2161,2160>2161,2160>2161" \
make_run.sh "$RUNS/vegas_2160_five_flow_standard" "$STATE_2160" TcpVegas 100 1000 200 0 0

cp "/work/code/config/5_flow.csv" \
   "$RUNS/vegas_2160_five_flow_standard/schedule.csv"

run_sim.sh "$RUNS/vegas_2160_five_flow_standard" 2>&1 | tee "$ANALYSIS/vegas_2160_five_flow_standard_console.txt"