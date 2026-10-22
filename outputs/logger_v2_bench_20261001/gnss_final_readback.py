from gnss_service import Gnss
import struct,json,pathlib,collections
g=Gnss();report={}
keys=[(0x30210001,100,2),(0x30210002,1,2),(0x10720001,1,1),(0x10720002,0,1),(0x20910006,1,1),(0x1031001f,1,1),(0x10310021,1,1),(0x10310022,1,1),(0x10310025,1,1),(0x1031000d,0,1),(0x1031000f,1,1)]
for k,v,n in keys:
 for attempt in range(3):
  try:f=g.poll(6,0x8b,b'\0\0\0\0'+struct.pack('<I',k));break
  except TimeoutError:
   report.setdefault('read_retries',[]).append(hex(k))
   if attempt==2:raise
 p=f[6:-2];got=int.from_bytes(p[8:8+n],'little');assert got==v,(hex(k),got,v);report.setdefault('ram_readback',{})[hex(k)]=got
try:f=g.poll(1,0x35);p=f[6:-2]
except TimeoutError:p=b'';report['nav_sat_poll']='No response; NAV-PVT used satellite count available in continuous capture'
sats=[]
for offset in range(8,len(p),12):
 b=p[offset:offset+12]
 if len(b)==12:sats.append({'system':b[0],'sv':b[1],'cno':b[2],'used':bool(struct.unpack_from('<I',b,8)[0]&8)})
report['nav_sat']={'channels':len(sats),'with_signal':sum(s['cno']>0 for s in sats),'used':sum(s['used'] for s in sats),'used_by_system':dict(collections.Counter(s['system'] for s in sats if s['used'])),'satellites':sats}
pathlib.Path('/data/bench-20261001/gnss_final_readback.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
