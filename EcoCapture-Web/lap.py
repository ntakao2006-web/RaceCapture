"""GNSS start/finish lap timing on the Linux side.

Ported from EcoCapture Core/Navigation.cs: crossings are taken only between
consecutive 3D fixes at most 1 s apart, the line is direction-aware, and laps
shorter than the minimum are ignored. All times are GNSS UTC; the Linux clock
is never used, so a restart of the Web container does not shift lap times.

Without a known travel direction the line is a circle (geofence) and the lap
is taken at the closest approach; the heading at that pass is then saved as
the line direction.

After each pass the line is disarmed until the car is more than one line
width away from it (the idea of RaceCapture's geo trigger), so GNSS jitter
while stopped on the line can never add laps, whatever the minimum lap time.
"""
import json
import math
import os
import time
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models import LAP_CHANNELS
from podium import utc_milliseconds

EARTH_M_PER_DEG = 111320.0
MAX_HACC_M = 25.0
MAX_FIX_GAP_MS = 1000
LEARN_MIN_KMH = 5.0
KEEP_LAPS = 500


class LapLine(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    enabled: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    bearing: float | None = Field(default=None, ge=0, lt=360)
    width_m: float = Field(default=30, ge=5, le=200)
    min_lap_s: float = Field(default=10, ge=5, le=7200)
    max_lap_s: float = Field(default=3600, ge=10, le=86400)

    @model_validator(mode='after')
    def valid(self):
        if self.enabled and (self.lat is None or self.lon is None):
            raise ValueError('Line position required')
        if self.max_lap_s <= self.min_lap_s:
            raise ValueError('max_lap_s must exceed min_lap_s')
        return self


def offset_m(lat0, lon0, lat, lon):
    return ((lon - lon0) * EARTH_M_PER_DEG * math.cos(math.radians(lat0)), (lat - lat0) * EARTH_M_PER_DEG)


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
        self.previous = None    # (utc_ms, x, y) of the last usable fix
        self.inside = None      # closest approach while inside the geofence
        self.latest_utc = None  # (utc_ms, monotonic) for the running lap clock
        self.last_itow = None
        self.armed = True       # False from a pass until the car is a line width away

    @staticmethod
    def empty_state():
        return {'count': 0, 'last_s': None, 'best_s': None, 'lap_start_ms': None, 'laps': []}

    def save(self):
        temp = self.path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as stream:
            json.dump({'line': self.line.model_dump(), 'state': self.state}, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        temp.replace(self.path)

    def configure(self, line):
        self.line = line; self.previous = None; self.inside = None; self.error = None; self.armed = True
        self.save()

    def reset(self):
        self.state = self.empty_state(); self.previous = None; self.inside = None
        self.save()

    def set_here(self, sample, width_m=None):
        values = (sample or {}).get('values', {})
        lat, lon = values.get('Lat'), values.get('Lon')
        if lat is None or lon is None:
            raise ValueError('GNSS not fixed')
        speed, yaw = values.get('GPSSpeed'), values.get('Yaw')
        # Heading of motion is meaningless at a standstill; learn it on the first pass instead.
        bearing = yaw % 360 if speed is not None and speed >= LEARN_MIN_KMH and yaw is not None else None
        data = {**self.line.model_dump(), 'enabled': True, 'lat': lat, 'lon': lon, 'bearing': bearing}
        if width_m is not None:
            data['width_m'] = width_m
        self.configure(LapLine.model_validate(data))

    def values(self):
        if not self.line.enabled:
            return dict.fromkeys(LAP_CHANNELS)
        s = self.state
        elapsed = None
        if s['lap_start_ms'] is not None and self.latest_utc:
            now_ms = self.latest_utc[0] + (time.monotonic() - self.latest_utc[1]) * 1000
            elapsed = max(0.0, (now_ms - s['lap_start_ms']) / 1000)
        minutes = lambda sec: None if sec is None else sec / 60
        return {'LapCount': s['count'], 'CurrentLap': s['count'] + 1 if s['lap_start_ms'] is not None else 0,
                'LapTime': minutes(s['last_s']), 'BestLap': minutes(s['best_s']), 'ElapsedTime': minutes(elapsed)}

    def crossed(self, at_ms):
        self.armed = False
        s = self.state
        if s['lap_start_ms'] is None:
            s['lap_start_ms'] = at_ms
        else:
            lap = (at_ms - s['lap_start_ms']) / 1000
            if lap < self.line.min_lap_s:
                return
            if lap <= self.line.max_lap_s:
                s['count'] += 1; s['last_s'] = lap
                s['best_s'] = lap if s['best_s'] is None else min(s['best_s'], lap)
                s['laps'] = (s['laps'] + [{'n': s['count'], 's': round(lap, 3), 'end_utc_ms': at_ms}])[-KEEP_LAPS:]
            # A gap longer than any real lap (pit stop, next day) restarts the
            # running lap without counting it; totals stay until an explicit reset.
            s['lap_start_ms'] = at_ms
        try:
            self.save()
        except OSError as exc:
            self.error = f'ラップ記録を保存できません: {exc}'

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
            self.previous = None; self.inside = None
            return self.values()
        self.latest_utc = (utc, time.monotonic())
        if not self.line.enabled:
            return self.values()
        x, y = offset_m(self.line.lat, self.line.lon, lat, lon)
        previous, self.previous = self.previous, (utc, x, y)
        if not self.armed:
            self.armed = math.hypot(x, y) > self.line.width_m
            self.inside = None
            return self.values()
        if previous is None or not 0 < utc - previous[0] <= MAX_FIX_GAP_MS:
            self.inside = None
            return self.values()
        half = self.line.width_m / 2
        if self.line.bearing is not None:
            b = math.radians(self.line.bearing)
            nx, ny = math.sin(b), math.cos(b)
            d0 = previous[1] * nx + previous[2] * ny
            d1 = x * nx + y * ny
            if d0 < 0 <= d1:
                f = -d0 / (d1 - d0)
                px, py = previous[1] + (x - previous[1]) * f, previous[2] + (y - previous[2]) * f
                if abs(px * ny - py * nx) <= half:
                    self.crossed(round(previous[0] + (utc - previous[0]) * f))
        else:
            distance = math.hypot(x, y)
            if distance <= half:
                if self.inside is None or distance < self.inside['distance']:
                    self.inside = {'distance': distance, 'utc': utc, 'yaw': values.get('Yaw'), 'speed': values.get('GPSSpeed')}
            elif self.inside is not None:
                closest, self.inside = self.inside, None
                if closest['speed'] is not None and closest['speed'] >= LEARN_MIN_KMH and closest['yaw'] is not None:
                    self.line = self.line.model_copy(update={'bearing': closest['yaw'] % 360})
                self.crossed(closest['utc'])
        return self.values()

    def public(self):
        return {'line': self.line.model_dump(), 'values': self.values(), 'error': self.error,
                'laps': self.state['laps'][-20:], 'running': self.state['lap_start_ms'] is not None}
