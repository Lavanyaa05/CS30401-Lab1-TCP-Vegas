#!/usr/bin/env python3
"""Summarize completed evaluation cases and optionally plot them with matplotlib."""
import argparse
import bisect
import csv
import json
import math
from pathlib import Path
from collections import defaultdict

def csv_rows(path):
    with path.open() as f: return list(csv.DictReader(f))

def series(path, divisor=1.0):
    points=[]
    with path.open() as f:
        for row in csv.reader(f):
            if row: points.append((int(row[1])/1e9, int(row[2])/divisor))
    points.sort(key=lambda x:x[0])
    return [p[0] for p in points],[p[1] for p in points]

def at(data,t,default=0):
    times,values=data
    index=bisect.bisect_right(times,t)-1
    return values[index] if index>=0 else default

def goodput(data,start,end):
    return (at(data,end)-at(data,start))*8/(end-start)/1e6

def percentile(values,q):
    if not values: return None
    return sorted(values)[max(0,math.ceil(q*len(values))-1)]

def mean(values):
    return sum(values)/len(values) if values else None

def write_csv(path,rows,fields=None):
    if not rows and fields is None: return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def extract_vegas(run,duration):
    fields=['time_ns','context','object','window_ns','base_ns','effective_base_ns','min_rtt_ns',
            'cwnd_segments','diff_packets','ssthresh_segments']
    per_second=defaultdict(list)
    target=run/'vegas_decision.csv'
    with target.open('w',newline='') as out,(run/'out.txt').open(errors='replace') as inp:
        w=csv.writer(out);w.writerow(fields)
        for line in inp:
            if not line.startswith('VEGAS_DECISION,'):continue
            row=line.strip().split(',')[1:]
            if len(row)!=len(fields):raise ValueError('Malformed Vegas decision line')
            w.writerow(row)
            second=int(row[0])//1000000000
            per_second[second].append([int(row[5])/1e6,int(row[6])/1e6,int(row[8])])
    def values(col):
        return [mean([r[col] for r in per_second[i]]) if per_second[i] else math.nan for i in range(duration)]
    return values(0),values(1),values(2)

def analyze_case(run,start,late):
    receipt=json.loads((run/'EVALUATION_COMPLETE.json').read_text())
    spec=receipt['spec'];duration=spec['duration_s'];logs=run/'logs_ns3'
    if not 0<=start<duration:raise ValueError(f'{run.name}: start must be below duration (use --start 0 for smoke runs).')
    q=csv_rows(logs/'network_queue_bins.csv')
    if len(q)!=duration:raise ValueError('Missing queue bins; only whole-second duration supported.')
    progress=[];cw=[];rtt=[];extras=[];flow_rates=[]
    for flow in range(spec['flows']):
        prefix=logs/f'tcp_flow_{flow}'
        pr=series(Path(str(prefix)+'_progress.csv'));progress.append(pr)
        cw.append(series(Path(str(prefix)+'_cwnd.csv'),1380))
        rtt.append(series(Path(str(prefix)+'_rtt.csv'),1e6))
        extras.extend(csv_rows(Path(str(prefix)+'_extra_bins.csv')))
        flow_rates.append(goodput(pr,start,duration))
    selected=[row for row in q if float(row['start_s'])>=start and float(row['end_s'])<=duration]
    tx=sum(int(row['data_tx_packets']) for row in extras if start<=int(row['start_s'])<duration)
    retrans=sum(int(row['retransmissions']) for row in extras if start<=int(row['start_s'])<duration)
    samples=[at(data,i/10,None) for data in rtt for i in range(start*10,duration*10)]
    samples=[x for x in samples if x is not None]
    denom=sum(x*x for x in flow_rates)
    result=dict(run=run.name,scenario=spec['scenario'],window_s=spec['window_s'],queue_packets=spec['queue_packets'],
        flows=spec['flows'],duration_s=duration,measurement_start_s=start,
        goodput_mbps=sum(flow_rates),late_start_s=late,
        late_goodput_mbps=sum(goodput(pr,late,duration) for pr in progress) if late<duration else None,
        mean_sampled_srtt_ms=mean(samples),p95_sampled_srtt_ms=percentile(samples,.95),
        mean_total_queued_packets=sum(float(row['total_queued_mean_packets'])*(float(row['end_s'])-float(row['start_s'])) for row in selected)/(duration-start),
        max_single_queue_packets=max(int(row['max_single_queue_packets']) for row in selected),
        queue_drops=sum(int(row['queue_drops']) for row in selected),
        tc_drops=sum(int(row['tc_drops']) for row in selected),
        total_buffer_drops=sum(int(row['total_buffer_drops']) for row in selected),
        data_tx_packets=tx,data_retransmissions=retrans,data_retransmission_percent=100*retrans/tx if tx else None,
        jain_fairness=sum(flow_rates)**2/(len(flow_rates)*denom) if denom else None,
        wall_seconds=receipt['wall_seconds'],improvement_vs_matched_original_percent=None)
    base,minimum,diff=extract_vegas(run,duration)
    bin_tx=[0]*duration;bin_retx=[0]*duration
    for row in extras:
        sec=int(row['start_s'])
        if sec<duration:
            bin_tx[sec]+=int(row['data_tx_packets']);bin_retx[sec]+=int(row['retransmissions'])
    time=[i/10 for i in range(duration*10)]
    details=dict(time=time,cwnd=[sum(at(data,t) for data in cw) for t in time],
        srtt=[mean([v for data in rtt if (v:=at(data,t,None)) is not None]) for t in time],
        seconds=list(range(duration)),goodput=[sum(goodput(pr,i,i+1) for pr in progress) for i in range(duration)],
        base=base,minimum=minimum,diff=diff,
        queued=[float(row['total_queued_mean_packets']) for row in q],
        drops=[int(row['total_buffer_drops']) for row in q],retx=bin_retx)
    per_flow=[dict(run=run.name,flow=i,goodput_mbps=rate) for i,rate in enumerate(flow_rates)]
    write_csv(run/'timeseries_100ms.csv',[
        dict(time_s=t,total_cwnd_segments=details['cwnd'][i],mean_flow_srtt_ms=details['srtt'][i])
        for i,t in enumerate(time)])
    write_csv(run/'timeseries_1s.csv',[
        dict(start_s=i,acked_goodput_mbps=details['goodput'][i],
             effective_base_ms=base[i],cycle_min_ms=minimum[i],mean_diff_packets=diff[i],
             total_queued_mean_packets=details['queued'][i],
             max_single_queue_packets=int(q[i]['max_single_queue_packets']),
             total_buffer_drops=details['drops'][i],data_retransmissions=bin_retx[i])
        for i in range(duration)])
    return result,details,per_flow

def plots(groups,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={0:'#444444',1:'#21918c',5:'#386cb0',10:'#984ea3'}
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    for key,cases in groups.items():
        fig,axes=plt.subplots(4,2,figsize=(13,12),sharex=True,layout='constrained')
        for row,d in sorted(cases,key=lambda x:x[0]['window_s']):
            w=row['window_s'];label='Original' if w==0 else f'T={w:g} s';color=colors.get(w)
            xs=[i+.5 for i in d['seconds']]
            for ax,x,y in [(axes[0,0],xs,d['goodput']),(axes[0,1],d['time'],d['cwnd']),
                           (axes[1,0],d['time'],d['srtt']),(axes[1,1],xs,d['base']),
                           (axes[2,0],xs,d['diff']),(axes[2,1],xs,d['queued']),
                           (axes[3,0],xs,d['drops']),(axes[3,1],xs,d['retx'])]:
                ax.plot(x,y,label=label,color=color,linewidth=1.1)
        labels=['ACKed goodput (Mbit/s)','Total cwnd (segments)','Mean across flows: SRTT (ms)',
                'Mean effective BaseRTT per decision (ms)','Mean diff per Vegas decision (packets)',
                'Time-mean total queued packets','Buffer / flow-control drops per second','Data retransmissions / second']
        for ax,label in zip(axes.flat,labels):
            ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,cases[0][0]['duration_s']);ax.legend(fontsize=8)
            event=39.9 if key[0]=='dense' else 121.6
            if event<cases[0][0]['duration_s']:ax.axvline(event,ls='--',color='#b87333',alpha=.65)
        axes[2,0].axhline(4,ls=':',color='black',alpha=.6)
        for ax in axes[-1]:ax.set_xlabel('Simulation time (s)')
        name=f'{key[0]}_q{key[1]}_f{key[2]}'
        fig.suptitle(f'Vegas comparison: {name} | matched links, traffic and duration',fontsize=13)
        fig.savefig(out/f'{name}.png',dpi=160);fig.savefig(out/f'{name}.pdf');plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('--start',type=int,default=20)
    p.add_argument('--late-start',type=int,default=60)
    p.add_argument('--plots',action='store_true')
    a=p.parse_args();root=a.root.expanduser().resolve();out=root/'analysis';out.mkdir(parents=True,exist_ok=True)
    cases=sorted(root.glob('*/EVALUATION_COMPLETE.json'))
    if not cases:raise SystemExit('No completed evaluation runs found.')
    results=[];groups=defaultdict(list);flows=[]
    for file in cases:
        row,d,perflow=analyze_case(file.parent,a.start,a.late_start)
        results.append(row);groups[(row['scenario'],row['queue_packets'],row['flows'])].append((row,d));flows+=perflow
        print(f"{row['run']}: {row['goodput_mbps']:.4f} Mbit/s, {row['total_buffer_drops']} buffer/flow-control drops, {row['data_retransmissions']} retransmissions")
    for group in groups.values():
        baseline=next((r for r,d in group if r['window_s']==0),None)
        if baseline and baseline['goodput_mbps']>0:
            for row,d in group:
                if row['duration_s']!=baseline['duration_s']:raise ValueError('Unequal matched durations')
                row['improvement_vs_matched_original_percent']=100*(row['goodput_mbps']/baseline['goodput_mbps']-1)
    write_csv(out/'summary.csv',results);write_csv(out/'per_flow.csv',flows)
    if a.plots:plots(groups,out)
    print('Saved:',out/'summary.csv')
    print('Queue means are summed across monitored devices, NOT divided by idle satellite queues.')
    print('Data retransmission percentage is retransmission events / data Tx events, NOT network loss probability.')
    print('SRTT percentiles use 100 ms time sampling and include defined samples from every flow.')
    print('Internal decision averages are cycle/event averages, not time-weighted averages.')

if __name__=='__main__':main()
