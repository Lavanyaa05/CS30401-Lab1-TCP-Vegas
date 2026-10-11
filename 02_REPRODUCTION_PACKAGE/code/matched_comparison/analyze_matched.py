"""Apply the original refresh metric definitions to explicit matched variants."""
import argparse
from array import array
import csv
import importlib.util
import math
from pathlib import Path
import sys

from common import (HERE, VARIANTS, read_json, sha, verify_package, verify_receipt,
                    write_csv, write_json)

module = importlib.util.spec_from_file_location('refresh_analysis', HERE / 'vendor/analyze_suite.py')
core = importlib.util.module_from_spec(module)
module.loader.exec_module(core)

def compact_series(path, divisor=1.0):
    """Same ordered samples/units as upstream; avoid millions of Python tuples."""
    times, values = array('d'), array('d')
    with path.open(newline='') as f:
        for row in csv.reader(f):
            if not row:
                continue
            t, value = int(row[1]) / 1e9, int(row[2]) / divisor
            if times and t < times[-1]:
                raise ValueError(f'Nonmonotonic course trace: {path}')
            times.append(t)
            values.append(value)
    return times, values

core.series = compact_series
LABELS = {'original': 'Original Vegas', 'refresh1': '1 s history', 'refresh5': '5 s history',
          'refresh10': '10 s history', 'adaptive': 'Adaptive Vegas'}
COLORS = {'original': '#444444', 'refresh1': '#21918c', 'refresh5': '#386cb0',
          'refresh10': '#984ea3', 'adaptive': '#d55e00'}
RESET_FIELDS = ['time_ns', 'context', 'object', 'old_base_ns', 'new_base_ns']

def extract_resets(run, spec):
    events = []
    previous = {}
    with (run / 'out.txt').open(errors='replace') as f:
        for line in f:
            if not line.startswith('VEGAS_ADAPTIVE_RESET,'):
                continue
            raw = line.strip().split(',')[1:]
            if len(raw) != len(RESET_FIELDS):
                raise ValueError('Malformed adaptive reset trace')
            event = dict(zip(RESET_FIELDS, raw))
            for field in ['time_ns', 'context', 'old_base_ns', 'new_base_ns']:
                event[field] = int(event[field])
            t = event['time_ns']
            key = event['object']
            if not spec['adaptive'] or not 0 <= t <= spec['duration_s'] * 1000000000:
                raise ValueError('Reset in disabled arm or outside simulation')
            if event['new_base_ns'] - event['old_base_ns'] <= 3000000:
                raise ValueError('Reset fails strict 3 ms threshold')
            if t - previous.get(key, -1000000000000) <= 10000000000:
                raise ValueError('Reset fails strict 10 s cooldown')
            previous[key] = t
            events.append(event)
    write_csv(run / 'adaptive_resets.csv', events, RESET_FIELDS)
    return events

def analyze(root, start=20, late=60, make_plots=False):
    root = Path(root).expanduser().resolve(strict=True)
    verify_package()
    cases = sorted(root.glob('*/EVALUATION_COMPLETE.json'))
    if not cases:
        raise ValueError('No completed evaluation runs found')
    results, flows, all_events, details = [], [], [], []
    receipts = {}
    for marker in cases:
        run = marker.parent
        receipt = verify_receipt(run)
        receipts[run.name] = sha(marker)
        spec = receipt['spec']
        if not 0 <= start < spec['duration_s'] or late < start:
            raise ValueError('Use integer 0 <= start < duration and late-start >= start; smoke uses 0 and 2')
        row, series, per_flow = core.analyze_case(run, start, late)
        resets = extract_resets(run, spec)
        series['resets'] = resets
        row.update(variant=spec['variant'], satellites=spec['satellites'], adaptive=spec['adaptive'],
                   adaptive_reset_count=sum(start * 1e9 <= r['time_ns'] < spec['duration_s'] * 1e9 for r in resets),
                   whole_run_reset_count=len(resets), fairness_informative=spec['flows'] > 1)
        for record in per_flow:
            record.update(scenario=spec['scenario'], variant=spec['variant'],
                          measurement_start_s=start, measurement_end_s=spec['duration_s'])
        for event in resets:
            all_events.append(dict(run=run.name, scenario=spec['scenario'], variant=spec['variant'], **event))
        # Keep per-flow internal series distinct; an object pointer is not a course flow ID.
        results.append(row)
        flows.extend(per_flow)
        details.append((row, series, spec['state']['route_events']))
        print(f"{run.name}: {row['goodput_mbps']:.6f} Mbps; {row['mean_total_queued_packets']:.4f} queued; resets={len(resets)}")
    groups = {}
    for row in results:
        key = (row['scenario'], row['flows'], row['duration_s'], row['queue_packets'])
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        originals = [r for r in group if r['variant'] == 'original']
        if len(originals) > 1:
            raise ValueError('Multiple original controls in a matched group')
        baseline = originals[0] if originals else None
        for row in group:
            row['improvement_vs_matched_original_percent'] = (
                100 * (row['goodput_mbps'] / baseline['goodput_mbps'] - 1)
                if baseline and baseline['goodput_mbps'] > 0 else None)
    out = root / 'analysis'
    out.mkdir(exist_ok=True)
    write_csv(out / 'summary.csv', results)
    write_csv(out / 'per_flow.csv', flows)
    write_csv(out / 'adaptive_resets.csv', all_events, ['run', 'scenario', 'variant'] + RESET_FIELDS)
    routes = []
    state_names = set()
    for row, _, events in details:
        if row['scenario'] not in state_names:
            state_names.add(row['scenario'])
            routes.extend(dict(scenario=row['scenario'], **event) for event in events)
    write_csv(out / 'route_events.csv', routes, ['scenario', 'time_s', 'before_prop_ms', 'after_prop_ms', 'delta_prop_ms'])
    if make_plots:
        plots(details, flows, out)
    generated = {p.relative_to(root).as_posix(): sha(p) for p in sorted(out.iterdir())
                 if p.is_file() and p.suffix in ['.csv', '.png', '.pdf']}
    for marker in cases:
        for name in ['adaptive_resets.csv', 'vegas_decision.csv', 'timeseries_100ms.csv', 'timeseries_1s.csv']:
            p = marker.parent / name
            generated[p.relative_to(root).as_posix()] = sha(p)
    write_json(out / 'analysis_manifest.json', dict(schema_version=1, measurement_start_s=start,
                late_start_s=late, analyzer_sha256=sha(Path(__file__)),
                analysis_core_sha256=sha(HERE / 'vendor/analyze_suite.py'), receipts_sha256=receipts,
                generated_sha256=generated))
    print('Saved:', out / 'summary.csv')
    return results

def plots(details, flows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = {}
    for row, d, events in details:
        groups.setdefault((row['scenario'], row['flows']), []).append((row, d, events))
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    for (scenario, flow_count), cases in groups.items():
        fig, axes = plt.subplots(4, 2, figsize=(13, 12), sharex=True, layout='constrained')
        for row, d, _ in sorted(cases, key=lambda x: list(VARIANTS).index(x[0]['variant'])):
            label, color = LABELS[row['variant']], COLORS[row['variant']]
            xsec = [i + .5 for i in d['seconds']]
            for ax, x, y in [(axes[0, 0], xsec, d['goodput']), (axes[0, 1], d['time'], d['cwnd']),
                             (axes[1, 0], d['time'], d['srtt']), (axes[1, 1], xsec, d['base']),
                             (axes[2, 0], xsec, d['diff']), (axes[2, 1], xsec, d['queued']),
                             (axes[3, 0], xsec, d['drops']), (axes[3, 1], xsec, d['retx'])]:
                ax.plot(x, y, label=label, color=color, linewidth=1.1)
        labels = ['ACKed goodput (Mbps)', 'Total cwnd (segments)', 'Mean flow SRTT (ms)',
                  'Mean effective BaseRTT per decision (ms)', 'Mean diff per decision (packets)',
                  'Time-mean total queued packets', 'Buffer drops per second', 'Data retransmissions per second']
        for ax, label in zip(axes.flat, labels):
            ax.set_ylabel(label)
            ax.grid(alpha=.2)
            ax.set_xlim(0, cases[0][0]['duration_s'])
            ax.axvspan(0, cases[0][0]['measurement_start_s'], color='grey', alpha=.08)
            for event in cases[0][2]:
                ax.axvline(float(event['time_s']), color='#b87333', ls='--', alpha=.4)
            ax.legend(fontsize=8)
        for ax in [axes[0, 0], axes[0, 1], axes[2, 1], axes[3, 0], axes[3, 1]]:
            ax.set_ylim(bottom=0)
        for row, d, _ in cases:
            if d['resets']:
                axes[1, 1].scatter([r['time_ns'] / 1e9 for r in d['resets']],
                                   [r['new_base_ns'] / 1e6 for r in d['resets']],
                                   marker='x', color=COLORS[row['variant']], label='Adaptive reset', zorder=5)
        axes[1, 1].legend(fontsize=8)
        axes[2, 0].axhline(4, color='black', ls=':', alpha=.6)
        for ax in axes[-1]:
            ax.set_xlabel('Simulation time (s)')
        fig.suptitle(f'{scenario}: {flow_count} flow(s); dashed lines are verified route changes')
        stem = f'{scenario}_q1000_f{flow_count}'
        for extension in ['png', 'pdf']:
            fig.savefig(out / f'{stem}.{extension}', dpi=160)
        plt.close(fig)
        if flow_count == 5:
            cases = sorted(cases, key=lambda x: list(VARIANTS).index(x[0]['variant']))
            fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
            for i, (row, _, _) in enumerate(cases):
                rates = sorted([r for r in flows if r['run'] == row['run']], key=lambda r: r['flow'])
                for r in rates:
                    axes[0].bar(i + (r['flow'] - 2) * .14, r['goodput_mbps'], width=.13,
                                color=plt.get_cmap('tab10')(r['flow']),
                                label=f"Flow {r['flow']}" if i == 0 else None)
                jain = row['jain_fairness']
                if jain is not None:
                    axes[1].bar(i, jain, color=COLORS[row['variant']])
                else:
                    axes[1].text(i, .1, 'undefined', rotation=90, ha='center')
            labels = [LABELS[r['variant']] for r, _, _ in cases]
            for ax in axes:
                ax.set_xticks(range(len(cases)), labels, rotation=20)
                ax.grid(axis='y', alpha=.2)
            axes[0].set_ylabel(f"Per-flow goodput, {cases[0][0]['measurement_start_s']}–{cases[0][0]['duration_s']} s (Mbps)")
            axes[0].legend(loc='upper center', bbox_to_anchor=(.5, 1.15), ncol=5, fontsize=8)
            axes[1].set_ylabel('Jain fairness, common measurement window')
            axes[1].set_ylim(0, 1.05)
            fig.suptitle(f'{scenario}: five competing flows, common measurement window')
            for extension in ['png', 'pdf']:
                fig.savefig(out / f'{scenario}_fairness.{extension}', dpi=160)
            plt.close(fig)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--start', type=int, default=20)
    p.add_argument('--late-start', type=int, default=60)
    p.add_argument('--plots', action='store_true')
    a = p.parse_args()
    analyze(a.root, a.start, a.late_start, a.plots)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, ImportError) as error:
        sys.exit(str(error))
