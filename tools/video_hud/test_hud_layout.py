"""hud_layout.py（PC）が、本体の hud_layout.h と同じ形を組み立て、同じ誤りを同じ行で見つけるかの試験。

testdata/*.golden は本体（UNO Q）で tools/unoq_overlay_enc/hud_dump.c を動かして作った頂点:
  ./hud_dump <ini> hud_font_64.pgm testdata/<状態>.state > <名前>.golden
  default_<状態>：hud_default.ini（normal warn alarm nodata edge）、features_<a|b>：testdata/features.ini
testdata/bad/*.ini は誤りのある設定。1行目の「# expect N」が誤りの行（本体の hud_dump でも同じ行で断ることを確かめてある）。
hud_layout.h か hud_layout.py の規則を変えたら、本体で golden を作り直してからこれを通す（手順書5-14）。
"""
import dataclasses
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_layout  # noqa: E402
import hud_preview  # noqa: E402

DATA = HERE / 'testdata'
FONT = hud_layout.load_font()


def read_state(path):
    """hud_dump.c と同じ読み方：値の名前 = 値、utc、age"""
    table, utc, age = {}, None, 0.0
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.startswith('#'):
            continue
        k, v = (s.strip() for s in line.split('=', 1))
        if k == 'utc':
            utc = int(v)
        elif k == 'age':
            age = float(v)
        else:
            table[k] = float(v)
    return table, utc, age


def vertices(quads):
    """quad4 と同じ順（0 1 3 1 2 3）の頂点"""
    out = []
    for xs, ys, u0, v0, u1, v1, c in quads:
        us, vs = (u0, u1, u1, u0), (v0, v0, v1, v1)
        for i in (0, 1, 3, 1, 2, 3):
            out.append((xs[i], ys[i], us[i], vs[i], *c))
    return out


class GoldenTest(unittest.TestCase):
    def check(self, ini, state, golden):
        hud = hud_layout.load(ini)
        table, utc, age = read_state(DATA / state)
        got = vertices(hud_layout.build(hud, FONT, hud_layout.values_from(hud, table), utc, age))
        lines = (DATA / golden).read_text().splitlines()
        self.assertEqual(lines[0], f'quads {len(got) // 6}', golden)
        want = [tuple(float(x) for x in ln.split()) for ln in lines[1:]]
        self.assertEqual(len(want), len(got))
        for i, (w, g) in enumerate(zip(want, got)):
            for j in range(8):
                tol = 2e-6 if j in (2, 3) else 2e-3  # u・vは小数6桁、ほかは4桁で書いてある
                self.assertTrue(math.isclose(w[j], g[j], abs_tol=tol), f'{golden} 頂点{i} 列{j}: 本体 {w[j]} / PC {g[j]}')

    def test_default_layout(self):
        for s in ('normal', 'warn', 'alarm', 'nodata', 'edge'):
            with self.subTest(s):
                self.check(hud_layout.DEFAULT_INI, f'{s}.state', f'default_{s}.golden')

    def test_features(self):
        for s in ('a', 'b'):
            with self.subTest(s):
                self.check(DATA / 'features.ini', f'features_{s}.state', f'features_{s}.golden')


class ParseTest(unittest.TestCase):
    def test_bad_configs_report_line(self):
        files = sorted((DATA / 'bad').glob('*.ini'))
        self.assertGreaterEqual(len(files), 20)
        for f in files:
            text = f.read_text(encoding='utf-8')
            expect = int(text.splitlines()[0].split()[-1])
            with self.subTest(f.name):
                with self.assertRaises(hud_layout.HudError) as cm:
                    hud_layout.parse(text)
                self.assertEqual(cm.exception.line, expect, str(cm.exception))

    def test_user_hud_ini_matches_default_layout(self):
        """最初の hud.ini は元の配置（hud_default.ini）と同じ計器"""
        a, b = hud_layout.load(HERE / 'hud.ini'), hud_layout.load(hud_layout.DEFAULT_INI)
        # 説明の行数だけ違う。NaN（しきい値なし）同士も同じとみなすため repr で比べる
        no_line = lambda hud: [repr(dataclasses.replace(it, line=0)) for it in hud.items]  # noqa: E731
        self.assertEqual(no_line(a), no_line(b))
        self.assertEqual(a.refs, b.refs)
        self.assertEqual(a.preview, b.preview)

    def test_bom_and_crlf(self):
        text = '﻿[a]\r\ntype = text\r\nx = 1\r\ny = 2\r\ntext = "A B"\r\n'
        hud = hud_layout.parse(text)
        self.assertEqual(hud.items[0].text, 'A B')

    def test_preview_values_must_be_numbers(self):
        with self.assertRaises(hud_layout.HudError) as cm:
            hud_layout.parse('[preview]\nvalues.RPM = fast\n')
        self.assertEqual(cm.exception.line, 2)


class EstimateTest(unittest.TestCase):
    """塗る面積からの重さの見積もり（本体での実測は手順書5-15）"""

    def test_default_is_ok(self):
        screens, ms, level = hud_layout.estimate(hud_layout.load(hud_layout.DEFAULT_INI), FONT)
        self.assertAlmostEqual(screens, 0.30, delta=0.02)
        self.assertEqual(level, 'ok')
        self.assertLess(abs(ms - 18.65), 1.0)  # 本体で18.65ms

    def test_full_screen_boxes(self):
        base = (HERE / 'hud.ini').read_text(encoding='utf-8')
        box = '[full{}]\ntype = box\nrect = 0 0 1920 1080\ncolor = 0 0 0 0.06\n\n'
        for n, want, measured in ((1, 'edge', 24.52), (2, 'heavy', 35.42)):
            hud = hud_layout.parse(base + ''.join(box.format(i) for i in range(n)))
            screens, ms, level = hud_layout.estimate(hud, FONT)
            self.assertEqual(level, want, n)
            self.assertGreaterEqual(ms, measured)  # 少し重めに見積もる

    def test_nodata_items_are_counted(self):
        hud = hud_layout.parse('[a]\ntype = box\nshow = nodata\nrect = 0 0 1920 1080\ncolor = red\n')
        self.assertAlmostEqual(hud_layout.estimate(hud, FONT)[0], 1.0)


class PreviewTest(unittest.TestCase):
    def test_renders_three_states(self):
        hud = hud_layout.load(hud_layout.DEFAULT_INI)
        bg = hud_preview.make_background()
        images = hud_preview.render_states(hud, FONT, bg, utc=1793335512)
        self.assertEqual(set(images), {'normal', 'alarm', 'nodata'})
        for data in images.values():
            self.assertTrue(data.startswith(b'\x89PNG'))

    def test_alarm_table_reaches_red(self):
        hud = hud_layout.load(hud_layout.DEFAULT_INI)
        table = hud_layout.alarm_table(hud, hud.preview)
        self.assertEqual(table['values.WaterTemp'], 110)
        self.assertEqual(table['can_signals.OilTemp'], 120)
        self.assertEqual(table['values.RPM'], 7000)
        self.assertEqual(table['values.Speed'], 128)  # しきい値の無いものはそのまま

    def test_rasterize_fills_pixel_centers(self):
        img = hud_preview.rasterize([((10, 20, 20, 10), (5, 5, 8, 8), -1, -1, -1, -1, (1, 0, 0, 1))], FONT,
                                    hud_preview.make_background())
        self.assertEqual(tuple(img[5, 10]), (1, 0, 0))
        self.assertEqual(tuple(img[7, 19]), (1, 0, 0))
        self.assertNotEqual(tuple(img[8, 10]), (1, 0, 0))
        self.assertNotEqual(tuple(img[5, 20]), (1, 0, 0))


if __name__ == '__main__':
    unittest.main()
