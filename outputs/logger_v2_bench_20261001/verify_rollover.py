import asyncio,json,struct,time,urllib.request,sys
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
from sd_decode import records
ROOT=Path('/data/bench-20261001/production')
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=b'{}' if data is not None else None,headers={'X-EcoCapture':'1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
async def main():
 before=api('/api/status');old=before['hardware']['sd_file']
 for i in range(180):
  await asyncio.sleep(1);after=api('/api/status')
  assert after['connected'] and after['hardware']['sd_errors']==0 and after['hardware']['sd_queue_dropped']==0,after
  if after['hardware']['sd_file']>old and after['hardware']['sd_bytes']>2048:break
 else:raise RuntimeError('No SD rollover observed')
 api('/api/log/stop',{});files=api('/api/sd/logs')
 bridge=TelemetryBridge()
 try:
  mbr=bytes.fromhex((await bridge.sector(0))[5:]);part=struct.unpack_from('<I',mbr,454)[0]
  bpb=bytes.fromhex((await bridge.sector(part))[5:]);spc=bpb[13];data=part+struct.unpack_from('<H',bpb,14)[0]+bpb[16]*struct.unpack_from('<I',bpb,36)[0]
  selected=[next(f for f in files if f['index']==index) for index in (old,old+1)]
  import io,zlib
  stamps=[];gnss=[]
  for file in selected:
   start=data+(file['cluster']-2)*spc;blocks=file['size']//512
   offsets=range(max(0,blocks-4),blocks) if file['index']==old else range(min(4,blocks))
   local=[]
   for offset in offsets:
    block=bytes.fromhex((await bridge.sector(start+offset))[5:])
    ident,sequence,used=struct.unpack_from('<IIH',block,4)
    assert block[:4]==b'ELB2' and ident==file['index'] and sequence==offset
    assert zlib.crc32(block[:508])==struct.unpack_from('<I',block,508)[0]
    pos=16
    while pos<used:
     kind,size,stamp=struct.unpack_from('<BBI',block,pos);pos+=6
     if kind==1:local.append(stamp)
     if kind==2:gnss.append(struct.unpack_from('<I',block,pos)[0])
     pos+=size
   assert local;stamps.append(local)
  gap=stamps[1][0]-stamps[0][-1];assert 0<gap<100,gap
  report={'passed':True,'before':before,'after':after,'files':selected,'boundary_gap_ms':gap,'crc_verified_boundary_blocks':8}
  (ROOT/'rollover_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
 finally:await bridge.close()
 api('/api/log/start',{})
asyncio.run(main())
