# Experiment / file map

## T1 — Standard Vegas, default 1,584 satellites
**Purpose:** baseline performance on the provided topology.

Raw tested files:
- `01_TESTED_RAW_RESULTS/runs/vegas_1584_200/`

Important outputs:
- `logs_ns3/tcp_flows.csv` — flow throughput summary
- `logs_ns3/tcp_flow_0_rtt.csv` — RTT trace
- `logs_ns3/tcp_flow_0_cwnd.csv` — cwnd trace
- `config_ns3.properties`, `schedule.csv` — exact run configuration

Reference average: **41.5 Mbit/s**.

## T2 — Standard Vegas, controlled 2,160 satellites
**Purpose:** strongest stale-BaseRTT failure case.

Raw tested files:
- `01_TESTED_RAW_RESULTS/runs/vegas_2160_200/`
- `01_TESTED_RAW_RESULTS/runs/dense_vegas/`

Mechanism-analysis files:
- `01_TESTED_RAW_RESULTS/analysis/vegas_2160_internal.csv`
- `01_TESTED_RAW_RESULTS/analysis/resampled_2160.csv`
- `01_TESTED_RAW_RESULTS/analysis/vegas_2160_direct_trace.txt`
- `01_TESTED_RAW_RESULTS/analysis/vegas_2160_instrumented_console.txt`

Reference average: **12.1 Mbit/s**.

Key event: route-induced propagation RTT increase near **39.9 s**, approximately **81.143 -> 85.448 ms (+4.305 ms)**.

## T3 — CUBIC capacity control, 1,584 satellites
**Purpose:** show the same nominal 100 Mbit/s path can carry near-link-rate traffic, so low Vegas throughput is not simply a low-capacity path.

Raw tested files:
- `01_TESTED_RAW_RESULTS/runs/cubic_1584_200/`

Reference average: **95.9 Mbit/s**.

## T4 — CUBIC capacity control, 2,160 satellites
Raw tested files:
- `01_TESTED_RAW_RESULTS/runs/cubic_2160_200/`

Reference average: **95.9 Mbit/s**.

## T5 — Instrumented Vegas mechanism trace
**Purpose:** connect stale BaseRTT -> high Vegas diff -> DECREASE decisions -> cwnd/throughput collapse.

Files:
- `01_TESTED_RAW_RESULTS/runs/vegas_2160_instrumented/`
- `01_TESTED_RAW_RESULTS/analysis/vegas_2160_instrumented_console.txt`
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_internal.csv`

Look for `VEGAS_TRACE` lines containing time, BaseRTT, minRTT, cwnd, targetCwnd, diff, alpha/beta/gamma, and action.

## T6 — Oracle reset immediately after route change
**Purpose:** causal timing control; asks whether simply resetting BaseRTT immediately is enough.

Files:
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_oracle_console.txt`

Observed event:
- `ORACLE_RESET,39.9355,82.4517,88.2292`

Reference average: **13.0 Mbit/s** — did not recover.

## T7 — Delayed oracle reset
**Purpose:** show BaseRTT relearning can recover performance if done after the new RTT floor stabilizes.

Files:
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_oracle_v2_console.txt`
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_oracle_v2_internal.csv`

Observed event:
- `ORACLE_RESET,40.5002,82.4517,87.2921`

Reference average: **71.0 Mbit/s**.

## T8 — Adaptive Vegas, 2,160 satellites
**Purpose:** main proposed solution.

Implementation:
- `03_ADAPTIVE_IMPLEMENTATION/adaptive-vegas.patch`
- `03_ADAPTIVE_IMPLEMENTATION/tcp-vegas.cc`
- `03_ADAPTIVE_IMPLEMENTATION/tcp-vegas.h`

Console evidence:
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_adaptive_v1_console.txt`

Observed reset:
- `ADAPTIVE_RESET,40.4762,82.4517,87.0198`

Reference average: **71.0 Mbit/s**.

## T9 — Adaptive Vegas, 1,584 satellites
**Purpose:** check that the idea also helps outside the strongest dense case.

Console evidence:
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_1584_adaptive_v1_console.txt`

Observed resets:
- `122.213 s`: `88.5564 -> 91.7887 ms`
- `188.059 s`: `91.4341 -> 99.451 ms`

Reference average: **64.7 Mbit/s**.

## T10 — Five-flow congestion-safety test
**Purpose:** check whether persistent real shared-path congestion falsely triggers BaseRTT relearning.

Files:
- `03_ADAPTIVE_IMPLEMENTATION/congestion_schedule.csv`
- `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_1584_congestion_safety_console.txt`
- clean rerun logic: `02_REPRODUCTION_PACKAGE/code/experiments/adaptive_runs.sh`

Setup:
- one Vegas flow from 0 s
- four more start at 35 s
- 60 s total

Observed result:
- **0 adaptive resets after cross-traffic begins**
- run-average flow rates approximately **20.6, 10.0, 10.2, 12.9, 13.0 Mbit/s**

This is limited safety evidence, not a proof of universal congestion safety.
