"""レポートの決めごとを見て直して保存する所（report_ops.py）と、アプリの口の試験。"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import report_ops
import video_collect as vc

RUN = {'id': 'LOG_20261108T010000Z_0000abcd', 'day': '2026-11-08', 'log': 'x/LOG_20261108T010000Z_0000abcd.csv', 'videos': []}


def table():
    times = {9: 112, 10: 111, 11: 110, 12: 119, 13: 111, 14: 190, 15: 125, 16: 110, 17: 111, 18: 110}
    laps, t = [], 1_800_000_000.0
    for n, s in times.items():
        laps.append({'lap': n, 'time_s': float(s), 'stop_s': 60.0 if n == 14 else 0.0, 'start': t, 'end': t + s})
        t += s
    return {'laps': laps, 'best': 11}


def body(**change):
    return {'name': 'テストの大会', 'race_laps': [9, 18], 'pit_laps': [14], 'drivers': ['A', 'B'], 'slow': {'12': 'incident'},
            'slow_memo': {'12': '黄旗'}, 'window': ['10:20', '10:50'], 'notes': '晴れ', 'quali': None, **change}


class SaveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_view_gives_the_draft_and_nothing_saved_at_first(self):
        v = report_ops.view(self.root, RUN, table())
        self.assertIsNone(v['saved'])
        self.assertEqual((v['draft']['auto']['pit_laps'], v['draft']['auto']['slow_laps']), ([14], [12]))
        self.assertEqual(len(v['laps']), 10)

    def test_saves_in_the_names_the_analysis_uses_and_reads_it_back(self):
        out = report_ops.save(self.root, RUN, table(), body(slow={'12': 'incident', '16': 'slow_all', '17': 'slow_all', '13': 'none', '10': 'none'}, pre_pit=[12, 13]))
        s = out['saved']
        self.assertEqual((s['race_laps'], s['stints'], s['pit_laps'], s['pit_out_laps']), ([9, 18], [[9, 14], [15, 18]], [14], [15]))
        self.assertEqual((s['incident_laps'], s['slow_all_laps'], s['pre_pit_slow']), ([12], [[16, 17]], [[12, 13]]))
        self.assertEqual((s['drivers'], s['slow_memo'], s['date'], s['race_csv']), (['A', 'B'], {'12': '黄旗'}, '2026-11-08', RUN['log']))
        path = self.root / 'reports' / (RUN['id'] + '.json')
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), s)
        self.assertEqual(report_ops.view(self.root, RUN, table())['saved'], s)
        self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])      # 途中のファイルを残さない

    def test_refuses_with_every_reason_and_writes_nothing(self):
        cases = [
            (body(race_laps=[18, 9]), '最初が最後より小さく'),
            (body(race_laps=[1, 18]), 'この走行の周（9〜18）に入っていません'),
            (body(pit_laps=[30]), '決勝の周（9〜18）の外'),
            (body(pit_laps=[18]), '最後の周（18周目）はピットの周にできません'),
            (body(drivers=['A', 'B', 'C']), 'スティントは 2 つです'),
            (body(window=['10時', '11:00']), '「10:20」の形'),
            (body(slow={'12': ''}), '12周目の理由が選ばれていません'),
            (body(quali={'id': 'x', 'laps': [5, 2]}), '予選は'),
            (body(pit_laps=['x']), '周の番号（数字）'),
        ]
        for sent, text in cases:
            with self.subTest(text):
                with self.assertRaisesRegex(ValueError, text):
                    report_ops.save(self.root, RUN, table(), sent)
        self.assertFalse((self.root / 'reports').exists())
        with self.assertRaisesRegex(ValueError, '／'):       # 2つ以上あれば、全部並べる
            report_ops.save(self.root, RUN, table(), body(pit_laps=[30], window=[]))

    def test_no_drivers_and_no_pits_are_fine(self):
        s = report_ops.save(self.root, RUN, table(), body(pit_laps=[], drivers=[], slow={}, slow_memo={}))['saved']
        self.assertEqual((s['stints'], s['pit_out_laps'], s['incident_laps']), ([[9, 18]], [], []))


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = vc.App(vc.PcStore(Path(self.tmp.name) / 'v2_video'), None)
        for name, value in (('runs', {'runs': [RUN]}), ('run_laps', table())):
            patcher = mock.patch.object(self.app, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.server = vc.make_server(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def call(self, path, data=None):
        req = urllib.request.Request(self.url + path, None if data is None else json.dumps(data).encode(),
                                     {'Content-Type': 'application/json', 'X-Video-Collect': '1'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_read_save_and_refuse_through_the_app(self):
        code, v = self.call('/api/report?id=' + RUN['id'])
        self.assertEqual((code, v['draft']['auto']['race_laps'], v['saved']), (200, [9, 18], None))
        self.assertEqual(self.call('/api/report?id=nothing')[0], 404)
        code, out = self.call('/api/report_save', {'id': RUN['id'], **body()})
        self.assertEqual((code, out['saved']['stints']), (200, [[9, 14], [15, 18]]))
        self.assertEqual(self.call('/api/report?id=' + RUN['id'])[1]['saved']['name'], 'テストの大会')
        code, out = self.call('/api/report_save', {'id': RUN['id'], **body(pit_laps=[99])})
        self.assertEqual(code, 409)
        self.assertIn('決勝の周（9〜18）の外', out['error'])
        self.assertEqual(self.call('/api/report_save', {'id': 'nothing', **body()})[0], 404)


if __name__ == '__main__':
    unittest.main()


class AnalysisTest(unittest.TestCase):
    """解析を流す所（解析そのものは動かさない）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = {**RUN, 'course': 'sugo'}
        self.other = {'id': 'LOG_20261107T230000Z_0000ffff', 'log': 'y/q.csv'}

    def test_config_uses_the_names_the_analysis_reads(self):
        saved = report_ops.save(self.root, self.run, table(), body(quali={'id': self.other['id'], 'laps': [2, 7]}))['saved']
        cfg = report_ops.analysis_config(self.root, self.run, saved, [self.run, self.other], 'ncec')
        self.assertEqual((cfg['course'], cfg['vehicle'], cfg['race_laps'], cfg['stints'], cfg['quali_laps']), ('sugo', 'ncec', [9, 18], [[9, 14], [15, 18]], [2, 7]))
        self.assertEqual((Path(cfg['race_csv']), Path(cfg['quali_csv'])), (self.root / RUN['log'], self.root / 'y/q.csv'))
        self.assertEqual(Path(cfg['out_dir']), self.root / 'reports' / RUN['id'])
        self.assertNotIn('lte_dir', cfg)
        self.assertNotIn('drivers', cfg)        # 人の名前は解析の設定へ写さない

    def test_reasons_it_cannot_run_are_said_before_anything_starts(self):
        saved = report_ops.save(self.root, self.run, table(), body())['saved']
        for args, text in (((self.run, None, [], 'ncec'), '先に、決めごとを保存'),
                           (({**self.run, 'course': None}, saved, [], 'ncec'), 'コースが分かりません'),
                           ((self.run, saved, [], None), '車の設定'),
                           ((self.run, {**saved, 'quali': {'id': 'gone', 'laps': [1, 2]}}, [], 'ncec'), '予選に選んだ走行')):
            with self.subTest(text):
                with self.assertRaisesRegex(ValueError, text):
                    report_ops.analysis_config(self.root, *args)
        with mock.patch.object(report_ops, 'missing_parts', return_value=['pandas']), mock.patch.object(report_ops.subprocess, 'run') as ran:
            with self.assertRaisesRegex(ValueError, 'pandas'):
                report_ops.run_analysis(self.root, self.run, [], 'ncec')
        ran.assert_not_called()

    def test_runs_the_analysis_and_reports_what_came_out_or_why_it_stopped(self):
        report_ops.save(self.root, self.run, table(), body())

        def fake(argv, **kw):
            cfg = json.loads(Path(argv[-1]).read_text(encoding='utf-8'))
            pub = Path(cfg['out_dir']) / 'pub'
            pub.mkdir(parents=True)
            (pub / 'facts.csv').write_text('key,value\na,1\nb,2\n', encoding='utf-8')
            (pub / 'laps.csv').write_text('lap\n', encoding='utf-8')
            self.assertEqual(kw['env']['PYTHONIOENCODING'], 'utf-8')
            return mock.Mock(returncode=0, stderr='')
        with mock.patch.object(report_ops, 'missing_parts', return_value=[]), mock.patch.object(report_ops.subprocess, 'run', side_effect=fake):
            out = report_ops.run_analysis(self.root, self.run, [], 'ncec')
        self.assertEqual((out['tables'], out['facts']), (['facts.csv', 'laps.csv'], 2))
        stopped = mock.Mock(returncode=1, stderr='Traceback\n  File x\nKeyError: PressVolt\n')
        with mock.patch.object(report_ops, 'missing_parts', return_value=[]), mock.patch.object(report_ops.subprocess, 'run', return_value=stopped):
            with self.assertRaisesRegex(RuntimeError, '途中で止まりました.*PressVolt'):
                report_ops.run_analysis(self.root, self.run, [], 'ncec')

    def test_app_runs_it_in_the_background(self):
        app = vc.App(vc.PcStore(self.root / 'v2_video'), None)
        with mock.patch.object(app, 'runs', return_value={'runs': [self.run]}):
            with self.assertRaisesRegex(ValueError, '先に、決めごとを保存'):
                app.action('/api/report_run', {'id': RUN['id']})
            self.assertIsNone(app.analysis)
            report_ops.save(self.root, self.run, table(), body())
            with mock.patch.object(report_ops, 'run_analysis', return_value={'out_dir': 'x', 'pub': 'x/pub', 'tables': ['facts.csv'], 'facts': 3, 'seconds': 20}):
                app.action('/api/report_run', {'id': RUN['id']})
                for _ in range(300):
                    if not app.analysis['running']:
                        break
                    threading.Event().wait(0.01)
            self.assertEqual((app.analysis['ok'], app.analysis['facts'], app.snapshot()['analysis']['run']), (True, 3, RUN['id']))
            with self.assertRaises(KeyError):
                app.action('/api/report_run', {'id': 'nothing'})


class ResultsTest(unittest.TestCase):
    """解析の結果を見る所"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_nothing_yet_is_said_and_tables_come_as_rows(self):
        self.assertFalse(report_ops.view(self.root, RUN, table())['has_results'])
        with self.assertRaisesRegex(ValueError, 'まだ解析を流していません'):
            report_ops.results(self.root, RUN)
        pub = self.root / 'reports' / RUN['id'] / 'pub'
        pub.mkdir(parents=True)
        (pub / 'facts.csv').write_text('key,text,value,label\nbest_lap,1:50.095,110.095,決勝のベスト（秒）\n', encoding='utf-8')
        (pub / 'laps.csv').write_text('session,lap,lap_s\n決勝,9,118.1\n決勝,10,114.4\n', encoding='utf-8')
        (pub / 'slides.csv').write_text('id\n1\n', encoding='utf-8')
        report_ops.save(self.root, RUN, table(), body())
        out = report_ops.results(self.root, RUN)
        self.assertEqual((out['name'], out['tables']['facts'][0]['text'], len(out['tables']['laps'])), ('テストの大会', '1:50.095', 2))
        self.assertEqual((out['tables']['track'], 'slides' in out['tables']), ([], False))      # 無い表は空、画面が出さない表は送らない
        self.assertTrue(report_ops.view(self.root, RUN, table())['has_results'])

    def test_through_the_app(self):
        app = vc.App(vc.PcStore(self.root / 'v2_video'), None)
        with mock.patch.object(app, 'runs', return_value={'runs': [RUN]}):
            with self.assertRaises(ValueError):
                app.report_data(RUN['id'])
            with self.assertRaises(KeyError):
                app.report_data('nothing')
