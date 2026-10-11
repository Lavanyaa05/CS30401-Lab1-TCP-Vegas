"""Shared provenance and validation helpers (standard library only)."""
import csv
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENARIOS = {'sat500': (500, 25, 20), 'default': (1584, 72, 22), 'dense': (2160, 72, 30)}
VARIANTS = {'original': (0, False), 'refresh1': (1, False), 'refresh5': (5, False),
            'refresh10': (10, False), 'adaptive': (0, True)}
SOURCES = [
    'src/internet/model/tcp-vegas.cc', 'src/internet/model/tcp-vegas.h',
    'scratch/main_satnet/main_satnet.cc', 'scratch/main_satnet/vegas-experiment.h',
    'scratch/main_satnet/vegas-queue-observer.h',
    'contrib/basic-sim/model/apps/tcp-flow-send-application.cc',
    'contrib/basic-sim/model/apps/vegas-flow-observer.h',
    'src/internet/model/adaptive-basertt-detector.h',
]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text())

def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)

def rows(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, records, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(records[0]))
        w.writeheader()
        w.writerows(records)

def reference():
    return read_json(HERE / 'reference/index.json')

def verify_package():
    index = reference()
    for group in ['reference_files', 'vendor_files']:
        for name, expected in index[group].items():
            if sha(HERE / name) != expected:
                raise ValueError('Bundled evidence changed: ' + name)

def package_hashes():
    files = []
    for directory, subdirs, names in os.walk(HERE):
        subdirs[:] = [d for d in subdirs if d not in ['__pycache__', '.venv', 'backups', 'tests'] and not d.startswith('.')]
        files.extend(Path(directory) / name for name in names)
    return {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(files)
            if p.suffix in ['.py', '.h', '.patch', '.csv', '.json', '.toml', '.lock', '.sh']}

def tree_digest(state):
    """Same POSIX path + hexadecimal file digest convention as the 500 runner."""
    h = hashlib.sha256()
    for p in sorted(Path(state).rglob('*')):
        if p.is_file():
            h.update(p.relative_to(state).as_posix().encode())
            h.update(sha(p).encode())
    return h.hexdigest()

def check_state(state, scenario):
    state = Path(state).expanduser().resolve(strict=True)
    nsat, planes, per_plane = SCENARIOS[scenario]
    if (state / 'tles.txt').read_text().splitlines()[0].split() != [str(planes), str(per_plane)]:
        raise ValueError(f'{scenario}: wrong constellation geometry')
    dyn = state / 'dynamic_state_100ms_for_200s'
    if list(state.glob('dynamic_state_*')) != [dyn]:
        raise ValueError(f'{state}: expected exactly one 100 ms / 200 s dynamic state')
    for t in range(0, 200000000000, 100000000):
        for prefix in ['fstate', 'gsl_if_bandwidth']:
            if not (dyn / f'{prefix}_{t}.txt').is_file():
                raise ValueError(f'Missing {prefix} at {t} in {dyn}')
    expected = reference()['states'][scenario]
    metadata = {p.name: sha(p) for p in sorted(state.iterdir()) if p.is_file()}
    for name, digest in expected.get('state_metadata_sha256', {}).items():
        if metadata.get(name) != digest:
            raise ValueError(f'{scenario}: reference metadata mismatch: {name}')
    digest = tree_digest(state)
    if expected.get('state_sha256', digest) != digest:
        raise ValueError(f'{scenario}: original full state checksum mismatch')
    # Verify reference path timing against these actual incremental route files.
    ref = rows(HERE / f'reference/path_{scenario}.csv')
    if len(ref) != 2000:
        raise ValueError('Incomplete reference route history')
    forwarding = {}
    previous = None
    events = []
    for i, row in enumerate(ref):
        t = i * 100000000
        if abs(float(row['t_s']) - t / 1e9) > 1e-8:
            raise ValueError('Reference route timestamps differ')
        with (dyn / f'fstate_{t}.txt').open() as f:
            for line in f:
                a, b, next_hop, _, _ = map(int, line.strip().split(','))
                forwarding[a, b] = next_hop
        def walk(a, b):
            path = [a]
            while a != b:
                a = forwarding.get((a, b), -1)
                if a < 0 or a in path or len(path) > nsat + 2:
                    return None
                path.append(a)
            return path
        pair = (walk(nsat, nsat + 1), walk(nsat + 1, nsat))
        connected = all(p is not None for p in pair)
        changed = int(previous is not None and previous != pair) if connected else 1
        path = '-'.join(map(str, pair[0])) if connected else ''
        if row['path_fwd'] != path or int(row['path_changed']) != changed:
            raise ValueError(f'{scenario}: reference route differs at {t / 1e9}s')
        if connected and changed:
            before = ref[i - 1]['rtt_prop_ms'] if i else ''
            after = row['rtt_prop_ms']
            events.append(dict(time_s=t / 1e9, before_prop_ms=before, after_prop_ms=after,
                               delta_prop_ms=float(after) - float(before) if before and after else ''))
        previous = pair if connected else None
    return dict(path=str(state), full_tree_sha256=digest, metadata_sha256=metadata,
                reference_routes_verified=True, route_events=events)

def validate_outputs(run, spec):
    run = Path(run)
    logs = run / 'logs_ns3'
    required = ['finished.txt', 'network_queue_bins.csv', 'queue_devices.csv',
                'queue_drop_events.csv', 'tc_drop_events.csv']
    for flow in range(spec['flows']):
        required += [f'tcp_flow_{flow}_{suffix}.csv' for suffix in
                     ['progress', 'cwnd', 'rtt', 'extra_bins', 'retransmissions', 'cong_state']]
    for name in required:
        p = logs / name
        if not p.is_file() or p.stat().st_size == 0:
            raise ValueError(f'Missing or empty output: {p}')
    if (logs / 'finished.txt').read_text().strip() != 'Yes':
        raise ValueError(f'{run}: simulator did not finish')
    text = (run / 'out.txt').read_text(errors='replace')
    mode = f"VEGAS_CONFIG,window_s={spec['window_s']},trace=1,adaptive={int(spec['adaptive'])}"
    if mode not in text.splitlines():
        raise ValueError(f'{run}: simulator did not acknowledge {mode}')
    binding = [line for line in text.splitlines() if line.startswith('VEGAS_QUEUE_BINDINGS,')]
    if not binding or not any(int(line.split(',')[1]) > 0 for line in binding):
        raise ValueError(f'{run}: queue observers did not bind')
    for flow in range(spec['flows']):
        if f'VEGAS_FLOW_BINDING,{flow}' not in text.splitlines():
            raise ValueError(f'{run}: observer missing for flow {flow}')
    bins = rows(logs / 'network_queue_bins.csv')
    if len(bins) != spec['duration_s'] or any(float(r['start_s']) != i or float(r['end_s']) != i + 1 for i, r in enumerate(bins)):
        raise ValueError(f'{run}: incomplete or unordered queue bins')
    if not any(line.startswith('VEGAS_DECISION,') for line in text.splitlines()):
        raise ValueError(f'{run}: no Vegas decisions recorded')
    if not spec['adaptive'] and 'VEGAS_ADAPTIVE_RESET,' in text:
        raise ValueError(f'{run}: adaptive reset in disabled arm')

def verify_receipt(run):
    run = Path(run)
    receipt = read_json(run / 'EVALUATION_COMPLETE.json')
    for name, digest in receipt['output_sha256'].items():
        if sha(run / name) != digest:
            raise ValueError(f'{run}: retained output changed: {name}')
    validate_outputs(run, receipt['spec'])
    return receipt
