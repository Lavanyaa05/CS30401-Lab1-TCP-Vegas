#!/usr/bin/env python3
from pathlib import Path
import csv, re, sys

RUNS = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/runs_repro")
ANALYSIS = Path(sys.argv[2] if len(sys.argv) > 2 else "/work/analysis_generated")
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "/work/analysis_generated/summary.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

cases = [
    ("Vegas standard 1584", "vegas_1584_standard", None),
    ("Vegas standard 2160", "vegas_2160_standard", None),
    ("CUBIC control 1584", "cubic_1584_control", None),
    ("CUBIC control 2160", "cubic_2160_control", None),
    ("Vegas adaptive 1584", "vegas_1584_adaptive", "vegas_1584_adaptive_console.txt"),
    ("Vegas adaptive 2160", "vegas_2160_adaptive", "vegas_2160_adaptive_console.txt"),
]

rate_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s+Mbit/s")
rows = []
for label, d, console in cases:
    p = RUNS / d / "logs_ns3" / "tcp_flows.txt"
    rate = None
    if p.exists():
        lines = [x for x in p.read_text().splitlines() if x and not x.startswith("TCP Flow ID")]
        if lines:
            m = rate_re.findall(lines[-1])
            if m:
                rate = float(m[-1])
    resets = 0
    if console:
        cp = ANALYSIS / console
        if cp.exists():
            resets = sum(1 for line in cp.read_text(errors="ignore").splitlines() if line.startswith("ADAPTIVE_RESET"))
    rows.append((label, rate, resets))

# Congestion safety: aggregate all five flows and count resets.
p = RUNS / "vegas_1584_congestion_safety" / "logs_ns3" / "tcp_flows.txt"
rates = []
if p.exists():
    for line in p.read_text().splitlines():
        if line and not line.startswith("TCP Flow ID"):
            m = rate_re.findall(line)
            if m:
                rates.append(float(m[-1]))
cp = ANALYSIS / "vegas_1584_congestion_safety_console.txt"
resets = 0
if cp.exists():
    resets = sum(1 for line in cp.read_text(errors="ignore").splitlines() if line.startswith("ADAPTIVE_RESET"))
rows.append(("Congestion safety aggregate", sum(rates) if rates else None, resets))

with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["case", "avg_rate_Mbit_s", "adaptive_reset_count"])
    w.writerows(rows)

for r in rows:
    print(r)
print(f"Wrote {OUT}")
