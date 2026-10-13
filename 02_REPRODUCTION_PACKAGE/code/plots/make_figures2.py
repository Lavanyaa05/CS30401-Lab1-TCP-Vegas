# Base RTT vs Min RTT, with their difference underneath
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path("/work/analysis_generated")
OUT = Path("/work/figures_generated")
OUT.mkdir(parents=True, exist_ok=True)

events = pd.read_csv(ROOT / "events.csv")
events = events[events["event_type"] == "VEGAS_TRACE"].copy()

for col in ["time_s", "base_rtt_ms", "min_rtt_ms"]:
    events[col] = pd.to_numeric(events[col], errors="coerce")

for run, data in events.groupby("run"):
    if not run.startswith("vegas_"):
        continue

    data = data.dropna(
        subset=["time_s", "base_rtt_ms", "min_rtt_ms"]
    ).sort_values("time_s")
    data = data[(data["time_s"] >= 35) & (data["time_s"] <= 50)]
    if data.empty:
        continue

    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    # Top: Base RTT and Min RTT
    ax[0].plot(data["time_s"], data["base_rtt_ms"],
               label="Base RTT", linewidth=1)
    ax[0].plot(data["time_s"], data["min_rtt_ms"],
               label="Min RTT", linewidth=1)
    ax[0].set_ylabel("RTT (ms)")
    ax[0].set_title(f"{run}: Base RTT vs Min RTT")
    ax[0].legend()

    # Bottom: difference between the two
    difference = data["min_rtt_ms"] - data["base_rtt_ms"]
    ax[1].plot(data["time_s"], difference, linewidth=1)
    ax[1].axhline(0, linewidth=0.8)
    ax[1].set_ylabel("Min RTT − Base RTT (ms)")
    ax[1].set_xlabel("Time (s)")

    for a in ax:
        a.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT / f"{run}_base_min_rtt.png", dpi=150)
    plt.close(fig)

    print(f"Saved {OUT / f'{run}_base_min_rtt.png'}")