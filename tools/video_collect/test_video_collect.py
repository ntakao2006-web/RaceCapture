"""video_collect.py の試験。本体の代わりに一時フォルダを「本体」にして、本体で動かすスクリプトをそのまま
Git Bash（かLinux）の sh で流す。吸い出しは cp（壊れた吸い出しの試験では1バイト変える）。"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import video_collect as vc  # noqa: E402

SH = shutil.which('sh')
BOOT = 'aaaaaaaa-1111-2222-3333-444444444444'


def posix(path):
    p = str(path)
    if os.name == 'nt' and len(p) > 1 and p[1] == ':':
        return '/' + p[0].lower() + p[2:].replace('\\', '/')
    return p


class FakeLink(vc.Link):
    kind = 'USB'

    def argv(self, command):
        return [SH, '-c', command]

    def pull_argv(self, remote, local):
        return [SH, '-c', f'cp {vc.q(remote)} {vc.q(posix(local))}']

    def label(self):
        return 'USB（試験）'


class BadLink(FakeLink):
    def pull_argv(self, remote, local):  # 中身が1バイト違う（大きさは同じ）
        return [SH, '-c', f'cp {vc.q(remote)} {vc.q(posix(local))} && printf Z | dd of={vc.q(posix(local))} bs=1 seek=3 conv=notrunc 2>/dev/null']


def uptime():
    return float(subprocess.run([SH, '-c', "cut -d' ' -f1 /proc/uptime"], capture_output=True, text=True).stdout)


def csv_text(start, seconds):
    from datetime import datetime, timezone
    rows = ['frame,video_s,utc,clock,host_utc']
    for k in range(seconds):
        t = datetime.fromtimestamp(start + k, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        rows.append(f'{k * 30},{k:.3f},{t},gnss,{t}')
    return '\n'.join(rows) + '\n'


class FakeItem:
    def __init__(self, collected=False, active=False, kept=False, size=1 << 30):
        self.collected, self.active, self.kept, self.size = collected, active, kept, size


class FakeState:
    """本体の一覧の代わり（結果のまとめ・入れ替わりの見積もりが見る所だけ）"""

    def __init__(self, items=(), chapters=None, free=20 << 30, minutes=300, active_file=None, active_log=None):
        self.free, self._minutes = free, minutes
        items = list(items)
        self.store = type('Store', (), {
            'items': items, 'chapters': list(chapters) if chapters is not None else items, 'active_file': active_file, 'active_log': active_log,
            'deletable_bytes': lambda self_: sum(i.size for i in items if i.collected or (not i.active and not i.kept))})()

    def minutes_left(self):
        return self._minutes


@unittest.skipUnless(SH, 'sh が無い（Git Bash か Linux で動かす）')
class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.data, self.out = base / 'data', base / 'pc' / 'v2_video'
        self.video = self.data / 'video'
        (self.data / 'logs').mkdir(parents=True)
        self.video.mkdir()
        (base / 'boot_id').write_text(BOOT + '\n')
        (self.data / 'logs' / 'LOG_20261108T040000Z_0000abcd.csv').write_bytes(b'x' * 100)  # 書いたばかり：消さない
        t0 = 1793750400  # 2026-11-03T00:00:00Z ごろ
        files = {
            # 前の起動の走行（2章）
            '20261107_090000_01': (b'A' * 1000, t0, 600), '20261107_090000_02': (b'B' * 500, t0 + 600, 300),
            # 前の名前の形：時刻が続いている2本は1つの走行に見せる
            '20261030_175847': (b'L' * 300, t0 - 9000, 601), '20261030_180849': (b'M' * 200, t0 - 8399, 300),
            # 今の走行（録画中は _02）
            '20261108_130205_01': (b'C' * 800, t0 + 4000, 600), '20261108_130205_02': (b'D' * 100, t0 + 4600, 60),
        }
        for stem, (body, start, secs) in files.items():
            (self.video / f'{stem}.ts').write_bytes(body)
            (self.video / f'{stem}.csv').write_text(csv_text(start, secs))
            os.utime(self.video / f'{stem}.ts', (start + secs, start + secs))
        (self.video / '20261108_130205.session').write_text(f'boot_id={BOOT}\nstart_mono=1\nclock=gnss\n')
        (self.video / '.recording').write_text(f'boot_id={BOOT}\nsession=20261108_130205\nfile=20261108_130205_02.ts\n'
                                               f'bt={uptime():.3f}\nmbps=10\nmin_free_mb=2048\n')
        (self.video / 'deleted.log').write_text('2026-11-07T00:00:00Z\trecorder\t20261101_090000_01.ts\t123\tuncollected\taaaaaaaa\n')
        self.link = FakeLink(root=posix(self.data), boot_file=posix(base / 'boot_id'))
        self.pc = vc.PcStore(self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        return vc.list_device(self.link)

    def test_list_groups_sessions_and_states(self):
        st = self.state()
        self.assertEqual(st.boot, BOOT)
        self.assertGreater(st.free, 0)
        self.assertEqual(st.store.active_file, '20261108_130205_02.ts')
        groups = vc.describe(st, self.pc)
        self.assertEqual([g['id'] for g in groups], ['20261030_175847', '20261107_090000', '20261108_130205'])
        legacy = groups[0]
        self.assertEqual(legacy['members'], ['20261030_175847', '20261030_180849'])
        self.assertEqual([c['name'] for c in legacy['chapters']], ['20261030_175847.ts', '20261030_180849.ts'])
        current = groups[2]
        self.assertTrue(current['current'])
        self.assertEqual([c['state'] for c in current['chapters']], ['current', 'recording'])
        self.assertEqual(groups[1]['seconds'], 900)
        self.assertEqual(st.deleted[0]['name'], '20261101_090000_01.ts')
        self.assertEqual([(g.name, g.size, g.active) for g in st.store.logs], [('LOG_20261108T040000Z_0000abcd.csv', 100, True)])
        self.assertEqual(st.store.deletable_bytes(), 1000 + 500 + 300 + 200 + 800)  # 今の走行の古い章も（ドラレコと同じ）

    def test_collect_verifies_marks_and_skips_the_file_being_written(self):
        job = vc.Job('test')
        n = vc.collect(self.link, self.state(), self.pc, None, job)
        self.assertEqual(n, 5, job.messages)
        for stem, session in (('20261107_090000_01', '20261107_090000'), ('20261030_180849', '20261030_175847')):
            pc_ts = self.out / session / f'{stem}.ts'
            sha = hashlib.sha256(pc_ts.read_bytes()).hexdigest()
            self.assertEqual(pc_ts.read_bytes(), (self.video / f'{stem}.ts').read_bytes())
            self.assertTrue((self.out / session / f'{stem}.csv').is_file())
            self.assertEqual((self.video / f'{stem}.ts.ok').read_text().split()[:2], [str(pc_ts.stat().st_size), sha])
            self.assertEqual(self.pc.index[f'{stem}.ts']['sha256'], sha)
        self.assertFalse((self.video / '20261108_130205_02.ts.ok').exists())
        self.assertFalse(list(self.out.rglob('*.part')))
        manifest = json.loads((self.out.parent / 'collected.json').read_text(encoding='utf-8'))
        self.assertIn('v2_video/20261107_090000_02.ts/500', manifest)
        self.assertEqual((self.out / '20261107_090000' / '20261107_090000.m3u8').read_text().splitlines(),
                         ['#EXTM3U', '20261107_090000_01.ts', '20261107_090000_02.ts'])
        states = {c['name']: c['state'] for g in vc.describe(self.state(), self.pc) for c in g['chapters']}
        self.assertEqual(states['20261108_130205_01.ts'], 'collected')
        self.assertEqual(states['20261108_130205_02.ts'], 'recording')
        self.assertEqual(vc.collect(self.link, self.state(), self.pc, None, vc.Job('again')), 0)

    def test_corrupt_copy_is_not_marked(self):
        bad = BadLink(root=self.link.root, boot_file=self.link.boot_file)
        with self.assertRaisesRegex(OSError, '中身が違う'):
            vc.collect(bad, self.state(), self.pc, ['20261107_090000'], vc.Job('test'))
        self.assertFalse(list(self.video.glob('*.ok')))
        self.assertFalse(list(self.out.rglob('*.ts*')))
        self.assertEqual(self.pc.index, {})

    def test_delete_only_what_is_verified_on_both_sides(self):
        vc.collect(self.link, self.state(), self.pc, None, vc.Job('test'))
        tampered = self.out / '20261107_090000' / '20261107_090000_01.ts'
        tampered.write_bytes(b'X' * 1000)  # PCの写しが変わった
        job = vc.Job('delete')
        removed = vc.delete_on_device(self.link, self.state(), self.pc, None, job)
        self.assertEqual(removed, 4)
        self.assertTrue(any('PCの写しが変わっている' in p for p in job.problems))
        left = sorted(p.name for p in self.video.iterdir())
        self.assertEqual(left, ['.recording', '20261107_090000_01.csv', '20261107_090000_01.ts', '20261107_090000_01.ts.ok',
                                '20261108_130205.session', '20261108_130205_02.csv', '20261108_130205_02.ts', 'deleted.log'])
        rows = vc.vs.parse_log((self.video / 'deleted.log').read_text())
        self.assertEqual(sorted(r['name'] for r in rows if r['by'] == 'pc'),
                         ['20261030_175847.ts', '20261030_180849.ts', '20261107_090000_02.ts', '20261108_130205_01.ts'])
        self.assertTrue(all(r['collected'] and r['boot'] == BOOT[:8] for r in rows if r['by'] == 'pc'))
        self.assertTrue((self.out / '20261107_090000' / '20261107_090000_02.ts').is_file())  # PCの写しは消さない

    def test_keep_marks_the_whole_session(self):
        st = self.state()
        legacy = vc.describe(st, self.pc)[0]
        vc.set_keep(self.link, legacy['members'], True)
        self.assertTrue((self.video / '20261030_175847.keep').exists() and (self.video / '20261030_180849.keep').exists())
        st = self.state()
        self.assertTrue(vc.describe(st, self.pc)[0]['kept'])
        self.assertEqual(st.store.deletable_bytes(), 1000 + 500 + 800)
        vc.set_keep(self.link, legacy['members'], False)
        self.assertFalse(list(self.video.glob('*.keep')))

    def test_keep_protects_the_logs_of_that_time(self):
        logs = self.data / 'logs'
        during, later = 'LOG_20261104T000500Z_0000000a.csv', 'LOG_20261104T020000Z_0000000b.csv'
        for name, mtime in ((during, 1793750400 + 800), (later, 1793750400 + 9000)):
            (logs / name).write_bytes(b'y' * 50)
            os.utime(logs / name, (mtime, mtime))
        group = next(g for g in vc.describe(self.state(), self.pc) if g['id'] == '20261107_090000')
        self.assertEqual(group['logs'], [during])
        vc.set_keep(self.link, group['members'], True, group['logs'])
        st = self.state()
        self.assertEqual({g.name: g.kept for g in st.store.logs}, {during: True, later: False, 'LOG_20261108T040000Z_0000abcd.csv': False})
        self.assertNotIn(during, [i.name for i in st.store.deletion_order()])
        vc.set_keep(self.link, group['members'], False, group['logs'])
        self.assertFalse(list(logs.glob('*.keep')))

    def test_join_keeps_bytes_and_shifts_the_csv(self):
        folder = self.out / 'S'
        folder.mkdir(parents=True)

        def ts(path, pts_list):
            data = b''
            for pts in pts_list:
                pes = bytes([0, 0, 1, 0xe0, 0, 0, 0x80, 0x80, 5, 0x21 | (pts >> 29 & 0x0e), pts >> 22 & 0xff,
                             0x01 | (pts >> 14 & 0xfe), pts >> 7 & 0xff, 0x01 | (pts << 1 & 0xfe)])
                data += bytes([0x47, 0x41, 0x00, 0x10]) + pes + b'\xff' * (184 - len(pes))
            path.write_bytes(data)
        ts(folder / 'S_01.ts', [90000 * k for k in range(0, 11)])          # 0〜10秒
        ts(folder / 'S_02.ts', [90000 * k + 900000 + 3000 for k in range(0, 6)])  # 続き（10.033秒から）
        ts(folder / 'S_03.ts', [90000 * k for k in range(0, 3)])           # 録画をやり直した（PTSが戻る）
        for name, n in (('S_01', 11), ('S_02', 6), ('S_03', 3)):
            (folder / f'{name}.csv').write_text('frame,video_s,utc,clock,host_utc\n' +
                                                ''.join(f'{k * 30},{k:.3f},T{k},gnss,H{k}\n' for k in range(n)))
        job = vc.Job('join')
        out = vc.join_session(self.pc, 'S', job)
        self.assertEqual(out.read_bytes(), b''.join((folder / f'S_0{k}.ts').read_bytes() for k in (1, 2, 3)))
        rows = [l.split(',') for l in (folder / 'S_all.csv').read_text().splitlines()[1:]]
        by = {(r[0], r[1]): float(r[2]) for r in rows}
        self.assertAlmostEqual(by[('S_01', '0')], 0)
        self.assertAlmostEqual(by[('S_02', '0')], 10 + 3000 / 90000, places=3)
        self.assertAlmostEqual(by[('S_03', '0')], 10 + 3000 / 90000 + 5 + 1 / 30, places=3)
        self.assertTrue(any('やり直した所が1か所' in m for m in job.messages))

    def test_backup_to_a_folder_is_checked(self):
        vc.collect(self.link, self.state(), self.pc, ['20261107_090000'], vc.Job('test'))
        target = Path(self.tmp.name) / 'backup'
        target.mkdir()
        self.pc.settings['backup'] = str(target)
        job = vc.Job('backup')
        self.assertEqual(vc.backup(self.pc, job), 2)
        self.assertEqual((target / '20261107_090000' / '20261107_090000_01.ts').read_bytes(), b'A' * 1000)
        self.assertTrue(all(str(target) in e['backup'] for e in self.pc.index.values()))
        self.assertEqual(vc.backup(self.pc, vc.Job('again')), 0)

    def test_refuses_when_the_pc_is_full(self):
        with patch.object(vc.shutil, 'disk_usage', return_value=type('U', (), {'free': 10})()):
            with self.assertRaisesRegex(OSError, 'PCの空きが足りない'):
                vc.collect(self.link, self.state(), self.pc, None, vc.Job('test'))

    def test_one_button_takes_logs_videos_and_the_card_without_deleting(self):
        """「回収する」1回で、本体の走行記録・動画・挿したSDカードを同じ run フォルダへ取る。元はどれも消さない"""
        sys.path.insert(0, str(Path(__file__).parents[1] / 'collect_logs'))
        import test_collect_logs as tcl
        server = vc.ThreadingHTTPServer(('127.0.0.1', 0), tcl.FakeUnoQ)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_port
        self.link.open_forward = lambda: (port, lambda: None)
        card = Path(self.tmp.name) / 'card'
        card.mkdir()
        (card / 'EL000001.BIN').write_bytes(b'ELB2' * 20000)
        tcl.MARKED.clear()
        try:
            with patch.object(vc.sd_card, 'volume', side_effect=lambda d: {
                    'drive': d, 'label': 'ECOLOGGER', 'fs': 'FAT32', 'total': 16 << 30, 'free': 8 << 30,
                    'cluster': 32768, 'sector': 512, 'removable': True}):
                job = vc.Job('回収')
                r = vc.collect_everything(self.link, self.pc, job, [str(card)])
                self.assertEqual(job.problems, [])
                self.assertEqual((r['logs'], r['videos'], r['sd']), (1, 5, 1))  # 記録中の走行記録・録画中の章は取らない
                self.assertEqual(r['got'], ['走行記録 1 本', '動画 5 本', 'SDカードの記録 1 本'])
                self.assertEqual(r['level'], 'warn')  # 録画中の1本は取っていないので、そのことを結果に出す
                self.assertIn('いま録画している動画 1 本', [m['what'] for m in r['missed']])
                self.assertTrue(any('電源を入れ直す' in n for n in r['next']))
                run = Path(r['folder'])
                self.assertTrue((run / 'v2_emmc' / tcl.LOGS[0]['name']).is_file())
                self.assertTrue((run / 'v2_sd' / 'EL000001.BIN').is_file())
                self.assertEqual(tcl.MARKED, [tcl.LOGS[0]['name']])  # 本体に回収済みの印
                self.assertTrue((card / 'EL000001.BIN').is_file())  # カードからは消さない
                self.assertTrue((self.video / '20261107_090000_01.ts').is_file())  # 本体の動画も消さない
                again = vc.collect_everything(self.link, self.pc, vc.Job('回収'), [str(card)])
                self.assertEqual((again['logs'], again['sd']), (0, 0))  # 2回目は何も取らない
        finally:
            server.shutdown()

    def test_without_the_logger_only_the_card_is_taken(self):
        card = Path(self.tmp.name) / 'card'
        card.mkdir()
        (card / 'EL000001.BIN').write_bytes(b'ELB2' * 20000)
        with patch.object(vc.sd_card, 'volume', side_effect=lambda d: {
                'drive': d, 'label': 'ECOLOGGER', 'fs': 'FAT32', 'total': 16 << 30, 'free': 8 << 30,
                'cluster': 32768, 'sector': 512, 'removable': True}):
            r = vc.collect_everything(None, self.pc, vc.Job('回収'), [str(card)])
        self.assertEqual((r['logs'], r['videos'], r['sd']), (0, 0, 1))
        self.assertTrue(any('本体がつながっていない' in n for n in r['notes']))
        self.assertEqual((r['got'], r['level']), (['SDカードの記録 1 本'], 'warn'))
        self.assertEqual(r['missed'], [{'what': '本体の走行記録と動画', 'why': '本体がつながっていない'}])
        self.assertTrue(any('USB-CをPCへ直接つなぐ' in n for n in r['next']))

    def test_result_says_nothing_new_when_everything_is_on_the_pc(self):
        r = vc.summarize_result({'logs': 0, 'videos': 0, 'sd': 0, 'notes': []}, 'USB', FakeState(), [])
        self.assertEqual((r['got'], r['missed'], r['next'], r['level']), ([], [], [], 'none'))

    def test_result_over_tethering_tells_how_to_get_the_videos(self):
        state = FakeState(chapters=[FakeItem(collected=False), FakeItem(collected=True)])
        r = vc.summarize_result({'logs': 2, 'videos': 0, 'sd': 0, 'notes': []}, 'テザリング', state, [], usb_blocked=True)
        self.assertEqual(r['level'], 'warn')
        self.assertEqual(r['missed'][0]['what'], '本体の動画 1 本')
        self.assertIn('ドックをつないだまま起動した', r['next'][0])
        self.assertIn('もう一度「回収する」', r['next'][0])
        done = vc.summarize_result({'logs': 2, 'videos': 0, 'sd': 0, 'notes': []}, 'テザリング', FakeState(chapters=[FakeItem(collected=True)]), [])
        self.assertEqual((done['missed'], done['level']), ([], 'ok'))   # 取る動画が残っていなければ、何も言わない

    def test_result_lists_failures_and_the_missing_card(self):
        r = vc.summarize_result({'logs': 0, 'videos': 0, 'sd': 0, 'notes': ['SDカードは挿さっていなかった']}, 'USB', FakeState(),
                                ['本体の動画：20261107_090000_01.ts：本体とPCで中身が違う'])
        self.assertEqual(r['missed'], [{'what': '本体の動画', 'why': '20261107_090000_01.ts：本体とPCで中身が違う'}])
        self.assertTrue(any('取れたものは取り直しません' in n for n in r['next']))
        self.assertTrue(any('SDカードの控え' in n for n in r['next']))

    def test_evict_risk_counts_only_what_the_logger_would_delete(self):
        gib = 1 << 30
        items = [FakeItem(collected=True, size=4 * gib), FakeItem(collected=False, size=2 * gib),
                 FakeItem(collected=False, active=True, size=gib), FakeItem(collected=False, kept=True, size=gib)]
        state = FakeState(items=items, free=3 * gib, minutes=100)
        risk = vc.evict_risk(state)
        self.assertEqual((risk['count'], risk['bytes']), (1, 2 * gib))     # 録画中・保護は消えないので数えない
        self.assertEqual(risk['safe_minutes'], 75)                         # 空き2+回収済み4=6GiBぶんは安全、残り2GiBが回収していないもの
        self.assertIsNone(vc.evict_risk(FakeState(items=[items[0], items[2]], free=3 * gib)))
        r = vc.summarize_result({'logs': 0, 'videos': 0, 'sd': 0, 'notes': []}, 'USB', state, [])
        self.assertTrue(any('あと約75分で古い順に消え始めます' in n for n in r['next']))

    def test_http_needs_the_page_header(self):
        app = vc.App(self.pc, None, link=self.link)
        app.refresh()
        server = vc.make_server(app, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            state = json.loads(urllib.request.urlopen(url + '/api/state').read())
            self.assertEqual(len(state['sessions']), 3)
            self.assertEqual(state['device']['logs_bytes'], 100)
            req = urllib.request.Request(url + '/api/settings', data=b'{"backup":"E:\\\\x"}', method='POST')
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(req)
            self.assertEqual(err.exception.code, 403)
            req.add_header('X-Video-Collect', '1')
            urllib.request.urlopen(req)
            self.assertEqual(self.pc.settings['backup'], 'E:\\x')
        finally:
            server.shutdown()

    def test_a_second_launch_opens_the_running_page_instead_of_sharing_the_port(self):
        app = vc.App(self.pc, None, link=self.link)
        app.refresh()
        first = vc.make_server(app, 0)
        port = first.server_port
        threading.Thread(target=first.serve_forever, daemon=True).start()
        try:
            self.assertEqual(vc.running_app(port), f'http://127.0.0.1:{port}/')
            second = vc.make_server(app, port)  # 同じ番号では待てず、別の番号になる
            try:
                self.assertNotEqual(second.server_port, port)
            finally:
                second.server_close()
            with patch.object(vc, 'App', side_effect=AssertionError('本体を探しに行かない')), \
                    patch.object(vc.webbrowser, 'open') as opened:
                self.assertEqual(vc.main(['--port', str(port), '--out', str(self.pc.root)]), 0)
            opened.assert_called_once_with(f'http://127.0.0.1:{port}/#now')  # 開く段を付ける（既定は「いまの様子」。2026-11-13）
        finally:
            first.shutdown()
            first.server_close()
        self.assertIsNone(vc.running_app(port))


if __name__ == '__main__':
    unittest.main(verbosity=2)
