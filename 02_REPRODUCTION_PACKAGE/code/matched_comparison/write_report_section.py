"""Produce measured Section V-C2 and a replacement V-C paragraph after validation."""
import argparse
from pathlib import Path
import sys

from analyze_matched import LABELS
from common import SCENARIOS, VARIANTS, rows
from validate_matched import validate

def number(value, digits=2):
    return f'{float(value):.{digits}f}' if value not in ['', None] else 'undefined'

def render_table(records, flows):
    columns = ['Satellites', 'Variant', 'Goodput Mbps', 'p95 SRTT ms', 'Mean queued packets',
               'Peak single queue', 'Buffer drops', 'Data retrans %']
    if flows == 5:
        columns.append('Jain fairness')
    columns.append('Resets')
    load = 'Single flow' if flows == 1 else 'Five competing flows'
    lines = [f'**Panel {"A" if flows == 1 else "B"}: {load}, 20–200 s.**', '',
             '| ' + ' | '.join(columns) + ' |',
             '|' + '|'.join(['---', '---'] + ['---:'] * (len(columns) - 2)) + '|']
    for scenario in SCENARIOS:
        for variant in VARIANTS:
            r = next(r for r in records if r['scenario'] == scenario and r['variant'] == variant and int(r['flows']) == flows)
            values = [r['satellites'], LABELS[variant], number(r['goodput_mbps']),
                      number(r['p95_sampled_srtt_ms']), number(r['mean_total_queued_packets']),
                      r['max_single_queue_packets'], r['total_buffer_drops'], number(r['data_retransmission_percent'], 4)]
            if flows == 5:
                values.append(number(r['jain_fairness'], 4))
            values.append(r['adaptive_reset_count'])
            lines.append('| ' + ' | '.join(values) + ' |')
    return '\n'.join(lines)

def write_report(root):
    root = Path(root).expanduser().resolve(strict=True)
    validate(root, 30)  # Recheck evidence; do not trust a stale validation marker.
    records = rows(root / 'analysis/summary.csv')
    text = ['### V-C2. Matched adaptive versus refresh comparison', '',
            'We reran original Vegas, 1/5/10 s sliding histories, and adaptive BaseRTT relearning '
            'at 500, 1,584, and 2,160 satellites using one flow and five competing same-variant flows. '
            'All 30 cases use the same instrumented build, original states, link and buffer settings, '
            'and seed. Every primary metric covers 20–200 s. The five flows start at 0–4 ms, '
            'so Jain fairness uses five simultaneously active flow rates over a common interval.', '',
            '**Table: Matched adaptive versus refresh performance and costs.**', '',
            render_table(records, 1), '', render_table(records, 5), '',
            'Queue means sum monitored device queues and integrate occupancy over time. '
            'p95 SRTT uses the refresh study’s 100 ms sampling convention. Retransmission percentage '
            'counts data retransmission events relative to all data transmission events; it is not a packet-loss rate. '
            'Reset counts in the table cover 20–200 s; complete timestamps are retained separately. '
            'Single-flow Jain fairness is non-informative and is omitted.', '']
    comparisons = []
    for scenario in SCENARIOS:
        one = {r['variant']: r for r in records if r['scenario'] == scenario and int(r['flows']) == 1}
        adaptive = one['adaptive']
        for other in ['refresh1', 'refresh5', 'refresh10']:
            ref = one[other]
            comparisons.append(f"At {adaptive['satellites']} satellites, adaptive versus {LABELS[other]} gives "
                f"{number(adaptive['goodput_mbps'])} versus {number(ref['goodput_mbps'])} Mbps, "
                f"{number(adaptive['mean_total_queued_packets'])} versus {number(ref['mean_total_queued_packets'])} mean queued packets, "
                f"and {number(adaptive['p95_sampled_srtt_ms'])} versus {number(ref['p95_sampled_srtt_ms'])} ms p95 SRTT.")
        five = {r['variant']: r for r in records if r['scenario'] == scenario and int(r['flows']) == 5}
        a = five['adaptive']
        text.append(' '.join(comparisons[-3:]))
        text.append('')
        text.append(f"With five flows at {a['satellites']} satellites, adaptive aggregate goodput is "
                    f"{number(a['goodput_mbps'])} Mbps and Jain fairness is {number(a['jain_fairness'], 4)}. "
                    + ' '.join(f"{LABELS[v]} has {number(five[v]['goodput_mbps'])} Mbps and fairness "
                               f"{number(five[v]['jain_fairness'], 4)}." for v in ['original', 'refresh1', 'refresh5', 'refresh10']))
        text.append('')
    def rates(variant, field):
        return ', '.join(number(next(r for r in records if r['scenario'] == s and r['variant'] == variant
                                    and int(r['flows']) == 1)[field]) for s in SCENARIOS)
    replacement = ('The matched 20–200 s comparison in Section V-C2 gives adaptive goodputs of '
                   + rates('adaptive', 'goodput_mbps') + ' Mbps at 500, 1,584, and 2,160 satellites, respectively. '
                   'The corresponding 1 s history rates are ' + rates('refresh1', 'goodput_mbps')
                   + ' Mbps, and the 5 s history rates are ' + rates('refresh5', 'goodput_mbps') + ' Mbps. '
                   'Adaptive mean total queues are ' + rates('adaptive', 'mean_total_queued_packets')
                   + ' packets, with p95 SRTTs of ' + rates('adaptive', 'p95_sampled_srtt_ms') + ' ms. '
                   'The new table also reports buffer drops, retransmissions and concurrent five-flow fairness. '
                   'These matched costs accompany the rate comparison and bound the justification for selecting '
                   'the conditional, constant-state adaptive detector in the tested layouts.')
    text += ['The table exposes the measured throughput, queue, delay, retransmission, and fairness trade-offs; '
             'a throughput ranking alone does not establish an overall winner. These are deterministic results '
             'for one endpoint pair and three geometries, not independent statistical repetitions. '
             'Five-flow fairness measures competition within each controller; it does not establish mixed-controller fairness.', '',
             '**Replacement for the last paragraph of V-C:**', '',
             replacement, '']
    if (root / 'analysis/dense_q1000_f1.png').is_file():
        text += ['Figures: `sat500_q1000_f1`, `default_q1000_f1`, `dense_q1000_f1`, corresponding `f5` plots, '
                 'and the three `*_fairness` plots. Dashed route-event annotations are verified against the input forwarding states.', '']
    out = root / 'analysis'
    (out / 'section_V_C2.md').write_text('\n'.join(text), encoding='utf-8')
    (out / 'comparison_table.md').write_text(render_table(records, 1) + '\n\n' + render_table(records, 5) + '\n', encoding='utf-8')
    (out / 'replacement_V_C_paragraph.txt').write_text(replacement + '\n', encoding='utf-8')
    print('Generated report-ready text and table under', out)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    write_report(p.parse_args().root)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        sys.exit(str(error) or 'Incomplete comparison matrix')
