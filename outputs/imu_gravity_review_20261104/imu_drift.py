"""How far does the BNO055 NDOF gravity estimate (GRV) wander from the true one, and what it does to LIA.

usage: python imu_drift.py <csv> <can|gnss>
  can : speed from can_signals["Speed"] (km/h, wheel speed)  -- V2 host CSV
  gnss: speed from GPSSpeed (km/h), deduplicated by gnss_itow_ms -- SD/race CSV
"""
import csv, json, sys, math
import numpy as np

path, src = sys.argv[1], sys.argv[2]
G = 9.80665
t = []; raw = []; spd_t = []; spd_v = []; last_itow = None
with open(path, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        h = r.get('imu_raw') or ''
        if len(h) != 92: continue
        ms = int(float(r['mcu_ms']))
        t.append(ms / 1000); raw.append(bytes.fromhex(h))
        if src == 'can':
            c = json.loads(r['can_signals']) if r.get('can_signals') else {}
            if c.get('Speed') is not None: spd_t.append(ms / 1000); spd_v.append(c['Speed'] / 3.6)
        else:
            it = r.get('gnss_itow_ms'); v = r.get('GPSSpeed')
            if it and v and it != last_itow and r.get('GPSFix') in ('3', '3.0', '4'):
                last_itow = it; spd_t.append(ms / 1000); spd_v.append(float(v) / 3.6)
t = np.array(t)
x = np.array([np.frombuffer(b[:44], '<i2') for b in raw], float)
cal = np.array([b[45] for b in raw])
acc = x[:, 0:3] / 100; gyr = x[:, 6:9] / 16; lia = x[:, 16:19] / 100; grv = x[:, 19:22] / 100
order = np.argsort(t); t, acc, gyr, lia, grv, cal = t[order], acc[order], gyr[order], lia[order], grv[order], cal[order]
spd_t = np.array(spd_t); spd_v = np.array(spd_v)
v = np.interp(t, spd_t, spd_v)
dur = t[-1] - t[0]
print(f'rows {len(t)}  span {dur/60:.1f} min  rate {len(t)/dur:.0f} Hz  speed max {spd_v.max()*3.6:.0f} km/h')
print('check acc = lia + grv: median / p99 residual m/s2', np.median(np.abs(acc - lia - grv)).round(2), np.percentile(np.abs(acc - lia - grv), 99).round(2))
accel_cal = (cal >> 2) & 3; sys_cal = cal >> 6; gyro_cal = (cal >> 4) & 3
print('calib share (accel=3, gyro=3, sys=3):', [round(float((c == 3).mean()), 2) for c in (accel_cal, gyro_cal, sys_cal)])

def box(a, n):
    k = np.ones(n) / n
    return np.apply_along_axis(lambda c: np.convolve(c, k, 'same'), 0, a) if a.ndim > 1 else np.convolve(a, k, 'same')

# Stationary: wheel/GNSS speed ~0 and the car is not rocking.
still = (v < 0.5) & (np.linalg.norm(gyr, axis=1) < 3)
still = box(still.astype(float), 200) > 0.999          # 2 s fully still
# Separate stops
stops = []; i = 0
while i < len(t):
    if still[i]:
        j = i
        while j < len(t) and still[j]: j += 1
        if t[j - 1] - t[i] >= 2: stops.append((i, j))
        i = j
    else: i += 1
up_ref = (acc[still] if still.any() else acc).mean(0); up_ref /= np.linalg.norm(up_ref)
if not still.any(): print('no stops: up_ref is the mean accel of the whole drive')
print(f'stops {len(stops)}  still share {still.mean():.2f}  up_ref(sensor) {up_ref.round(3)}  '
      f'mount tilt from sensor Z {math.degrees(math.acos(abs(up_ref[2]))):.1f} deg')

def ang(a, b):
    a = a / np.linalg.norm(a, axis=-1, keepdims=True); b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))

print('\n-- at each stop: fusion gravity (GRV) vs measured gravity (mean acc), and LIA left over')
print('  t[min]  len[s]  GRV-err[deg]  |LIA|[G]  slope-vs-ref[deg]  calib(s/g/a/m)')
for i, j in stops:
    ga = acc[i:j].mean(0); gg = grv[i:j].mean(0)
    li = np.linalg.norm(lia[i:j].mean(0)) / G
    c = cal[(i + j) // 2]
    print(f'  {(t[i]-t[0])/60:6.1f}  {t[j-1]-t[i]:6.0f}  {ang(gg, ga):11.2f}  {li:8.3f}  {ang(ga, up_ref):12.2f}       '
          f'{c>>6}/{c>>4&3}/{c>>2&3}/{c&3}')

# Gravity and car axes that best explain the raw accel given speed and yaw rate
# (closed circuits turn one way on average, so the plain mean accel is not "up").
n = 50
vs = box(v, n); dv = np.gradient(vs, t); dv = box(dv, n)
moving = (v > 3) & (abs(dv) < 1.2 * G) & (t > t[0] + 2) & (t < t[-1] - 2)
up = up_ref.copy()
for it in range(6):
    h = acc - np.outer(acc @ up, up)
    X = dv[moving] - dv[moving].mean(); Y = h[moving] - h[moving].mean(0)
    fwd = (X[:, None] * Y).sum(0) / (X * X).sum(); gain = np.linalg.norm(fwd); fwd /= gain
    left = np.cross(up, fwd)
    yaw = np.radians(box(gyr @ up, n))
    lat_ref = vs * yaw
    if still.sum() > 1000: break          # real stops give gravity directly
    resid = acc - np.outer(dv, fwd) - np.outer(lat_ref, left)
    up = resid[moving].mean(0); up /= np.linalg.norm(up)
print(f'\nup (sensor) {up.round(3)}  tilt from sensor Z {math.degrees(math.acos(abs(up[2]))):.1f} deg')
print(f'forward (sensor) {fwd.round(3)}  left {left.round(3)}  gain {gain:.2f}')

a_ndof = box(lia @ fwd, n) / G;  l_ndof = box(lia @ left, n) / G
a_fixed = box((acc - G * up) @ fwd, n) / G;  l_fixed = box((acc - G * up) @ left, n) / G
ref = dv / G; lref = lat_ref / G
grv_err = ang(grv, up)
print('\n-- moving (>3 m/s): vs dv/dt (long) and v*yaw-rate (lat)')
for name, a, l in (('NDOF LIA (now)', a_ndof, l_ndof), ('fixed gravity', a_fixed, l_fixed)):
    e = (a - ref)[moving]; el = (l - lref)[moving]
    print(f'  {name:16s} long bias {e.mean():+.3f} rms {np.sqrt((e**2).mean()):.3f}  |  lat bias {el.mean():+.3f} rms {np.sqrt((el**2).mean()):.3f}  [G]')
print(f'  GRV vs up while moving: median {np.median(grv_err[moving]):.1f}  p95 {np.percentile(grv_err[moving],95):.1f}  max {grv_err[moving].max():.1f} deg')
print(f'  signal size: |long| p95 {np.percentile(abs(ref[moving]),95):.2f} G  |lat| p95 {np.percentile(abs(lref[moving]),95):.2f} G')

print('\n-- per minute (moving rows) bias [G]: long NDOF / fixed | lat NDOF / fixed | GRV err med [deg] | accel calib')
m0 = t[0]
for k in range(int(dur // 60) + 1):
    sel = moving & (t >= m0 + 60 * k) & (t < m0 + 60 * (k + 1))
    if sel.sum() < 500: continue
    print(f'  {k:3d}  {(a_ndof-ref)[sel].mean():+.3f} / {(a_fixed-ref)[sel].mean():+.3f}  |  {(l_ndof-lref)[sel].mean():+.3f} / {(l_fixed-lref)[sel].mean():+.3f}  |  {np.median(grv_err[sel]):5.1f}  |  {np.bincount(accel_cal[sel], minlength=4).argmax()}')
import os
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.basename(path) + '.drift.npz'), t=t, grv_err=grv_err, a_ndof=a_ndof, a_fixed=a_fixed, ref=ref, l_ndof=l_ndof, l_fixed=l_fixed, lref=lref, v=v, still=still)
