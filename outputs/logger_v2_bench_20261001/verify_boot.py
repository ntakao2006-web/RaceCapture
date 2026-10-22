import json,subprocess,sys,time,urllib.request
from pathlib import Path
adb=Path(sys.argv[1]).resolve();root=Path(__file__).parent/'production'
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=b'{}' if data is not None else None,headers={'X-EcoCapture':'1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30 if data is not None else 3) as r:return json.load(r)
before=api('/api/status');assert before['connected'] and not before['sd_copy']['active']
before_boot_id=subprocess.check_output([str(adb),'shell','cat','/proc/sys/kernel/random/boot_id'],timeout=3,text=True).strip()
api('/api/log/stop',{})
subprocess.run([str(adb),'shell','docker','run','--rm','--privileged','--pid=host','--user','0','--entrypoint','/usr/bin/nsenter','ecocapture-web:0.2.0','-t','1','-m','-p','--','/bin/systemctl','reboot'],timeout=20)
started=time.monotonic();print('UNO Q reboot requested; waiting for automatic acquisition',flush=True)
time.sleep(10)
for i in range(240):
 try:
  state=subprocess.run([str(adb),'get-state'],timeout=3,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if state.returncode and i%15==0:
   subprocess.run([str(adb),'kill-server'],timeout=3,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   subprocess.run([str(adb),'start-server'],timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  subprocess.run([str(adb),'forward','tcp:8080','tcp:8080'],timeout=3,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  after=api('/api/status')
  after_boot_id=subprocess.check_output([str(adb),'shell','cat','/proc/sys/kernel/random/boot_id'],timeout=3,text=True).strip()
  boot_service=subprocess.check_output([str(adb),'shell','systemctl','is-active','ecocapture-web-start.service'],timeout=3,text=True).strip()
  if after_boot_id!=before_boot_id and boot_service=='active' and after['connected'] and after['logging']['active'] and after['hardware']['sd_logging'] and after['hardware']['seq']>100:break
 except Exception:pass
 time.sleep(1)
else:raise RuntimeError('Automatic acquisition did not return after reboot')
assert after_boot_id!=before_boot_id
assert after['hardware']['sd_errors']==after['hardware']['sd_queue_dropped']==after['hardware']['imu_errors']==after['hardware']['gnss_errors']==0,after
time.sleep(35);stable=api('/api/status')
assert stable['connected'] and stable['logging']['active'] and stable['hardware']['sd_logging']
assert stable['logging']['name']==after['logging']['name']
assert stable['logging']['rows']>after['logging']['rows']+3000
assert stable['hardware']['sd_blocks']>after['hardware']['sd_blocks']+300
assert stable['bridge_errors']==after['bridge_errors'] and stable['hardware']['dropped']==after['hardware']['dropped'],(after,stable)
assert stable['hardware']['sd_errors']==stable['hardware']['sd_queue_dropped']==0
report={'passed':True,'automatic_logging':True,'boot_service_completed':True,'before_linux_boot_id':before_boot_id,'after_linux_boot_id':after_boot_id,'recovery_seconds':time.monotonic()-started-35,'before':before,'after':after,'stable_after_35_seconds':stable}
(root/'boot_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
