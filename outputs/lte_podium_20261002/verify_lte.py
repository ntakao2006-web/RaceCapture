"""Use only the running Web's serialized Bridge; never open a second RPC client."""
import asyncio,json,time,urllib.request
from pathlib import Path
BASE='http://127.0.0.1:8080'
def request(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json','X-EcoCapture':'1'})
    return json.load(urllib.request.urlopen(req,timeout=50))
async def main():
    before=request('/api/status');start=time.monotonic();states=[]
    task=asyncio.create_task(asyncio.to_thread(request,'/api/podium/check?watchdog=true',{}))
    while not task.done():
        states.append(await asyncio.to_thread(request,'/api/status'));await asyncio.sleep(.05)
    probe=await task
    await asyncio.sleep(5);after=request('/api/status');duration=time.monotonic()-start
    rate=(after['received']-before['received'])/duration
    keys=('imu_errors','gnss_errors','dropped','sd_errors','sd_queue_dropped')
    deltas={k:after['hardware'][k]-before['hardware'][k] for k in keys}
    assert all(probe[k] for k in ('at','rf_off','flow_control','power_off','watchdog_power_off')),probe
    assert probe['uart_queries']==20 and probe['uart_overflows']==0,probe
    assert all(s['connected'] and s['logging']['active'] for s in states)
    assert 98<=rate<=102,(rate,duration)
    assert after['bridge_errors']==before['bridge_errors'],(before['bridge_errors'],after['bridge_errors'])
    assert not any(deltas.values()),deltas
    report={'passed':True,'lte':probe,'observed_seconds':duration,'receive_hz':rate,
            'status_observations':len(states),'new_hardware_errors':deltas,
            'bridge_errors_delta':after['bridge_errors']-before['bridge_errors'],
            'emmc_rows_delta':after['logging']['rows']-before['logging']['rows'],
            'sd_note':'Existing FAT32 partition is full; SD continuation was not tested. Data preserved.',
            'network_tested':False,'before':before,'after':after}
    Path('/home/arduino/ecocapture-v2-data/lte-podium-20261002').mkdir(exist_ok=True)
    Path('/home/arduino/ecocapture-v2-data/lte-podium-20261002/live_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('before','after')}))
asyncio.run(main())
