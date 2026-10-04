"""Run from Windows after forwarding tcp:17223 to device tcp:7223."""
import json
import socket
import time
import urllib.request
from pathlib import Path

def status():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/status',timeout=5) as r:return json.load(r)
before=status();start=time.monotonic();count=0;ticks=set();meta=[];values={}
with socket.create_connection(('127.0.0.1',17223),timeout=5) as sock:
    sock.sendall(b'{"getMeta":{}}\r\n{"setTelemetry":{"rate":10,"transport":"wifi"}}\r\n')
    with sock.makefile('rb') as stream:
        while time.monotonic()-start<30:
            packet=json.loads(stream.readline())
            if 'meta' in packet:meta=packet['meta']
            if 's' not in packet:continue
            sample=packet['s'];meta=sample.get('meta',meta);count+=1;ticks.add(sample['t'])
            nmask=(len(meta)+31)//32;masks=sample['d'][-nmask:];data=iter(sample['d'][:-nmask])
            values={c['nm']:next(data) for i,c in enumerate(meta) if masks[i//32]&(1<<(i%32))}
after=status()
report={'duration_s':round(time.monotonic()-start,2),'samples':count,'unique_mcu_timestamps':len(ticks),
    'channels':len(meta),'metadata':meta,'last_values':values,
    'bridge_errors_delta':after['bridge_errors']-before['bridge_errors'],
    'sd_errors_delta':after['hardware']['sd_errors']-before['hardware']['sd_errors'],
    'sd_dropped_delta':after['hardware']['sd_queue_dropped']-before['hardware']['sd_queue_dropped'],
    'sd_blocks_delta':after['hardware']['sd_blocks']-before['hardware']['sd_blocks'],
    'connected':after['connected'],'source':after['source']}
assert count>200 and len(ticks)>200 and report['connected'] and report['sd_blocks_delta']>0,report
assert all(report[k]==0 for k in ('bridge_errors_delta','sd_errors_delta','sd_dropped_delta')),report
Path('outputs/racecapture_unoq_20261002/live_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('metadata','last_values')},indent=2))
