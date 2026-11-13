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


class HomeTest(unittest.TestCase):
    """The cover page (home.html, 2026-11-13, SP-6-1): what it is sent and where it is served."""

    def bridge(self):
        import tempfile
        import types
        folder = tempfile.mkdtemp()
        return live_bridge.Bridge(types.SimpleNamespace(db=os.path.join(folder, 'map.db'), lap_split=None,
                                                        grafana_token_file=os.path.join(folder, 'none')))

    def test_message_has_now_values_but_no_line_passes(self):
        b = self.bridge()
        pace = b.paces['r'] = live_bridge.Pace()
        for t in range(0, 30):
            ts, f = row(t, 88.4, t, t, 2, 5, lap_time=110.0)
            pace.add(ts, {**f, 'GPSSats': 19, 'OilTemp': 104.2, 'BestLap': 109.5 / 60})
        msg = json.loads(b.home_msg('r'))
        home = msg['home']
        self.assertNotIn('passes', home)          # the cover shows only "now"
        self.assertEqual(home['speed'], 88.4)
        self.assertEqual(home['sats'], 19)
        self.assertEqual(home['oil'], 104.2)
        self.assertEqual(home['count'], 2)
        self.assertAlmostEqual(home['last_lap'], 110.0)
        self.assertEqual(home['data_t'], pace.last_ts)   # the page tells how old the values are from this
        self.assertIsInstance(msg['now'], int)
        self.assertIn('passes', pace.clock())      # the clock and the timing sheet still get them

    def test_room_without_data(self):
        self.assertIsNone(json.loads(self.bridge().home_msg('nobody'))['home'])

    def test_served_at_home_and_at_the_root(self):
        import types
        b = self.bridge()
        for path in ('/home?room=x', '/home/', '/?room=x', '/'):
            response = b.http(None, types.SimpleNamespace(path=path))
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('EcoLogger ピット'.encode(), response.body, path)
        self.assertEqual(b.http(None, types.SimpleNamespace(path='/ws?room=x&kind=home')), None)

    def test_page_signs_like_the_logger(self):
        """home.html builds the signed text the same way as remote_command.payload (id|t|op|arg as
        compact JSON): the page says so in its source, and a null or integer arg reads the same in
        JSON.stringify and json.dumps."""
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'EcoCapture-Web'))
        import remote_command
        with open(os.path.join(os.path.dirname(__file__), 'home.html'), encoding='utf-8') as f:
            page = f.read()
        self.assertIn("`${id}|${t}|${op}|${JSON.stringify(arg === undefined ? null : arg)}`", page)
        self.assertEqual(remote_command.payload('ab12', 5, 'status', None), b'ab12|5|status|null')
        self.assertEqual(remote_command.payload('ab12', 5, 'lap_count', 12), b'ab12|5|lap_count|12')
        for op in remote_command.OPS:
            self.assertIn(f"{op}:", page)   # every operation the logger takes has a label on the page


class LapResetTest(unittest.TestCase):
    """Laps set back to 0 on the logger (2026-11-13, SP-6-1): the run before is forgotten, as the
    logger forgets it (lap.py LapTimer.reset: count 0, no last or best lap, no race clock). What a
    real run also does -- rows lost, the same values for a while, a logger restarting, a count
    corrected by hand -- must not."""

    def run_before(self):
        """Into lap 4 (t = 0..320 s), laps of 100 s, the best 99.5 s."""
        p = live_bridge.Pace()
        for t in range(0, 321):
            p.add(*circuit_row(t, t, t % 100, t // 100, lap_time=100.0 if t >= 100 else None,
                               best=99.5 if t >= 100 else None))
        c = p.clock()
        self.assertEqual((c['count'], c['last_lap'], c['best'], len(c['passes'])), (3, 100.0, 99.5, 4))
        return p

    @staticmethod
    def reset_row(t_s):
        """As the logger sends it after the reset: only the count, no times."""
        return 1_800_000_000_000 + int(t_s * 1000), {'Speed': 0.0, 'OilTemp': 95.0, 'WaterTemp': 88.0,
                                                    'LapCount': 0, 'CurrentLap': 0}

    def test_reset_forgets_the_run_before(self):
        p = self.run_before()
        p.add(*self.reset_row(321))
        c = p.clock()
        self.assertEqual(c['count'], 0)
        self.assertIsNone(c['last_lap'])
        self.assertIsNone(c['best'])        # the logger forgets its best lap too
        self.assertEqual(c['passes'], [])
        self.assertIsNone(c['start'])
        self.assertEqual(c['oil'], 95.0)    # what is being measured now stays
        self.assertNotIn('LastLapAvgSpeed', p.add(*self.reset_row(322)))
        # The next run starts a new sheet and takes its own times
        for t in range(400, 520):
            p.add(*circuit_row(t, t - 400, (t - 400) % 100, (t - 400) // 100,
                               lap_time=101.0 if t >= 500 else None, best=101.0 if t >= 500 else None))
        c = p.clock()
        self.assertEqual([q['k'] for q in c['passes']], ['start', 'control'])
        self.assertEqual((c['count'], c['last_lap'], c['best']), (1, 101.0, 101.0))

    def test_the_cover_and_the_sheet_are_told(self):
        import tempfile
        import types
        folder = tempfile.mkdtemp()
        b = live_bridge.Bridge(types.SimpleNamespace(db=os.path.join(folder, 'map.db'), lap_split=None,
                                                     grafana_token_file=os.path.join(folder, 'none')))
        pace = b.paces['r'] = self.run_before()
        ws = object()
        self.assertEqual(len(json.loads(b.laps_msg(ws, 'r'))['laps']['passes']), 4)
        pace.add(*self.reset_row(321))
        home = json.loads(b.home_msg('r'))['home']
        self.assertEqual((home['count'], home['last_lap'], home['best']), (0, None, None))
        self.assertEqual(json.loads(b.laps_msg(ws, 'r'))['laps']['passes'], [])   # sent again, empty

    def kept(self, p):
        c = p.clock()
        self.assertEqual((c['last_lap'], c['best']), (100.0, 99.5))
        return c

    def test_lost_rows_and_the_same_values_keep_it(self):
        p = self.run_before()
        for t in range(350, 380):      # 30 s without a row, then the same lap going on
            p.add(*circuit_row(t, t, t - 300, 3, lap_time=100.0, best=99.5))
        self.assertEqual(len(self.kept(p)['passes']), 4)

    def test_a_restarting_logger_keeps_it(self):
        """No lap values for a while (the lap line not read yet), then the same count again."""
        p = self.run_before()
        for t in range(321, 400):
            p.add(1_800_000_000_000 + t * 1000, {'Speed': 0.0, 'OilTemp': 95.0})
        self.kept(p)
        for t in range(400, 420):
            p.add(*circuit_row(t, t, t - 300, 3, lap_time=100.0, best=99.5))
        self.assertEqual(self.kept(p)['count'], 3)

    def test_a_count_corrected_by_hand_keeps_it(self):
        """set_count from the pit, also to 0: the logger keeps its lap times and sends them on."""
        for count in (2, 0):
            p = self.run_before()
            for t in range(321, 330):
                p.add(*circuit_row(t, t, t - 300, count, lap_time=100.0, best=99.5))
            self.assertEqual(self.kept(p)['count'], count)

    def test_before_the_first_lap_nothing_is_dropped(self):
        """Count 0 without times is every row before the first pass: not a reset."""
        p = live_bridge.Pace()
        for t in range(0, 50):
            p.add(*circuit_row(t, t, t, 0))
        c = p.clock()
        self.assertIsNotNone(c['start'])
        self.assertEqual([q['k'] for q in c['passes']], ['start'])


class FeedTest(unittest.TestCase):
    """How old the newest rows are, for the map and G-G pages (2026-11-13, SP-6-2)."""

    def bridge(self, folder):
        import types
        return live_bridge.Bridge(types.SimpleNamespace(
            dir=folder, db=os.path.join(folder, 'map.db'), lap_split=None, vm_url='http://127.0.0.1:9/',
            grafana_token_file=os.path.join(folder, 'none')))

    @staticmethod
    def write(folder, room, rows, mode='w'):
        """A session file as the server writes it: Utc, Speed; `rows` = [(utc_ms, speed)]."""
        os.makedirs(os.path.join(folder, room), exist_ok=True)
        path = os.path.join(folder, room, '20261113-000000Z.jsonl')
        with open(path, mode, encoding='utf-8') as f:
            if mode == 'w':
                f.write(json.dumps({'recv_ms': 1, 'meta': [{'nm': 'Utc'}, {'nm': 'Speed'}]}) + '\n')
            if rows:
                f.write(json.dumps({'recv_ms': 1, 'samples': [[t, v, 3] for t, v in rows]}) + '\n')
        return path

    def test_a_room_without_data_says_so(self):
        import tempfile
        msg = json.loads(self.bridge(tempfile.mkdtemp()).feed_msg('nobody'))
        self.assertEqual(msg['feed'], {'data_t': None})
        self.assertIsInstance(msg['now'], int)
        self.assertNotIn('t', msg)   # a page from before reads rows by `t` and lets this pass

    def test_rows_set_the_time_on_the_servers_clock(self):
        """Not the rows' own time (here a day old): when they got here. Rows already taken do not count."""
        import asyncio
        import tempfile
        import time
        import unittest.mock
        folder = tempfile.mkdtemp()
        b = self.bridge(folder)
        utc = round(time.time() * 1000) - 86_400_000

        async def run():
            task = asyncio.ensure_future(b.follow())
            await asyncio.sleep(0.2)
            self.assertIsNone(json.loads(b.feed_msg('r'))['feed']['data_t'])
            before = round(time.time() * 1000)
            self.write(folder, 'r', [(utc, 50.0), (utc + 100, 51.0)])
            await asyncio.sleep(0.4)
            first = json.loads(b.feed_msg('r'))
            self.assertTrue(before <= first['feed']['data_t'] <= first['now'], first)
            self.write(folder, 'r', [(utc + 100, 51.0)], mode='a')   # the same row again (the server replaying)
            await asyncio.sleep(0.4)
            self.assertEqual(json.loads(b.feed_msg('r'))['feed']['data_t'], first['feed']['data_t'])
            self.write(folder, 'r', [(utc + 200, 52.0)], mode='a')
            await asyncio.sleep(0.4)
            self.assertGreater(json.loads(b.feed_msg('r'))['feed']['data_t'], first['feed']['data_t'])
            task.cancel()

        with unittest.mock.patch.object(live_bridge, 'http_post', lambda *a, **k: None):
            asyncio.run(run())

    def test_a_restarted_bridge_takes_it_from_the_file(self):
        """Bridge.rebuild: the rows were here before this bridge; the file's last write tells when."""
        import tempfile
        import time
        folder = tempfile.mkdtemp()
        utc = round(time.time() * 1000) - 600_000
        path = self.write(folder, 'r', [(utc, 50.0)])
        os.utime(path, (time.time() - 300, time.time() - 300))
        b = self.bridge(folder)
        b.rebuild()
        self.assertAlmostEqual(json.loads(b.feed_msg('r'))['feed']['data_t'], (time.time() - 300) * 1000, delta=2000)

    def test_only_the_pages_drawing_rows_get_it(self):
        self.assertEqual(live_bridge.FEED_KINDS, (None, 'gg'))
        self.assertFalse(set(live_bridge.FEED_KINDS) & set(live_bridge.CLOCK_KINDS))


if __name__ == '__main__':
    unittest.main()
