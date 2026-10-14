import json
import math
import tempfile
import unittest
from pathlib import Path
from lap import LapLine, LapTimer, EARTH_M_PER_DEG
from models import LAP_CHANNELS

LAT0, LON0 = 36.5, 140.2


def fix(t_ms, north_m, east_m=0.0, speed=30.0, yaw=0.0, hacc=2.0):
    """One 10 Hz GNSS solution; t_ms is ms after 2026-10-24T00:00:00Z."""
    base = 1792800000  # 2026-10-24T00:00:00Z
    utc = base + t_ms // 1000
    from datetime import datetime, timezone
    text = datetime.fromtimestamp(utc, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'values': {'Lat': LAT0 + north_m / EARTH_M_PER_DEG,
                       'Lon': LON0 + east_m / (EARTH_M_PER_DEG * math.cos(math.radians(LAT0))),
                       'GPSSpeed': speed, 'Yaw': yaw},
            'gnss_utc': text, 'gnss_itow_ms': t_ms, 'gnss_hacc_m': hacc}


def drive_north(timer, start_ms, laps, lap_s, east_m=0.0):
    """Repeatedly cross the line heading north; each pass crosses at start + k*lap_s."""
    for k in range(laps + 1):
        cross = start_ms + k * lap_s * 1000
        timer.update(fix(cross - 1000, -200.0, east_m))  # out on the lap, far from the line
        for t in range(cross - 300, cross + 400, 100):
            timer.update(fix(t, (t - cross) / 100.0, east_m))  # 1 m per 100 ms, crossing at `cross`


class LapTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def timer(self, **line):
        t = LapTimer(self.root)
        t.configure(LapLine(enabled=True, lat=LAT0, lon=LON0, **{'bearing': 0.0, 'min_lap_s': 30, **line}))
        return t

    def test_disabled_reports_no_values(self):
        t = LapTimer(self.root)
        self.assertEqual(t.update(fix(0, 0)), dict.fromkeys(LAP_CHANNELS))

    def test_line_crossings_count_laps_with_interpolated_time(self):
        t = self.timer()
        drive_north(t, 10_050, laps=3, lap_s=95)
        v = t.values()
        self.assertEqual(v['LapCount'], 3); self.assertEqual(v['CurrentLap'], 4)
        self.assertAlmostEqual(v['LapTime'] * 60, 95, places=2)
        self.assertAlmostEqual(v['BestLap'] * 60, 95, places=2)

    def test_wrong_direction_outside_width_and_short_lap_are_ignored(self):
        t = self.timer(width_m=20)
        for tt in range(0, 700, 100):  # southbound
            t.update(fix(tt, 3 - tt / 100.0))
        self.assertEqual(t.values()['CurrentLap'], 0)
        drive_north(t, 10_000, laps=1, lap_s=40, east_m=15)  # 15 m beside a 20 m wide line
        self.assertEqual(t.values()['CurrentLap'], 0)
        drive_north(t, 100_000, laps=1, lap_s=10)  # 10 s < 30 s minimum
        self.assertEqual(t.values()['LapCount'], 0); self.assertEqual(t.values()['CurrentLap'], 1)

    def test_jitter_on_the_line_never_adds_laps_until_the_car_leaves(self):
        t = self.timer(min_lap_s=5)
        drive_north(t, 10_000, laps=0, lap_s=60)
        self.assertEqual(t.values()['CurrentLap'], 1)
        for k in range(600):  # stopped on the line for 60 s, position wobbling +-1 m
            t.update(fix(20_000 + k * 100, 1.0 if k % 2 else -1.0, speed=0.5))
        self.assertEqual(t.values()['LapCount'], 0)
        drive_north(t, 120_000, laps=0, lap_s=60)  # leaves, comes round, crosses again
        self.assertEqual(t.values()['LapCount'], 1)

    def test_default_minimum_lap_is_short(self):
        self.assertEqual(LapLine().min_lap_s, 10)

    def test_poor_fix_or_gap_breaks_crossing(self):
        t = self.timer()
        t.update(fix(0, -1)); t.update(fix(100, 1, hacc=40))
        t.update(fix(1500, 2))
        self.assertEqual(t.values()['CurrentLap'], 0)
        t.update(fix(2000, -1)); t.update(fix(3200, 1))  # 1.2 s gap
        self.assertEqual(t.values()['CurrentLap'], 0)

    def test_repeated_itow_is_processed_once(self):
        t = self.timer()
        t.update(fix(0, -1))
        for _ in range(10):t.update(fix(0, -1))  # 100 Hz IMU rows reuse the GNSS solution
        t.update(fix(100, 1))
        self.assertEqual(t.values()['CurrentLap'], 1)

    def test_geofence_learns_direction_at_closest_approach(self):
        t = self.timer(bearing=None)
        for tt in range(0, 4100, 100):  # eastbound past the point, 4 m north of it
            t.update(fix(tt, 4, (tt - 2000) / 100.0, yaw=90.0))
        self.assertEqual(t.values()['CurrentLap'], 1)
        self.assertAlmostEqual(t.line.bearing, 90.0)
        self.assertEqual(t.state['lap_start_ms'], 1792800000 * 1000 + 2000)
        self.assertEqual(json.loads((self.root / 'lap.json').read_text())['line']['bearing'], 90.0)

    def test_state_survives_restart_and_reset_clears_it(self):
        t = self.timer()
        drive_north(t, 0, laps=2, lap_s=60)
        again = LapTimer(self.root)
        self.assertEqual(again.values()['LapCount'], 2)
        again.reset()
        self.assertEqual(LapTimer(self.root).values()['LapCount'], 0)

    def test_long_gap_restarts_running_lap_without_counting(self):
        t = self.timer(max_lap_s=600)
        drive_north(t, 0, laps=1, lap_s=60)
        drive_north(t, 60_000 + 3600_000, laps=0, lap_s=60)
        self.assertEqual(t.values()['LapCount'], 1)
        self.assertEqual(t.state['lap_start_ms'] % 10_000_000, (1792800000 * 1000 + 3660_000) % 10_000_000)

    def test_set_here_takes_heading_only_when_moving(self):
        t = LapTimer(self.root)
        t.set_here(fix(0, 0, speed=0.5, yaw=123))
        self.assertTrue(t.line.enabled); self.assertIsNone(t.line.bearing)
        t.set_here(fix(0, 0, speed=20, yaw=370 - 360))
        self.assertEqual(t.line.bearing, 10)
        with self.assertRaises(ValueError):t.set_here({'values': {'Lat': None, 'Lon': None}})

    def test_invalid_line(self):
        for data in ({'enabled': True}, {'min_lap_s': 100, 'max_lap_s': 50}, {'bearing': 360}):
            with self.assertRaises(ValueError):LapLine(**data)

    def test_corrupt_file_falls_back_safely(self):
        (self.root / 'lap.json').write_text('{bad')
        t = LapTimer(self.root)
        self.assertFalse(t.line.enabled); self.assertIsNotNone(t.error)


if __name__ == '__main__':
    unittest.main()
