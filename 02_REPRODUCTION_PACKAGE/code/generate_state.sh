#!/usr/bin/env bash
set -euo pipefail

: "${LAB:?LAB is not set. Run inside the CS30401 course container.}"
OUT=${1:-/work/state_2160}

python3 "$LAB/scripts/gen_state.py" "$OUT" \
  --threads 4 \
  --duration 200 \
  --orbits 72 \
  --sats-per-orbit 30 \
  --gs "Seoul,37.56826,126.97783" \
  --gs "London,51.50853,-0.12574"
