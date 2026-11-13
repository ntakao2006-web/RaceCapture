"""What EcoCapture DASH shows, worked out from EcoCapture's /api/telemetry (no GTK here).

The driver screen for the SUGO 120-minute endurance (2026-11-08, task_sugo_20261108_breakdown.md
SG-2-6): the running lap, the gap to the best lap, the last lap with its difference from the lap
before (or PIT), the best lap and lap number, the time since the first control-line pass after the
lap reset, the clock, and small lights for recording, GNSS, sending (SPEC.md M-2) and the oil sensors. Oil pressure, oil and
water temperatures are not shown as gauges (the Defi meters are there): only their warnings are.

A normal pit stop is not a warning: the lap begun in the pit lane gets a blue strip (PIT IN while
stopped, PIT OUT once moving) and a pit lap PIT in blue; and the gap to the best lap is not shown on the out lap or while stopped (it would be a big red
number that looks like an alarm). Red is only for the slower gap and the temperature warnings.

Three warnings, not tied to what to do about them (the driver decides), each on or off by itself:
- oil pressure (OilPress, kPa) low for the engine speed: below the line of oil_press_warn, judged only
  at oil_press_min_rpm and above (a hot idle is 80-100 kPa, a stopped or stalling engine reads 0);
- oil temperature 120 C, the warning of ncec-roadster track/thermal-limits.md;
- water temperature 110 C (oil ~ water + 10 C through the heat exchanger), so the ECU water
  temperature still warns when the oil sensor is lost.
Every warning that is on is shown side by side in one red band over the middle row (oil pressure
first, smaller when there are more), with one alarm sound each time a warning comes on. A warning
comes on after its hold time above the limit (press_hold_on_s 0.5 s, hold_on_s 5 s for the temperatures, so
the Defi unit's voltage falling when the key is turned off does not set it off) and goes off after
hold_off_s below it. For flash_s (a minute) after a warning comes on, the band flashes bright and dark
red (the white text always readable), to catch the eye from the side wherever on the lap it came on:
a minute takes in the home or the back straight. Then it stays bright red, as a long hot stint
flashing all the time would only make the numbers harder to read. The sound is about ten seconds:
six bursts of the two-tone alarm, so one of them gets through the helmet and the engine.

Engine speed and speed along the top (added 2026-11-06 for the NCEC: the stock speedometer is not to be
trusted and the tuned ECU revs to 8000 rpm, past the stock tachometer): ten segments as the ten shift
lights of an AiM dash (there are no LEDs, so they are drawn), lit green, yellow then red from
rpm_bar_start up to the last one below shift_rpm; from shift_rpm the whole bar flashes red (the usual
sign of a shift light; the user's call on 2026-11-06 over blue: the warnings are red too, but in the
middle band, so the place tells them apart) and from limit_rpm the engine speed number is shown inverted
as well (the limiter itself is felt; the bar is there to shift before it). No sound for either. The speed is GPSSpeed. On the
lap begun in the pit lane, until the car is faster than pit_lane_max_kmh, the speed turns yellow from
pit_speed_warn_kmh and red above pit_speed_limit_kmh (SUGO: 60 km/h, a drive-through over it). The pit
lane before the control line is not known, so there the speed stays white.

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
    'oil_warn': 120.0,
    'water_warn': 110.0,
    # Oil pressure (kPa) too low for the engine speed: [rpm, kPa] points, straight between them and flat
    # outside. 1500-3000 rpm follows the rule of thumb of about 10 psi per 1000 rpm (HP Academy), 100 kPa
    # being also Defi's danger line for a hot idle; above 3000 rpm it stays at 200 kPa, well under the
    # NC's 337-591 kPa at 3000 rpm with oil at 100 C (service data) and its relief valve's 420-520 kPa,
    # so a hot engine at high revs does not set it off. A pump, leak or starvation in a long corner does.
    'oil_press_warn': [[1500, 100], [3000, 200]],
    'oil_press_min_rpm': 1500,
    # The temperatures (oil, water) must stay at the limit this long. 5 s, not 1 s (2026-11-07): when the key
    # is turned off the Defi unit loses its power before the logger, so its thermistor voltage falls from
    # about 2.3 V to 0 in about a second, and on the way the oil temperature read 132-197 C for 1.03 s (with
    # the 1 s the last value is kept), which sounded the warning. A real overheat takes minutes.
    'hold_on_s': 5.0,
    'press_hold_on_s': 0.5,  # pressure gone does harm quicker than heat
    'hold_off_s': 5.0,
    'flash_s': 60.0,  # the band flashes this long after a warning comes on (0: never); a minute: one straight
    'delta_full_scale_s': 2.0,
    # The engine speed bar (rpm). The NCEC's limiter is 8000 rpm (NOPRO MZ-TUNE+). The user's call on
    # 2026-11-06: the bar from 4000 (easier to read, 350 rpm a segment) and the red flashing from 7500, 500
    # short of the limiter (it was 5000 and 7700). To be set per gear from the logs of 2026-11-07 (and the
    # RPM above 3439 is still to be checked against the stock tachometer).
    'rpm_bar_start': 4000,
    'shift_rpm': 7500,
    # segments in the bar, coloured green 40%, yellow 30%, red 30% (segment_colours). The user's call on
    # 2026-11-07 from 10/20/30 drawn side by side: 30 (117 rpm a segment; the full bar at 7384, close to the flashing)
    'rpm_segments': 30,
    'limit_rpm': 7950,
    # The speed in the pit lane (km/h): SUGO's pit lane limit is 60
    'pit_speed_limit_kmh': 60,
    'pit_speed_warn_kmh': 56,
    'pit_lane_max_kmh': 80,  # on the out lap, faster than this is out of the pit lane (as lap.py's pit_max_kmh)
    'stale_s': 2.0,
    # The burnt-in video (EcoCapture /api/status 'video', unoq_video_check_procedure.md 5-17): fewer minutes
    # left than this (a 120-minute race with the grid and the cool-down lap) is shown in yellow
    'video_warn_min': 130,
    # The sending light (EcoCapture /api/status 'podium'): 'streaming' but nothing sent for longer than this
    # is shown as not sending. Rows go out 10 times a second; over LTE they are sent five at a time, or
    # after 1 s when fewer have come (podium.py RELAY_BATCH), and a slow link may take about 2 s over one
    # send (the limit podium.py's VoiceGuard allows on LTE). 5 s is over twice that, so a healthy link
    # never trips it, and still short enough to be seen within one straight.
    'send_stale_s': 5.0,
    # The UNO Q's one sound card: its 4th front end (MultiMedia4) is routed to SEC_MI2S_RX, the I2S
    # link to the ANX7625 (the USB-C video bridge) and so to the monitor's speaker over HDMI
    # (device tree: sound/hdmi-i2s-dai-link, port 18; checked 2026-11-04). PipeWire does not use the card.
    # repeat: bursts of the two-tone alarm (1.5 s each, 0.25 s apart; 6 is about ten seconds)
    'sound': {'enabled': True, 'device': 'plughw:CARD=ArduinoImolaHPH,DEV=3', 'volume': 0.8, 'repeat': 6,
              'card': 'ArduinoImolaHPH', 'route': ['SEC_MI2S_RX Audio Mixer MultiMedia4']},
}

def rpm_segments(config):
    """The number of segments in the bar (at least 3: one of each colour)."""
    return max(3, int(config.get('rpm_segments', 10)))


def segment_colours(n):
    """'g' / 'y' / 'r' for each of n segments: green 40%, yellow 30%, red 30% (ten: 4-3-3 as an AiM's ten
    shift lights; twenty: 8-6-6)."""
    green, yellow = max(1, round(n * 0.4)), max(1, round(n * 0.3))
    return ('g',) * green + ('y',) * yellow + ('r',) * (n - green - yellow)
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
    """+0.41 / −0.84 (U+2212, as wide as +); +38.4 and +123 once the hundredths stop mattering, so the
    number with its unit still fits its cell (in the pit lane before the line the gap runs to tens of seconds)."""
    if seconds is None:
        return '--'
    if abs(seconds) < 0.005:
        return '0.00'
    sign = '+' if seconds > 0 else '−'
    size = abs(seconds)
    return f'{sign}{size:.{2 if size < 10 else 1 if size < 100 else 0}f}'


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


def press_limit(config, rpm):
    """The lowest oil pressure (kPa) taken as healthy at this engine speed; None where it is not judged."""
    if rpm is None or rpm < config['oil_press_min_rpm']:
        return None
    try:
        pts = sorted((float(r), float(p)) for r, p in config['oil_press_warn'])
    except (TypeError, ValueError):
        return None
    if not pts:
        return None
    if rpm <= pts[0][0]:
        return pts[0][1]
    for (r0, p0), (r1, p1) in zip(pts, pts[1:]):
        if rpm <= r1:
            return p1 if r1 <= r0 else p0 + (p1 - p0) * (rpm - r0) / (r1 - r0)
    return pts[-1][1]


def rpm_bar(config, rpm):
    """(segments lit 0-n, 'shift' / 'limit' / None). The first segment lights at rpm_bar_start, the last one
    step below shift_rpm, so the full bar comes just before the flashing."""
    if rpm is None:
        return 0, None
    n = rpm_segments(config)
    start, shift, limit = (float(config[k]) for k in ('rpm_bar_start', 'shift_rpm', 'limit_rpm'))
    if rpm >= shift:
        return n, 'limit' if rpm >= limit else 'shift'
    if rpm < start or shift <= start:
        return 0, None
    return min(n, 1 + int((rpm - start) * n / (shift - start))), None


class Alarm:
    """One warning, on or off with its hold times; value is the latest reading (kept while the sensor is lost)."""

    def __init__(self, label, unit, hold_on_s, hold_off_s):
        self.label, self.unit = label, unit
        self.hold_on_s, self.hold_off_s = hold_on_s, hold_off_s
        self.on, self.value, self._since = False, None, None
        self.on_at = None  # when it last came on

    def update(self, now, bad, value):
        """True at the moment it comes on."""
        if value is not None:
            self.value = value
        if bad == self.on:
            self._since = None
            return False
        self._since = now if self._since is None else self._since
        if now - self._since < (self.hold_on_s if bad else self.hold_off_s):
            return False
        self.on, self._since = bad, None
        if bad:
            self.on_at = now
        return bad


class Warning:
    """The oil pressure, oil temperature and water temperature warnings, and when to sound."""

    def __init__(self, config):
        self.config = config
        c = config
        self.alarms = {'press': Alarm('油圧', 'kPa', c['press_hold_on_s'], c['hold_off_s']),
                       'oil': Alarm('油温', '℃', c['hold_on_s'], c['hold_off_s']),
                       'water': Alarm('水温', '℃', c['hold_on_s'], c['hold_off_s'])}

    def update(self, now, oil, water, press=None, rpm=None):
        """Returns 'warn' at the moment any warning comes on (one sound each), else None."""
        limit = press_limit(self.config, rpm)
        bad = {'press': press is not None and limit is not None and press < limit,
               'oil': oil is not None and oil >= self.config['oil_warn'],
               'water': water is not None and water >= self.config['water_warn']}
        reading = {'press': press, 'oil': oil, 'water': water}
        new = [alarm.update(now, bad[key], reading[key]) for key, alarm in self.alarms.items()]
        return 'warn' if any(new) else None

    @property
    def on(self):
        return any(alarm.on for alarm in self.alarms.values())

    def active(self):
        """The warnings that are on, in the order the band shows them (oil pressure first)."""
        return [alarm for alarm in self.alarms.values() if alarm.on]

    def flashing(self, now):
        """A warning came on less than flash_s ago (a new one flashes the band again)."""
        return any(a.on and a.on_at is not None and now - a.on_at < self.config['flash_s'] for a in self.alarms.values())


class DashModel:
    def __init__(self, config, lapref_path=None):
        self.config = config
        self.lapref = LapRef(lapref_path)
        self.warning = Warning(config)
        self.last_good = None  # monotonic time of the last frame with live values
        self.press_seen = False  # the oil pressure has come at least once (until then its light says nothing)
        self.pit_lane, self.pit_lap = False, None  # still in the pit lane on the lap begun there

    def pit_speed(self, out_lap, lap_no, speed):
        """'warn' / 'over' / None for the speed in the pit lane after the line (see the module notes)."""
        if not out_lap:
            self.pit_lane, self.pit_lap = False, None
            return None
        if lap_no != self.pit_lap:  # a new lap begun in the pit lane
            self.pit_lane, self.pit_lap = True, lap_no
        if speed is not None and speed > self.config['pit_lane_max_kmh']:
            self.pit_lane = False
        if not self.pit_lane or speed is None:
            return None
        shown = round(speed)
        return 'over' if shown > self.config['pit_speed_limit_kmh'] else 'warn' if shown >= self.config['pit_speed_warn_kmh'] else None

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
        press, rpm = (pick('OilPress'), pick('RPM')) if live else (None, None)
        self.press_seen = self.press_seen or press is not None
        sound = self.warning.update(now, oil, water, press, rpm)
        delta = self.lapref.update(lat, lon, number(lap.get('CurrentLap')), elapsed, last, best) if live else None
        speed_kind = self.pit_speed(out_lap, number(lap.get('CurrentLap')), speed if live else None)
        lit, rpm_mode = rpm_bar(self.config, rpm)
        stopped = speed is not None and speed < STOPPED_KMH
        if out_lap or stopped:
            delta = None  # still tracked above, so the reference keeps its place
        # The strip under the running lap: the pit stop first (the temperature has its own band), else the
        # sector just completed against that sector's best (lap.py, 2026-11-07), until the next one ends
        sector_no, sector_diff = number(lap.get('LastSector')), number(lap.get('SectorDiffS'))
        if out_lap:
            notice, notice_kind = ('PIT IN' if stopped else 'PIT OUT'), 'pit'
        elif sector_no and sector_diff is not None and elapsed is not None:
            notice = f'S{int(sector_no)} {fmt_signed(sector_diff)}'
            notice_kind = 'slower' if sector_diff > 0.005 else 'faster' if sector_diff < -0.005 else 'even'
        else:
            notice, notice_kind = '', None

        diff, pit = number(lap.get('LapDiffS')), lap.get('LastLapPit') is True
        if pit:
            note, note_kind = 'PIT', 'pit'
        elif diff is not None:
            note, note_kind = f'前周比 {fmt_signed(diff)}s', 'slower' if diff > 0.005 else 'faster' if diff < -0.005 else 'even'
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
        send_text, send_kind = send_light(status.get('podium'), self.config['send_stale_s'])
        state = {
            'stale': stale,
            'rpm': '--' if rpm is None else f'{int(round(rpm))}',
            'rpm_lit': lit, 'rpm_mode': rpm_mode,
            'speed': '--' if speed is None or not live else f'{int(round(speed))}',
            'speed_kind': speed_kind,
            'stale_s': None if self.last_good is None else now - self.last_good,
            'lap_now': fmt_lap(elapsed, 1),
            'notice': notice, 'notice_kind': notice_kind,
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
            'send': send_text, 'send_kind': send_kind,
            'gnss': lat is not None and lon is not None and not (lat == 0 and lon == 0),
            'oil_sensor': oil is not None,
            'press_sensor': press is not None if self.press_seen else None,
            'sensor': sensor_light(oil is not None, press is not None if self.press_seen else None),
            'warn': self.warning.on,
            'warn_flash': self.warning.flashing(now),
            'warns': [{'label': a.label, 'value': '--' if a.value is None else f'{a.value:.0f}', 'unit': a.unit}
                      for a in self.warning.active()],
        }
        return state, sound


def sensor_light(oil, press):
    """(text, ok) of the oil sensors' light; press None: no oil pressure yet (not wired), so not mentioned."""
    if press is None:
        return ('油温センサー', True) if oil else ('油温センサー途絶', False)
    if oil and press:
        return '油温・油圧', True
    return ('油圧センサー途絶' if oil else '油温センサー途絶' if press else '油温・油圧途絶'), False


def send_light(podium, stale_s):
    """(text, kind) of the sending light, from EcoCapture's /api/status 'podium' (podium.py status()).
    'ok': streaming, and the last row went out within stale_s. 'warn': sending is on but nothing is going
    out (connecting, retrying, waiting for the GNSS time, or streaming with the last row older than
    stale_s). 'off': sending is switched off. None: not known (the API could not be read, or an older
    EcoCapture without the item). The words stay short: this is read while driving, the colour says it."""
    if not isinstance(podium, dict):
        return '送信 --', None
    enabled = podium.get('enabled')
    if enabled is False or (enabled is None and podium.get('state') == 'off'):
        return '送信OFF', 'off'
    age = number(podium.get('last_sent_age_ms'))
    if podium.get('state') == 'streaming' and age is not None and age <= stale_s * 1000:
        return '送信中', 'ok'
    return '未送信', 'warn'


def tone_wav(kind, volume=0.8, rate=44100, repeat=6):
    """The warning sound as WAV bytes: 'warn' bursts, 1.5 s each and 0.25 s apart (six: about ten
    seconds; a break between bursts is heard better than one long tone). A burst is 15 rapid beeps of
    a 2500 Hz square wave, 0.05 s on and 0.05 s off (picked by ear on 2026-11-05 over the old
    1000/750 Hz sine two-tone, which sounded like a household alarm rather than a race dash).
    Same samples as AlarmTone in the phone app (Circuit.kt)."""
    if kind != 'warn':
        raise ValueError(kind)
    freq, beep_s, beeps, gap_s = 2500.0, .05, 15, .25
    amp = max(0.0, min(1.0, volume)) * 32000
    n = int(rate * beep_s)
    fade = int(rate * .004)
    harmonics = list(range(1, int(rate / 2 * 0.9 / freq) + 1, 2))  # band-limited square: odd, below Nyquist
    on = bytearray()
    for k in range(n):
        s = sum(math.sin(2 * math.pi * h * freq * k / rate) / h for h in harmonics)
        gain = min(1.0, k / fade, (n - 1 - k) / fade)
        on += struct.pack('<h', int(amp * gain * s * 4 / math.pi / 1.2))  # 1.2: the overshoot, no clipping
    burst = (bytes(on) + bytes(len(on))) * beeps                       # 1.5 s
    gap = bytes(2 * int(rate * gap_s))
    frames = gap.join([burst] * max(1, int(repeat)))
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
    return out.getvalue()
