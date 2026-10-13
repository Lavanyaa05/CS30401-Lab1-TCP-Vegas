#!/usr/bin/env bash
set -euo pipefail

: "${LAB:?LAB is not set.}"

OUT=${1:?Usage: generate_state.sh OUTPUT_DIR}
ORBITS=${2:-72}
SATS_PER_ORBIT=${3:-30}

python3 "$LAB/scripts/gen_state.py" "$OUT" \
  --threads 8 \
  --duration 200 \
  --orbits "$ORBITS" \
  --sats-per-orbit "$SATS_PER_ORBIT" \
  --gs "Seoul,37.56826,126.97783" \
  --gs "London,51.50853,-0.12574"