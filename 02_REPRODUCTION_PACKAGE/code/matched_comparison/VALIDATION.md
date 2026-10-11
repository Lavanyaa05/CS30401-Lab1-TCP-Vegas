# Validation status

The local test suite passed **13 tests with no skips** on Windows with Python
3.14. Plot tests used matplotlib 3.10.8; the production C++ detector was compiled
and executed with the locally installed portable Zig 0.16 compiler. On the
Linux course VM the test suite uses g++ or clang++ instead.

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

**Not yet executed:** the course ns-3 integration build, Linux smoke simulations,
and the 30 real 200-second satellite runs. This machine has no accessible
running course Linux environment. Run [LINUX_RUNBOOK.md](LINUX_RUNBOOK.md) on
the original VM before claiming adaptive performance, producing measured
Section V-C2 text, or exporting final experiment evidence. The report/export
scripts require validated full-study results.
