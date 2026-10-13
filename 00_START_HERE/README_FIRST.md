# CS30401 Group Testing Pack — START HERE

This package collects the **actual files/results we used during development**, the **final Adaptive Vegas implementation**, the **current reproduction scripts**, the **reference graphs**, the **current report**, and the **recurring BaseRTT refresh experiments** so every group member can inspect and retest the project from one folder.

## What our project tests

Problem: after a LEO route change raises the true propagation RTT, TCP Vegas may keep an old historical `BaseRTT`. It then interprets part of the new propagation delay as queueing, reduces `cwnd`, and underutilizes the path.

Fix: sender-side Adaptive BaseRTT relearning. If the per-cycle minimum RTT remains more than **3 ms above BaseRTT for 5 consecutive Vegas cycles**, and the last reset was more than **10 s ago**, BaseRTT is relearned from the current cycle minimum RTT.

## Folder map

- `01_TESTED_RAW_RESULTS/` — original baseline/instrumented simulation runs and analysis files exported from the development environment.
- `02_REPRODUCTION_PACKAGE/` — clean scripts intended for fresh-container reruns of the main baseline, CUBIC, adaptive, and congestion-safety experiments.
- `03_ADAPTIVE_IMPLEMENTATION/` — final `adaptive-vegas.patch`, modified `tcp-vegas.cc/.h`, experiment schedules, and console traces for adaptive/oracle/safety development runs.
- `04_REFERENCE_GRAPHS/` — coloured graphs currently used as visual references.
- `05_CURRENT_REPORT/` — latest Word report with repaired graph rendering.
- `06_ASSIGNMENT_REFERENCE/` — lab handout and environment guide.
- `07_RECURRING_BASERTT_REFRESH/` — separate sliding-window BaseRTT implementation, 12-case reproduction workflow, compact reference evidence, analysis scripts, and regression checks. See its [README](../07_RECURRING_BASERTT_REFRESH/README.md) for full instructions.

## Fastest way for a teammate to retest the main experiments

Use the official course Docker image and a fresh ns-3 tree. Mount this package somewhere under `/work`, then run:

```bash
bash /work/<this-folder>/02_REPRODUCTION_PACKAGE/code/run_all.sh
```

That script is intended to rerun:

1. Standard Vegas, 1,584 satellites
2. Standard Vegas, 2,160 satellites
3. CUBIC, 1,584 satellites
4. CUBIC, 2,160 satellites
5. Adaptive Vegas, 2,160 satellites
6. Adaptive Vegas, 1,584 satellites
7. Five-flow congestion-safety test

It also generates a summary CSV and the current automated comparison plots.

**Important:** the fresh-container end-to-end reproduction has not yet been fully verified by the whole group. Treat failures as things to fix before final submission, not as proof the experiment is wrong.

## Oracle tests

Two oracle timing controls were also tested during development:

- immediate oracle reset: `39.9355 s`, average throughput about `13.0 Mbit/s` (did not recover)
- delayed oracle reset: `40.5002 s`, average throughput about `71.0 Mbit/s` (recovered)

Their actual console traces and the delayed-oracle internal CSV are in:

`03_ADAPTIVE_IMPLEMENTATION/analysis/`

The current clean `run_all.sh` does **not** automatically recreate the oracle variants. The oracle files are included so teammates can audit exactly what was observed, but the oracle experiment still needs a clean scripted reproduction path before we claim it as fully reproducible in the final submission.

## Reference result targets

These are the development-run values to compare against, not hard-coded pass/fail values:

| Test | Reference result |
|---|---:|
| Standard Vegas — 1,584 | 41.5 Mbit/s |
| Standard Vegas — 2,160 | 12.1 Mbit/s |
| Adaptive Vegas — 1,584 | 64.7 Mbit/s |
| Adaptive Vegas — 2,160 | 71.0 Mbit/s |
| CUBIC — 1,584 | 95.9 Mbit/s |
| CUBIC — 2,160 | 95.9 Mbit/s |
| Immediate oracle — 2,160 | 13.0 Mbit/s |
| Delayed oracle — 2,160 | 71.0 Mbit/s |

Adaptive reset timestamps observed during development:

- 2,160 adaptive: `40.4762 s`, BaseRTT `82.4517 -> 87.0198 ms`
- 1,584 adaptive: `122.213 s`, `88.5564 -> 91.7887 ms`
- 1,584 adaptive: `188.059 s`, `91.4341 -> 99.451 ms`

Congestion-safety development run:

- flow 0 started at 0 s
- flows 1–4 started at 35 s
- no `ADAPTIVE_RESET` occurred after cross-traffic began
- measured run averages: approximately 20.6, 10.0, 10.2, 12.9, 13.0 Mbit/s

## Recurring BaseRTT refresh experiments

`07_RECURRING_BASERTT_REFRESH/` complements the adaptive relearning method with a sliding RTT history. Old RTT samples expire, and BaseRTT uses the lowest remaining sample. Refresh happens on valid RTT observations, rather than blindly resetting BaseRTT on a timer. A history of `0` preserves original Vegas's lifetime minimum.

The separate workflow runs **12 cases**: 500, 1,584, and 2,160 satellites, each with histories of **0, 1, 5, and 10 seconds**. Each case uses a single Seoul–London flow for 200 simulated seconds, 100 Mbps links, and 1,000-packet DropTail buffers.

Use a **dedicated course-enabled ns-3.48 installation or Docker volume**: the adaptive and recurring-refresh patches both modify Vegas sources and must not be applied on top of each other. Follow the folder's [environment instructions](../07_RECURRING_BASERTT_REFRESH/README.md#2-recommended-environment-a-dedicated-course-container), then run inside that environment:

```bash
cd /work/<this-folder>/07_RECURRING_BASERTT_REFRESH
export NS3_DIR=/home/ubuntu/ns-3.48
bash run_all.sh --threads 4
```

This launcher installs the locked Python dependencies, checks/applies the patch, generates and validates constellation states, builds the simulator, runs the matrix, and produces CSVs and figures under `generated/analysis/`. It is separate from `02_REPRODUCTION_PACKAGE/code/run_all.sh`; the main launcher does not run these cases.

To regenerate archived metrics without running ns-3 or installing scientific dependencies:

```bash
cd /work/<this-folder>/07_RECURRING_BASERTT_REFRESH
python3 code/reproduce_reference.py --no-plots
```

This verifies compact evidence checksums, recomputes metrics into `generated-reference/`, and checks the archived targets. Plot-generation instructions are in the folder's README.

Archived reference **average goodput during 20–200 s**:

| RTT history | 500 satellites | 1,584 satellites | 2,160 satellites |
|---|---:|---:|---:|
| Original (`0`) | 9.16 Mbit/s | 45.41 Mbit/s | 12.41 Mbit/s |
| 1 s | 89.28 Mbit/s | 78.75 Mbit/s | 82.17 Mbit/s |
| 5 s | 86.16 Mbit/s | 74.65 Mbit/s | 79.82 Mbit/s |
| 10 s | 82.14 Mbit/s | 70.84 Mbit/s | 73.54 Mbit/s |

Shorter histories improve goodput in these archived runs but can learn a standing queue. These single-flow experiments do not establish multi-flow fairness. When comparing against the adaptive results in the current report, use the refresh analysis's matching **0–200 s** goodput column, rather than the 20–200 s values above.

**Validation status:** archived analysis reproduces 120 checked values across 12 completed cases, and patch checks reproduce all seven modified-source hashes. Regression tests cover orchestration and analysis, but the consolidated launcher has **not completed a fresh end-to-end ns-3 rerun in the preparation environment**. See [VALIDATION.md](../07_RECURRING_BASERTT_REFRESH/VALIDATION.md). The group still needs to verify that fresh rerun before claiming the consolidated workflow is fully reproduced.

## Before final submission

The group still needs to verify the complete fresh-container reproduction and make sure every figure/table in the final report has a command that regenerates it. In particular, the oracle controls and all final report figures must be connected to the reproduction package.
