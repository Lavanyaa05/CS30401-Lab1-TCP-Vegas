import csv
import bisect
import os

def read_simple(path):
    rows = []
    with open(path) as f:
        for row in csv.reader(f):
            if not row:
                continue
            flow = int(row[0])
            t = int(row[1]) / 1e9
            value = float(row[2])
            rows.append((t, value))
    return rows

def read_path(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def latest_value(rows, t):
    times = [x[0] for x in rows]
    i = bisect.bisect_right(times, t) - 1
    if i < 0:
        return None
    return rows[i][1]

def throughput_bins(progress, duration=200, bin_s=1):
    times = [x[0] for x in progress]
    vals = [x[1] for x in progress]

    def acked_at(t):
        i = bisect.bisect_right(times, t) - 1
        if i < 0:
            return 0
        return vals[i]

    out = []
    for start in range(0, duration, bin_s):
        end = start + bin_s
        b0 = acked_at(start)
        b1 = acked_at(end)
        mbps = (b1 - b0) * 8 / 1e6 / bin_s
        out.append((start + bin_s/2, mbps))
    return out

def avg_near(series, t0, t1):
    vals = [v for t,v in series if t0 <= t < t1]
    if not vals:
        return None
    return sum(vals) / len(vals)

def analyse(name):
    base = f"/work/runs/vegas_{name}_200/logs_ns3"

    cwnd = read_simple(base + "/tcp_flow_0_cwnd.csv")
    rtt  = read_simple(base + "/tcp_flow_0_rtt.csv")
    prog = read_simple(base + "/tcp_flow_0_progress.csv")
    path = read_path(f"/work/path_{name}.csv")

    # units
    cwnd = [(t, v/1000) for t,v in cwnd]       # kB
    rtt  = [(t, v/1e6) for t,v in rtt]         # ms
    thr  = throughput_bins(prog)

    print("\n" + "="*70)
    print(f"{name} SATELLITES")
    print("="*70)

    changes = []
    for i, row in enumerate(path):
        if int(row["path_changed"]) == 1 and i > 0:
            t = float(row["t_s"])
            before = float(path[i-1]["rtt_prop_ms"])
            after = float(row["rtt_prop_ms"])
            jump = after - before
            changes.append((t, before, after, jump))

    for t, before, after, jump in changes:
        cw_before = avg_near(cwnd, max(0,t-5), t)
        cw_after  = avg_near(cwnd, t, min(200,t+10))

        rtt_before = avg_near(rtt, max(0,t-5), t)
        rtt_after  = avg_near(rtt, t, min(200,t+10))

        thr_before = avg_near(thr, max(0,t-5), t)
        thr_after  = avg_near(thr, t, min(200,t+10))

        print(f"\nRoute change @ {t:.1f}s")
        print(f"  Prop RTT: {before:.3f} -> {after:.3f} ms  jump={jump:+.3f} ms")

        if cw_before is not None and cw_after is not None:
            print(f"  cwnd avg:  {cw_before:.2f} -> {cw_after:.2f} kB")

        if rtt_before is not None and rtt_after is not None:
            print(f"  TCP RTT:   {rtt_before:.3f} -> {rtt_after:.3f} ms")

        if thr_before is not None and thr_after is not None:
            print(f"  Throughput:{thr_before:.2f} -> {thr_after:.2f} Mbit/s")

    return cwnd, rtt, thr, path, changes

d1584 = analyse("1584")
d2160 = analyse("2160")

print("\n\n===== DENSE CASE: 39.9 s EVENT IN MORE DETAIL =====")

cwnd, rtt, thr, path, changes = d2160

for a,b in [(20,30),(30,39.9),(39.9,50),(50,60),(60,75),(75,100),(100,140),(140,170),(170,200)]:
    c = avg_near(cwnd,a,b)
    r = avg_near(rtt,a,b)
    th = avg_near(thr,a,b)

    print(
        f"{a:5.1f}-{b:5.1f}s | "
        f"cwnd={c:8.2f} kB | "
        f"RTT={r:8.3f} ms | "
        f"throughput={th:8.2f} Mbit/s"
    )

# Save a compact CSV for later plotting/reporting
os.makedirs("/work/analysis", exist_ok=True)

with open("/work/analysis/dense_windows.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["start_s","end_s","avg_cwnd_kB","avg_rtt_ms","avg_throughput_Mbps"])
    for a,b in [(20,30),(30,39.9),(39.9,50),(50,60),(60,75),(75,100),(100,140),(140,170),(170,200)]:
        w.writerow([
            a,b,
            avg_near(cwnd,a,b),
            avg_near(rtt,a,b),
            avg_near(thr,a,b)
        ])

print("\nSaved: /work/analysis/dense_windows.csv")
