import asyncio,hashlib,json,struct,sys,urllib.request
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
ROOT=Path('/data/bench-20261001/production')
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=b'{}' if data is not None else None,headers={'X-EcoCapture':'1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
async def main():
 bridge=TelemetryBridge()
 for i in range(180):
  try:
   if json.loads(await bridge.call('logger.status'))['seq']>100:break
  except Exception:pass
  await asyncio.sleep(1)
 else:raise RuntimeError('MCU did not become ready')
 await bridge.command('LOG0')
 try:
  mbr=bytes.fromhex((await bridge.sector(0))[5:]);start,size=struct.unpack_from('<II',mbr,454)
  lba=start+size-1;original=bytes.fromhex((await bridge.sector(lba))[5:])
  (ROOT/'identical_write_original_sector.bin').write_bytes(original)
  for repeat in range(3):
   for offset in range(0,512,16):
    assert await bridge.command(f'H{offset}:'+original[offset:offset+16].hex())=='loaded'
   result=await bridge.command('W'+str(lba));assert 'accepted=1 busy_done=1' in result,result
   assert bytes.fromhex((await bridge.sector(lba))[5:])==original
   print('Identical sector write/readback passed '+str(repeat+1),flush=True)
  report={'passed':True,'identical_write_only':True,'sector':lba,'upload_bytes_per_request':16,'repetitions':3,'sha256':hashlib.sha256(original).hexdigest()}
  (ROOT/'sd_write_report.json').write_text(json.dumps(report,indent=2))
 finally:await bridge.close()
 print(json.dumps(report),flush=True)
asyncio.run(main())
