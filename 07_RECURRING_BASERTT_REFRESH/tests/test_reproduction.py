"""Regression checks for analysis, input protection and runner orchestration.
Synthetic fixtures below test control flow only; they are never experimental results.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CODE=Path(__file__).resolve().parents[1]/'code'
sys.path.insert(0,str(CODE))
import experiments as runner
import analyze
import reproduce_reference

class RegressionTests(unittest.TestCase):
    def test_matrix_and_node_ids(self):
        cases=runner.plan(argparse.Namespace(satellites=[500,1584,2160],windows=[0,1,5,10],duration=200))
        self.assertEqual(len(cases),12)
        self.assertEqual({(s['satellites'],s['window_s']) for s in cases},{(n,w) for n in (500,1584,2160) for w in (0,1,5,10)})
        for s in cases:
            self.assertEqual(s['src'],s['satellites']);self.assertEqual(s['dst'],s['satellites']+1)
            self.assertEqual(s['orbits']*s['satellites_per_orbit'],s['satellites'])
            self.assertFalse(s['pacing'])

    def test_duplicate_timestamp_and_monotonic_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'trace.csv';p.write_text('0,0,0\n0,100,10\n0,100,20\n0,200,30\n')
            self.assertEqual(analyze.sample(p,[0,99,100,200],0,monotonic=True),[0,0,20,30])
            p.write_text('0,0,20\n0,100,10\n')
            with self.assertRaises(ValueError):analyze.sample(p,[0,100],0,monotonic=True)

    def test_source_evidence_checksums(self):
        reproduce_reference.verify_evidence()

    def test_protected_output(self):
        for root in [CODE,CODE.parent,CODE.parent/'reference',CODE.parent/'reference'/'runs']:
            with self.assertRaises(ValueError):runner.validate_output(root)
        runner.validate_output(CODE.parent/'generated')

    def test_reject_changed_source_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'ns3').touch();q=p/'src/internet/model';q.mkdir(parents=True)
            f=q/'tcp-vegas.cc';f.write_text('adaptive or otherwise modified implementation\n')
            before=f.read_bytes()
            with self.assertRaisesRegex(ValueError,'Baseline source differs'):runner.install(p)
            self.assertEqual(before,f.read_bytes())

    def test_full_matrix_resume_and_partial_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'generated';ns3=root/'ns3';ns3.mkdir()
            launched=[]
            def fake_state(n, *_):return root/f'state{n}',f'state-sha-{n}'
            def fake_call(argv,log=None,env=None,cwd=None):
                args=list(map(str,argv))
                if args[1].endswith('make_run.sh'):
                    run=Path(args[2]);(run/'config_ns3.properties').write_text('fixture=true\n')
                elif args[1].endswith('run_sim.sh'):
                    run=Path(args[2]);spec=json.loads((run/'evaluation.json').read_text());logs=run/'logs_ns3';logs.mkdir()
                    launched.append((spec['satellites'],int(env['VEGAS_WINDOW_S'])))
                    self.assertEqual(env['FLOWS'],f"{spec['src']}>{spec['dst']}")
                    self.assertEqual(env['PACING'],'false')
                    (run/'out.txt').write_text(f"VEGAS_QUEUE_BINDINGS,fixture\nVEGAS_CONFIG,window_s={spec['window_s']},trace=1\n")
                    (logs/'finished.txt').write_text('Yes\n')
                    (logs/'queue_devices.csv').write_text('fixture\n')
                    for name in ['queue_drop_events.csv','tc_drop_events.csv','tcp_flow_0_retransmissions.csv','tcp_flow_0_cong_state.csv']:
                        (logs/name).write_text('fixture\n')
                    (logs/'network_queue_bins.csv').write_text('start_s,end_s,total_queued_mean_packets,max_single_queue_packets,queue_drops,tc_drops,total_buffer_drops\n0,1,0,0,0,0,0\n1,2,0,0,0,0,0\n')
                    (logs/'tcp_flow_0_extra_bins.csv').write_text('start_s,end_s,data_tx_packets,retransmissions\n0,1,10,0\n1,2,10,0\n')
                    (logs/'tcp_flow_0_progress.csv').write_text('0,0,0\n0,1000000000,13800\n0,1999999999,27600\n')
                    (logs/'tcp_flow_0_cwnd.csv').write_text('0,0,13800\n')
                    (logs/'tcp_flow_0_rtt.csv').write_text('0,0,80000000\n')
                elif args[1].endswith('analyze.py'):
                    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
                # build is intentionally mocked; this test never claims ns-3 compilation.
            argv=['experiments.py','run','--duration','2','--output',str(out),'--ns3',str(ns3),'--no-plots']
            with patch.object(runner,'install'),patch.object(runner,'prepare_state',side_effect=fake_state),patch.object(runner,'source_hashes',return_value={'fixture':'hash'}),patch.object(runner,'call',side_effect=fake_call),patch.object(sys,'argv',argv):
                runner.main();self.assertEqual(len(launched),12)
                runner.main();self.assertEqual(len(launched),12)
                run=out/'runs'/'sat500_vegas1_r100_q1000_f1';(run/'EVALUATION_COMPLETE.json').unlink()
                with self.assertRaisesRegex(ValueError,'Incomplete run'):runner.main()
                with patch.object(sys,'argv',argv+['--retry-incomplete']):runner.main()
                self.assertEqual(len(launched),13)
                self.assertEqual(len(list((out/'incomplete').glob('*'))),1)
                receipt=run/'EVALUATION_COMPLETE.json';data=json.loads(receipt.read_text());data['spec']['duration_s']=200;receipt.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,'Completed inputs differ'):runner.main()
            with (out/'analysis/summary.csv').open() as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),12)
            self.assertTrue(all(abs(float(r['goodput_mbps'])-.1104)<1e-10 for r in rows))

if __name__=='__main__':unittest.main()
