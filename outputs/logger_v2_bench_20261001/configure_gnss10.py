from gnss_service import Gnss,ubx
import struct,time,json,pathlib,collections,os
g=Gnss()
def setvals(values):
 p=b'\0\1\0\0'+b''.join(struct.pack('<I',k)+v.to_bytes(n,'little') for k,v,n in values)
 g.drain();g.frames=[];g.send(ubx(6,0x8a,p));g.wait(5,1,ack=b'\x06\x8a')
def verify(values):
 f=g.poll(6,0x8b,b'\0\0\0\0'+b''.join(struct.pack('<I',k) for k,v,n in values));p=f[6:-2];got={};pos=4
 widths={k:n for k,v,n in values}
 while pos<len(p):
  k=struct.unpack_from('<I',p,pos)[0];pos+=4;n=widths[k];got[k]=int.from_bytes(p[pos:pos+n],'little');pos+=n
 assert all(got.get(k)==v for k,v,n in values),(values,got)
 return {hex(k):v for k,v in got.items()}
signals=[(0x1031001f,1,1),(0x10310001,1,1),(0x10310021,1,1),(0x10310007,1,1),(0x10310022,1,1),(0x1031000d,0,1),(0x1031000f,1,1),(0x10310025,1,1),(0x10310018,1,1),(0x10310024,1,1),(0x10310012,1,1),(0x10310020,1,1),(0x10310005,1,1)]
rates=[(0x10720001,1,1),(0x10720002,0,1),(0x20910006,1,1),(0x30210001,100,2),(0x30210002,1,2),(0x20110021,4,1)]
setvals([(0x30210001,1000,2)]);setvals(signals);time.sleep(.7);setvals(rates)
report={'profile':'four_10','systems':'GPS+Galileo+BeiDou B1C+GLONASS, QZSS/SBAS enabled','configuration_layer':'RAM, reapplied by final firmware on boot','signals_readback':verify(signals),'rates_readback':verify(rates)}
p=pathlib.Path('/data/bench-20261001');(p/'gnss10_configuration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
rows=[];start=time.monotonic();g.drain();g.frames=[]
with (p/'gnss10_actual.jsonl').open('w') as f:
 while time.monotonic()-start<65:
  g.drain()
  for frame in g.frames:
   if frame[2:4]!=b'\x01\x07' or len(frame)!=100:continue
   b=frame[6:-2];r={'host_s':round(time.monotonic()-start,3),'itow':struct.unpack_from('<I',b,0)[0],'fix':b[20],'valid':bool(b[21]&1),'sats':b[23],'hacc_mm':struct.unpack_from('<I',b,40)[0],'lat_e7':struct.unpack_from('<i',b,28)[0],'lon_e7':struct.unpack_from('<i',b,24)[0]};rows.append(r);f.write(json.dumps(r)+'\n')
  g.frames=[];g.c.receive(1);time.sleep(.04)
 f.flush();os.fsync(f.fileno())
delta=[(b['itow']-a['itow'])%604800000 for a,b in zip(rows,rows[1:])]
summary={'samples':len(rows),'elapsed_s':rows[-1]['host_s']-rows[0]['host_s'],'measured_hz':(len(rows)-1)/(rows[-1]['host_s']-rows[0]['host_s']),'itow_interval_ms':dict(collections.Counter(delta)),'sats_min':min(r['sats'] for r in rows),'sats_max':max(r['sats'] for r in rows),'last':rows[-1],'valid_fix_samples':sum(r['valid'] and r['fix']==3 for r in rows),'state':g.c.state()}
(p/'gnss10_actual.summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
