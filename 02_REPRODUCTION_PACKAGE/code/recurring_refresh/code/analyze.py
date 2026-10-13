#!/usr/bin/env python3
"""Recompute metrics from raw traces or validated compact 1 s / 100 ms traces."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from analysis_core import extract_vegas

def read(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))

def write(p,rows,fields=None):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def sample(p,grid,flow,initial=0,monotonic=False):
    """Right-continuous sampling with same-time last-event semantics; bounded memory."""
    out=[];i=0;last=initial;prev_t=-1;prev_v=None
    with p.open(newline='') as f:
        for row in csv.reader(f):
            if not row:continue
            fid,t,v=map(int,row)
            if fid!=flow or t<prev_t or v<0 or (monotonic and prev_v is not None and v<prev_v):raise ValueError(f'Invalid trace: {p}')
            while i<len(grid) and grid[i]<t:out.append(last);i+=1
            last=v;prev_t=t;prev_v=v
    return out+[last]*(len(grid)-len(out))

def number(v):return None if v in (None,'') else float(v)
def avg(values):
    good=[x for x in values if x is not None and math.isfinite(x)]
    return statistics.mean(good) if good else None

def summarize(run,start=20,late=60):
    receipt=json.loads((run/'EVALUATION_COMPLETE.json').read_text());spec=receipt['spec']
    duration=spec['duration_s'];flows=spec['flows'];logs=run/'logs_ns3'
    if not 0<=start<duration:raise ValueError(f'{run}: measurement start outside run.')
    raw=all((logs/f'tcp_flow_{i}_progress.csv').is_file() and (logs/f'tcp_flow_{i}_rtt.csv').is_file() for i in range(flows))
    per_flow=[];all_rtt=[]
    if raw:
        goodput=[0.]*duration;cwnd=[0.]*(10*duration);rtts=[[] for _ in cwnd];flow_samples=[]
        for flow in range(flows):
            prefix=logs/f'tcp_flow_{flow}'
            ack=sample(Path(str(prefix)+'_progress.csv'),[int(i*1e9) for i in range(duration+1)],flow,monotonic=True)
            rr=sample(Path(str(prefix)+'_rtt.csv'),[i*100000000 for i in range(duration*10)],flow,None)
            ww=sample(Path(str(prefix)+'_cwnd.csv'),[i*100000000 for i in range(duration*10)],flow)
            per_flow.append(dict(run=run.name,flow=flow,goodput_mbps=(ack[-1]-ack[start])*8/((duration-start)*1e6)))
            for i in range(duration):goodput[i]+=(ack[i+1]-ack[i])*8/1e6
            for i in range(duration*10):
                cwnd[i]+=ww[i]/1380
                value=rr[i]/1e6 if rr[i] is not None else None
                if value is not None:rtts[i].append(value)
                if i>=start*10 and value is not None:all_rtt.append(value)
                flow_samples.append(dict(time_s=i/10,flow=flow,srtt_ms=value))
        write(run/'flow_samples_100ms.csv',flow_samples)
        fast=[dict(time_s=i/10,total_cwnd_segments=cwnd[i],mean_flow_srtt_ms=avg(rtts[i])) for i in range(duration*10)]
        if (run/'out.txt').is_file():base,current,diff=extract_vegas(run,duration)
        else:base=current=diff=[None]*duration
        queue=read(logs/'network_queue_bins.csv') if (logs/'network_queue_bins.csv').is_file() else []
        extras=[r for f in range(flows) for r in read(logs/f'tcp_flow_{f}_extra_bins.csv')] if (logs/'tcp_flow_0_extra_bins.csv').is_file() else []
        slow=[]
        for i in range(duration):
            q=queue[i] if queue else {}
            slow.append(dict(start_s=i,acked_goodput_mbps=goodput[i],effective_base_ms=base[i],cycle_min_ms=current[i],mean_diff_packets=diff[i],
                total_queued_mean_packets=q.get('total_queued_mean_packets'),max_single_queue_packets=q.get('max_single_queue_packets'),total_buffer_drops=q.get('total_buffer_drops'),
                data_retransmissions=sum(int(x['retransmissions']) for x in extras if int(x['start_s'])==i) if extras else None))
        write(run/'timeseries_1s.csv',slow);write(run/'timeseries_100ms.csv',fast)
    else:
        slow=read(run/'timeseries_1s.csv');fast=read(run/'timeseries_100ms.csv')
        if flows!=1 and not (run/'flow_samples_100ms.csv').is_file():raise ValueError('Compact multi-flow case needs per-flow RTT samples.')
        if (run/'flow_samples_100ms.csv').is_file():
            all_rtt=[float(r['srtt_ms']) for r in read(run/'flow_samples_100ms.csv') if start<=float(r['time_s'])<duration and r['srtt_ms']!='']
        else:all_rtt=[float(r['mean_flow_srtt_ms']) for r in fast if start<=float(r['time_s'])<duration and r['mean_flow_srtt_ms']!='']
        if flows==1:per_flow=[dict(run=run.name,flow=0,goodput_mbps=avg([float(r['acked_goodput_mbps']) for r in slow if start<=float(r['start_s'])<duration]))]
        else:per_flow=read(run/'per_flow.csv')
    if [float(r['start_s']) for r in slow]!=list(range(duration)):raise ValueError(f'Missing 1 s bins: {run}')
    if len(fast)!=duration*10:raise ValueError(f'Missing 100 ms samples: {run}')
    if [float(r['time_s']) for r in fast]!=[i/10 for i in range(duration*10)]:raise ValueError(f'Invalid 100 ms sample grid: {run}')
    qrows=read(logs/'network_queue_bins.csv') if (logs/'network_queue_bins.csv').is_file() else []
    if qrows and ([float(r['start_s']) for r in qrows]!=list(range(duration)) or [float(r['end_s']) for r in qrows]!=list(range(1,duration+1))):
        raise ValueError(f'Missing or invalid queue bins: {run}')
    qs=[r for r in qrows if start<=float(r['start_s']) and float(r['end_s'])<=duration]
    extra=[r for f in range(flows) for r in read(logs/f'tcp_flow_{f}_extra_bins.csv')] if (logs/'tcp_flow_0_extra_bins.csv').is_file() else []
    es=[r for r in extra if start<=float(r['start_s'])<duration]
    tx=sum(int(r['data_tx_packets']) for r in es) if extra else None
    retx=sum(int(r['retransmissions']) for r in es) if extra else None
    all_rtt.sort();rates=[float(r['goodput_mbps']) for r in per_flow];denom=flows*sum(r*r for r in rates)
    row={k:spec[k] for k in ('satellites','tcp','window_s','rate_mbps','queue_packets','flows','duration_s')}
    row.update(run=run.name,measurement_start_s=start,goodput_mbps=avg([float(r['acked_goodput_mbps']) for r in slow if start<=float(r['start_s'])<duration]),
        measurement_end_s=duration,whole_goodput_mbps=avg([float(r['acked_goodput_mbps']) for r in slow]),late_start_s=late,
        late_goodput_mbps=avg([float(r['acked_goodput_mbps']) for r in slow if late<=float(r['start_s'])<duration]),
        mean_sampled_srtt_ms=avg(all_rtt),p95_sampled_srtt_ms=all_rtt[math.ceil(.95*len(all_rtt))-1] if all_rtt else None,
        mean_total_queued_packets=sum(float(r['total_queued_mean_packets'])*(float(r['end_s'])-float(r['start_s'])) for r in qs)/(duration-start) if qrows else None,
        max_single_queue_packets=max(int(r['max_single_queue_packets']) for r in qs) if qrows else None,
        queue_drops=sum(int(r['queue_drops']) for r in qs) if qrows else None,
        tc_drops=sum(int(r['tc_drops']) for r in qs) if qrows else None,
        total_buffer_drops=sum(int(r['total_buffer_drops']) for r in qs) if qrows else None,
        data_tx_packets=tx,data_retransmissions=retx,data_retransmission_percent=100*retx/tx if tx else None,
        jain_fairness=sum(rates)**2/denom if denom else None,wall_seconds=receipt.get('wall_seconds'),
        provenance=receipt.get('provenance','fresh unified runner'),improvement_vs_original_percent=None)
    decisions=run/'vegas_decision.csv'
    if decisions.is_file():
        for v in read(decisions):
            w=int(v['cwnd_segments']);b=int(v['effective_base_ns']);r=int(v['min_rtt_ns'])
            # ns-3 computes in floating point; integer comparison is exact except boundary rounding.
            predicted=w-math.floor(w*(b/r))
            if abs(predicted-int(v['diff_packets']))>1:raise ValueError(f'Inconsistent Vegas decision at {v["time_ns"]}')
    write(run/'per_flow.csv',per_flow)
    return row

def analyze_paths(root,out):
    events=[];connectivity=[]
    for file in sorted((root/'paths').glob('path_*.csv')):
        n=int(file.stem.split('_')[-1]);rows=read(file);connected=[r for r in rows if r['rtt_prop_ms']!='']
        connectivity.append(dict(satellites=n,samples=len(rows),connected_fraction=len(connected)/len(rows),unreachable_seconds=.1*(len(rows)-len(connected)),
            min_propagation_rtt_ms=min(float(r['rtt_prop_ms']) for r in connected),max_propagation_rtt_ms=max(float(r['rtt_prop_ms']) for r in connected)))
        for i,r in enumerate(rows):
            if i and r['path_changed']=='1' and r['rtt_prop_ms'] and rows[i-1]['rtt_prop_ms']:
                events.append(dict(satellites=n,time_s=r['t_s'],rtt_before_ms=rows[i-1]['rtt_prop_ms'],rtt_after_ms=r['rtt_prop_ms'],delta_ms=float(r['rtt_prop_ms'])-float(rows[i-1]['rtt_prop_ms']),hops_fwd=r['hops_fwd']))
    if events:write(out/'route_events.csv',events)
    if connectivity:write(out/'connectivity.csv',connectivity)

def analyze_events(root,out):
    """Exact subsecond intervals need raw progress or the original derived event CSV."""
    events=[];decisions=[]
    for w in (0,1,5,10):
        run=root/'runs'/f'sat500_vegas{w}_r100_q1000_f1'
        if not run.exists():continue
        receipt=json.loads((run/'EVALUATION_COMPLETE.json').read_text())
        if receipt['spec']['duration_s']!=200:continue
        progress=run/'logs_ns3/tcp_flow_0_progress.csv'
        if progress.is_file():
            times=[153.8,163.8,173.8,192.5]
            ack=sample(progress,[round(t*1e9) for t in times],0,monotonic=True)
            for i,label in enumerate(('before','first 10 s after','later on longer route')):
                events.append(dict(case=f'vegas{w}',interval=label,start_s=times[i],end_s=times[i+1],goodput_mbps=(ack[i+1]-ack[i])*8/((times[i+1]-times[i])*1e6),basis='raw cumulative ACK trace'))
        p=run/'vegas_decision.csv'
        if p.is_file():
            rows=read(p)
            for t in (163.7,168.8,183.8):
                before=[r for r in rows if int(r['time_ns'])<=round(t*1e9)]
                if before:decisions.append(dict(case=f'vegas{w}',requested_time_s=t,**before[-1]))
    historical=root/'archived_event_windows_500.csv'
    if historical.is_file():
        for row in read(historical):
            if row['case'] in ('vegas0','vegas1','vegas5','vegas10') and not any(r['case']==row['case'] and r['interval']==row['interval'] for r in events):
                events.append(dict(row,basis='supplied derived CSV; original subsecond progress absent from compact archive'))
    if events:write(out/'event_windows_500.csv',events)
    if decisions:write(out/'decision_examples.csv',decisions)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--start',type=int,default=20);p.add_argument('--no-plots',action='store_true');a=p.parse_args()
    root=a.root.resolve();out=root/'analysis';out.mkdir(exist_ok=True)
    rows=[]
    for marker in sorted((root/'runs').glob('*/EVALUATION_COMPLETE.json')):
        row=summarize(marker.parent,a.start);rows.append(row);print(row['run'],f"{row['goodput_mbps']:.6f} Mbps",flush=True)
    if not rows:raise SystemExit('No completed cases under root/runs/. Use import_results.py for old packages.')
    for row in rows:
        if row['tcp']!='TcpVegas':continue
        b=next((r for r in rows if r['tcp']=='TcpVegas' and r['window_s']==0 and all(r[k]==row[k] for k in ('satellites','queue_packets','flows','rate_mbps','duration_s'))),None)
        if b and b['goodput_mbps']>0:row['improvement_vs_original_percent']=100*(row['goodput_mbps']/b['goodput_mbps']-1)
    write(out/'summary.csv',rows);analyze_paths(root,out);analyze_events(root,out)
    write(out/'goodput_windows.csv',[dict(run=r['run'],satellites=r['satellites'],window_s=r['window_s'],duration_s=r['duration_s'],
        whole_start_s=0,whole_goodput_mbps=r['whole_goodput_mbps'],measurement_start_s=r['measurement_start_s'],goodput_mbps=r['goodput_mbps'],
        late_start_s=r['late_start_s'],late_goodput_mbps=r['late_goodput_mbps']) for r in rows])
    if not a.no_plots:
        from figures import generate
        generate(root,rows,out)
    print('Wrote',out)

if __name__=='__main__':main()
