# Matched adaptive versus refresh Vegas study

This package prepares 30 matched runs: three original constellation states ×
five variants × one/five flows. All runs last 200 simulated seconds. Primary
metrics cover **20–200 s**; secondary goodput covers **60–200 s**.

The package implements the experiment; it does not contain new satellite
measurements. Use the original Linux course ns-3.48 installation to generate
them. The existing reproduction scripts and historical results are unchanged.

Follow [LINUX_RUNBOOK.md](LINUX_RUNBOOK.md) for the exact commands.

## Implementation

`install_matched.py` requires the exact instrumented refresh source hashes
recorded in the supplied result ZIPs. It edits the Vegas model and configuration
helper at checked insertion points, adds a private detector header, and saves
byte-for-byte backups beside the ns-3 tree. It leaves the queue, retransmission,
flow and satellite observers unchanged. `--check` is read-only; installation is
idempotent only for identical installed sources and installer/detector versions.

The added `ns3::TcpVegas::AdaptiveBaseRtt` attribute defaults to false. The
configuration helper reads `VEGAS_ADAPTIVE=0|1` and retains `VEGAS_WINDOW_S`.
Adaptive plus a positive history is rejected both by the helper and model.

| Variant | VEGAS_WINDOW_S | VEGAS_ADAPTIVE |
|---|---:|---:|
| original | 0 | 0 |
| refresh1 | 1 | 0 |
| refresh5 | 5 | 0 |
| refresh10 | 10 | 0 |
| adaptive | 0 | 1 |

Adaptive exactly preserves the prototype's strict **>3 ms**, five eligible
calculations, and strict **>10 s** cooldown. Counting takes place only at the
original eligible Vegas calculation site; recovery/insufficient-sample branches
do not acquire new detector behavior. Eligible nonqualifying calculations reset
the counter. Ordinary minimum updates can lower BaseRTT between resets. No
route metadata, notification, additional traffic, or direct cwnd increase is used.

`VEGAS_DECISION` retains its existing columns. The added trace is:

```text
VEGAS_ADAPTIVE_RESET,time_ns,context,object,old_base_ns,new_base_ns
```

An object pointer distinguishes instances within one simulation; it is not a
stable course flow ID. Per-flow throughput and fairness use the course's flow
IDs, independent of internal decision/reset attribution.

## Integrity and completion

The runner validates constellation geometry, original state provenance, all
4,000 expected routing/bandwidth files, and the archived path snapshots against
actual incremental forwarding states. It hashes full state trees, all modified
sources, package scripts/helpers, generated schedules/configurations, and the
built executable. All compared cases must share source and executable hashes.
Metadata and archived path matching for 1,584/2,160 do not establish historical
route-file byte identity; the new full-tree hashes establish identity within
this rerun study. Reproducing the twelve archived controls is the additional gate.

Successful cases retain `evaluation.json` and `EVALUATION_COMPLETE.json`.
Completion requires successful simulator exit, `finished.txt=Yes`, nonzero queue
observer bindings, every flow observer, all required traces, complete queue bins,
and unchanged source/state/executable hashes. Receipts hash the retained raw
outputs. Analysis and validation check those hashes before using any results.

Cases run sequentially through the exact vendored course helpers. The runner
builds first and the course wrapper rebuilds if needed. A matching completed
case is verified and skipped. Matching incomplete cases require
`--retry-incomplete`; the entire old attempt is preserved as `incomplete_*`.
Changed inputs require a new output root. Do not run another source-editing or
simulation process against the same ns-3 tree during the study.

## Metrics and outputs

The untouched `vendor/analyze_suite.py` defines progress-counter goodput,
nearest-rank p95 of 100 ms SRTT samples, queue time integrals, drop scopes,
retransmission-event percentage, and common-window Jain fairness. The wrapper
uses compact arrays for monotonically ordered raw traces to reduce memory;
sample values, boundary lookup, and metric definitions remain the same.

Queues are summed across monitored device queues, rather than averaged over
idle devices. For five flows the p95 pools defined per-flow time samples;
the plotted SRTT is the mean across flows. Single-flow Jain fairness is
non-informative. All-zero goodput yields undefined fairness. Retransmission
percentage is not packet-loss probability. Per-second internal decision means
are event averages, not time-weighted averages.

Outputs under `<results>/analysis/` include:

- `summary.csv`, `per_flow.csv`, `adaptive_resets.csv`, `route_events.csv`.
- `analysis_manifest.json` and `validation.json`.
- Six eight-panel comparison plots and three fairness plots, each as PNG/PDF.
- `section_V_C2.md`, `comparison_table.md`, `replacement_V_C_paragraph.txt`.

Each completed case also has `vegas_decision.csv`, `adaptive_resets.csv`,
`timeseries_1s.csv`, and `timeseries_100ms.csv`. Full raw traces remain retained.
Route annotations are verified from the actual state inputs, including the
dense change near 39.9 s and the 500 change near 163.8 s.

The full validator requires exactly 30 cases and 90 per-flow rows and compares
all twelve single-flow original/refresh controls with archived values.
Goodput, mean/p95 SRTT and mean queue tolerances are 0.001 in reported units;
buffer-drop components and retransmission counts must match exactly. The report
and exporter refuse an incomplete, tampered, or regression-failing full study.
The runbook first validates the twelve single-flow controls with
`--expected-cases 12 --controls-only` before completing the remaining cases.

## Tests and evidence status

```bash
python3 -m unittest discover -s "$MATCHED_CODE/tests" -v
```

Tests reconstruct the recorded Linux Vegas model from the repository's adaptive
files plus the original patches and verify its hashes. They exercise installer
backups/idempotence/refusal, known counter and queue integrals, percentile and
fairness edge cases, tampered/incomplete evidence, and synthetic 30-case report
and export generation. When g++ or clang++ is available, they compile and run
the **production detector header** against strict threshold, persistence,
cooldown, downward-minimum, and independent-instance boundaries.

Synthetic fixtures are test data, not satellite results. The Linux smoke check
and full ns-3 simulation/build remain required before interpreting performance.
The optional state test also accepts the extracted Linux course state at
`STATE_500` (default: `~/cs30401/work/Vegas_500_AllInOne/state500/state`), copying
it into a temporary directory before testing tamper detection.

## Sources and licenses

`vendor/` contains unchanged code from the supplied `Vegas_Evaluation.zip` and
`Vegas_500_AllInOne.zip`. `reference/index.json` records result-archive, vendor,
and reference hashes; `reference/controls.csv` contains the twelve measured
refresh controls. This generated CSV uses LF line endings, pinned by Git
attributes; its checksum records those bytes. Its values are unchanged from
the original CRLF export, whose checksum is verified by a regression test.
The dependency project and lock are copied unchanged from
the evaluation package. The model modifications retain ns-3's GPL-2.0-only
notices; the course shell helpers retain their course provenance. Adaptive
behavior originates in this repository's `03_ADAPTIVE_IMPLEMENTATION` patch.

The optional `_import_inputs.py` is a development import utility for the
original Windows Downloads packages; it is not needed on Linux and does not
run simulations. Do not rerun it over modified references.
