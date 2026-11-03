import io
import json
import math
import tempfile
import unittest
import wave
from pathlib import Path

from dash_model import DEFAULTS, DashModel, LapRef, Warning, fmt_hms, fmt_lap, fmt_signed, load_config, tone_wav

LAT0, LON0, RADIUS = 38.14, 140.77, 400.0


def config(**changes):
    data = json.loads(json.dumps(DEFAULTS))
    data.update(changes)
    return data


def on_circle(fraction):
    angle = 2 * math.pi * fraction
    return (LAT0 + RADIUS * math.sin(angle) / 111320.0,
            LON0 + RADIUS * math.cos(angle) / (111320.0 * math.cos(math.radians(LAT0))))


def frame(lap=None, oil=98.0, water=88.0, lat=LAT0, lon=LON0, connected=True, logging=True):
    return {'status': {'connected': connected, 'logging': {'active': logging}},
            'sample': {'values': {'Lat': lat, 'Lon': lon}, 'can_signals': {'OilTemp': oil, 'WaterTemp': water},
                       'gnss_utc': '2026-11-08T02:16:15Z', 'lap': lap or {}}}


class FormatTests(unittest.TestCase):
    def test_times(self):
        self.assertEqual(fmt_lap(112.34), '1:52.34')
        self.assertEqual(fmt_lap(72.39, 1), '1:12.3')  # cut, never rounded up to the next tenth
        self.assertEqual(fmt_lap(5.0), '0:05.00')
        self.assertEqual(fmt_lap(None), '--')
        self.assertEqual(fmt_hms(2175), '0:36:15')
        self.assertEqual(fmt_hms(7322.9), '2:02:02')

    def test_signed(self):
        self.assertEqual(fmt_signed(0.41), '+0.41')
        self.assertEqual(fmt_signed(-0.84), '−0.84')
        self.assertEqual(fmt_signed(0.001), '0.00')
        self.assertEqual((fmt_signed(38.42), fmt_signed(-123.4)), ('+38.4', '−123'))
        self.assertEqual(fmt_signed(None), '--')


class WarningTests(unittest.TestCase):
    def test_level_needs_one_second_and_sounds_once(self):
        w = Warning(config())
        self.assertIsNone(w.update(0.0, 121, 100))
        self.assertIsNone(w.update(0.5, 121, 100)); self.assertEqual(w.level, 0)
        self.assertEqual(w.update(1.0, 121, 100), 'warn'); self.assertEqual(w.level, 2)
        self.assertEqual((w.label, w.value), ('油温', 121))
        self.assertIsNone(w.update(1.1, 122, 100)); self.assertIsNone(w.update(9.0, 122, 100))

    def test_pit_in_repeats_and_leaves_five_seconds_after(self):
        w = Warning(config())
        w.update(0.0, 131, 110)
        self.assertEqual(w.update(1.0, 131, 110), 'pit'); self.assertEqual(w.level, 3)
        self.assertIsNone(w.update(3.0, 131, 110))
        self.assertEqual(w.update(5.0, 131, 110), 'pit')  # every repeat_s (4 s)
        self.assertIsNone(w.update(6.0, 100, 90)); self.assertEqual(w.level, 3)
        self.assertIsNone(w.update(10.9, 100, 90)); self.assertEqual(w.level, 3)
        self.assertIsNone(w.update(11.0, 100, 90)); self.assertEqual(w.level, 0)

    def test_short_dip_keeps_the_level(self):
        w = Warning(config())
        w.update(0.0, 125, 100); w.update(1.0, 125, 100)
        w.update(2.0, 118, 100)
        self.assertIsNone(w.update(4.0, 124, 100)); self.assertEqual(w.level, 2)  # back up before 5 s: no new beep
        self.assertIsNone(w.update(12.0, 124, 100))

    def test_water_warns_when_the_oil_sensor_is_lost(self):
        w = Warning(config())
        w.update(0.0, None, 112); self.assertEqual(w.update(1.0, None, 112), 'warn')
        self.assertEqual((w.level, w.label, w.value), (2, '水温', 112))
        w2 = Warning(config())
        w2.update(0.0, 111, 99); w2.update(1.0, 111, 99)
        self.assertEqual((w2.level, w2.label), (1, '油温'))


class LapRefTests(unittest.TestCase):
    def drive(self, ref, laps, hz=10.0, until=None):
        """Laps of the given durations round the circle; LapTime/BestLap as lap.py reports them."""
        times, best = [], None
        for k, lap_s in enumerate(laps, start=1):
            steps = int(lap_s * hz)
            for j in range(steps):
                el = j / hz
                if until is not None and k == len(laps) and el > until:
                    return
                lat, lon = on_circle(el / lap_s)
                ref.update(lat, lon, k, el, times[-1] if times else None, best)
            times.append(lap_s); best = min(times)

    def test_gap_to_the_best_lap_at_the_same_place(self):
        ref = LapRef()
        self.drive(ref, [100.0, 110.0], until=50.0)
        self.assertIsNotNone(ref.ref); self.assertEqual(ref.ref['no'], 1)
        self.assertAlmostEqual(ref.delta, 50.0 * (1 - 100 / 110), delta=0.15)

    def test_a_slower_lap_does_not_replace_the_best_and_the_file_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lapref.json'
            ref = LapRef(path)
            self.drive(ref, [100.0, 104.0, 98.0, 101.0], until=40.0)
            self.assertEqual(ref.ref['no'], 3)
            self.assertAlmostEqual(ref.delta, 40.0 * (1 - 98 / 101), delta=0.15)
            again = LapRef(path)
            self.assertEqual(again.ref['no'], 3)
            lat, lon = on_circle(0.25)
            self.assertAlmostEqual(again.update(lat, lon, 9, 26.0, 101.0, 98.0), 26.0 - 24.5, delta=0.15)
            self.assertIsNone(again.update(lat, lon, 9, 26.0, 101.0, 97.0))  # best changed (reset): not this track

    def test_far_from_the_track_gives_no_gap(self):
        ref = LapRef()
        self.drive(ref, [100.0, 105.0], until=10.0)
        self.assertIsNotNone(ref.delta)
        self.assertIsNone(ref.update(LAT0 + 0.01, LON0, 2, 11.0, 100.0, 100.0))


class ModelTests(unittest.TestCase):
    def test_screen_values(self):
        m = DashModel(config())
        lap = {'CurrentLap': 23, 'ElapsedTime': 72.3 / 60, 'LapTime': 112.34 / 60, 'BestLap': 111.12 / 60,
               'RaceTime': 2175 / 60, 'LapDiffS': 0.41, 'LastLapPit': False}
        s, _ = m.update(frame(lap), 0.0)
        self.assertEqual((s['lap_now'], s['last'], s['best'], s['lap_no'], s['elapsed'], s['clock']),
                         ('1:12.3', '1:52.34', '1:51.12', '23', '0:36:15', '11:16'))
        self.assertEqual((s['last_note'], s['last_note_kind']), ('前周比 +0.41秒', 'slower'))
        self.assertEqual((s['notice'], s['notice_kind']), ('', None))
        self.assertTrue(s['rec'] and s['gnss'] and s['oil_sensor'] and not s['stale'])
        self.assertEqual((s['video'], s['video_kind']), ('', None))  # an EcoCapture without the video summary

    def test_video_light(self):
        m = DashModel(config())
        f = frame()
        f['status']['video'] = {'recording': True, 'minutes_left': 108}
        s, _ = m.update(f, 0.0)
        self.assertEqual((s['video'], s['video_kind']), ('録画 1:48', 'warn'))  # short of a 120-minute race
        f['status']['video'] = {'recording': True, 'minutes_left': 150}
        s, _ = m.update(f, 0.1)
        self.assertEqual((s['video'], s['video_kind']), ('録画 2:30', 'ok'))
        f['status']['video'] = {'recording': False, 'minutes_left': 150}
        s, _ = m.update(f, 0.2)
        self.assertEqual((s['video'], s['video_kind']), ('録画なし', 'warn'))

    def test_waiting_pit_lost_and_stale(self):
        m = DashModel(config())
        s, _ = m.update(frame({'CurrentLap': 0, 'RaceTime': None}, oil=None), 0.0)
        self.assertEqual((s['elapsed'], s['lap_now'], s['lap_no']), ('スタート待ち', '--', '--'))
        self.assertFalse(s['oil_sensor'])
        s, _ = m.update(frame({'CurrentLap': 8, 'LapTime': 3.7, 'LapDiffS': None, 'LastLapPit': True}), 0.1)
        self.assertEqual((s['last_note'], s['last_note_kind']), ('PIT', 'pit'))
        s, _ = m.update(None, 2.0); self.assertFalse(s['stale'])
        s, _ = m.update(None, 2.2); self.assertTrue(s['stale']); self.assertAlmostEqual(s['stale_s'], 2.1)
        s, _ = m.update(frame(connected=False), 3.0); self.assertTrue(s['stale'])

    def test_a_pit_stop_is_not_shown_as_a_warning(self):
        m = DashModel(config())
        m.lapref.update = lambda *args: 41.5  # what the pit lane, 11 m from the track, would give
        lap = {'CurrentLap': 9, 'ElapsedTime': 0.5, 'LapStartPit': False}
        moving = lambda **kw: {**frame(lap={**lap, **kw}), 'sample': {**frame(lap={**lap, **kw})['sample'],
                                                                         'values': {'Lat': LAT0, 'Lon': LON0, 'GPSSpeed': 120.0}}}
        s, _ = m.update(moving(), 0.0)
        self.assertEqual((s['delta'], s['delta_kind'], s['notice']), ('+41.5', 'slower', ''))
        in_box = moving(LapStartPit=True, LastLapPit=True); in_box['sample']['values']['GPSSpeed'] = 0.0
        s, _ = m.update(in_box, 0.1)  # stopped in the box, past the line
        self.assertEqual((s['delta'], s['notice'], s['notice_kind']), ('--', 'ピットイン', 'pit'))
        s, _ = m.update(moving(LapStartPit=True, LastLapPit=True), 0.2)  # the out lap
        self.assertEqual((s['delta'], s['delta_kind'], s['delta_frac'], s['notice'], s['notice_kind']),
                         ('--', None, None, 'ピットアウト', 'pit'))
        self.assertEqual((s['last_note'], s['last_note_kind'], s['warn_level']), ('PIT', 'pit', 0))
        stopped = moving(); stopped['sample']['values']['GPSSpeed'] = 3.0
        s, _ = m.update(stopped, 0.3)  # stopped on the in lap (a box before the line): nothing known yet
        self.assertEqual((s['delta'], s['notice']), ('--', ''))

    def test_the_temperature_takes_the_same_strip_and_comes_first(self):
        m = DashModel(config())
        out_lap = {'CurrentLap': 9, 'ElapsedTime': 0.5, 'LapStartPit': True, 'LastLapPit': True}
        for k in range(12):
            s, _ = m.update(frame(out_lap, oil=122), k * 0.1)
        self.assertEqual((s['notice'], s['notice_kind']), ('クーリング　油温 122℃', 'cool'))
        for k in range(12):
            s, _ = m.update(frame(out_lap, oil=96, water=121), 2.0 + k * 0.1)
        self.assertEqual((s['notice'], s['notice_kind']), ('ピットイン　水温 121℃', 'pitin'))

    def test_no_warning_from_values_of_a_dead_link(self):
        m = DashModel(config())
        m.update(frame(oil=135), 0.0)
        s, sound = m.update(frame(oil=135, connected=False), 1.5)
        self.assertEqual((s['warn_level'], sound), (0, None))


class SoundAndConfigTests(unittest.TestCase):
    def test_tones(self):
        for kind, seconds in (('warn', 0.9), ('pit', 2.0)):
            with wave.open(io.BytesIO(tone_wav(kind)), 'rb') as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), seconds, places=2)

    def test_config_file_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dash.json'
            path.write_text(json.dumps({'oil_limits': [105, 115, 125], 'sound': {'device': 'hdmi'}, 'unknown': 1}))
            c = load_config(path)
            self.assertEqual(c['oil_limits'], [105, 115, 125])
            self.assertEqual((c['sound']['device'], c['sound']['volume']), ('hdmi', 0.8))
            self.assertNotIn('unknown', c)
        self.assertEqual(load_config('/nonexistent.json')['water_limits'], [100.0, 110.0, 120.0])


if __name__ == '__main__':
    unittest.main()
