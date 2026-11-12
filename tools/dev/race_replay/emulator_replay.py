"""Drive a stored race through EcoLogger on the Android EMULATOR, at real speed (2026-10-26, ER-13).

Feeds the fixes of race_csv.py's `fixes` CSV to the emulator's GPS one by one (`adb emu geo fix`,
with the speed; this emulator ignores `geo nmea`) and saves a screenshot at the given race
seconds, so the driver screen can be looked at as it was during the race. The app on the
emulator has to be recording already, with the race's lines and class set and laps at 0.

Only the emulator is touched: the serial is checked to be an emulator (emulator-NNNN) and every
adb call names it, so a phone left plugged in is never driven.

  python -I emulator_replay.py <fixes.csv> <start_utc_ms> <goal_utc_ms> <out_dir> [shot_s ...]
      [--serial emulator-5554] [--before 60] [--after 40]

The app takes each fix's time from the emulator's clock, so this runs at real speed
(the 16.5-minute 2026-10-25 Super Cub race: ~18 minutes from 60 s before the start).
"""
import argparse
import csv
import os
import subprocess
import time

ADB = os.path.expandvars(r'%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fixes')
    ap.add_argument('start', type=int)
    ap.add_argument('goal', type=int)
    ap.add_argument('out_dir')
    ap.add_argument('shots', type=float, nargs='*')
    ap.add_argument('--serial', default='emulator-5554')
    ap.add_argument('--before', type=float, default=60)
    ap.add_argument('--after', type=float, default=40)
    args = ap.parse_args()
    if not args.serial.startswith('emulator-'):
        raise SystemExit('only an emulator (emulator-NNNN) may be driven')
    if args.serial.encode() not in subprocess.run([ADB, 'devices'], capture_output=True).stdout:
        raise SystemExit(f'{args.serial} is not running')

    def adb(*a):
        return subprocess.run([ADB, '-s', args.serial, *a], capture_output=True)

    rows = [r for r in csv.DictReader(open(args.fixes, encoding='utf-8'))
            if args.start - args.before * 1000 <= int(r['utc_ms']) <= args.goal + args.after * 1000]
    os.makedirs(args.out_dir, exist_ok=True)
    shots = sorted(args.shots)
    t0_data, t0_wall = int(rows[0]['utc_ms']), time.time()
    for r in rows:
        t = int(r['utc_ms'])
        wait = t0_wall + (t - t0_data) / 1000 - time.time()
        if wait > 0:
            time.sleep(wait)
        # geo fix <longitude> <latitude> <altitude> <satellites> <velocity in knots>
        adb('emu', 'geo', 'fix', r['lon'], r['lat'], '185', '12', f'{float(r["speed_kmh"]) / 1.852:.2f}')
        race = (t - args.start) / 1000
        if shots and race >= shots[0]:
            name = f'race_{int(shots.pop(0)):04d}.png'
            time.sleep(1.2)   # the screen redraws every 0.2 s
            with open(os.path.join(args.out_dir, name), 'wb') as f:
                f.write(adb('exec-out', 'screencap', '-p').stdout)
            print(f'{race:7.1f} s: {name}', flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
