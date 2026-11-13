"""設定を本体へ入れる道具（setups_apply.py）の試験。本体の代わりに、組み立てたコマンドを読んで真似る作りものを使う。"""
import base64
import contextlib
import copy
import io
import json
import re
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import setups
import setups_apply as tool

RELAY = 'wss://relay.example/ws/audio/'


class FakeUnoQ:
    def __init__(self):
        vehicle, course = setups.load('vehicle', 'ncec'), setups.load('course', 'sugo')
        self.config = {'schema': 1, 'device_name': 'EcoLogger V2', 'auto_record': True, **copy.deepcopy(vehicle['logger'])}
        self.line = {**copy.deepcopy(course['line']), 'set_at': '2026-11-08T06:46+09:00'}
        self.podium = {'enabled': True, 'destination': 'server', 'server_url': RELAY + 'ncec', 'backup_server_urls': [],
                       'channels': list(vehicle['send']['channels'])}
        self.recording, self.files, self.posts, self.backups = True, {}, [], []
        self.lap_state = {'count': 12}

    def __call__(self, command):
        if command.startswith('cat '):
            return self.files.get(command.split()[1], '')
        if command.startswith('mkdir -p '):
            m = re.search(r'echo (\S+) \| base64 -d > (\S+)\.tmp', command)
            self.files[m.group(2)] = base64.b64decode(m.group(1)).decode()
            return ''
        if command.startswith('cd '):   # cd DATA || exit 1; [ -e NAME ] || cp -p <file> NAME; ls -l NAME
            self.backups.append(shlex.split(command)[-1])
            return self.backups[-1] + '\n'
        words = shlex.split(command)
        assert words[0] == 'curl', command
        path = next(w for w in words if w.startswith('http')).removeprefix(tool.API)
        body = json.loads(words[words.index('--data-binary') + 1]) if '--data-binary' in words else None
        if body is not None:
            assert 'X-EcoCapture: 1' in words
            self.posts.append(path)
        if path == '/api/config' and body is not None:
            if self.recording:
                return '{"detail":"設定を保存する前に記録を停止してください"}\n409'
            self.config = body
        if path == '/api/lap' and body is not None:
            self.line = {**self.line, **body}
        if path == '/api/podium' and body is not None:
            self.podium.update(body)
        if path == '/api/log/stop':
            self.recording = False
        if path == '/api/log/start':
            self.recording = True
        result = {'/api/config': self.config, '/api/lap': {'line': self.line, 'values': {'LapCount': self.lap_state['count']}},
                  '/api/podium': {'config': self.podium, 'channels': [{'name': n} for n in sorted(setups.BUILT_IN_CHANNELS | {s['name'] for s in self.config['signals']})]},
                  '/api/status': {'logging': {'active': self.recording}, 'sd_copy': {'active': False}},
                  '/api/log/stop': {}, '/api/log/start': {}}[path]
        return json.dumps(result) + '\n200'


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.device = FakeUnoQ()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(tool, 'LOCAL_BACKUPS', Path(self.tmp.name) / 'config-backups')
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_tool(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tool.main(list(args), run=self.device)
        return code, out.getvalue()

    def test_check_only_changes_nothing_and_reports(self):
        self.device.line['lat'] += 0.001
        code, text = self.run_tool('--vehicle', 'ncec', '--course', 'sugo')
        self.assertEqual(code, 1)
        self.assertEqual((self.device.posts, self.device.backups, self.device.files), ([], [], {}))
        self.assertIn('line.lat', text)
        self.assertIn('本体に無い・違うコースの設定: sugo', text)
        self.assertIn('本体は変えていません', text)

    def test_course_apply_puts_files_backs_up_and_keeps_recording_and_laps(self):
        self.device.line['lat'] += 0.001
        code, text = self.run_tool('--course', 'sugo', '--apply')
        self.assertEqual(code, 0, text)
        self.assertEqual(json.loads(self.device.files[f'{tool.COURSE_DIR}/sugo.json']), setups.load('course', 'sugo'))
        self.assertEqual(self.device.posts, ['/api/lap'])                       # 記録は止めない・ラップは消さない
        self.assertTrue(self.device.recording)
        self.assertEqual(self.device.lap_state['count'], 12)
        self.assertRegex(self.device.backups[0], r'^lap\.json\.bak-\d{8}-\d{6}$')
        self.assertEqual(setups.diff_course(setups.load('course', 'sugo'), self.device.line), [])
        self.assertEqual(self.run_tool('--course', 'sugo', '--apply')[0], 0)    # 2回目は何もしない
        self.assertEqual((self.device.posts, len(self.device.backups)), (['/api/lap'], 1))

    def test_vehicle_apply_stops_recording_saves_and_restarts(self):
        self.device.config['signals'] = self.device.config['signals'][:12]      # Defiの信号がまだ無い本体
        self.device.podium['channels'] = ['Lat', 'Lon', 'Speed']
        code, text = self.run_tool('--vehicle', 'ncec', '--apply')
        self.assertEqual(code, 0, text)
        self.assertEqual(self.device.posts, ['/api/log/stop', '/api/config', '/api/log/start', '/api/podium'])
        self.assertTrue(self.device.recording)
        self.assertEqual(len(self.device.config['signals']), 17)
        self.assertEqual(self.device.podium['channels'], setups.load('vehicle', 'ncec')['send']['channels'])
        saved, = (Path(self.tmp.name) / 'config-backups').glob('*/config.json')
        self.assertEqual(len(json.loads(saved.read_text(encoding='utf-8'))['signals']), 12)   # 控えは入れる前の設定
        self.assertIn('before-setup-ncec', self.device.backups[0])
        self.assertIn('ここで分かれます', text)

    def test_same_vehicle_does_not_stop_recording(self):
        code, _ = self.run_tool('--vehicle', 'ncec', '--apply')
        self.assertEqual((code, self.device.posts), (0, []))

    def test_room_is_changed_without_showing_the_server(self):
        self.device.podium.update(server_url=RELAY + 'majesta', backup_server_urls=[RELAY + 'majesta'])
        code, text = self.run_tool('--vehicle', 'ncec', '--apply')
        self.assertEqual(code, 0, text)
        self.assertEqual((self.device.podium['server_url'], self.device.podium['backup_server_urls']), (RELAY + 'ncec', [RELAY + 'ncec']))
        self.assertNotIn('relay.example', text)
        self.assertIn('majesta', text)

    def test_room_is_left_alone_when_the_destination_is_not_a_relay(self):
        self.device.podium.update(server_url='', destination='server')
        code, text = self.run_tool('--vehicle', 'ncec', '--apply')
        self.assertEqual(code, 1)
        self.assertIn('部屋は変えません', text)
        self.assertEqual(self.device.posts, [])

    def test_bad_names_and_device_errors(self):
        self.assertEqual(self.run_tool('--course', 'nothing')[0], 2)

        def broken(command):
            raise RuntimeError('本体でのコマンドが失敗しました: timeout')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tool.main(['--course', 'sugo'], run=broken), 1)
        self.assertIn('★', out.getvalue())


if __name__ == '__main__':
    unittest.main()
