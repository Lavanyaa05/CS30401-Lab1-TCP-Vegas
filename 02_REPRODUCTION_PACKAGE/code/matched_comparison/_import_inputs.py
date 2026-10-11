"""Development-only import of the supplied evidence; never runs a simulator."""
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
DOWNLOADS = Path.home() / 'Downloads' / 'Telegram Desktop'

def copy(z, name, dest):
    target = ROOT / dest
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(z.read(name))

def main():
    with ZipFile(DOWNLOADS / 'Vegas_Evaluation.zip') as z:
        for name in ['analyze_suite.py', 'vegas-queue-observer.h', 'vegas-flow-observer.h']:
            copy(z, 'Vegas_Evaluation/' + name, 'vendor/' + name)
        for name in ['pyproject.toml', 'uv.lock']:
            copy(z, 'Vegas_Evaluation/' + name, name)
    with ZipFile(DOWNLOADS / 'Vegas_500_AllInOne.zip') as z:
        for name in ['vegas-window.patch', 'vegas-experiment.h']:
            copy(z, 'Vegas_500_AllInOne/patches/vegas/' + name, 'vendor/' + name)
        for name in ['make_run.sh', 'run_sim.sh']:
            copy(z, 'Vegas_500_AllInOne/course/' + name, 'vendor/' + name)
        for scenario, name in [('sat500', 'state500/path_500.csv'), ('default', 'historical/path_1584.csv'), ('dense', 'historical/path_2160.csv')]:
            copy(z, 'Vegas_500_AllInOne/' + name, 'reference/path_' + scenario + '.csv')
    index = {'sources': {}, 'states': {}, 'archives': {}}
    controls = []
    for archive, prefix, cases in [
        ('vegas-500-results_results.zip', 'vegas-500-results', [('sat500', 'vegas1')]),
        ('vegas-evaluation_results.zip', 'vegas-evaluation', [('default', 'default_w1_q1000_f1'), ('dense', 'dense_w1_q1000_f1')]),
    ]:
        path = DOWNLOADS / archive
        index['archives'][archive] = hashlib.sha256(path.read_bytes()).hexdigest()
        with ZipFile(path) as z:
            for scenario, run in cases:
                spec = json.loads(z.read(prefix + '/' + run + '/evaluation.json'))
                if index['sources'] and index['sources'] != spec['source_sha256']:
                    raise ValueError('Reference source hashes differ')
                index['sources'] = spec['source_sha256']
                index['states'][scenario] = {k: spec[k] for k in ['state_sha256', 'state_metadata_sha256'] if k in spec}
            for row in csv.DictReader(io.StringIO(z.read(prefix + '/analysis/summary.csv').decode())):
                if row.get('tcp', 'TcpVegas') != 'TcpVegas':
                    continue
                row['variant'] = 'original' if float(row['window_s']) == 0 else 'refresh' + str(int(float(row['window_s'])))
                controls.append(row)
    fields = list(dict.fromkeys(k for row in controls for k in row))
    with (ROOT / 'reference/controls.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(controls)
    index['reference_files'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted((ROOT / 'reference').glob('*.csv'))}
    index['vendor_files'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT / 'vendor').glob('*'))}
    (ROOT / 'reference/index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Imported 12 reference controls, exact observer sources, and route histories.')

if __name__ == '__main__':
    main()
