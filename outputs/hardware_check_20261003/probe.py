import asyncio,json,time,struct,sys,re
from pathlib import Path
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
from sim7070 import SIM7070
OUT=Path('/out')
report={'steps':[],'states':[]}; b=TelemetryBridge(); running=True
def save():OUT.joinpath('probe.json').write_text(json.dumps(report,indent=2))
async def collect():
    while running:
        try:
            await b.call('logger.take')
            s=json.loads(await b.call('logger.status'))
            if not report['states'] or s['mcu_ms']-report['states'][-1]['mcu_ms']>=1000:report['states'].append(s);save()
        except Exception as e:report.setdefault('collector_errors',[]).append(str(e))
        await asyncio.sleep(.04)
async def main():
    global running
    task=asyncio.create_task(collect());m=SIM7070(b)
    async def at(c,timeout=10):
        started=time.monotonic()
        try:
            v=(await m.command(c,timeout)).decode('ascii','replace');ok=True
        except Exception as e:v=str(e)+' '+m.buffer.decode('ascii','replace');ok=False
        if c in ('AT+CCID','AT+CIMI','AT+GSN'):v=re.sub(r'\d{10,}',lambda x:x[0][:5]+'***'+x[0][-4:],v)
        report['steps'].append({'command':c,'ok':ok,'response':v,'seconds':round(time.monotonic()-started,3)});save();print(c,ok,v.strip(),flush=True)
        return v,ok
    try:
        await m.uart.power(True);await asyncio.sleep(4)
        for _ in range(3):
            if (await at('AT'))[1]:break
        for c in ['ATE0','AT+IFC=2,2','AT+CMEE=2','ATI','AT+GMR','AT+CFUN?','AT+CPIN?','AT+CCID','AT+CIMI','AT+CNMP?','AT+CMNB?','AT+CBANDCFG?','AT+CGDCONT?','AT+CNCFG?']:
            await at(c)
        await at('AT+CFUN=0',15)
        await at('AT+CGDCONT=1,"IP","soracom.io"')
        await at('AT+CNCFG=0,1,"soracom.io","sora","sora",1')
        await at('AT+CFUN=1',15)
        await at('AT+CPSMS=0');await at('AT+CEDRXS=0')
        registered=False
        for i in range(36):
            await at('AT+CEREG?');await at('AT+CPSI?');await at('AT+CSQ')
            v,ok=await at('AT+CGATT?')
            if ok and re.search(r'\+CGATT:\s*1',v):registered=True;break
            await asyncio.sleep(5)
        report['registered']=registered
        if registered:
            await at('AT+COPS?');await at('AT+CNACT=0,1',30);await asyncio.sleep(2)
            await at('AT+CNACT?');await at('AT+CDNSGIP="example.com"',20)
            await at('AT+CASSLCFG=0,"SSL",0')
            v,ok=await at('AT+CAOPEN=0,0,"TCP","example.com",80',30)
            if ok:
                try:
                    await m.wait(b'+CAOPEN:',30);await asyncio.sleep(.3);await m.pump()
                    report['socket_open']=m.buffer.decode('ascii','replace');save()
                    if re.search(rb'\+CAOPEN:\s*0,0',m.buffer):
                        await m.send(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: keep-alive\r\n\r\n')
                        await asyncio.sleep(2)
                        await at('AT+CARECV=0,512',20)
                        report['http_test_sent_bytes']=61
                except Exception as e:report['socket_error']=str(e);save()
            await at('AT+CACLOSE=0')
        await asyncio.sleep(10)
    finally:
        await m.close();report['final_lte']=json.loads(await b.call('logger.lter'));running=False;await task;save();await b.close()
asyncio.run(main())
