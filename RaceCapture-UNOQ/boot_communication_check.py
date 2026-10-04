"""Bounded boot-only recovery; never reset after data reception has begun."""
import json,subprocess,time,urllib.request
from pathlib import Path

MARKER=Path('/run/ecocapture-communication-verified')
def read_status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/status',timeout=3) as response:return json.load(response)
    except Exception:return None
def can_recover(status):
    return bool(status and status.get('received')==0
        and not status.get('logging',{}).get('active')
        and not status.get('hardware',{}).get('sd_logging')
        and 'method logger.status not available' in (status.get('error') or ''))
def wait_received(seconds=40):
    end=time.monotonic()+seconds;latest=None
    while time.monotonic()<end:
        latest=read_status()
        if latest and latest.get('connected') and latest.get('received',0)>0:return latest
        # Even stale samples prove this is no longer initial boot acquisition.
        if latest and (latest.get('received',0)>0 or latest.get('logging',{}).get('active')):return latest
        time.sleep(1)
    return latest
def main():
    if MARKER.exists():
        print('Already verified this boot; no reset.',flush=True);return
    for attempt in range(3):
        status=wait_received()
        if status and status.get('connected') and status.get('received',0)>0:
            MARKER.write_text('verified\n');print('MCU telemetry verified.',flush=True);return
        if attempt==2 or not can_recover(status):
            raise SystemExit('No safe boot recovery available; no further resets.')
        print(f'Boot handshake unavailable; recovery attempt {attempt+1}/2.',flush=True)
        subprocess.run(['systemctl','restart','arduino-router.service'],check=True,timeout=120)
        subprocess.run(['systemctl','restart','ecocapture-mcu-start.service'],check=True,timeout=30)
        subprocess.run(['systemctl','restart','ecocapture-web-start.service'],check=True,timeout=60)
if __name__=='__main__':main()
