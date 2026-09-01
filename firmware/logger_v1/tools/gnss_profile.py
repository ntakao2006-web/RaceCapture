"""List/select g-firmware GNSS bench profiles via A105. No OTP/NVS writes.

Selection stops/closes SD, waits for matching RAM readback, then restores the
previous logging state. This is a temporary bench setting, lost at reboot.
Close RaceCapture/its guard before comparing profiles. Keep antenna stationary.
"""
import argparse
import json
import time
from rcp_client import Client
from verify_sd_session import wait_state


def select(client, profile, timeout=30):
    profiles = client.query({'getGnssProfiles': None})['getGnssProfiles']['profiles']
    if not any(p['id'] == profile and p['supported'] for p in profiles):
        raise ValueError('Unknown or unsupported profile: ' + profile)
    before = client.query({'getStatus': None})['status']['logging']
    was_logging = before['status'] == 1
    try:
        result = client.query({'setLogging': False})['setLogging']
        if result['rc'] != 1:
            raise RuntimeError(result)
        wait_state(client, lambda s: s['logging']['closed'] and not s['logging']['file'])
        result = client.query({'setGnssProfile': {'id': profile, 'confirm': 'GNSS_PROFILE_TEST'}})['setGnssProfile']
        if result['rc'] != 1:
            raise RuntimeError(result)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            cfg = client.query({'getGnssDiagnostics': None})['getGnssDiagnostics']['configuration']
            if cfg['verified'] and cfg.get('profileId') == profile:
                return cfg
            time.sleep(.2)
        raise TimeoutError('GNSS profile not verified; inspect diagnostics before measurement')
    finally:
        if was_logging:
            result = client.query({'setLogging': True})['setLogging']
            if result['rc'] != 1:
                raise RuntimeError('Failed to resume SD: ' + str(result))
            wait_state(client, lambda s: s['logging']['status'] == 1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['list', 'select'])
    p.add_argument('--port', default='COM8')
    p.add_argument('--profile')
    p.add_argument('--settle-seconds', type=float, default=120,
                   help='Fixed warmup after selection; do not shorten only for profiles that fix quickly')
    args = p.parse_args()
    if args.action == 'select' and (not args.profile or args.settle_seconds < 0):
        p.error('select requires --profile and nonnegative settle time')
    client = Client(args.port)
    try:
        if args.action == 'list':
            print(json.dumps(client.query({'getGnssProfiles': None}), indent=2))
        else:
            cfg = select(client, args.profile)
            print(json.dumps(cfg, indent=2), flush=True)
            end = time.monotonic() + args.settle_seconds
            while time.monotonic() < end:
                time.sleep(min(1, max(0, end-time.monotonic())))
            print(json.dumps(client.query({'getGnssDiagnostics': None}), indent=2), flush=True)
    finally:
        client.close()


if __name__ == '__main__':
    main()
