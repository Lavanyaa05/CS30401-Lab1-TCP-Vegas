"""Figures generated exclusively from the measured CSVs passed to the analyzer."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS={0:'#b54945',1:'#09847f',5:'#3f6db5',10:'#9251a8'}
LABELS={0:'Original',1:'1 s history',5:'5 s history',10:'10 s history'}

def read(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def xy(rows,x,y):
    return [float(r[x]) for r in rows],[float(r[y]) if r.get(y) not in ('',None) else float('nan') for r in rows]

def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=180,bbox_inches='tight')
    fig.savefig(out/(name+'.pdf'),bbox_inches='tight')
    plt.close(fig)

def generate(root,rows,out):
    root=Path(root);out=Path(out)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    satellites=sorted({int(r['satellites']) for r in rows})
    fig,axes=plt.subplots(len(satellites),2,figsize=(12,3.1*len(satellites)),squeeze=False,layout='constrained')
    for axesrow,n in zip(axes,satellites):
        cases=sorted([r for r in rows if int(r['satellites'])==n],key=lambda r:r['window_s'])
        for r in cases:
            w=int(r['window_s']);ts=read(root/'runs'/r['run']/'timeseries_1s.csv')
            for ax,metric in zip(axesrow,['acked_goodput_mbps','total_queued_mean_packets']):
                ax.plot(*xy(ts,'start_s',metric),color=COLORS[w],label=LABELS[w],lw=1.2)
                ax.set_xlim(0,r['duration_s']);ax.axvspan(0,r['measurement_start_s'],color='#eeeeee',zorder=-2)
                ax.grid(alpha=.2);ax.set_xlabel('Simulation time (s)')
            axesrow[0].set_ylabel(f'{n:,} satellites\nGoodput (Mbps)')
            axesrow[1].set_ylabel('Total queued packets')
        axesrow[0].legend(ncol=2,fontsize=8)
    save(fig,out,'throughput_and_queues')
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    metrics=[('goodput_mbps','Goodput (Mbps)'),('mean_total_queued_packets','Mean total queued packets'),('p95_sampled_srtt_ms','p95 sampled SRTT (ms)')]
    for ax,(key,label) in zip(axes,metrics):
        for j,w in enumerate(COLORS):
            vals=[next((r[key] for r in rows if int(r['satellites'])==n and int(r['window_s'])==w),None) for n in satellites]
            for i,v in enumerate(vals):
                if v is not None:ax.bar(i+(j-1.5)*.19,float(v),width=.18,color=COLORS[w],label=LABELS[w] if i==0 else None)
        ax.set_xticks(range(len(satellites)),[f'{n:,}' for n in satellites]);ax.set_xlabel('Satellites');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=4,frameon=False,fontsize=9)
    fig.suptitle(f"Measurement interval: {rows[0]['measurement_start_s']}–{rows[0]['duration_s']} s")
    save(fig,out,'refresh_tradeoffs')
    # Route evidence is optional for a caller analyzing only the run directories.
    for n in satellites:
        path=root/'paths'/f'path_{n}.csv'
        if not path.is_file():continue
        fig,axs=plt.subplots(3,1,figsize=(10,7),sharex=True,layout='constrained')
        axs[0].plot(*xy(read(path),'t_s','rtt_prop_ms'),color='black',lw=1.5,label='Physical propagation RTT')
        for r in rows:
            if int(r['satellites'])!=n:continue
            w=int(r['window_s']);base=root/'runs'/r['run']
            slow=read(base/'timeseries_1s.csv');fast=read(base/'timeseries_100ms.csv')
            axs[0].plot(*xy(slow,'start_s','effective_base_ms'),color=COLORS[w],label=LABELS[w])
            axs[1].plot(*xy(fast,'time_s','total_cwnd_segments'),color=COLORS[w])
            axs[2].plot(*xy(slow,'start_s','acked_goodput_mbps'),color=COLORS[w])
        for ax,label in zip(axs,['RTT / effective BaseRTT (ms)','cwnd (segments)','Goodput (Mbps)']):
            ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,max(r['duration_s'] for r in rows))
        axs[0].legend(ncol=3,fontsize=8);axs[-1].set_xlabel('Simulation time (s)')
        fig.suptitle(f'{n:,} satellites: route delay and Vegas response')
        save(fig,out,f'route_baseline_{n}')
    # A report-ready markdown table is easier to merge than a second report.
    lines=['# Recurring BaseRTT refresh results','',f"Summary interval: {rows[0]['measurement_start_s']}–{rows[0]['duration_s']} s.",'',
           '| Satellites | History | Goodput (Mbps) | Mean queue (packets) | p95 SRTT (ms) | Retransmissions |',
           '|---:|---|---:|---:|---:|---:|']
    for r in sorted(rows,key=lambda r:(r['satellites'],r['window_s'])):
        lines.append(f"| {r['satellites']} | {LABELS[r['window_s']]} | {r['goodput_mbps']:.2f} | {r['mean_total_queued_packets']:.2f} | {r['p95_sampled_srtt_ms']:.2f} | {r['data_retransmissions']} |")
    lines+=['','Queue occupancy is summed over monitored device queues. SRTT includes propagation and queueing.','The history is a sliding minimum. These results do not establish multi-flow fairness.']
    (out/'report_table.md').write_text('\n'.join(lines)+'\n')
