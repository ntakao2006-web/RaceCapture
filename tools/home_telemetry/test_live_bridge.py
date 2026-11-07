"""Tests for live_bridge.Pace.outlook (2026-10-25, ER-13).

  python -m unittest test_live_bridge     (needs websockets, like live_bridge itself)

The race replay runs only where drive_logs/ is (the race records hold positions and stay out of
the repository): the Super Cub finished 16:27.56 against the 16:27.36 limit on 2026-10-25, and
the pit's clock has to say "over the limit" in lap 2, not at the goal.
"""
import json
import os
import unittest

import live_bridge

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RACE = os.path.join(ROOT, 'drive_logs', '20261025_race_server', 'super-cub', '20261025-050404Z.jsonl')
LIMIT = 987.36


def row(t_s, speed, race_s, lap_s, count, left, lap_time=None):
    """One point as the app sends it (times in minutes), t_s from an arbitrary start."""
    f = {'Speed': speed, 'RaceTime': race_s / 60, 'LapCount': count, 'LapsLeft': left,
         'TimeLimit': LIMIT, 'Margin': 30.0, 'CurrentLap': count + 1}
    if lap_s is not None:
        f['ElapsedTime'] = lap_s / 60
    if lap_time is not None:
        f['LapTime'] = lap_time / 60
    return 1_800_000_000_000 + int(t_s * 1000), f


class OutlookTest(unittest.TestCase):
    def test_even_pace_keeps_the_margin(self):
        """At the pace that covers the regulation distance 30 s inside the limit, the outlook is +30 s."""
        p = live_bridge.Pace()
        v = 6856.72 / (LIMIT - 30) * 3.6
        for t in range(0, 121):
            p.add(*row(t, v, t, t, 0, 3))
        o = p.clock()['outlook']
        self.assertAlmostEqual(o['spare'], 30.0, delta=0.2)
        self.assertLess(o['min_kmh'], v)
        self.assertFalse(o['from_last'])

    def test_nothing_early_in_lap_1_or_without_a_limit(self):
        p = live_bridge.Pace()
        for t in range(0, 20):
            p.add(*row(t, 25.0, t, t, 0, 3))
        self.assertIsNone(p.clock()['outlook'])   # lap 1, under 30 s: no lap before to go by
        q = live_bridge.Pace()
        for t in range(0, 60):
            ts, f = row(t, 25.0, t, t, 0, 3)
            del f['TimeLimit']
            q.add(ts, f)
        self.assertIsNone(q.clock()['outlook'])

    def test_unknown_lap_count_has_no_distance(self):
        p = live_bridge.Pace()
        for t in range(0, 60):
            p.add(*row(t, 25.0, t, t, 0, 5))
        self.assertIsNone(p.clock()['outlook'])

    def test_lap_split_follows_the_app(self):
        """--lap-split 293.2,2.3 (Motegi, reference 0115) gives the app's lap distances (OutlookTest)."""
        p = live_bridge.Pace((293.2, 2.3))
        laps = [p.lap_m(k, 3) for k in range(3)]
        self.assertAlmostEqual(sum(laps), 6856.72, places=6)
        self.assertAlmostEqual(laps[1] - laps[0], 293.2, places=6)
        self.assertAlmostEqual(laps[2] - laps[1], 2.3, places=6)
        self.assertIsNone(live_bridge.Pace().lap_m(0, 3))

    def replay(self, split):
        f = live_bridge.Follower(RACE, from_start=True)
        p = live_bridge.Pace(split)
        seen = []   # (race seconds, lap count, outlook)
        newest = 0
        for ts, fields in f.poll():
            if ts <= newest:      # Bridge.only_new
                continue
            newest = ts
            p.add(ts, fields)
            c = p.clock()
            if c['start'] is not None and c['end'] is None and c['outlook'] is not None:
                seen.append(((ts - c['start']) / 1000, c['count'], c['outlook']))
        self.assertEqual(round(p.clock()['end'] - p.clock()['start']), 987564)
        first = next(s for s, n, o in seen if n >= 1 and o['spare'] < 0)
        self.assertTrue(289 <= first <= 420, first)
        # From then on to the goal it reads over the limit: the alarm stays on for 10 minutes.
        self.assertTrue(all(o['spare'] < 0 for s, n, o in seen if s >= first))
        return seen

    @unittest.skipUnless(os.path.isfile(RACE), 'race record not here (drive_logs/)')
    def test_super_cub_race_with_the_lap_split(self):
        seen = self.replay((293.2, 2.3))
        before_goal = [o for s, n, o in seen if s <= 987.3]
        self.assertAlmostEqual(before_goal[-1]['spare'], -0.2, delta=1.5)   # it ended 0.2 s over
        lap3 = next(o for s, n, o in seen if n == 2)
        self.assertAlmostEqual(lap3['min_kmh'], 24.8, delta=0.1)          # the app: 24.77

    @unittest.skipUnless(os.path.isfile(RACE), 'race record not here (drive_logs/)')
    def test_super_cub_race_without_the_lap_split_errs_late(self):
        seen = self.replay(None)
        before_goal = [o for s, n, o in seen if s <= 987.3]
        self.assertTrue(-6 < before_goal[-1]['spare'] < -2)   # GNSS distance runs short: a few seconds late


def circuit_row(t_s, race_s, lap_s, count, speed=150.0, oil=100.0, water=90.0, lap_time=None, best=None):
    """One Ver.2 row at a circuit (SUGO: one control line, no limit, no lap count)."""
    f = {'Speed': speed, 'OilTemp': oil, 'WaterTemp': water, 'RaceTime': race_s / 60,
         'ElapsedTime': lap_s / 60, 'LapCount': count, 'CurrentLap': count + 1}
    if lap_time is not None:
        f['LapTime'] = lap_time / 60
    if best is not None:
        f['BestLap'] = best / 60
    return 1_800_000_000_000 + int(t_s * 1000), f


class TimingSheetTest(unittest.TestCase):
    """The circuit timing sheet (laps.html, 2026-11-04): each pass carries its lap's highest
    speed and temperatures, and laps lost over LTE are marked, not invented."""

    def drive(self, p, laps, lap_s=100.0, every=0.8, t0=0.0, hot=None):
        """`laps` laps at 1.25 rows/s, the oil `hot` °C hotter in the middle of lap index 1."""
        t, n = t0, 0
        while t < t0 + laps * lap_s:
            k = int((t - t0) // lap_s)
            into = t - t0 - k * lap_s
            oil = 100.0 + (hot if hot and k == 1 and 40 <= into < 41 else 0)
            p.add(*circuit_row(t, t - t0, into, k, speed=120 + into / 2, oil=oil,
                               lap_time=lap_s if k else None, best=lap_s if k else None))
            n += 1
            t = t0 + n * every
        return t

    def test_peaks_go_with_their_lap(self):
        p = live_bridge.Pace()
        self.drive(p, 4, hot=12)
        passes = [q for q in p.clock()['passes'] if q['k'] == 'control']
        self.assertEqual([q['n'] for q in passes], [1, 2, 3])
        self.assertEqual([q['oil'] for q in passes], [100.0, 112.0, 100.0])
        # The top speed is the last row before the line, not the first of the next lap
        self.assertTrue(all(169 <= q['vmax'] <= 170 for q in passes), passes)
        self.assertTrue(all(abs(q['s'] - 100.0) < 0.01 for q in passes))
        self.assertNotIn('e', passes[0])
        c = p.clock()
        self.assertEqual(c['best'], 100.0)
        self.assertEqual(c['oil'], 100.0)
        self.assertEqual(c['water'], 90.0)

    def test_a_lost_lap_is_marked(self):
        """LTE away for a lap and a half: LapCount jumps 1 -> 3. Lap 2 has no time of its own."""
        p = live_bridge.Pace()
        for t in range(0, 140):       # lap 1, and into lap 2
            p.add(*circuit_row(t, t, t % 100, t // 100, lap_time=100.0 if t >= 100 else None))
        for t in range(301, 320):     # back in lap 4: laps 2 and 3 done, the last took 101 s
            p.add(*circuit_row(t, t, t - 300, 3, lap_time=101.0))
        passes = [q for q in p.clock()['passes'] if q['k'] == 'control']
        self.assertEqual([q['n'] for q in passes], [1, 2, 3])
        self.assertEqual(passes[1].get('e'), 1)
        self.assertNotIn('oil', passes[1])
        self.assertNotIn('e', passes[2])
        self.assertNotIn('oil', passes[2])   # the rows of the span belong to laps 2 and 3
        self.assertEqual(passes[2]['s'], 101.0)

    def sector_drive(self, p, laps, lose=()):
        """Laps of 100 s with sector lines at 30, 60 and 80 s, the values as lap.py sends them;
        rows at times in `lose` (s) do not arrive."""
        ends = (30.0, 60.0, 80.0)
        for n in range(int(laps * 100 / 0.8)):
            t = n * 0.8
            k, into = int(t // 100), t % 100
            ts, f = circuit_row(t, t, into, k, lap_time=100.0 if k else None)
            done = sum(into >= e for e in ends)
            f['Sector'] = done + 1
            if done:
                f.update(LastSector=done, SectorTime=(ends[done - 1] - (ends[done - 2] if done > 1 else 0)) / 60)
            elif k:
                f.update(LastSector=4, SectorTime=20.0 / 60)
            if not any(a <= t < b for a, b in lose):
                p.add(ts, f)

    def test_sector_times_go_with_their_lap(self):
        p = live_bridge.Pace()
        self.sector_drive(p, 3.5)
        passes = [q for q in p.clock()['passes'] if q['k'] == 'control']
        self.assertEqual([q['n'] for q in passes], [1, 2, 3])
        self.assertEqual([q['x'] for q in passes], [[30.0, 30.0, 20.0, 20.0]] * 3)

    def test_a_sector_lost_over_lte_is_left_out(self):
        """No rows from 25 s to 65 s of lap 2: S1 is caught later (its value stays), S2 is not."""
        p = live_bridge.Pace()
        self.sector_drive(p, 2.5, lose=[(125.0, 165.0)])
        passes = [q for q in p.clock()['passes'] if q['k'] == 'control']
        self.assertEqual(passes[1]['x'], [None, 30.0, 20.0, 20.0])   # S2's own value had been replaced by S3's
        self.assertEqual(passes[0]['x'], [30.0, 30.0, 20.0, 20.0])

    def test_no_sector_lines_send_no_sectors(self):
        p = live_bridge.Pace()
        self.drive(p, 3)
        self.assertFalse(any('x' in q for q in p.clock()['passes']))

    def test_live_temperatures_go_stale(self):
        p = live_bridge.Pace()
        p.add(*circuit_row(0, 0, 0, 0))
        ts, f = circuit_row(11, 11, 11, 0)
        del f['OilTemp']
        p.add(ts, f)
        self.assertIsNone(p.clock()['oil'])
        self.assertEqual(p.clock()['water'], 90.0)

    def test_a_lap_reset_starts_a_new_sheet(self):
        p = live_bridge.Pace()
        self.drive(p, 3)
        self.assertEqual(len(p.clock()['passes']), 3)   # start and 2 laps
        self.drive(p, 2, t0=1000.0)                     # RaceTime back to 0: the final after qualifying
        passes = p.clock()['passes']
        self.assertEqual([q['k'] for q in passes], ['start', 'control'])

    def test_passes_are_sent_only_when_they_change(self):
        class Args:
            db = ':memory:'
            grafana_token_file = os.devnull + '-none'
        bridge = live_bridge.Bridge(Args())
        pace = bridge.paces['sugo'] = live_bridge.Pace()
        ws = object()
        self.drive(pace, 2)
        first = json.loads(bridge.laps_msg(ws, 'sugo'))['laps']
        self.assertEqual(len(first['passes']), 2)   # the start and lap 1
        again = json.loads(bridge.laps_msg(ws, 'sugo'))['laps']
        self.assertNotIn('passes', again)
        self.assertEqual(again['lap'], 2)
        self.assertIn('passes', json.loads(bridge.laps_msg(object(), 'sugo'))['laps'])   # another page
        pace.add(*circuit_row(200.8, 200.8, 0.8, 2, lap_time=100.0))
        self.assertEqual(len(json.loads(bridge.laps_msg(ws, 'sugo'))['laps']['passes']), 3)


if __name__ == '__main__':
    unittest.main()
