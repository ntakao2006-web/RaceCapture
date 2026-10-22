import json,time,urllib.request
from pathlib import Path
ROOT=Path('/home/arduino/ecocapture-v2-data/bench-20261001/production')
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=b'{}' if data is not None else None,headers={'X-EcoCapture':'1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
for i in range(180):
 try:
  if api('/api/status')['connected']:break
 except Exception:pass
 time.sleep(1)
else:raise RuntimeError('Web did not become ready')
api('/api/log/stop',{})
logs=api('/api/logs');candidates=[f for f in logs if not f['active'] and not f['demo'] and f['size']>3000]
selected=min(candidates,key=lambda f:f['size']);before=api('/api/sd/logs')
api('/api/logs/'+selected['name']+'/sd',{})
print('Copying real CSV to SD: '+selected['name']+' '+str(selected['size'])+' bytes',flush=True)
for i in range(3600):
 time.sleep(1);status=api('/api/status');copy=status['sd_copy']
 if i%60==0:print(json.dumps({'elapsed_seconds':i,'copy':copy}),flush=True)
 if not copy['active']:break
else:raise RuntimeError('SD copy did not finish within one hour; operation left untouched')
assert status['connected'] and copy.get('verified') and not copy.get('error'),status
after=api('/api/sd/logs');assert before==after,(before,after)
report={'passed':True,'source':selected,'copy':copy,'existing_logger_entries_unchanged':True,'existing_files':len(before)}
(ROOT/'sd_copy_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
api('/api/log/start',{})
