import json
import shlex
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sugo_setup

ECORUN = {'enabled': True, 'lat': 36.5337, 'lon': 140.2255, 'bearing': 154.2, 'width_m': 30.0, 'min_lap_s': 10.0,
          'max_lap_s': 3600.0, 'start': {'lat': 36.5314, 'lon': 140.2274, 'bearing': 151.5, 'width_m': 30.0},
          'goal': {'lat': 36.5337, 'lon': 140.2258, 'bearing': 151.0, 'width_m': 30.0}, 'total_laps': 7,
          'time_limit_s': 2360.11, 'margin_s': 30.0, 'set_at': '2026-10-25T03:31+09:00'}
SIGNALS = [{'name': 'RPM'}, {'name': 'Speed'}]


class FakeUnoQ:
    """本体の代わり：sugo_setupが組み立てたシェルのコマンドを読んで、APIとファイルを真似る"""
    def __init__(self):
        self.line = dict(ECORUN); self.laps = 7; self.files = {'lap.json': json.dumps({'line': ECORUN})}
        self.posts = []

    def __call__(self, command):
        words = shlex.split(command)
        if words[0] == 'curl':
            url = next(w for w in words if w.startswith('http'))
            path = url.removeprefix(sugo_setup.API)
            body = json.loads(words[words.index('--data-binary') + 1]) if '--data-binary' in words else None
            if body is not None and 'X-EcoCapture: 1' not in words:  # 本物と同じく、操作ヘッダーの無い書き込みは断る
                return '{"detail":"操作ヘッダーが必要です"}\n403'
            return json.dumps(self.api(path, body)) + '\n200'
        if words[0] == 'cat':
            return self.files[words[1].rsplit('/', 1)[1]]
        if words[0] == 'cd':  # 退避: cd DATA && [ -e NAME ] || cp -p lap.json NAME; ls -l NAME
            name = words[-1]; self.files.setdefault(name, self.files['lap.json'])
            return name + '\n'
        raise AssertionError(command)

    def api(self, path, body):
        if body is not None:
            self.posts.append(path)
        if path == '/api/config':
            return {'profile': 'ncec-2005-mt', 'signals': SIGNALS + [{'name': 'OilTemp'}]}
        if path == '/api/can/ncec':
            return {'signals': SIGNALS}
        if path == '/api/status':
            return {'hardware': {'can1_ready': 1, 'result': 'CAN1 listen-only'}}
        if path == '/api/podium':
            return {'config': {'enabled': True, 'link': 'lte', 'destination': 'server', 'backup_server_urls': []}}
        if path == '/api/lap':
            if body is not None:
                self.line = {**self.line, **body}
                self.files['lap.json'] = json.dumps({'line': self.line})
            return {'line': self.line, 'values': {'LapCount': self.laps}}
        if path == '/api/lap/reset':
            self.laps = 0
            return {}
        raise AssertionError(path)


class SugoSetupTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeUnoQ()
        self.runner = sugo_setup.runner
        sugo_setup.runner = lambda use_adb, host: self.device

    def tearDown(self):
        sugo_setup.runner = self.runner

    def test_check_only_changes_nothing(self):
        self.assertEqual(sugo_setup.main([]), 0)
        self.assertEqual(self.device.posts, [])
        self.assertEqual(self.device.line, ECORUN)

    def test_apply_backs_up_then_sets_the_sugo_line_and_resets(self):
        self.assertEqual(sugo_setup.main(['--apply']), 0)
        self.assertEqual(self.device.posts, ['/api/lap', '/api/lap/reset'])
        self.assertEqual(sugo_setup.line_changes(self.device.line), [])
        self.assertIsNone(self.device.line['start'])
        self.assertEqual(self.device.laps, 0)
        backup = next(n for n in self.device.files if n.startswith('lap.json.bak-'))
        self.assertTrue(backup.endswith('-ecorun'))
        self.assertEqual(json.loads(self.device.files[backup])['line'], ECORUN)
        # 2回目は何もしない（退避を上書きしない）
        self.assertEqual(sugo_setup.main(['--apply']), 0)
        self.assertEqual(self.device.posts, ['/api/lap', '/api/lap/reset'])

    def test_reset_only_clears_laps_on_the_sugo_line(self):
        self.assertEqual(sugo_setup.main(['--reset']), 1)  # エコランのラインのままなら消さない
        self.assertEqual((self.device.posts, self.device.laps), ([], 7))
        sugo_setup.main(['--apply']); self.device.laps = 3
        self.assertEqual(sugo_setup.main(['--reset']), 0)
        self.assertEqual(self.device.posts[-1], '/api/lap/reset')
        self.assertEqual(self.device.laps, 0)
        self.assertEqual(sugo_setup.line_changes(self.device.line), [])

    def test_restore_puts_the_saved_lines_back(self):
        sugo_setup.main(['--apply'])
        backup = next(n for n in self.device.files if n.startswith('lap.json.bak-'))
        self.assertEqual(sugo_setup.main(['--restore', backup]), 0)
        self.assertEqual(self.device.line, ECORUN)


if __name__ == '__main__':
    unittest.main()
