"""What EcoCapture DASH shows, worked out from EcoCapture's /api/telemetry (no GTK here).

The driver screen for the SUGO 120-minute endurance (2026-11-08, task_sugo_20261108_breakdown.md
SG-2-6): the running lap, the gap to the best lap, the last lap with its difference from the lap
before (or PIT), the best lap and lap number, the time since the first control-line pass after the
lap reset, the clock, and small lights for recording, GNSS and the oil temperature sensor. Oil and
water temperatures are not shown as gauges (the Defi meters are there): only their warnings are.

A normal pit stop is not a warning: the out lap is tagged ピットアウト and a pit lap PIT in blue,
and the gap to the best lap is not shown on the out lap or while stopped (it would be a big red
number that looks like an alarm). Red is only for the slower gap and the temperature warnings.

Warnings (ncec-roadster track/thermal-limits.md, provisional): oil 110 C caution, 120 C start
cooling, 130 C pit in; water 10 C lower (oil ~ water + 10 C through the heat exchanger), so the
ECU water temperature still warns when the oil sensor is lost. A level is entered after hold_on_s
above it and left after hold_off_s below it, as on the RaceCapture page.

The gap to the best lap is the algorithm of tools/unoq_overlay_enc/lap_ref.h (the burnt-in video
HUD), ported so both show the same number: the best lap's track is kept, and the running lap's
elapsed time is compared with the best lap's at the nearest point of that track.
"""
from __future__ import annotations

import io
import json
import math
import os
import struct
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

DEFAULTS = {
    'api': 'http://127.0.0.1:8080/api/telemetry',
    'oil_limits': [110.0, 120.0, 130.0],
    'water_limits': [100.0, 110.0, 120.0],
    'hold_on_s': 1.0,
    'hold_off_s': 5.0,
    'delta_full_scale_s': 2.0,
    'stale_s': 2.0,
    # The burnt-in video (EcoCapture /api/status 'video', unoq_video_check_procedure.md 5-17): fewer minutes
    # left than this (a 120-minute race with the grid and the cool-down lap) is shown in yellow
    'video_warn_min': 130,
    # The UNO Q's one sound card: its 4th front end (MultiMedia4) is routed to SEC_MI2S_RX, the I2S
    # link to the ANX7625 (the USB-C video bridge) and so to the monitor's speaker over HDMI
    # (device tree: sound/hdmi-i2s-dai-link, port 18; checked 2026-11-04). PipeWire does not use the card.
    'sound': {'enabled': True, 'device': 'plughw:CARD=ArduinoImolaHPH,DEV=3', 'volume': 0.8, 'repeat_s': 4.0,
              'card': 'ArduinoImolaHPH', 'route': ['SEC_MI2S_RX Audio Mixer MultiMedia4']},
}

WARN_TEXT = {1: '注意', 2: 'クーリング開始', 3: 'ピットイン'}
STOPPED_KMH = 10.0  # slower than this the gap to the best lap means nothing (in the pit, on the grid)

# lap_ref.h
LR_MAX = 8192        # points kept per lap (13 min at 10 Hz; a longer lap is never the reference)
LR_MATCH_M = 40.0    # farther than this from the best lap's track: no gap (pit garage, off course)
LR_EDGE_S = 3.0      # a lap recorded to within this of both ends counts as recorded in full


def load_config(path):
    """DEFAULTS, overridden by the JSON file at path when it exists."""
    config = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return config
    for key, value in data.items():
        if key == 'sound' and isinstance(value, dict):
            config['sound'].update(value)
        elif key in config:
            config[key] = value
    return config


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def fmt_lap(seconds, digits=2):
    """1:52.34 (or 1:12.3 with digits=1)."""
    if seconds is None or seconds < 0:
        return '--'
    scale = 10 ** digits
    total = math.floor(seconds * scale + 1e-6)
    minutes, rest = divmod(total, 60 * scale)
    return f'{minutes}:{rest // scale:02d}.{rest % scale:0{digits}d}'


def fmt_hms(seconds):
    if seconds is None or seconds < 0:
        return '--'
    total = int(seconds)
    return f'{total // 3600}:{total // 60 % 60:02d}:{total % 60:02d}'


def fmt_signed(seconds):
    """+0.41 / −0.84 (U+2212, as wide as +)."""
    if seconds is None:
        return '--'
    if abs(seconds) < 0.005:
        return '0.00'
    sign = '+' if seconds > 0 else '−'
    return f'{sign}{abs(seconds):.2f}'


def parse_utc(text):
    if not isinstance(text, str) or not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


class LapRef:
    """lap_ref.h's lr_update: the gap (s) to the best lap at the same place on the track."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.cur, self.cur_no, self.idx = [], -1, 0
        self.ref = None  # {'no', 'time_s', 'pts': [(lat, lon, elapsed_s), ...]}
        self.delta = None
        self.load()

    def load(self):
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            pts = [tuple(p) for p in data['pts']]
            if len(pts) >= 2 and len(pts) <= LR_MAX:
                self.ref = {'no': int(data['no']), 'time_s': float(data['time_s']), 'pts': pts}
        except (OSError, ValueError, KeyError, TypeError):
            self.ref = None

    def save(self):
        if not self.path or not self.ref:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.ref), encoding='utf-8')
            os.replace(temp, self.path)
        except OSError:
            pass

    def nearest(self, lat, lon, lo, hi):
        """(distance m, segment i, position u along it) of the best lap's track nearest (lat, lon)."""
        pts = self.ref['pts']
        kx, ky = math.cos(math.radians(lat)) * 111320.0, 111320.0
        best = (math.inf, 0, 0.0)
        for i in range(lo, min(hi, len(pts) - 1)):
            bx, by = (pts[i + 1][1] - pts[i][1]) * kx, (pts[i + 1][0] - pts[i][0]) * ky
            px, py = (lon - pts[i][1]) * kx, (lat - pts[i][0]) * ky
            l2 = bx * bx + by * by
            u = min(max((px * bx + py * by) / l2, -1 if i == 0 else 0), 2 if i + 2 == len(pts) else 1) if l2 > 0 else 0.0
            d = math.hypot(px - u * bx, py - u * by)
            if d < best[0]:
                best = (d, i, u)
        return best

    def update(self, lat, lon, lap_no, elapsed_s, last_s, best_s):
        if lat == 0 and lon == 0:
            lat = lon = None  # 0, 0 can come before the first fix
        no = -1 if lap_no is None else int(lap_no)
        if no != self.cur_no:  # a new lap
            cur = self.cur
            if (self.cur_no > 0 and no == self.cur_no + 1 and last_s is not None and 20 <= len(cur) < LR_MAX
                    and cur[0][2] <= LR_EDGE_S and abs(cur[-1][2] - last_s) <= LR_EDGE_S):  # recorded in full
                if best_s is not None and abs(last_s - best_s) < .01:  # and it is the best lap
                    self.ref = {'no': self.cur_no, 'time_s': last_s, 'pts': list(cur)}
                    self.save()
            self.cur, self.cur_no, self.idx = [], no, 0
        if lat is not None and lon is not None and elapsed_s is not None and len(self.cur) < LR_MAX \
                and (not self.cur or elapsed_s > self.cur[-1][2]):
            self.cur.append((lat, lon, elapsed_s))
        self.delta = None
        ref = self.ref
        if not ref or best_s is None or abs(ref['time_s'] - best_s) >= .05 or lat is None or lon is None \
                or elapsed_s is None or len(ref['pts']) < 2:
            return None
        d, i, u = self.nearest(lat, lon, max(0, self.idx - 10), self.idx + 150)
        if d > LR_MATCH_M:  # not near the last match (restart, jump): search the whole lap
            d, i, u = self.nearest(lat, lon, 0, len(ref['pts']))
        if d > LR_MATCH_M:
            return None
        self.idx = i
        pts = ref['pts']
        self.delta = elapsed_s - (pts[i][2] + u * (pts[i + 1][2] - pts[i][2]))
        return self.delta


class Warning:
    """Oil / water temperature warning level 0..3 with the hold times, and when to sound."""

    def __init__(self, config):
        self.config = config
        self.level, self.label, self.value = 0, None, None
        self._up = self._down = None
        self._last_pit_sound = None

    @staticmethod
    def step(value, limits):
        return 0 if value is None else sum(1 for limit in limits if value >= limit)

    def update(self, now, oil, water):
        """Returns the sound to play now: 'warn', 'pit' or None."""
        lo, lw = self.step(oil, self.config['oil_limits']), self.step(water, self.config['water_limits'])
        raw = max(lo, lw)
        self.label, self.value = ('油温', oil) if lo >= lw and oil is not None else ('水温', water)
        before = self.level
        if raw == self.level:
            self._up = self._down = None
        elif raw > self.level:
            self._down = None
            self._up = now if self._up is None else self._up
            if now - self._up >= self.config['hold_on_s']:
                self.level, self._up = raw, None
        else:
            self._up = None
            self._down = now if self._down is None else self._down
            if now - self._down >= self.config['hold_off_s']:
                self.level, self._down = raw, None
        if self.level == 3:
            repeat = self.config['sound']['repeat_s']
            # Repeats while it is still that hot, not during the hold after it has cooled.
            if before < 3 or (raw >= 3 and (self._last_pit_sound is None or now - self._last_pit_sound >= repeat)):
                self._last_pit_sound = now
                return 'pit'
            return None
        self._last_pit_sound = None
        return 'warn' if self.level == 2 and before < 2 else None


class DashModel:
    def __init__(self, config, lapref_path=None):
        self.config = config
        self.lapref = LapRef(lapref_path)
        self.warning = Warning(config)
        self.last_good = None  # monotonic time of the last frame with live values

    def update(self, frame, now, wall=None):
        """frame: the /api/telemetry envelope (None when it could not be read). Returns (state, sound)."""
        status = (frame or {}).get('status') or {}
        sample = (frame or {}).get('sample') or {}
        live = bool(status.get('connected')) and bool(sample)
        if live:
            self.last_good = now
        stale = self.last_good is None or now - self.last_good > self.config['stale_s']
        values, can = sample.get('values') or {}, sample.get('can_signals') or {}
        lap = sample.get('lap') or {}
        pick = lambda name: number(can.get(name)) if number(can.get(name)) is not None else number(values.get(name))
        minutes = lambda name: None if number(lap.get(name)) is None else number(lap.get(name)) * 60
        lat, lon = number(values.get('Lat')), number(values.get('Lon'))
        speed = number(values.get('GPSSpeed')) if number(values.get('GPSSpeed')) is not None else pick('Speed')
        out_lap = lap.get('LapStartPit') is True
        elapsed, last, best = minutes('ElapsedTime'), minutes('LapTime'), minutes('BestLap')
        race = minutes('RaceTime')
        oil, water = (pick('OilTemp'), pick('WaterTemp')) if live else (None, None)
        sound = self.warning.update(now, oil, water)
        delta = self.lapref.update(lat, lon, number(lap.get('CurrentLap')), elapsed, last, best) if live else None
        if out_lap or (speed is not None and speed < STOPPED_KMH):
            delta = None  # still tracked above, so the reference keeps its place

        diff, pit = number(lap.get('LapDiffS')), lap.get('LastLapPit') is True
        if pit:
            note, note_kind = 'PIT', 'pit'
        elif diff is not None:
            note, note_kind = f'前周比 {fmt_signed(diff)}', 'slower' if diff > 0.005 else 'faster' if diff < -0.005 else 'even'
        else:
            note, note_kind = '', None
        utc = parse_utc(sample.get('gnss_utc')) or parse_utc(sample.get('host_utc'))
        clock = (utc.astimezone(JST) if utc else (wall or datetime.now(JST))).strftime('%H:%M')
        scale = self.config['delta_full_scale_s']
        current = number(lap.get('CurrentLap'))
        # How long the burnt-in video can still record (EcoCapture works it out from the free space and
        # the videos the recorder may delete). No light from an EcoCapture without the summary.
        video = status.get('video')
        left = number((video or {}).get('minutes_left'))
        if video is None:
            video_text, video_kind = '', None
        elif not video.get('recording'):
            video_text, video_kind = '録画なし', 'warn'
        else:
            video_text = '録画' if left is None else f'録画 {int(left) // 60}:{int(left) % 60:02d}'
            video_kind = 'ok' if left is None or left >= self.config['video_warn_min'] else 'warn'
        state = {
            'stale': stale,
            'stale_s': None if self.last_good is None else now - self.last_good,
            'lap_now': fmt_lap(elapsed, 1),
            'lap_tag': 'ピットアウト' if out_lap else '',
            'delta': fmt_signed(delta),
            'delta_kind': None if delta is None else 'slower' if delta > 0.005 else 'faster' if delta < -0.005 else 'even',
            'delta_frac': None if delta is None else max(-1.0, min(1.0, delta / scale)),
            'last': fmt_lap(last), 'last_note': note, 'last_note_kind': note_kind,
            'best': fmt_lap(best),
            'lap_no': '--' if not current else str(int(current)),
            'elapsed': fmt_hms(race) if race is not None else 'スタート待ち',
            'clock': clock,
            'rec': bool((status.get('logging') or {}).get('active')),
            'video': video_text, 'video_kind': video_kind,
            'gnss': lat is not None and lon is not None and not (lat == 0 and lon == 0),
            'oil_sensor': oil is not None,
            'warn_level': self.warning.level,
            'warn_text': WARN_TEXT.get(self.warning.level, ''),
            'warn_label': self.warning.label,
            'warn_value': None if self.warning.value is None else f'{self.warning.value:.0f}℃',
        }
        return state, sound


def tone_wav(kind, volume=0.8, rate=22050):
    """The warning sounds as WAV bytes: 'warn' three short beeps, 'pit' a two-tone alarm."""
    if kind == 'warn':
        parts = [(880, .18), (0, .12)] * 3
    elif kind == 'pit':
        parts = [(1000, .25), (750, .25)] * 4
    else:
        raise ValueError(kind)
    frames = bytearray()
    amp = max(0.0, min(1.0, volume)) * 32000
    fade = int(rate * .005)
    for freq, length in parts:
        n = int(rate * length)
        for k in range(n):
            gain = min(1.0, k / fade, (n - 1 - k) / fade) if freq else 0.0
            frames += struct.pack('<h', int(amp * gain * math.sin(2 * math.pi * freq * k / rate)))
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
    return out.getvalue()
