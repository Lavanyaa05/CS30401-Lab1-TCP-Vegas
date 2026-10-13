import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path("/work/analysis_generated")
OUT = Path("/work/figures_generated")
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "timeseries.csv")

for run in sorted(df["run"].unique()):
    if not run.startswith("vegas_"):
        continue

    data = df[df["run"] == run]
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    # Goodput: cumulative delivered bytes -> 1-second rate
    delivered = data[data["metric"] == "delivered_bytes"]

    if not delivered.empty:
        delivered = delivered.sort_values("time_s")
        delivered["second"] = delivered["time_s"].astype(int)

        for flow, f in delivered.groupby("flow_id"):
            per_second = f.groupby("second")["value"].last()
            goodput = per_second.diff() * 8 / 1e6
            ax[0].plot(goodput.index, goodput.values,
                       label=f"Flow {flow}", linewidth=1)

        ax[0].legend()
    ax[0].set_ylabel("Goodput (Mbps)")
    ax[0].set_title(run)

    # CWND
    cwnd = data[data["metric"] == "cwnd_bytes"]
    for flow, f in cwnd.groupby("flow_id"):
        ax[1].plot(
            f["time_s"],
            f["value"] / 1380,
            label=f"Flow {flow}",
            linewidth=1
        )

    if cwnd["flow_id"].nunique() > 1:
        ax[1].legend()

    ax[1].set_ylabel("CWND (segments)")
    ax[1].set_xlabel("Time (s)")

    for a in ax:
        a.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT / f"{run}_goodput_cwnd.png", dpi=150)
    plt.close(fig)

    print(f"Saved {OUT / f'{run}_goodput_cwnd.png'}")
