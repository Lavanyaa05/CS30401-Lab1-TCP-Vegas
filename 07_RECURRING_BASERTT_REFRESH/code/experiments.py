#!/usr/bin/env python3
"""Reproduce the 12 recurring BaseRTT-history experiments in an isolated course ns-3 tree."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile

HERE = Path(__file__).resolve().parent
LAYOUTS = {500:(25,20), 1584:(72,22), 2160:(72,30)}
WINDOWS = (0, 1, 5, 10)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def call(argv, log=None, env=None, cwd=None):
    print('RUN:', ' '.join(map(str,argv)),flush=True)
    if log:
        with Path(log).open('w') as out:
            proc=subprocess.Popen(list(map(str,argv)),stdout=out,stderr=subprocess.STDOUT,env=env,cwd=cwd)
            while True:
                try: rc=proc.wait(timeout=30);break
                except subprocess.TimeoutExpired:print('Still running; log:',log,flush=True)
                except BaseException:
                    proc.terminate();proc.wait();raise
        if rc:raise RuntimeError(f'Command exited {rc}; see {log}')
    else:subprocess.run(list(map(str,argv)),check=True,env=env,cwd=cwd)

def plan(a):
    cases=[]
    for n in dict.fromkeys(a.satellites):
        for w in dict.fromkeys(a.windows):
            cases.append(dict(run=f'sat{n}_vegas{w}_r100_q1000_f1',
                scenario=f'sat{n}',satellites=n,orbits=LAYOUTS[n][0],satellites_per_orbit=LAYOUTS[n][1],
                tcp='TcpVegas',window_s=w,rate_mbps=100,queue_packets=1000,flows=1,
                duration_s=a.duration,src=n,dst=n+1,seed=123456789,pacing=False))
    return cases

def validate_output(root):
    package=HERE.parent
    protected=[HERE,package/'reference',package/'tests']
    if root==package or any(root==p or root.is_relative_to(p) or p.is_relative_to(root) for p in protected):
        raise ValueError('Choose a generated output directory, never the package/code/reference root.')
    if any(c.isspace() for c in str(root)):
        raise ValueError('Output path must not contain whitespace (course launcher limitation).')

def package_hash():
    h=hashlib.sha256()
    for p in sorted(HERE.rglob('*')):
        rel=p.relative_to(HERE)
        if p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in rel.parts) and p.suffix!='.pyc':
            h.update(str(rel).encode());h.update(p.read_bytes())
    return h.hexdigest()

def source_hashes(ns3):
    expected=json.loads((HERE/'provenance/implementation.json').read_text())['source_sha256']
    return {rel:sha(ns3/rel) for rel in expected if (ns3/rel).is_file()}

def install(ns3):
    if any(c.isspace() for c in str(ns3)):raise ValueError('ns-3 path must not contain whitespace (course launcher limitation).')
    if not (ns3/'ns3').is_file():raise ValueError(f'Not a course ns-3 installation: {ns3}')
    expected=json.loads((HERE/'provenance/implementation.json').read_text())['source_sha256']
    if source_hashes(ns3)==expected:
        print('Exact measured implementation is already installed.',flush=True);return
    baseline=json.loads((HERE/'provenance/implementation.json').read_text())['baseline_file_sha256']
    for rel,digest in baseline.items():
        if not (ns3/rel).is_file() or sha(ns3/rel)!=digest:raise ValueError(f'Baseline source differs: {rel}. Use a clean course installation; no patch applied.')
    for rel in set(expected)-set(baseline):
        if (ns3/rel).exists():raise ValueError(f'Unexpected existing observer: {rel}; no patch applied.')
    call(['git','apply','--check',HERE/'patches/ns3-refresh.patch'],cwd=ns3)
    # Save originals outside the simulator tree; recover if a postcondition fails.
    with tempfile.TemporaryDirectory(prefix='refresh-patch-') as temp:
        backup=Path(temp)
        for rel in baseline:
            (backup/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ns3/rel,backup/rel)
        try:
            call(['git','apply',HERE/'patches/ns3-refresh.patch'],cwd=ns3)
            if source_hashes(ns3)!=expected:raise ValueError('Patched source hashes differ.')
        except BaseException:
            for rel in baseline:shutil.copy2(backup/rel,ns3/rel)
            for rel in set(expected)-set(baseline):(ns3/rel).unlink(missing_ok=True)
            raise

def state_digest(state,duration=200):
    dyn=state/f'dynamic_state_100ms_for_{duration}s'
    if len(list(state.glob('dynamic_state_*ms_for_*s')))!=1:raise ValueError(f'Ambiguous dynamic-state folders: {state}')
    for t in range(0,duration*1000000000,100000000):
        for prefix in ('fstate_','gsl_if_bandwidth_'):
            if not (dyn/f'{prefix}{t}.txt').is_file():raise ValueError(f'Incomplete state: {prefix}{t}.txt')
    h=hashlib.sha256()
    for p in sorted(state.rglob('*')):
        if p.is_file():h.update(str(p.relative_to(state)).encode());h.update(p.read_bytes())
    return h.hexdigest()

def prepare_state(n,root,a,env):
    supplied=getattr(a,f'state_{n}',None)
    state=Path(supplied).expanduser().resolve() if supplied else root/'states'/f'sat{n}'/'state'
    receipt=state.parent/'STATE_COMPLETE.json'
    if not supplied and not receipt.is_file():
        if state.exists():raise ValueError(f'Incomplete state exists: {state}. Move it aside before regenerating; it is not overwritten.')
        state.parent.mkdir(parents=True,exist_ok=True)
        argv=[sys.executable,HERE/'course/gen_state.py',state.parent,'--orbits',LAYOUTS[n][0],
              '--sats-per-orbit',LAYOUTS[n][1],'--duration','200','--step-ms','100','--threads',a.threads]
        call(argv,log=state.parent/'generation.log',env=env)
        receipt.write_text(json.dumps({'command':list(map(str,argv)),'satellites':n},indent=2)+'\n')
    targets=json.loads((HERE/'provenance/state_metadata.json').read_text())[str(n)]
    for rel,value in targets.items():
        if not (state/rel).is_file() or sha(state/rel)!=value:raise ValueError(f'{state/rel} differs from the measured scenario.')
    digest=state_digest(state)
    if any(c.isspace() for c in str(state)):raise ValueError('State path must not contain whitespace (course config limitation).')
    paths=root/'paths';paths.mkdir(exist_ok=True)
    pathfile=paths/f'path_{n}.csv'
    call([sys.executable,HERE/'course/path_truth.py',state,'dynamic_state_100ms_for_200s',n,n+1,pathfile],
         log=paths/f'path_{n}.log',env=env)
    expected=json.loads((HERE/'provenance/path_hashes.json').read_text())[str(n)]
    if sha(pathfile)!=expected:raise ValueError(f'Path truth for {n} differs from the measured run; investigate before comparing results.')
    return state,digest

def validate_run(run,spec):
    logs=run/'logs_ns3'
    required=['finished.txt','network_queue_bins.csv','queue_devices.csv','queue_drop_events.csv','tc_drop_events.csv']
    for f in range(spec['flows']):
        required += [f'tcp_flow_{f}_{s}.csv' for s in ('progress','cwnd','rtt','extra_bins','retransmissions','cong_state')]
    for name in required:
        if not (logs/name).is_file() or not (logs/name).stat().st_size:raise ValueError(f'Missing/empty trace: {logs/name}')
    if (logs/'finished.txt').read_text().strip()!='Yes':raise ValueError('Simulation did not finish.')
    with (run/'out.txt').open(errors='replace') as f:
        queue_bound=False;configured=False
        for line in f:
            queue_bound |= 'VEGAS_QUEUE_BINDINGS,' in line
            configured |= f"VEGAS_CONFIG,window_s={spec['window_s']:g},trace=1" in line
    if not queue_bound or (spec['tcp']=='TcpVegas' and not configured):raise ValueError('Requested tracing/controller settings were not acknowledged.')
    with (logs/'network_queue_bins.csv').open() as f:
        rows=list(__import__('csv').DictReader(f))
    if len(rows)!=spec['duration_s'] or [float(r['start_s']) for r in rows]!=list(range(spec['duration_s'])):
        raise ValueError('Missing or unordered queue bins; refusing a completion receipt.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','install','states','run'])
    p.add_argument('--satellites',nargs='+',type=int,choices=LAYOUTS,default=[500,1584,2160])
    p.add_argument('--windows',nargs='+',type=int,choices=WINDOWS,default=list(WINDOWS))
    p.add_argument('--duration',type=int,default=200)
    p.add_argument('--threads',type=int,default=1)
    p.add_argument('--output',type=Path,default=HERE.parent/'generated')
    p.add_argument('--ns3',type=Path,default=Path(os.environ.get('NS3_DIR',str(Path.home()/'cs30401/ns-3.48'))))
    for n in LAYOUTS:p.add_argument(f'--state-{n}',type=Path)
    p.add_argument('--retry-incomplete',action='store_true')
    p.add_argument('--no-plots',action='store_true',help='CSV analysis only; no matplotlib needed for analysis.')
    a=p.parse_args()
    if not 1<=a.duration<=200 or a.threads<1:p.error('Duration must be 1..200 s and threads must be positive.')
    cases=plan(a)
    if a.action=='plan':print(json.dumps(cases,indent=2));return
    ns3=a.ns3.expanduser().resolve()
    if a.action in ('install','run'):
        validate_output(a.output.expanduser().resolve())
        install(ns3)
    if a.action=='install':return
    root=a.output.expanduser().resolve();validate_output(root);root.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,NS3_DIR=str(ns3),SATGENPY=str(HERE/'third_party/satgenpy'),VEGAS_TRACE='1',VEGAS_EXTRA_TRACE='1')
    states={n:prepare_state(n,root,a,env) for n in a.satellites}
    if a.action=='states':return
    call([sys.executable,ns3/'ns3','build','main_satnet'],cwd=ns3,log=root/'build.log',env=env)
    provenance={'target_image':'ghcr.io/yeonjong21/cs30401-lab1:2026f-v1','ns3':str(ns3),'ns3_version':(ns3/'VERSION').read_text().strip() if (ns3/'VERSION').exists() else None,'os':platform.platform(),'python':sys.version,'source_sha256':source_hashes(ns3),'patch_sha256':sha(HERE/'patches/ns3-refresh.patch'),'runner_sha256':sha(__file__),'analysis_sha256':sha(HERE/'analyze.py'),'package_source_sha256':package_hash()}
    compiler=shutil.which('g++')
    if compiler:provenance['compiler']=subprocess.run([compiler,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
    lab=os.environ.get('LAB')
    if lab:
        r=subprocess.run(['git','-C',lab,'rev-parse','HEAD'],capture_output=True,text=True)
        provenance['environment_repository_commit']=r.stdout.strip() if r.returncode==0 else None
    (root/f'environment_{time.time_ns()}.json').write_text(json.dumps(provenance,indent=2)+'\n')
    for s in cases:
        n=s['satellites'];state,digest=states[n]
        spec=dict(s,state_sha256=digest,source_sha256=provenance['source_sha256'],package_source_sha256=provenance['package_source_sha256'])
        run=root/'runs'/s['run'];done=run/'EVALUATION_COMPLETE.json'
        if done.is_file():
            if json.loads(done.read_text())['spec']!=spec:raise ValueError(f'Completed inputs differ: {run}. Choose a new output directory.')
            validate_run(run,spec);print('SKIP completed:',s['run'],flush=True);continue
        if run.exists():
            old=run/'evaluation.json'
            if not a.retry_incomplete or not old.is_file() or json.loads(old.read_text())!=spec:raise ValueError(f'Incomplete run: {run}. Use --retry-incomplete only for matching inputs.')
            archive=root/'incomplete';archive.mkdir(exist_ok=True)
            run.rename(archive/(run.name+'_'+str(time.time_ns())))
        run.mkdir(parents=True)
        (run/'evaluation.json').write_text(json.dumps(spec,indent=2)+'\n')
        caseenv=dict(env,VEGAS_WINDOW_S=str(s['window_s']),PACING=str(s['pacing']).lower(),FLOWS=','.join([f'{n}>{n+1}']*s['flows']))
        call(['bash',HERE/'course/make_run.sh',run,state,s['tcp'],s['rate_mbps'],s['queue_packets'],s['duration_s'],n,n+1],env=caseenv)
        started=time.monotonic()
        call(['bash',HERE/'course/run_sim.sh',run],log=run/'launcher.log',env=caseenv)
        validate_run(run,spec)
        done.write_text(json.dumps({'spec':spec,'wall_seconds':time.monotonic()-started},indent=2)+'\n')
    argv=[sys.executable,HERE/'analyze.py',root,'--start',20 if a.duration>20 else 0]
    if a.no_plots:argv.append('--no-plots')
    call(argv)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as e:raise SystemExit(str(e))
    except KeyboardInterrupt:raise SystemExit('Interrupted. Completed cases are preserved; resume with --retry-incomplete.')
