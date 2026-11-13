"""「いまの様子」の操作（app_ops.py）の試験。本体・LTEは使わず、差し替えて確かめる。"""
import threading
import time
import unittest
from unittest import mock

import app_ops
import remote_command_pc as rc
import unoq_link

SECRET = {'secret': 'ab' * 32, 'url': 'wss://relay.example/ws/audio/ncec'}
STATUS = {'logging': True, 'log_s': 5, 'hz': 100, 'gnss': True, 'sd': True, 'video': True,
          'lap': {'enabled': True, 'count': 0, 'current': 1, 'running': True, 'race_min': None}}


class FakeApp:
    def __init__(self, link=None):
        self.link, self.job, self.lock = link, None, threading.Lock()
        self.now = {'phase': 'connected' if link else 'waiting', 'op': None, 'key': None, 'lte': None}


def wait(app, seconds=3):
    end = time.time() + seconds
    while app.now['op'] and app.now['op']['running'] and time.time() < end:
        time.sleep(0.01)
    return app.now['op']


class OpsTest(unittest.TestCase):
    def patch(self, *args, **kw):
        patcher = mock.patch.object(*args, **kw)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_lap_reset_goes_direct_when_connected_and_reads_back(self):
        link = unoq_link.AdbLink(['adb'], 'S1')
        calls = []

        def api(link_, path, body=None, wait=15):
            calls.append((path, body))
            return {'values': {'LapCount': 0}, 'line': {'enabled': True}}
        self.patch(app_ops, 'device_api', side_effect=api)
        send = self.patch(rc, 'send')
        app = FakeApp(link)
        app_ops.Ops(app).action('/api/op/lap_reset', {})
        op = wait(app)
        self.assertEqual(calls, [('/api/lap/reset', {}), ('/api/lap', None)])   # 送ったあと読み直す
        self.assertTrue(op['ok'])
        self.assertEqual(op['via'], 'USB')
        self.assertIn('完了 0周', op['lines'][1])
        send.assert_not_called()

    def test_lap_reset_goes_by_lte_when_not_connected(self):
        self.patch(rc, 'load_local', return_value=SECRET)
        send = self.patch(rc, 'send', return_value={'ok': True, 'op': 'lap_reset', 'message': 'done', 'status': STATUS})
        app = FakeApp()
        app_ops.Ops(app).action('/api/op/lap_reset', {})
        op = wait(app)
        self.assertEqual(send.call_args.args[:2], ('lap_reset', None))
        self.assertEqual((op['via'], op['ok']), ('LTE', True))
        self.assertEqual(len(app.now['lte']['checks']), 5)       # 読み直した値を様子にも出す

    def test_lte_no_reply_is_reported_as_unknown(self):
        self.patch(rc, 'load_local', return_value=SECRET)
        self.patch(rc, 'send', return_value=None)
        app = FakeApp()
        app_ops.Ops(app).action('/api/op/lte', {'op': 'status'})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('返事がありませんでした', op['lines'][0])

    def test_refusals_say_why_and_what_to_do(self):
        app = FakeApp()
        ops = app_ops.Ops(app)
        self.patch(rc, 'load_local', return_value={})
        for path, body, text in (('/api/op/lte', {'op': 'status'}, '合言葉の準備'),
                                 ('/api/op/phone_key', {}, '合言葉の準備'),
                                 ('/api/op/setup', {}, '本体をつないでから'),
                                 ('/api/op/lte', {'op': 'lap_count', 'arg': 1000}, '0〜999'),
                                 ('/api/op/lte', {'op': 'reboot'}, '知らない命令')):
            with self.subTest(path=path, body=body):
                with self.assertRaises(app_ops.Refused) as caught:
                    ops.action(path, body)
                self.assertIn(text, str(caught.exception))
                self.assertIsNone(app.now['op'])     # 断ったときは何も始めない
        with self.assertRaises(KeyError):
            ops.action('/api/op/nothing', {})

    def test_one_at_a_time_and_not_during_a_job(self):
        self.patch(rc, 'load_local', return_value=SECRET)
        gate = threading.Event()
        self.patch(rc, 'send', side_effect=lambda *a, **k: gate.wait(3) and None)
        app = FakeApp()
        ops = app_ops.Ops(app)
        ops.action('/api/op/lte', {'op': 'status'})
        with self.assertRaises(app_ops.Refused) as caught:
            ops.action('/api/op/lte', {'op': 'lap_start'})
        self.assertIn('待っている途中', str(caught.exception))
        gate.set()
        wait(app)
        app.job = mock.Mock(running=True)
        with self.assertRaises(app_ops.Refused) as caught:
            ops.action('/api/op/lte', {'op': 'status'})
        self.assertIn('作業の途中', str(caught.exception))

    def test_setup_uses_the_connected_link_and_new_warns(self):
        link = unoq_link.SshLink('unoq')
        seen = {}

        def setup(log=print, new=False):
            import video_collect
            seen['link'], seen['new'] = video_collect.find_link('unoq'), new
            log('合言葉を本体とPCに入れました')
        self.patch(rc, 'setup', side_effect=setup)
        app = FakeApp(link)
        app_ops.Ops(app).action('/api/op/setup', {'new': True})
        op = wait(app)
        self.assertIs(seen['link'], link)
        self.assertTrue(seen['new'])
        self.assertTrue(op['ok'])
        self.assertIn('QRを読み直', op['lines'][-1])

    def test_setup_that_exits_with_a_reason_is_shown(self):
        self.patch(rc, 'setup', side_effect=SystemExit('本体に中継サーバーのURLがありません'))
        app = FakeApp(unoq_link.AdbLink(['adb'], 'S1'))
        app_ops.Ops(app).action('/api/op/setup', {})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('中継サーバーのURL', op['lines'][0])

    def test_phone_key_gives_a_picture_without_the_secret_and_expires(self):
        self.patch(rc, 'load_local', return_value=SECRET)
        app = FakeApp()
        ops = app_ops.Ops(app)
        ops.action('/api/op/phone_key', {})
        key = app.now['key']
        self.assertEqual(len(key['matrix']), len(key['matrix'][0]))
        self.assertTrue(set(''.join(key['matrix'])) <= {'0', '1'})
        self.assertNotIn(SECRET['secret'], repr(key))
        self.assertNotIn('relay.example', repr(key))
        ops.expire()
        self.assertIsNotNone(app.now['key'])
        key['until'] = time.time() - 1
        ops.expire()
        self.assertIsNone(app.now['key'])
        ops.action('/api/op/phone_key', {})
        ops.action('/api/op/hide_key', {})
        self.assertIsNone(app.now['key'])


if __name__ == '__main__':
    unittest.main()
