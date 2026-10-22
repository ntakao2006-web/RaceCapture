from gnss_service import Gnss
import time,json,pathlib,struct,collections,os,sys
g=Gnss();duration=int(sys.argv[1]) if len(sys.argv)>1 else 120;rows=[];start=time.monotonic();g.drain();g.frames=[]
p=pathlib.Path('/data/bench-20261001/gnss10_settled.jsonl')
with p.open('w') as f:
 while time.monotonic()-start<duration:
  g.drain()
  for frame in g.frames:
   if frame[2:4]!=b'\x01\x07' or len(frame)!=100:continue
   b=frame[6:-2];r={'host_s':round(time.monotonic()-start,3),'itow':struct.unpack_from('<I',b)[0],'fix':b[20],'valid':bool(b[21]&1),'sats':b[23],'hacc_mm':struct.unpack_from('<I',b,40)[0]};rows.append(r);f.write(json.dumps(r)+'\n')
  g.frames=[];time.sleep(.05)
 f.flush();os.fsync(f.fileno())
delta=[(b['itow']-a['itow'])%604800000 for a,b in zip(rows,rows[1:])]
summary={'samples':len(rows),'elapsed_s':rows[-1]['host_s']-rows[0]['host_s'],'measured_hz':(len(rows)-1)/(rows[-1]['host_s']-rows[0]['host_s']),'itow_interval_ms':dict(collections.Counter(delta)),'sats_min':min(r['sats'] for r in rows),'sats_max':max(r['sats'] for r in rows),'hacc_min_mm':min(r['hacc_mm'] for r in rows),'hacc_max_mm':max(r['hacc_mm'] for r in rows),'valid_fix_samples':sum(r['fix']==3 and r['valid'] for r in rows),'last':rows[-1],'state':g.c.state()}
p.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
