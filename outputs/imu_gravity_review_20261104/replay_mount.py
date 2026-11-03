"""Replay a V2 eMMC CSV through EcoCapture-Web/imu_mount.py as the logger would run it live,
and compare its LongAccel/LatAccel with the speed-derived reference (and with BNO055 NDOF).

usage: python replay_mount.py LOG.csv [--mount state.json]
"""
import csv, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'EcoCapture-Web'))
from imu_mount import ImuMount, G

path = sys.argv[1]
mount = ImuMount()
if '--mount' in sys.argv: mount.load(json.loads(Path(sys.argv[sys.argv.index('--mount') + 1]).read_text()))
t = []; out = []; lia = []; spd = []; gyr = []; ups = []; last_itow = None; calib_events = 0; last_up = None
with open(path, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        h = r.get('imu_raw') or ''
        if len(h) != 92: continue
        x = np.frombuffer(bytes.fromhex(h)[:44], '<i2').astype(float)
        it = r.get('gnss_itow_ms'); v = r.get('GPSSpeed'); fix = r.get('GPSFix') in ('3', '4')
        can = json.loads(r['can_signals']) if r.get('can_signals') else {}
        speed = can.get('Speed') if can.get('Speed') is not None else (float(v) if v and fix else None)
        if it and it != last_itow:
            last_itow = it
            mount.on_fix(int(it), float(v) / 3.6 if v and fix else None, float(r['Yaw']) if r.get('Yaw') and fix else None)
        car = mount.add(list(x[0:3] / 100), list(x[6:9] / 16), speed)
        if mount.up is not None and mount.up is not last_up: calib_events += 1; last_up = mount.up
        t.append(int(float(r['mcu_ms'])) / 1000); out.append(car if car else (np.nan,) * 3)
        lia.append(x[16:19] / 100); spd.append((speed or 0) / 3.6); gyr.append(x[6:9] / 16)
t = np.array(t); out = np.array(out, float); lia = np.array(lia); v = np.array(spd); gyr = np.array(gyr)
print(f'rows {len(t)}  {(t[-1]-t[0])/60:.1f} min  up updates {calib_events}')
print('final state', json.dumps(mount.public(), ensure_ascii=False))

def box(a, n=50):
    k = np.ones(n) / n
    return np.convolve(a, k, 'same')
up = np.array(mount.up); f = np.array(mount.forward()); left = np.cross(up, f)
vs = box(v); dv = box(np.gradient(vs, t)); ref = dv / G
lref = vs * np.radians(box(gyr @ up)) / G
ok = (v > 3) & (abs(dv) < 1.2 * G) & np.isfinite(out[:, 0])
ndl = box(lia @ f) / G; ndt = box(lia @ -left) / G     # NDOF, projected on the same final axes
lo = box(np.nan_to_num(out[:, 0])) ; la = box(np.nan_to_num(out[:, 1]))
print(f'moving rows with output {ok.sum()} ({ok.mean():.2f})')
for name, a, l in (('NDOF (BNO055)', ndl, ndt), ('imu_mount', lo, la)):
    e = (a - ref)[ok]; el = (l + lref)[ok]   # LatAccel is + to the right, the reference + to the left
    print(f'  {name:14s} long bias {e.mean():+.3f} rms {np.sqrt((e**2).mean()):.3f} p95 {np.percentile(abs(e),95):.3f} | '
          f'lat bias {el.mean():+.3f} rms {np.sqrt((el**2).mean()):.3f} p95 {np.percentile(abs(el),95):.3f}  [G]')
vert = out[:, 2][ok & np.isfinite(out[:, 2])]
print(f'  VertAccel mean {np.mean(vert):+.3f} G (0 = gravity removed)')
