"""つなぎ方の共通の部品（unoq_link.py）の試験。実物の adb・ssh は使わず、差し替えて順番と理由の文を確かめる。"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'remote_command'))
sys.path.insert(0, str(HERE.parent / 'sugo_setup'))
sys.path.insert(0, str(HERE.parent / 'video_hud'))

import unoq_link  # noqa: E402


def usb(devices, answers=None, adb='adb'):
    """adb に見える機器と、機器ごとの確かめの返事（文字列か例外）を差し替える"""
    answers = answers or {}

    def run(self, script, timeout=60):
        value = answers.get(getattr(self, 'serial', getattr(self, 'host', None)), '')
        if isinstance(value, Exception):
            raise value
        return value
    return [mock.patch.object(unoq_link, 'find_adb', return_value=adb),
            mock.patch.object(unoq_link, 'usb_devices', return_value=devices),
            mock.patch.object(unoq_link.Link, 'run', run),
            mock.patch.object(unoq_link.shutil, 'which', return_value='ssh')]


class SurveyTest(unittest.TestCase):
    def go(self, patches, **kw):
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return unoq_link.survey(**kw)

    def test_usb_first_and_ssh_not_tried(self):
        link, notes = self.go(usb([('PHONE1', 'device'), ('UNOQ1', 'device')], {'UNOQ1': 'EcoLoggerV2\n', 'unoq': 'EcoLoggerV2\n'}))
        self.assertIsInstance(link, unoq_link.AdbLink)
        self.assertEqual(link.serial, 'UNOQ1')
        self.assertEqual([n.way for n in notes], ['USB'])

    def test_falls_back_to_tethering(self):
        link, notes = self.go(usb([], {'unoq': 'EcoLoggerV2\n'}))
        self.assertIsInstance(link, unoq_link.SshLink)
        self.assertEqual([(n.way, n.ok) for n in notes], [('USB', False), ('テザリング', True)])
        self.assertIn('ドックを外し', notes[0].fix)

    def test_no_adb(self):
        link, notes = self.go(usb(None, {'unoq': OSError('ssh: connect to host timed out')}, adb=None))
        self.assertIsNone(link)
        self.assertIn('adb がPCに入っていません', notes[0].text)
        self.assertIn('同じテザリング', notes[1].fix)

    def test_usb_reasons(self):
        link, notes = self.go(usb([('A', 'unauthorized'), ('B', 'device'), ('C', 'device')],
                                  {'B': 'something else', 'C': subprocess.TimeoutExpired('adb', 20)}), ssh_host=None)
        self.assertIsNone(link)
        self.assertIn('A：PCからの操作を本体が許していません', notes[0].text)
        self.assertIn('B：ロガーではありません', notes[0].text)
        self.assertIn('C：返事がありません', notes[0].text)

    def test_ssh_reasons(self):
        for error, text in ((OSError('本体でのコマンドが失敗（255）: Permission denied (publickey).'), '鍵が合わず'),
                            (OSError('Host key verification failed.'), '鍵と違う機械'),
                            (subprocess.TimeoutExpired('ssh', 20), '返事をしません')):
            with self.subTest(text):
                patches = usb([], {'unoq': error})
                for p in patches:
                    p.start()
                try:
                    link, notes = unoq_link.survey(usb=False)
                finally:
                    for p in patches:
                        p.stop()
                self.assertIsNone(link)
                self.assertIn(text, notes[0].text)

    def test_connect_adb_only_and_message(self):
        for p in usb([], {'unoq': 'EcoLoggerV2\n'}):
            p.start()
            self.addCleanup(p.stop)
        self.assertIsInstance(unoq_link.connect(), unoq_link.SshLink)
        with self.assertRaises(unoq_link.NoLink) as caught:
            unoq_link.connect(use_adb=True)      # --adb はUSBだけ（テザリングへは行かない）
        text = str(caught.exception)
        self.assertIn('USB：USBに機器が見えません', text)
        self.assertNotIn('テザリング：', text)
        self.assertIn('LTE：', text)
        self.assertIsInstance(caught.exception, RuntimeError)   # 道具の except RuntimeError で受けられる


class ArgvTest(unittest.TestCase):
    def test_adb(self):
        link = unoq_link.AdbLink(['adb'], 'S1')
        self.assertEqual(link.argv('ls'), ['adb', '-s', 'S1', 'shell', 'ls'])
        self.assertEqual(link.push_argv('a.txt', '/tmp/a'), ['adb', '-s', 'S1', 'push', 'a.txt', '/tmp/a'])

    def test_ssh_uses_found_target_for_both_ways(self):
        import unoq_ssh
        opts = ['-o', 'HostName=192.0.2.7', '-o', 'HostKeyAlias=uno-q.local']
        with mock.patch.object(unoq_ssh, 'target_opts', return_value=opts):
            link = unoq_link.SshLink('unoq')
            self.assertEqual(link.argv('ls'), ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', *opts, 'unoq', 'ls'])
            self.assertEqual(link.argv('top', tty=True)[:2], ['ssh', '-t'])
            self.assertNotIn('BatchMode=yes', link.argv('top', tty=True))
            for argv in (link.pull_argv('/r', 'l'), link.push_argv('l', '/r')):   # 取る・送るの両方に付く（前は取るほうに無い道具があった）
                self.assertEqual(argv[:4 + len(opts)], ['scp', '-q', '-o', 'BatchMode=yes', *opts])
            self.assertEqual(link.pull_argv('/r', 'l')[-2:], ['unoq:/r', 'l'])
            self.assertEqual(link.push_argv('l', '/r')[-2:], ['l', 'unoq:/r'])


class LteTest(unittest.TestCase):
    def note(self, local, send):
        import remote_command_pc as rc
        with mock.patch.object(rc, 'load_local', return_value=local), mock.patch.object(rc, 'send', side_effect=send):
            return unoq_link.lte_answers()

    def test_cases(self):
        self.assertIn('合言葉がありません', self.note({}, AssertionError('送ってはいけない')).text)
        self.assertIn('返事がありません', self.note({'secret': 'ab' * 32}, lambda *a, **k: None).text)
        self.assertIn('断りました', self.note({'secret': 'ab' * 32}, lambda *a, **k: {'ok': False, 'message': 'bad signature'}).text)
        self.assertTrue(self.note({'secret': 'ab' * 32}, lambda *a, **k: {'ok': True}).ok)
        self.assertIn('送れません', self.note({'secret': 'ab' * 32}, OSError('no route')).text)


class ToolsUseItTest(unittest.TestCase):
    """道具の runner が、共通の部品で見つけたつなぎ方でコマンドを動かす"""

    def setUp(self):
        self.link = mock.Mock()
        self.link.label.return_value = 'USB（S1）'
        self.link.argv.side_effect = lambda command, tty=False: [sys.executable, '-c', 'import sys; print(sys.argv[1])', command]
        patcher = mock.patch.object(unoq_link, 'connect', return_value=self.link)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    def test_sugo_setup(self):
        import sugo_setup
        with mock.patch('builtins.print'):
            run = sugo_setup.runner(False, 'unoq')
        self.assertEqual(run('echo hi').strip(), 'echo hi')
        self.connect.assert_called_once_with(False, 'unoq')

    def test_hud_apply(self):
        import hud_apply
        with mock.patch('builtins.print'):
            run = hud_apply.runner(True, 'unoq')
        self.assertEqual(run('cat x', b'data').strip(), 'cat x')
        self.connect.assert_called_once_with(True, 'unoq')

    def test_no_link_reaches_the_tool_as_runtime_error(self):
        import hud_apply
        self.connect.side_effect = unoq_link.NoLink([unoq_link.Note('USB', False, 'USBに機器が見えません', '挿し直す')])
        with self.assertRaises(RuntimeError):
            hud_apply.runner(False, 'unoq')


if __name__ == '__main__':
    unittest.main()
