import json,time,urllib.request,subprocess,sys
from pathlib import Path
ROOT=Path('/home/arduino/ecocapture-v2-data/bench-20261001/production');ROOT.mkdir(parents=True,exist_ok=True)
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=b'{}' if data is not None else None,headers={'X-EcoCapture':'1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def ready():
 for i in range(60):
  try:
   s=api('/api/status')
   if s['connected']:return s
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('Web did not become ready')
old=ready()['hardware']['sd_file'];api('/api/log/stop',{});api('/api/log/start',{})
for i in range(90):
 before=ready()
 if before['hardware']['sd_file']!=old and before['hardware']['sd_logging']:break
 time.sleep(1)
else:raise RuntimeError('SD did not start new file')
assert before['hardware']['sd_logging'] and before['hardware']['sd_queue_dropped']==0
subprocess.run(['docker','stop','-t','15','ecocapture-web'],check=True)
print('Web stopped: testing independent SD for 30 seconds',flush=True);time.sleep(30)
subprocess.run(['docker','start','ecocapture-web'],check=True)
after=ready();assert after['hardware']['sd_logging'] and after['hardware']['sd_errors']==0 and after['hardware']['sd_queue_dropped']==0
assert after['hardware']['sd_blocks']>before['hardware']['sd_blocks']+300,(before,after)
assert after['hardware']['seq']>before['hardware']['seq']+2900,(before,after)
report={'passed':True,'without_web_seconds':30,'before':before,'after':after};(ROOT/'independent_sd_report.json').write_text(json.dumps(report,indent=2))
print('Independent SD passed',flush=True)
api('/api/log/stop',{});time.sleep(1);files=api('/api/sd/logs');(ROOT/'sd_files.json').write_text(json.dumps(files,indent=2))
index=after['hardware']['sd_file'];f=next(x for x in files if x['index']==index);assert not f['active'] and f['size']>200000
path=ROOT/f'EL{index:06}.BIN'
print(f'Downloading {path.name}: {f["size"]} bytes',flush=True)
with urllib.request.urlopen(f'http://127.0.0.1:8080/api/sd/logs/{index}/download',timeout=30) as response,path.open('wb') as output:
 while b:=response.read(65536):output.write(b);print(f'Downloaded {output.tell()} bytes',flush=True)
assert path.stat().st_size==f['size']
sys.path.insert(0,'/home/arduino/EcoCapture-Web');from sd_decode import convert,records
stats=convert(path,path.with_suffix('.csv'))
with path.open('rb') as stream:r=list(records(stream))
stamps=[stamp for kind,stamp,data in r if kind==1];gaps=[b-a for a,b in zip(stamps,stamps[1:])];hz=(len(stamps)-1)*1000/(stamps[-1]-stamps[0])
assert 95<hz<105,(hz,stats);assert len(stamps)>2900;assert max(gaps)<100,max(gaps)
stats.update(passed=True,imu_hz=hz,max_gap_ms=max(gaps),blocks=path.stat().st_size//512,crc_verified=True,gnss_records=sum(k==2 for k,_,_ in r));(ROOT/'sd_decode_report.json').write_text(json.dumps(stats,indent=2))
print(json.dumps(stats),flush=True)
# Resume acquisition after the bounded SD download.
api('/api/log/start',{})
