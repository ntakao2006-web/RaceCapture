"""レポートの決めごとの下書き（report_draft.py）の試験。作りものの周の表で確かめる。"""
import tempfile
import unittest
from pathlib import Path

import report_draft
import run_laps
from test_run_laps import HEADER, T0, iso
from datetime import timedelta


def lap(n, time_s, stop_s=0.0, start=None):
    return {'lap': n, 'time_s': time_s, 'stop_s': stop_s, 'start': start, 'end': None if start is None else start + time_s}


class DraftTest(unittest.TestCase):
    def test_pits_split_the_stints_and_slow_laps_are_listed(self):
        times = {9: 112, 10: 111, 11: 110, 12: 110.5, 13: 119, 14: 111, 15: 190, 16: 125, 17: 110, 18: 111, 19: 110, 20: 111}
        t, laps = T0.timestamp(), []
        for n, s in times.items():
            laps.append(lap(n, s, stop_s=62.0 if n == 15 else 0.0, start=t))
            t += s
        d = report_draft.draft({'id': 'x'}, {'laps': laps})
        a = d['auto']
        self.assertEqual((a['race_laps'], a['pit_laps'], a['pit_out_laps']), ([9, 20], [15], [16]))
        self.assertEqual(a['stints'], [[9, 15], [16, 20]])
        self.assertEqual(a['slow_laps'], [13])                 # ピットの周・出た周は挙げない
        self.assertEqual(a['window'], ['09:55', '10:28'])      # 10:00 に始まり約23分。前後5分
        self.assertIn('drivers', [m['key'] for m in d['manual']])

    def test_a_stop_on_the_last_lap_is_not_a_pit_but_is_said(self):
        d = report_draft.draft({}, {'laps': [lap(1, 100), lap(2, 101), lap(3, 99), lap(4, 180, stop_s=40)]})
        self.assertEqual((d['auto']['pit_laps'], d['auto']['stints']), ([], [[1, 4]]))
        self.assertTrue(any('最後の周（4周目）' in n for n in d['notes']))

    def test_waiting_before_the_start_is_not_a_race_lap(self):
        d = report_draft.draft({}, {'laps': [lap(8, 195, stop_s=540), lap(9, 115), lap(10, 111), lap(11, 110)]})
        self.assertEqual((d['auto']['race_laps'], d['auto']['pit_laps'], d['auto']['stints']), ([9, 11], [], [[9, 11]]))
        self.assertTrue(any('最初の周（8周目）' in n for n in d['notes']))

    def test_a_reset_in_the_middle_uses_the_laps_after_it(self):
        d = report_draft.draft({}, {'laps': [lap(1, 100), lap(2, 100), lap(1, 90), lap(2, 91), lap(3, 92)]})
        self.assertEqual(d['auto']['race_laps'], [1, 3])
        self.assertTrue(any('0周に戻して' in n for n in d['notes']))

    def test_gaps_old_tables_and_no_laps_are_said(self):
        d = report_draft.draft({}, {'laps': [lap(1, 100), lap(3, 100)]})
        self.assertTrue(any('周の番号が飛んでいます' in n for n in d['notes']))
        old = report_draft.draft({}, {'laps': [{'lap': 1, 'time_s': 100.0}]})
        self.assertTrue(any('ピットの周は出せません' in n for n in old['notes']))
        self.assertEqual(report_draft.draft({}, {'laps': []})['auto'], {})


class StopSecondsTest(unittest.TestCase):
    def test_the_lap_table_counts_the_seconds_stopped_per_lap(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'LOG_20261108T010000Z_0000abcd.csv'
            rows, t = [HEADER], T0
            for n, stopped in ((0, 0), (1, 30), (2, 0)):       # 60秒の周を3つ。2つ目で30秒止まる
                for k in range(60):
                    speed = 0 if 10 <= k < 10 + stopped else 80
                    rows.append(f'1,{iso(t)},{speed},{speed},"[0.9, 0.1]",{n},,,,100,88')
                    t += timedelta(seconds=1)
            rows.append(f'1,{iso(t)},80,80,"[0.9, 0.1]",3,1.0,,,100,88')
            log.write_text('\n'.join(rows) + '\n', encoding='utf-8')
            laps = run_laps.laps_of(log)['laps']
            self.assertEqual([round(x['stop_s']) for x in laps], [0, 30, 0])


if __name__ == '__main__':
    unittest.main()
