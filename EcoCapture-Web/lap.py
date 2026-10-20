"""GNSS lap timing on the Linux side: control line, plus optional start and goal lines.

Ported from EcoCapture Core/Navigation.cs: crossings are taken only between
consecutive 3D fixes at most 1 s apart, a line is direction-aware, and laps
shorter than the minimum are ignored. All times are GNSS UTC; the Linux clock
is never used, so a restart of the Web container does not shift lap times.

A line whose travel direction is not known yet works as a circle (geofence).
When the car leaves the circle moving at least LEARN_MIN_KMH, its GNSS heading
becomes the line direction, and the crossing time is taken from the fixes
inside the circle as if the line had been there all along (falling back to the
closest approach when they do not cross it).

After each control or goal pass that line is disarmed until the car is more
than one line width away from it (the idea of RaceCapture's geo trigger), so
GNSS jitter while stopped on the line can never add laps.

Eco-run courses (Honda EMC, Motegi oval) have three lines: a standing start
line, a control line passed every lap, and a goal line on a branch that is
crossed only once after the required laps. With a start line the race clock
and lap 1 begin there (start to the first control pass counts as one lap);
every forward crossing before lap 1 is complete restarts the clock, so the
last one, the actual departure, wins over jitter on the grid. The goal ends
the race: the stretch since the last control pass counts as the final lap
unless it is shorter than the minimum lap (goal right after the control line).
With a required lap count the goal is ignored until the final lap, so a goal
line placed roughly from a map cannot end the race early.
"""
import hashlib
import json
import math
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models import LAP_CHANNELS
from podium import utc_milliseconds

EARTH_M_PER_DEG = 111320.0
MAX_HACC_M = 25.0
MAX_FIX_GAP_MS = 1000
LEARN_MIN_KMH = 5.0
KEEP_LAPS = 500
KEEP_INSIDE = 1200  # fixes kept while inside a direction-less line (2 min at 10 Hz)
TARGETS = ('control', 'start', 'goal')
# Registering a line while standing on it: average the last few seconds of fixes
# (a person on foot at the course walk), unless they spread like a moving car.
HERE_WINDOW_MS = 3000
HERE_MIN_FIXES = 10
HERE_MAX_SPREAD_M = 3.0


class Gate(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    bearing: float | None = Field(default=None, ge=0, lt=360)
    width_m: float = Field(default=30, ge=5, le=200)


class LapLine(BaseModel):
    """The control line (top-level fields, kept for saved settings) and the race options."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    enabled: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    bearing: float | None = Field(default=None, ge=0, lt=360)
    width_m: float = Field(default=30, ge=5, le=200)
    min_lap_s: float = Field(default=10, ge=5, le=7200)
    max_lap_s: float = Field(default=3600, ge=10, le=86400)
    start: Gate | None = None
    goal: Gate | None = None
    total_laps: int | None = Field(default=None, ge=1, le=1000)
    set_at: str | None = None  # when the lines last changed (GNSS time, JST), shown with the QR code

    @model_validator(mode='after')
    def valid(self):
        if self.enabled and (self.lat is None or self.lon is None):
            raise ValueError('Line position required')
        if self.max_lap_s <= self.min_lap_s:
            raise ValueError('max_lap_s must exceed min_lap_s')
        return self

    def gate(self, target):
        if target == 'control':
            return Gate(lat=self.lat, lon=self.lon, bearing=self.bearing, width_m=self.width_m) if self.enabled else None
        return getattr(self, target)


JST = timezone(timedelta(hours=9))


def line_code(line):
    """The lines as one text line for the QR code the Android loggers read
    (android-logger LineCode.kt reads the same format). The Ver.2 GNSS with its
    active antenna is the single reference every phone copies:

      ECOLINES1|c=lat,lon,bearing,width|s=...|g=...|at=<when>|src=Ver.2|id=XXXX

    "-" stands for a missing line or an unknown bearing; id is the first four
    hex digits (upper case) of SHA-1 over the "c=...|s=...|g=..." part.
    Returns (text, id)."""
    def gate(g):
        if g is None:
            return '-'
        bearing = '-' if g.bearing is None else f'{g.bearing:.1f}'
        return f'{g.lat:.7f},{g.lon:.7f},{bearing},{int(round(g.width_m))}'
    lines = '|'.join(f'{key}={gate(line.gate(target))}' for key, target in (('c', 'control'), ('s', 'start'), ('g', 'goal')))
    code = hashlib.sha1(lines.encode('utf-8')).hexdigest()[:4].upper()
    return f'ECOLINES1|{lines}|at={line.set_at or ""}|src=Ver.2|id={code}', code


def offset_m(lat0, lon0, lat, lon):
    return ((lon - lon0) * EARTH_M_PER_DEG * math.cos(math.radians(lat0)), (lat - lat0) * EARTH_M_PER_DEG)


def line_crossing(bearing, half, a, b):
    """Interpolated time when a -> b crosses the line forward within `half` of its centre."""
    rad = math.radians(bearing)
    nx, ny = math.sin(rad), math.cos(rad)
    d0 = a[1] * nx + a[2] * ny
    d1 = b[1] * nx + b[2] * ny
    if not d0 < 0 <= d1:
        return None
    f = -d0 / (d1 - d0)
    px, py = a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
    if abs(px * ny - py * nx) > half:
        return None
    return round(a[0] + (b[0] - a[0]) * f)


class Watch:
    """Crossing detector for one line; runtime state only."""
    def __init__(self, rearm=True):
        self.rearm = rearm
        self.armed = True
        self.inside = []

    def reset(self):
        self.armed = True; self.inside = []

    def observe(self, gate, current):
        """Re-arm once the car is a line width away; runs on every usable fix, even after a gap."""
        if not self.armed:
            self.armed = math.hypot(*offset_m(gate.lat, gate.lon, current[1], current[2])) > gate.width_m
            self.inside = []

    def step(self, gate, previous, current, speed, yaw):
        """previous/current are (utc_ms, lat, lon). Returns (crossing_ms or None, learned bearing or None)."""
        a = (previous[0], *offset_m(gate.lat, gate.lon, previous[1], previous[2]))
        b = (current[0], *offset_m(gate.lat, gate.lon, current[1], current[2]))
        if not self.armed:
            return None, None
        half = gate.width_m / 2
        if gate.bearing is not None:
            at = line_crossing(gate.bearing, half, a, b)
            if at is not None and self.rearm:
                self.armed = False
            return at, None
        if math.hypot(b[1], b[2]) <= half:
            self.inside = (self.inside or [a])[-KEEP_INSIDE:] + [b]
            return None, None
        if not self.inside:
            return None, None
        points, self.inside = self.inside + [b], []
        learned = yaw % 360 if speed is not None and speed >= LEARN_MIN_KMH and yaw is not None else None
        at = None
        if learned is not None:
            for p, q in zip(points, points[1:]):
                at = line_crossing(learned, gate.width_m, p, q) or at  # the last crossing is the departure
        if at is None:
            at = min(points, key=lambda p: math.hypot(p[1], p[2]))[0]
        if self.rearm:
            self.armed = False
        return at, learned


class LapTimer:
    def __init__(self, root):
        self.path = Path(root) / 'lap.json'
        self.error = None
        self.line = LapLine()
        self.state = self.empty_state()
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding='utf-8'))
                self.line = LapLine.model_validate(data.get('line', {}))
                self.state = {**self.empty_state(), **data.get('state', {})}
        except (ValueError, OSError, AttributeError):
            self.line = LapLine(); self.state = self.empty_state()
            self.error = 'ラップ設定を読めません。設定し直してください。'
        self.previous = None    # (utc_ms, lat, lon) of the last usable fix
        self.latest_utc = None  # (utc_ms, monotonic) for the running clocks
        self.last_itow = None
        self.recent = deque(maxlen=60)  # (utc_ms, lat, lon) of usable fixes, for set_here
        self.last_here = None
        self.watches = {'start': Watch(rearm=False), 'control': Watch(), 'goal': Watch()}

    @staticmethod
    def empty_state():
        return {'count': 0, 'last_s': None, 'best_s': None, 'lap_start_ms': None, 'laps': [],
                'race_start_ms': None, 'race_end_ms': None, 'finished': False}

    def save(self):
        temp = self.path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as stream:
            json.dump({'line': self.line.model_dump(), 'state': self.state}, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        temp.replace(self.path)

    def try_save(self):
        try:
            self.save()
        except OSError as exc:
            self.error = f'ラップ記録を保存できません: {exc}'

    def forget_motion(self):
        self.previous = None
        for watch in self.watches.values():
            watch.reset()

    def configure(self, line):
        gates = lambda l: [l.gate(t) for t in TARGETS]
        if gates(line) != gates(self.line) and self.latest_utc is not None:
            stamp = datetime.fromtimestamp(self.latest_utc[0] / 1000, JST).strftime('%Y-%m-%dT%H:%M+09:00')
            line = line.model_copy(update={'set_at': stamp})
        self.line = line; self.error = None
        self.forget_motion()
        self.save()

    def reset(self):
        self.state = self.empty_state()
        self.forget_motion()
        self.save()

    def here_position(self, sample):
        """(lat, lon, fixes averaged, spread in m) for the line being registered here."""
        values = (sample or {}).get('values', {})
        lat, lon = values.get('Lat'), values.get('Lon')
        if lat is None or lon is None:
            raise ValueError('GNSS not fixed')
        fresh = self.latest_utc is not None and time.monotonic() - self.latest_utc[1] < 1.5
        if fresh and self.recent:
            last = self.recent[-1][0]
            points = [p for p in self.recent if last - p[0] <= HERE_WINDOW_MS]
            if len(points) >= HERE_MIN_FIXES:
                mlat = sum(p[1] for p in points) / len(points)
                mlon = sum(p[2] for p in points) / len(points)
                spread = max(math.hypot(*offset_m(mlat, mlon, p[1], p[2])) for p in points)
                if spread <= HERE_MAX_SPREAD_M:
                    return mlat, mlon, len(points), spread
        return lat, lon, 1, None

    def set_here(self, sample, width_m=None, target='control'):
        if target not in TARGETS:
            raise ValueError('Unknown line')
        values = (sample or {}).get('values', {})
        lat, lon, count, spread = self.here_position(sample)
        speed, yaw = values.get('GPSSpeed'), values.get('Yaw')
        # Heading of motion is meaningless at a standstill; learn it on the first pass instead.
        bearing = yaw % 360 if speed is not None and speed >= LEARN_MIN_KMH and yaw is not None else None
        data = self.line.model_dump()
        if target == 'control':
            data.update(enabled=True, lat=lat, lon=lon, bearing=bearing)
            if width_m is not None:
                data['width_m'] = width_m
        else:
            old = data.get(target) or {}
            data[target] = {'lat': lat, 'lon': lon, 'bearing': bearing,
                            'width_m': width_m if width_m is not None else old.get('width_m', 30)}
        self.configure(LapLine.model_validate(data))
        self.last_here = {'target': target, 'fixes': count, 'spread_m': None if spread is None else round(spread, 2)}

    def values(self):
        if not self.line.enabled:
            return dict.fromkeys(LAP_CHANNELS)
        s = self.state
        now_ms = self.latest_utc[0] + (time.monotonic() - self.latest_utc[1]) * 1000 if self.latest_utc else None
        since = lambda start: None if start is None or now_ms is None else max(0.0, (now_ms - start) / 1000)
        minutes = lambda sec: None if sec is None else sec / 60
        if s['finished']:
            elapsed, current = None, s['count']
            race = None if s['race_start_ms'] is None else (s['race_end_ms'] - s['race_start_ms']) / 1000
        else:
            elapsed, current = since(s['lap_start_ms']), s['count'] + 1 if s['lap_start_ms'] is not None else 0
            race = since(s['race_start_ms'])
        total = self.line.total_laps
        return {'LapCount': s['count'], 'CurrentLap': current,
                'LapTime': minutes(s['last_s']), 'BestLap': minutes(s['best_s']), 'ElapsedTime': minutes(elapsed),
                'RaceTime': minutes(race), 'LapsLeft': None if total is None else max(0, total - s['count'])}

    def record_lap(self, at_ms):
        s = self.state
        lap = (at_ms - s['lap_start_ms']) / 1000
        s['count'] += 1; s['last_s'] = lap
        s['best_s'] = lap if s['best_s'] is None else min(s['best_s'], lap)
        s['laps'] = (s['laps'] + [{'n': s['count'], 's': round(lap, 3), 'end_utc_ms': at_ms}])[-KEEP_LAPS:]

    def started(self, at_ms):
        s = self.state
        if s['finished'] or s['count'] > 0:
            return
        s['race_start_ms'] = s['lap_start_ms'] = at_ms  # a later forward crossing (re-start) replaces it
        self.try_save()

    def crossed(self, at_ms):
        s = self.state
        if s['finished'] or (self.line.start is not None and s['race_start_ms'] is None):
            return
        if s['lap_start_ms'] is None:
            s['lap_start_ms'] = at_ms
            if s['race_start_ms'] is None:
                s['race_start_ms'] = at_ms
        else:
            lap = (at_ms - s['lap_start_ms']) / 1000
            if lap < self.line.min_lap_s:
                return
            if lap <= self.line.max_lap_s:
                self.record_lap(at_ms)
            # A gap longer than any real lap (pit stop, next day) restarts the
            # running lap without counting it; totals stay until an explicit reset.
            s['lap_start_ms'] = at_ms
        self.try_save()

    def finished(self, at_ms):
        s = self.state
        if s['finished'] or s['lap_start_ms'] is None:
            return
        # The goal is only reached on the final lap. A goal line drawn from a map
        # too close to the circuit must not end the race on an ordinary lap.
        if self.line.total_laps is not None and s['count'] < self.line.total_laps - 1:
            return
        if (at_ms - s['lap_start_ms']) / 1000 >= self.line.min_lap_s:
            self.record_lap(at_ms)
        s['finished'] = True; s['race_end_ms'] = at_ms; s['lap_start_ms'] = None
        self.try_save()

    def update(self, sample):
        values = sample.get('values', {})
        itow = sample.get('gnss_itow_ms')
        if itow is None or itow == self.last_itow:
            return self.values()
        self.last_itow = itow
        utc = utc_milliseconds(sample)
        lat, lon = values.get('Lat'), values.get('Lon')
        hacc = sample.get('gnss_hacc_m')
        if utc is None or lat is None or lon is None or (hacc is not None and hacc > MAX_HACC_M):
            self.previous = None  # keep each line's disarm: a poor fix must not re-arm it
            for watch in self.watches.values():
                watch.inside = []
            return self.values()
        self.latest_utc = (utc, time.monotonic())
        self.recent.append((utc, lat, lon))
        if not self.line.enabled:
            return self.values()
        previous, self.previous = self.previous, (utc, lat, lon)
        for target in TARGETS:
            if (gate := self.line.gate(target)) is not None:
                self.watches[target].observe(gate, self.previous)
        if previous is None or not 0 < utc - previous[0] <= MAX_FIX_GAP_MS:
            for watch in self.watches.values():
                watch.inside = []
            return self.values()
        learned_any = False
        for target, event in (('start', self.started), ('control', self.crossed), ('goal', self.finished)):
            gate = self.line.gate(target)
            if gate is None:
                continue
            at, learned = self.watches[target].step(gate, previous, self.previous, values.get('GPSSpeed'), values.get('Yaw'))
            if learned is not None:
                self.learn(target, learned); learned_any = True
            if at is not None:
                event(at)
        if learned_any:
            self.try_save()
        return self.values()

    def learn(self, target, bearing):
        if target == 'control':
            self.line = self.line.model_copy(update={'bearing': bearing})
        else:
            self.line = self.line.model_copy(update={target: getattr(self.line, target).model_copy(update={'bearing': bearing})})

    def public(self):
        return {'line': self.line.model_dump(), 'values': self.values(), 'error': self.error,
                'laps': self.state['laps'][-20:], 'running': self.state['lap_start_ms'] is not None,
                'finished': self.state['finished'], 'here': self.last_here}


def line_qr(line):
    """The QR code of line_code as inline SVG, with what the screens show next to it."""
    import segno
    text, code = line_code(line)
    svg = segno.make(text, error='m').svg_inline(scale=6, border=4, dark='#000', light='#fff')
    unknown = [name for name, target in (('コントロール', 'control'), ('スタート', 'start'), ('ゴール', 'goal'))
               if line.gate(target) is not None and line.gate(target).bearing is None]
    return {'text': text, 'id': code, 'at': line.set_at, 'svg': svg, 'unknown_bearing': unknown}
