"""周ごとの表（run_laps.py）の試験。作りものの走行記録で確かめる。"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import run_laps

T0 = datetime(2026, 11, 8, 1, 0, 0, tzinfo=timezone.utc)
HEADER = 'schema,host_utc,Speed,GPSSpeed,imu_raw,LapCount,LapTime,LastSector,SectorTime,OilTemp,WaterTemp'


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def write(path, lap_seconds, oil_hot=None, reset_after=None, speed_missing=False):
    """lap_seconds：周ごとの長さ（秒）。1秒に1行。oil_hot：(周, 何秒間) 油温が125℃になる"""
    rows, t, count, last_time, sector = [HEADER], T0, 0, '', ('', '')
    for n, seconds in enumerate(lap_seconds, 1):
        for k in range(seconds):
            hot = oil_hot and oil_hot[0] == n and 10 <= k < 10 + oil_hot[1]
            if k == seconds // 2:
                sector = ('1', f'{(seconds // 2) / 60:.6f}')
            speed = '' if speed_missing else str(100 + n * 10 if k == 5 else 80)
            rows.append(f'1,{iso(t)},{speed},{90 + n},"[0.9, 0.1]",{count},{last_time},{sector[0]},{sector[1]},{125 if hot else 100},88')
            t += timedelta(seconds=1)
        count += 1
        last_time = f'{seconds / 60:.6f}'
        sector = ('2', f'{(seconds - seconds // 2) / 60:.6f}')
        if reset_after == n:   # 周が終わった行を1つ書いてから、ラップを0周に戻す
            rows.append(f'1,{iso(t)},80,90,"[0.9, 0.1]",{count},{last_time},{sector[0]},{sector[1]},100,88')
            t += timedelta(seconds=1)
            count, last_time = 0, ''
    rows.append(f'1,{iso(t)},80,90,"[0.9, 0.1]",{count},{last_time},{sector[0]},{sector[1]},100,88')
    path.write_text('\n'.join(rows) + '\n1,2026-11-08T0', encoding='utf-8')   # 最後は電源断の書きかけ
    return path


class LapsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / 'LOG_20261108T010000Z_0000abcd.csv'

    def test_times_best_sectors_and_top_speed(self):
        write(self.log, [100, 90, 95])
        table = run_laps.laps_of(self.log)
        self.assertEqual([lap['lap'] for lap in table['laps']], [1, 2, 3])
        self.assertEqual([lap['time_s'] for lap in table['laps']], [100.0, 90.0, 95.0])
        self.assertEqual(table['best'], 2)
        self.assertEqual(table['laps'][1]['sectors'], [45.0, 45.0])
        self.assertEqual([lap['vmax'] for lap in table['laps']], [110, 120, 130])
        self.assertEqual(table['laps'][1]['end'] - table['laps'][1]['start'], 90.0)

    def test_warning_needs_to_last_and_marks_only_its_lap(self):
        write(self.log, [60, 60, 60], oil_hot=(2, 20))
        laps = run_laps.laps_of(self.log, warn={'OilTemp': 120, 'WaterTemp': 110})['laps']
        self.assertEqual([lap['warn'] for lap in laps], [[], ['油温'], []])
        write(self.log, [60, 60], oil_hot=(1, 3))      # 3秒だけの跳ねは印にしない
        self.assertEqual([lap['warn'] for lap in run_laps.laps_of(self.log, warn={'OilTemp': 120})['laps']], [[], []])
        self.assertNotIn('OilTemp', str(laps))         # 温度の数字は表に出さない

    def test_video_per_lap(self):
        write(self.log, [100, 100, 100])
        base = T0.timestamp()
        chapters = [{'start': base - 5, 'end': base + 150}]
        self.assertEqual([lap['video'] for lap in run_laps.laps_of(self.log, chapters)['laps']], ['all', 'part', 'none'])
        self.assertEqual({lap['video'] for lap in run_laps.laps_of(self.log)['laps']}, {'none'})

    def test_reset_in_the_middle_keeps_the_earlier_laps(self):
        write(self.log, [60, 70, 80, 90], reset_after=2)
        laps = run_laps.laps_of(self.log)['laps']
        self.assertEqual([(lap['lap'], lap['time_s']) for lap in laps], [(1, 60.0), (2, 70.0), (1, 80.0), (2, 90.0)])

    def test_uses_gnss_speed_when_the_car_speed_is_missing(self):
        write(self.log, [60], speed_missing=True)
        self.assertEqual(run_laps.laps_of(self.log)['laps'][0]['vmax'], 91)

    def test_cached_reads_once_and_again_when_something_changes(self):
        write(self.log, [60, 60])
        (self.root / 'a').mkdir()
        log = self.root / 'a' / self.log.name
        self.log.replace(log)
        run = {'id': log.stem, 'log': 'a/' + log.name, 'videos': []}
        first = run_laps.cached(self.root, run, {'OilTemp': 120})
        self.assertEqual(len(first['laps']), 2)
        with mock.patch.object(run_laps, 'laps_of', side_effect=AssertionError('読み直してはいけない')):
            self.assertEqual(run_laps.cached(self.root, run, {'OilTemp': 120}), first)
        with mock.patch.object(run_laps, 'laps_of', return_value={'laps': [], 'best': None, 'rows': 0}) as again:
            run_laps.cached(self.root, run, {'OilTemp': 130})          # しきい値が変わったら読み直す
            run_laps.cached(self.root, {**run, 'videos': [{'start': 1, 'end': 2}]}, {'OilTemp': 130})   # 動画が増えても
        self.assertEqual(again.call_count, 2)

    def test_empty_file(self):
        self.log.write_text('', encoding='utf-8')
        self.assertEqual(run_laps.laps_of(self.log), {'laps': [], 'best': None, 'rows': 0})


if __name__ == '__main__':
    unittest.main()


class ClockTest(unittest.TestCase):
    def test_lap_times_of_day_follow_the_gnss_clock(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'LOG_20261108T010000Z_0000abcd.csv'
            rows = ['schema,host_utc,gnss_utc,Speed,LapCount,LapTime']
            for k in range(0, 201):
                true = T0 + timedelta(seconds=k)
                host = true + timedelta(seconds=0.5 - 810)          # 本体の時計が13分半遅れている
                rows.append(f'1,{iso(host)},{true:%Y-%m-%dT%H:%M:%SZ},80,{k // 100},{"" if k < 100 else "1.666667"}')
            log.write_text('\n'.join(rows) + '\n', encoding='utf-8')
            lap = run_laps.laps_of(log)['laps'][0]
            self.assertAlmostEqual(lap['end'], T0.timestamp() + 100, delta=1)
            self.assertAlmostEqual(lap['start'], T0.timestamp(), delta=1)
            chapters = [{'start': T0.timestamp() - 5, 'end': T0.timestamp() + 150}]     # 動画の時刻は測位の時計
            self.assertEqual(run_laps.laps_of(log, chapters)['laps'][0]['video'], 'all')
