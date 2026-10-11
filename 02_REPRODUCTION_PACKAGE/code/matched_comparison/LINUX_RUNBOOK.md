# Linux: run the matched adaptive/refresh study

Use the **original Linux VM** with the course ns-3.48/Hypatia installation and
the states that produced the supplied refresh ZIPs. These commands execute
ns-3 TCP, so Linux kernel TCP sysctls do not select the experiment's controller.
Allow several hours depending on VM resources; the increased-throughput cases
and instrumentation can be much slower than original Vegas. Retain sufficient
disk space for per-ACK logs plus the optional raw export.

## 1. Copy the prepared repository and input package

Put this repository at `~/cs30401/work/CS30401-Lab1-TCP-Vegas`.
If the 500 input package is not already extracted:

```bash
mkdir -p "$HOME/cs30401/work"
unzip -n "$HOME/Downloads/Vegas_500_AllInOne.zip" -d "$HOME/cs30401/work"
```

The original `Vegas_Investigation` and `Vegas_Evaluation` modifications must
already be installed in the VM's ns-3 tree. This installer deliberately refuses
an unmodified tree or the older standalone adaptive tree. If the read-only
check in step 3 fails, compare the named source file with the refresh VM's
version; do not replace whole model files or force a conflicting patch.

## 2. Set paths

```bash
export NS3_DIR="$HOME/cs30401/ns-3.48"
export LAB="$HOME/cs30401/lab"
export PATH="$LAB/scripts:$PATH"
export VEGAS_REPO="$HOME/cs30401/work/CS30401-Lab1-TCP-Vegas"
export MATCHED_CODE="$VEGAS_REPO/02_REPRODUCTION_PACKAGE/code/matched_comparison"
export STATE_500="$HOME/cs30401/work/Vegas_500_AllInOne/state500/state"
export STATE_1584="$LAB/data/seoul_london/state"
export STATE_2160="$HOME/cs30401/work/states/sat_2160/state"
export MATCHED_RESULTS="$HOME/cs30401/work/vegas-adaptive-matched"
```

Correct paths if your installation differs. Keep the state contents unchanged.
The expected layouts are 25×20, 72×22, and 72×30 satellites, with source and
destination node IDs N and N+1. Five-flow starts are 0–4 ms, with 100 GB per flow.

## 3. Check prerequisites and run package tests

```bash
test -f "$NS3_DIR/scratch/main_satnet/main_satnet.cc"
test -f "$STATE_500/tles.txt"
test -f "$STATE_1584/tles.txt"
test -f "$STATE_2160/tles.txt"
command -v bash
command -v python3
command -v g++
python3 -m unittest discover -s "$MATCHED_CODE/tests" -v
python3 "$MATCHED_CODE/install_matched.py" "$NS3_DIR" --check
```

Require passing tests, including the C++ detector test on Linux. The source
check does not write files. Test reconstruction requires Git and the original
adaptive files in this repository. Smoke and full runs must use separate roots.

## 4. Install adaptive mode and build

```bash
python3 "$MATCHED_CODE/install_matched.py" "$NS3_DIR"
cd "$NS3_DIR"
./ns3 build main_satnet
```

Save the printed backup location. Identical reinstallation is a no-op. The
runner does not modify the source or states after installation.

## 5. Preview the full 30-case matrix

```bash
python3 "$MATCHED_CODE/run_matched.py" \
  --scenarios sat500 default dense \
  --variants original refresh1 refresh5 refresh10 adaptive \
  --flows 1 5 --duration 200 \
  --sat500-state "$STATE_500" \
  --default-state "$STATE_1584" \
  --dense-state "$STATE_2160" \
  --output "$MATCHED_RESULTS" --dry-run
```

Expect 30 cases. Dry-run reads and verifies complete states/routes and sources
but does not create run directories or execute simulations.

## 6. Run four five-second smoke checks

```bash
python3 "$MATCHED_CODE/run_matched.py" \
  --scenarios dense --variants original adaptive --flows 1 5 --duration 5 \
  --dense-state "$STATE_2160" --output "$MATCHED_RESULTS-smoke"
python3 "$MATCHED_CODE/analyze_matched.py" \
  "$MATCHED_RESULTS-smoke" --start 0 --late-start 2
python3 "$MATCHED_CODE/validate_matched.py" \
  "$MATCHED_RESULTS-smoke" --expected-cases 4
```

These check compilation, mode selection, observer binding, completion, and
analysis. They do not measure long-run performance or prove adaptive activation.

## 7. Run controls, check their reproducibility, then finish the matrix

First run all twelve single-flow original/refresh controls:

```bash
python3 "$MATCHED_CODE/run_matched.py" \
  --scenarios sat500 default dense \
  --variants original refresh1 refresh5 refresh10 --flows 1 --duration 200 \
  --sat500-state "$STATE_500" --default-state "$STATE_1584" \
  --dense-state "$STATE_2160" --output "$MATCHED_RESULTS"
python3 "$MATCHED_CODE/analyze_matched.py" "$MATCHED_RESULTS" --start 20 --late-start 60
python3 "$MATCHED_CODE/validate_matched.py" "$MATCHED_RESULTS" --expected-cases 12 --controls-only
```

Only continue if those twelve controls reproduce the archived metrics.
Then request the entire matrix; the verified controls are skipped:

```bash
python3 "$MATCHED_CODE/run_matched.py" \
  --scenarios sat500 default dense \
  --variants original refresh1 refresh5 refresh10 adaptive \
  --flows 1 5 --duration 200 \
  --sat500-state "$STATE_500" --default-state "$STATE_1584" \
  --dense-state "$STATE_2160" --output "$MATCHED_RESULTS"
```

Keep the terminal alive (use an existing tmux session if available). The runner
prints each case and a heartbeat every 30 seconds; detailed output is in each
case's `launcher.log` and `out.txt`.

If interrupted, repeat the same command with `--retry-incomplete`. Previous
unfinished attempts are preserved. Source, package, state, or binary changes
require a fresh output root. Do not reuse the smoke root for 200-second runs.

## 8. Analyze and validate all 30 cases

```bash
python3 "$MATCHED_CODE/analyze_matched.py" "$MATCHED_RESULTS" --start 20 --late-start 60
python3 "$MATCHED_CODE/validate_matched.py" "$MATCHED_RESULTS" --expected-cases 30
```

Require PASS: 30 cases, 90 flow rows, and 12 archived controls checked. A control
mismatch is an investigation gate: inspect source/state/configuration
differences; do not weaken tolerances to make a comparison pass.

## 9. Generate figures and report-ready text

Use the evaluation package's locked plotting dependencies:

```bash
uv sync --frozen --project "$MATCHED_CODE"
uv run --frozen --project "$MATCHED_CODE" python \
  "$MATCHED_CODE/analyze_matched.py" "$MATCHED_RESULTS" --start 20 --late-start 60 --plots
python3 "$MATCHED_CODE/validate_matched.py" "$MATCHED_RESULTS" --expected-cases 30
python3 "$MATCHED_CODE/write_report_section.py" "$MATCHED_RESULTS"
```

If uv is absent, use the course-provided uv installation or a dedicated Python
virtual environment with matplotlib; the metric analysis itself needs only
Python's standard library. Revalidate after regenerating analysis artifacts.

Open `<results>/analysis/section_V_C2.md` and `comparison_table.md`. Insert the
new section after V-C, replace V-C's last paragraph with the generated text,
and assign table/figure numbers consistent with the report. The Word files
are not edited by this package. Review earlier statements that adaptive queue,
delay, 500-satellite coverage, or competitive fairness remain unmeasured.

Interpret SRTT together with queues, drops, retransmissions, and goodput. Compare
five-flow fairness over the common window. Do not choose a universal winner
from one seed and city pair or claim mixed-controller fairness.

## 10. Export compact and raw evidence

```bash
python3 "$MATCHED_CODE/package_matched.py" "$MATCHED_RESULTS" --include-raw
```

Outputs beside the result directory are `vegas-adaptive-matched_results.zip`
and `vegas-adaptive-matched_raw.zip`. The compact ZIP omits per-ACK progress and
SRTT traces. The raw ZIP includes all completed evidence for recalculation.
Each contains file checksums. Existing exports are never overwritten; rename
an old export before generating another one. Share the code package too.
