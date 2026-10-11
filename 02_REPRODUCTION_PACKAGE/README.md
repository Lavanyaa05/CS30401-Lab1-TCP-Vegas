# CS30401 Lab 1 — Adaptive TCP Vegas for Dynamic LEO Paths

This repository contains the reproducibility package for our CS30401 Lab 1 study of TCP Vegas under dynamic LEO routing.

## Environment

Use the official course image:

```text
ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

The experiments were run with ns-3.48 + the course Hypatia-based LEO environment. Unless noted otherwise: 100 Mbit/s ISL/GSL links, 1000-packet drop-tail queues, no TCP pacing, 100 ms routing-state updates, and seed 123456789.

## Repository contents

```text
code/
  .gitattributes             
  adaptive-vegas.patch       Final ns-3 patch
  run_all.sh                 End-to-end reproduction
  generate_state.sh          2160-satellite controlled topology generation
  experiments/               Baseline, adaptive, and safety runs
  analysis/                  Result extraction + original analysis scripts
  plots/                     Figure generation
  config/                    Reference schedules/configuration
```

## Reproduce everything

For the separate 30-case matched adaptive-versus-refresh study (including
five-flow fairness), see [the matched comparison package](code/matched_comparison/README.md)
and its [Linux runbook](code/matched_comparison/LINUX_RUNBOOK.md).
This study requires the original instrumented refresh environment and states;
it is independent of the existing reproduction workflow below.

  Start the fresh course container with /code mounted at /work/code:

```bash
bash /work/code/run_all.sh
``` 

### Expected runtime: ~15–25 minutes end-to-end.
What it does: Automatically generates the 2160-satellite state, executes unmodified standard Vegas and CUBIC baselines, applies the patch, builds/runs adaptive Vegas and congestion-safety experiments, and extracts all summary tables and comparison figures


Output locations:

```text
/work/runs_repro/
/work/analysis_generated/summary.csv
/work/figures_generated/
```

## Patch details

Apply manually, if desired:

```bash
cd "$NS3_DIR"
git apply --ignore-space-change --ignore-whitespace --check /work/code/adaptive-vegas.patch
git apply --ignore-space-change --ignore-whitespace /work/code/adaptive-vegas.patch
./ns3 build
```

The patch modifies only:

```text
src/internet/model/tcp-vegas.cc
src/internet/model/tcp-vegas.h
```
## Figure/table mapping

- Main standard-vs-adaptive throughput comparison: `/work/figures_generated/standard_vs_adaptive.png`
- CUBIC topology-capacity control: `/work/figures_generated/cubic_controls.png`
- Numeric values used by generated figures: `/work/analysis_generated/summary.csv`
- Internal Vegas mechanism traces from development are included under `results/reference/`
