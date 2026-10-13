# Report references supplied on 13 October 2026

These CSVs transcribe the user's Table III and Figure 4 screenshots. They are
reported reference values, not output from a new simulation. Table III averages
0–200 s; Figure 4 metrics average/sample 20–200 s in the 2,160-satellite case.

Adaptive values are group-reported development averages. In particular, the
500-satellite adaptive value 13.0 Mbps conflicts with the accompanying statement
that adaptive Vegas was not tested at 500 satellites. The 500-satellite CUBIC
95.9 Mbps value is also not backed by a case in the current reproduction runner.
Both are retained for transcription, flagged in reference outputs, and are never
inserted into fresh simulation summaries. Verify them against raw run evidence
before including them as evaluated results in the final report.

`make_report_figures.py --reference` intentionally redraws these supplied values.
Fresh mode reads generated summaries only, leaving absent measurements blank.
