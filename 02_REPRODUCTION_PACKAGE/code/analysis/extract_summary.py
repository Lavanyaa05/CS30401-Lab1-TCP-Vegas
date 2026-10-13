
#!/usr/bin/env python3
from pathlib import Path
import csv
import re
import sys
from collections import defaultdict

RUNS = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/runs_repro")
ANALYSIS = Path(sys.argv[2] if len(sys.argv) > 2 else "/work/analysis_generated")
MSS = 1380  # Verify against the configured TCP segment size.

ANALYSIS.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.reader(f))


def write_csv(name, header, rows):
    path = ANALYSIS / name
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{path}: {len(rows)} rows")


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def console_for(run_name):
    # Most run logs use the run directory name as the console filename.
    candidates = [
        ANALYSIS / f"{run_name}_console.txt",
        ANALYSIS / f"{run_name}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path

    # Some existing scripts use different descriptive names.
    aliases = {
        "vegas_1584_congestion_safety":
            "vegas_1584_congestion_safety_console.txt",
        "vegas_diagnostic": "vegas_diagnostic_console.txt",
    }
    if run_name in aliases:
        path = ANALYSIS / aliases[run_name]
        if path.exists():
            return path
    return None


summary = []
flows_out = []
timeseries = []
events = []
fairness = []

for run_dir in sorted(RUNS.iterdir()):
    logs = run_dir / "logs_ns3"
    if not logs.is_dir():
        continue

    run = run_dir.name
    flow_rows = read_csv(logs / "tcp_flows.csv")
    flow_data = {}

    for row in flow_rows:
        if len(row) < 9:
            continue
        try:
            fid, src, dst = int(row[0]), int(row[1]), int(row[2])
            configured_size = number(row[3])
            start_ns, end_ns, duration_ns = map(float, row[4:7])
            sent_bytes = number(row[7])
            status = row[8]
        except (ValueError, TypeError):
            continue

        duration_s = duration_ns / 1e9
        rate = (
            sent_bytes * 8 / duration_s / 1e6
            if sent_bytes is not None and duration_s > 0
            else None
        )

        flow_data[fid] = {
            "src": src, "dst": dst,
            "start": start_ns / 1e9,
            "end": end_ns / 1e9,
        }

        flows_out.append([
            run, fid, src, dst, configured_size,
            start_ns / 1e9, end_ns / 1e9, duration_s,
            sent_bytes, rate, status
        ])

    # Read CWND, RTT and delivered-byte progress traces.
    for fid, info in sorted(flow_data.items()):
        for metric, filename in [
            ("cwnd_bytes", f"tcp_flow_{fid}_cwnd.csv"),
            ("rtt_ns", f"tcp_flow_{fid}_rtt.csv"),
            ("delivered_bytes", f"tcp_flow_{fid}_progress.csv"),
        ]:
            for row in read_csv(logs / filename):
                if len(row) < 3:
                    continue
                try:
                    row_fid = int(row[0])
                    t = float(row[1]) / 1e9
                    value = float(row[2])
                except ValueError:
                    continue

                if row_fid != fid:
                    continue

                if metric == "rtt_ns":
                    value /= 1e6  # milliseconds
                    unit = "ms"
                elif metric == "cwnd_bytes":
                    unit = "bytes"
                else:
                    unit = "bytes"

                timeseries.append([
                    run, fid, t, metric, value, unit
                ])

    # Aggregate per-flow goodput and Jain fairness over common windows.
    # Throughput is calculated from cumulative delivered-byte traces.
    windows = [(0, 45), (45, 60), (60, 100), (45, 100)]

    def delivered_at(rows, t):
        if not rows:
            return None
        points = []
        for row in rows:
            if len(row) < 3:
                continue
            try:
                points.append((float(row[1]) / 1e9, float(row[2])))
            except ValueError:
                pass
        points.sort()
        if not points or t < points[0][0] or t > points[-1][0]:
            return None
        for i in range(1, len(points)):
            t0, b0 = points[i - 1]
            t1, b1 = points[i]
            if t0 <= t <= t1:
                if t1 == t0:
                    return b1
                return b0 + (b1 - b0) * (t - t0) / (t1 - t0)
        return points[-1][1] if t == points[-1][0] else None

    progress = {
        fid: read_csv(logs / f"tcp_flow_{fid}_progress.csv")
        for fid in flow_data
    }

    for begin, end in windows:
        rates = []
        for fid, info in sorted(flow_data.items()):
            # Exclude flows not active for the entire measurement window.
            if info["start"] > begin or info["end"] < end:
                continue
            b0 = delivered_at(progress[fid], begin)
            b1 = delivered_at(progress[fid], end)
            if b0 is None or b1 is None:
                continue
            rates.append((fid, max(0, b1 - b0) * 8 / (end - begin) / 1e6))

        if not rates:
            continue

        values = [rate for _, rate in rates]
        total = sum(values)
        jain = (
            total * total / (len(values) * sum(v * v for v in values))
            if sum(v * v for v in values) > 0 else None
        )
        fairness.append([run, begin, end, len(values), total, jain])

    # Preserve Vegas/reset event lines for later analysis.
    console = console_for(run)
    reset_count = 0
    trace_count = 0

    if console:
        for line in console.read_text(errors="ignore").splitlines():
            if line.startswith("VEGAS_TRACE,"):
                fields = line.split(",")
                trace_count += 1
                if len(fields) >= 12:
                    events.append([
                        run, "VEGAS_TRACE",
                        fields[1], fields[2], fields[3],
                        fields[4], fields[5], fields[6],
                        fields[7], fields[8], fields[9],
                        fields[10], fields[11], line
                    ])
            elif line.startswith(("ADAPTIVE_RESET,", "ORACLE_RESET,")):
                fields = line.split(",")
                reset_count += 1
                events.append([
                    run, fields[0],
                    fields[1] if len(fields) > 1 else "",
                    *([""] * 10), line
                ])

    summary.append([
        run, len(flow_data),
        sum(
            row[9] for row in flows_out
            if row[0] == run and row[9] is not None
        ),
        trace_count, reset_count,
        "console found" if console else "console missing"
    ])

write_csv("run_summary.csv", [
    "run", "flow_count", "sum_flow_average_rates_Mbps",
    "vegas_trace_events", "reset_events", "console_status"
], summary)

write_csv("flow_metrics.csv", [
    "run", "flow_id", "source", "destination", "configured_size",
    "start_s", "end_s", "duration_s", "sent_bytes",
    "average_rate_Mbps", "status"
], flows_out)

write_csv("timeseries.csv", [
    "run", "flow_id", "time_s", "metric", "value", "unit"
], timeseries)

write_csv("events.csv", [
    "run", "event_type", "time_s", "base_rtt_ms", "min_rtt_ms",
    "cwnd_segments", "target_cwnd", "diff", "alpha", "beta",
    "gamma", "ssthresh_segments", "action", "raw_line"
], events)

write_csv("fairness.csv", [
    "run", "window_start_s", "window_end_s", "flow_count",
    "aggregate_goodput_Mbps", "jain_fairness"
], fairness)
