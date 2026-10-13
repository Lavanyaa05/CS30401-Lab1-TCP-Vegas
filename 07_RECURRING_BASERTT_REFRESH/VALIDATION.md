# Validation record

Prepared 12 October 2026 against repository main commit `2208e6640f0623e80c381d5bb7816e657130a25b`.

## Executed in this preparation session

- Read the current GitHub repository and cloned that exact commit. No applicable AGENTS.md was present in the checkout. The existing root and folders 00–06 remain unchanged.
- Generated the complete 12-case plan and checked constellation geometry, history settings, ground node IDs, fixed settings and unique names.
- Replayed all 12 compact archived cases. All **120 archived numerical regression checks passed** at absolute tolerance 1e-6 and relative tolerance 1e-8. Goodput windows at 0–200 s, 20–200 s and 60–200 s are emitted separately.
- Generated the goodput/queue timelines, goodput/queue/SRTT comparison and route/BaseRTT/cwnd plots from those measured CSVs.
- Applied the actual combined patch to a pristine fixture of its four affected baseline files. All seven resulting source SHA-256 hashes matched the implementations recorded in the experiment archive. Repeated installation detected the exact implementation and made no changes. The patch retains an upstream blank line at EOF to preserve measured file hashes; Git's whitespace warning does not indicate a failed apply.
- Ran six standard-library regression tests, including same-timestamp ACK sampling, rejection of decreasing ACK counters, evidence checksums, protected output paths and refusal to patch differing source.
- The orchestration regression launched all 12 cases using explicitly synthetic simulator fixtures, verified completed-case skipping, refusal of an unapproved incomplete retry, preservation of incomplete data in a separate archive, and rejection of a changed completed specification. These fixtures test control flow only and are not shipped as measured results.
- Checked Python compilation and shell syntax. Archived evidence retains byte identity through `.gitattributes` so Windows Git line-ending settings cannot invalidate its hashes.

## Not executed in this preparation session

- No new ns-3 compilation, constellation regeneration or full satellite simulation was performed. This environment has no installed course ns-3 tree or Docker executable. The baseline fixture verifies patch transformation, not compilation.
- The full course-container launcher, state validation and simulator runs must still be executed in a fresh dedicated official course environment before claiming a fresh end-to-end reproduction.
- The locked environment is included from the prior packages. Its complete fresh installation requires package-index access and has not been repeated here.
- No adaptive, mixed-protocol, multi-flow or new path/seed experiment is claimed by this package.

## Interpretation limits

Archived reference data are compact: 1 s goodput bins and 100 ms SRTT/cwnd samples retain the headline calculations, but full per-ACK progress and RTT are absent. Subsecond event rates in the archived 500-satellite event CSV are supplied derived measurements, not recoverable at arbitrary new boundaries from those bins. Fresh runs retain the raw traces.

Matching reference summaries establishes consistency of this analysis with the archived data. It does not establish accuracy of every simulator/model assumption or generality across routes, random seeds and congestion patterns.
