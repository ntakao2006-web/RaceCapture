import json
import math
import tempfile
import unittest
from pathlib import Path
from lap import LapLine, LapTimer, EARTH_M_PER_DEG, line_code
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


def gate(north_m, east_m=0.0, bearing=0.0, width_m=30):
    return {'lat': LAT0 + north_m / EARTH_M_PER_DEG,
            'lon': LON0 + east_m / (EARTH_M_PER_DEG * math.cos(math.radians(LAT0))),
            'bearing': bearing, 'width_m': width_m}


def pass_north(timer, cross_ms, north_m, east_m=0.0):
    """Come from far south and cross northing `north_m` heading north at `cross_ms`."""
    timer.update(fix(cross_ms - 1000, north_m - 200, east_m))
    for t in range(cross_ms - 300, cross_ms + 400, 100):
        timer.update(fix(t, north_m + (t - cross_ms) / 100.0, east_m))


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

    def emc(self, **line):
        # Motegi-like layout: standing start 500 m before the control line, goal on a branch 300 m east.
        return self.timer(start=gate(-500), goal=gate(0, east_m=300), total_laps=7, **line)

    def test_eco_run_start_six_control_passes_and_goal_make_seven_laps(self):
        t = self.emc()
        pass_north(t, 5_000, 0)                     # driving to the grid over the control line: ignored
        self.assertEqual(t.values()['CurrentLap'], 0)
        pass_north(t, 60_000, -500)                 # start
        v = t.values(); self.assertEqual((v['CurrentLap'], v['LapsLeft']), (1, 7))
        for k in range(6):
            pass_north(t, 400_000 + k * 330_000, 0)
        v = t.values(); self.assertEqual((v['LapCount'], v['CurrentLap'], v['LapsLeft']), (6, 7, 1))
        self.assertAlmostEqual(t.state['laps'][0]['s'], 340.0)  # start -> first control pass is lap 1
        pass_north(t, 2_400_000, 0, east_m=300)     # goal branch
        v = t.values()
        self.assertEqual((v['LapCount'], v['CurrentLap'], v['LapsLeft']), (7, 7, 0))
        self.assertIsNone(v['ElapsedTime']); self.assertTrue(t.state['finished'])
        self.assertAlmostEqual(v['RaceTime'] * 60, 2_340.0)
        self.assertAlmostEqual(t.state['laps'][-1]['s'], 2_400 - 2_050)
        pass_north(t, 2_800_000, 0)                 # cool-down lap after the goal: nothing changes
        self.assertEqual(t.values()['LapCount'], 7)
        t.reset(); self.assertFalse(t.state['finished']); self.assertEqual(t.values()['CurrentLap'], 0)

    def test_goal_is_ignored_before_the_final_lap(self):
        t = self.emc()
        pass_north(t, 0, -500); pass_north(t, 300_000, 0)
        pass_north(t, 600_000, 0, east_m=300)       # goal drawn too close to the circuit: lap 2 only
        self.assertFalse(t.state['finished']); self.assertEqual(t.values()['LapCount'], 1)
        t.line = t.line.model_copy(update={'total_laps': None})
        pass_north(t, 900_000, 0, east_m=300)       # without a lap count the goal is always taken
        self.assertTrue(t.state['finished'])

    def test_goal_right_after_control_pass_does_not_add_a_lap(self):
        t = self.timer(start=gate(-500), goal=gate(0, east_m=300))  # no lap count: goal any time
        pass_north(t, 0, -500); pass_north(t, 300_000, 0)
        pass_north(t, 303_000, 0, east_m=300)
        self.assertEqual(t.values()['LapCount'], 1); self.assertTrue(t.state['finished'])

    def test_standing_start_learns_direction_and_last_departure_wins(self):
        t = self.timer(start={**gate(0), 'bearing': None}, min_lap_s=30)
        for k in range(300):  # waiting on the grid, wobbling across the line
            t.update(fix(k * 100, 0.8 if k % 2 else -0.8, speed=0.3, yaw=200.0))
        for k in range(1, 40):  # flag: drive off north
            t.update(fix(30_000 + k * 100, 0.8 + k * 0.5, speed=15.0, yaw=0.0))
        self.assertAlmostEqual(t.line.start.bearing, 0.0)
        self.assertGreaterEqual(t.state['race_start_ms'] % 100_000, 29_800)  # the last forward crossing, not an early wobble
        self.assertEqual(t.values()['CurrentLap'], 1)
        self.assertEqual(json.loads((self.root / 'lap.json').read_text())['line']['start']['bearing'], 0.0)

    def test_learned_headings_cannot_be_taught_the_wrong_way_before_the_race(self):
        # 2026-10-24: lines registered without headings (learned on a pass), as at the course walk.
        def pass_south(timer, cross_ms, north_m):
            timer.update(fix(cross_ms - 1000, north_m + 200, yaw=180.0))
            for t in range(cross_ms - 300, cross_ms + 400, 100):
                timer.update(fix(t, north_m - (t - cross_ms) / 100.0, yaw=180.0))
            timer.update(fix(cross_ms + 1000, north_m - 40, yaw=180.0))  # out of the line's circle
        def pass_north_out(timer, cross_ms, north_m):
            pass_north(timer, cross_ms, north_m)
            timer.update(fix(cross_ms + 1000, north_m + 40))
        unknown = lambda g: {**g, 'bearing': None}
        t = self.timer(bearing=None, start=unknown(gate(-500)), goal=unknown(gate(0, east_m=300)), total_laps=3)
        pass_south(t, 5_000, 0)          # to the grid the wrong way over the control line
        self.assertIsNone(t.line.bearing)  # A: no heading from a pass that counts for nothing
        pass_south(t, 20_000, -500)      # ... and over the start line the wrong way
        self.assertAlmostEqual(t.line.start.bearing, 180.0)
        pass_north_out(t, 60_000, -500)  # B: the standing start takes the heading afresh
        self.assertAlmostEqual(t.line.start.bearing, 0.0)
        self.assertEqual(t.state['race_start_ms'] % 1_000_000, 60_000)
        pass_north_out(t, 400_000, 0)    # the first control pass of the race teaches it and counts lap 1
        self.assertAlmostEqual(t.line.bearing, 0.0)
        self.assertEqual(t.values()['LapCount'], 1)
        self.assertEqual(sorted(t.state['learned']), ['control', 'start'])
        t.reset()                        # C: the reset forgets learned headings
        self.assertIsNone(t.line.bearing); self.assertIsNone(t.line.start.bearing)
        self.assertEqual(t.state['learned'], [])
        typed = self.emc()               # typed-in headings stay through a reset
        pass_north(typed, 60_000, -500); typed.reset()
        self.assertEqual((typed.line.bearing, typed.line.start.bearing), (0.0, 0.0))

    def test_restart_before_first_lap_resets_the_clock(self):
        t = self.emc()
        pass_north(t, 10_000, -500); pass_north(t, 200_000, -500)
        self.assertEqual(t.state['race_start_ms'] % 1_000_000, 200_000)
        pass_north(t, 600_000, 0); pass_north(t, 900_000, -500)  # after lap 1 the start line is ignored
        self.assertEqual(t.state['race_start_ms'] % 1_000_000, 200_000)

    def test_set_here_for_start_and_goal(self):
        t = LapTimer(self.root)
        t.set_here(fix(0, 0, speed=20, yaw=0), target='control')
        t.set_here(fix(0, -500, speed=0, yaw=0), width_m=20, target='start')
        t.set_here(fix(0, 0, 300, speed=10, yaw=90), target='goal')
        self.assertIsNone(t.line.start.bearing); self.assertEqual(t.line.start.width_m, 20)
        self.assertEqual(t.line.goal.bearing, 90)
        with self.assertRaises(ValueError): t.set_here(fix(0, 0), target='pit')

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

    def test_set_here_standing_averages_the_last_three_seconds(self):
        t = LapTimer(self.root)  # course walk: no line yet
        for k in range(40):  # 4 s on foot at the line, jittering +-1 m around 5 m north
            last = fix(k * 100, 5.0 + (1.0 if k % 2 else -1.0), speed=0.3)
            t.update(last)
        t.set_here(last, target='control')
        north = (t.line.lat - LAT0) * EARTH_M_PER_DEG
        self.assertAlmostEqual(north, 5.0, delta=0.1)  # the last fix alone is 1 m off
        self.assertEqual(t.last_here['fixes'], 31)
        self.assertLessEqual(t.last_here['spread_m'], 1.1)
        self.assertEqual(t.public()['here']['target'], 'control')

    def test_set_here_moving_uses_the_current_fix(self):
        t = LapTimer(self.root)
        for k in range(40):  # driving north at 1 m per 100 ms: 30 m in the window
            last = fix(k * 100, k * 1.0, speed=36, yaw=0)
            t.update(last)
        t.set_here(last, target='start')
        self.assertAlmostEqual((t.line.start.lat - LAT0) * EARTH_M_PER_DEG, 39.0, delta=0.01)
        self.assertEqual(t.last_here['fixes'], 1)
        self.assertEqual(t.line.start.bearing, 0.0)

    def test_invalid_line(self):
        for data in ({'enabled': True}, {'min_lap_s': 100, 'max_lap_s': 50}, {'bearing': 360}):
            with self.assertRaises(ValueError):LapLine(**data)

    def test_corrupt_file_falls_back_safely(self):
        (self.root / 'lap.json').write_text('{bad')
        t = LapTimer(self.root)
        self.assertFalse(t.line.enabled); self.assertIsNotNone(t.error)

    def test_pit_lane_passes_mark_the_laps_on_either_side(self):
        # North-bound line: the pit lane 11 m to the right (east), at most 80 km/h there.
        t = self.timer(width_m=50, pit_offset_m=11.0, pit_max_kmh=80.0)
        passes = [(10_000, 0.0, 150.0), (110_000, -4.0, 150.0), (205_000, 10.0, 55.0),
                  (500_000, 1.0, 150.0), (600_000, 0.5, 150.0), (698_000, 2.0, 150.0)]
        for cross, east, kmh in passes:
            t.update(fix(cross - 1000, -200.0, east, speed=kmh))
            for tt in range(cross - 300, cross + 400, 100):
                t.update(fix(tt, (tt - cross) / 100.0, east, speed=kmh))
        laps = t.state['laps']
        self.assertEqual([lap['pit'] for lap in laps], [False, True, True, False, False])
        self.assertEqual([p['pit'] for p in t.state['passes']], [False, False, True, False, False, False])
        self.assertAlmostEqual(t.state['passes'][2]['offset_m'], 10.0, places=0)
        self.assertEqual(t.state['passes'][1]['offset_m'], -4.0)
        v = t.values()
        self.assertIs(v['LastLapPit'], False); self.assertIs(v['LapStartPit'], False)
        self.assertAlmostEqual(v['LapDiffS'], -2.0, places=2)  # 98 s after 100 s

    def test_pit_lap_has_no_difference_and_fast_passes_are_never_pit(self):
        t = self.timer(width_m=50, pit_offset_m=11.0, pit_max_kmh=80.0)
        for k, (east, kmh) in enumerate([(0.0, 150.0), (0.0, 150.0), (11.0, 50.0)]):
            cross = 10_000 + k * 100_000
            t.update(fix(cross - 1000, -200.0, east, speed=kmh))
            for tt in range(cross - 300, cross + 400, 100):
                t.update(fix(tt, (tt - cross) / 100.0, east, speed=kmh))
        v = t.values()
        self.assertIs(v['LastLapPit'], True); self.assertIsNone(v['LapDiffS'])
        self.assertIs(v['LapStartPit'], True)  # the out lap: it began in the pit lane
        self.assertFalse(t.is_pit(11.0, 150.0))  # the right edge of the straight at full speed
        self.assertFalse(t.is_pit(4.0, 40.0))    # slow, but on the track side of halfway
        self.assertTrue(t.is_pit(6.0, 40.0))
        t.configure(t.line.model_copy(update={'pit_offset_m': None}))
        self.assertFalse(t.is_pit(11.0, 40.0))   # no pit lane set: nothing is a pit pass

    def test_lap_difference_waits_for_two_laps(self):
        t = self.timer()
        drive_north(t, 10_050, laps=1, lap_s=95)
        self.assertIsNone(t.values()['LapDiffS']); self.assertIs(t.values()['LastLapPit'], False)
        drive_north(t, 10_050 + 95_000, laps=1, lap_s=97)
        self.assertAlmostEqual(t.values()['LapDiffS'], 2.0, places=2)


class SectorTests(unittest.TestCase):
    """Sector lines (2026-11-07, SUGO): the course is modelled as a run north through the control
    line (0 m) and the two sector lines (300 m, 600 m), then back south of the control line."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def timer(self, **line):
        t = LapTimer(self.root)
        t.configure(LapLine(enabled=True, lat=LAT0, lon=LON0, bearing=0.0, min_lap_s=30,
                            sectors=[gate(300), gate(600)], **line))
        return t

    @staticmethod
    def lap(t, start_ms, s1, s2, s3, skip=()):
        """Control pass at start_ms, then the sector lines after s1 and s1+s2 seconds; the next
        control pass is at start_ms + s1+s2+s3 (made by the next call or by `close`)."""
        pass_north(t, start_ms, 0)
        if 1 not in skip:
            pass_north(t, start_ms + int(s1 * 1000), 300)
        if 2 not in skip:
            pass_north(t, start_ms + int((s1 + s2) * 1000), 600)
        return start_ms + int((s1 + s2 + s3) * 1000)

    def test_sector_times_and_difference_from_the_best(self):
        t = self.timer()
        self.assertIsNone(t.values()['Sector'])  # before the first control pass (the out lap)
        nxt = self.lap(t, 10_000, 30, 40, 30)
        v = t.values()
        self.assertEqual(v['Sector'], 3); self.assertEqual(v['LastSector'], 2)
        self.assertAlmostEqual(v['SectorTime'] * 60, 40, places=2); self.assertIsNone(v['SectorDiffS'])
        nxt = self.lap(t, nxt, 28, 41, 30)  # the control pass at the start of this call ends lap 1
        lap1 = t.state['laps'][0]
        self.assertEqual(lap1['sectors'], [30.0, 40.0, 30.0]); self.assertAlmostEqual(lap1['s'], 100.0, places=2)
        v = t.values()
        self.assertEqual(v['Sector'], 3); self.assertEqual(v['LastSector'], 2)
        self.assertAlmostEqual(v['SectorDiffS'], 1.0, places=2)  # 41 s against the best 40 s
        pass_north(t, nxt, 0)
        v = t.values()
        self.assertEqual(v['Sector'], 1); self.assertEqual(v['LastSector'], 3)
        self.assertAlmostEqual(v['SectorTime'] * 60, 30, places=2); self.assertAlmostEqual(v['SectorDiffS'], 0.0, places=2)
        self.assertEqual(t.state['laps'][1]['sectors'], [28.0, 41.0, 30.0])
        self.assertEqual([round(b, 3) for b in t.state['sector_best']], [28.0, 40.0, 30.0])
        # kept across a restart of the container
        again = LapTimer(self.root)
        self.assertEqual(again.state['laps'][1]['sectors'], [28.0, 41.0, 30.0])

    def test_a_missed_sector_line_leaves_that_and_the_next_sector_without_time(self):
        t = self.timer()
        nxt = self.lap(t, 10_000, 30, 40, 30, skip=(1,))
        pass_north(t, nxt, 0)
        self.assertEqual(t.state['laps'][0]['sectors'], [None, None, 30.0])
        self.assertEqual(t.values()['LastSector'], 3)

    def test_sector_line_passed_again_on_the_same_lap_counts_once(self):
        t = self.timer()
        self.lap(t, 10_000, 30, 40, 30, skip=(2,))
        pass_north(t, 10_000 + 35_000, 300)  # the 300 m line again (e.g. a spin and back across)
        self.assertEqual(t.values()['Sector'], 2)
        self.assertAlmostEqual(t.values()['SectorTime'] * 60, 30, places=2)

    def test_pit_sectors_have_no_difference_and_are_never_best(self):
        t = self.timer(pit_offset_m=11.0, pit_max_kmh=80.0)
        nxt = self.lap(t, 10_000, 30, 40, 30)
        nxt = self.lap(t, nxt, 30, 40, 30)
        # an in lap: the control pass that ends it is in the pit lane (11 m right of travel = east)
        t.update(fix(nxt - 1000, -200, 11.0, speed=50))
        for tt in range(nxt - 300, nxt + 400, 100):
            t.update(fix(tt, (tt - nxt) / 100.0, 11.0, speed=50))
        self.assertIs(t.state['laps'][-1]['pit'], True)
        self.assertEqual(t.values()['LastSector'], 3); self.assertIsNone(t.values()['SectorDiffS'])
        pass_north(t, nxt + 50_000, 300)  # the out lap's first sector, 50 s from the pit lane
        self.assertIsNone(t.values()['SectorDiffS'])
        self.assertAlmostEqual(t.state['sector_best'][0], 30.0, places=2)

    def test_a_sector_line_needs_its_bearing_and_changing_them_forgets_the_sector_times(self):
        with self.assertRaises(ValueError):
            LapLine(enabled=True, lat=LAT0, lon=LON0, sectors=[{'lat': LAT0, 'lon': LON0}])
        t = self.timer()
        nxt = self.lap(t, 10_000, 30, 40, 30)
        pass_north(t, nxt, 0)
        t.configure(t.line.model_copy(update={'sectors': [LapLine.model_validate({'sectors': [gate(400)]}).sectors[0]]}))
        self.assertEqual(t.state['sector_best'], []); self.assertIsNone(t.values()['LastSector'])
        self.assertEqual(t.state['count'], 1)  # the laps themselves stay

    def test_no_sector_lines_no_sector_values(self):
        t = LapTimer(self.root)
        t.configure(LapLine(enabled=True, lat=LAT0, lon=LON0, bearing=0.0, min_lap_s=30))
        drive_north(t, 10_050, laps=2, lap_s=95)
        v = t.values()
        self.assertIsNone(v['Sector']); self.assertIsNone(v['SectorTime'])
        self.assertNotIn('sectors', t.state['laps'][0])


class LineCodeTest(unittest.TestCase):
    """The QR text the Android loggers read (android-logger LineCodeTest uses the same strings)."""

    def test_format_and_id(self):
        line = LapLine.model_validate({'enabled': True, 'lat': 36.5328, 'lon': 140.226322, 'bearing': 150.0, 'width_m': 40,
                                       'start': {'lat': 36.53073, 'lon': 140.228057, 'width_m': 30}, 'set_at': '2026-10-24T06:40+09:00'})
        text, code = line_code(line)
        lines = 'c=36.5328000,140.2263220,150.0,40|s=36.5307300,140.2280570,-,30|g=-'
        self.assertEqual(text, f'ECOLINES1|{lines}|at=2026-10-24T06:40+09:00|src=Ver.2|id={code}')
        import hashlib
        self.assertEqual(code, hashlib.sha1(lines.encode()).hexdigest()[:4].upper())
        self.assertEqual(code, '1600')  # also fixed in android-logger LineCodeTest

    def test_changing_a_line_stamps_gnss_time(self):
        with tempfile.TemporaryDirectory() as root:
            t = LapTimer(root)
            t.update(fix(0, 0.0))  # 2026-10-24T00:00:00Z = 09:00 JST
            t.configure(LapLine(enabled=True, lat=LAT0, lon=LON0))
            self.assertEqual(t.line.set_at, '2026-10-24T09:00+09:00')
            same = t.line.model_copy(update={'min_lap_s': 20})
            t.configure(same.model_copy(update={'set_at': None}))
            self.assertIsNone(t.line.set_at)  # only a change of the lines themselves is stamped


if __name__ == '__main__':
    unittest.main()
