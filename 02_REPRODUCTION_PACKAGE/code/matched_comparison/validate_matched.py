"""Validate retained evidence and all twelve archived control comparisons."""
import argparse
import math
from pathlib import Path
import sys

from common import (HERE, SCENARIOS, VARIANTS, read_json, rows, sha, verify_package,
                    verify_receipt, write_json)

FLOAT_CONTROLS = ['goodput_mbps', 'mean_sampled_srtt_ms', 'p95_sampled_srtt_ms', 'mean_total_queued_packets']
INT_CONTROLS = ['queue_drops', 'tc_drops', 'total_buffer_drops', 'data_retransmissions']

def validate(root, expected_cases=30, save=True, controls_only=False):
    root = Path(root).expanduser().resolve(strict=True)
    verify_package()
    out = root / 'analysis'
    manifest = read_json(out / 'analysis_manifest.json')
    if manifest['analyzer_sha256'] != sha(HERE / 'analyze_matched.py'):
        raise ValueError('Analyzer changed since analysis; regenerate summaries')
    if manifest['analysis_core_sha256'] != sha(HERE / 'vendor/analyze_suite.py'):
        raise ValueError('Analysis core changed since analysis')
    for name, digest in manifest['generated_sha256'].items():
        if sha(root / name) != digest:
            raise ValueError('Generated evidence changed: ' + name)
    completed = sorted(root.glob('*/EVALUATION_COMPLETE.json'))
    if len(completed) != expected_cases or len(manifest['receipts_sha256']) != expected_cases:
        raise ValueError(f'Expected {expected_cases} completed receipts and analyzed cases, found {len(completed)}')
    summaries = rows(out / 'summary.csv')
    per_flow = rows(out / 'per_flow.csv')
    if len(summaries) != expected_cases or len({r['run'] for r in summaries}) != expected_cases:
        raise ValueError('Summary row count/uniqueness differs from completed matrix')
    summary_by_run = {r['run']: r for r in summaries}
    state_hashes, source_hashes, binary_hashes, identities = {}, set(), set(), set()
    flow_count = 0
    for marker in completed:
        name = marker.parent.name
        if manifest['receipts_sha256'].get(name) != sha(marker):
            raise ValueError('Receipt changed after analysis: ' + name)
        receipt = verify_receipt(marker.parent)
        spec = receipt['spec']
        source_hashes.add(tuple(sorted(spec['source_sha256'].items())))
        binary_hashes.add(receipt['executable_sha256'])
        state_hashes.setdefault(spec['scenario'], set()).add(spec['state']['full_tree_sha256'])
        if not spec['state']['reference_routes_verified']:
            raise ValueError('Reference route events were not verified')
        identities.add((spec['scenario'], spec['variant'], spec['flows']))
        flow_count += spec['flows']
        row = summary_by_run[name]
        for key in ['scenario', 'variant', 'flows', 'duration_s', 'satellites', 'window_s', 'queue_packets']:
            if str(row[key]) != str(spec[key]):
                raise ValueError(f'{name}: summary and manifest disagree on {key}')
        for key in ['goodput_mbps', 'mean_sampled_srtt_ms', 'p95_sampled_srtt_ms',
                    'mean_total_queued_packets', 'max_single_queue_packets', 'data_tx_packets',
                    'data_retransmissions', 'total_buffer_drops']:
            if not row[key] or not math.isfinite(float(row[key])) or float(row[key]) < 0:
                raise ValueError(f'{name}: missing, nonfinite, or negative {key}')
        if int(row['max_single_queue_packets']) > spec['queue_packets']:
            raise ValueError(f'{name}: individual queue exceeds its configured limit')
        if float(row['mean_total_queued_packets']) > (spec['satellites'] * 6 + 2) * spec['queue_packets']:
            raise ValueError(f'{name}: impossible total queue occupancy')
        if int(row['total_buffer_drops']) != int(row['queue_drops']) + int(row['tc_drops']):
            raise ValueError('Buffer-drop counts are not additive')
        if int(row['data_retransmissions']) > int(row['data_tx_packets']):
            raise ValueError('Retransmissions exceed data transmission events')
        retransmissions = 0
        for flow in range(spec['flows']):
            retransmissions += sum(int(row['measurement_start_s']) * 1000000000 <= int(event['time_ns']) < spec['duration_s'] * 1000000000
                                   for event in rows(marker.parent / 'logs_ns3' / f'tcp_flow_{flow}_retransmissions.csv'))
        if retransmissions != int(row['data_retransmissions']):
            raise ValueError(f'{name}: retransmission event log differs from summary counters')
        tx, retx = int(row['data_tx_packets']), int(row['data_retransmissions'])
        if tx:
            if not row['data_retransmission_percent'] or abs(float(row['data_retransmission_percent']) - 100 * retx / tx) > 1e-10:
                raise ValueError('Retransmission percentage does not match counters')
        elif row['data_retransmission_percent']:
            raise ValueError('Zero-transmission percentage must be undefined')
        rates = [r for r in per_flow if r['run'] == name]
        if sorted(int(r['flow']) for r in rates) != list(range(spec['flows'])):
            raise ValueError(f'{name}: missing or duplicate per-flow rows')
        values = [float(r['goodput_mbps']) for r in rates]
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Invalid per-flow goodput')
        if abs(sum(values) - float(row['goodput_mbps'])) > 1e-8:
            raise ValueError('Per-flow rates do not sum to aggregate goodput')
        denom = len(values) * sum(v * v for v in values)
        expected_jain = sum(values) ** 2 / denom if denom else None
        if expected_jain is None:
            if row['jain_fairness']:
                raise ValueError('Zero-traffic fairness must be undefined')
        elif not row['jain_fairness'] or abs(float(row['jain_fairness']) - expected_jain) > 1e-10:
            raise ValueError('Jain fairness does not match common-window flow rates')
        if (row['fairness_informative'] == 'True') != (spec['flows'] == 5):
            raise ValueError('Incorrect fairness interpretation')
        if not spec['adaptive'] and int(row['whole_run_reset_count']) != 0:
            raise ValueError('Adaptive resets found in a control arm')
    if len(per_flow) != flow_count:
        raise ValueError(f'Expected {flow_count} per-flow rows, found {len(per_flow)}')
    if len(source_hashes) != 1 or len(binary_hashes) != 1 or any(len(v) != 1 for v in state_hashes.values()):
        raise ValueError('Compared cases have different source builds or state trees')
    comparisons = []
    if expected_cases == 30:
        expected = {(s, v, f) for s in SCENARIOS for v in VARIANTS for f in [1, 5]}
        if identities != expected or flow_count != 90:
            raise ValueError('Full study must contain exactly the 30 specified cases and 90 flows')
    if controls_only:
        expected = {(s, v, 1) for s in SCENARIOS for v in VARIANTS if v != 'adaptive'}
        if expected_cases != 12 or identities != expected or flow_count != 12:
            raise ValueError('Control gate requires exactly twelve original/refresh single-flow cases')
    check_controls = expected_cases == 30 or controls_only
    if check_controls:
        if manifest['measurement_start_s'] != 20 or manifest['late_start_s'] != 60:
            raise ValueError('Full study requires 20–200 s main and 60–200 s late metrics')
        if any(int(r['duration_s']) != 200 for r in summaries):
            raise ValueError('Full study requires 200 simulated seconds per case')
        archived = rows(HERE / 'reference/controls.csv')
        for ref in archived:
            row = next(r for r in summaries if r['scenario'] == ref['scenario']
                       and r['variant'] == ref['variant'] and int(r['flows']) == 1)
            for key in FLOAT_CONTROLS:
                delta = abs(float(row[key]) - float(ref[key]))
                comparisons.append(dict(run=row['run'], metric=key, delta=delta, tolerance=.001))
                if delta > .001:
                    raise ValueError(f"Archived control mismatch: {row['run']} {key}, delta={delta:.9g} > 0.001. Investigate source/state/config before reporting.")
            for key in INT_CONTROLS:
                if int(row[key]) != int(ref[key]):
                    raise ValueError(f"Archived control mismatch: {row['run']} {key}")
        if len(archived) != 12:
            raise ValueError('Expected twelve archived single-flow controls')
    result = dict(status='passed', full_matrix=expected_cases == 30, completed_cases=len(completed),
                  per_flow_rows=len(per_flow), archived_controls_checked=12 if check_controls else 0,
                  summary_sha256=sha(out / 'summary.csv'), per_flow_sha256=sha(out / 'per_flow.csv'),
                  analysis_manifest_sha256=sha(out / 'analysis_manifest.json'),
                  validator_sha256=sha(Path(__file__)), control_comparisons=comparisons)
    if save:
        write_json(out / 'validation.json', result)
    print(f'PASS: {len(completed)} cases, {len(per_flow)} flow rows; archived controls checked: {result["archived_controls_checked"]}')
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--expected-cases', type=int, default=30)
    p.add_argument('--controls-only', action='store_true', help='Gate twelve single-flow controls against the archives before adaptive/full matrix')
    a = p.parse_args()
    if a.expected_cases < 1:
        p.error('expected-cases must be positive')
    validate(a.root, a.expected_cases, controls_only=a.controls_only)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        sys.exit(str(error) or 'Missing required matched control')
