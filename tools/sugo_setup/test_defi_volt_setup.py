import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import defi_volt_setup
import sugo_setup

OIL = {'channel': 2, 'name': 'OilTemp', 'unit': '°C', 'can_id': 0x600, 'conversion': 'sensorhub_oiltemp'}
SIGNALS = [{'channel': 1, 'name': 'RPM', 'can_id': 0x201, 'conversion': 'linear'}, OIL]


class FakeUnoQ:
    """本体の代わり：組み立てたシェルのコマンドを読んで、APIと設定ファイルの退避を真似る"""
    def __init__(self, knows_defi_volt=True):
        self.config = {'schema': 1, 'profile': 'ncec-2005-mt', 'signals': list(SIGNALS)}
        self.recording = True; self.knows = knows_defi_volt; self.stop_reply_lost = False
        self.files = {'config.json': json.dumps(self.config)}; self.posts = []

    def __call__(self, command):
        words = shlex.split(command)
        if words[0] == 'curl':
            path = next(w for w in words if w.startswith('http')).removeprefix(sugo_setup.API)
            body = json.loads(words[words.index('--data-binary') + 1]) if '--data-binary' in words else None
            if body is not None and 'X-EcoCapture: 1' not in words:
                return '{"detail":"操作ヘッダーが必要です"}\n403'
            if path == '/api/log/stop' and self.stop_reply_lost:  # 本体は止めたが、応答がcurlの待ち時間に間に合わない
                self.recording = False; self.posts.append(path)
                raise RuntimeError('本体でのコマンドが失敗しました: 000')
            return self.api(path, body)
        if words[0] == 'cd':  # cd DATA || exit 1; [ -e NAME ] || cp -p config.json NAME; ls -l NAME
            self.files.setdefault(words[-1], self.files['config.json'])
            return words[-1] + '\n'
        raise AssertionError(command)

    def api(self, path, body):
        if body is not None:
            self.posts.append(path)
        if path == '/api/config' and body is not None:
            if self.recording:
                return '{"detail":"設定を保存する前に記録を停止してください"}\n409'
            if not self.knows and any(s.get('conversion') == 'defi_volt' for s in body['signals']):
                return '{"detail":[{"msg":"Input should be \'linear\', \'ntc\' or \'sensorhub_oiltemp\'"}]}\n422'
            self.config = body; self.files['config.json'] = json.dumps(body)
        if path == '/api/log/stop':
            self.recording = False
        if path == '/api/log/start':
            self.recording = True
        result = {'/api/config': self.config,
                  '/api/status': {'hardware': {'can_counts': [6800, 0]}, 'logging': {'active': self.recording},
                                  'sd_copy': {'active': False}},
                  '/api/telemetry': {'sample': {'can_signals': {}, 'can_states': {}}},
                  '/api/log/stop': {}, '/api/log/start': {}}[path]
        return json.dumps(result) + '\n200'


class DefiVoltSetupTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeUnoQ()
        self.runner, self.backups = sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS
        sugo_setup.runner = lambda use_adb, host: self.device
        self.folder = tempfile.TemporaryDirectory(); defi_volt_setup.LOCAL_BACKUPS = Path(self.folder.name)

    def tearDown(self):
        sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS = self.runner, self.backups
        self.folder.cleanup()

    def test_check_only_changes_nothing(self):
        self.assertEqual(defi_volt_setup.main([]), 0)
        self.assertEqual(self.device.posts, [])
        self.assertEqual(list(defi_volt_setup.LOCAL_BACKUPS.iterdir()), [])

    def test_apply_backs_up_stops_recording_and_keeps_other_signals(self):
        self.assertEqual(defi_volt_setup.main(['--apply']), 0)
        self.assertEqual(self.device.posts, ['/api/log/stop', '/api/config', '/api/log/start'])
        self.assertTrue(self.device.recording)
        self.assertEqual(self.device.config['signals'], SIGNALS + defi_volt_setup.DEFI_SIGNALS)
        self.assertEqual([(s['name'], s['byte_offset'], s['can_id']) for s in defi_volt_setup.DEFI_SIGNALS],
                         [('PressVolt', 0, 0x580), ('Temp1Volt', 2, 0x580), ('Temp2Volt', 4, 0x580)])
        backup = next(n for n in self.device.files if n.startswith('config.json.bak-'))
        self.assertTrue(backup.endswith('-before-defivolt'))
        self.assertEqual(json.loads(self.device.files[backup])['signals'], SIGNALS)
        local, = defi_volt_setup.LOCAL_BACKUPS.glob('*/config.json')
        self.assertEqual(json.loads(local.read_text(encoding='utf-8'))['signals'], SIGNALS)
        # 2回目は何もしない
        self.assertEqual(defi_volt_setup.main(['--apply']), 0)
        self.assertEqual(len(self.device.posts), 3)

    def test_the_signals_pass_the_logger_model(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'EcoCapture-Web'))
        try:
            from models import Signal
        except ImportError as error:  # pydanticが無いPC
            self.skipTest(str(error))
        for sig in defi_volt_setup.DEFI_SIGNALS:
            self.assertEqual(Signal(**sig).model_dump(), sig)

    def test_remove_puts_only_the_voltage_signals_away(self):
        defi_volt_setup.main(['--apply'])
        self.assertEqual(defi_volt_setup.main(['--remove']), 0)
        self.assertEqual(self.device.config['signals'], SIGNALS)
        self.assertTrue(self.device.recording)

    def test_old_logger_is_reported_and_recording_resumes(self):
        self.device = FakeUnoQ(knows_defi_volt=False)
        with self.assertRaises(RuntimeError):
            defi_volt_setup.main(['--apply'])
        self.assertEqual(self.device.config['signals'], SIGNALS)
        self.assertTrue(self.device.recording)

    def test_lost_stop_reply_still_resumes_recording(self):
        self.device.stop_reply_lost = True
        with self.assertRaises(RuntimeError):
            defi_volt_setup.main(['--apply'])
        self.assertEqual(self.device.posts, ['/api/log/stop', '/api/log/start'])
        self.assertEqual(self.device.config['signals'], SIGNALS)
        self.assertTrue(self.device.recording)


if __name__ == '__main__':
    unittest.main()
