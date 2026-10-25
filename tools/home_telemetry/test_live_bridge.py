"""Tests for live_bridge.Pace.outlook (2026-10-25, ER-13).

  python -m unittest test_live_bridge     (needs websockets, like live_bridge itself)

The race replay runs only where drive_logs/ is (the race records hold positions and stay out of
the repository): the Super Cub finished 16:27.56 against the 16:27.36 limit on 2026-10-25, and
the pit's clock has to say "over the limit" in lap 2, not at the goal.
"""
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


if __name__ == '__main__':
    unittest.main()
