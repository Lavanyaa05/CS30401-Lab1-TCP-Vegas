# Which files should I open first?

If you only want to understand or verify one thing, use this map.

- **Understand the final algorithm:** `03_ADAPTIVE_IMPLEMENTATION/adaptive-vegas.patch`
- **See the actual modified ns-3 source:** `03_ADAPTIVE_IMPLEMENTATION/tcp-vegas.cc` and `.h`
- **Rerun the main experiments:** `02_REPRODUCTION_PACKAGE/code/run_all.sh`
- **See exact baseline configs/results:** `01_TESTED_RAW_RESULTS/runs/`
- **See why Vegas collapsed:** `01_TESTED_RAW_RESULTS/analysis/vegas_2160_internal.csv` and `vegas_2160_instrumented_console.txt`
- **See immediate oracle failure:** `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_oracle_console.txt`
- **See delayed oracle success:** `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_oracle_v2_console.txt`
- **See automatic dense reset:** `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_2160_adaptive_v1_console.txt`
- **See automatic default-topology resets:** `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_1584_adaptive_v1_console.txt`
- **See congestion-safety result:** `03_ADAPTIVE_IMPLEMENTATION/analysis/vegas_1584_congestion_safety_console.txt`
- **See reference graphs:** `04_REFERENCE_GRAPHS/`
- **See current report:** `05_CURRENT_REPORT/CS30401_TCP_Vegas_Graphs_Fixed.docx`
