"""Actual USB-only logger acceptance. Leaves a new recording running."""
import asyncio,csv,io,json,time,math
from pathlib import Path
import httpx,websockets
async def main():
 headers={'X-EcoCapture':'1'}
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8080',timeout=15) as client:
  await client.post('/api/log/stop',headers=headers)
  before=(await client.get('/api/status')).json();assert before['connected'],before
  result=await client.post('/api/log/start',headers=headers);result.raise_for_status();name=result.json()['name']
  start=time.monotonic();sequences=set();calibration=None
  async with websockets.connect('ws://127.0.0.1:8080/ws',origin='http://127.0.0.1:8080') as ws:
   while time.monotonic()-start<30:
    envelope=json.loads(await asyncio.wait_for(ws.recv(),3));sample=envelope['sample']
    assert envelope['status']['connected'] and sample['source']=='logger-v2-hardware' and sample['demo'] is False
    assert sample['values']['RPM'] is None and sample['values']['Speed'] is None
    assert sample['values']['Lat'] is None and sample['values']['Lon'] is None
    norm=math.sqrt(sum(sample['values'][k]**2 for k in ('AccelX','AccelY','AccelZ')));assert 8<norm<11,norm
    sequences.add(sample['seq']);calibration=sample['imu_calibration']
  middle=(await client.get('/api/status')).json()
  await asyncio.sleep(5)
  after=(await client.get('/api/status')).json()
  assert after['logging']['rows']>middle['logging']['rows']+400,(middle,after)
  assert after['bridge_errors']==before['bridge_errors'],(before,after)
  assert after['hardware']['dropped']==before['hardware']['dropped'],(before,after)
  assert after['hardware']['imu_errors']==before['hardware']['imu_errors']==0
  assert after['hardware']['gnss_errors']==before['hardware']['gnss_errors']==0
  assert after['hardware']['can_overflow']==[0,0]
  result=await client.post('/api/log/stop',headers=headers);result.raise_for_status()
  content=await client.get(f'/api/logs/{name}/download');content.raise_for_status();rows=list(csv.DictReader(io.StringIO(content.text)))
  assert len(rows)==result.json()['rows'] and len(rows)>3000,len(rows)
  assert all(row['source']=='logger-v2-hardware' and row['demo']=='0' for row in rows)
  assert all(int(b['seq'])==int(a['seq'])+1 for a,b in zip(rows,rows[1:])), 'Missing MCU sample'
  duration=(int(rows[-1]['mcu_ms'])-int(rows[0]['mcu_ms']))/1000
  hz=(len(rows)-1)/duration;assert 95<hz<105,hz
  raw=await client.get(f'/api/logs/{name}/can');raw.raise_for_status();assert not raw.text.strip(),raw.text[:100]
  report={'passed':True,'csv':name,'csv_rows':len(rows),'recorded_hz':hz,'websocket_unique_samples':len(sequences),'without_test_browser_rows':after['logging']['rows']-middle['logging']['rows'],'imu_calibration':calibration,'before':before,'after':after}
  Path('/data/bench-20261001/production').mkdir(exist_ok=True,parents=True)
  Path('/data/bench-20261001/production/live_report.json').write_text(json.dumps(report,indent=2))
  print(json.dumps(report,indent=2))
  result=await client.post('/api/log/start',headers=headers);result.raise_for_status()
asyncio.run(main())
