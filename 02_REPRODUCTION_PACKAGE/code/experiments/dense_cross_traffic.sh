#!/usr/bin/env bash
set -euo pipefail

: "${STATE_EXAMPLE:?STATE_EXAMPLE is not set. Run inside the course container.}"


ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
STATE_2160=${1:-/work/state_2160/state}
RUNS=${2:-/work/runs_repro}
ANALYSIS=${3:-/work/analysis_generated}

mkdir -p "$RUNS" "$ANALYSIS"

# Five adaptive Vegas flows, 2160 satellites, 200 seconds.
FLOWS="2160>2161,2160>2161,2160>2161,2160>2161,2160>2161" \
make_run.sh "$RUNS/vegas_2160_five_flow_adaptive" \
  "$STATE_2160" TcpVegas 100 1000 200 0 0

run_sim.sh "$RUNS/vegas_2160_five_flow_adaptive" 2>&1 \
  | tee "$ANALYSIS/vegas_2160_five_flow_adaptive_console.txt"

# Standard vs adaptive Vegas with UDP cross-traffic.
# 1584 satellites, 100 Mbps path, 200-second simulation.
# UDP sends 85 Mbps from t=35s until t=200s.

PATCH="$ROOT/adaptive-vegas.patch"

PATCH_WAS_APPLIED=false
if git -C "$NS3_DIR" apply --reverse --check \
    --ignore-space-change --ignore-whitespace "$PATCH"; then
    PATCH_WAS_APPLIED=true
fi

restore_patch_state() {
    if [ "$PATCH_WAS_APPLIED" = false ]; then
        if git -C "$NS3_DIR" apply --reverse --check \
            --ignore-space-change --ignore-whitespace "$PATCH"; then
            git -C "$NS3_DIR" apply -R \
                --ignore-space-change --ignore-whitespace "$PATCH"
        fi
    fi
}
trap restore_patch_state EXIT

run_udp_case() {
    local NAME="$1"
    local UDP_RUN="$RUNS/$NAME"

    mkdir -p "$ANALYSIS"

    make_run.sh "$UDP_RUN" "$STATE_EXAMPLE" TcpVegas \
        100 1000 200 1584 1585

    cat > "$UDP_RUN/udp_burst_schedule.csv" <<'EOF'
0,1584,1585,85,35000000000,165000000000,,
EOF

    local CONFIG="$UDP_RUN/config_ns3.properties"

    sed -i -E \
      '/^[[:space:]]*(enable_udp_burst_scheduler|udp_burst_schedule_filename|udp_burst_enable_logging_for_udp_burst_ids)[[:space:]]*=/d' \
      "$CONFIG"

    cat >> "$CONFIG" <<'EOF'
enable_udp_burst_scheduler=true
udp_burst_schedule_filename="udp_burst_schedule.csv"
udp_burst_enable_logging_for_udp_burst_ids=set(0)
EOF

    run_sim.sh "$UDP_RUN" \
        2>&1 | tee "$ANALYSIS/${NAME}_console.txt"
}

# Standard Vegas
if [ "$PATCH_WAS_APPLIED" = true ]; then
    git -C "$NS3_DIR" apply -R \
        --ignore-space-change --ignore-whitespace "$PATCH"
fi

echo "Running standard Vegas with UDP cross-traffic..."
run_udp_case "vegas_1584_udp85_standard"

# Adaptive Vegas
git -C "$NS3_DIR" apply \
    --ignore-space-change --ignore-whitespace "$PATCH"

echo "Running adaptive Vegas with UDP cross-traffic..."
run_udp_case "vegas_1584_udp85_adaptive"
