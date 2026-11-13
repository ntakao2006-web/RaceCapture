"""走行の索引（run_index.py）の試験。作りものの保存先（一時フォルダー）で確かめる。"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import run_index

T0 = datetime(2026, 11, 8, 1, 0, 0, tzinfo=timezone.utc)   # 日本時間 10:00
HEADER = 'schema,demo,source,host_utc,seq,mcu_ms,Lat,Lon,GPSFix,imu_raw,LapCount,OilTemp'


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def write_log(folder, start, minutes, laps=None, where=(35.0, 139.0), fix=True, name_id='0000abcd', partial_last=False):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'LOG_{start:%Y%m%dT%H%M%S}Z_{name_id}.csv'
    rows = [HEADER]
    for k in range(int(minutes * 60) + 1):
        t = start + timedelta(seconds=k)
        lap = '' if laps is None else str(int(laps * k / max(1, minutes * 60)))
        rows.append(f'1,False,logger-v2-hardware,{iso(t)},{k},{k * 1000},{where[0]},{where[1]},{3 if fix else 0},"[0.99, 0.01]",{lap},90.5')   # 値の中にカンマのある列（本物と同じ）
    text = '\n'.join(rows) + '\n'
    if partial_last:
        text += '1,False,logger-v2-hard'     # 電源断で書きかけの行
    path.write_text(text, encoding='utf-8')
    return path


def write_chapter(root, session, number, start, minutes):
    folder = root / 'v2_video' / session
    folder.mkdir(parents=True, exist_ok=True)
    ts = folder / f'{session}_{number:02}.ts'
    ts.write_bytes(b'G' * 188)
    rows = ['frame,video_s,utc,clock,host_utc']
    for k in range(int(minutes * 60) + 1):
        rows.append(f'{k * 30},{k:.3f},{iso(start + timedelta(seconds=k))},gnss,{iso(start + timedelta(seconds=k))}')
    ts.with_suffix('.csv').write_text('\n'.join(rows) + '\n\n', encoding='utf-8')
    return ts


class RunIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.object(run_index, 'load_courses', return_value={'here': (35.0, 139.0), 'far': (38.0, 140.0)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_gets_the_day_it_was_driven_and_its_videos(self):
        # 走ったのは11/8（日本時間）。回収したのは11/11（フォルダーの名前）
        write_log(self.root / '20261111' / 'run01_1516' / 'v2_emmc', T0, 20, laps=7, partial_last=True)
        write_chapter(self.root, '20261108_100000', 1, T0 - timedelta(minutes=1), 10)
        write_chapter(self.root, '20261108_100000', 2, T0 + timedelta(minutes=9), 12)
        write_chapter(self.root, '20261107_150000', 1, T0 - timedelta(days=1), 10)       # 別の日の動画は結ばない
        (self.root / 'v2_video' / 'laps').mkdir()
        (self.root / 'v2_video' / 'laps' / 'cut.ts').write_bytes(b'x')                   # 切り出した動画は章ではない
        run, = run_index.build(self.root)
        self.assertEqual(run['day'], '2026-11-08')
        self.assertEqual((run['minutes'], run['laps'], run['course']), (20.0, 7, 'here'))
        self.assertEqual([Path(v['path']).name for v in run['videos']], ['20261108_100000_01.ts', '20261108_100000_02.ts'])
        self.assertEqual((run['video'], run['gaps']), ('all', []))
        self.assertEqual(run['log'], '20261111/run01_1516/v2_emmc/' + run['id'] + '.csv')

    def test_partial_and_missing_video_with_the_gap(self):
        write_log(self.root / '20261108' / 'run01_1200' / 'v2_emmc', T0, 30)
        write_log(self.root / '20261108' / 'run01_1200' / 'v2_emmc', T0 + timedelta(hours=2), 5, name_id='0000beef', fix=False)
        write_chapter(self.root, '20261108_100000', 1, T0, 10)
        write_chapter(self.root, '20261108_100000', 2, T0 + timedelta(minutes=20), 10)
        later, first = run_index.build(self.root)          # 新しい順
        self.assertEqual((first['video'], first['video_minutes']), ('part', 20.0))
        gap, = first['gaps']
        self.assertEqual(gap, [round((T0 + timedelta(minutes=10)).timestamp()), round((T0 + timedelta(minutes=20)).timestamp())])
        self.assertEqual((later['video'], later['videos'], later['laps'], later['course']), ('none', [], None, None))

    def test_same_log_collected_twice_is_one_run(self):
        write_log(self.root / '20261108' / 'run01_1200' / 'v2_emmc', T0, 2)
        write_log(self.root / '20261109' / 'run01_0900' / 'v2_emmc', T0, 2)
        self.assertEqual(len(run_index.build(self.root)), 1)

    def test_far_from_every_course_is_unknown(self):
        write_log(self.root / '20261108' / 'run01_1200' / 'v2_emmc', T0, 1, where=(36.0, 139.0))
        self.assertIsNone(run_index.build(self.root)[0]['course'])

    def test_second_build_reads_only_what_changed(self):
        log = write_log(self.root / '20261108' / 'run01_1200' / 'v2_emmc', T0, 3)
        first = run_index.build(self.root)
        saved = json.loads((self.root / run_index.INDEX_NAME).read_text(encoding='utf-8'))
        self.assertEqual(saved['runs'], first)
        with mock.patch.object(run_index, 'read_log', side_effect=AssertionError('読み直してはいけない')):
            self.assertEqual(run_index.build(self.root), first)
        with open(log, 'a', encoding='utf-8') as f:        # 追記されたら読み直す
            f.write(f'1,False,logger-v2-hardware,{iso(T0 + timedelta(minutes=9))},999,999000,35.0,139.0,3,"[1, 2]",,90.5\n')
        self.assertEqual(run_index.build(self.root)[0]['minutes'], 9.0)

    def test_no_save_and_empty(self):
        self.assertEqual(run_index.build(self.root, save=False), [])
        self.assertFalse((self.root / run_index.INDEX_NAME).exists())

    def test_real_course_files_load(self):
        mock.patch.stopall()
        self.assertIn('sugo', run_index.load_courses())
        self.assertIn('SUGO', run_index.course_names()['sugo'])


if __name__ == '__main__':
    unittest.main()
