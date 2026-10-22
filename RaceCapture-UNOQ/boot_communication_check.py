"""Bounded boot-only recovery; never reset after data reception has begun."""
import json,subprocess,time,urllib.request
from pathlib import Path

MARKER=Path('/run/ecocapture-communication-verified')
# The initial handshake failed on every power-up measured (5 of 5, 2026-10-20) and
# waiting the full 40 s before recovering cost that much telemetry time. After a
# good start data arrives about 3 s after the containers start, so the missing
# method for this long in a row is taken as the failure.
FAILING_FOR_S=10
def read_status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/status',timeout=3) as response:return json.load(response)
    except Exception:return None
def can_recover(status):
    return bool(status and status.get('received')==0
        and not status.get('logging',{}).get('active')
        and not status.get('hardware',{}).get('sd_logging')
        and 'method logger.status not available' in (status.get('error') or ''))
def wait_received(seconds=40,failing_for=FAILING_FOR_S):
    end=time.monotonic()+seconds;latest=None;failing_since=None
    while time.monotonic()<end:
        latest=read_status()
        if latest and latest.get('connected') and latest.get('received',0)>0:return latest
        # Even stale samples prove this is no longer initial boot acquisition.
        if latest and (latest.get('received',0)>0 or latest.get('logging',{}).get('active')):return latest
        if can_recover(latest):
            failing_since=failing_since or time.monotonic()
            if time.monotonic()-failing_since>=failing_for:return latest
        else:failing_since=None
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
        # The router then takes ~32 s to stop (it hangs in the kernel closing ttyHS1).
        # Clearing RTS/CTS first with stty was tried on 2026-10-20: stty hung on the
        # same tty, the timeout escaped and no recovery ran at all. Do not add it back.
        subprocess.run(['systemctl','restart','arduino-router.service'],check=True,timeout=120)
        subprocess.run(['systemctl','restart','ecocapture-mcu-start.service'],check=True,timeout=30)
        subprocess.run(['systemctl','restart','ecocapture-web-start.service'],check=True,timeout=60)
if __name__=='__main__':main()
