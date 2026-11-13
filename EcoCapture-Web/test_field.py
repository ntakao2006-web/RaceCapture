import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import field
from lap import LapTimer
from test_lap import LAT0, EARTH_M_PER_DEG, fix

HEAD = {'X-EcoCapture': '1'}
DASH_MODEL = Path(__file__).resolve().parent.parent / 'RaceCapture-UNOQ' / 'dash_model.py'


class FakeRuntime:
    def __init__(self, root):
        self.laps = LapTimer(root)
        self.sample = None
        self.connected = True
        self.logging = {'active': True, 'error': None, 'sd_warning': None}
        self.video = None
        self.podium = None  # None: status() without the item

    def status(self):
        status = {'connected': self.connected, 'logging': self.logging, 'video': self.video}
        return status if self.podium is None else {**status, 'podium': self.podium}

    def feed(self, sample):
        self.laps.update(sample)
        self.sample = sample


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.root = Path(self.dir.name)
        self.runtime = FakeRuntime(self.root)
        self.token = field.load_token(self.root)
        self.client = TestClient(field.create_app(self.runtime, self.token))
        self.key = {**HEAD, 'X-Field-Key': self.token}

    def tearDown(self):
        self.dir.cleanup()

    def stand(self, north_m, start_ms=0):
        for k in range(35):
            self.runtime.feed(fix(start_ms + k * 100, north_m, speed=0.2))

    def test_token_is_kept_private_and_reused(self):
        self.assertGreaterEqual(len(self.token), 8)
        self.assertEqual(field.load_token(self.root), self.token)
        if os.name == 'posix':
            self.assertEqual((self.root / 'field_token').stat().st_mode & 0o777, 0o600)
        url = field.field_urls(self.token, ['192.168.1.5'])
        self.assertEqual(url, [f'http://uno-q.local:8082/?k={self.token}', f'http://192.168.1.5:8082/?k={self.token}'])

    def test_api_needs_the_key_and_the_header(self):
        self.assertEqual(self.client.get('/api/field/state').status_code, 403)
        self.assertEqual(self.client.get('/api/field/state', headers={'X-Field-Key': 'wrong-key!'}).status_code, 403)
        self.assertEqual(self.client.get(f'/api/field/state?k={self.token}').status_code, 200)
        self.assertEqual(self.client.post('/api/field/reset', headers={'X-Field-Key': self.token}).status_code, 403)
        self.assertEqual(self.client.post('/api/field/reset', headers=self.key).status_code, 200)

    def test_live_stream_needs_the_key_and_sends_the_fix(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/api/field/live?k=wrong-key!') as ws:
                ws.receive_text()
        self.runtime.feed(fix(1500, 10.0, speed=31.0, hacc=0.6))
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            frame = ws.receive_json()
        self.assertTrue(frame['connected'])
        self.assertEqual(frame['utc'], 1792800001500)
        self.assertAlmostEqual(frame['speed'], 31.0)
        self.assertAlmostEqual(frame['hacc_m'], 0.6)
        self.assertTrue(frame['rec'])
        self.assertIsNone(frame['line_id'])
        self.assertIsNone(frame['line_code'])
        self.assertEqual(frame['lap'], {'count': 0, 'laps_left': None, 'finished': False, 'running': False})
        self.client.post('/api/field/here', json={'target': 'control'}, headers=self.key).raise_for_status()
        self.client.post('/api/field/total', json={'total_laps': 3}, headers=self.key).raise_for_status()
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            frame = ws.receive_json()
        self.assertTrue(frame['line_code'].startswith('ECOLINES1|c='))
        self.assertTrue(frame['line_code'].endswith('id=' + frame['line_id']))
        self.assertEqual(frame['total_laps'], 3)
        self.assertIsNone(frame['time_limit_s'])
        self.client.post('/api/field/total', json={'time_limit_s': 2360.11, 'margin_s': 30}, headers=self.key).raise_for_status()
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            frame = ws.receive_json()
        self.assertEqual((frame['total_laps'], frame['time_limit_s'], frame['margin_s']), (3, 2360.11, 30))
        self.assertEqual(frame['lap']['laps_left'], 3)
        self.runtime.connected = False
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            frame = ws.receive_json()
        self.assertFalse(frame['connected'])
        self.assertIsNone(frame['lat'])
        self.assertIsNone(frame['dash'])

    def test_live_stream_carries_what_the_dash_shows(self):
        # The phone's circuit screen (android-logger Circuit.kt) shows what EcoCapture DASH does.
        sample = fix(1500, 10.0, speed=0.0)
        sample['can_signals'] = {'OilTemp': 121.5, 'WaterTemp': float('nan'), 'Speed': 42.0, 'OilPress': 85.0}
        sample['values']['WaterTemp'] = 96.0
        sample['values']['RPM'] = 5200.0
        sample['gnss_utc'] = '2026-11-08T02:16:15Z'
        self.runtime.feed(sample)
        sample['lap'] = {'CurrentLap': 9, 'ElapsedTime': 0.5, 'LapTime': 1.87, 'BestLap': 1.85, 'RaceTime': 20.0,
                         'LapDiffS': 0.41, 'LastLapPit': True, 'LapStartPit': True, 'LapsLeft': None}
        self.runtime.video = {'recording': True, 'minutes_left': 148}
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            dash = ws.receive_json()['dash']
        self.assertEqual(dash['lap'], sample['lap'])
        self.assertEqual((dash['oil'], dash['water'], dash['speed']), (121.5, 96.0, 0.0))  # the CAN first, NaN skipped
        self.assertEqual((dash['press'], dash['rpm']), (85.0, 5200.0))  # the oil pressure warning, against the engine speed
        self.assertEqual((dash['utc'], dash['video']), ('2026-11-08T02:16:15Z', {'recording': True, 'minutes_left': 148}))
        del sample['values']['GPSSpeed']
        del sample['can_signals']['OilPress']
        with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
            dash = ws.receive_json()['dash']
        self.assertEqual(dash['speed'], 42.0)  # no GNSS speed: the car's
        self.assertIsNone(dash['press'])  # not wired: no oil pressure, so no warning on the phone

    def test_live_stream_says_whether_the_logger_sends(self):
        # The eco-run screen's light (android-logger LoggerLights.kt, SPEC.md M-2): one word, None when not known.
        def frame():
            with self.client.websocket_connect(f'/api/field/live?k={self.token}') as ws:
                return ws.receive_json()
        self.assertIn('send', frame())
        self.assertIsNone(frame()['send'])  # status() without 'podium'
        ok = {'enabled': True, 'state': 'streaming', 'message': 'センサ値を送信中', 'last_sent_age_ms': 120}
        for podium, want in ((ok, 'ok'), ({**ok, 'last_sent_age_ms': 5000}, 'ok'), ({**ok, 'last_sent_age_ms': 5001}, 'warn'),
                             ({**ok, 'last_sent_age_ms': None}, 'warn'), ({**ok, 'state': 'retry'}, 'warn'),
                             ({**ok, 'state': 'waiting_gps'}, 'warn'),
                             ({'enabled': False, 'state': 'off', 'last_sent_age_ms': 90000}, 'off')):
            self.runtime.podium = podium
            self.assertEqual(frame()['send'], want, podium)
        # Sending does not wait for the MCU or the log: the light is there without a sample and without recording
        self.runtime.podium = ok
        self.runtime.connected = False
        self.runtime.logging = {'active': False, 'error': None, 'sd_warning': None}
        self.assertEqual((frame()['send'], frame()['rec'], frame()['fix']), ('ok', False, None))

    def test_send_state_is_one_small_word(self):
        ok = {'enabled': True, 'state': 'streaming', 'last_sent_age_ms': 120}
        self.runtime.feed(fix(1500, 10.0, speed=31.0, hacc=0.6))
        without = len(json.dumps(field.live_frame(self.runtime)))
        self.runtime.podium = ok
        self.assertLessEqual(len(json.dumps(field.live_frame(self.runtime))) - without, 2)  # null -> "ok"
        self.runtime.podium = {**ok, 'state': 'retry'}
        self.assertLessEqual(len(json.dumps(field.live_frame(self.runtime))) - without, 2)  # null -> "warn"
        self.assertEqual(len(json.dumps({'send': 'warn'})) - len(json.dumps({})), 14)  # the item at its longest

    @unittest.skipUnless(DASH_MODEL.exists(), 'RaceCapture-UNOQ/dash_model.py is not here (on the logger)')
    def test_send_state_is_the_kind_of_the_dash_light(self):
        # field.py cannot import RaceCapture-UNOQ, so the rule is written twice: this holds them together.
        spec = importlib.util.spec_from_file_location('dash_model_for_field_test', DASH_MODEL)
        dash_model = importlib.util.module_from_spec(spec); spec.loader.exec_module(dash_model)
        self.assertEqual(field.SEND_STALE_S, dash_model.DEFAULTS['send_stale_s'])
        states = ('streaming', 'off', 'connecting', 'authenticating', 'waiting', 'waiting_gps', 'retry', 'auth_failed',
                  'relay_connecting', None, 7)
        ages = (None, 0, 120, 4999.5, 5000, 5001, 90000, -1, 'x', True, float('nan'), float('inf'))
        cases = [None, 'streaming', [], 3, {}, {'state': 'off'}, {'state': 'streaming', 'last_sent_age_ms': 80}]
        for enabled in (True, False, None, 'absent'):
            for state in states:
                for age in ages:
                    podium = {'state': state, 'last_sent_age_ms': age}
                    cases.append(podium if enabled == 'absent' else {**podium, 'enabled': enabled})
        for podium in cases:
            for stale_s in (field.SEND_STALE_S, 2.0):
                self.assertEqual(field.send_state(podium, stale_s), dash_model.send_light(podium, stale_s)[1], (podium, stale_s))
        self.assertEqual({field.send_state(p) for p in cases}, {'ok', 'warn', 'off', None})

    def test_page_is_served_without_admin_routes(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('コースウォーク', page.text)
        self.assertEqual(self.client.get('/field.js').status_code, 200)
        self.assertEqual(self.client.get('/index.html').status_code, 404)
        for path in ('/api/config', '/api/logs', '/api/device/wifi', '/api/lap'):
            self.assertIn(self.client.get(path, headers=self.key).status_code, (404, 405))

    def test_course_walk_registers_three_lines_laps_and_reset(self):
        state = self.client.get('/api/field/state', headers=self.key).json()
        self.assertIsNone(state['gnss']['lat'])
        self.assertEqual(self.client.post('/api/field/here', json={'target': 'control'}, headers=self.key).status_code, 409)
        self.stand(-300)
        self.client.post('/api/field/here', json={'target': 'start'}, headers=self.key).raise_for_status()
        self.stand(0, 10000)
        d = self.client.post('/api/field/here', json={'target': 'control'}, headers=self.key).json()
        self.assertEqual(d['here']['fixes'], 31)
        self.stand(-80, 20000)
        self.client.post('/api/field/here', json={'target': 'goal'}, headers=self.key).raise_for_status()
        line = self.runtime.laps.line
        self.assertTrue(line.enabled)
        self.assertAlmostEqual((line.start.lat - LAT0) * EARTH_M_PER_DEG, -300, delta=0.1)
        self.assertAlmostEqual((line.goal.lat - LAT0) * EARTH_M_PER_DEG, -80, delta=0.1)
        self.assertIsNone(line.bearing)  # learned on the first pass
        d = self.client.post('/api/field/total', json={'total_laps': 3}, headers=self.key).json()
        self.assertEqual(d['line']['total_laps'], 3)
        d = self.client.post('/api/field/total', json={'total_laps': None}, headers=self.key).json()
        self.assertIsNone(d['line']['total_laps'])
        self.assertEqual(self.client.post('/api/field/total', json={'total_laps': 0}, headers=self.key).status_code, 400)
        d = self.client.post('/api/field/total', json={'total_laps': 7, 'time_limit_s': 987.36, 'margin_s': 30}, headers=self.key).json()
        self.assertEqual((d['line']['total_laps'], d['line']['time_limit_s'], d['line']['margin_s']), (7, 987.36, 30))
        self.assertEqual((d['values']['TimeLimit'], d['values']['Margin']), (987.36, 30))
        d = self.client.post('/api/field/total', json={'margin_s': 0}, headers=self.key).json()
        self.assertEqual((d['line']['total_laps'], d['line']['time_limit_s'], d['line']['margin_s']), (7, 987.36, 0))
        for bad in ({'time_limit_s': 0}, {'margin_s': -1}, {'time_limit_s': 'x'}):
            self.assertEqual(self.client.post('/api/field/total', json=bad, headers=self.key).status_code, 400)
        self.runtime.laps.state['count'] = 1
        self.assertEqual(self.client.post('/api/field/total', json={'time_limit_s': 2360.11}, headers=self.key).status_code, 409)
        self.assertEqual(self.client.post('/api/field/total', json={'margin_s': 45}, headers=self.key).status_code, 409)
        same = {'total_laps': 7, 'time_limit_s': 987.36, 'margin_s': 0}  # the same values again are fine
        self.client.post('/api/field/total', json=same, headers=self.key).raise_for_status()
        self.runtime.laps.state['count'] = 0
        self.client.post('/api/field/total', json={'total_laps': None, 'time_limit_s': None, 'margin_s': None}, headers=self.key).raise_for_status()
        self.assertEqual(self.client.post('/api/field/here', json={'target': 'pit'}, headers=self.key).status_code, 400)
        code = self.client.get('/api/field/code', headers=self.key).json()
        self.assertIn('<svg', code['svg'])
        self.assertEqual(len(code['id']), 4)
        self.assertEqual(set(code['unknown_bearing']), {'コントロール', 'スタート', 'ゴール'})
        self.runtime.laps.state['count'] = 2
        self.client.post('/api/field/reset', headers=self.key).raise_for_status()
        self.assertEqual(self.runtime.laps.state['count'], 0)
        state = self.client.get('/api/field/state', headers=self.key).json()
        self.assertNotIn('laps', state['lap'])
        self.assertTrue(state['logging']['active'])
        self.assertIsNotNone(state['gnss']['hacc_m'])

    def test_no_line_qr_until_control_is_set_and_disconnected_logger_refused(self):
        self.assertEqual(self.client.get('/api/field/code', headers=self.key).status_code, 409)
        self.stand(0)
        self.runtime.connected = False
        self.assertEqual(self.client.post('/api/field/here', json={'target': 'control'}, headers=self.key).status_code, 409)


if __name__ == '__main__':
    unittest.main()
