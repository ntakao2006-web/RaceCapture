import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import collect_logs

LOGS = [{'name': 'LOG_20261024T010000Z_0123abcd.csv', 'size': 6, 'active': False, 'demo': False},
        {'name': 'LOG_20261024T020000Z_4567abcd.csv', 'size': 3, 'active': True, 'demo': False}]


class FakeUnoQ(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {'/api/status': b'{}', '/api/logs': json.dumps(LOGS).encode(),
                f'/api/logs/{LOGS[0]["name"]}/download': b'a,b\n1,2',
                f'/api/logs/{LOGS[0]["name"]}/metadata': b'{"state":"closed"}'}.get(self.path)
        self.send_response(200 if body is not None else 404); self.end_headers()
        self.wfile.write(body or b'')

    def log_message(self, *args):
        pass


class CollectTests(unittest.TestCase):
    def setUp(self):
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
        self.assertEqual((run / 'v2_emmc' / LOGS[0]['name']).read_bytes(), b'a,b\n1,2')
        self.assertTrue((run / 'v2_emmc' / (LOGS[0]['name'] + '.meta.json')).exists())
        self.assertFalse((run / 'v2_emmc' / LOGS[1]['name']).exists())  # still recording
        self.assertEqual(len(list((self.v1 / 'logs').iterdir())), 5)
        self.assertEqual(self.run_once(), 0)
        self.assertEqual(len(list(self.out.glob('*/run*'))), 1)  # nothing new -> no new folder
        (self.v2 / 'EL000002.BIN').write_bytes(b'next session')
        self.assertEqual(self.run_once(), 0)
        run2 = next(self.out.glob('*/run02_*'))
        self.assertEqual([p.name for p in (run2 / 'v2_sd').glob('*.BIN')], ['EL000002.BIN'])

    def test_unreachable_uno_q_still_collects_cards(self):
        self.server.shutdown()
        rc = collect_logs.main(['--drives', str(self.v1), '--url', 'http://127.0.0.1:9/', '--no-phone', '--out', str(self.out)])
        self.assertEqual(rc, 0)
        self.assertTrue(next(self.out.glob('*/run01_*/v1_sd')).is_dir())


if __name__ == '__main__':
    unittest.main()
