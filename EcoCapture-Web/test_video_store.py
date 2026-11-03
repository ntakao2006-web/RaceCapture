"""video_store.py: the deletion rules for onboard videos. The scenarios in
tools/unoq_overlay_enc/testdata/video_store/ are also run by the recorder's video_store_test.c, so the
recorder and EcoCapture delete the same files in the same order (unoq_video_check_procedure.md 5-17)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import video_store as vs

SCENARIOS = Path(__file__).resolve().parents[1] / 'tools' / 'unoq_overlay_enc' / 'testdata' / 'video_store'
ZERO = '0' * 64


def run_scenario(path, test):
    boot, now, wall = '', 0.0, None
    with tempfile.TemporaryDirectory() as tmp:
        v, lg = Path(tmp) / 'video', Path(tmp) / 'logs'
        v.mkdir()
        lg.mkdir()
        for raw in path.read_text(encoding='utf-8').splitlines():
            line = raw.split('#', 1)[0].strip()
            if not line:
                continue
            cmd, _, rest = line.partition(' ')
            rest = rest.strip()
            d = lg if cmd.startswith('log') and cmd != 'logged' else v
            scan = lambda: vs.scan(v, boot, now, lg, wall)
            if cmd == 'boot':
                boot = rest
            elif cmd == 'now':
                now = float(rest)
            elif cmd == 'wall':
                wall = float(rest)
            elif cmd in ('recording', 'logrecording'):
                (d / '.recording').write_text(''.join(t + '\n' for t in rest.split()), encoding='utf-8')
            elif cmd in ('file', 'logfile'):
                name, size, mtime = rest.split()
                (d / name).write_bytes(b'x' * int(size))
                os.utime(d / name, (int(mtime), int(mtime)))
            elif cmd in ('ok', 'logok'):
                name, size = rest.split()
                (d / (name + '.ok')).write_text(f'{size} {ZERO} 2026-11-08T00:00:00Z\n', encoding='utf-8')
            elif cmd in ('keep', 'logkeep'):
                (d / (rest + '.keep')).write_bytes(b'')
            elif cmd == 'expect':
                got = ' '.join(i.name for i in scan().deletion_order())
                test.assertEqual(got, rest, f'{path.name}: 消す順')
            elif cmd == 'bytes':
                test.assertEqual(scan().deletable_bytes(), int(rest), f'{path.name}: 消してよい大きさ')
            elif cmd == 'delete':
                for _ in range(int(rest)):
                    order = scan().deletion_order()
                    if order:
                        vs.delete(v, order[0], 'test', boot, lg)
            elif cmd in ('left', 'logsleft'):
                got = ' '.join(sorted(n for n in os.listdir(d) if n != vs.LOG_NAME or d == lg))
                test.assertEqual(got, rest, f'{path.name}: 残ったファイル')
            elif cmd == 'logged':
                log = v / vs.LOG_NAME
                lines = log.read_text(encoding='utf-8').count('\n') if log.exists() else 0
                test.assertEqual(lines, int(rest), f'{path.name}: 消した記録')
            else:
                test.fail(f'{path.name}: 知らない行 {cmd}')


class VideoStoreTests(unittest.TestCase):
    def test_scenarios(self):
        files = sorted(SCENARIOS.glob('*.txt'))
        if not files:
            self.skipTest('場面のファイルが無い（リポジトリの外で動かしている）')
        for path in files:
            with self.subTest(path.name):
                run_scenario(path, self)

    def test_session_names(self):
        self.assertEqual(vs.session_of('20261108_130205_03.ts'), ('20261108_130205', 3))
        self.assertEqual(vs.session_of('20261108_130205_1234.ts'), ('20261108_130205', 1234))
        self.assertEqual(vs.session_of('20261108_130205_1.ts'), ('20261108_130205_1', 0))
        self.assertEqual(vs.session_of('20261030_211950.ts'), ('20261030_211950', 0))

    def test_minutes_left_counts_free_space_and_what_may_be_deleted(self):
        mib = 1048576
        store = vs.Store({'a_01.ts': (770 * 10**6, 1)}, {}, 'B', 0)  # nothing recording: deletable
        per_min = 10e6 / 8 * 60 * vs.TS_OVERHEAD
        self.assertAlmostEqual(store.minutes_left(1024 * mib + per_min * 5), 5 + 770e6 / per_min)
        self.assertEqual(store.minutes_left(0, min_free_mb=1024 + 770), 0)
        rec = '.recording'
        store = vs.Store({'20261108_130205_01.ts': (100, 1)},
                         {rec: 'boot_id=B\nsession=20261108_130205\nfile=20261108_130205_01.ts\nbt=99\nmbps=5\nmin_free_mb=1\n'},
                         'B', 100)
        self.assertEqual(store.deletable_bytes(), 0)
        self.assertAlmostEqual(store.minutes_left(mib + 5e6 / 8 * 60 * vs.TS_OVERHEAD), 1)

    def test_make_room_stops_when_nothing_may_be_deleted_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name, mtime in (('20261108_090000_01.ts', 10), ('20261108_090000_02.ts', 20), ('20261108_130205_01.ts', 30)):
                (d / name).write_bytes(b'x' * 10)
                (d / (name[:-3] + '.csv')).write_bytes(b'c')
                os.utime(d / name, (mtime, mtime))
            (d / '20261108_090000.session').write_text('boot_id=B\n', encoding='utf-8')
            (d / '.recording').write_text('boot_id=B\nsession=20261108_130205\nfile=20261108_130205_01.ts\nbt=99\n',
                                          encoding='utf-8')
            done = vs.make_room(d, 1, lambda: 0, 'ecocapture', 'B', 100)
            self.assertEqual([c.name for c in done], ['20261108_090000_01.ts', '20261108_090000_02.ts'])
            self.assertEqual(sorted(os.listdir(d)), ['.recording', '20261108_130205_01.csv', '20261108_130205_01.ts', vs.LOG_NAME])
            rows = vs.parse_log((d / vs.LOG_NAME).read_text(encoding='utf-8'))
            self.assertEqual([(r['by'], r['name'], r['size'], r['collected'], r['boot']) for r in rows],
                             [('ecocapture', '20261108_090000_01.ts', 10, False, 'B'),
                              ('ecocapture', '20261108_090000_02.ts', 10, False, 'B')])


    def test_deleting_a_log_takes_all_its_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v, lg, j = root / 'video', root / 'logs', root / 'sd-journals'
            for d in (v, lg, j):
                d.mkdir()
            name = 'LOG_20261101T000000Z_0123abcd.csv'
            for part in ('', '.meta.json', '.can.jsonl', '.sd-journal.jsonl', '.ok', '.keep'):
                (lg / (name + part)).write_bytes(b'x')
                os.utime(lg / (name + part), (1000, 1000))
            (j / (name + '.timestamps.jsonl')).write_bytes(b'x')
            store = vs.scan(v, 'B', 100, now_wall=10000)
            self.assertEqual([(i.kind, i.name, i.size) for i in store.items], [('log', name, 4)])
            self.assertEqual(store.deletion_order(), [])  # protected and the marker is not for this size
            vs.delete(v, store.logs[0], 'ecocapture', 'B')
            self.assertEqual(os.listdir(lg) + os.listdir(j), [])
            rows = vs.parse_log((v / vs.LOG_NAME).read_text(encoding='utf-8'))
            self.assertEqual([(r['kind'], r['name'], r['size'], r['by']) for r in rows], [('log', name, 4, 'ecocapture')])

if __name__ == '__main__':
    unittest.main(verbosity=2)
