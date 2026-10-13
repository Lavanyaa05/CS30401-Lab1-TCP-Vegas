#!/usr/bin/env python3
"""Copy immutable compact evidence, recompute metrics and check archived targets. No simulation."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from experiments import HERE, sha, validate_output

def verify_evidence():
    reference=HERE.parent/'reference'
    expected=json.loads((HERE/'provenance/reference_sha256.json').read_text())
    for rel,digest in expected.items():
        if not (reference/rel).is_file() or sha(reference/rel)!=digest:
            raise ValueError(f'Archived evidence checksum mismatch: {rel}')
    return reference

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=HERE.parent/'generated-reference')
    p.add_argument('--no-plots',action='store_true')
    a=p.parse_args();root=a.output.resolve();validate_output(root)
    source=verify_evidence()
    if root.exists():raise ValueError(f'Output already exists: {root}. Use a new folder or analyze the existing copy directly.')
    shutil.copytree(source,root)
    cmd=[sys.executable,HERE/'analyze.py',root]
    if a.no_plots:cmd.append('--no-plots')
    subprocess.run(list(map(str,cmd)),check=True)
    subprocess.run([sys.executable,str(HERE/'verify_results.py'),str(root/'analysis/summary.csv')],check=True)

if __name__=='__main__':
    try:main()
    except (ValueError,subprocess.CalledProcessError) as e:raise SystemExit(str(e))
