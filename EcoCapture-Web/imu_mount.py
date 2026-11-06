"""How the logger sits in the car: BNO055 sensor axes -> the car's longitudinal /
lateral / vertical G, the same method as the Android logger (android-logger Mount.kt).

BNO055's own linear acceleration (NDOF) re-estimates gravity at every moment and is
pulled off by braking and cornering: in the October 2026 drives it was right at rest
but about ±0.1 G (up to 0.35 G) off while driving (outputs/imu_gravity_review_20261104).
Here gravity is fixed instead:

- Up (1 G): the mean raw accelerometer reading while the car stands still (speed
  < 1 km/h, gyro < 2 °/s, steady for 2 s), re-taken at each stop and blended in. More
  than 10° away means the logger was re-mounted: start over. A level taken from the
  Web screen is kept fixed (a stop that disagrees by more than 10° shows as moved).
- Forward: starts as the BNO055 +X axis and is then learned from GNSS: on straight
  stretches the horizontal accel between two fixes about 1 s apart, weighted by the
  speed change, is summed, so the sum points forward. Turning the logger in place
  (same up, another forward) is not detected: reset the calibration after moving it.
- The logger is taken out and put back between drives, a few degrees off each time.
  So after each start (power on, EcoCapture restart) the first still level replaces
  the saved one instead of being blended in, and the saved forward is kept only as a
  light start (weight FORWARD_KEEP, a few seconds of braking): the first accelerations
  and brakes of the new drive decide it.

Output in G: LongAccel + accelerating, LatAccel + towards the car's right, VertAccel
+ up with gravity removed (0 at rest). Road slope is not removed: on a 5 % grade
LongAccel reads about 0.05 G.

The three outputs are low-passed (2nd-order Butterworth, 2 Hz, about 0.1 s behind):
the logger shakes with the car at 20-50 Hz (NCEC 2026-11-06: 29 Hz at idle = the
engine's 2nd order, about 40 Hz on the road, over 85 % of the accel power above
10 Hz), which made the G ball jump when the screens pick one 100 Hz row about every
0.1 s. The filter runs on the raw accel in sensor axes, so the calibration can
change without a jump; AccelX/Y/Z and imu_raw stay unfiltered. vehicle() itself
is the unfiltered projection.
"""
import json
import math
import os
import struct
from collections import deque
from pathlib import Path

G = 9.80665
BUCKET_ROWS = 10           # the calibration works on 0.1 s means of the 100 Hz rows
STILL_ROWS = 20            # 2 s of 0.1 s means
MOVED_DEG = 10.0
MIN_FORWARD_WEIGHT = 3.0   # about a dozen 0.5 m/s² speed changes
FORWARD_KEEP = 10.0        # saved forward weight kept at each start: about 10 s at 1 m/s² of speed change
FIX_MS = 1000              # GNSS fixes used for learning: about 1 s apart (10 Hz receiver)
ROW_HZ = 100.0             # BNO055 rows (the STM32 reads every 10 ms; NDOF updates accel at 100 Hz)
LOWPASS_HZ = 2.0           # G output filter: 5 Hz shook visibly, 1.5 Hz lags 0.15 s
GAP_MS = 200               # a longer gap between rows starts the filter again from the new row


class LowPass:
    """2nd-order Butterworth low-pass (bilinear) on a 3-vector, started at the first row so
    there is no transient from zero (gravity is in the input)."""
    def __init__(self, fc=LOWPASS_HZ, fs=ROW_HZ):
        k = math.tan(math.pi * fc / fs); q = math.sqrt(2.0); n = 1.0 / (1.0 + q * k + k * k)
        self.b0 = k * k * n; self.b1 = 2.0 * self.b0
        self.a1 = 2.0 * (k * k - 1.0) * n; self.a2 = (1.0 - q * k + k * k) * n
        self.reset()

    def reset(self):
        self.state = None  # per axis: x[n-1], x[n-2], y[n-1], y[n-2]

    def __call__(self, x):
        if self.state is None:
            self.state = [[v, v, v, v] for v in x]
            return list(x)
        out = []
        for v, s in zip(x, self.state):
            y = self.b0 * (v + s[1]) + self.b1 * s[0] - self.a1 * s[2] - self.a2 * s[3]
            s[1] = s[0]; s[0] = v; s[3] = s[2]; s[2] = y
            out.append(y)
        return out


def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def norm(a): return math.sqrt(dot(a, a))
def unit(a): n = norm(a); return [a[0] / n, a[1] / n, a[2] / n]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def horizontal(a, up): d = dot(a, up); return [a[i] - d * up[i] for i in range(3)]
def angle_deg(a, b): return math.degrees(math.acos(max(-1.0, min(1.0, dot(a, b) / (norm(a) * norm(b))))))


class ImuMount:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.error = None
        self.clear(save=False)
        if self.path and self.path.exists():
            try:
                self.load(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError, OSError, TypeError, KeyError, IndexError, ZeroDivisionError):
                self.clear(save=False)
                self.error = '取付の校正を読めませんでした。停車中に自動で取り直します。'
        self.new_mounting()

    def new_mounting(self):
        """A new start: the logger may have been put back slightly differently. The first still
        level replaces the saved up, and the saved forward only starts the learning."""
        self.fresh = self.up is not None and not self.manual
        if self.forward_weight > FORWARD_KEEP:
            k = FORWARD_KEEP / self.forward_weight
            self.forward_sum = [v * k for v in self.forward_sum]; self.forward_weight = FORWARD_KEEP
            self._changed()

    # -- state ----------------------------------------------------------------
    def clear(self, save=True):
        self.fresh = False; self.up = None; self.g = G; self.manual = False; self.moved = False
        self.forward_sum = [0.0, 0.0, 0.0]; self.forward_weight = 0.0
        self.restart()
        self._changed()
        if save: self.save()

    def restart(self):
        """Forget the short-term buffers (MCU restart, new SD file); the calibration stays."""
        self.bucket = [0.0] * 6; self.bucket_n = 0; self.bucket_speed = None
        self.window = deque(maxlen=STILL_ROWS)   # 0.1 s mean accels, always kept (manual level)
        self.still_rows = 0
        self.interval = [0.0, 0.0, 0.0]; self.interval_n = 0
        self.last_fix = None  # (itow_ms, speed m/s, heading °)
        self.pvt_itow = None
        self.lowpass = LowPass(); self.last_row_ms = None

    def load(self, data):
        up = data.get('up')
        self.up = unit([float(v) for v in up]) if up else None
        self.g = float(data.get('g') or G)
        self.manual = bool(data.get('manual')) and self.up is not None
        self.moved = False
        self.forward_sum = [float(v) for v in data.get('forward_sum') or (0, 0, 0)][:3]
        self.forward_weight = float(data.get('forward_weight') or 0)
        self._changed()

    def _changed(self):
        self.snapshot = None; self.axes = None; self.dirty = True

    def state(self):
        """Everything needed to continue from here (saved file, the log's imu_mount column, sd_decode --mount)."""
        if self.snapshot is None:
            r = lambda v: [round(x, 5) for x in v] if v else None
            f = self.forward()
            self.snapshot = {'up': r(self.up), 'g': round(self.g, 4), 'manual': self.manual, 'moved': self.moved,
                             'forward': r(f), 'forward_sum': r(self.forward_sum), 'forward_weight': round(self.forward_weight, 4),
                             'learned': self.forward_learned}
        return self.snapshot

    def save(self):
        if not self.path: return
        temp = self.path.with_suffix('.tmp')
        try:
            with temp.open('w', encoding='utf-8') as stream:
                json.dump(self.state(), stream, allow_nan=False)
                stream.flush(); os.fsync(stream.fileno())
            temp.replace(self.path)
            self.dirty = False; self.error = None
        except OSError as exc:
            self.error = f'取付の校正を保存できません: {exc}'

    # -- input ----------------------------------------------------------------
    def add(self, accel, gyro, speed_kmh, ms=None):
        """One 100 Hz row: raw accel (m/s², gravity included), gyro (°/s), speed (km/h, CAN or GNSS) if known,
        and the row's MCU time (ms) when known, so a gap restarts the filter.
        Returns the low-passed (LongAccel, LatAccel, VertAccel) in G, or None before the 1 G calibration."""
        if ms is not None:
            if self.last_row_ms is not None and (ms - self.last_row_ms) % 2**32 > GAP_MS: self.lowpass.reset()
            self.last_row_ms = ms
        smooth = self.lowpass(accel)
        for i in range(3):
            self.bucket[i] += accel[i]; self.bucket[3 + i] += gyro[i]; self.interval[i] += accel[i]
        self.bucket_n += 1; self.interval_n += 1
        self.bucket_speed = speed_kmh
        if self.bucket_n >= BUCKET_ROWS:
            n = self.bucket_n
            self._row([v / n for v in self.bucket[:3]], [v / n for v in self.bucket[3:]], self.bucket_speed)
            self.bucket = [0.0] * 6; self.bucket_n = 0
        return self.vehicle(smooth)

    def _row(self, accel, gyro, speed_kmh):
        self.window.append(accel)
        still = speed_kmh is not None and speed_kmh < 1.0 and norm(gyro) < 2.0
        self.still_rows = self.still_rows + 1 if still else 0
        if self.still_rows < STILL_ROWS: return
        self.still_rows = 0  # next sample after another 2 s
        mean = self.steady_mean()
        if mean is None: return
        u = unit(mean)
        if self.manual:
            moved = angle_deg(self.up, u) > MOVED_DEG
            if moved != self.moved: self.moved = moved; self._changed()
            return
        if self.up is None or angle_deg(self.up, u) > MOVED_DEG:
            # First calibration, or the logger was re-mounted: start over.
            self.up = u; self.g = norm(mean); self.forward_sum = [0.0, 0.0, 0.0]; self.forward_weight = 0.0
        elif self.fresh:
            # First stop since the start: put back a few degrees off, take this level as it is.
            self.up = u; self.g = norm(mean)
        else:
            self.up = unit([self.up[i] * 0.8 + u[i] * 0.2 for i in range(3)]); self.g = self.g * 0.8 + norm(mean) * 0.2
        self.fresh = False
        self._changed()

    def on_pvt(self, nav):
        """The receiver's UBX NAV-PVT payload (92 bytes) as often as it is seen, or None when there is none:
        each new 3D fix goes to on_fix (ground speed, heading of motion)."""
        if nav is None or nav[20] < 3 or not nav[21] & 1:
            if self.last_fix is not None: self.on_fix(0, None, None)
            self.pvt_itow = None
            return
        itow = struct.unpack_from('<I', nav)[0]
        if itow == self.pvt_itow: return
        self.pvt_itow = itow
        self.on_fix(itow, struct.unpack_from('<i', nav, 60)[0] / 1000, struct.unpack_from('<i', nav, 64)[0] * 1e-5)

    def on_fix(self, itow_ms, speed_ms, heading_deg):
        """Each new GNSS fix (speed m/s, heading of motion °); None speed when there is no fix."""
        if speed_ms is None:
            self.last_fix = None; self.interval = [0.0, 0.0, 0.0]; self.interval_n = 0
            return
        prev = self.last_fix
        if prev is not None:
            dt_ms = (itow_ms - prev[0]) % 604800000
            if dt_ms < FIX_MS - 50: return  # keep summing the accel until about 1 s has passed
        n = self.interval_n
        mean = [v / n for v in self.interval] if n else None
        self.interval = [0.0, 0.0, 0.0]; self.interval_n = 0
        self.last_fix = (itow_ms, speed_ms, heading_deg)
        if prev is None or mean is None or n < 50: return
        dt = dt_ms / 1000
        if not 0.5 <= dt <= 1.6: return
        if speed_ms < 2.0 or prev[1] < 2.0: return
        if heading_deg is None or prev[2] is None: return
        turn = abs(heading_deg - prev[2]) % 360
        if turn > 180: turn = 360 - turn
        if turn / dt > 4.0: return  # only straight driving: no centripetal part
        dvdt = (speed_ms - prev[1]) / dt
        if abs(dvdt) < 0.3 or self.up is None: return
        h = horizontal(mean, self.up)
        for i in range(3): self.forward_sum[i] += h[i] * dvdt
        self.forward_weight += dvdt * dvdt
        self._changed()

    def level_now(self):
        """Take 1 G from the last 2 s and keep it fixed; False when the logger was not steady."""
        mean = self.steady_mean()
        if mean is None: return False
        u = unit(mean)
        if self.up is None or angle_deg(self.up, u) > MOVED_DEG:
            self.forward_sum = [0.0, 0.0, 0.0]; self.forward_weight = 0.0  # re-mounted: learn forward again
        self.up = u; self.g = norm(mean); self.manual = True; self.moved = False; self.fresh = False
        self._changed(); self.save()
        return True

    def steady_mean(self):
        if len(self.window) < STILL_ROWS: return None
        n = len(self.window)
        mean = [sum(a[i] for a in self.window) / n for i in range(3)]
        steady = all(math.sqrt(sum((a[i] - mean[i]) ** 2 for a in self.window) / n) < 0.08 for i in range(3))
        if not steady or abs(norm(mean) - G) > 0.6: return None
        return mean

    # -- output ---------------------------------------------------------------
    @property
    def forward_learned(self):
        return self.forward_weight >= MIN_FORWARD_WEIGHT

    def forward(self):
        if self.up is None: return None
        if self.forward_learned:
            f = horizontal(self.forward_sum, self.up)
            if norm(f) > 1e-6: return unit(f)
        # Not learned yet: the BNO055 +X axis is meant to point forward.
        for guess in ([1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]):
            h = horizontal(guess, self.up)
            if norm(h) > 0.3: return unit(h)
        return None

    def vehicle(self, accel):
        if self.axes is None:
            f = self.forward()
            self.axes = (f, cross(f, self.up), self.up) if f else ()
        if not self.axes: return None
        f, r, u = self.axes
        return dot(accel, f) / G, dot(accel, r) / G, (dot(accel, u) - self.g) / G

    def public(self):
        """For the Web screen: the calibration as words, the tilt and how far forward is from the IMU X axis."""
        s = self.state()
        up = ('1G：まだ（停車中に自動で取るか、下のボタンで）' if self.up is None else
              '1G：手動で取った値。ただし今の向きと10°以上違います（付け直した？）' if self.manual and self.moved else
              '1G：手動で取った値' if self.manual else '1G：停車中に自動で取った値')
        tilt = round(angle_deg(self.up, [0.0, 0.0, 1.0]), 1) if self.up else None
        offset = None
        if self.up is not None:
            x = horizontal([1.0, 0.0, 0.0], self.up)
            if norm(x) > 0.3:
                f = self.forward(); offset = round(math.degrees(math.atan2(dot(cross(unit(x), f), self.up), dot(unit(x), f))))
        side = None if offset is None else 'IMUのX軸とほぼ同じ向き' if abs(offset) < 3 else f'IMUのX軸から{"左" if offset > 0 else "右"}へ{abs(offset)}°'
        fwd = ('' if self.up is None else
               f'　前方：走行中にGNSSで学習済み（{side}）' if self.forward_learned and side else
               '　前方：走行中にGNSSで学習済み' if self.forward_learned else
               '　前方：IMUのX軸を前と仮定中（加速・減速すると学習）')
        return {**s, 'message': up + fwd, 'tilt_deg': tilt, 'forward_from_x_deg': offset, 'error': self.error}
