import json,os,time,subprocess,urllib.request
from pathlib import Path
def procs():
    result={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            stat=(p/'stat').read_text().split();cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if any(x in cmd for x in ('race_capture','rcp_bridge.py','x11vnc','Xvfb','Xorg','websockify','uvicorn')):
                result[p.name]=(int(stat[13])+int(stat[14]),int(stat[23])*os.sysconf('SC_PAGE_SIZE'),cmd)
        except (OSError,IndexError):pass
    return result
def status():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/status',timeout=3) as r:return json.load(r)
a=procs();sa=status();t=time.monotonic();time.sleep(10);b=procs();sb=status();dt=time.monotonic()-t
result={'duration_s':dt,'processes':[dict(pid=k,cpu_percent=round((v[0]-a[k][0])/os.sysconf('SC_CLK_TCK')/dt*100,1),rss_mb=round(v[1]/1048576,1),command=v[2]) for k,v in b.items() if k in a],
    'sensors_hz':sb['receive_hz'],'bridge_errors_delta':sb['bridge_errors']-sa['bridge_errors'],
    'sd_errors_delta':sb['hardware']['sd_errors']-sa['hardware']['sd_errors'],
    'sd_dropped_delta':sb['hardware']['sd_queue_dropped']-sa['hardware']['sd_queue_dropped']}
print(json.dumps(result,indent=2))
