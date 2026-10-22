import asyncio,json,time,sys,re
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
from sim7070 import SIM7070
b=TelemetryBridge();m=SIM7070(b);report={'steps':[]};run=True
def save():Path('/out/network_retry.json').write_text(json.dumps(report,indent=2))
async def collect():
 while run:
  await b.call('logger.take');await asyncio.sleep(.04)
async def at(c,t=10):
 try:v=(await m.command(c,t)).decode('ascii','replace');ok=True
 except Exception as e:v=str(e)+' '+m.buffer.decode('ascii','replace');ok=False
 report['steps'].append({'command':c,'ok':ok,'response':v});save();print(c,ok,v.strip(),flush=True);return v
async def main():
 global run
 task=asyncio.create_task(collect())
 try:
  await m.uart.power(True);await asyncio.sleep(4)
  for c in ['AT','ATE0','AT+IFC=2,2','AT+CMEE=2']:await at(c)
  for _ in range(60):
   v=await at('AT+CGATT?')
   if re.search(r'\+CGATT:\s*1',v):break
   await asyncio.sleep(2)
  for c in ['AT+CPIN?','AT+CPSMS=0','AT+CEDRXS=0','AT+CPSI?','AT+CNACT?','AT+CNCFG=0,1,"soracom.io","sora","sora",1','AT+CNACT=0,1']:await at(c,30)
  await asyncio.sleep(3);await at('AT+CNACT?')
  for host in ['example.com','104.20.23.154','example.com']:
   await at('AT+CACLOSE=0');await at('AT+CASSLCFG=0,"SSL",0')
   v=await at(f'AT+CAOPEN=0,0,"TCP","{host}",80',40)
   until=time.monotonic()+30
   while '+CAOPEN:' not in v and time.monotonic()<until:
    await m.pump();v=m.buffer.decode('ascii','replace');await asyncio.sleep(.05)
   if re.search(r'\+CAOPEN:\s*0,0',v):
    request=b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: keep-alive\r\n\r\n'
    await m.send(request);await asyncio.sleep(2)
    for _ in range(10):
     v=await at('AT+CARECV=0,512',15)
     if 'HTTP/1.' in v:report['http_received']=True;save();break
     await asyncio.sleep(.5)
    await at('AT+CAACK=0');await at('AT+CASTATE?');await at('AT+CACLOSE=0')
  report['hardware_final']=json.loads(await b.call('logger.status'));save()
 finally:
  await m.close();run=False;await task;await b.close();save()
asyncio.run(main())
