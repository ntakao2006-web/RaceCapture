import json, pathlib, subprocess, time, urllib.request
ADB='other/uno_q_tools/platform-tools/adb.exe'
SERIAL='3263089125'
OUT=pathlib.Path('outputs/racecapture_unoq_20261002')
def adb(*args):return subprocess.check_output([ADB,'-s',SERIAL,*args],text=True,timeout=15).strip()
def status():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/status',timeout=3) as r:return json.load(r)
before=status();old=adb('shell','cat /proc/sys/kernel/random/boot_id')
req=urllib.request.Request('http://127.0.0.1:8080/api/log/stop',data=b'{}',headers={'Content-Type':'application/json','X-EcoCapture':'1'})
with urllib.request.urlopen(req,timeout=15) as r:json.load(r)
assert status()['hardware']['sd_logging']==0
start=time.monotonic()
subprocess.run([ADB,'-s',SERIAL,'shell','docker run --rm --privileged --pid=host --user 0 --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 -t 1 -m -p -- systemctl reboot'],timeout=20,capture_output=True)
while time.monotonic()-start<180:
    try:
        new=adb('shell','cat /proc/sys/kernel/random/boot_id')
        if new==old:raise RuntimeError('Old boot')
        adb('forward','tcp:8080','tcp:8080');adb('forward','tcp:6080','tcp:6080')
        after=status()
        services=adb('shell','systemctl is-active racecapture-app logger-v2-rcp racecapture-display racecapture-web racecapture-vnc').splitlines()
        if after['connected'] and after['hardware']['sd_logging'] and services==['active']*5:
            result={'elapsed_s':round(time.monotonic()-start,2),'old_boot_id':old,'new_boot_id':new,'services':services,'status':after}
            OUT.joinpath('boot_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k!='status'}),flush=True)
            break
    except Exception:pass
    time.sleep(2)
else:raise RuntimeError('UNO Q did not recover within 180 seconds')
