"""Unit/integration tests use synthetic evidence, never satellite simulations."""
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from zipfile import ZipFile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analyze_matched as analysis
import common
import install_matched as installer
import package_matched
import run_matched as runner
import validate_matched
import write_report_section

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, newline='\n')

def fixture(root, scenarios=('sat500', 'default', 'dense'), variants=tuple(common.VARIANTS), loads=(1, 5), duration=200):
    """Known counters/costs; archived rows define only regression-test targets."""
    controls = {(r['scenario'], r['variant']): r for r in common.rows(HERE / 'reference/controls.csv')}
    for scenario in scenarios:
        for variant in variants:
            for load in loads:
                window, adaptive = common.VARIANTS[variant]
                nsat, planes, per_plane = common.SCENARIOS[scenario]
                directory = root / f'{scenario}_{variant}_q1000_f{load}'
                logs = directory / 'logs_ns3'
                spec = dict(scenario=scenario, satellites=nsat, orbits=planes, satellites_per_orbit=per_plane,
                            variant=variant, window_s=window, adaptive=adaptive, queue_packets=1000,
                            flows=load, duration_s=duration, source_sha256={'fake-source': 'synthetic'},
                            state=dict(full_tree_sha256='synthetic-' + scenario, reference_routes_verified=True,
                                       route_events=[dict(time_s=39.9, before_prop_ms=81.143, after_prop_ms=85.448, delta_prop_ms=4.305)]))
                common.write_json(directory / 'evaluation.json', spec) if directory.exists() else None
                ref = controls.get((scenario, variant)) if load == 1 else None
                rate = float(ref['goodput_mbps']) if ref else (60 if adaptive else 70)
                queued = float(ref['mean_total_queued_packets']) if ref else 20
                peak = int(ref['max_single_queue_packets']) if ref else 80
                tx = int(ref['data_tx_packets']) if ref else 1000
                retx = int(ref['data_retransmissions']) if ref else 2
                drops = int(ref['total_buffer_drops']) if ref else 0
                # Construct 1800 equally spaced SRTT samples with the specified
                # mean and nearest-rank p95, rounded to integer nanoseconds.
                p95 = float(ref['p95_sampled_srtt_ms']) if ref else 100
                mean = float(ref['mean_sampled_srtt_ms']) if ref else 95
                low = (mean * 1800 - p95 * 91) / 1709
                for flow in range(load):
                    prefix = logs / f'tcp_flow_{flow}'
                    useful_end = round(rate * (duration - 20) * 1e6 / 8 / load) if duration > 20 else round(rate * duration * 1e6 / 8 / load)
                    start = 20 if duration > 20 else 0
                    progress = ''.join(f'{flow},{i * 1000000000},{round(useful_end * max(0, i-start) / (duration-start))}\n' for i in range(duration + 1))
                    write(Path(str(prefix) + '_progress.csv'), progress)
                    write(Path(str(prefix) + '_cwnd.csv'), f'{flow},0,13800\n')
                    rtt = ''.join(f'{flow},{i * 100000000},{round((p95 if i >= 1909 else low) * 1e6)}\n' for i in range(duration * 10))
                    write(Path(str(prefix) + '_rtt.csv'), rtt)
                    write(Path(str(prefix) + '_extra_bins.csv'), 'start_s,data_tx_packets,data_tx_payload_bytes,retransmissions,retransmitted_payload_bytes\n'
                          + f'{start},{tx if flow == 0 else 0},1380000,{retx if flow == 0 else 0},0\n')
                    write(Path(str(prefix) + '_retransmissions.csv'), 'time_ns,sequence,payload_bytes\n'
                          + ''.join(f'{start*1000000000+1000000},{i*1380},1380\n' for i in range(retx if flow == 0 else 0)))
                    write(Path(str(prefix) + '_cong_state.csv'), 'time_ns,old_state,new_state\n')
                write(logs / 'network_queue_bins.csv',
                      'start_s,end_s,total_queued_mean_packets,max_single_queue_packets,queue_drops,tc_drops,total_buffer_drops\n'
                      + ''.join(f'{i},{i+1},{queued},{peak},{drops if i == start else 0},0,{drops if i == start else 0}\n' for i in range(duration)))
                write(logs / 'queue_devices.csv', 'node,device,type,mean_packets,peak_packets,queue_drops\n0,0,synthetic,0,0,0\n')
                write(logs / 'queue_drop_events.csv', 'time_ns,node,device,payload_bytes\n')
                write(logs / 'tc_drop_events.csv', 'time_ns,node,payload_bytes\n')
                write(logs / 'finished.txt', 'Yes\n')
                console = f'VEGAS_CONFIG,window_s={window},trace=1,adaptive={int(adaptive)}\nVEGAS_QUEUE_BINDINGS,10\n'
                console += ''.join(f'VEGAS_FLOW_BINDING,{i}\n' for i in range(load))
                console += f'VEGAS_DECISION,1000000000,{nsat},0x1,{window*1000000000},80000000,80000000,81000000,100,2,50\n'
                if adaptive:
                    console += f'VEGAS_ADAPTIVE_RESET,2000000000,{nsat},0x1,80000000,84000000\n'
                write(directory / 'out.txt', console)
                for name, value in runner.input_text(directory, root / 'synthetic-state', nsat, load, duration).items():
                    write(directory / name, value)
                common.write_json(directory / 'evaluation.json', spec)
                retained = [directory / 'out.txt', directory / 'config_ns3.properties', directory / 'schedule.csv'] + list(logs.iterdir())
                common.write_json(directory / 'EVALUATION_COMPLETE.json', dict(spec=spec, wall_seconds=1,
                    executable_sha256='synthetic-binary', output_sha256={p.relative_to(directory).as_posix(): common.sha(p) for p in retained}))

class MetricsTests(unittest.TestCase):
    def test_counter_boundaries_and_percentile(self):
        data = ([0, 20, 100, 200], [0, 1000, 2000, 3000])
        self.assertAlmostEqual(analysis.core.goodput(data, 20, 200), 2000 * 8 / 180 / 1e6)
        self.assertEqual(analysis.core.percentile(list(range(100)), .95), 94)
        self.assertIsNone(analysis.core.percentile([], .95))

    def test_compact_series_equal_to_original_convention(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'trace.csv'
            write(p, '0,0,1000\n0,100000000,2000\n0,100000000,3000\n')
            data = analysis.compact_series(p)
            self.assertEqual(analysis.core.at(data, .1), 3000)
            write(p, '0,100000000,1\n0,0,2\n')
            with self.assertRaisesRegex(ValueError, 'Nonmonotonic'):
                analysis.compact_series(p)

    def test_known_queue_integral_and_unequal_fairness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, ('dense',), ('original',), (5,), 5)
            case = root / 'dense_original_q1000_f5'
            logs = case / 'logs_ns3'
            write(logs / 'network_queue_bins.csv',
                  'start_s,end_s,total_queued_mean_packets,max_single_queue_packets,queue_drops,tc_drops,total_buffer_drops\n'
                  + ''.join(f'{i},{i+1},{2*i},20,0,0,0\n' for i in range(5)))
            for i in range(5):
                write(logs / f'tcp_flow_{i}_progress.csv', f'{i},0,0\n{i},5000000000,{(i+1)*1000000}\n')
            r, _, _ = analysis.core.analyze_case(case, 0, 2)
            self.assertEqual(r['mean_total_queued_packets'], 4)
            self.assertAlmostEqual(r['jain_fairness'], 15**2 / (5 * 55))
            for i in range(5):
                write(logs / f'tcp_flow_{i}_progress.csv', f'{i},0,0\n{i},5000000000,0\n')
            r, _, _ = analysis.core.analyze_case(case, 0, 2)
            self.assertIsNone(r['jain_fairness'])

class IntegrationTests(unittest.TestCase):
    def test_30_case_analysis_validation_report_exports(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp) / 'synthetic'
            fixture(root)
            rows = analysis.analyze(root)
            self.assertEqual(len(rows), 30)
            result = validate_matched.validate(root)
            self.assertEqual(result['per_flow_rows'], 90)
            self.assertEqual(result['archived_controls_checked'], 12)
            # Explicit original selection: adaptive also has window_s=0.
            a = next(r for r in rows if r['scenario'] == 'dense' and r['variant'] == 'adaptive' and r['flows'] == 1)
            self.assertAlmostEqual(a['improvement_vs_matched_original_percent'], 100*(60/12.414602666666665-1))
            write_report_section.write_report(root)
            self.assertIn('V-C2', (root / 'analysis/section_V_C2.md').read_text(encoding='utf-8'))
            for panel in [write_report_section.render_table(common.rows(root / 'analysis/summary.csv'), n) for n in [1, 5]]:
                widths = {len(line.split('|')) for line in panel.splitlines() if line.startswith('|')}
                self.assertEqual(len(widths), 1)
            targets = package_matched.package(root, True)
            with ZipFile(targets[0]) as z:
                self.assertFalse(any(n.endswith('_progress.csv') for n in z.namelist()))
                self.assertTrue(any(n.endswith('ARCHIVE_SHA256.json') for n in z.namelist()))
            with ZipFile(targets[1]) as z:
                self.assertEqual(sum(n.endswith('_progress.csv') for n in z.namelist()), 90)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                package_matched.package(root, True)

    def test_tampered_raw_evidence_and_missing_observers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, ('dense',), ('original',), (1,), 5)
            case = root / 'dense_original_q1000_f1'
            common.verify_receipt(case)
            write(case / 'logs_ns3/tcp_flow_0_progress.csv', '0,0,0\n')
            with self.assertRaisesRegex(ValueError, 'retained output changed'):
                common.verify_receipt(case)
            write(case / 'out.txt', 'VEGAS_CONFIG,window_s=0,trace=1,adaptive=0\nVEGAS_QUEUE_BINDINGS,0\n')
            with self.assertRaisesRegex(ValueError, 'did not bind'):
                common.validate_outputs(case, common.read_json(case / 'evaluation.json'))

    def test_incomplete_report_refused(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            fixture(root, ('dense',), ('original', 'adaptive'), (1, 5), 5)
            analysis.analyze(root, 0, 2)
            validate_matched.validate(root, 4)
            with self.assertRaisesRegex(ValueError, 'Expected 30'):
                write_report_section.write_report(root)

    def test_twelve_control_gate_and_regression_failure(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            fixture(root, variants=('original', 'refresh1', 'refresh5', 'refresh10'), loads=(1,))
            analysis.analyze(root)
            result = validate_matched.validate(root, 12, controls_only=True)
            self.assertEqual(result['archived_controls_checked'], 12)
            self.assertFalse(result['full_matrix'])
            # Change a raw counter, update its receipt, and regenerate analysis:
            # the evidence is internally consistent but no longer reproduces controls.
            case = root / 'dense_original_q1000_f1'
            p = case / 'logs_ns3/tcp_flow_0_progress.csv'
            lines = p.read_text().splitlines()
            final = lines[-1].split(',')
            final[2] = str(int(final[2]) + 1000000)
            lines[-1] = ','.join(final)
            write(p, '\n'.join(lines) + '\n')
            receipt = common.read_json(case / 'EVALUATION_COMPLETE.json')
            receipt['output_sha256'][p.relative_to(case).as_posix()] = common.sha(p)
            common.write_json(case / 'EVALUATION_COMPLETE.json', receipt)
            analysis.analyze(root)
            with self.assertRaisesRegex(ValueError, 'Archived control mismatch'):
                validate_matched.validate(root, 12, controls_only=True)

    def test_input_schedule_and_manifest_hashes(self):
        inputs = runner.input_text(Path('/work/runs/case'), Path('/work/state'), 500, 5, 200)
        self.assertEqual([int(line.split(',')[4]) for line in inputs['schedule.csv'].splitlines()], [0, 1000000, 2000000, 3000000, 4000000])
        self.assertIn('set(0,1,2,3,4)', inputs['config_ns3.properties'])
        self.assertEqual(len(runner.text_hashes(inputs)), 2)

    def test_plot_exports(self):
        if importlib.util.find_spec('matplotlib') is None:
            self.skipTest('Install the locked plotting environment to test PNG/PDF exports')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            fixture(root, ('dense',), ('original', 'adaptive'), (1, 5), 5)
            analysis.analyze(root, 0, 2, True)
            self.assertEqual(len(list((root / 'analysis').glob('*.png'))), 3)
            self.assertEqual(len(list((root / 'analysis').glob('*.pdf'))), 3)
            for p in (root / 'analysis').glob('*.png'):
                self.assertTrue(p.read_bytes().startswith(b'\x89PNG'))
            validate_matched.validate(root, 4)

    def test_runner_dry_run_resume_retry_and_changed_input_refusal(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            ns3, lab, state = root / 'ns3', root / 'lab', root / 'state'
            for source in common.SOURCES:
                write(ns3 / source, 'synthetic source\n')
            for name in ['make_run.sh', 'run_sim.sh']:
                write(lab / 'scripts' / name, 'synthetic helper\n')
            state.mkdir()
            out = root / 'results'
            args = runner.parser().parse_args(['--scenarios', 'dense', '--variants', 'original', 'adaptive',
                     '--flows', '1', '5', '--duration', '5', '--dense-state', str(state), '--output', str(out), '--dry-run'])
            calls = []
            fail = [False]
            def fake_command(command, log, env, cwd=None):
                calls.append(str(command[1]))
                if str(command[1]).endswith('/ns3') or str(command[1]).endswith('\\ns3'):
                    write(ns3 / 'build/scratch/ns3.48-main_satnet-default', 'synthetic executable')
                elif Path(command[1]).name == 'make_run.sh':
                    directory = Path(command[2])
                    spec = common.read_json(directory / 'evaluation.json')
                    fixture(directory.parent, ('dense',), (spec['variant'],), (spec['flows'],), 5)
                    (directory / 'EVALUATION_COMPLETE.json').unlink()
                    common.write_json(directory / 'evaluation.json', spec)
                    for name, text in runner.input_text(directory, state, 2160, spec['flows'], 5).items():
                        write(directory / name, text)
                elif fail[0]:
                    fail[0] = False
                    raise ValueError('synthetic interruption')
                write(Path(log), 'synthetic console\n')
            fake_os = types.SimpleNamespace(environ=os.environ, name='posix', path=os.path,
                                            access=os.access, X_OK=os.X_OK)
            state_spec = dict(path=str(state), full_tree_sha256='synthetic-state', metadata_sha256={},
                              reference_routes_verified=True, route_events=[])
            with patch.dict(os.environ, NS3_DIR=str(ns3), LAB=str(lab)), \
                 patch.object(runner, 'install'), patch.object(runner, 'os', fake_os), \
                 patch.object(runner, 'check_state', return_value=state_spec), \
                 patch.object(runner, 'tree_digest', return_value='synthetic-state'), \
                 patch.object(runner, 'command', side_effect=fake_command):
                runner.run(args)
                self.assertFalse(out.exists())
                self.assertEqual(calls, [])
                args.dry_run = False
                fail[0] = True
                with self.assertRaisesRegex(ValueError, 'synthetic interruption'):
                    runner.run(args)
                self.assertFalse(list(out.glob('*/EVALUATION_COMPLETE.json')))
                with self.assertRaisesRegex(ValueError, 'requires --retry-incomplete'):
                    runner.run(args)
                args.retry_incomplete = True
                runner.run(args)
                self.assertEqual(len(list(out.glob('*/EVALUATION_COMPLETE.json'))), 4)
                self.assertEqual(len(list(out.glob('incomplete_*'))), 1)
                calls.clear()
                runner.run(args)
                self.assertEqual(len(calls), 1)  # Build check only; all cases skipped.
                write(ns3 / common.SOURCES[0], 'changed source\n')
                with self.assertRaisesRegex(ValueError, 'completed inputs differ'):
                    runner.run(args)

class InstallerTests(unittest.TestCase):
    def test_real_vegas_source_integration_and_backup(self):
        git = shutil.which('git')
        if not git:
            self.skipTest('git is required to reconstruct the recorded refresh fixture')
        repo = HERE.parents[2]
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp) / 'ns3'
            for name in ['tcp-vegas.cc', 'tcp-vegas.h']:
                target = root / 'src/internet/model' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo / '03_ADAPTIVE_IMPLEMENTATION' / name, target)
            subprocess.run([git, 'apply', '--reverse', '--ignore-space-change', '--ignore-whitespace', str(repo / '03_ADAPTIVE_IMPLEMENTATION/adaptive-vegas.patch')], cwd=root, check=True, capture_output=True)
            subprocess.run([git, 'apply', str(HERE / 'vendor/vegas-window.patch')], cwd=root, check=True, capture_output=True)
            expected = common.reference()['sources']
            for name in [installer.CC, installer.HH]:
                # Git on Windows can leave mixed CRLF/LF in patch fixtures;
                # recorded source hashes are the original Linux LF bytes.
                write(root / name, (root / name).read_text())
                self.assertEqual(common.sha(root / name), expected[name])
            write(root / installer.HELPER, (HERE / 'vendor/vegas-experiment.h').read_text())
            for name in expected:
                if not (root / name).exists():
                    write(root / name, 'synthetic observer fixture\n')
            write(root / 'VERSION', '3.48\n')
            local_expected = {name: common.sha(root / name) for name in expected}
            originals = {name: (root / name).read_bytes() for name in local_expected}
            with patch.object(installer, 'reference', return_value={'sources': local_expected}):
                installer.install(root, True)
                self.assertFalse((root / installer.DETECTOR).exists())
                installer.install(root)
                installer.install(root)
                self.assertEqual((root / installer.CC).read_text().count('VEGAS_ADAPTIVE_RESET,'), 1)
                self.assertIn('m_shiftCount(sock.m_shiftCount)', (root / installer.CC).read_text())
                self.assertIn('adaptive && seconds > 0.0', (root / installer.HELPER).read_text())
                marker = common.read_json(root.parent / 'ns3-matched-install.json')
                for name in [installer.CC, installer.HH, installer.HELPER]:
                    self.assertEqual((Path(marker['backup']) / name).read_bytes(), originals[name])
                self.assertEqual((root / 'scratch/main_satnet/main_satnet.cc').read_bytes(), originals['scratch/main_satnet/main_satnet.cc'])
                write(root / installer.CC, 'changed\n')
                with self.assertRaisesRegex(ValueError, 'Installed source changed'):
                    installer.install(root)

    def test_detector_production_cpp_boundaries(self):
        compiler = shutil.which('g++') or shutil.which('clang++')
        compile_command = [compiler] if compiler else ([sys.executable, '-m', 'ziglang', 'c++']
                                                     if importlib.util.find_spec('ziglang') else None)
        if not compile_command:
            self.skipTest('C++ compiler unavailable; run this test in the Linux course VM')
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / ('detector.exe' if os.name == 'nt' else 'detector')
            compiler_env = os.environ.copy()
            compiler_env.update(ZIG_GLOBAL_CACHE_DIR=str(Path(tmp) / 'zig-global'),
                                ZIG_LOCAL_CACHE_DIR=str(Path(tmp) / 'zig-local'))
            result = subprocess.run(compile_command + ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(HERE),
                            str(HERE / 'tests/detector_test.cc'), '-o', str(binary)],
                            env=compiler_env, capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            subprocess.run([str(binary)], check=True)

class StateTests(unittest.TestCase):
    def test_supplied_500_state_hash_and_verified_route_events(self):
        archive = Path.home() / 'Downloads/Telegram Desktop/Vegas_500_AllInOne.zip'
        if not archive.is_file():
            self.skipTest('Optional original 500 input ZIP is not present at the development location')
        with tempfile.TemporaryDirectory() as tmp, ZipFile(archive) as z:
            state = Path(tmp) / 'state'
            prefix = 'Vegas_500_AllInOne/state500/state/'
            for name in z.namelist():
                if name.startswith(prefix) and not name.endswith('/'):
                    relative = Path(name[len(prefix):])
                    self.assertNotIn('..', relative.parts)
                    target = state / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(name))
            verified = common.check_state(state, 'sat500')
            self.assertEqual(verified['full_tree_sha256'], common.reference()['states']['sat500']['state_sha256'])
            self.assertTrue(verified['reference_routes_verified'])
            self.assertTrue(any(abs(e['time_s'] - 163.8) < 1e-8 for e in verified['route_events']))
            write(state / 'dynamic_state_100ms_for_200s/fstate_0.txt', 'changed\n')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                common.check_state(state, 'sat500')

if __name__ == '__main__':
    unittest.main()
