"""export_session.py（解析アプリ用の ecorun 形式への書き出し）の試験。作りものの走行記録で確かめる。

本体の時計を測位より約13分進め（11/8の朝と同じ）、測位は10Hz・届くまで40ms遅れ、周は線を越えて50ms後に数える。
"""
import gzip
import csv
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_session as ex  # noqa: E402

START = datetime(2026, 11, 8, 3, 0, 0, tzinfo=timezone.utc).timestamp()   # 本当の時刻で記録の始まり
HOST_AHEAD = 800.3       # 本体の時計の進み（秒）
LAP_S = [70.0, 61.25, 60.5, 62.0]   # 周の長さ（最初の周は線を越えるまでの走り出し）
INTRO = 3.0              # 測位が出るまでの秒
UNITS = {'Speed': 'km/h', 'RPM': 'rpm', 'LongAccel': 'g', 'ClutchDisengaged': '', 'Lat': '°', 'Lon': '°',
         'GPSSpeed': 'km/h', 'Yaw': '°', 'GPSFix': '', 'LapCount': '', 'LapTime': 'Min', 'LastSector': '',
         'SectorTime': 'Min', 'PressVoltState': ''}
HEADER = ['schema', 'host_utc', 'mcu_ms', 'Speed', 'RPM', 'LongAccel', 'ClutchDisengaged', 'Lat', 'Lon', 'Altitude',
          'GPSSpeed', 'Yaw', 'GPSFix', 'GPSSats', 'gnss_utc', 'gnss_itow_ms', 'gnss_hacc_m', 'LapCount', 'LapTime',
          'LastSector', 'SectorTime', 'PressVoltState']


def iso(t, frac=True):
    d = datetime.fromtimestamp(t, timezone.utc)
    return d.strftime('%Y-%m-%dT%H:%M:%S') + (d.strftime('.%f') + '+00:00' if frac else 'Z')


def crossings():
    out, at = [], START + INTRO
    for s in LAP_S:
        at += s
        out.append(at)
    return out          # 線を越えた本当の時刻（1周目の終わり、2周目の終わり、…）


def position(t):
    a = 2 * math.pi * (t - START) / 60.0
    return 35.0 + 0.0018 * math.cos(a), 135.0 + 0.0022 * math.sin(a)


def write_log(folder):
    path = Path(folder) / 'LOG_20261108T030000Z_test.csv'
    cross = crossings()
    rows = [HEADER]
    end = cross[-1] + 4.0
    n = int((end - START) * 100)
    for k in range(n):
        t = START + k / 100
        fix_t = math.floor((t - 0.04) * 10) / 10          # 40ms前までに出た最新の解
        has_fix = fix_t >= START + INTRO
        lap = sum(1 for c in cross if t >= c + 0.05)
        lap_time = '' if lap == 0 else f'{LAP_S[lap - 1] / 60:.8f}'
        lat, lon = position(fix_t)
        itow = round((fix_t + ex.LEAP - ex.GPS_EPOCH) % 604800 * 1000)
        # 周に入って20秒後にセクター1を越え、そのタイムは (20 + 済んだ周の数) 秒。越えるまでは前の値のまま
        began = cross[lap - 1] if lap else START + INTRO
        done = lap if t >= began + 20 else lap - 1
        sector = ('1', f'{(20 + done) / 60:.8f}') if done >= 0 else ('', '')
        rows.append(['1', iso(t + HOST_AHEAD), str(k * 10), '100', f'{2000 + k % 500}', '0.25', str(1 if k % 1000 < 50 else 0),
                     *((f'{lat:.8f}', f'{lon:.8f}', '120.5', '99.0', '45.0', '3', '12') if has_fix else ('',) * 7),
                     iso(math.floor(fix_t), frac=False) if has_fix else '', str(itow) if has_fix else '', '1.2' if has_fix else '',
                     str(lap), lap_time, *sector, '4'])
    with open(path, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(rows)
    Path(str(path) + '.meta.json').write_text(json.dumps({
        'units': UNITS, 'config': {'device_name': 'EcoLogger V2', 'signals': [{'name': 'RPM', 'can_id': 513}]}}), encoding='utf-8')
    return path


def read_gz(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return list(csv.reader(f))


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = write_log(cls.tmp.name)
        quiet = lambda *a: None   # noqa: E731
        cls.lap_dir, cls.lap = ex.export(cls.log, Path(cls.tmp.name) / 'lap.ecorun', laps=(2, 3), log=quiet)
        cls.all_dir, cls.all = ex.export(cls.log, Path(cls.tmp.name) / 'all.ecorun', log=quiet)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_session_header(self):
        s = self.lap
        self.assertEqual((s['format'], s['version'], s['clock']), ('ecorun', 1, 'gnss'))
        self.assertEqual(s['channels_file'], 'channels.csv.gz')
        self.assertEqual(s['gnss'], {'source': 'logger', 'rate_hz': 10.0})
        self.assertEqual(s['videos'], [])
        self.assertTrue(s['t0_utc'].endswith('Z'))

    def test_clock_is_corrected_to_gnss(self):
        # 2周目の始まり（1周目の終わり）の5秒前が t=0。本体の時計の13分の進みが取れていること
        t0 = ex.utc_seconds([self.lap['t0_utc']])[0]
        self.assertAlmostEqual(t0, crossings()[0] - 5.0, delta=0.12)

    def test_laps(self):
        cross = crossings()
        laps = self.lap['laps']
        self.assertEqual([x['lap'] for x in laps], [2, 3])
        t0 = ex.utc_seconds([self.lap['t0_utc']])[0]
        for x, (a, b), dur, sec in zip(laps, zip(cross[0:2], cross[1:3]), LAP_S[1:3], (21.0, 22.0)):
            self.assertEqual(x['time_s'], dur)
            self.assertAlmostEqual(x['start'] + t0, a, delta=0.12)
            self.assertAlmostEqual(x['end'] + t0, b, delta=0.12)
            self.assertEqual(x['sectors'], [sec])
        self.assertEqual([x['lap'] for x in self.all['laps']], [1, 2, 3, 4])

    def test_gnss_points_are_real_fixes_at_fix_time(self):
        rows = read_gz(self.lap_dir / 'gnss.csv.gz')
        self.assertEqual(rows[0], ['t', 'lat', 'lon', 'alt_m', 'speed_kmh', 'heading_deg', 'sats', 'hacc_m'])
        t0 = ex.utc_seconds([self.lap['t0_utc']])[0]
        ts = [float(r[0]) for r in rows[1:]]
        self.assertEqual(ts, sorted(set(ts)))
        for r in rows[1:]:
            fix = float(r[0]) + t0
            self.assertAlmostEqual((fix * 10) % 1, 0, delta=0.002) if (fix * 10) % 1 < 0.5 else \
                self.assertAlmostEqual((fix * 10) % 1, 1, delta=0.002)
            lat, lon = position(round(fix * 10) / 10)
            self.assertAlmostEqual(float(r[1]), lat, places=7)
            self.assertAlmostEqual(float(r[2]), lon, places=7)
        self.assertAlmostEqual(len(ts) / (ts[-1] - ts[0]), 10, delta=0.2)

    def test_channels(self):
        names = [c['name'] for c in self.lap['channels']]
        self.assertEqual(names, ['Speed', 'RPM', 'LongAccel', 'ClutchDisengaged'])   # 位置・周・状態の印は出さない
        kinds = {c['name']: (c['unit'], c['kind']) for c in self.lap['channels']}
        self.assertEqual(kinds['LongAccel'], ('g', 'number'))
        self.assertEqual(kinds['ClutchDisengaged'], ('', 'state'))
        rows = read_gz(self.lap_dir / 'channels.csv.gz')
        self.assertEqual(rows[0], ['t'] + names)
        ts = [float(r[0]) for r in rows[1:]]
        self.assertEqual(ts[0], 0.0)
        self.assertTrue(all(b > a for a, b in zip(ts, ts[1:])))
        self.assertAlmostEqual(ts[1] - ts[0], 0.02, places=6)
        self.assertAlmostEqual(ts[-1], self.lap['duration_s'], places=3)
        self.assertTrue(all(r[1] == '100' and r[3] == '0.25' for r in rows[1:]))

    def test_no_logger_internals(self):
        text = (self.lap_dir / 'session.json').read_text(encoding='utf-8')
        for word in ('can_id', 'signals', 'LapCount', 'imu_raw', 'mcu_ms'):
            self.assertNotIn(word, text)

    def test_resample_holds_and_expires(self):
        out = ex.resample(ex.np.array([0.0, 1.0, 5.0]), ex.np.array([1.0, 2.0, 3.0]), ex.np.array([-0.5, 0.5, 1.9, 3.0, 5.0]))
        self.assertTrue(math.isnan(out[0]))
        self.assertEqual(list(out[1:3]), [1.0, 2.0])
        self.assertTrue(math.isnan(out[3]))      # 1秒より古い値は持たない
        self.assertEqual(out[4], 3.0)

    def test_sync_pairs(self):
        rows = [(v, 1000.0 + v) for v in range(0, 11)]          # 動画の秒 v が UTC 1000+v
        pairs = ex.sync_pairs(rows, key_utc=1003.0, video_start=0.0, duration=5.0, t0=1001.0)
        self.assertEqual(pairs[0], [0.0, 2.0])                  # 切り出しの頭（UTC 1003）は t=2
        self.assertEqual(pairs[-1], [5.0, 7.0])
        self.assertEqual(len(pairs), 6)

    def test_line_crossings(self):
        # 北緯35度を東へ40m/sで走り、東向きの線（経度135度）を START+12.34 秒に越える。測位は10Hz
        m_per_deg = ex.EARTH_M_PER_DEG * math.cos(math.radians(35.0))
        t = ex.np.arange(START, START + 25, 0.1)
        x = 40.0 * (t - (START + 12.34))
        g = ex.pd.DataFrame({'utc': t, 'lat': 35.0 + 3.0 / ex.EARTH_M_PER_DEG, 'lon': 135.0 + x / m_per_deg})
        line = {'lat': 35.0, 'lon': 135.0, 'bearing': 90.0, 'width_m': 20.0}
        c = ex.line_crossings(g, line)
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(c[0], START + 12.34, delta=1e-4)
        self.assertEqual(len(ex.line_crossings(g, {**line, 'bearing': 270.0})), 0)   # 逆向きは数えない
        self.assertEqual(len(ex.line_crossings(g, {**line, 'width_m': 4.0})), 0)     # 中心から3m：幅4mの外
        gap = g[(g.utc < START + 12.0) | (g.utc > START + 13.2)]                       # 越えた所の前後1.2秒が抜けた
        self.assertEqual(len(ex.line_crossings(gap, line)), 0)

    def test_snap_laps_shares_boundaries(self):
        cross = [100.0, 161.25, 221.75, 283.75]
        delay = [0.05, 0.17, -0.01, 0.12]                   # 周が増えた行は、越えた時刻から周ごとに違うだけ遅れる
        times = [61.25, 60.5, 62.0]
        laps = [{'lap': i + 2, 'end': cross[i + 1] + delay[i + 1], 'time_s': times[i]} for i in range(3)]
        for x in laps:
            x['start'] = x['end'] - x['time_s']
        laps[2]['time_s'] = 62.5                            # 本体のタイムと合わない周（線が違う）
        laps[2]['start'] = laps[2]['end'] - 62.5
        self.assertEqual(ex.snap_laps(laps, ex.np.array(cross)), 2)
        self.assertEqual((laps[0]['start'], laps[0]['end']), (100.0, 161.25))
        self.assertEqual(laps[1]['start'], laps[0]['end'])  # 前の周の終わりと次の周の始まりが同じ時刻
        self.assertEqual(laps[1]['end'], 221.75)
        self.assertNotIn('snapped', laps[2])
        self.assertAlmostEqual(laps[2]['end'], 283.87)       # 合わない周は周が増えた行の時刻のまま
        self.assertEqual(ex.snap_laps(laps, ex.np.array([])), 0)

    def test_unknown_laps_stop_with_reason(self):
        with self.assertRaises(SystemExit) as cm:
            ex.export(self.log, Path(self.tmp.name) / 'x.ecorun', laps=(8, 9), log=lambda *a: None)
        self.assertIn('8〜9周', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
