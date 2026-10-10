import csv
import bisect

def read_trace(path, scale=1.0):
    rows = []
    with open(path) as f:
        for r in csv.reader(f):
            if not r:
                continue
            t = int(r[1]) / 1e9
            v = float(r[2]) / scale
            rows.append((t, v))
    return rows

def value_at(rows, t):
    times = [x[0] for x in rows]
    i = bisect.bisect_right(times, t) - 1
    if i < 0:
        return None
    return rows[i][1]

def throughput_1s(progress):
    times = [x[0] for x in progress]
    vals = [x[1] for x in progress]

    def acked(t):
        i = bisect.bisect_right(times, t) - 1
        return 0 if i < 0 else vals[i]

    out = {}
    for s in range(200):
        out[s] = (acked(s+1) - acked(s)) * 8 / 1e6
    return out

def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals)/len(vals) if vals else None

def analyse(name):
    base = f"/work/runs/vegas_{name}_200/logs_ns3"

    cwnd = read_trace(base + "/tcp_flow_0_cwnd.csv", 1000)   # kB
    rtt  = read_trace(base + "/tcp_flow_0_rtt.csv", 1e6)     # ms
    prog = read_trace(base + "/tcp_flow_0_progress.csv", 1)   # bytes
    thr  = throughput_1s(prog)

    samples = []
    for s in range(200):
        t = s + 0.5
        samples.append({
            "time": t,
            "cwnd": value_at(cwnd, t),
            "rtt": value_at(rtt, t),
            "thr": thr[s],
        })

    print(f"\n===== {name} satellites =====")

    windows = [
        (20,30),
        (30,40),
        (40,50),
        (50,60),
        (60,75),
        (75,100),
        (100,140),
        (140,170),
        (170,200),
    ]

    for a,b in windows:
        rows = [x for x in samples if a <= x["time"] < b]

        c = mean([x["cwnd"] for x in rows])
        r = mean([x["rtt"] for x in rows])
        th = mean([x["thr"] for x in rows])

        print(
            f"{a:3d}-{b:3d}s | "
            f"cwnd={c:8.2f} kB | "
            f"RTT={r:8.3f} ms | "
            f"throughput={th:8.2f} Mbit/s"
        )

    with open(f"/work/analysis/resampled_{name}.csv","w",newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s","cwnd_kB","rtt_ms","throughput_Mbps"])
        for x in samples:
            w.writerow([x["time"],x["cwnd"],x["rtt"],x["thr"]])

analyse("1584")
analyse("2160")
