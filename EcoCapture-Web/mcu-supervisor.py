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
OPENOCD = ['/opt/openocd/bin/openocd', '-d1', '-s', '/opt/openocd', '-f', 'openocd_gpiod.cfg',
           '-c', 'reset_config srst_only srst_push_pull; init; reset run; shutdown']


def log(text):
    print('mcu-supervisor: ' + text, flush=True)


def link_state():
    """'up', 'down', or None when the web service itself is unreachable (left alone)."""
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=4) as response:
            return 'up' if json.load(response).get('connected') else 'down'
    except (OSError, ValueError):
        return None


def flashing():
    return subprocess.run(['pgrep', '-f', 'flash-mcu.sh'], capture_output=True).returncode == 0


def run(args, timeout):
    subprocess.run(args, check=True, timeout=timeout, capture_output=True)


def recover():
    run(['docker', 'stop', '-t', '15', 'ecocapture-web'], 30)
    run(['systemctl', 'restart', 'arduino-router'], 25)
    for _ in range(15):
        active = subprocess.run(['systemctl', 'is-active', '--quiet', 'arduino-router']).returncode == 0
        if active and os.path.exists('/var/run/arduino-router.sock'):
            break
        time.sleep(1)
    else:
        raise RuntimeError('router did not become ready')
    time.sleep(3)  # let ExecStartPost set RTS/CTS before the MCU boots
    run(OPENOCD, 20)
    run(['docker', 'start', 'ecocapture-web'], 30)


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
            down_since = down_since or now
            if now - down_since >= DOWN_LIMIT_S and now >= next_allowed:
                log('MCU link down for %ds, resetting MCU' % (now - down_since))
                try:
                    recover()
                    log('recovery sequence finished')
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
