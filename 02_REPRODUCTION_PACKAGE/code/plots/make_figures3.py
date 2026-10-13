
# Grouped bar charts: goodput and P95 RTT
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path("/work/analysis_generated")
OUT = Path("/work/figures_generated")
OUT.mkdir(parents=True, exist_ok=True)

summary = pd.read_csv(ROOT / "run_summary.csv")
ts = pd.read_csv(ROOT / "timeseries.csv")

satellites = [500, 1584, 2160]
protocols = ["Standard Vegas", "Adaptive Vegas", "CUBIC"]

run_names = {
    (500, "Standard Vegas"): "vegas_500_standard",
    (1584, "Standard Vegas"): "vegas_1584_standard",
    (2160, "Standard Vegas"): "vegas_2160_standard",
    (500, "Adaptive Vegas"): "vegas_500_adaptive",
    (1584, "Adaptive Vegas"): "vegas_1584_adaptive",
    (2160, "Adaptive Vegas"): "vegas_2160_adaptive",
    (500, "CUBIC"): "cubic_500_control",
    (1584, "CUBIC"): "cubic_1584_control",
    (2160, "CUBIC"): "cubic_2160_control",
}

colors = {
    "Standard Vegas": "#7895B2",
    "Adaptive Vegas": "#8FAF8F",
    "CUBIC": "#C58B78",
}


def grouped_bar(values, ylabel, title, filename):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(satellites))
    width = 0.24

    for i, protocol in enumerate(protocols):
        y = [values.get((sat, protocol), np.nan) for sat in satellites]
        ax.bar(
            x + (i - 1) * width,
            y,
            width,
            label=protocol,
            color=colors[protocol],
            edgecolor="#444444",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in satellites])
    ax.set_xlabel("Satellite count")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)

    # Matching scale on the right side
    ax_right = ax.twinx()
    ax_right.set_ylim(ax.get_ylim())
    ax_right.set_yticks(ax.get_yticks())
    ax_right.set_ylabel(ylabel)
    ax_right.grid(False)

    fig.tight_layout()
    output_path = OUT / filename
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {output_path}")


# 1. Goodput: sum of per-flow average rates
goodput = {}

for (sat, protocol), run in run_names.items():
    row = summary[summary["run"] == run]
    if not row.empty:
        goodput[(sat, protocol)] = float(
            row.iloc[0]["sum_flow_average_rates_Mbps"]
        )

grouped_bar(
    goodput,
    "Goodput (Mbit/s)",
    "Goodput by satellite count and TCP algorithm",
    "comparison_goodput.png",
)

# 2. 95th-percentile RTT, converted from nanoseconds to milliseconds
rtt = ts[ts["metric"] == "rtt_ns"].copy()
rtt["value"] = pd.to_numeric(rtt["value"], errors="coerce")
rtt = rtt.dropna(subset=["value"])

p95 = rtt.groupby("run")["value"].quantile(0.95) / 1e6

rtt_values = {
    (sat, protocol): p95.get(run_names[(sat, protocol)], np.nan)
    for sat in satellites
    for protocol in protocols
}

grouped_bar(
    rtt_values,
    "P95 RTT (ms)",
    "95th-percentile RTT by satellite count and TCP algorithm",
    "comparison_p95_rtt.png",
)
