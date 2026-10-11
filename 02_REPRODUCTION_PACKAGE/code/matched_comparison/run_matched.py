"""Run the 30 matched Vegas cases sequentially, with verified inputs and resume."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from common import (HERE, SCENARIOS, SOURCES, VARIANTS, check_state, package_hashes,
                    read_json, sha, tree_digest, validate_outputs, verify_package,
                    verify_receipt, write_json)
from install_matched import install

def input_text(run, state, satellites, flows, duration):
    relative = os.path.relpath(state, run).replace('\\', '/')
    config = f'''simulation_end_time_ns={duration * 1000000000}
simulation_seed=123456789
satellite_network_dir="{relative}"
satellite_network_routes_dir="{relative}/dynamic_state_100ms_for_200s"
dynamic_state_update_interval_ns=100000000
isl_data_rate_megabit_per_s=100
gsl_data_rate_megabit_per_s=100
isl_max_queue_size_pkts=1000
gsl_max_queue_size_pkts=1000
enable_isl_utilization_tracking=false
tcp_socket_type=TcpVegas
tcp_enable_pacing=false
enable_tcp_flow_scheduler=true
tcp_flow_schedule_filename="schedule.csv"
tcp_flow_enable_logging_for_tcp_flow_ids=set({','.join(map(str, range(flows)))})
'''
    schedule = ''.join(f'{i},{satellites},{satellites + 1},100000000000,{i * 1000000},,\n' for i in range(flows))
    return {'config_ns3.properties': config, 'schedule.csv': schedule}

def text_hashes(texts):
    import hashlib
    return {name: hashlib.sha256(text.encode()).hexdigest() for name, text in texts.items()}

def command(args, log, env, cwd=None):
    print('START:', ' '.join(map(str, args)), '\nLog:', log, flush=True)
    with Path(log).open('w') as output:
        job = subprocess.Popen(list(map(str, args)), stdout=output, stderr=subprocess.STDOUT,
                               env=env, cwd=cwd, start_new_session=os.name == 'posix')
        try:
            while True:
                try:
                    status = job.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    print('Still running; see', log, flush=True)
        except BaseException:
            if os.name == 'posix':
                os.killpg(job.pid, signal.SIGTERM)
            else:
                job.terminate()
            try:
                job.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(job.pid, signal.SIGKILL)
                else:
                    job.kill()
                job.wait()
            raise
    if status:
        print('\n'.join(Path(log).read_text(errors='replace').splitlines()[-25:]))
        raise ValueError(f'Command failed ({status}); retained log: {log}')

def executable(ns3):
    candidates = [p for p in (ns3 / 'build').rglob('ns3.48-main_satnet*')
                  if p.is_file() and os.access(p, os.X_OK) and p.suffix not in ['.o', '.so', '.a']]
    if len(candidates) != 1:
        raise ValueError(f'Expected one built main_satnet executable, found {candidates}; reconcile build profiles')
    return candidates[0]

def run(args):
    verify_package()
    ns3 = Path(os.environ.get('NS3_DIR', '')).expanduser()
    lab = Path(os.environ.get('LAB', '')).expanduser()
    if not os.environ.get('NS3_DIR') or not os.environ.get('LAB'):
        raise ValueError('Set NS3_DIR and LAB to the existing course installation')
    ns3, lab = ns3.resolve(strict=True), lab.resolve(strict=True)
    install(ns3, check=True)
    if not (ns3 / SOURCES[-1]).is_file():
        raise ValueError('Run install_matched.py without --check before running the matrix')
    # Check course helpers exist, but execute exact vendored helpers for reproducibility.
    for name in ['make_run.sh', 'run_sim.sh']:
        if not (lab / 'scripts' / name).is_file():
            raise ValueError('Missing course helper: ' + name)
    sources = {name: sha(ns3 / name) for name in SOURCES}
    states = {}
    for scenario in args.scenarios:
        state = getattr(args, scenario + '_state')
        print('Verifying complete state and reference routes:', scenario, state, flush=True)
        states[scenario] = check_state(state, scenario)
    out = args.output.expanduser().resolve()
    package = package_hashes()
    plans = []
    # All twelve single-flow controls precede adaptive in the default matrix.
    for flows in args.flows:
        for variant in args.variants:
            window, adaptive = VARIANTS[variant]
            for scenario in args.scenarios:
                nsat, planes, per_plane = SCENARIOS[scenario]
                name = f'{scenario}_{variant}_q1000_f{flows}'
                inputs = input_text(out / name, states[scenario]['path'], nsat, flows, args.duration)
                spec = dict(schema_version=1, scenario=scenario, satellites=nsat, orbits=planes,
                            satellites_per_orbit=per_plane, variant=variant, window_s=window,
                            adaptive=adaptive, shift_threshold_ns=3000000, persistence_cycles=5,
                            cooldown_ns=10000000000, tcp='TcpVegas', queue_packets=1000,
                            flows=flows, duration_s=args.duration, rate_mbps=100, mss_bytes=1380,
                            route_step_ns=100000000, seed=123456789, pacing=False, src=nsat,
                            dst=nsat + 1, flow_start_ns=[i * 1000000 for i in range(flows)],
                            flow_size_bytes=100000000000, state=states[scenario],
                            source_sha256=sources, package_sha256=package,
                            input_sha256=text_hashes(inputs), extra_trace=True, vegas_trace=True)
                plans.append((name, spec, inputs))
    print(f'{len(plans)} cases; sequential; {args.duration} simulated seconds each. Output: {out}', flush=True)
    for name, spec, _ in plans:
        print(name, f"history={spec['window_s']}s adaptive={int(spec['adaptive'])} endpoints={spec['src']}>{spec['dst']}")
    if args.dry_run:
        return
    if os.name != 'posix':
        raise ValueError('Simulation execution requires the original Linux course environment')
    # Reject incompatible existing cases before building or creating any case directory.
    for name, spec, _ in plans:
        directory = out / name
        done = directory / 'EVALUATION_COMPLETE.json'
        if done.exists():
            receipt = verify_receipt(directory)
            if receipt['spec'] != spec:
                raise ValueError(f'{directory}: completed inputs differ; use a new output root')
        elif directory.exists():
            manifest = directory / 'evaluation.json'
            if not args.retry_incomplete or not manifest.is_file() or read_json(manifest) != spec:
                raise ValueError(f'{directory}: matching incomplete case requires --retry-incomplete; otherwise use a new root')
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(NS3_DIR=str(ns3), LAB=str(lab), VEGAS_TRACE='1', VEGAS_EXTRA_TRACE='1', PACING='false')
    command([sys.executable, ns3 / 'ns3', 'build', 'main_satnet'], out / 'build.log', env, ns3)
    binary = executable(ns3)
    binary_hash = sha(binary)
    write_json(out / 'study.json', dict(schema_version=1, expected_cases=[name for name, _, _ in plans],
                states=states, source_sha256=sources, package_sha256=package,
                executable=str(binary), executable_sha256=binary_hash))
    for name, spec, inputs in plans:
        directory = out / name
        done = directory / 'EVALUATION_COMPLETE.json'
        if done.exists():
            if read_json(done)['executable_sha256'] != binary_hash:
                raise ValueError(f'{directory}: executable differs; use a new output root')
            print('SKIP completed:', name, flush=True)
            continue
        if directory.exists():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            directory.rename(out / ('incomplete_' + name + '_' + stamp))
        directory.mkdir()
        write_json(directory / 'evaluation.json', spec)
        case_env = env.copy()
        case_env.update(VEGAS_WINDOW_S=str(spec['window_s']), VEGAS_ADAPTIVE=str(int(spec['adaptive'])),
                        FLOWS=','.join([f"{spec['src']}>{spec['dst']}"] * spec['flows']))
        command(['bash', HERE / 'vendor/make_run.sh', directory, spec['state']['path'], 'TcpVegas',
                 '100', '1000', str(args.duration), str(spec['src']), str(spec['dst'])],
                directory / 'setup.log', case_env)
        for filename, expected in spec['input_sha256'].items():
            if sha(directory / filename) != expected:
                raise ValueError(f'{directory}: generated {filename} differs from planned input')
        started = time.monotonic()
        command(['bash', HERE / 'vendor/run_sim.sh', directory], directory / 'launcher.log', case_env)
        validate_outputs(directory, spec)
        if sha(binary) != binary_hash or any(sha(ns3 / p) != h for p, h in sources.items()):
            raise ValueError('Source or executable changed during simulation; case not marked complete')
        if tree_digest(Path(spec['state']['path'])) != spec['state']['full_tree_sha256']:
            raise ValueError('State changed during simulation; case not marked complete')
        retained = [directory / 'out.txt', directory / 'config_ns3.properties', directory / 'schedule.csv']
        retained += [p for p in sorted((directory / 'logs_ns3').rglob('*')) if p.is_file()]
        write_json(done, dict(spec=spec, wall_seconds=time.monotonic() - started,
                   executable_sha256=binary_hash, executable_path=str(binary),
                   output_sha256={p.relative_to(directory).as_posix(): sha(p) for p in retained}))
        print('COMPLETE:', name, flush=True)
    print('All requested cases completed. Run analyze_matched.py, then validate_matched.py.', flush=True)

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenarios', nargs='+', choices=list(SCENARIOS), default=list(SCENARIOS))
    p.add_argument('--variants', nargs='+', choices=list(VARIANTS), default=list(VARIANTS))
    p.add_argument('--flows', nargs='+', type=int, choices=[1, 5], default=[1, 5])
    p.add_argument('--duration', type=int, default=200)
    home = Path.home() / 'cs30401'
    p.add_argument('--sat500-state', type=Path, default=home / 'work/Vegas_500_AllInOne/state500/state')
    p.add_argument('--default-state', type=Path, default=Path(os.environ.get('STATE_EXAMPLE', str(home / 'lab/data/seoul_london/state'))))
    p.add_argument('--dense-state', type=Path, default=home / 'work/states/sat_2160/state')
    p.add_argument('--output', type=Path, default=home / 'work/vegas-adaptive-matched')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--retry-incomplete', action='store_true')
    return p

def main():
    p = parser()
    a = p.parse_args()
    if not 1 <= a.duration <= 200:
        p.error('duration must be an integer from 1 to 200')
    for name in ['scenarios', 'variants', 'flows']:
        if len(getattr(a, name)) != len(set(getattr(a, name))):
            p.error('Duplicate ' + name)
    run(a)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit('Stopped; matching unfinished attempts can be retried with --retry-incomplete.')
    except (ValueError, OSError, KeyError) as error:
        sys.exit(str(error))
