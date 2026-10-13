# Recurring BaseRTT refresh: complete reproduction package

This is the **sliding-window BaseRTT experiment**, complementary to the group's adaptive relearning method. It combines the earlier `Vegas_Investigation`, `Vegas_Evaluation` and `Vegas_500_AllInOne` work into one 12-case workflow.

**Integration:** add this entire `07_RECURRING_BASERTT_REFRESH/` folder at the repository root. No existing file in folders `00`–`06` needs editing. This package neither invokes nor replaces `02_REPRODUCTION_PACKAGE/code/run_all.sh`. It uses its own output directories and a separate simulator installation/volume.

**Validation status:** the archived analysis reproduces 120 checked values across 12 completed cases. Patch application reproduces all seven recorded modified-source hashes. Regression tests cover the 12-case matrix, resume, incomplete-run recovery, input protection and analysis boundary behavior. **The new consolidated launcher has not completed a fresh end-to-end ns-3 rerun in this preparation environment.** Source-hash checks and mocked runner tests do not establish a new compilation or simulation result. See [VALIDATION.md](VALIDATION.md).

## 1. What this reproduces

| Satellites | Planes × satellites/plane | Sender → receiver | History lengths |
|---:|---:|---|---|
| 500 | 25 × 20 | Seoul 500 → London 501 | 0, 1, 5, 10 s |
| 1,584 | 72 × 22 | Seoul 1584 → London 1585 | 0, 1, 5, 10 s |
| 2,160 | 72 × 30 | Seoul 2160 → London 2161 | 0, 1, 5, 10 s |

`0` is **original Vegas with a lifetime minimum**, not a zero-RTT target. A nonzero history expires old RTT samples and uses the lowest remaining RTT. Refresh occurs on valid RTT observations; it is not a timer that blindly resets BaseRTT once every T seconds. At a decision, the baseline is clamped to the current cycle minimum to prevent unsigned subtraction underflow when an older cycle sample outlives the history window.

All 12 experiments use one continuously backlogged 100 GB transfer, 200 simulated seconds, 100 Mbps ISL/GSL links, 1,000-packet DropTail buffers, no pacing, seed 123456789, MSS 1,380 bytes, initial cwnd 10 segments, alpha=2, beta=4 and gamma=1. Ground stations are Seoul `(37.56826,126.97783)` and London `(51.50853,-0.12574)`. The course generator uses its 550 km / 53° shell parameters, +Grid ISLs, shortest-distance routing, 100 ms forwarding updates and its 25° elevation setting. The three layouts change both geometry and route history.

The full matrix is checked in as [experiment_matrix.json](experiment_matrix.json). Regenerate it with:

```bash
cd 07_RECURRING_BASERTT_REFRESH
python3 code/experiments.py plan
```

This command needs only Python's standard library and makes no simulator changes.



## 2. Recommended environment: a dedicated course container

Use the official image from the course environment guide. **Use a different ns-3 volume from the adaptive tests.** Both methods modify `tcp-vegas.cc/.h`, so applying one on top of the other is unsupported. The installer rejects a differing source baseline before modifying any file. It also accepts a simulator already patched with the exact recurring-refresh implementation.

From the repository root, on your Linux VM/host:

```bash
docker pull ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
docker run -it --rm --name lab1-refresh \
  -v cs30401-refresh-ns348:/home/ubuntu/ns-3.48 \
  -v "$PWD":/work/repo \
  ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

If `cs30401-refresh-ns348` already contains some other modification, choose a new volume name. Do not delete a volume containing work you need. The dedicated volume persists the refresh-patched simulator across container restarts. In Windows PowerShell use one line and `-v "${PWD}:/work/repo"`.

Inside the container:

```bash
cd /work/repo/07_RECURRING_BASERTT_REFRESH
export NS3_DIR=/home/ubuntu/ns-3.48
bash run_all.sh --threads 4
```

The launcher installs the locked Python environment with `uv`, checks/applies the patch, generates the three states, validates their metadata and route timelines, builds `main_satnet`, runs the 12 cases sequentially and generates CSVs and figures. Internet access is needed for the first dependency installation. The bundled `satgenpy` avoids a separate Hypatia checkout.

The `.venv/` and `generated/` directories are local to this addition and ignored by Git. Existing adaptive output paths such as `/work/runs_repro` are not used. Run as the course container's normal `ubuntu` user, not root; ns-3's launcher can reject root execution.

### If you already use a manual Linux VM installation

The simulator must be **course-enabled ns-3.48**, including the Hypatia satellite modules and `scratch/main_satnet`, not bare upstream ns-3. Use a separate clean installation if your current one contains adaptive changes. Follow `../06_ASSIGNMENT_REFERENCE/CS30401_26F_Lab1_Environment_Guide.pdf` to create it. Then:

```bash
cd /path/to/CS30401-Lab1-TCP-Vegas/07_RECURRING_BASERTT_REFRESH
export NS3_DIR="$HOME/cs30401-refresh/ns-3.48"
bash run_all.sh --threads 4
```

Use Python 3.12 and `uv` for the pinned scientific dependencies. The environment guide covers installation of `uv`, build tools and the course simulator. Paths to the simulator, generated outputs and state directories must not contain whitespace because the course launcher/config format assumes this.

### Record the actual environment

The image tag is the intended environment, not an immutable digest. On the Docker host retain:

```bash
docker image inspect ghcr.io/yeonjong21/cs30401-lab1:2026f-v1 \
  --format '{{json .RepoDigests}}'
```

Each run invocation also saves `generated/environment_<timestamp>.json` with OS, Python, compiler, source hashes, package source hash, ns-3 version and the course repository commit when `$LAB` is set. The historical archive does not establish an exact original Docker image digest.

## 3. Smoke test and individual cases

A short run checks build/logging only; it cannot reproduce route events or long-run throughput. Generate the states once, then reuse them for the smoke test and full matrix:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
uv sync --frozen --project code
uv run --frozen --project code python code/experiments.py states --threads 4
uv run --frozen --project code python code/experiments.py run \
  --ns3 "$NS3_DIR" --satellites 500 --windows 0 5 --duration 5 \
  --state-500 "$PWD/generated/states/sat500/state" --output "$PWD/smoke"
# Full 200 s matrix, reusing the generated states:
bash run_all.sh --threads 4
```

Even for a 5 s smoke run, automatically generated state covers 200 s. Route validation is against the complete archived timeline, so generating that state can still be expensive.

One layout or one case:

```bash
bash run_all.sh --satellites 1584
bash run_all.sh --satellites 2160 --windows 5
```

Other history selections use `--windows 0 1 5 10`. Keep the same output folder for subsets of the same experiment. Put a different duration in a different output folder. Analysis includes all completed cases already present in that output folder, not only the most recent selection.

To reuse separately generated course states, supply their **state directory**, not its parent:

```bash
bash run_all.sh \
  --state-500 /work/state500/state \
  --state-1584 /work/state1584/state \
  --state-2160 /work/state2160/state
```

They must contain exactly one `dynamic_state_100ms_for_200s` tree, all 2,000 forwarding and all 2,000 bandwidth snapshots, matching top-level metadata and the matching Seoul–London path timeline. The runner records a complete state-tree hash for resume checks. The reference timeline does not constrain every untraversed path in the network; the supplied generator and dependencies are retained for this reason.

For staged execution, replace `run` with `install` (patch only) or `states` (state generation/validation only) in `python code/experiments.py ...`. `install` does not build; `run` builds before launching cases.

## 4. Resume and failures

Repeat the identical run command to skip validated complete cases. If a simulation was interrupted:

```bash
bash run_all.sh --threads 4 --retry-incomplete
```

Only an incomplete case whose input specification still matches is retried. Its previous directory moves into `generated/incomplete/<name>_<timestamp>/`. That archive is outside `runs/`, so analysis cannot count it as an additional experiment. Changed source/package hashes, states or duration require a new output directory. Do not edit the code while a sweep is running, and do not run two sweeps against the same output or ns-3 tree concurrently.

A stopped state generation is different from a stopped simulation: move its incomplete `generated/states/satN/` directory aside and rerun state generation. `--retry-incomplete` applies to simulations, not state generation.

Useful logs:

- `generated/build.log`: compiler/build errors.
- `generated/states/satN/generation.log`: state generation progress/errors.
- `generated/paths/path_N.log`: path extraction/validation.
- `generated/runs/<case>/out.txt`: simulator output, Vegas decision/state logs and trace bindings.
- `generated/runs/<case>/launcher.log`: wrapper output.
- `evaluation.json`: intended inputs, written before execution.
- `EVALUATION_COMPLETE.json`: written only after a successful simulator exit and required trace checks.

If the installer reports `Baseline source differs`, use a fresh dedicated course installation. Do not force the patch or overwrite your adaptive files. If a path hash differs, keep the generated state and logs and investigate the environment/scenario difference before treating the results as matched.

State generation, compilation and detailed logging can take hours in a VM. The archived 12 simulations consumed about 1.52 hours in total, excluding state generation/build; this is historical timing, not a runtime promise. Allow several GB or more for generated routes and full per-ACK logs. `--threads` controls state generation, while simulations run sequentially.

## 5. Regenerate results without running ns-3

The ZIP includes compact evidence from all 12 completed runs. This route works with Python's standard library for CSVs:

```bash
cd 07_RECURRING_BASERTT_REFRESH
python3 code/reproduce_reference.py --no-plots
```

It verifies evidence checksums, copies the evidence to `generated-reference/`, recomputes the metrics and checks them against the archived targets. It never uses the expected values to generate a chart or simulation result. `reference/` stays unchanged. Choose `--output /some/new/folder` if the destination already exists.

For plots as well:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
uv sync --frozen --project code
uv run --frozen --project code python code/reproduce_reference.py
```

If you already made the CSV-only copy, rerun analysis on that copy instead:

```bash
uv run --frozen --project code python code/analyze.py generated-reference
python3 code/verify_results.py generated-reference/analysis/summary.csv
```

For fresh simulations, replace `generated-reference` with `generated`. To compare fresh 200 s results with all 12 historical targets:

```bash
python3 code/verify_results.py generated/analysis/summary.csv
```

The default tolerances are strict regression tolerances. A difference is a diagnostic to investigate, not permission to substitute reference numbers. For an explicitly approximate comparison you can supply `--rtol 0.01`; document that choice. All 12 cases must be present for reference verification. Smoke tests and partial selections are intentionally rejected by this numerical verifier.

### Reference values: average goodput during 20–200 s

| History | 500 satellites | 1,584 satellites | 2,160 satellites |
|---|---:|---:|---:|
| Original | 9.16 Mbps | 45.41 Mbps | 12.41 Mbps |
| 1 s | 89.28 Mbps | 78.75 Mbps | 82.17 Mbps |
| 5 s | 86.16 Mbps | 74.65 Mbps | 79.82 Mbps |
| 10 s | 82.14 Mbps | 70.84 Mbps | 73.54 Mbps |

A shorter history improves throughput in these runs but can learn a standing queue. For 2,160 satellites, 1 s yields 76.29 average total queued packets and p95 SRTT 111.19 ms; 5 s yields 15.65 packets and 92.00 ms. These are single-flow observations, not a multi-flow fairness result or evidence that one threshold is globally optimal.

## 6. Output and report mapping

Everything below is generated inside `<output>/analysis/`:

| File | Purpose |
|---|---|
| `summary.csv` | Goodput, SRTT, queues, drops, retransmissions, metadata and original-Vegas relative gain |
| `goodput_windows.csv` | Side-by-side 0–200 s, 20–200 s and 60–200 s goodput for full runs |
| `refresh_tradeoffs.png/.pdf` | Goodput, mean queue and p95 SRTT comparison |
| `throughput_and_queues.png/.pdf` | Goodput and queues over time for each constellation |
| `route_baseline_500.png/.pdf` and corresponding 1584/2160 files | Physical route RTT, effective BaseRTT, cwnd and goodput |
| `report_table.md` | Table to merge into the report; generated when plots are enabled |
| `route_events.csv`, `connectivity.csv` | Route-change times and sampled connectivity |
| `event_windows_500.csv`, `decision_examples.csv` | 500-satellite route-event investigations |

Each run also receives `timeseries_1s.csv`, `timeseries_100ms.csv`, `vegas_decision.csv` and `per_flow.csv`. Fresh raw runs include additional per-flow RTT samples. A packet retransmission is not necessarily a buffer-overflow loss.

- Goodput counts newly acknowledged application bytes, in decimal Mbps. `whole_goodput_mbps` starts at 0 s; `goodput_mbps` defaults to 20 s; `late_goodput_mbps` starts at 60 s. Later does not necessarily mean steady state.
- Queue occupancy is a time-weighted **sum across monitored device queues**. The maximum single queue is reported separately.
- SRTT percentiles use right-continuous 100 ms samples and nearest-rank p95. They include propagation delay, not just queueing delay.
- Queue and traffic-control drop counts are reported separately and summed. Retransmission percentage is retransmission events / data transmission events, not a packet-loss probability.
- With one positive-throughput flow, Jain fairness equals 1 automatically and provides no competition evidence.
- For adaptive results in the existing report, compare using the matching **0–200 s** column; do not compare those values with the default 20–200 s refresh average.

The compact archive retains exact 1 s goodput bins, 100 ms SRTT/cwnd samples, decisions and queue/retransmission event/bin traces. It omits huge raw per-ACK progress/RTT logs, simulator console logs and all generated constellation states. It can regenerate the supplied sampled summaries; arbitrary new sampling intervals require fresh raw runs. Archived subsecond 500-route event rates are explicitly labelled as previously derived when raw progress is absent. Archived configs include old relative state paths and are provenance only; the runner generates new configs for real simulations.

## 8. Files, dependencies and provenance

- `code/patches/ns3-refresh.patch`: the combined course-compatible patch, including sliding RTT history and passive queue/flow observers.
- `code/experiments.py`: plan/install/state/run stages, strict source and state checks, resume.
- `code/analyze.py`, `analysis_core.py`, `figures.py`: measured-trace analysis and figures.
- `code/reproduce_reference.py`, `verify_results.py`: offline evidence replay and regression.
- `code/course/`: course generator/path/config/launch helpers with attribution/license.
- `code/third_party/satgenpy/`: pinned Hypatia source, commit `0ac531c313eba2335f6344b46347140c3a0d4230`, with MIT license.
- `code/pyproject.toml`, `uv.lock`: retained locked scientific environment.
- `code/provenance/`: baseline/modified hashes, state metadata, path hashes, reference metrics, evidence checksums and upstream archive checksums.
- `reference/`: immutable compact experimental evidence for the 12 cases.
- `tests/`: regression and mocked orchestration checks, requiring only standard-library Python and Git for separate patch testing.

The patch changes four simulator source files and adds three observer headers **inside the dedicated external ns-3 tree**, not inside folders `00`–`06` of this GitHub repo. It does not change Vegas alpha/beta/gamma or add the adaptive detector. The exact affected paths are in `code/provenance/implementation.json`.

Historical implementations and original results used to prepare this package are identified in `code/provenance/package_origin.json`. The source commit recovered during preparation is not proof of the original measurement environment's commit. Review the applicable upstream GPL/MIT notices before redistribution; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Run local regression checks:

```bash
python3 -m unittest discover -s tests -v
```

This GitHub-oriented package includes compact reference results. If creating the handout's final submission ZIP, follow its separate layout and exclusions for generated states and simulation logs; do not blindly submit this entire GitHub addition as the final handout ZIP.
