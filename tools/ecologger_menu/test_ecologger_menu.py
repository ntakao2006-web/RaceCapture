import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import ecologger_menu as m


def output(status=None, lap=None, screen='ecocapture-dash: active (power-on: enabled)\nracecapture-app: inactive (power-on: disabled)',
           temps='47800\n52100', uptime='891.16 2424.02'):
    return (f"@@S\n{json.dumps(status) if status else ''}\n@@L\n{json.dumps(lap) if lap else ''}\n"
            f"@@D\n{screen}\n@@H\n{temps}\n@@U\n{uptime}\n")


STATUS = {
    'connected': True, 'receive_hz': 99.6, 'storage_free_bytes': 5 * 2**30,
    'sensors': {'imu': '正常', 'gnss': '3D 12衛星', 'can': 'CAN1 0', 'sd': '記録中 EL1.BIN', 'camera': '接続'},
    'logging': {'active': True, 'name': 'LOG_x.csv', 'elapsed_s': 3725, 'sd_warning': None},
    'video': {'recording': True, 'minutes_left': 190, 'uncollected': 2, 'uncollected_bytes': 3 * 2**30},
    'podium': {'enabled': True, 'state': 'streaming', 'message': '中継サーバーへ送信中', 'radio': {'rsrp': -98}},
}
LAP = {'values': {'LapCount': 12}, 'line': {'enabled': True}}


class SummarizeTests(unittest.TestCase):
    def rows(self, **kw):
        return {name: (value, warn) for name, value, warn in m.summarize(output(**kw))}

    def test_all_well_has_no_warnings(self):
        rows = self.rows(status=STATUS, lap=LAP)
        self.assertEqual([k for k, (_, w) in rows.items() if w], [])
        self.assertEqual(rows['記録'][0], '記録中 1時間02分（LOG_x.csv）')
        self.assertEqual(rows['ラップ'][0], '12周（ライン 有効）')
        self.assertEqual(rows['HDMIの画面'][0], 'EcoCapture DASH')
        self.assertEqual(rows['本体の温度'][0], '52℃')
        self.assertIn('RSRP -98 dBm', rows['LTE'][0])

    def test_stopped_logging_and_no_gps_are_warned(self):
        status = {**STATUS, 'logging': {'active': False, 'error': None},
                  'sensors': {**STATUS['sensors'], 'gnss': '測位待ち'}}
        rows = self.rows(status=status, lap=LAP)
        self.assertTrue(rows['記録'][1])
        self.assertTrue(rows['測位'][1])

    def test_no_answer_from_ecocapture(self):
        rows = self.rows(status=None, lap=None, screen='')
        self.assertTrue(rows['EcoCapture'][1])
        self.assertTrue(rows['HDMIの画面'][1])

    def test_why_usb_is_not_used(self):
        host = output(status=STATUS, lap=LAP) + '@@C\n0\n'
        rows = {n: (v, w) for n, v, w in m.summarize(host, usb=False)}
        self.assertIn('ドックをつないだまま本体が起動', rows['USB'][0])
        self.assertTrue(rows['USB'][1])
        waiting = {n: v for n, v, w in m.summarize(output(status=STATUS, lap=LAP) + '@@C\n1\n', usb=False)}
        self.assertIn('PCから見えません', waiting['USB'])
        self.assertNotIn('USB', {n for n, v, w in m.summarize(host, usb=True)})  # USBでつながっていれば出さない
        self.assertNotIn('USB', {n for n, v, w in m.summarize(output(status=STATUS, lap=LAP), usb=False)})  # 古い本体の出力

    def test_racecapture_screen(self):
        rows = self.rows(status=STATUS, lap=LAP,
                         screen='ecocapture-dash: inactive (power-on: disabled)\nracecapture-app: active (power-on: enabled)')
        self.assertEqual(rows['HDMIの画面'], ('RaceCaptureアプリ', False))


class FakeLink:
    def __init__(self, out='ok'):
        self.out = out

    def run(self, script, timeout=60):
        return self.out

    def label(self):
        return 'USB（テスト）'


class Conn:
    def __init__(self):
        self.text = ''

    def configure(self, text='', foreground=None):
        self.text = text


class StuckReadTests(unittest.TestCase):
    """11/6：開いたメニューが最初に「つながっていません」になったあと二度と読み直さなかった件の再発防止"""

    def setUp(self):
        self.log_patch = mock.patch.object(m, 'LOG_FILE', Path(tempfile.mkdtemp()) / 'menu.log')
        self.log_patch.start()

    def tearDown(self):
        self.log_patch.stop()

    def test_failed_ssh_search_is_forgotten_so_tethering_can_be_found_later(self):
        fake_ssh = types.SimpleNamespace(_found={'unoq': None})
        with mock.patch.dict(sys.modules, {'unoq_ssh': fake_ssh}), \
                mock.patch.object(m.video_collect, 'find_link', return_value=None):
            self.assertIsNone(m.Device(print).find())
        self.assertNotIn('unoq', fake_ssh._found)

    def test_usb_that_appears_while_on_tethering_is_used_next_read(self):
        device = m.Device(print)
        device.link = FakeLink('slow')  # テザリング
        usb = mock.Mock(spec=m.video_collect.AdbLink)
        usb.run.return_value = 'fast'
        usb.label.return_value = 'USB（x）'
        with mock.patch.object(device, 'usb_appeared', return_value=True),                 mock.patch.object(m.video_collect, 'find_link', return_value=usb) as find:
            self.assertEqual(device.run('x'), 'fast')
        find.assert_called_once()
        self.assertIs(device.link, usb)

    def test_tethering_stays_when_no_usb(self):
        device = m.Device(print)
        device.link = FakeLink('slow')
        with mock.patch.object(device, 'usb_appeared', return_value=False),                 mock.patch.object(m.video_collect, 'find_link') as find:
            self.assertEqual(device.run('x'), 'slow')
        find.assert_not_called()

    def test_a_held_lock_does_not_block_after_abandon(self):
        device = m.Device(print)
        device.lock.acquire()  # 返ってこない前の操作が鍵を持ったまま
        device.abandon()
        device.link = FakeLink('state')
        # PCに実物のadbの機器が見えていても左右されないように（見えているとUSBへつなぎ直しに行く）
        with mock.patch.object(device, 'usb_appeared', return_value=False):
            self.assertEqual(device.run('x'), 'state')

    def test_a_read_that_never_returns_is_abandoned_and_its_late_result_dropped(self):
        menu = object.__new__(m.Menu)
        menu.device, menu.conn = m.Device(print), Conn()
        menu.busy, menu.read_id, menu.read_started = True, 1, time.monotonic() - 10
        started = []
        menu.background = lambda work, done: started.append(done)
        menu.refresh(quiet=True)
        self.assertEqual(started, [])  # まだ待つ
        menu.read_started = time.monotonic() - m.READ_LIMIT_S - 1
        menu.refresh(quiet=True)
        self.assertEqual(len(started), 1)  # 見捨てて読み直した
        self.assertEqual(menu.read_id, 2)
        self.assertIn('返事が', menu.conn.text)
        menu.show_status([], None, read_id=1)  # 古い読み取りが遅れて返っても無視（窓を触らない）
        self.assertTrue(menu.busy)
        self.assertIn('見捨てて読み直す', m.LOG_FILE.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
