from gnss_service import Gnss,ubx
import json,struct,pathlib,time
g=Gnss();rows=[]
g.send(ubx(6,4,b'\0\0\0\0'));time.sleep(1)
for key in [0x40a40001,0x40a40003,0x40a40005,0x40a4000a]:
 try:
  f=g.poll(6,0x8b,b'\0\x04\0\0'+struct.pack('<I',key));p=f[6:-2]
  rows.append({'key':hex(key),'frame':f.hex(),'value':struct.unpack_from('<I',p,8)[0] if len(p)==12 and struct.unpack_from('<I',p,4)[0]==key else None})
 except Exception as e:rows.append({'key':hex(key),'error':str(e),'value':None})
report={'method':'individual read-only factory keys after physical reset','keys':rows,'verified':all(r['value']==(96000000 if i==3 else 192000000) for i,r in enumerate(rows))}
pathlib.Path('/data/bench-20261001/gnss_clock_individual_readback.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
