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
        out = report_ops.save(self.root, RUN, table(), body(slow={'12': 'incident', '16': 'slow_all', '17': 'slow_all', '13': 'pre_pit', '10': 'none'}))
        s = out['saved']
        self.assertEqual((s['race_laps'], s['stints'], s['pit_laps'], s['pit_out_laps']), ([9, 18], [[9, 14], [15, 18]], [14], [15]))
        self.assertEqual((s['incident_laps'], s['slow_all_laps'], s['pre_pit_slow']), ([12], [[16, 17]], [[13, 13]]))
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
