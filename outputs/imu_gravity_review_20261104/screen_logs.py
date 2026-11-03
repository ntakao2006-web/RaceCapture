"""Screen V2 eMMC CSVs: duration, speed, how the IMU sat (gravity direction per minute)."""
import csv, glob, math, os, sys
import numpy as np

STEP = 100  # every 100th row = 1 Hz
out = []
for path in sorted(glob.glob(os.path.join(sys.argv[1], '*.csv'))):
    with open(path, encoding='utf-8', errors='replace') as f:
        rd = csv.reader(f)
        hdr = next(rd); ix = {k: i for i, k in enumerate(hdr)}
        rows = []
        for n, r in enumerate(rd):
            if n % STEP: continue
            try:
                a = [float(r[ix['AccelX']]), float(r[ix['AccelY']]), float(r[ix['AccelZ']])]
            except (ValueError, IndexError): continue
            sp = r[ix['GPSSpeed']]; cs = r[ix['Speed']] if 'Speed' in ix else ''
            rows.append((int(float(r[ix['mcu_ms']])) / 1000, a, float(sp) if sp else np.nan, float(cs) if cs else np.nan, r[ix['imu_calibration']]))
    if len(rows) < 30:
        out.append(f'{os.path.basename(path)[4:19]}  short ({len(rows)} s)'); continue
    t = np.array([r[0] for r in rows]); a = np.array([r[1] for r in rows]); gs = np.array([r[2] for r in rows]); cs = np.array([r[3] for r in rows])
    spd = np.where(np.isnan(cs), gs, cs)
    mov = np.nan_to_num(spd) > 10
    # per-minute gravity direction (low-passed accel) -> mount changes
    dirs = []
    for k in range(0, len(a), 60):
        m = a[k:k + 60].mean(0); dirs.append(m / np.linalg.norm(m))
    dirs = np.array(dirs)
    up = a.mean(0); up /= np.linalg.norm(up)
    spread = np.degrees(np.arccos(np.clip(dirs @ up, -1, 1)))
    tilt = math.degrees(math.acos(abs(up[2])))
    out.append(f'{os.path.basename(path)[4:19]}  {(t[-1]-t[0])/60:6.1f} min  vmax {np.nanmax(spd) if np.isfinite(spd).any() else float("nan"):5.0f}  '
               f'moving {mov.mean():.2f}  up {up.round(2)}  tilt {tilt:4.1f}  per-min dir spread max {spread.max():4.1f}  '
               f'can {"y" if np.isfinite(cs).any() else "n"}')
    print(out[-1], flush=True)
