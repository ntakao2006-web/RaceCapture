"""周の動画（lap_clip.py）と、アプリが動画を流す出口の試験。ffmpeg と本物の録画は使わない。"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import lap_clip
import video_collect as vc

RUN = {'id': 'LOG_20261108T010000Z_0000abcd', 'videos': []}
LAP = {'lap': 3, 'time_s': 110.095, 'start': 1000.0, 'end': 1110.0}


class MakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def chapters(self, *spans):
        patcher = mock.patch.object(lap_clip, 'chapter_rows', side_effect=[('a.ts', 'a.csv', a, b, []) for a, b in spans])
        patcher.start()
        self.addCleanup(patcher.stop)
        return {**RUN, 'videos': [{'path': f'v2_video/s/{k}.ts'} for k in range(len(spans))]}

    def test_no_times_or_no_video_is_said_plainly(self):
        with self.assertRaises(lap_clip.NoVideo):
            lap_clip.make(self.root, RUN, 0, {**LAP, 'start': None})
        with self.assertRaisesRegex(lap_clip.NoVideo, 'PCにありません'):
            lap_clip.make(self.root, RUN, 0, LAP)
        with self.assertRaisesRegex(lap_clip.NoVideo, 'PCにありません'):
            lap_clip.make(self.root, self.chapters((0, 500)), 0, LAP)      # 別の時間の動画しか無い

    def test_cuts_then_makes_the_mp4_and_remembers_it(self):
        import lap_video
        run = self.chapters((990, 1200))
        made = []

        def fake_ffmpeg(argv, **kw):
            made.append(argv)
            Path(argv[-1]).write_bytes(b'mp4')
            return mock.Mock(returncode=0, stderr='')
        with mock.patch.object(lap_video, 'cut_plan', return_value=([('a.ts', 0, 10)], 996.3)) as plan, \
                mock.patch.object(lap_video, 'write_cut', side_effect=lambda plan_, out: Path(out).write_bytes(b'ts')), \
                mock.patch.object(lap_clip.subprocess, 'run', side_effect=fake_ffmpeg):
            clip = lap_clip.make(self.root, run, 2, LAP, ffmpeg='ffmpeg')
        self.assertEqual(plan.call_args.args[1:], (LAP['start'] - lap_clip.LEAD_S, LAP['end'] + lap_clip.TAIL_S))
        self.assertEqual((clip['lead_in_s'], clip['partial'], clip['seconds']), (3.7, False, 110.0))
        folder = self.root / lap_clip.CLIP_DIR
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [clip['file'][:-4] + '.json', clip['file']])   # 途中のファイルは残さない
        self.assertIn('-c:v', made[0])
        self.assertEqual(made[0][made[0].index('-c:v') + 1], 'copy')        # 映像は作り直さない
        with mock.patch.object(lap_clip, 'chapter_rows', return_value=('a.ts', 'a.csv', 990, 1200, [])), \
                mock.patch.object(lap_clip.subprocess, 'run', side_effect=AssertionError('作り直してはいけない')):
            self.assertEqual(lap_clip.make(self.root, run, 2, LAP, ffmpeg='ffmpeg'), clip)

    def test_partial_video_is_flagged_and_failures_leave_nothing(self):
        import lap_video
        run = self.chapters((1050, 1200))
        with mock.patch.object(lap_video, 'cut_plan', return_value=([('a.ts', 0, 10)], 1050.0)), \
                mock.patch.object(lap_video, 'write_cut', side_effect=lambda plan_, out: Path(out).write_bytes(b'ts')), \
                mock.patch.object(lap_clip.subprocess, 'run', return_value=mock.Mock(returncode=1, stderr='bad stream')):
            with self.assertRaisesRegex(OSError, 'bad stream'):
                lap_clip.make(self.root, run, 0, LAP, ffmpeg='ffmpeg')
        self.assertEqual(list((self.root / lap_clip.CLIP_DIR).iterdir()), [])

    def test_no_ffmpeg(self):
        import lap_video
        run = self.chapters((990, 1200))
        with mock.patch.object(lap_video, 'ffbin', side_effect=SystemExit('ffmpeg が見つからない')):
            with self.assertRaisesRegex(lap_clip.NoFfmpeg, 'ffmpeg'):
                lap_clip.make(self.root, run, 0, LAP)


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.app = vc.App(vc.PcStore(root / 'v2_video'), None)
        folder = root / lap_clip.CLIP_DIR
        folder.mkdir(parents=True)
        (folder / 'lap.mp4').write_bytes(bytes(range(256)) * 4)
        (folder / 'lap.json').write_text('{}', encoding='utf-8')
        (root / 'secret.mp4').write_bytes(b'x')
        self.server = vc.make_server(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def get(self, path, headers=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers or {}), timeout=5) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_whole_file_and_ranges(self):
        code, headers, body = self.get('/media/lap.mp4')
        self.assertEqual((code, len(body), headers['Content-Type'], headers['Accept-Ranges']), (200, 1024, 'video/mp4', 'bytes'))
        code, headers, body = self.get('/media/lap.mp4', {'Range': 'bytes=10-19'})
        self.assertEqual((code, body, headers['Content-Range']), (206, bytes(range(10, 20)), 'bytes 10-19/1024'))
        code, headers, body = self.get('/media/lap.mp4', {'Range': 'bytes=1000-'})
        self.assertEqual((code, len(body), headers['Content-Range']), (206, 24, 'bytes 1000-1023/1024'))
        code, _, body = self.get('/media/lap.mp4', {'Range': 'bytes=-4'})
        self.assertEqual((code, body), (206, bytes([252, 253, 254, 255])))
        self.assertEqual(self.get('/media/lap.mp4', {'Range': 'bytes=5000-'})[0], 416)

    def test_only_clips_are_served(self):
        for path in ('/media/lap.json', '/media/..%2Fsecret.mp4', '/media/..%5Csecret.mp4', '/media/nothing.mp4', '/media/'):
            with self.subTest(path):
                self.assertEqual(self.get(path)[0], 404)

    def test_clip_for_an_unknown_lap_is_404(self):
        self.assertEqual(self.get('/api/clip?id=nothing&n=0')[0], 404)
        self.assertEqual(self.get('/api/clip?id=nothing')[0], 404)


if __name__ == '__main__':
    unittest.main()
