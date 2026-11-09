"""lap_video.py・wind_reduce.py の試験（合成した記録・TS・音で。drive_logs は使わない）
  python -m unittest tools/lap_video/test_lap_video.py
"""
import csv
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import lap_video as lv  # noqa: E402
import wind_reduce as wr  # noqa: E402

T0 = datetime(2026, 11, 8, 2, 0, 0, tzinfo=timezone.utc).timestamp()


def iso(t, frac=True):
    d = datetime.fromtimestamp(t, timezone.utc)
    return d.isoformat(timespec='microseconds') if frac else d.strftime('%Y-%m-%dT%H:%M:%SZ')


class Laps(unittest.TestCase):
    def write_log(self, path, host_off):
        """100Hz・60秒。20秒・50秒でラインを通る（第1周30秒・第2周30秒）。本体の時計は host_off 秒ずれている"""
        with open(path, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['host_utc', 'gnss_utc', 'LapCount', 'LapTime', 'RPM'])
            for i in range(6000):
                t = T0 + i / 100
                lc = 0 if t < T0 + 20 else (1 if t < T0 + 50 else 2)
                lt = '' if lc == 0 else ('0.5' if lc == 1 else '0.5')
                w.writerow([iso(t + host_off), iso(t, frac=False), lc, lt, 6000 + i])

    def test_laps_and_clock_fix(self):
        for off in (0.0, -810.0):   # 11/8の朝は本体の時計が13分半遅れていた
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'LOG_a.csv'
                self.write_log(p, off)
                laps = lv.read_laps([p])
                self.assertEqual([x['lap'] for x in laps], [1, 2])
                self.assertAlmostEqual(laps[0]['end'], T0 + 20, delta=0.05)
                self.assertAlmostEqual(laps[1]['end'], T0 + 50, delta=0.05)
                self.assertAlmostEqual(laps[1]['start'], T0 + 20, delta=0.05)
                ts, rp = lv.read_rpm([p], T0 + 10, T0 + 11)
                self.assertAlmostEqual(ts[0], T0 + 10, delta=0.05)
                self.assertAlmostEqual(rp[0], 7000, delta=6)

    def test_same_lap_in_two_logs_counts_once(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'LOG_a.csv', Path(d) / 'LOG_b.csv'
            self.write_log(a, 0)
            self.write_log(b, 0)
            self.assertEqual([x['lap'] for x in lv.read_laps([a, b])], [1, 2])


def pkt(pid, payload=b'', pusi=False, rai=False):
    p = bytearray(b'\xff' * 188)
    p[0], p[1], p[2] = 0x47, (0x40 if pusi else 0) | pid >> 8, pid & 0xff
    if rai:
        p[3], p[4], p[5] = 0x30, 1, 0x40
        p[6:6 + len(payload)] = payload
    else:
        p[3] = 0x10
        p[4:4 + len(payload)] = payload
    return bytes(p)


def pes(pts):
    b = bytes([0x21 | (pts >> 29) & 0x0e, (pts >> 22) & 0xff, (pts >> 14) & 0xfe | 1, (pts >> 7) & 0xff, (pts << 1) & 0xfe | 1])
    return b'\x00\x00\x01\xe0\x00\x00\x80\x80\x05' + b


def make_chapter(d, name, utc0, secs, pts0):
    """30コマ/秒、1秒ごとにキーフレーム（その前にPAT）。映像の秒と時刻の表（.csv）も書く"""
    tsf, cf = Path(d) / f'{name}.ts', Path(d) / f'{name}.csv'
    with open(tsf, 'wb') as w:
        for k in range(secs * 30):
            pts = pts0 + k * 3000
            if k % 30 == 0:
                w.write(pkt(0, b'\x00pat'))
            w.write(pkt(lv.PID_VID, pes(pts), pusi=True, rai=k % 30 == 0))
            w.write(pkt(lv.PID_VID))
    rows = [(k / 30, utc0 + k / 30) for k in range(0, secs * 30, 30)]
    with open(cf, 'w', encoding='utf-8') as fh:
        fh.write('frame,video_s,utc,clock,host_utc\n')
        for v, u in rows:
            fh.write(f'0,{v:.3f},{iso(u)},gnss,{iso(u)}\n')
    return (str(tsf), str(cf), rows[0][1], rows[-1][1], rows)


def first_pts(path):
    f, keys, _ = lv.scan_keys(path)
    return f


class Cut(unittest.TestCase):
    def test_cut_inside_one_chapter(self):
        with tempfile.TemporaryDirectory() as d:
            ch = make_chapter(d, 'a_01', T0, 20, 90000)
            plan, start_utc = lv.cut_plan([ch], T0 + 5.5, T0 + 9.2)
            out = Path(d) / 'cut.ts'
            lv.write_cut(plan, out)
            data = out.read_bytes()
            self.assertEqual(len(data) % 188, 0)
            self.assertEqual(data[1] & 0x1f, 0)  # PATから始まる
            self.assertAlmostEqual(start_utc, T0 + 5.0, delta=0.01)   # 5.5秒の前のキーフレーム
            self.assertAlmostEqual((first_pts(out) - 90000) / 90000, 5.0, delta=0.01)
            f, keys, _ = lv.scan_keys(out)
            last = max(p for p, _ in keys)
            self.assertAlmostEqual((last - 90000) / 90000, 9.0, delta=0.01)   # 9.2秒の後のキーフレームの手前まで

    def test_cut_across_chapters(self):
        with tempfile.TemporaryDirectory() as d:
            a = make_chapter(d, 'a_01', T0, 10, 90000)
            b = make_chapter(d, 'a_02', T0 + 10, 10, 90000 + 10 * 90000)
            plan, start_utc = lv.cut_plan([a, b], T0 + 7.5, T0 + 12.5)
            self.assertEqual(len(plan), 2)
            out = Path(d) / 'cut.ts'
            lv.write_cut(plan, out)
            f, keys, _ = lv.scan_keys(out)
            secs = [round((p - 90000) / 90000) for p, _ in keys]
            self.assertEqual(secs, [7, 8, 9, 10, 11, 12])


class Wind(unittest.TestCase):
    def test_harmonics_kept_noise_between_lowered(self):
        sr, dur = 48000, 6.0
        t = np.arange(int(sr * dur)) / sr
        rpm_of = lambda tt: 6000 + 1000 * tt / dur   # noqa: E731
        phase = 2 * np.pi * np.cumsum(rpm_of(t) / 60) / sr
        eng = sum(0.05 / k * np.sin(k * phase) for k in range(1, 9))
        rng = np.random.default_rng(1)
        noise = 0.05 * rng.standard_normal(len(t))
        x = eng + noise
        rt = np.arange(-2, dur + 2, 0.02)
        off, _ = wr.find_offset(x, sr, rt, rpm_of(rt))
        self.assertLessEqual(abs(off), 0.1)
        y, info = wr.process(x, sr, rt, rpm_of(rt))
        # 倍音の所と間の強さを、元と比べる（音量はそろえる）
        N = 4096

        def bins(s):
            s = s / np.sqrt(np.mean(s ** 2))
            fr = np.lib.stride_tricks.sliding_window_view(s, N)[::1024] * np.hanning(N)
            P = np.abs(np.fft.rfft(fr, axis=1)) ** 2
            f = np.fft.rfftfreq(N, 1 / sr)
            tc = (np.arange(len(P)) * 1024 + N / 2) / sr
            o = f[None, :] / (rpm_of(tc)[:, None] / 60)
            dd = np.abs(o - np.round(o))
            band = (o > 0.7) & (o < 8.3)
            return P[band & (dd < 0.05)].sum(), P[band & (dd > 0.3)].sum()
        on0, off0 = bins(x)
        on1, off1 = bins(y)
        gain_between = 10 * np.log10(off1 / off0) - 10 * np.log10(on1 / on0)
        self.assertLess(gain_between, -8.0)
        self.assertEqual(info['shift_min_gain_db'], 0.0)   # 回転が急に動く所は無い


class Incidents(unittest.TestCase):
    """incidents.py：横滑り角（IMUだけ）と、まとまりの拾い方"""
    def test_beta_steady_corner_small_and_oversteer_large(self):
        import pandas as pd
        import incidents as inc
        n = 6000                              # 100Hz・60秒
        t = np.arange(n) / 100
        v = np.full(n, 80.0)                  # km/h
        R = 60.0                              # 半径60mの定常旋回 → 回る速さ v/R
        r = np.degrees(v / 3.6 / R)
        ay = (v / 3.6) ** 2 / R
        gyro = r.copy()
        gyro[4000:4030] += 30.0               # 40秒目に0.3秒、30deg/s余計に回る（後ろが出る。実際の記録でも全体のごく一部）
        d = pd.DataFrame({'ts': t, 'v': v, 'GyroZ': gyro, 'LatAccel': -ay / 9.81, 'AccelZ': np.zeros(n)})
        inc.add_signals(d)
        self.assertLess(d.beta[500:3900].abs().max(), 1.0)
        self.assertGreater(d.beta[4000:4100].abs().max(), 7.0)

    def test_spans_groups_close_hits(self):
        import incidents as inc
        ts = np.arange(1000) / 100
        m = np.zeros(1000, bool)
        m[100:120] = m[200:210] = True        # 1秒しか離れていない → 1つ
        m[700:740] = True                     # 4.8秒離れている → 別
        self.assertEqual(inc.spans(m, ts, gap=3.0), [(100, 209), (700, 739)])


if __name__ == '__main__':
    unittest.main()
