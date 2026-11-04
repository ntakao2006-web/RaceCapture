import io
import json
import math
import tempfile
import unittest
import wave
from pathlib import Path

from dash_model import (DEFAULTS, DashModel, LapRef, Warning, fmt_hms, fmt_lap, fmt_signed, load_config, press_limit,
                        sensor_light, tone_wav)

LAT0, LON0, RADIUS = 38.14, 140.77, 400.0


def config(**changes):
    data = json.loads(json.dumps(DEFAULTS))
    data.update(changes)
    return data


def on_circle(fraction):
    angle = 2 * math.pi * fraction
    return (LAT0 + RADIUS * math.sin(angle) / 111320.0,
            LON0 + RADIUS * math.cos(angle) / (111320.0 * math.cos(math.radians(LAT0))))


def frame(lap=None, oil=98.0, water=88.0, lat=LAT0, lon=LON0, connected=True, logging=True, press=None, rpm=None):
    can = {'OilTemp': oil, 'WaterTemp': water}
    if press is not None:
        can['OilPress'] = press
    return {'status': {'connected': connected, 'logging': {'active': logging}},
            'sample': {'values': {'Lat': lat, 'Lon': lon, 'RPM': rpm}, 'can_signals': can,
                       'gnss_utc': '2026-11-08T02:16:15Z', 'lap': lap or {}}}


def shown(w):
    return [(a.label, a.value) for a in w.active()]


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
    def test_on_after_one_second_with_one_sound(self):
        w = Warning(config())
        self.assertIsNone(w.update(0.0, 121, 100))
        self.assertIsNone(w.update(0.5, 121, 100)); self.assertFalse(w.on)
        self.assertEqual(w.update(1.0, 121, 100), 'warn'); self.assertTrue(w.on)
        self.assertEqual(shown(w), [('油温', 121)])
        for t in (1.1, 5.0, 9.0):
            self.assertIsNone(w.update(t, 135, 100))  # no second level, no repeat
        self.assertEqual(shown(w), [('油温', 135)])

    def test_off_five_seconds_after_and_a_short_dip_keeps_it(self):
        w = Warning(config())
        w.update(0.0, 125, 100); w.update(1.0, 125, 100)
        w.update(2.0, 118, 100)
        self.assertIsNone(w.update(4.0, 124, 100)); self.assertTrue(w.on)  # back up before 5 s: no new sound
        w.update(5.0, 115, 100)
        self.assertIsNone(w.update(9.9, 115, 100)); self.assertTrue(w.on)
        self.assertIsNone(w.update(10.0, 115, 100)); self.assertFalse(w.on)

    def test_below_120_nothing_and_water_warns_when_the_oil_sensor_is_lost(self):
        w = Warning(config())
        w.update(0.0, 119, 109); w.update(2.0, 119, 109)
        self.assertFalse(w.on)  # no caution level below the warning any more
        w2 = Warning(config())
        w2.update(0.0, None, 112); self.assertEqual(w2.update(1.0, None, 112), 'warn')
        self.assertEqual((w2.on, shown(w2)), (True, [('水温', 112)]))

    def test_oil_pressure_line_follows_the_engine_speed(self):
        c = config()
        self.assertIsNone(press_limit(c, None))
        self.assertIsNone(press_limit(c, 900))     # idle: 80 kPa hot is normal
        self.assertIsNone(press_limit(c, 1499))
        self.assertEqual(press_limit(c, 1500), 100)
        self.assertAlmostEqual(press_limit(c, 2250), 150)
        self.assertEqual((press_limit(c, 3000), press_limit(c, 7200)), (200, 200))  # flat above 3000 rpm
        self.assertIsNone(press_limit(config(oil_press_warn='broken'), 4000))   # a bad setting never stops the dash

    def test_oil_pressure_warns_after_half_a_second_only_with_the_engine_running(self):
        w = Warning(config())
        self.assertIsNone(w.update(0.0, 98, 88, 0.0, 0.0))     # engine off: 0 kPa, no warning
        self.assertIsNone(w.update(5.0, 98, 88, 60.0, 1000))   # idle
        self.assertIsNone(w.update(9.0, 98, 88, 60.0, 1000)); self.assertFalse(w.on)
        self.assertIsNone(w.update(10.0, 98, 88, 150.0, 5000))
        self.assertIsNone(w.update(10.4, 98, 88, 150.0, 5000)); self.assertFalse(w.on)
        self.assertEqual(w.update(10.5, 98, 88, 150.0, 5000), 'warn')
        self.assertEqual(shown(w), [('油圧', 150.0)])
        self.assertIsNone(w.update(11.0, 98, 88, 380.0, 5000)); self.assertTrue(w.on)  # off 5 s after
        self.assertIsNone(w.update(16.0, 98, 88, 380.0, 5000)); self.assertFalse(w.on)
        self.assertIsNone(w.update(20.0, 98, 88, None, 5000)); self.assertFalse(w.on)  # no sensor: nothing

    def test_warnings_side_by_side_each_with_its_sound(self):
        w = Warning(config())
        w.update(0.0, 122, 100, 380.0, 5000)
        self.assertEqual(w.update(1.0, 122, 100, 380.0, 5000), 'warn')
        w.update(2.0, 124, 104, 120.0, 5000)
        self.assertEqual(w.update(2.5, 124, 104, 120.0, 5000), 'warn')  # the oil pressure comes on: a new sound
        self.assertEqual(shown(w), [('油圧', 120.0), ('油温', 124)])      # oil pressure first
        w.update(3.0, 125, 111, 120.0, 5000)
        self.assertEqual(w.update(4.0, 125, 111, 120.0, 5000), 'warn')
        self.assertEqual([a.label for a in w.active()], ['油圧', '油温', '水温'])
        self.assertIsNone(w.update(4.1, 126, 112, 110.0, 5000))  # all on already: no more sound


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
        self.assertEqual((s['last_note'], s['last_note_kind']), ('前周比 +0.41s', 'slower'))
        self.assertEqual((s['notice'], s['warn']), ('', False))
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
        self.assertEqual((s['delta'], s['notice']), ('--', 'PIT IN'))
        s, _ = m.update(moving(LapStartPit=True, LastLapPit=True), 0.2)  # the out lap
        self.assertEqual((s['delta'], s['delta_kind'], s['delta_frac'], s['notice']), ('--', None, None, 'PIT OUT'))
        self.assertEqual((s['last_note'], s['last_note_kind'], s['warn']), ('PIT', 'pit', False))
        stopped = moving(); stopped['sample']['values']['GPSSpeed'] = 3.0
        s, _ = m.update(stopped, 0.3)  # stopped on the in lap (a box before the line): nothing known yet
        self.assertEqual((s['delta'], s['notice']), ('--', ''))

    def test_the_temperature_warning_is_apart_from_the_pit_strip(self):
        m = DashModel(config())
        out_lap = {'CurrentLap': 9, 'ElapsedTime': 0.5, 'LapStartPit': True, 'LastLapPit': True}
        sounds = [m.update(frame(out_lap, oil=122), k * 0.1)[1] for k in range(12)]
        s, _ = m.update(frame(out_lap, oil=122), 1.2)
        self.assertEqual((s['warn'], s['warns'], s['notice']), (True, [{'label': '油温', 'value': '122', 'unit': '℃'}], 'PIT OUT'))
        self.assertEqual([x for x in sounds if x], ['warn'])

    def test_the_band_flashes_for_ten_seconds_after_each_new_warning(self):
        w = Warning(config())
        w.update(0.0, 122, 100); w.update(1.0, 122, 100)  # the oil comes on at 1.0
        self.assertTrue(w.flashing(1.0)); self.assertTrue(w.flashing(10.9))
        self.assertFalse(w.flashing(11.0))  # then steady red
        w.update(20.0, 122, 100, 120.0, 5000); w.update(20.5, 122, 100, 120.0, 5000)  # the oil pressure joins
        self.assertTrue(w.flashing(20.5)); self.assertFalse(w.flashing(30.5))
        self.assertFalse(Warning(config(flash_s=0)).flashing(0.0))
        m = DashModel(config())
        states = [m.update(frame(oil=125), k * 0.5)[0] for k in range(30)]
        self.assertEqual([s['warn_flash'] for s in states if s['warn']][:2], [True, True])
        self.assertEqual((states[-1]['warn'], states[-1]['warn_flash']), (True, False))

    def test_the_band_lists_every_warning_and_the_sensor_light(self):
        m = DashModel(config())
        s, _ = m.update(frame(oil=98), 0.0)
        self.assertEqual((s['press_sensor'], s['sensor']), (None, ('油温センサー', True)))  # oil pressure not wired yet
        for k in range(12):
            s, _ = m.update(frame(oil=123, press=110.0, rpm=5200.0), 0.1 + k * 0.1)
        self.assertEqual(s['warns'], [{'label': '油圧', 'value': '110', 'unit': 'kPa'},
                                      {'label': '油温', 'value': '123', 'unit': '℃'}])
        self.assertEqual((s['press_sensor'], s['sensor']), (True, ('油温・油圧', True)))
        s, _ = m.update(frame(oil=98), 2.0)  # the oil pressure lost after it had come
        self.assertEqual((s['press_sensor'], s['sensor']), (False, ('油圧センサー途絶', False)))
        self.assertEqual(s['warns'][0], {'label': '油圧', 'value': '110', 'unit': 'kPa'})  # last value until it goes off
        self.assertEqual([sensor_light(False, None), sensor_light(False, True), sensor_light(False, False)],
                         [('油温センサー途絶', False), ('油温センサー途絶', False), ('油温・油圧途絶', False)])

    def test_no_warning_from_values_of_a_dead_link(self):
        m = DashModel(config())
        m.update(frame(oil=135), 0.0)
        s, sound = m.update(frame(oil=135, connected=False), 1.5)
        self.assertEqual((s['warn'], sound), (False, None))


class SoundAndConfigTests(unittest.TestCase):
    def test_tones(self):
        with wave.open(io.BytesIO(tone_wav('warn')), 'rb') as w:
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 2.0, places=2)

    def test_config_file_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dash.json'
            path.write_text(json.dumps({'oil_warn': 115, 'sound': {'device': 'hdmi'}, 'unknown': 1}))
            c = load_config(path)
            self.assertEqual(c['oil_warn'], 115)
            self.assertEqual((c['sound']['device'], c['sound']['volume']), ('hdmi', 0.8))
            self.assertNotIn('unknown', c)
        self.assertEqual(load_config('/nonexistent.json')['water_warn'], 110.0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dash.json'
            path.write_text(json.dumps({'oil_press_warn': [[2000, 150], [4000, 250]], 'oil_press_min_rpm': 2000}))
            c = load_config(path)
            self.assertEqual((press_limit(c, 1900), press_limit(c, 3000), press_limit(c, 6000)), (None, 200, 250))


if __name__ == '__main__':
    unittest.main()
