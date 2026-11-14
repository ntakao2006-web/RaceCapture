"""analysis_open.py（走行の行から解析アプリで開く、SP-10-8）の試験。書き出しの道具と解析アプリは作りもので置き換える"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis_open as ao  # noqa: E402


class FindAppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.repo = self.root / 'work' / 'EcoLogger'
        self.repo.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, p):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'')
        return p

    def test_nothing_found(self):
        self.assertIsNone(ao.find_app(self.home, self.repo, env={}))

    def test_order(self):
        # 開発の手元（リポジトリの隣）：.venv があればソースで動かす
        dev = self.repo.parent / ao.APP_NAME
        self.touch(dev / 'ecoanalysis' / '__init__.py')
        self.touch(dev / '.venv' / 'Scripts' / 'pythonw.exe')
        argv, cwd, where = ao.find_app(self.home, self.repo, env={})
        self.assertEqual(argv[1:], ['-m', 'ecoanalysis'])
        self.assertEqual(cwd, str(dev))
        self.assertIn('隣', where)
        # 配る zip を ~/.ecologger に広げたもの（zip の中は EcoLogger-Analysis/EcoLogger-Analysis.exe）が先
        exe = self.touch(self.home / '.ecologger' / ao.APP_NAME / f'{ao.APP_NAME}.exe')
        self.assertEqual(ao.find_app(self.home, self.repo, env={})[0], [str(exe)])
        # 書いておいた場所がさらに先（引用符つきでもよい）
        other = self.touch(self.root / 'apps' / 'x.exe')
        self.touch(self.home / '.ecologger' / 'analysis_app.txt').write_text(f'"{other}"\n', encoding='utf-8')
        self.assertEqual(ao.find_app(self.home, self.repo, env={})[0], [str(other)])
        # 環境変数がいちばん先。無い場所なら次へ
        self.assertEqual(ao.find_app(self.home, self.repo, env={'ECOLOGGER_ANALYSIS': str(self.root / 'none')})[0], [str(other)])
        self.assertEqual(ao.find_app(self.home, self.repo, env={'ECOLOGGER_ANALYSIS': str(dev)})[0][1:], ['-m', 'ecoanalysis'])

    def test_built_exe_in_dev_folder(self):
        exe = self.touch(self.repo.parent / ao.APP_NAME / 'dist' / ao.APP_NAME / f'{ao.APP_NAME}.exe')
        argv, cwd, _ = ao.find_app(self.home, self.repo, env={})
        self.assertEqual((argv, cwd), ([str(exe)], str(exe.parent)))


class OpenRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name) / 'drive_logs'
        run_dir = self.logs / '20261108' / 'run02_1303'
        self.csv = run_dir / 'v2_emmc' / 'LOG_x.csv'
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text('schema\n', encoding='utf-8')
        for d in ('20261107/run01_1520', '20261111/run02_2049', '20261108/run02_1303'):
            (self.logs / d / 'v2_sd').mkdir(parents=True)
        self.run = {'id': '20261108_1303', 'log': '20261108/run02_1303/v2_emmc/LOG_x.csv', 'video_minutes': 30}
        self.app = (['fake.exe'], '.', 'test')

    def tearDown(self):
        self.tmp.cleanup()

    def test_sd_candidates(self):
        sds = ao.sd_folders(self.logs, self.csv)
        rel = [str(p.relative_to(self.logs)).replace('\\', '/') for p in sds]
        self.assertEqual(rel, ['20261108/run02_1303/v2_sd', '20261111/run02_2049/v2_sd'])   # 自分のSD、後で回収したSD。前の日は見ない
        argv = ao.export_argv(self.csv, 'out', True, sds, python='py')
        self.assertEqual(argv.count('--sd'), 2)
        self.assertEqual(argv[-1], '--video')

    def fake_export(self, calls, fail_with_sd=False):
        def run(argv, on_line=None, timeout=3600):
            calls.append(argv)
            if fail_with_sd and '--sd' in argv:
                raise RuntimeError('書き出しに失敗：SD')
            out = Path(argv[argv.index('--out') + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / 'session.json').write_text(json.dumps({'gnss': {'source': 'sd' if '--sd' in argv else 'logger'}}), encoding='utf-8')
            if on_line:
                on_line('書き出し：' + str(out))
            return []
        return run

    def test_export_then_launch_and_skip_when_fresh(self):
        calls, launched, lines = [], [], []
        with mock.patch.object(ao, 'run_export', self.fake_export(calls)), \
                mock.patch.object(ao, 'launch', lambda app, out: launched.append(str(out))):
            r = ao.open_run(self.logs, self.run, False, on_line=lines.append, app=self.app)
            self.assertTrue(r['exported'])
            self.assertEqual(r['gnss'], 'sd')
            self.assertTrue(r['out'].endswith('20261108_1303.ecorun'))
            self.assertEqual(launched, [r['out']])
            self.assertTrue(lines)
            r2 = ao.open_run(self.logs, self.run, False, app=self.app)    # 走行記録より新しいので書き出し直さない
            self.assertFalse(r2['exported'])
            self.assertEqual(len(calls), 1)
            later = time.time() + 5                                       # 走行記録が新しくなったら書き出し直す
            os.utime(self.csv, (later, later))
            self.assertTrue(ao.open_run(self.logs, self.run, False, app=self.app)['exported'])
            v = ao.open_run(self.logs, self.run, True, app=self.app)      # 動画つきは別の置き場
            self.assertTrue(v['out'].endswith('20261108_1303_video.ecorun'))
            self.assertIn('--video', calls[-1])

    def test_retry_without_sd(self):
        calls = []
        with mock.patch.object(ao, 'run_export', self.fake_export(calls, fail_with_sd=True)), \
                mock.patch.object(ao, 'launch', lambda app, out: None):
            r = ao.open_run(self.logs, self.run, False, app=self.app)
        self.assertEqual(r['gnss'], 'logger')
        self.assertEqual(['--sd' in a for a in calls], [True, False])

    def test_errors(self):
        with mock.patch.object(ao, 'find_app', lambda: None):
            with self.assertRaisesRegex(RuntimeError, '見つかりません'):
                ao.open_run(self.logs, self.run, False)
        with self.assertRaisesRegex(RuntimeError, '走行記録が無い'):
            ao.open_run(self.logs, {**self.run, 'log': 'none.csv'}, False, app=self.app)
        with mock.patch.object(ao.shutil, 'disk_usage', lambda p: mock.Mock(free=10**9)):   # 30分の動画は約2.3GB
            with self.assertRaisesRegex(RuntimeError, '空きが足りません'):
                ao.open_run(self.logs, self.run, True, app=self.app)

    def test_run_export_reports_failure(self):
        ok = ao.run_export([sys.executable, '-c', 'print("あ"); print("い")'])
        self.assertEqual(ok, ['あ', 'い'])
        with self.assertRaisesRegex(RuntimeError, '失敗.*だめ'):
            ao.run_export([sys.executable, '-c', 'import sys; print("だめ"); sys.exit(2)'])


if __name__ == '__main__':
    unittest.main()
