#!/usr/bin/env python3
from pathlib import Path
import csv, sys
import matplotlib.pyplot as plt

summary = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/analysis_generated/summary.csv")
outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "/work/figures_generated")
outdir.mkdir(parents=True, exist_ok=True)

rows = {}
with summary.open() as f:
    for r in csv.DictReader(f):
        rows[r["case"]] = None if not r["avg_rate_Mbit_s"] else float(r["avg_rate_Mbit_s"])

# Main standard-vs-adaptive comparison.
labels = ["1584", "2160"]
standard = [rows.get("Vegas standard 1584"), rows.get("Vegas standard 2160")]
adaptive = [rows.get("Vegas adaptive 1584"), rows.get("Vegas adaptive 2160")]

x = list(range(len(labels)))
width = 0.36
fig, ax = plt.subplots(figsize=(6.4, 4.2))
ax.bar([i-width/2 for i in x], standard, width, label="Standard Vegas")
ax.bar([i+width/2 for i in x], adaptive, width, label="Adaptive Vegas")
ax.set_xticks(x, labels)
ax.set_xlabel("Satellite count")
ax.set_ylabel("Average throughput (Mbit/s)")
ax.legend()
fig.tight_layout()
fig.savefig(outdir / "standard_vs_adaptive.png", dpi=220)
plt.close(fig)

# CUBIC controls.
cubic = [rows.get("CUBIC control 1584"), rows.get("CUBIC control 2160")]
fig, ax = plt.subplots(figsize=(6.4, 4.2))
ax.bar(labels, cubic)
ax.set_xlabel("Satellite count")
ax.set_ylabel("Average throughput (Mbit/s)")
fig.tight_layout()
fig.savefig(outdir / "cubic_controls.png", dpi=220)
plt.close(fig)

print(f"Wrote figures to {outdir}")
