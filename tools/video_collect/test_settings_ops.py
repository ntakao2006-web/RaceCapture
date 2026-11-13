"""「設定」の段（settings_ops.py）の試験。本体は作りもの（settings_fake.FakeUnoQ）に差し替えて確かめる。"""
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import app_ops
import settings_ops as so
import video_collect as vc
from settings_fake import FakeUnoQ

GOOD_HUD = so.PC_HUD.read_bytes()
LENS = json.dumps({'model': 'opencv_radial_k1k2', 'f_ratio': 0.8, 'size': [1280, 720], 'k1': -0.38, 'k2': 0.08, 'zoom': 1.4,
                   'shift_x': 0.0, 'shift_y': 0.0}).encode()
SH = shutil.which('sh') or next((p for p in (r'C:\Program Files\Git\usr\bin\sh.exe', r'C:\Program Files\Git\bin\sh.exe') if Path(p).exists()), None)


class FakeLink:
    def __init__(self, kind='USB'):
        self.kind = kind


class FakeApp:
    def __init__(self, link=None):
        self.link, self.job, self.lock = link, None, threading.Lock()
        self.now = {'phase': 'connected' if link else 'waiting', 'op': None, 'key': None, 'lte': None}


def wait(app, seconds=5):
    end = time.time() + seconds
    while app.now['op'] and app.now['op']['running'] and time.time() < end:
        time.sleep(0.01)
    return app.now['op']


class Base(unittest.TestCase):
    def patch(self, *args, **kw):
        patcher = mock.patch.object(*args, **kw)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / 'hud.ini').write_bytes(GOOD_HUD)
        (self.tmp / 'lens.json').write_bytes(LENS)
        self.patch(so, 'PC_HUD', self.tmp / 'hud.ini')
        self.patch(so, 'PC_LENS', self.tmp / 'lens.json')
        self.dev = FakeUnoQ()
        self.patch(so, 'make_run', side_effect=lambda link: self.dev.run)
        self.launched = []
        self.patch(so, 'launch', side_effect=lambda path, args: self.launched.append((path.name, args)))

    def start(self, link='USB'):
        self.app = FakeApp(FakeLink(link) if link else None)
        self.ops = app_ops.Ops(self.app)
        self.ops.settings = so.Settings(self.ops, sleep=lambda s: None)
        return self.ops

    def do(self, what, body=None):
        """操作を1つ送って、終わるまで待つ。結果（app.now['op']）を返す"""
        self.ops.action('/api/op/set_' + what, body or {})
        return wait(self.app)

    def refused(self, what, body=None):
        before = list(self.dev.commands)
        with self.assertRaises(app_ops.Refused) as caught:
            self.ops.action('/api/op/set_' + what, body or {})
        self.assertIsNone(self.app.now['op'])   # 断ったときは何も始めない
        self.written(before, 0)
        return str(caught.exception)

    def written(self, before, count):
        """before のあとに、本体を書き換えるコマンドがいくつ出たか"""
        new = self.dev.commands[len(before):]
        self.assertEqual(sum(1 for c in new if 'cat >' in c or c.startswith('rm -f') or 'echo KEPT' in c or 'echo SWAPPED' in c), count, new)

    def view(self):
        return self.app.now['settings']


class ReadTest(Base):
    def test_without_the_logger_it_says_so_and_still_shows_the_pc_files(self):
        self.start(link=None)
        self.ops.action('/api/op/set_read', {})
        v = self.view()
        self.assertIsNone(v['device'])
        self.assertIn('本体がつながっていないので読めません', v['error'])
        self.assertTrue(v['pc']['hud']['ok'])
        self.assertIn('計器', v['pc']['hud']['lines'][0])
        self.assertIn('k1=-0.38', v['pc']['lens']['lines'][0])
        self.assertEqual(self.dev.commands, [])

    def test_reads_every_group_from_the_logger(self):
        self.dev.put('exposure.ini', 'mode = camera\ntarget = 130\n')
        self.dev.put('audio.ini', 'mic_volume = -21dB  # 割れたので下げた\nlimiter = 0\n')
        self.dev.put('smooth_ms', '0\n')
        self.dev.put('audio_off', '')
        self.dev.tick()
        self.start()
        self.ops.action('/api/op/set_read', {})
        d = self.view()['device']
        self.assertTrue(d['recording'])
        self.assertEqual((d['hud']['which'], d['hud']['file']), ('default', False))
        self.assertIn('元の配置', d['hud']['lines'][0])
        self.assertIn('補正せずに描いています', d['lens']['lines'][0])
        self.assertEqual((d['exposure']['mode'], d['exposure']['target']), ('camera', '130'))
        self.assertIn('カメラ任せ', d['exposure']['lines'][0])
        self.assertEqual(d['audio']['values'], {'mic_volume': '-21dB', 'highpass_hz': '100', 'gain_db': '0', 'limiter': '0'})
        self.assertIn('低音カット 100 Hz（既定）', d['audio']['lines'])
        self.assertTrue(any('録らない設定' in ln for ln in d['audio']['lines']))
        self.assertEqual(d['smooth']['values'], {'smooth_ms': '0', 'telemetry_hz': '25'})
        self.assertIn('（補間しない）', d['smooth']['lines'][0])
        self.assertEqual([d[g]['prev'] for g in so.GROUPS], [''] * 5)
        self.written([], 0)                      # 読むだけ

    def test_a_stopped_recorder_is_shown_as_the_last_record(self):
        self.dev.active = False
        self.start()
        self.ops.action('/api/op/set_read', {})
        d = self.view()['device']
        self.assertFalse(d['recording'])
        self.assertTrue(d['hud']['lines'][0].startswith('最後に録画したときの記録：'))

    def test_a_read_that_fails_gives_the_reason(self):
        self.dev.fail = '@@END'
        self.start()
        self.ops.action('/api/op/set_read', {})
        self.assertIsNone(self.view()['device'])
        self.assertIn('本体から読めませんでした', self.view()['error'])

    def test_parse_read_needs_the_end_mark(self):
        files, marks = so.parse_read('@@F smooth_ms 12\n150\n@@F audio.ini 13\na = 1\n\n# x\n\n@@N audio_off 5\n@@END\n')
        self.assertEqual(files, {'smooth_ms': ('150', 12), 'audio.ini': ('a = 1\n\n# x\n', 13)})
        self.assertEqual(marks, {'audio_off': 5})
        with self.assertRaises(ValueError):
            so.parse_read('@@F smooth_ms 12\n150\n')


class HudTest(Base):
    def test_send_keeps_the_old_value_sends_and_reads_back(self):
        self.start()
        op = self.do('hud', {'what': 'send'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual((op['kind'], op['via']), ('settings', 'USB'))
        self.assertEqual(self.dev.text('hud.ini').encode(), GOOD_HUD)
        self.assertTrue(self.dev.has('prev/hud.ini.none'))        # 送る前は自分の配置が無かった、という控え
        text = '\n'.join(op['lines'])
        self.assertIn('控えました', text)
        self.assertIn('反映されました', text)
        self.assertIn('本体から読み直した値', text)
        self.assertIn('自分の配置（hud.ini） で描いています', text)
        d = self.view()['device']['hud']
        self.assertEqual((d['which'], d['same_as_pc']), ('own', True))
        self.assertIn('元の配置でした', d['prev'])
        keep = next(i for i, c in enumerate(self.dev.commands) if 'echo KEPT' in c)
        push = next(i for i, c in enumerate(self.dev.commands) if 'cat >' in c)
        self.assertLess(keep, push)                                # 控えてから送る

    def test_send_the_same_file_changes_nothing(self):
        self.dev.put('hud.ini', GOOD_HUD)
        self.dev.tick()
        self.start()
        before = list(self.dev.commands)
        op = self.do('hud', {'what': 'send'})
        self.assertTrue(op['ok'])
        self.assertIn('もうPCの hud.ini と同じ中身です', '\n'.join(op['lines']))
        self.written(before, 0)

    def test_a_heavy_or_wrong_layout_is_never_sent(self):
        self.start()
        so.PC_HUD.write_text(GOOD_HUD.decode() + ''.join(
            f'[full{i}]\ntype = box\nrect = 0 0 1920 1080\ncolor = 0 0 0 0.06\n\n' for i in range(3)), encoding='utf-8')
        self.assertIn('重すぎます', self.refused('hud', {'what': 'send'}))
        so.PC_HUD.write_text('[a]\ntype = なし\n', encoding='utf-8')
        self.assertIn('誤りがあります', self.refused('hud', {'what': 'send'}))
        so.PC_HUD.unlink()
        self.assertIn('ありません', self.refused('hud', {'what': 'send'}))

    def test_an_old_recorder_gets_nothing_and_no_backup(self):
        self.dev.ready = False
        self.start()
        before = list(self.dev.commands)
        op = self.do('hud', {'what': 'send'})
        self.assertFalse(op['ok'])
        self.assertIn('対応していません', '\n'.join(op['lines']))
        self.written(before, 0)

    def test_nothing_is_sent_when_the_old_value_cannot_be_kept(self):
        self.dev.fail = 'echo KEPT'
        self.start()
        op = self.do('hud', {'what': 'send'})
        self.assertFalse(op['ok'])
        self.assertIn('控えられなかったので、何も変えていません', op['lines'][0])
        self.assertFalse(self.dev.has('hud.ini'))

    def test_a_file_the_recorder_cannot_read_is_reported_with_the_way_back(self):
        self.dev.accepts = False
        self.start()
        op = self.do('hud', {'what': 'send'})
        self.assertFalse(op['ok'])
        text = '\n'.join(op['lines'])
        self.assertIn('本体がこのファイルを読めませんでした', text)
        self.assertIn('「前の値へ戻す」', text)

    def test_default_then_back_and_forth(self):
        self.dev.put('hud.ini', GOOD_HUD)
        self.dev.tick()
        self.start()
        op = self.do('hud', {'what': 'default'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertFalse(self.dev.has('hud.ini'))
        self.assertEqual(self.dev.text('prev/hud.ini').encode(), GOOD_HUD)
        self.assertEqual(self.view()['device']['hud']['which'], 'default')
        self.assertIn('の自分の配置', self.view()['device']['hud']['prev'])
        op = self.do('restore', {'group': 'hud'})                 # 前の値（自分の配置）へ戻す
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('hud.ini').encode(), GOOD_HUD)
        self.assertIn('戻した配置で描いています', '\n'.join(op['lines']))
        self.assertEqual(self.view()['device']['hud']['which'], 'own')
        self.assertTrue(self.dev.has('prev/hud.ini.none'))        # 戻す前（元の配置）が、代わりに控えになる
        op = self.do('restore', {'group': 'hud'})                 # もう一度で、戻す前に戻る
        self.assertTrue(op['ok'], op['lines'])
        self.assertFalse(self.dev.has('hud.ini'))
        self.assertIn('元の配置で描いています', '\n'.join(op['lines']))

    def test_default_when_already_default_changes_nothing(self):
        self.start()
        before = list(self.dev.commands)
        op = self.do('hud', {'what': 'default'})
        self.assertTrue(op['ok'])
        self.assertIn('もう元の配置です', op['lines'][0])
        self.written(before, 0)


class LensExposureTest(Base):
    def test_lens_send_off_and_restore(self):
        self.start()
        op = self.do('lens', {'what': 'send'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('lens.json').encode(), LENS)
        self.assertIn('補正して描いています', '\n'.join(op['lines']))
        d = self.view()['device']['lens']
        self.assertTrue(d['same_as_pc'])
        self.assertIn('補正なしでした', d['prev'])
        before = list(self.dev.commands)
        self.assertIn('同じ中身', '\n'.join(self.do('lens', {'what': 'send'})['lines']))   # 同じなら送らない
        self.written(before, 0)
        op = self.do('lens', {'what': 'off'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertFalse(self.dev.has('lens.json'))
        self.assertIn('k1=-0.38', self.view()['device']['lens']['prev'])
        op = self.do('restore', {'group': 'lens'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('lens.json').encode(), LENS)
        self.assertIn('戻した値で補正して描いています', '\n'.join(op['lines']))

    def test_lens_file_problems_are_refused_with_the_way_out(self):
        self.start()
        so.PC_LENS.write_text(json.dumps({**json.loads(LENS), 'zoom': 9}))
        self.assertIn('zoom', self.refused('lens', {'what': 'send'}))
        so.PC_LENS.unlink()
        self.assertIn('値を決めてから', self.refused('lens', {'what': 'send'}))

    def test_exposure_choices_and_restore(self):
        self.start()
        op = self.do('exposure', {'what': 'camera'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('exposure.ini'), 'mode = camera\n')
        self.assertEqual(self.view()['device']['exposure']['mode'], 'camera')
        self.assertIn('既定', self.view()['device']['exposure']['prev'])
        before = list(self.dev.commands)
        self.assertIn('もうその決め方です', '\n'.join(self.do('exposure', {'what': 'camera'})['lines']))
        self.written(before, 0)
        op = self.do('exposure', {'what': 'brighter'})            # 目標は own のときだけ効くので、一緒に own になる
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('exposure.ini'), 'mode = own\ntarget = 130\n')
        self.assertIn('目標の明るさ 130', '\n'.join(op['lines']))
        self.assertIn('カメラ任せ', self.view()['device']['exposure']['prev'])
        op = self.do('restore', {'group': 'exposure'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('exposure.ini'), 'mode = camera\n')
        self.assertEqual(self.view()['device']['exposure']['mode'], 'camera')
        with self.assertRaises(KeyError):
            self.ops.action('/api/op/set_exposure', {'what': 'auto'})

    def test_exposure_stops_at_the_end_of_the_range(self):
        self.dev.put('exposure.ini', 'mode = own\ntarget = 200\n')
        self.dev.tick()
        self.start()
        before = list(self.dev.commands)
        op = self.do('exposure', {'what': 'brighter'})
        self.assertIn('上の端', op['lines'][0])
        self.written(before, 0)


class AudioSmoothTest(Base):
    def test_audio_rewrites_only_the_named_items_and_says_when_it_takes_effect(self):
        self.dev.put('audio.ini', '# 11/7 の走行で割れた\nmic_volume = -15dB\nmic_agc = off\n')
        self.start()
        op = self.do('audio', {'values': {'mic_volume': '-21', 'highpass_hz': '120', 'gain_db': '', 'limiter': '1'}})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('audio.ini'), '# 11/7 の走行で割れた\nmic_volume = -21dB\nmic_agc = off\nhighpass_hz = 120\nlimiter = 1\n')
        text = '\n'.join(op['lines'])
        self.assertIn('次に録画が始まったとき', text)
        self.assertIn('マイクの音量 -21dB', text)
        self.assertIn('マイクの音量 -15dB', self.view()['device']['audio']['prev'])
        op = self.do('restore', {'group': 'audio'})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual(self.dev.text('audio.ini'), '# 11/7 の走行で割れた\nmic_volume = -15dB\nmic_agc = off\n')
        self.assertIn('次に録画が始まったとき', '\n'.join(op['lines']))

    def test_audio_first_write_can_be_undone_to_no_file(self):
        self.start()
        self.assertTrue(self.do('audio', {'values': {'limiter': '0'}})['ok'])
        self.assertEqual(self.dev.text('audio.ini'), 'limiter = 0\n')
        self.assertTrue(self.do('restore', {'group': 'audio'})['ok'])
        self.assertFalse(self.dev.has('audio.ini'))
        self.assertEqual(self.dev.text('prev/audio.ini'), 'limiter = 0\n')

    def test_audio_values_out_of_range_are_refused(self):
        self.start()
        for values, text in (({'mic_volume': '30%'}, 'dBの数字'), ({'mic_volume': '5'}, '-95〜0'), ({'mic_volume': '-120dB'}, '-95〜0'),
                             ({'highpass_hz': '-1'}, '0〜1000'), ({'highpass_hz': 'abc'}, '0〜1000'), ({'gain_db': '50'}, '-40〜20'),
                             ({'limiter': '2'}, 'リミッター'), ({}, '変える値がありません'), (None, '変える値がありません')):
            with self.subTest(values=values):
                self.assertIn(text, self.refused('audio', {'values': values}))
        self.assertEqual(so.clean_audio({'mic_volume': ' -12.5 dB ', 'gain_db': 3}), {'mic_volume': '-12.5dB', 'gain_db': '3'})

    def test_a_stopped_recorder_shows_what_the_file_says(self):
        self.dev.active = False
        self.start()
        op = self.do('exposure', {'what': 'camera'})
        self.assertTrue(op['ok'], op['lines'])
        text = chr(10).join(op['lines'])
        self.assertIn('次に録画が始まったときから、この設定で録ります', text)
        self.assertIn('設定のファイル（exposure.ini）：カメラ任せ', text)
        self.assertEqual(self.view()['device']['exposure']['mode'], 'camera')

    def test_files_saved_on_windows_compare_equal(self):
        self.assertTrue(so.same_text('{' + chr(10) + ' "a": 1' + chr(10) + '}', b'{' + bytes([13, 13, 10]) + b' "a": 1' + bytes([13, 10]) + b'}' + bytes([10])))
        self.assertFalse(so.same_text('a', b'b'))

    def test_smooth_writes_only_what_changed_and_restores_both(self):
        self.dev.put('telemetry_hz', '25\n')
        self.start()
        before = list(self.dev.commands)
        op = self.do('smooth', {'values': {'smooth_ms': '200', 'telemetry_hz': '25'}})
        self.assertTrue(op['ok'], op['lines'])
        self.assertEqual((self.dev.text('smooth_ms'), self.dev.text('telemetry_hz')), ('200\n', '25\n'))
        self.written(before, 2)                                    # 控え1回＋変わった1つだけ書く
        self.assertIn('次に録画が始まったとき', '\n'.join(op['lines']))
        self.assertEqual(self.view()['device']['smooth']['values'], {'smooth_ms': '200', 'telemetry_hz': '25'})
        self.assertIn('150（既定）', self.view()['device']['smooth']['prev'])
        before = list(self.dev.commands)
        self.assertIn('もうその値です', self.do('smooth', {'values': {'smooth_ms': '200'}})['lines'][0])
        self.written(before, 0)
        self.assertTrue(self.do('restore', {'group': 'smooth'})['ok'])
        self.assertFalse(self.dev.has('smooth_ms'))               # 前は無かった（既定）ので、ファイルごと無くなる
        self.assertEqual(self.dev.text('telemetry_hz'), '25\n')

    def test_smooth_values_out_of_range_are_refused(self):
        self.start()
        for values, text in (({'smooth_ms': '500'}, '0〜300'), ({'smooth_ms': '-1'}, '0〜300'), ({'telemetry_hz': '0'}, '1〜100'),
                             ({'telemetry_hz': '200'}, '1〜100'), ({'smooth_ms': 'x'}, '0〜300'), ({}, '変える値がありません')):
            with self.subTest(values=values):
                self.assertIn(text, self.refused('smooth', {'values': values}))


class RulesTest(Base):
    def test_without_the_logger_every_change_says_why_and_what_to_do(self):
        self.start(link=None)
        for what, body in (('hud', {'what': 'send'}), ('hud', {'what': 'default'}), ('lens', {'what': 'send'}), ('lens', {'what': 'off'}),
                           ('exposure', {'what': 'own'}), ('audio', {'values': {'limiter': '1'}}), ('smooth', {'values': {'smooth_ms': '100'}}),
                           ('restore', {'group': 'hud'}), ('open', {'tool': 'lens_preview'})):
            with self.subTest(what=what, body=body):
                text = self.refused(what, body)
                self.assertIn('本体がつながっていないので', text)
                self.assertIn('USBかテザリングでつないで', text)

    def test_restore_without_a_backup_says_so_when_pressed(self):
        self.start()
        for group in so.GROUPS:
            with self.subTest(group=group):
                self.assertIn('まだ控えがありません', self.refused('restore', {'group': group}))
        with self.assertRaises(KeyError):
            self.ops.action('/api/op/set_restore', {'group': 'everything'})

    def test_one_at_a_time_and_no_read_in_the_middle(self):
        self.start()
        gate = threading.Event()
        run = self.dev.run
        self.dev.run = lambda command, data=None: (gate.wait(3), run(command, data))[1]
        self.ops.action('/api/op/set_exposure', {'what': 'camera'})
        for what, body in (('lens', {'what': 'send'}), ('restore', {'group': 'hud'}), ('read', {})):
            with self.assertRaises(app_ops.Refused) as caught:
                self.ops.action('/api/op/set_' + what, body)
            self.assertIn('途中です', str(caught.exception))
        gate.set()
        self.assertTrue(wait(self.app)['ok'])

    def test_tools_open_in_a_new_window_or_say_what_is_missing(self):
        self.patch(so.os, 'name', 'nt')
        self.start()
        self.patch(so, 'missing_parts', side_effect=lambda parts: [p for p in parts if p == 'cv2'])
        self.assertIn('別の窓で開きました', self.ops.action('/api/op/set_open', {'tool': 'hud_preview'})['opened'])
        text = self.refused('open', {'tool': 'lens_view'})
        self.assertIn('opencv-python', text)
        self.assertIn('pip install', text)
        self.ops.action('/api/op/set_open', {'tool': 'lens_preview'})
        self.assertEqual(self.launched, [('Preview-HUD.cmd', []), ('Lens-Preview.cmd', ['--adb'])])   # USBのときは --adb
        self.app.link.kind = 'テザリング'
        self.ops.action('/api/op/set_open', {'tool': 'lens_preview'})
        self.assertEqual(self.launched[-1], ('Lens-Preview.cmd', []))
        with self.assertRaises(KeyError):
            self.ops.action('/api/op/set_open', {'tool': 'cmd'})
        self.assertEqual([(p.name, p.exists()) for _, p, _, _ in so.TOOLS.values()],
                         [('Preview-HUD.cmd', True), ('Lens-View.cmd', True), ('Lens-Preview.cmd', True)])

    def test_the_app_itself_does_not_load_pillow_or_opencv(self):
        code = ('import sys; sys.path.insert(0, r"%s"); import video_collect, app_ops, settings_ops; settings_ops.tools(); settings_ops.pc_view(); '
                'print([m for m in ("PIL", "cv2", "numpy") if m in sys.modules])' % Path(so.__file__).parent)
        out = subprocess.run([so.sys.executable, '-c', code], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.stdout.strip(), '[]', out.stderr)

    def test_http_gives_the_page_script_and_the_read_values(self):
        self.start()
        with tempfile.TemporaryDirectory() as tmp:
            app = vc.App(vc.PcStore(Path(tmp) / 'v2_video'), None, link=self.app.link)
            app.now = self.app.now
            app.ops = app_ops.Ops(app)
            app.ops.settings = so.Settings(app.ops, sleep=lambda s: None)
            server = vc.make_server(app, 0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f'http://127.0.0.1:{server.server_port}'

            def post(path, body):
                req = urllib.request.Request(url + path, json.dumps(body).encode(), {'X-Video-Collect': '1'})
                return json.loads(urllib.request.urlopen(req).read())
            try:
                self.assertIn('renderSettings', urllib.request.urlopen(url + '/settings.js').read().decode())
                page = urllib.request.urlopen(url + '/').read().decode()
                self.assertIn('id="tab-settings"', page)
                self.assertIn('src="/settings.js"', page)
                self.assertTrue(post('/api/op/set_read', {})['ok'])
                state = json.loads(urllib.request.urlopen(url + '/api/state').read())
                self.assertEqual(state['now']['settings']['device']['hud']['which'], 'default')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    post('/api/op/set_restore', {'group': 'lens'})
                self.assertEqual(caught.exception.code, 409)
                self.assertIn('まだ控えがありません', json.loads(caught.exception.read())['error'])
                caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()


@unittest.skipUnless(SH, 'sh が無いPCでは、本体で動かすコマンドの書き方を確かめられない')
class ShellTest(unittest.TestCase):
    """settings_ops が組み立てるコマンドを、本物の sh で動かす（置き場だけ一時フォルダーへ読み替える）"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / 'ecologger-video'

    def sh(self, command, data=None):
        done = subprocess.run([SH, '-c', command.replace(so.REMOTE, self.root.as_posix())], input=data, capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace'))
        return done.stdout.decode('utf-8').replace('\r\n', '\n')

    def test_read_before_anything_exists(self):
        self.assertEqual(so.parse_read(self.sh(so.read_command())), ({}, {}))
        self.assertIn('NOPREV', self.sh(so.have_command(('hud.ini',))))
        self.assertIn('NOPREV', self.sh(so.swap_command(('hud.ini',))))

    def test_write_keep_swap_and_read(self):
        self.assertIn('ok', self.sh(so.write_command('smooth_ms'), b'200\n'))
        self.assertIn('ok', self.sh(so.write_command('audio.ini'), 'mic_volume = -21dB  # 下げた\n\nlimiter = 0\n'.encode()))
        (self.root / 'audio_off').write_bytes(b'')
        files, marks = so.parse_read(self.sh(so.read_command()))
        self.assertEqual({k: v[0] for k, v in files.items()}, {'smooth_ms': '200\n', 'audio.ini': 'mic_volume = -21dB  # 下げた\n\nlimiter = 0\n'})
        self.assertEqual(list(marks), ['audio_off'])
        self.assertFalse(list(self.root.glob('*.tmp')))

        self.assertIn('KEPT', self.sh(so.keep_command(so.GROUPS['smooth'])))     # 200 と「無かった」を控える
        self.assertIn('HAVE', self.sh(so.have_command(so.GROUPS['smooth'])))
        self.sh(so.write_command('smooth_ms'), b'0\n')
        self.sh(so.write_command('telemetry_hz'), b'10\n')
        files, marks = so.parse_read(self.sh(so.read_command()))
        self.assertEqual((files['prev/smooth_ms'][0], 'prev/telemetry_hz.none' in marks), ('200\n', True))

        out = self.sh(so.swap_command(so.GROUPS['smooth']))                    # 戻す：200 と「無し」
        self.assertIn('SWAPPED', out)
        lines = [ln.split() for ln in out.splitlines() if ln.startswith('@@S')]
        self.assertEqual((lines[0][:2], len(lines[0]), lines[1]), (['@@S', 'smooth_ms'], 4, ['@@S', 'telemetry_hz', '-']))
        self.assertEqual(lines[0][3], '4')                                       # 「200」と改行で4バイト
        self.assertEqual((self.root / 'smooth_ms').read_bytes(), b'200\n')
        self.assertFalse((self.root / 'telemetry_hz').exists())
        self.assertEqual(((self.root / 'prev' / 'smooth_ms').read_bytes(), (self.root / 'prev' / 'telemetry_hz').read_bytes()), (b'0\n', b'10\n'))
        self.assertEqual(sorted(p.name for p in (self.root / 'prev').iterdir()), ['smooth_ms', 'telemetry_hz'])

        self.assertIn('SWAPPED', self.sh(so.swap_command(so.GROUPS['smooth'])))  # もう一度で、戻す前に戻る
        self.assertEqual(((self.root / 'smooth_ms').read_bytes(), (self.root / 'telemetry_hz').read_bytes()), (b'0\n', b'10\n'))
        self.assertEqual(sorted(p.name for p in (self.root / 'prev').iterdir()), ['smooth_ms', 'telemetry_hz.none'])

    def test_keep_replaces_the_older_backup(self):
        self.sh(so.write_command('lens.json'), b'{"a": 1}')
        self.sh(so.keep_command(('lens.json',)))
        self.sh('rm -f ' + so.REMOTE + '/lens.json')
        self.sh(so.keep_command(('lens.json',)))
        self.assertEqual([p.name for p in (self.root / 'prev').iterdir()], ['lens.json.none'])
        self.sh(so.write_command('lens.json'), b'{"a": 2}')
        self.sh(so.keep_command(('lens.json',)))
        self.assertEqual([p.name for p in (self.root / 'prev').iterdir()], ['lens.json'])
        self.assertEqual(so.parse_read(self.sh(so.read_command()))[0]['prev/lens.json'][0], '{"a": 2}')


if __name__ == '__main__':
    unittest.main()
