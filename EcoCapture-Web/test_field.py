import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import field
from lap import LapTimer
from test_lap import LAT0, EARTH_M_PER_DEG, fix

HEAD = {'X-EcoCapture': '1'}


class FakeRuntime:
    def __init__(self, root):
        self.laps = LapTimer(root)
        self.sample = None
        self.connected = True
        self.logging = {'active': True, 'error': None, 'sd_warning': None}

    def status(self):
        return {'connected': self.connected, 'logging': self.logging}

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
