#!/usr/bin/env python3
"""Numerical regression against the archived 20–200 s reference, not new experimental proof."""
import argparse
import csv
import json
import math
from pathlib import Path

def verify(path,rtol=1e-8,atol=1e-6):
    expected=json.loads((Path(__file__).parent/'provenance/reference_metrics.json').read_text())
    with Path(path).open() as f:rows=list(csv.DictReader(f))
    found={r['run']:r for r in rows}
    if len(found)!=len(rows) or set(found)!=set(expected):raise ValueError('Expected exactly the 12 canonical refresh cases, with no duplicates.')
    errors=[];checks=0
    for name,metrics in expected.items():
        r=found[name]
        if float(r['measurement_start_s'])!=20 or float(r['duration_s'])!=200:raise ValueError('Reference verification requires the 20–200 s summary.')
        for key,target in metrics.items():
            actual=r.get(key)
            ok=actual in ('',None) if target is None else actual not in ('',None) and math.isclose(float(actual),target,rel_tol=rtol,abs_tol=atol)
            checks+=1
            if not ok:errors.append(f'{name}: {key}: measured {actual}, reference {target}')
    if errors:raise ValueError('\n'.join(errors))
    print(f'PASS: {checks} archived numerical checks across {len(rows)} cases. This is an analysis regression, not a fresh ns-3 run.')
    return checks

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('summary',type=Path)
    p.add_argument('--rtol',type=float,default=1e-8);p.add_argument('--atol',type=float,default=1e-6)
    a=p.parse_args()
    if a.rtol<0 or a.atol<0:p.error('Tolerances must be nonnegative.')
    try:verify(a.summary,a.rtol,a.atol)
    except ValueError as e:raise SystemExit(str(e))
