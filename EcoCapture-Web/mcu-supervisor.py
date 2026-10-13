#!/usr/bin/python3
"""Restore the Linux<->MCU Bridge when it stays down (runs as root on the UNO Q host).

After an MCU-internal reset (loop watchdog, IWDG, SYSRESETREQ) while Linux is
polling, the STM32 keeps acquiring and writing SD but the UART link to Linux
does not come back. The sequence used by flash-mcu.sh (web stop -> router
restart -> NRST reset -> web start) restores it, so repeat that here.
"""
import json
import os
import subprocess
import time
import urllib.request

STATUS_URL = 'http://127.0.0.1:8080/api/status'
POLL_S = 5
DOWN_LIMIT_S = int(os.environ.get('MCU_SUPERVISOR_DOWN_S', '30'))
COOLDOWN_S = int(os.environ.get('MCU_SUPERVISOR_COOLDOWN_S', '120'))
BACKOFF_S = 600
STARTUP_GRACE_S = 120
RECOVERY = ['sh', '/home/arduino/EcoCapture-Web/flash-mcu.sh', '--recover']


def log(text):
    print('mcu-supervisor: ' + text, flush=True)


def link_state():
    """'up', 'down', or None when the web service itself is unreachable (left alone)."""
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=4) as response:
            state = json.load(response)
            if not isinstance(state, dict) or type(state.get('connected')) is not bool:
                return None
            return 'up' if state['connected'] else 'down'
    except (OSError, ValueError):
        return None


def flashing():
    return subprocess.run(['pgrep', '-f', 'flash-mcu.sh'], capture_output=True).returncode == 0


def recover():
    # The helper holds the same flock as firmware updates. A process-name check
    # alone cannot prevent a flash from starting after the check.
    # Cover the helper's per-stage deadlines (up to ~148 s plus Docker startup).
    result = subprocess.run(RECOVERY, timeout=180, capture_output=True, text=True)
    if result.returncode == 75:
        return False
    if result.returncode:
        raise RuntimeError('recovery exit %d: %s' % (result.returncode, result.stderr[-2000:]))
    return True


def main():
    time.sleep(STARTUP_GRACE_S)
    log('watching %s (down limit %ds)' % (STATUS_URL, DOWN_LIMIT_S))
    down_since = None
    next_allowed = 0.0
    failures = 0
    while True:
        now = time.monotonic()
        state = None if flashing() else link_state()
        if state == 'up':
            if failures:
                log('link restored')
            down_since, failures = None, 0
        elif state == 'down':
            if down_since is None:
                down_since = now
            if now - down_since >= DOWN_LIMIT_S and now >= next_allowed:
                log('MCU link down for %ds, resetting MCU' % (now - down_since))
                try:
                    attempted = recover()
                    if not attempted:
                        log('maintenance busy; recovery deferred')
                        down_since = None
                        time.sleep(POLL_S)
                        continue
                    log('recovery sequence finished; waiting for live reception')
                except (subprocess.SubprocessError, OSError, RuntimeError) as error:
                    log('recovery failed: %s' % error)
                failures += 1
                next_allowed = time.monotonic() + (BACKOFF_S if failures >= 3 else COOLDOWN_S)
                down_since = None
        else:
            down_since = None
        time.sleep(POLL_S)


if __name__ == '__main__':
    main()
