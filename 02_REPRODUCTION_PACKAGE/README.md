# CS30401 Lab 1 — Adaptive TCP Vegas for Dynamic LEO Paths

This repository contains the reproducibility package for our CS30401 Lab 1 study of TCP Vegas under dynamic LEO routing.

## Problem and idea

Standard TCP Vegas keeps `BaseRTT` as the minimum RTT observed over the connection. When a LEO route change causes a persistent upward propagation-delay shift, that historical minimum can become stale. Vegas can then interpret the new propagation baseline as queueing, repeatedly reduce `cwnd`, and settle at low throughput.

Our modification adds a sender-side adaptive BaseRTT relearning rule. If the per-cycle minimum RTT remains more than 3 ms above the stored BaseRTT for 5 consecutive Vegas cycles, and at least 10 s have passed since the previous reset, BaseRTT is relearned from the current minimum RTT. The implementation uses sender RTT history only; it does not require satellite IDs, route oracle information, receiver changes, or network signaling.

## Environment

Use the official course image:

```text
ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

The experiments were run with ns-3.48 + the course Hypatia-based LEO environment. Unless noted otherwise: 100 Mbit/s ISL/GSL links, 1000-packet drop-tail queues, no TCP pacing, 100 ms routing-state updates, and seed 123456789.

## Repository contents

```text
code/
  adaptive-vegas.patch       Final ns-3 patch
  run_all.sh                 End-to-end reproduction
  generate_state.sh          2160-satellite controlled topology generation
  experiments/               Baseline, adaptive, and safety runs
  analysis/                  Result extraction + original analysis scripts
  plots/                     Figure generation
  config/                    Reference schedules/configuration
results/reference/            Compact reference traces used during development
```

Generated constellation states, ns-3 trees, run directories, and large logs are intentionally excluded.

## Reproduce everything

Start a **fresh official course container** with this repository mounted somewhere under `/work`. Then run:

```bash
bash /work/<repo-folder>/code/run_all.sh
```

The script performs the following in order:

1. Generates the controlled 2160-satellite state (72 planes × 30 satellites; Seoul and London ground stations).
2. Runs standard Vegas on 1584 and 2160 satellites.
3. Runs CUBIC controls on both topologies.
4. Applies `adaptive-vegas.patch` to the clean ns-3.48 tree.
5. Runs adaptive Vegas on 2160 and 1584 satellites.
6. Runs the congestion-safety control with one flow from 0 s and four additional flows from 35 s.
7. Extracts a summary CSV and generates comparison figures.

Output locations:

```text
/work/runs_repro/
/work/analysis_generated/summary.csv
/work/figures_generated/
```

### Expected runtime

On the machine used for development, each 200 s simulation was roughly a few minutes or less, while the 60 s congestion-safety run was about half a minute. End-to-end runtime depends on CPU and state-generation time; allow roughly 15–30 minutes for the complete script.

## Key reproduced results

The development runs produced the following main averages:

| Experiment | Average throughput |
|---|---:|
| Standard Vegas, 1584 satellites | 41.5 Mbit/s |
| Standard Vegas, 2160 satellites | 12.1 Mbit/s |
| Adaptive Vegas, 1584 satellites | 64.7 Mbit/s |
| Adaptive Vegas, 2160 satellites | 71.0 Mbit/s |
| CUBIC, 1584 satellites | 95.9 Mbit/s |
| CUBIC, 2160 satellites | 95.9 Mbit/s |

In the 2160-satellite case, the important route event was an upward propagation-RTT change near 39.9 s. Instrumentation showed stale BaseRTT causing Vegas `diff` to exceed its decrease threshold after the route shift. The adaptive sender detected the persistent shift and reset BaseRTT at approximately 40.48 s in the development run.

The congestion-safety control introduced four competing flows at 35 s. No `ADAPTIVE_RESET` was triggered in that run, providing evidence that this tested queueing/contention event did not falsely trigger the relearning rule.

These values are reference results, not hard-coded pass criteria. Small timing differences can occur across machines; the scripts regenerate results from the simulator.

## Patch details

Apply manually, if desired:

```bash
cd "$NS3_DIR"
git apply --check /work/<repo-folder>/code/adaptive-vegas.patch
git apply /work/<repo-folder>/code/adaptive-vegas.patch
```

The patch modifies only:

```text
src/internet/model/tcp-vegas.cc
src/internet/model/tcp-vegas.h
```

## Congestion-safety schedule

`code/config/congestion_schedule.csv` uses five flows from Seoul (1584) to London (1585): flow 0 begins at 0 s; flows 1–4 begin at 35 s. All flows in a run use the same TCP variant, as required by the course framework.

## Figure/table mapping

- Main standard-vs-adaptive throughput comparison: `/work/figures_generated/standard_vs_adaptive.png`
- CUBIC topology-capacity control: `/work/figures_generated/cubic_controls.png`
- Numeric values used by generated figures: `/work/analysis_generated/summary.csv`
- Internal Vegas mechanism traces from development are included under `results/reference/` for audit/reference, but they are not required by `run_all.sh`.

## Limitations

The 2160-satellite topology is a controlled density perturbation, not a claim about a particular deployed Starlink configuration. The adaptive parameters (3 ms threshold, 5 cycles, 10 s cooldown) are a deliberately simple first-pass setting and are not claimed to be globally optimal. The safety result demonstrates no false reset under the tested multi-flow contention scenario; it does not prove safety under every possible queueing pattern.
