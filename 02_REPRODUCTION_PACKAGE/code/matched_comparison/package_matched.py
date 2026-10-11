"""Export compact results and optionally raw evidence without overwriting archives."""
import argparse
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from common import sha
from validate_matched import validate

def package(root, include_raw=False):
    root = Path(root).expanduser().resolve(strict=True)
    targets = [root.parent / (root.name + '_results.zip')]
    if include_raw:
        targets.append(root.parent / (root.name + '_raw.zip'))
    if any(p.exists() for p in targets):
        raise ValueError('Export already exists; choose another output root or rename the previous archive')
    validate(root, 30)
    done = sorted(root.glob('*/EVALUATION_COMPLETE.json'))
    compact = [p for p in sorted((root / 'analysis').rglob('*')) if p.is_file()]
    if (root / 'study.json').is_file():
        compact.append(root / 'study.json')
    raw = []
    for marker in done:
        case = marker.parent
        for p in sorted(case.rglob('*')):
            if p.is_file():
                if p.name.endswith(('_progress.csv', '_rtt.csv')):
                    raw.append(p)
                else:
                    compact.append(p)
    # Each archive includes the receipt/manifests needed to verify it. Raw archive
    # contains the whole completed evidence, so it can independently regenerate metrics.
    filesets = [compact] + ([compact + raw] if include_raw else [])
    created = []
    try:
        for target, files in zip(targets, filesets):
            created.append(target)
            checksums = {}
            with ZipFile(target, 'x', ZIP_DEFLATED) as z:
                for p in sorted(set(files)):
                    name = root.name + '/' + p.relative_to(root).as_posix()
                    z.write(p, name)
                    checksums[name] = sha(p)
                import json
                z.writestr(root.name + '/ARCHIVE_SHA256.json', json.dumps(checksums, indent=2) + '\n')
                z.writestr(root.name + '/CONTENTS.txt',
                    'Matched 30-case study. Compact export omits raw progress/SRTT traces; '
                    'the raw export retains all evidence for independent recalculation.\n'
                    'Use the matched_comparison source package and its pinned analyzer.\n')
    except BaseException:
        for p in created:
            p.unlink(missing_ok=True)
        raise
    for target in targets:
        print(target, f'({target.stat().st_size / 1024**2:.2f} MiB)')
    return targets

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--include-raw', action='store_true')
    a = p.parse_args()
    package(a.root, a.include_raw)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        sys.exit(str(error) or 'Incomplete comparison matrix')
