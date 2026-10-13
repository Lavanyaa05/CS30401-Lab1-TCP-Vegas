# CS30401 Lab 1 — Original, Adaptive and Recurring-Refresh TCP Vegas

This package runs the group's original Vegas/CUBIC controls, adaptive BaseRTT relearning, and recurring BaseRTT refresh in one command. `README.md` and `code/` contain the inputs for these experiments

## 1. Environment and prerequisites

The reference platform is the official course Docker image **`ghcr.io/yeonjong21/cs30401-lab1:2026f-v1`**: Ubuntu 24.04, **ns-3.48**, and the TA's Hypatia satellite modules. Bare upstream ns-3 and Hypatia's original ns-3.31 modules are insufficient. Python 3.12 and `uv` are recommended for the locked dependencies in `code/pyproject.toml` and `code/uv.lock`. The first Docker pull/dependency installation needs Internet access. Run the simulator as the normal container `ubuntu` user, not root.

The adaptive and refresh patches both modify `tcp-vegas.cc/.h` and must **never be stacked**. The combined script runs original controls on a clean `$NS3_DIR`, applies adaptive changes there, and uses a separate `$REFRESH_NS3_DIR` for refresh. By default it copies clean simulator sources before applying either method, excludes build caches, and configures a new release build. An existing refresh tree must match either the clean course baseline or the exact refresh implementation; source hashes are checked before installation.

Allow several GB for states, the extra simulator/build, and detailed per-ACK traces. State generation and full runs can take hours on a VM. Paths used for the simulator, code, states and outputs must not contain spaces.

### Docker setup (recommended; commands on the Linux VM/host)

```bash
docker pull ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
mkdir -p output
docker run -it --rm --name lab1-repro \
  -v cs30401-repro-clean-20261013:/home/ubuntu/ns-3.48 \
  -v "$PWD":/work/package \
  -v "$PWD/output":/work/output \
  ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

Inside the container:

```bash
cd /work/package
export NS3_DIR=/home/ubuntu/ns-3.48
# LAB, STATE_EXAMPLE and course scripts on PATH are set by the image.
check_env.sh
export REPRO_WORK=/work/output
bash code/run_all.sh --threads 4
```

`check_env.sh` checks the clean installation using ping RTT versus geometry (about 1–2 minutes). The runner then installs dependencies with `uv sync --frozen --project code`, builds the patched implementations, runs all experiments and produces analysis/plots. `--threads 4` controls refresh state generation; simulations remain sequential. The adaptive state's generator also uses four threads.

To record the actual image digest, run on the host:

```bash
docker image inspect ghcr.io/yeonjong21/cs30401-lab1:2026f-v1 \
  --format '{{json .RepoDigests}}'
```

The tag identifies the intended platform; the historical measurements do not establish an immutable original image digest.

### Manual Linux VM setup (Ubuntu 24.04/22.04)

These follow section 2.2 of the Lab Environment Guide. On Ubuntu 22.04, install newer CMake as shown; ns-3.48 needs CMake 3.25 or newer.

```bash
sudo apt update
sudo apt install -y g++ python3 python3-venv git curl bzip2 cmake ninja-build
curl -LsSf https://astral.sh/uv/install.sh | sh
# Open a new terminal so uv is on PATH.
# Ubuntu 22.04 only:
uv tool install cmake

mkdir -p "$HOME/cs30401-repro"
cd "$HOME/cs30401-repro"
git clone https://github.com/Yeonjong21/cs30401-lab1-env.git lab
git clone https://github.com/snkas/hypatia.git lab/hypatia
git -C lab/hypatia checkout 0ac531c313eba2335f6344b46347140c3a0d4230
curl -L -o ns-3.48.tar.gz \
  https://codeload.github.com/nsnam/ns-3-dev-git/tar.gz/refs/tags/ns-3.48
tar xzf ns-3.48.tar.gz
mv ns-3-dev-git-ns-3.48 ns-3.48
bash lab/scripts/setup_ns3.sh "$HOME/cs30401-repro/ns-3.48"
(cd lab && uv sync --frozen)
export NS3_DIR="$HOME/cs30401-repro/ns-3.48"
export LAB="$HOME/cs30401-repro/lab"
export STATE_EXAMPLE="$LAB/data/seoul_london/state"
export PATH="$LAB/scripts:$PATH"
source "$LAB/.venv/bin/activate"
check_env.sh
```

Then change into this reproduction package and run:

```bash
export REPRO_WORK="$HOME/cs30401-repro-output"
bash code/run_all.sh --threads 4
```

The runner installs its own locked Python environment at `$REPRO_WORK/repro_venv`. A manual installation must retain its actual environment repository commit; a changing upstream `main` is not a pinned historical version. Record it, along with OS/compiler/version information:

```bash
cat /etc/os-release
g++ --version
cat "$NS3_DIR/VERSION"
git -C "$LAB" rev-parse HEAD
```

The refresh runner also writes `refresh_generated/environment_<timestamp>.json` with platform, compiler, Python, ns-3 version, source hashes and the course repository commit when `$LAB` is available. If the course baseline has changed, source-hash checks stop execution; use the course version matching the reference image rather than forcing the patch.

## 2. Experiments, implementation and parameter basis

| Stage | Cases | Duration and purpose |
|---|---|---|
| Original controls | Original `TcpVegas` and `TcpCubic`, each at 1,584 and 2,160 satellites | Four 200 s runs: reproduce Vegas underutilization and check available path capacity |
| Adaptive | `TcpVegas`, 1,584 and 2,160 satellites | Two 200 s runs: persistent-shift BaseRTT relearning |
| Adaptive safety | Five `TcpVegas` flows, 1,584 satellites | 60 s: flow 0 starts at 0 s; four competitors start at 35 s |
| Recurring refresh | 500, 1,584 and 2,160 satellites × histories 0, 1, 5, 10 s | Twelve 200 s runs: original control and throughput/queue/delay trade-offs |

The default sweep therefore performs **19 simulations**, with 3,660 simulated seconds in total. The refresh study includes its own instrumented original controls, separate from the unmodified controls above.

| Parameter | Value and basis |
|---|---|
| Layouts | 1,584 = 72 × 22 course default; 2,160 = 72 × 30 controlled density perturbation; 500 = 25 × 20 sparse refresh extension. The latter two are experimental constructions, not deployed shells. |
| Orbits/links | Course 550 km circular shell, 53° inclination, 25° minimum elevation; +Grid ISLs, two same-plane and two adjacent-plane neighbors. |
| Routing | Shortest distance over ISLs only; 100 ms precomputed forwarding updates. No terrestrial path segments. |
| Ground stations | Seoul `(37.56826,126.97783)` → London `(51.50853,-0.12574)`, retained course endpoints. IDs are `N` and `N+1` for `N` satellites. |
| Link capacity | Every ISL and GSL = 100 Mbit/s; fixed to compare controller behavior, with CUBIC as capacity control. |
| Queues | 1,000-packet DropTail device queues on both link types; deliberate large-buffer condition. At 100 Mbps and 90 ms RTT, BDP ≈ 1.125 MB ≈ 815 MSS-sized segments. This is not a deployed-equipment claim. |
| Traffic | Each flow requests 100 GB and stays backlogged through the run. `NO_ONGOING` in the flow summary is expected. |
| TCP | MSS 1,380 bytes, initial cwnd 10 segments, 32 MiB send/receive buffers, SACK/timestamps/window scaling; Vegas alpha=2, beta=4, gamma=1; pacing disabled. |
| Duration/seed | 200 s captures route events and later behavior; 60 s safety run probes added contention. Seed 123456789; deterministic configured inputs, not statistical repetitions. |

The model changes propagation continuously and switches forwarding instantly. It does not add weather, random bit errors, capacity variation or a link-layer handover outage. Queue overflow or missing satellite visibility can cause loss. Changing constellation size also changes geometry and route history, so satellite count alone is not isolated.

**Adaptive rule:** at an eligible Vegas calculation, `minRTT > BaseRTT + 3 ms` must hold for five consecutive qualifying calculations while more than 10 s have passed since the last reset. Then BaseRTT becomes the current cycle minimum. These are strict comparisons. The initial reset timestamp is far in the past; the first reset need not wait 10 s after startup. The engineering thresholds are prototype choices, not optimized constants. No route/orbit notification or receiver modification is used.

**Recurring refresh:** history 0 retains original lifetime-minimum Vegas. Histories 1, 5 and 10 s expire old RTT observations and select the minimum still in the window, updated on valid RTT samples. This is a sliding minimum, not an unconditional timer reset. The decision baseline is clamped against the current cycle minimum to avoid unsigned underflow. A shorter history can adapt sooner but can learn a standing queue. Refresh adds passive flow/queue observers and retains Vegas alpha/beta/gamma.

### Exact constellation-generation commands

The unmodified/adaptive default layout uses `$STATE_EXAMPLE`. The runner creates its 2,160 state using `code/generate_state.sh`, equivalent to:

```bash
python3 "$LAB/scripts/gen_state.py" "$REPRO_WORK/state_2160" \
  --threads 4 --duration 200 --orbits 72 --sats-per-orbit 30 \
  --gs 'Seoul,37.56826,126.97783' --gs 'London,51.50853,-0.12574'
```

The refresh runner uses the bundled course generator and pinned `satgenpy`. Its exact per-layout commands have the following form, using `(25,20)`, `(72,22)`, `(72,30)` respectively:

```bash
export UV_PROJECT_ENVIRONMENT="$REPRO_WORK/repro_venv"
export SATGENPY="$PWD/code/recurring_refresh/code/third_party/satgenpy"
uv run --frozen --project code python code/recurring_refresh/code/course/gen_state.py \
  "$REPRO_WORK/refresh_generated/states/sat500" \
  --orbits 25 --sats-per-orbit 20 --duration 200 --step-ms 100 --threads 4
```

Omitted `--gs` options use the same Seoul/London defaults. For the full workflow, let `run_all.sh` generate all three layouts and their completion receipts; manually generating into those automatic destinations without receipts makes the runner treat them as incomplete. The generated state is validated against metadata and archived route-timeline hashes before simulations. Exact invoked commands are printed and state-generation logs are retained locally.

## 3. Patches and build

`code/adaptive-vegas.patch` modifies sender Vegas and adds controller decision/reset logging. `code/recurring_refresh/code/patches/ns3-refresh.patch` contains the recurring history plus passive observers. They target separate clean course trees. The combined script applies/builds both automatically, **after original controls have run on the unmodified adaptive tree**.

For separate, staged work only (do not perform this before a full `run_all.sh`):

```bash
# Adaptive only; NS3_DIR must start clean.
git -C "$NS3_DIR" apply --ignore-space-change --ignore-whitespace \
  --check "$PWD/code/adaptive-vegas.patch"
git -C "$NS3_DIR" apply --ignore-space-change --ignore-whitespace \
  "$PWD/code/adaptive-vegas.patch"
(cd "$NS3_DIR" && ./ns3 build main_satnet)

# Refresh only; REFRESH_NS3_DIR must be a separate course installation.
uv run --frozen --project code python code/recurring_refresh/code/experiments.py install \
  --ns3 "$REFRESH_NS3_DIR" --output "$REPRO_WORK/refresh_generated"
(cd "$REFRESH_NS3_DIR" && ./ns3 build main_satnet)
```

For additional simulator edits, the guide's `make_patch.sh` saves changes relative to the course baseline. Submit patches rather than an ns-3 source tree or compiled artifacts.

## 4. Runtime, outputs and resume

The earlier **15–25 minute estimate covered the adaptive workflow only**. The archived twelve refresh simulations took approximately **1.52 hours excluding state generation and build**. Allow **several hours for the combined cold run**, particularly on a VM; CPU, disk, available memory and compilation materially affect timing. These are estimates/historical timings, not a fresh measured runtime for this combined launcher.

With `REPRO_WORK=/work/output`, the results persist in the host's `output/` folder:

| Path under `$REPRO_WORK` | Contents |
|---|---|
| `runs_repro/` | Four original/CUBIC controls, two adaptive runs, five-flow safety run; configs, schedules and ns-3 logs |
| `analysis_generated/summary.csv` | Original/adaptive whole-run rates and adaptive reset counts; safety aggregate is a sum of individual flow averages |
| `analysis_generated/*_console.txt` | Adaptive decision and reset traces |
| `figures_generated/` | `standard_vs_adaptive.png`, `cubic_controls.png`, `comparison_goodput.png/.pdf`, `refresh_queue_delay_2160.png/.pdf` |
| `refresh_generated/runs/` | Twelve refresh/original configurations, raw traces, completion receipts and sampled time series |
| `refresh_generated/paths/` | Generated geometric path RTT timelines |
| `refresh_generated/analysis/` | Measured summaries, goodput windows, queue/delay figures and report table |
| `refresh_generated/build.log` and `states/satN/generation.log` | Build and state-generation diagnostics |
| `ns3_refresh/` | Separate refresh simulator/build; do not submit |

**Full-run restart:** original/adaptive stages require a fresh clean `$NS3_DIR` and fresh output locations; they do not implement resume. Existing outputs are rejected before they can be overwritten. Use a new Docker volume and new `REPRO_WORK` for a full rerun.

**Refresh-stage resume:** after reaching the refresh stage, reuse the same source package, simulator, states and output folder:

```bash
export REFRESH_NS3_DIR="$REPRO_WORK/ns3_refresh"
bash code/run_all.sh --refresh-only --threads 4 --retry-incomplete
```

Complete refresh cases are validated/skipped. Matching incomplete simulations move into `refresh_generated/incomplete/` before retry. Changed inputs/source hashes require a new output directory. Interrupted state generation requires moving its incomplete `states/satN/` folder aside first. Never run simultaneous sweeps against the same simulator/output.

A selected refresh case (after the initial setup):

```bash
bash code/run_all.sh --refresh-only --satellites 2160 --windows 5 --threads 4
```

Refresh options are forwarded only to refresh; they do not change the original/adaptive workloads. Omitting selections executes all three layouts and all four histories. Analysis includes all completed cases already in that refresh output. Check available options with:

```bash
bash code/run_all.sh --help
python3 code/recurring_refresh/code/experiments.py --help
python3 code/recurring_refresh/code/experiments.py plan
```

## 5. Figure/table mapping and measurement intervals

After simulations, regenerate analysis without rerunning ns-3:

```bash
export UV_PROJECT_ENVIRONMENT="$REPRO_WORK/repro_venv"
uv sync --frozen --project code
uv run --frozen --project code python code/analysis/extract_summary.py \
  "$REPRO_WORK/runs_repro" "$REPRO_WORK/analysis_generated" \
  "$REPRO_WORK/analysis_generated/summary.csv"
uv run --frozen --project code python code/plots/make_figures.py \
  "$REPRO_WORK/analysis_generated/summary.csv" "$REPRO_WORK/figures_generated"
uv run --frozen --project code python code/recurring_refresh/code/analyze.py \
  "$REPRO_WORK/refresh_generated"
```

The new report plotting command is **D** and is also called by `run_all.sh` after refresh analysis:

```bash
uv run --frozen --project code python code/plots/make_report_figures.py \
  --refresh-summary "$REPRO_WORK/refresh_generated/analysis/summary.csv" \
  --adaptive-summary "$REPRO_WORK/analysis_generated/summary.csv" \
  --outdir "$REPRO_WORK/figures_generated" \
  --analysisdir "$REPRO_WORK/analysis_generated"
```

It creates `run_summary.csv`, `table_iii.md`, `comparison_goodput.png/.pdf` and `refresh_queue_delay_2160.png/.pdf`. The table and comparison use refresh **whole_goodput_mbps (0–200 s)** plus available adaptive/CUBIC whole-run rates. The queue/delay panels use **20–200 s**. Missing values stay blank in CSV and display as a dash in the Markdown table. Do not copy the default refresh `goodput_mbps` column into Table III.

The commands above are abbreviated as **A** (extract_summary), **B** (make_figures), **C** (refresh analyze) in the mapping. All also run automatically in `run_all.sh`.

| Report content | Command and generated source |
|---|---|
| Setup table (Table I) | Parameters in section 2 and generated `config_ns3.properties`/`schedule.csv`; descriptive, not a measured plot |
| Experiment matrix (Table II, T1–T4/T8–T10/Refresh) | Full `run_all.sh`; `experiments.py plan` lists the refresh matrix |
| Table III / Table 3 and Figure 3, all methods | D → `analysis_generated/run_summary.csv`, `table_iii.md`, `figures_generated/comparison_goodput.png/.pdf` |
| Figure 4, dense mean queue and p95 SRTT | D → `figures_generated/refresh_queue_delay_2160.png/.pdf` |
| Standard/adaptive quantitative comparison | A → `analysis_generated/summary.csv`; B → `figures_generated/standard_vs_adaptive.png` |
| CUBIC capacity controls | A → summary CUBIC rows; B → `figures_generated/cubic_controls.png` |
| Refresh whole-run comparison, including original 500 case | C → `refresh_generated/analysis/goodput_windows.csv`, 0–200 s column |
| Refresh goodput/queue/p95 SRTT trade-off | C → `refresh_tradeoffs.png/.pdf`, `summary.csv`, `report_table.md` |
| Refresh throughput/queue time series | C → `throughput_and_queues.png/.pdf` |
| Route RTT/BaseRTT/cwnd/goodput mechanisms | C → `route_baseline_500.png/.pdf`, `route_baseline_1584.png/.pdf`, `route_baseline_2160.png/.pdf` |
| Route events/connectivity/500 event investigations | C → `route_events.csv`, `connectivity.csv`, `event_windows_500.csv`, `decision_examples.csv` |
| Safety reset count and aggregate | A → `Congestion safety aggregate` row; per-flow rates remain in `runs_repro/vegas_1584_congestion_safety/logs_ns3/tcp_flows.txt` |

The previous Figure 3/Table 3 filenames now have implemented generators (command D). The earlier listed Figure 1 `vegas_2160_standard_goodput_cwnd.png`, Figure 2 `vegas_2160_five_flow_adaptive_base_min_rtt.png`, and Table 4 `cs304/analysis_generated/flow_metrics.csv` still lack exact exporters in this package. Fresh refresh mechanism figures are available through command C; use their actual filenames when updating the report.

**Validation of this integration:** Bash syntax/help, the 12-case plan, existing six refresh regression tests and mocked combined orchestration checks passed for the initial integration. The new report script was additionally checked against the supplied reference values and generated archived refresh summaries. Mock checks cover stage order, seven original/adaptive simulations, separate refresh configuration, cache exclusion, refresh resume dispatch and same-tree rejection. No fresh end-to-end ns-3 build/sweep was performed in the editing environment; these checks do not certify numerical reproduction.

**Remaining report reproduction gaps:** the current report additionally discusses T5's earlier instrumented dense run and T6–T7 oracle resets at 39.9355/40.5002 s. Those exact oracle experiment generators and their figure commands are not present in this package and are not regenerated by this runner. The newly added script renders Table III and Figures 3–4; the historical dense/safety figures and per-flow safety table still need exact exporters. The refresh route-baseline plots provide newly generated mechanism evidence but are not an exact replacement for those historical figures. Before final submission, add the missing scenario/analysis commands and map every final numbered figure/table, or revise the report to use only results reproducible here. This README does not certify those gaps as solved.

Use matching intervals: adaptive/original `tcp_flows.txt` rates are whole-run 0–200 s averages; refresh `summary.csv` defaults to **20–200 s** and additionally reports whole-run and 60–200 s goodput. Use `goodput_windows.csv` **0–200 s** when comparing with adaptive. Five-flow safety averages use 0–60 s for flow 0 and 35–60 s for each later flow; their sum is not a shared-interval aggregate throughput or a fairness measurement.

Refresh goodput counts newly acknowledged application bytes in decimal Mbps. Queue occupancy is a time-weighted sum over monitored device queues; SRTT includes propagation. Retransmissions are not equivalent to buffer losses. Single-flow Jain fairness of 1 establishes no multi-flow fairness result. Do not replace failed fresh measurements with archived target numbers.

## 6. Supplied Table III and Figure 4 reference results

These are the values in the screenshots supplied on 13 October 2026. They are **reported reference values, not newly simulated measurements**. `*` marks a group-reported development average. `†` marks a 500-satellite value without a corresponding run in the current reproduction package.

**Table III. Average goodput over 0–200 s (Mbps).**

| Constellation | Original Vegas | 1 s history | 5 s history | 10 s history | Adaptive Vegas | CUBIC control |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 8.93 | 82.15 | 79.12 | 75.01 | 13.0*† | 95.9† |
| 1,584 | 41.51 | 72.17 | 68.37 | 64.60 | 64.7* | 95.86 |
| 2,160 | 12.12 | 75.43 | 73.03 | 67.13 | 71.0* | 95.91 |

The table's adaptive 500 value (13.0 Mbps) contradicts the accompanying text saying adaptive was not tested at 500 satellites. The existing runner also does not run a 500-satellite adaptive or CUBIC case. Verify those two supplied entries against raw evidence, or mark them unavailable in the final report. Reference rendering preserves them with visible flags; fresh rendering never inserts them. The 1,584/2,160 reported adaptive improvement is approximately 55.9%/485.8% using the unrounded baseline totals; the rounded table alone gives slightly different percentages.

![Table III comparison: supplied whole-run reference values](report_reference/figures/comparison_goodput.png)

**Figure 4. Dense-case trade-off, 2,160 satellites, 20–200 s.**

| History | Goodput (Mbps) | Mean total queue (packets) | p95 SRTT (ms) |
|---|---:|---:|---:|
| Original | 12.41 | 0.081 | 87.15 |
| 1 s | 82.17 | 76.29 | 111.19 |
| 5 s | 79.82 | 15.65 | 92.00 |
| 10 s | 73.54 | 4.82 | 88.55 |

![Figure 4: dense-case queue and RTT trade-off](report_reference/figures/refresh_queue_delay_2160.png)

Every tested recent-history setting improves whole-run goodput over original Vegas in these three layouts. Improvement is not monotonic in satellite count because route history/geometry differ. In the dense case, 5 s reduces mean total queue by approximately 79.5% versus 1 s and p95 SRTT by 19.19 ms, while reducing 20–200 s goodput by 2.35 Mbps. These observations demonstrate the rate/queue/delay trade-off; they do not establish multi-flow fairness or that one controller is universally best.

### Redraw the supplied table and graphs without a simulator

Reference CSVs live in `code/report_data/` with explicit provenance notes. This command needs only the plotting dependencies and does not access or modify ns-3:

```bash
uv sync --frozen --project code
uv run --frozen --project code python code/plots/make_report_figures.py \
  --reference --outdir report_reference/figures --analysisdir report_reference/analysis
```

Outputs:

- `report_reference/analysis/run_summary.csv` and `table_iii.md` reproduce Table III, with reference-source metadata and the cautions above.
- `report_reference/figures/comparison_goodput.png/.pdf` compare all six methods across the three layouts.
- `report_reference/figures/refresh_queue_delay_2160.png/.pdf` reproduce Figure 4's two panels, with queue and RTT units labelled.

Reference mode is explicitly labelled on every figure. It redraws supplied numbers and **does not prove simulation reproducibility**. Keep reference outputs separate from `$REPRO_WORK` fresh results. The full runner uses generated summaries only.


Reference: S. Kassing, D. Bhattacherjee, A. B. Aguas, J. E. Saethre, and A. Singla, “Exploring the ‘Internet from space’ with Hypatia,” Proceedings of the ACM Internet Measurement Conference (IMC), 2020. See the course Lab 1 Handout (submission/reproducibility rules) and Lab Environment Guide (sections 1–2, 4 and 6) for platform and model details.
