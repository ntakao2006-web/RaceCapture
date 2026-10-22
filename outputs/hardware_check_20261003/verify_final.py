import json,time,urllib.request,csv,io,hashlib
from pathlib import Path
p=Path(__file__).parent
def req(path,body=None,raw=False):
 data=None if body is None else json.dumps(body).encode()
 r=urllib.request.Request('http://127.0.0.1:8080'+path,data=data,headers={'Content-Type':'application/json','X-EcoCapture':'1'})
 with urllib.request.urlopen(r,timeout=30) as f:v=f.read()
 return v if raw else json.loads(v)
before=req('/api/status');time.sleep(15);after=req('/api/status');stopped=req('/api/log/stop',{})
name=after['logging']['name'];data=req('/api/logs/'+name+'/download',raw=True);(p/name).write_bytes(data)
rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
sd=req('/api/sd/logs');final=req('/api/status');podium=req('/api/podium')['config']
(p/'final_status.json').write_text(json.dumps(final,indent=2));(p/'final_sd_files.json').write_text(json.dumps(sd,indent=2))
report={'before':before,'after':after,'rows_downloaded':len(rows),'file':name,'sha256':hashlib.sha256(data).hexdigest(),'columns':list(rows[0]) if rows else [],'new_bridge_errors':after['bridge_errors']-before['bridge_errors'],'new_errors':{k:after['hardware'][k]-before['hardware'][k] for k in ['imu_errors','gnss_errors','dropped','sd_errors','sd_queue_dropped','lte_overflows']},'lte_off':final['hardware']['lte_power']==0 and not podium['enabled'],'can2_listen_only':final['hardware']['can2_mode']==3,'recording_stopped':not final['logging']['active'] and not final['hardware']['sd_logging'],'config':podium}
(p/'final_check.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('before','after','columns','config')},indent=2))
assert report['rows_downloaded']>1000 and report['new_bridge_errors']==0 and not any(report['new_errors'].values())
assert report['lte_off'] and report['can2_listen_only'] and report['recording_stopped']
