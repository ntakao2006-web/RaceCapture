import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import collect_logs

LOGS = [{'name': 'LOG_20261024T010000Z_0123abcd.csv', 'size': 6, 'active': False, 'demo': False, 'collected': False},
        {'name': 'LOG_20261024T020000Z_4567abcd.csv', 'size': 3, 'active': True, 'demo': False, 'collected': False}]
CSV = b'a,b\n1,2'
MARKED = []  # 本体に回収済みの印を頼んだ名前（中身が合ったもの）


class FakeUnoQ(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {'/api/status': b'{}', '/api/logs': json.dumps(LOGS).encode(),
                f'/api/logs/{LOGS[0]["name"]}/download': CSV,
                f'/api/logs/{LOGS[0]["name"]}/metadata': b'{"state":"closed"}'}.get(self.path)
        self.send_response(200 if body is not None else 404); self.end_headers()
        self.wfile.write(body or b'')

    def do_POST(self):  # 本体と同じく、送られたSHA-256を自分の中身と比べる（CANの生ログは無い）
        import hashlib
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        ok = (self.path == f'/api/logs/{LOGS[0]["name"]}/collected' and self.headers.get('X-EcoCapture') == '1'
              and body == {'sha256': hashlib.sha256(CSV).hexdigest(), 'can_sha256': None})
        if ok:
            MARKED.append(LOGS[0]['name'])
        self.send_response(200 if ok else 409); self.end_headers()

    def log_message(self, *args):
        pass


class CollectTests(unittest.TestCase):
    def setUp(self):
        MARKED.clear()
        self.video_link = collect_logs.video_link
        collect_logs.video_link = lambda: None  # この試験の中ではPCのadbを使わない
        self.dir = Path(tempfile.mkdtemp())
        self.v1 = self.dir / 'v1card'; (self.v1 / 'logs').mkdir(parents=True)
        for name in ('20261024_100000_JST_L1234ABCD_0002.csv', '20261024_100000_JST_L1234ABCD_0002_can.csv',
                     '20261024_100000_JST_L1234ABCD_0002.meta.json', 'L1234ABCD_0000.csv', 'notes.txt'):
            (self.v1 / 'logs' / name).write_text('x')
        self.v2 = self.dir / 'v2card'; self.v2.mkdir()
        (self.v2 / 'EL000001.BIN').write_bytes(b'not a real log')
        self.phone = self.dir / 'phones' / 'Pixel 9a'; self.phone.mkdir(parents=True)
        (self.phone / 'EL_car2_20261024_101500.csv').write_text('Utc,Lat\n')
        (self.phone / 'memo.csv').write_text('x')
        self.out = self.dir / 'out'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeUnoQ)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/'

    def tearDown(self):
        collect_logs.video_link = self.video_link
        self.server.shutdown(); shutil.rmtree(self.dir)

    def run_once(self):
        return collect_logs.main(['--drives', str(self.v1), str(self.v2), '--url', self.url,
                                  '--phone-dir', str(self.phone.parent), '--out', str(self.out)])

    def test_collects_everything_once_and_never_touches_sources(self):
        self.assertEqual(self.run_once(), 0)
        run = next(self.out.glob('*/run01_*'))
        self.assertEqual(sorted(p.name for p in (run / 'v1_sd').iterdir()),
                         ['20261024_100000_JST_L1234ABCD_0002.csv', '20261024_100000_JST_L1234ABCD_0002.meta.json',
                          '20261024_100000_JST_L1234ABCD_0002_can.csv', 'L1234ABCD_0000.csv'])
        self.assertEqual([p.name for p in (run / 'phone').iterdir()], ['EL_car2_20261024_101500.csv'])
        self.assertTrue((run / 'v2_sd' / 'EL000001.BIN').exists())  # undecodable BIN is still kept
        self.assertEqual((run / 'v2_emmc' / LOGS[0]['name']).read_bytes(), CSV)
        self.assertEqual(MARKED, [LOGS[0]['name']])  # 取ったら本体に回収済みの印を頼む
        self.assertTrue((run / 'v2_emmc' / (LOGS[0]['name'] + '.meta.json')).exists())
        self.assertFalse((run / 'v2_emmc' / LOGS[1]['name']).exists())  # still recording
        self.assertEqual(len(list((self.v1 / 'logs').iterdir())), 5)
        self.assertEqual(self.run_once(), 0)
        self.assertEqual(len(list(self.out.glob('*/run*'))), 1)  # nothing new -> no new folder
        (self.v2 / 'EL000002.BIN').write_bytes(b'next session')
        self.assertEqual(self.run_once(), 0)
        run2 = next(self.out.glob('*/run02_*'))
        self.assertEqual([p.name for p in (run2 / 'v2_sd').glob('*.BIN')], ['EL000002.BIN'])
        # カードを空にすると、STM32は EL000001 から付け直す。名前も大きさも前と同じでも、中身が違えば取る
        for f in self.v2.iterdir():
            f.unlink()
        (self.v2 / 'EL000001.BIN').write_bytes(b'not a real lo9')
        self.assertEqual(self.run_once(), 0)
        run3 = next(self.out.glob('*/run03_*'))
        self.assertEqual((run3 / 'v2_sd' / 'EL000001.BIN').read_bytes(), b'not a real lo9')
        self.assertEqual(self.run_once(), 0)
        self.assertEqual(len(list(self.out.glob('*/run*'))), 3)

    def test_sd_files_collected_before_the_index_are_recognised_by_content(self):
        self.assertEqual(self.run_once(), 0)
        (self.out / 'v2_sd_index.json').unlink()  # 前の版は名前と大きさだけを collected.json に残していた
        self.assertEqual(self.run_once(), 0)
        self.assertEqual(len(list(self.out.glob('*/run*'))), 1)
        index = json.loads((self.out / 'v2_sd_index.json').read_text(encoding='utf-8'))
        self.assertEqual([k.split('/')[0] for k in index], ['EL000001.BIN'])

    def test_a_log_collected_before_gets_its_mark(self):
        LOGS[0]['collected'] = False
        self.assertEqual(self.run_once(), 0)
        MARKED.clear()
        self.assertEqual(self.run_once(), 0)  # 本体に印がまだ無い（前の版で回収した等）：写しで確かめて印を頼む
        self.assertEqual(MARKED, [LOGS[0]['name']])

    @unittest.skipUnless(shutil.which('sh'), 'sh が無い')
    def test_videos_go_through_the_collector_app(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'video_collect'))
        import test_video_collect as tv
        data = self.dir / 'data'; (data / 'video').mkdir(parents=True); (data / 'logs').mkdir()
        (data / 'video' / '20261108_130000_01.ts').write_bytes(b'0123456789')
        (data / 'video' / '20261108_130000_01.csv').write_text(tv.csv_text(1793750400, 3))
        (self.dir / 'boot').write_text(tv.BOOT)
        link = tv.FakeLink(root=tv.posix(data), boot_file=tv.posix(self.dir / 'boot'))
        collect_logs.video_link = lambda: link  # tearDown で戻す
        args = ['--drives', '--no-emmc', '--no-phone', '--out', str(self.out)]
        self.assertEqual(collect_logs.main(args), 0)
        self.assertEqual((self.out / 'v2_video' / '20261108_130000' / '20261108_130000_01.ts').read_bytes(), b'0123456789')
        self.assertTrue((data / 'video' / '20261108_130000_01.ts.ok').exists())  # 確かめて印を付けた（消してはいない）
        self.assertTrue((data / 'video' / '20261108_130000_01.ts').exists())
        manifest = json.loads((self.out / 'collected.json').read_text(encoding='utf-8'))
        self.assertIn('v2_video/20261108_130000_01.ts/10', manifest)
        self.assertEqual(collect_logs.main(args), 0)
        self.assertFalse(list(self.out.glob('*/run*')))  # 動画は走行のフォルダへ置き、run フォルダは作らない

    def test_unreachable_uno_q_still_collects_cards(self):
        self.server.shutdown()
        rc = collect_logs.main(['--drives', str(self.v1), '--url', 'http://127.0.0.1:9/', '--no-phone', '--out', str(self.out)])
        self.assertEqual(rc, 0)
        self.assertTrue(next(self.out.glob('*/run01_*/v1_sd')).is_dir())


if __name__ == '__main__':
    unittest.main()
