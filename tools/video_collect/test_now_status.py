"""「いまの様子」（now_status.py）の試験。本体は使わず、状態のJSONと作りもののつなぎで確かめる。"""
import json
import subprocess
import threading
import unittest
from unittest import mock

import now_status as ns

GOOD = {
    'connected': True, 'receive_hz': 99.8, 'storage_free_bytes': 20 * 2**30,
    'logging': {'active': True, 'elapsed_s': 754, 'name': 'LOG_20261113_101500', 'error': None, 'sd_warning': None},
    'sensors': {'gnss': '測位中', 'imu': '正常', 'can': '受信中', 'sd': '記録中', 'camera': '接続'},
    'video': {'recording': True, 'minutes_left': 412, 'uncollected': 3, 'uncollected_bytes': 5 * 2**30},
    'podium': {'enabled': True, 'state': 'streaming', 'message': '送信中', 'radio': {'rsrp': -97}},
}
LAP = {'values': {'LapCount': 12}, 'line': {'enabled': True}}


def states(found):
    return {c['name']: c['state'] for c in found}


def changed(**parts):
    status = json.loads(json.dumps(GOOD))
    for key, value in parts.items():
        status[key] = {**status[key], **value} if isinstance(value, dict) else value
    return status


class ChecksTest(unittest.TestCase):
    def test_all_good(self):
        found, extra = ns.checks(GOOD, LAP)
        self.assertEqual(states(found), dict.fromkeys(['記録', '測位', 'SDカード', '録画', 'LTE'], 'ok'))
        self.assertTrue(all(c['fix'] == '' for c in found))   # 良いときは直し方を出さない
        self.assertIn('12分34秒', found[0]['text'])
        self.assertIn('RSRP -97', found[4]['text'])
        self.assertEqual(extra[0], ('ラップ', '完了 12周（線はあり）'))

    def test_each_bad(self):
        cases = [
            ('記録', changed(logging={'active': False, 'error': 'disk full'}), 'disk full'),
            ('記録', changed(connected=False), '基板から値が届いていません'),
            ('記録', changed(receive_hz=42), '値が少ない'),
            ('測位', changed(sensors={'gnss': '測位待ち'}), '測位待ち'),
            ('SDカード', changed(logging={'sd_warning': 'SDカードに記録していません'}), 'SDカードに記録していません'),
            ('録画', changed(video={'recording': False}), '録画していません'),
            ('録画', changed(video={'minutes_left': 12}), 'あと約12分'),
            ('LTE', changed(podium={'enabled': False}), '送信がOFF'),
            ('LTE', changed(podium={'state': 'reconnecting', 'message': 'つなぎ直しています'}), 'つなぎ直しています'),
        ]
        for name, status, text in cases:
            with self.subTest(text):
                found, _ = ns.checks(status, LAP)
                bad = [c for c in found if c['state'] == 'bad']
                self.assertEqual([c['name'] for c in bad], [name])
                self.assertIn(text, bad[0]['text'])
                self.assertTrue(bad[0]['fix'])   # 直す所には必ず直し方が付く

    def test_no_answer_is_unknown_not_good(self):
        found, extra = ns.checks(None)
        self.assertEqual(set(states(found).values()), {'unknown'})
        self.assertEqual(extra, [])

    def test_lte(self):
        found, extra = ns.checks_lte({'logging': True, 'log_s': 90, 'hz': 99.9, 'gnss': True, 'sd': False, 'video': True,
                                      'lap': {'enabled': True, 'count': 3, 'current': 4}})
        self.assertEqual(states(found), {'記録': 'ok', '測位': 'ok', 'SDカード': 'bad', '録画': 'ok', 'LTE': 'ok'})
        self.assertIn('完了 3周', extra[0][1])

    def test_read_parses_and_hints_usb(self):
        import unoq_link
        out = f"@@S\n{json.dumps(GOOD)}\n@@L\n{json.dumps(LAP)}\n@@C\n0\n"
        link = unoq_link.SshLink('unoq')
        with mock.patch.object(unoq_link.SshLink, 'run', return_value=out):
            result = ns.read(link)
        self.assertEqual(len(result['checks']), 5)
        self.assertIn('ドックを外し', result['usb_hint'])
        usb = unoq_link.AdbLink(['adb'], 'S1')
        with mock.patch.object(unoq_link.AdbLink, 'run', return_value=out):
            self.assertEqual(ns.read(usb)['usb_hint'], '')


class FakeApp:
    def __init__(self):
        self.link, self.state, self.error, self.job, self.now, self.ssh_host = None, None, '', None, None, 'unoq'
        self.lock, self.refreshed = threading.Lock(), 0

    def refresh(self):
        self.refreshed += 1


class WatcherTest(unittest.TestCase):
    def setUp(self):
        import unoq_link
        self.unoq_link = unoq_link
        self.app = FakeApp()
        self.found = None
        self.notes = [unoq_link.Note('USB', False, 'USBに機器が見えません', '挿し直す')]
        self.reader = mock.Mock(return_value={'checks': ns.checks(GOOD, LAP)[0], 'extra': [], 'usb_hint': ''})
        self.watcher = ns.Watcher(self.app, survey=lambda: (self.found, self.notes), reader=self.reader)
        patcher = mock.patch.object(unoq_link, 'usb_ready', return_value=False)
        self.usb_ready = patcher.start()
        self.addCleanup(patcher.stop)

    def test_waits_then_switches_by_itself(self):
        self.assertEqual(self.app.now['phase'], 'searching')
        self.watcher.step()
        self.assertEqual(self.app.now['phase'], 'waiting')
        self.assertEqual(self.app.now['notes'][0]['text'], 'USBに機器が見えません')
        self.reader.assert_not_called()
        self.found = self.unoq_link.AdbLink(['adb'], 'S1')       # つないだ
        self.assertEqual(self.watcher.step(), ns.READ_EVERY_S)
        self.assertEqual((self.app.now['phase'], self.app.now['via']), ('connected', 'USB'))
        self.assertEqual(self.app.refreshed, 1)                   # 回収の段の一覧も読む
        self.assertGreater(self.app.now['read_at'], 0)

    def test_lost_link_goes_back_to_searching(self):
        self.app.link = self.found = self.unoq_link.AdbLink(['adb'], 'S1')
        self.watcher.step()
        self.reader.side_effect = subprocess.TimeoutExpired('adb', 30)   # 抜いた
        self.found = None
        self.watcher.step()
        self.assertIsNone(self.app.link)
        self.assertEqual(self.app.now['phase'], 'searching')
        self.watcher.step()
        self.assertEqual(self.app.now['phase'], 'waiting')

    def test_does_not_read_during_a_job(self):
        self.app.link = self.unoq_link.AdbLink(['adb'], 'S1')
        self.app.job = mock.Mock(running=True)
        self.watcher.step()
        self.reader.assert_not_called()
        self.assertTrue(self.app.now['paused'])

    def test_switches_to_usb_when_it_appears(self):
        self.app.link = self.unoq_link.SshLink('unoq')
        self.usb_ready.return_value = True
        self.found = self.unoq_link.AdbLink(['adb'], 'S1')
        self.watcher.step()
        self.assertIs(self.app.link, self.found)

    def test_ask_lte(self):
        import remote_command_pc as rc
        with mock.patch.object(rc, 'load_local', return_value={}):
            self.watcher.ask_lte()
        self.assertIn('合言葉がありません', self.app.now['lte']['error'])
        with mock.patch.object(rc, 'load_local', return_value={'secret': 'ab' * 32}), mock.patch.object(rc, 'send', return_value=None):
            self.watcher.ask_lte()
        self.assertIn('返事がありません', self.app.now['lte']['error'])
        answer = {'ok': True, 'status': {'logging': True, 'log_s': 5, 'hz': 100, 'gnss': True, 'sd': True, 'video': True, 'lap': {}}}
        with mock.patch.object(rc, 'load_local', return_value={'secret': 'ab' * 32}), mock.patch.object(rc, 'send', return_value=answer):
            self.watcher.ask_lte()
        self.assertEqual(len(self.app.now['lte']['checks']), 5)


if __name__ == '__main__':
    unittest.main()
