import asyncio,json,time,struct,sys,io,collections
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
from sd_decode import records
from sim7070 import SIM7070
from types import SimpleNamespace
b=TelemetryBridge();out=Path('/out');report={'can':[]}
def save():out.joinpath('can_sd.json').write_text(json.dumps(report,indent=2))
async def state():return json.loads(await b.call('logger.status'))
async def files():
 result=[]
 while True:
  page=json.loads(await b.command('FILES'+str(len(result))));result+=page
  if len(page)<16:return result
async def cellular():
 report['lte']=[]
 for attempt in range(5):
  modem=SIM7070(b);item={'attempt':attempt+1};started=time.monotonic()
  original=modem.command
  async def traced(c,timeout=5):
   item['last_command']=c
   return await original(c,timeout)
  modem.command=traced
  try:
   await modem.connect(SimpleNamespace(apn='soracom.io',username='sora',password='sora',host='example.com',port=80))
   item['connect_seconds']=time.monotonic()-started;item['radio']=(await modem.command('AT+CPSI?')).decode();item['responses']=[]
   for _ in range(3):
    await modem.send(b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: keep-alive\r\n\r\n')
    lines=[]
    while True:
     line=await modem.readline();lines.append(line.decode())
     if line==b'\r\n':break
    item['responses'].append(''.join(lines));await asyncio.sleep(1)
   item['ack']=(await modem.command('AT+CAACK=0')).decode();item['passed']=all('HTTP/1.1 200 OK' in v for v in item['responses'])
  except Exception as e:item['error']=repr(e);item['buffer']=modem.buffer.decode('ascii','replace')
  finally:await modem.close()
  report['lte'].append(item);save();print('LTE_RESULT',json.dumps(item),flush=True);await asyncio.sleep(2)
async def main():
 try:
  await b.command('LOG0');report['initial']=await state();report['files_before']=await files();save()
  await b.call('logger.take');await b.command('LOG1');network=asyncio.create_task(cellular())
  for rate in [125000,250000,500000,1000000]+[500000]*8:
   await b.call('logger.take');before=await state();frames=[];samples=[];states=[]
   print('CAN_BEGIN',rate,await b.command('BENCH'+str(rate)),flush=True)
   end=time.monotonic()+30
   while time.monotonic()<end:
    batch=json.loads(await b.call('logger.take'));frames+=batch['can'];samples+=batch['rows'];s=await state()
    if not states or s['mcu_ms']-states[-1]['mcu_ms']>=500:states.append(s)
    if s['result'].startswith('BENCH_DONE'):break
    await asyncio.sleep(.025)
   batch=json.loads(await b.call('logger.take'));frames+=batch['can'];samples+=batch['rows']
   valid=[];bad=[]
   for f in frames:
    _,ch,ident,ext,rtr,data=f;n=ident-(0x18ff0000 if ext else 0x100)
    dlc=(n//4)%9;expected=bytes((n*17+j*29)&255 for j in range(dlc)).hex()
    if 0<=n<1200 and ch==(1 if n&1 else 2) and ext==bool((n//2)&1) and not rtr and data==expected:valid.append(n)
    else:bad.append(f)
   item={'rate':rate,'result':s['result'],'received':len(frames),'unique_matched':len(set(valid)),'duplicates':len(valid)-len(set(valid)),'missing':[n for n in range(1200) if n not in set(valid)],'bad':bad,'directions':dict(collections.Counter(f[1] for f in frames)),'before':before,'after':s,'states':states,'imu_samples':len(samples)}
   report['can'].append(item);out.joinpath(f'can_final_{len(report["can"]):02}_{rate}.json').write_text(json.dumps(frames));save();print('CAN_RESULT',rate,len(frames),len(set(valid)),len(bad),s['result'],flush=True)
  while not network.done():await b.call('logger.take');await asyncio.sleep(.04)
  await network
  await b.command('END');report['independent_before']=await state();await b.close();await asyncio.sleep(15);report['independent_after']=await state()
  await b.command('LOG0');report['files_after']=await files();save()
  async def read(lba):return bytes.fromhex((await b.sector(lba))[5:])
  m=await read(0);part,size=struct.unpack_from('<II',m,454);boot=await read(part)
  reserved=struct.unpack_from('<H',boot,14)[0];fatsize=struct.unpack_from('<I',boot,36)[0];spc=boot[13];copies=boot[16];base=part+reserved+copies*fatsize
  report['sd_geometry']={'partition_start':part,'sectors':size,'bytes':size*512,'cluster_bytes':spc*512,'fat_copies':copies,'boot_backup_equal':boot==await read(part+6),'first_fat_sector_equal':await read(part+reserved)==await read(part+reserved+fatsize)};save()
  new=[f for f in report['files_after'] if f['index'] not in {x['index'] for x in report['files_before']} and f['size']]
  report['sd_verified']=[];sd_can=[]
  for f in new:
   data=bytearray();start=base+(f['cluster']-2)*spc
   for i in range((f['size']+511)//512):
    data.extend(await read(start+i))
    if i%16==0:await b.call('logger.take')
   data=data[:f['size']];out.joinpath(f"EL{f['index']:06}.BIN").write_bytes(data)
   decoded=list(records(io.BytesIO(data)));counts=dict(collections.Counter(r[0] for r in decoded));can=[]
   for kind,stamp,p in decoded:
    if kind==3:can.append([stamp,p[0],struct.unpack_from('<I',p,1)[0],p[5]&1,bool(p[5]&2),p[7:].hex()])
   sd_can.extend(can)
   report['sd_verified'].append({'file':f,'crc_sequence_ok':True,'record_counts':counts,'can_count':len(can),'first_ms':decoded[0][1] if decoded else None,'last_ms':decoded[-1][1] if decoded else None});save();print('SD_VERIFIED',f,counts,flush=True)
  live=[]
  for i,test in enumerate(report['can'],1):live+=json.loads(out.joinpath(f'can_final_{i:02}_{test["rate"]}.json').read_text())
  report['sd_matches_live_can']=collections.Counter(tuple(x[1:]) for x in live)==collections.Counter(tuple(x[1:]) for x in sd_can)
  report['final']=await state();save()
 finally:
  await b.command('END');await b.command('LOG0');await b.close()
asyncio.run(main())
