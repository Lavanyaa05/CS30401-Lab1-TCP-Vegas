# Validation status

On 2026-10-12, the Linux course VM passed **14 tests with no skips** using
Python 3.11.15, the locked matplotlib 3.11.2 environment, and g++ for the
production detector. This includes synthetic 30-case analysis/report/export,
PNG/PDF generation, and the extracted original 500-satellite state test.

The Linux checkout exposed two portability defects, now fixed: the generated
control CSV's recorded checksum used CRLF while Git stored LF, and the mocked
runner executable lacked its Unix execute bit. The control values were checked
field for field against both original result ZIPs; all twelve rows match.
Reference/vendor checkout line endings and generated control CSV line endings
are now pinned to LF without relaxing byte-level evidence checks.

Verified:

- Reconstructed refresh Vegas model files match the source hashes recorded in
  the supplied result archives; all bundled observer/reference hashes match.
- Installer insertion points, backups, idempotence and changed-source refusal.
- Production detector threshold, persistence, cooldown, downward-minimum and
  independent-instance boundaries.
- Runner dry-run, completion/resume, failed-attempt retention and input-change
  refusal using mocked subprocesses and synthetic output.
- Counter-window boundaries, queue integrals, p95 sampling, equal/unequal/zero
  traffic fairness, and retransmission counter/event consistency.
- Synthetic 30-case analysis, 90 flow rows, twelve-control regression gate,
  report tables/text, PNG/PDF plots, and compact/raw ZIP exports.
- Actual supplied 500-satellite state full digest, forwarding/path verification,
  and the route event at 163.8 s. Modified state data are rejected.
- Representative synthetic figures were visually inspected. Synthetic data
  remain under ignored test-artifact directories and are not measured results.

The matched implementation was installed into the exact recorded refresh
sources with byte-for-byte backups, and the course `main_satnet` build passed.
All three original state trees passed full input and reference-route validation.
The four real five-second dense smoke simulations passed analysis and validation
(four cases, twelve per-flow rows); PNG/PDF figures were generated and the
five-flow comparison was visually inspected. The adaptive five-flow smoke
recorded four resets; neither disabled control recorded any.

All twelve real 200-second single-flow original/refresh controls passed the
archived reproducibility gate. Every compared metric matched exactly using
the locked Python environment. The gate receipt is retained locally as
`matched-results-workflow/controls-validation.json` at the repository root.

Full-study completion requires `full_matrix: true`, thirty completed cases,
ninety flow rows, and twelve checked controls in
`matched-results/analysis/validation.json`. The local unattended workflow
records its current stage in `matched-results-workflow/status.txt` and its
execution log in `matched-results-workflow/workflow.log`. It stops on failure
and generates plots and report text only after the complete simulation matrix.
See [LINUX_RUNBOOK.md](LINUX_RUNBOOK.md); the report/export scripts require
validated full-study results before claiming adaptive performance.
