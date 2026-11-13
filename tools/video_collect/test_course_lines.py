"""「コースと線」の段（course_lines.py と app_ops.py の線の操作）の試験。本体・LTEは使わず、差し替えて確かめる。"""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import app_ops
import course_lines as cl
import now_status
import remote_command_pc as rc
import setups
import video_collect as vc

SECRET = {'secret': 'ab' * 32, 'url': 'wss://relay.example/ws/audio/ncec'}
SUGO = setups.load('course', 'sugo')
STATUS = {'logging': True, 'log_s': 5, 'hz': 100, 'gnss': True, 'sd': True, 'video': True,
          'lap': {'enabled': True, 'count': 3, 'current': 4, 'running': True, 'race_min': None}}


def sugo(**change):
    """SUGOの線（コースの設定のもの）を clean した形で。change で一部を変える"""
    return cl.clean({**json.loads(json.dumps(SUGO['line'])), **change})


def north(line, metres):
    return {**line, 'lat': line['lat'] + metres / cl.M_PER_DEG}


def telemetry(kmh=0.0, fix=True):
    values = {'Speed': kmh, 'GPSSpeed': kmh, 'GPSFix': 3, 'Lat': 38.14, 'Lon': 140.77, 'Yaw': 97.0} if fix else {'Speed': None, 'GPSFix': 0}
    return {'sample': {'values': values, 'gnss_hacc_m': 0.9 if fix else None}}


class FakeLink:
    """つないだ本体の代わり。run は本体で動かしたスクリプトを覚える"""
    kind, root = 'USB', '/data'

    def __init__(self):
        self.scripts, self.fail = [], False

    def run(self, script, timeout=60):
        self.scripts.append(script)
        if self.fail:
            raise OSError('本体でのコマンドが失敗')
        return 'KEPT\n'


class FakeDevice:
    """本体の /api/lap・/api/telemetry の代わり（本体と同じく、送られた分をいまの線に重ねる）"""
    def __init__(self, line=None, kmh=0.0, fix=True, running=False, keep=False):
        self.line = {**(line or sugo()), 'set_at': '2026-11-13T10:00+09:00'}
        self.kmh, self.fix, self.running, self.keep, self.calls = kmh, fix, running, keep, []
        self.extra = {}     # 本体のソフトが新しいときに付く印など

    def api(self, link, path, body=None, wait=15):
        self.calls.append((path, body))
        if path == '/api/telemetry':
            return telemetry(self.kmh, self.fix)
        if path == '/api/lap' and body is not None and not self.keep:
            self.line = {**self.line, **body}
        return {'line': self.line, 'values': {'LapCount': 3}, 'running': self.running, **self.extra}

    def posts(self):
        return [body for path, body in self.calls if body is not None]


class FakeApp:
    def __init__(self, link=None):
        self.link, self.job, self.lock = link, None, threading.Lock()
        self.now = {'phase': 'connected' if link else 'waiting', 'via': 'USB' if link else '', 'op': None, 'key': None, 'lte': None, 'course': None}


def wait(app, seconds=3):
    end = time.time() + seconds
    while app.now['op'] and app.now['op']['running'] and time.time() < end:
        time.sleep(0.01)
    return app.now['op']


class LinesTest(unittest.TestCase):
    def test_clean_keeps_only_the_line_and_sends_it_whole(self):
        line = cl.clean({'lat': 38.0, 'lon': 140.0, 'bearing': 90, 'width_m': 30, 'set_at': 'x', 'junk': 1, 'enabled': False,
                         'sectors': [{'lat': 38.1, 'lon': 140.1, 'bearing': 10, 'width_m': 20, 'junk': 2}]})
        self.assertEqual(line, {'enabled': True, 'lat': 38.0, 'lon': 140.0, 'bearing': 90, 'width_m': 30, 'start': None, 'goal': None,
                                'sectors': [{'lat': 38.1, 'lon': 140.1, 'bearing': 10, 'width_m': 20}]})
        self.assertEqual(cl.problems(line), [])
        self.assertEqual(cl.problems(sugo()), [])
        self.assertIn('min_lap_s', sugo())            # PCの設定から始めた線は、線のほかの値も一緒に送る
        with self.assertRaises(ValueError):
            cl.clean([1, 2])

    def test_problems_say_which_line_and_what(self):
        gate = {'lat': 38.1, 'lon': 140.1, 'bearing': 10, 'width_m': 20}
        cases = [({'lat': None, 'lon': None}, 'コントロールライン（周を数える線）がありません'),
                 ({'width_m': 4}, 'コントロールライン：幅が 5〜200 m の外'),
                 ({'width_m': 201}, 'コントロールライン：幅が 5〜200 m の外'),
                 ({'bearing': 360}, 'コントロールライン：進む向きが 0〜359.5° の外'),
                 ({'lat': 91}, 'コントロールライン：場所'),
                 ({'start': {**gate, 'width_m': 500}}, 'スタートの線：幅'),
                 ({'goal': {**gate, 'lon': 181}}, 'ゴールの線：場所'),
                 ({'sectors': [gate, {**gate, 'bearing': None}]}, 'セクター2の終わりの線：進む向きが要ります'),
                 ({'sectors': [gate] * 10}, 'セクターの線が10本'),
                 ({'min_lap_s': 100, 'max_lap_s': 50}, '1周の最長が、最短より長くなっていません')]
        for change, text in cases:
            with self.subTest(text):
                found = cl.problems(sugo(**change))
                self.assertTrue(any(text in p for p in found), found)
        self.assertEqual(cl.problems(sugo(bearing=None)), [])   # コントロールラインの向きは、通ったときに本体が覚えられる

    def test_changes_tell_how_far_and_what(self):
        now = sugo()
        self.assertEqual(cl.changes(now, sugo()), ([], False))
        self.assertEqual(cl.changes({**now, 'set_at': 'x', 'pit_offset_m': 3.0}, {k: v for k, v in now.items() if k not in cl.RACE_KEYS}),
                         ([], False))                     # 送らない「線のほかの値」は比べない
        found, sector = cl.changes(now, north(sugo(width_m=40.0, bearing=100.0), 1.0))
        self.assertEqual(found, ['線 4本 → 4本', 'コントロールライン：北へ 1.00 m 動かす・幅 50 → 40 m・向き 97.5° → 100°'])
        self.assertFalse(sector)
        gate = {'lat': 38.14, 'lon': 140.77, 'bearing': 10.0, 'width_m': 20.0}
        found, sector = cl.changes(now, sugo(sectors=now['sectors'][:2], start=gate, min_lap_s=30.0))
        self.assertEqual(found[0], '線 4本 → 4本')
        self.assertIn('足す：スタート（38.1400000, 140.7700000・幅 20 m・向き 10°）', found)
        self.assertIn('消す：セクター3の終わり', found)
        self.assertIn('1周の最短（秒）：60 → 30', found)
        self.assertTrue(sector)
        self.assertTrue(cl.lines_moved(now, north(now, 0.5)))
        self.assertFalse(cl.lines_moved(now, sugo(min_lap_s=30.0)))
        found, _ = cl.changes({'enabled': False, 'lat': None, 'lon': None}, now)   # 線の無い本体へ入れる
        self.assertEqual(found[0], '線 0本 → 4本')
        self.assertTrue(found[1].startswith('足す：コントロールライン'))

    def test_match_names_the_course_or_none(self):
        self.assertEqual(cl.match({**SUGO['line'], 'set_at': '2026-11-07T09:00+09:00'}), 'sugo')
        self.assertIsNone(cl.match(north(dict(SUGO['line']), 1.0)))
        self.assertIsNone(cl.match(None))
        self.assertEqual(cl.racing_kmh(None, 'sugo')[0], 100)
        self.assertEqual(cl.racing_kmh(None, 'nowhere')[0], cl.DEFAULT_RACING_KMH)

    def test_speed_and_position_from_telemetry(self):
        self.assertEqual(cl.speed({'sample': {'values': {'Speed': 80.0, 'GPSSpeed': 83.5}}}), 83.5)
        self.assertEqual(cl.speed({'sample': {'values': {'Speed': None, 'GPSSpeed': 12.0}}}), 12.0)
        for unknown in (None, {}, {'sample': None}, {'sample': {'values': {'Speed': None}}}, {'sample': {'values': {'Speed': 'x'}}}):
            self.assertIsNone(cl.speed(unknown))
        self.assertIsNone(cl.position(telemetry(fix=False)))
        self.assertEqual(cl.position(telemetry(40.0)), {'lat': 38.14, 'lon': 140.77, 'yaw': 97.0, 'speed_kmh': 40.0, 'hacc_m': 0.9})

    def test_vehicle_is_compared_by_its_signals(self):
        logger = setups.load('vehicle', 'ncec')['logger']
        same = cl.vehicle_view(logger)
        self.assertEqual((same['id'], same['same'], same['count']), ('ncec', True, 0))
        other = cl.vehicle_view({**logger, 'signals': logger['signals'][:-1]})
        self.assertFalse(other['same'])
        self.assertTrue(other['diffs'])
        self.assertIsNone(cl.vehicle_view(None))

    def test_view_says_whether_the_line_is_live(self):
        app = FakeApp(FakeLink())
        app.now['course'] = cl.device_view({'line': {**SUGO['line'], 'set_at': None}, 'values': {'LapCount': 2}, 'running': True}, telemetry(30.0))
        seen = cl.view(app)
        self.assertEqual((seen['connected'], seen['device']['live'], seen['device']['match'], seen['device']['speed_kmh']), (True, True, 'sugo', 30.0))
        self.assertEqual([c['id'] for c in seen['courses']], setups.names('course'))
        app.now['phase'] = 'waiting'                      # 切れたあとは「最後に分かっている線」
        self.assertFalse(cl.view(app)['device']['live'])
        self.assertIsNone(cl.device_view({'error': 'x'}))
        self.assertIsNone(cl.view(FakeApp())['device'])

    def test_watcher_reads_the_line_speed_and_signals(self):
        logger = setups.load('vehicle', 'ncec')['logger']
        text = (f"@@S\n{{}}\n@@L\n{json.dumps({'line': SUGO['line'], 'values': {'LapCount': 1}, 'running': False})}\n@@C\n1\n"
                f"@@T\n{json.dumps(telemetry(12.0))}\n@@G\n{json.dumps(logger)}\n")
        link = mock.Mock(run=mock.Mock(return_value=text))
        course = now_status.read(link)['course']
        self.assertEqual((course['speed_kmh'], course['vehicle']['same'], cl.match(course['line'])), (12.0, True, 'sugo'))
        link.run.return_value = '@@S\n{}\n@@L\n\n@@C\n1\n'   # 線が読めなかった回
        self.assertIsNone(now_status.read(link)['course'])


class LineOpsTest(unittest.TestCase):
    def patch(self, *args, **kw):
        patcher = mock.patch.object(*args, **kw)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def direct(self, **device):
        link, dev = FakeLink(), FakeDevice(**device)
        self.patch(app_ops, 'device_api', side_effect=dev.api)
        self.send = self.patch(rc, 'send')
        app = FakeApp(link)
        return app, app_ops.Ops(app), link, dev

    def lte(self, reply=None, secret=SECRET):
        self.patch(rc, 'load_local', return_value=secret)
        self.api = self.patch(app_ops, 'device_api')
        self.send = self.patch(rc, 'send', return_value=reply)
        app = FakeApp()
        return app, app_ops.Ops(app)

    # ---- 送る前の確認
    def test_plan_direct_reads_the_device_and_changes_nothing(self):
        app, ops, link, dev = self.direct()
        plan = ops.action('/api/op/line_plan', {'line': north(sugo(), 2.0), 'course': 'sugo'})
        self.assertEqual([c[0] for c in dev.calls], ['/api/lap', '/api/telemetry'])
        self.assertEqual((dev.posts(), link.scripts), ([], []))
        self.assertEqual((plan['via'], plan['direct'], plan['need_code'], plan['same'], plan['by_name']), ('USB', True, False, False, None))
        self.assertEqual(plan['changes'], ['線 4本 → 4本', 'コントロールライン：北へ 2.00 m 動かす'])
        self.assertTrue(any('控えます' in n for n in plan['notes']))
        self.assertIsNone(app.now['op'])

    def test_plan_needs_the_code_at_racing_speed_only(self):
        for kmh, need in ((0.0, False), (99.0, False), (100.0, True), (132.0, True)):   # SUGOの設定は100 km/h
            with self.subTest(kmh):
                app, ops, link, dev = self.direct(kmh=kmh)
                plan = ops.line_plan({'line': north(sugo(), 2.0)})
                self.assertEqual(plan['need_code'], need)
                self.assertEqual('走行中' in plan['title'], need)
        app, ops, link, dev = self.direct(line=north(sugo(), 50.0), kmh=70.0)    # 設定に無い線の本体：下書きの元のコースか、目安の60
        self.assertFalse(ops.line_plan({'line': sugo(), 'course': 'sugo'})['need_code'])
        self.assertTrue(ops.line_plan({'line': sugo()})['need_code'])

    def test_plan_unknown_speed_counts_as_stopped_and_says_so(self):
        app, ops, link, dev = self.direct(fix=False)
        plan = ops.line_plan({'line': north(sugo(), 2.0)})
        self.assertFalse(plan['need_code'])
        self.assertTrue(any('車速が分かりません' in n and '止まっているものとして' in n for n in plan['notes']))

    def test_plan_warns_about_the_running_lap_and_the_sector_times(self):
        app, ops, link, dev = self.direct(running=True)
        plan = ops.line_plan({'line': sugo(sectors=[])})
        self.assertTrue(any('1周を数えている途中' in n and '本体のソフトが古く' in n for n in plan['notes']))
        dev.extra = {'line_change_restarts': True}      # 線を変えたら走っている周を捨てる本体
        newer = ops.line_plan({'line': sugo(sectors=[])})['notes']
        self.assertTrue(any('走っている周は数えず' in n for n in newer))
        self.assertFalse(any('本体のソフトが古く' in n for n in newer))
        self.assertTrue(any('セクターのタイムとベストは消えます' in n for n in plan['notes']))
        same = ops.line_plan({'line': sugo()})
        self.assertTrue(same['same'])
        self.assertIn('変わる所はありません', same['changes'][0])

    def test_plan_by_lte_always_needs_the_code(self):
        app, ops = self.lte()
        plan = ops.line_plan({'line': sugo(), 'course': 'sugo'})
        self.assertEqual((plan['via'], plan['direct'], plan['need_code'], plan['by_name']), ('LTE', False, True, 'sugo'))
        self.assertTrue(any('新しい線を次に通った所からラップを数え直します' in n for n in plan['notes']))
        self.assertEqual(plan['changes'][0], '線 4本')            # 本体の線が分からないので、送る線を出す
        self.assertIsNone(ops.line_plan({'line': north(sugo(), 3.0)})['by_name'])
        app.now['course'] = {'line': sugo(), 'read_at': time.time()}   # 前に読んだ線があれば、それと比べる
        self.assertEqual(ops.line_plan({'line': north(sugo(), 3.0)})['changes'][1], 'コントロールライン：北へ 3.00 m 動かす')
        self.api.assert_not_called()
        self.send.assert_not_called()

    def test_plan_by_lte_without_the_secret_says_what_to_do(self):
        app, ops = self.lte(secret={})
        with self.assertRaises(app_ops.Refused) as caught:
            ops.line_plan({'line': sugo()})
        self.assertIn('合言葉の準備', str(caught.exception))

    def test_a_bad_line_is_never_sent(self):
        bad = sugo(width_m=300)
        app, ops, link, dev = self.direct()
        self.assertTrue(any('幅が 5〜200 m の外' in p for p in ops.line_plan({'line': bad})['problems']))
        self.assertIn('線の形になっていません', ops.line_plan({'line': 'x'})['problems'][0])
        with self.assertRaises(app_ops.Refused) as caught:
            ops.action('/api/op/line_set', {'line': bad, 'confirmed': True})
        self.assertIn('幅が 5〜200 m の外', str(caught.exception))
        self.assertEqual((dev.calls, link.scripts), ([], []))
        app, ops = self.lte()
        with self.assertRaises(app_ops.Refused):
            ops.line_set({'line': sugo(lat=None, lon=None), 'confirmed': True})
        self.send.assert_not_called()
        self.assertIsNone(app.now['op'])

    # ---- 直接入れる
    def test_direct_keeps_the_old_line_sends_and_reads_back(self):
        app, ops, link, dev = self.direct()
        new = north({k: v for k, v in sugo().items() if k not in cl.RACE_KEYS}, 2.0)
        ops.action('/api/op/line_set', {'line': new})
        op = wait(app)
        self.assertEqual([(p, b is not None) for p, b in dev.calls],
                         [('/api/lap', False), ('/api/telemetry', False), ('/api/lap', True), ('/api/lap', False)])   # 読む → 送る → 読み直す
        self.assertEqual(dev.posts(), [new])
        self.assertEqual(len(link.scripts), 1)                    # 送る前に、本体の中で控える
        self.assertRegex(link.scripts[0], r"cd /data .*\n.*\n\[ -e (lap\.json\.bak-\d{8}-\d{6}) \] \|\| cp -p lap\.json \1 ")
        self.assertEqual((op['ok'], op['via'], op['kind']), (True, 'USB', 'line'))
        self.assertIn('本体から読み直して確かめました：送った線と同じです', op['lines'][0])
        self.assertIn('PCにあるどの設定とも違う線', '\n'.join(op['lines']))
        self.assertRegex(op['lines'][-1], r'本体の lap\.json\.bak-\d{8}-\d{6} に控えました')
        self.assertEqual(app.now['course']['line']['lat'], new['lat'])   # 図は、読み直した値になる
        self.assertEqual(app.now['course']['line']['min_lap_s'], 60.0)   # 送らなかった値は本体のまま
        self.send.assert_not_called()

    def test_direct_at_racing_speed_waits_for_the_code(self):
        app, ops, link, dev = self.direct(kmh=120.0)
        with self.assertRaises(app_ops.Refused) as caught:
            ops.line_set({'line': north(sugo(), 2.0)})
        self.assertIn('確認の数字', str(caught.exception))
        self.assertEqual((dev.posts(), link.scripts), ([], []))
        self.assertIsNone(app.now['op'])
        ops.line_set({'line': north(sugo(), 2.0), 'confirmed': True})   # 断らない：確認を済ませれば入る
        self.assertTrue(wait(app)['ok'])
        self.assertEqual(len(dev.posts()), 1)

    def test_direct_same_line_changes_nothing(self):
        app, ops, link, dev = self.direct()
        ops.line_set({'line': sugo()})
        op = wait(app)
        self.assertTrue(op['ok'])
        self.assertIn('もう同じでした', op['lines'][0])
        self.assertEqual((dev.posts(), link.scripts), ([], []))

    def test_direct_does_not_send_when_the_old_line_cannot_be_kept(self):
        app, ops, link, dev = self.direct()
        link.fail = True
        ops.line_set({'line': north(sugo(), 2.0)})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('控えられなかったので、何も変えていません', op['lines'][0])
        self.assertEqual(dev.posts(), [])

    def test_direct_reports_a_read_back_that_differs(self):
        app, ops, link, dev = self.direct(keep=True)              # 本体が受けたのに変わらなかった
        ops.line_set({'line': north(sugo(), 2.0)})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('★送った線と違う所があります', op['lines'][0])

    def test_direct_unreadable_device_says_so(self):
        app, ops, link, dev = self.direct()
        self.patch(app_ops, 'device_api', side_effect=OSError('/api/lap: HTTP 000'))
        for call in (lambda: ops.line_plan({'line': sugo()}), lambda: ops.line_set({'line': sugo()}), ops.car_here):
            with self.assertRaises(app_ops.Refused) as caught:
                call()
            self.assertIn('読めませんでした', str(caught.exception))

    # ---- LTEで送る
    def test_lte_sends_the_whole_line_after_the_code(self):
        new = north(sugo(), 2.0)
        back = {'name': None, 'control': [round(new['lat'], 7), new['lon'], 97.5, 50.0], 'start': None, 'goal': None, 'sectors': 3,
                'id': 'AB12', 'at': '2026-11-13T10:05+09:00', 'changed': True}
        app, ops = self.lte({'ok': True, 'op': 'line_set', 'message': 'line set', 'line': back, 'status': STATUS})
        with self.assertRaises(app_ops.Refused) as caught:
            ops.action('/api/op/line_set', {'line': new})
        self.assertIn('確認の数字', str(caught.exception))
        self.send.assert_not_called()
        ops.action('/api/op/line_set', {'line': new, 'confirmed': True})
        op = wait(app)
        self.assertEqual(self.send.call_args.args[0], 'line_set')
        arg = self.send.call_args.args[1]
        self.assertEqual(arg, {k: v for k, v in new.items() if k != 'enabled'})   # 線まるごと（start・goal・sectors も）
        self.assertEqual((op['ok'], op['via'], op['kind']), (True, 'LTE', 'line'))
        self.assertIn('本体から読み直した線は、送った線と同じでした', op['lines'][1])
        self.assertTrue(app.now['course']['sent'])                # つながるまで、図には送って確かめた線を出す
        self.assertEqual(app.now['course']['line']['lat'], new['lat'])
        self.assertEqual(len(app.now['lte']['checks']), 5)
        self.api.assert_not_called()

    def test_lte_read_back_that_differs_is_not_ok(self):
        back = {'name': 'sugo', 'control': [38.0, 140.0, 97.5, 50.0], 'start': None, 'goal': None, 'sectors': 3, 'id': 'AB12', 'at': None, 'changed': True}
        app, ops = self.lte({'ok': True, 'op': 'line_set', 'message': 'line set', 'line': back, 'status': STATUS})
        ops.line_set({'line': sugo(), 'confirmed': True})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('★本体から読み直した線が、送った線と違います', op['lines'][1])
        self.assertIsNone(app.now['course'])

    def test_lte_by_name_sends_only_the_name_and_explains_a_missing_course(self):
        app, ops = self.lte({'ok': False, 'op': 'course_select', 'message': 'no course sugo', 'courses': ['motegi'], 'status': STATUS})
        ops.line_set({'line': sugo(), 'by_name': 'sugo', 'confirmed': True})
        op = wait(app)
        self.assertEqual(self.send.call_args.args[:2], ('course_select', {'name': 'sugo'}))
        self.assertFalse(op['ok'])
        text = '\n'.join(op['lines'])
        self.assertIn('本体に「sugo」というコースの設定がありません（入っているのは motegi）', text)
        self.assertIn('線まるごと', text)
        with self.assertRaises(app_ops.Refused):
            ops.line_set({'by_name': 'nowhere', 'confirmed': True})

    def test_lte_no_reply_is_reported(self):
        app, ops = self.lte(None)
        ops.line_set({'line': sugo(), 'confirmed': True})
        op = wait(app)
        self.assertFalse(op['ok'])
        self.assertIn('返事がありませんでした', op['lines'][0])

    # ---- 車のいまの位置
    def test_car_here_needs_a_link_and_a_fix(self):
        app, ops, link, dev = self.direct(kmh=40.0)
        self.assertEqual(ops.action('/api/op/car_here', {})['yaw'], 97.0)
        dev.fix = False
        with self.assertRaises(app_ops.Refused) as caught:
            ops.car_here()
        self.assertIn('測位していません', str(caught.exception))
        app, ops = self.lte()
        with self.assertRaises(app_ops.Refused) as caught:
            ops.car_here()
        self.assertIn('USBかテザリング', str(caught.exception))

    # ---- 画面との受け渡し
    def test_http_gives_the_plan_the_page_script_and_the_reason(self):
        link, dev = FakeLink(), FakeDevice(kmh=120.0)
        self.patch(app_ops, 'device_api', side_effect=dev.api)
        with tempfile.TemporaryDirectory() as tmp:
            app = vc.App(vc.PcStore(Path(tmp) / 'v2_video'), None, link=link)
            app.now = FakeApp(link).now
            app.ops = app_ops.Ops(app)
            server = vc.make_server(app, 0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f'http://127.0.0.1:{server.server_port}'

            def post(path, body):
                req = urllib.request.Request(url + path, json.dumps(body).encode(), {'X-Video-Collect': '1'})
                return json.loads(urllib.request.urlopen(req).read())
            try:
                self.assertIn('renderLines', urllib.request.urlopen(url + '/course_lines.js').read().decode())
                self.assertIn('id="tab-lines"', urllib.request.urlopen(url + '/').read().decode())
                state = json.loads(urllib.request.urlopen(url + '/api/state').read())
                self.assertEqual([c['id'] for c in state['course']['courses']], setups.names('course'))
                plan = post('/api/op/line_plan', {'line': north(sugo(), 2.0)})
                self.assertEqual((plan['ok'], plan['need_code'], plan['via']), (True, True, 'USB'))
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    post('/api/op/line_set', {'line': north(sugo(), 2.0)})
                self.assertEqual(caught.exception.code, 409)
                self.assertIn('確認の数字', json.loads(caught.exception.read())['error'])
                caught.exception.close()
                self.assertEqual(dev.posts(), [])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
