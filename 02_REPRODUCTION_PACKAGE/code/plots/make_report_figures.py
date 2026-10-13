#!/usr/bin/env python3
"""Render Table III and Figure 4 from supplied references OR fresh run summaries."""
import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FIELDS = ['original_vegas_mbps', 'history_1s_mbps', 'history_5s_mbps',
          'history_10s_mbps', 'adaptive_vegas_mbps', 'cubic_control_mbps']
LABELS = ['Original Vegas', '1 s history', '5 s history', '10 s history',
          'Adaptive Vegas', 'CUBIC control']
COLORS = ['#426884', '#b6652d', '#3b7b66', '#797979', '#8766a8', '#c8a34a']
COUNTS = [500, 1584, 2160]


def read_csv(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))


def number(value):
    return None if value in (None, '') else float(value)


def load_data(args):
    if args.reference:
        ref = Path(__file__).resolve().parents[1] / 'report_data'
        rows = read_csv(ref / 'table_iii_reference.csv')
        data = {int(r['satellites']): {k: number(r[k]) for k in FIELDS} for r in rows}
        dense = {int(float(r['window_s'])): r for r in read_csv(ref / 'figure_4_dense_reference.csv')}
        return data, dense
    data = {n: {k: None for k in FIELDS} for n in COUNTS}
    dense = {}
    for r in read_csv(args.refresh_summary):
        n, w = int(r['satellites']), int(float(r['window_s']))
        if n not in data or w not in (0, 1, 5, 10):
            continue
        if r['tcp'] != 'TcpVegas' or int(r['flows']) != 1:
            continue
        if int(r['duration_s']) != 200:
            raise ValueError('Table III requires 200 s runs; smoke results cannot be plotted as full results.')
        key = 'original_vegas_mbps' if w == 0 else f'history_{w}s_mbps'
        if data[n][key] is not None:
            raise ValueError(f'Duplicate refresh case: satellites={n}, window={w}.')
        data[n][key] = number(r['whole_goodput_mbps'])  # 0–200 s, NOT goodput_mbps.
        if n == 2160:
            if float(r['measurement_start_s']) != 20 or float(r['measurement_end_s']) != 200:
                raise ValueError('Figure 4 requires a 20–200 s measurement interval.')
            dense[w] = r
    if args.adaptive_summary:
        for r in read_csv(args.adaptive_summary):
            # Never use the congestion-safety aggregate as a single-flow rate.
            for n in COUNTS:
                if r['case'] == f'Vegas adaptive {n}':
                    data[n]['adaptive_vegas_mbps'] = number(r['avg_rate_Mbit_s'])
                elif r['case'] == f'CUBIC control {n}':
                    data[n]['cubic_control_mbps'] = number(r['avg_rate_Mbit_s'])
    return data, dense


def write_table(data, directory, reference):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'run_summary.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['satellites'] + FIELDS + ['interval_s', 'source'])
        writer.writeheader()
        for n in COUNTS:
            writer.writerow(dict(satellites=n, **data[n], interval_s='0–200',
                                 source='supplied_report_reference' if reference else 'generated_run_summaries'))
    lines = ['Table III. Average goodput over 0–200 s, in Mbps.', '',
             '| Constellation | ' + ' | '.join(LABELS) + ' |',
             '|---:|' + '---:|' * len(FIELDS)]
    for n in COUNTS:
        cells = []
        for k in FIELDS:
            v = data[n][k]
            cell = '—' if v is None else f'{v:.2f}'
            if reference and k == 'adaptive_vegas_mbps':
                cell += '*'
            if reference and n == 500 and k in ('adaptive_vegas_mbps', 'cubic_control_mbps'):
                cell += '†'
            cells.append(cell)
        lines.append('| ' + f'{n:,}' + ' | ' + ' | '.join(cells) + ' |')
    lines += ['', '— = no measurement in the input summaries.']
    if reference:
        lines += ['* = group-reported development average.',
                  '† = supplied 500-satellite value lacks a matching case in the current runner; '
                  'adaptive 13.0 also conflicts with the accompanying untested-at-500 statement.',
                  'Reference transcription only; not a fresh simulation result.']
    (directory / 'table_iii.md').write_text('\n'.join(lines) + '\n')


def save(fig, out, name):
    fig.savefig(out / (name + '.png'), dpi=250)
    fig.savefig(out / (name + '.pdf'))
    plt.close(fig)


def comparison(data, out, reference):
    fig, ax = plt.subplots(figsize=(10, 5.8))
    width = .125
    for j, (key, label, color) in enumerate(zip(FIELDS, LABELS, COLORS)):
        for i, n in enumerate(COUNTS):
            value = data[n][key]
            if value is None:
                continue
            x = i + (j - 2.5) * width
            flagged = reference and n == 500 and j in (4, 5)
            ax.bar(x, value, width, color=color, label=label if i == 1 else None,
                   hatch='///' if flagged else None, edgecolor='white', linewidth=.6)
            suffix = '*' if reference and j == 4 else ''
            if flagged:
                suffix += '†'
            ax.text(x, value + 1.5, f'{value:.2f}{suffix}', ha='center', va='bottom',
                    fontsize=8, rotation=65)
    # Explicit handles retain the legend even when a method is wholly missing.
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=c, label=l) for c, l in zip(COLORS, LABELS)],
              loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(.5, 1.23))
    ax.set_xticks(range(3), [f'{n:,}' for n in COUNTS])
    ax.set_xlabel('Satellite count')
    ax.set_ylabel('Average goodput, 0–200 s (Mbps)')
    ax.set_ylim(0, 118)
    ax.set_axisbelow(True)
    ax.grid(axis='y', alpha=.18)
    ax.spines[['top', 'right']].set_visible(False)
    note = ('Supplied report reference. * Development average. † Unverified 500-satellite case.'
            if reference else 'Generated summaries only. Missing measurements are left blank.')
    fig.text(.5, .025, note, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .055, 1, .93))
    save(fig, out, 'comparison_goodput')


def tradeoff(dense, out, reference):
    if any(w not in dense for w in (0, 1, 5, 10)):
        warnings.warn('All four 2160 histories are required for Figure 4; skipping that figure.')
        return
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 4.1))
    for ax, key, ylabel in zip(axes,
            ['mean_total_queued_packets', 'p95_sampled_srtt_ms'],
            ['Mean total queue (packets)', 'p95 SRTT (ms)']):
        vals = [float(dense[w][key]) for w in (0, 1, 5, 10)]
        ax.bar(range(4), vals, color=COLORS[:4], width=.7)
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals)*.025, str(Decimal(str(v)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)), ha='center', fontsize=10)
        ax.set_xticks(range(4), ['Orig.', '1 s', '5 s', '10 s'], rotation=32)
        ax.set_xlabel('History window')
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, max(vals)*1.20)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.20)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('2,160 satellites · 20–200 s', fontsize=12)
    fig.text(.5, .015, 'Supplied report reference' if reference else 'Generated run measurements',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, .95))
    save(fig, out, 'refresh_queue_delay_2160')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--reference', action='store_true', help='Redraw supplied screenshot values, explicitly labelled.')
    group.add_argument('--refresh-summary', type=Path, help='Fresh refresh analysis/summary.csv.')
    p.add_argument('--adaptive-summary', type=Path, help='Original/adaptive analysis_generated/summary.csv.')
    p.add_argument('--outdir', type=Path, required=True)
    p.add_argument('--analysisdir', type=Path, required=True)
    args = p.parse_args()
    data, dense = load_data(args)
    args.outdir.mkdir(parents=True, exist_ok=True)
    write_table(data, args.analysisdir, args.reference)
    comparison(data, args.outdir, args.reference)
    tradeoff(dense, args.outdir, args.reference)
    print(f'Wrote Table III to {args.analysisdir} and figures to {args.outdir}.')


if __name__ == '__main__':
    main()
