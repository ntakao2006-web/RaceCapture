import asyncio,json,time,sys,types,struct
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
from sim7070 import SIM7070
b=TelemetryBridge();report={'attempts':[],'states':[]};run=True
def save():Path('/out/transport.json').write_text(json.dumps(report,indent=2))
async def collect():
 while run:
  await b.call('logger.take');s=json.loads(await b.call('logger.status'))
  if not report['states'] or s['mcu_ms']-report['states'][-1]['mcu_ms']>=1000:report['states'].append(s);save()
  await asyncio.sleep(.04)
async def main():
 global run
 task=asyncio.create_task(collect())
 try:
  await b.command('LOG1')
  for i in range(5):
   m=SIM7070(b);item={'attempt':i+1,'commands':[]};start=time.monotonic()
   original=m.command
   async def traced(c,timeout=5):
    try:
     v=await original(c,timeout);item['commands'].append([c,v.decode('ascii','replace')]);return v
    except Exception:
     item['failed_command']=c;raise
   m.command=traced
   try:
    await m.connect(types.SimpleNamespace(apn='soracom.io',username='sora',password='sora',host='example.com',port=80))
    item['connect_seconds']=time.monotonic()-start;item['network']=(await m.command('AT+CPSI?')).decode()
    item['responses']=[]
    for n in range(3):
     await m.send(b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: keep-alive\r\n\r\n')
     lines=[]
     while True:
      line=await m.readline();lines.append(line.decode('ascii','replace'))
      if line==b'\r\n':break
     item['responses'].append(''.join(lines));await asyncio.sleep(1)
    item['ack']=(await m.command('AT+CAACK=0')).decode();item['passed']=all('HTTP/1.1 200 OK' in r for r in item['responses'])
   except Exception as e:item['error']=repr(e);item['buffer']=m.buffer.decode('ascii','replace')
   finally:await m.close()
   report['attempts'].append(item);save();print(json.dumps({k:v for k,v in item.items() if k not in ('commands','responses')}),flush=True);await asyncio.sleep(2)
 finally:await b.command('LOG0');run=False;await task;await b.close();save()
asyncio.run(main())
