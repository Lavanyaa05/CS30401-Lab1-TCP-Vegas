"""Extract the preserved instrumented Vegas decision format from fresh console logs."""
import csv
import math
from collections import defaultdict

def mean(values):
    return sum(values)/len(values) if values else None

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

