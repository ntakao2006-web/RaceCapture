"""油温・水温の警告の値が、車の設定（vehicles/ncec.json）と、数字を別々に持っている6か所とで食い違っていないか（SP-7-1）。

警告の線（油温 120℃・水温 110℃）は、車載画面・スマホ・周回表・表紙・Grafana・動画の計器が、それぞれ自分の初期値として
持っている（本体・スマホ・サーバーと、動く場所が別々なので、いまは1つのファイルを読みに行けない）。
どこか1か所だけ変えると、画面によって警告の出る温度が違ってしまうので、ここで突き合わせる。
車の設定の値を変えたら、この試験が落ちた所を全部そろえること。

注意（警告の10℃下）とピットイン（10℃上）の段は、ピットの側（周回表・表紙・Grafana）にしか無い。その段の刻みもここで見る。
"""
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'tools' / 'video_hud'))

import setups  # noqa: E402


def text(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


def numbers(pattern, source):
    found = re.search(pattern, source)
    if not found:
        raise AssertionError(f'書き方が変わっていて読めない：{pattern}')
    return [float(x) for x in re.findall(r'\d+(?:\.\d+)?', found.group(1))]


class WarnLinesTest(unittest.TestCase):
    def setUp(self):
        dash = setups.load('vehicle', 'ncec')['dash']
        self.oil, self.water = dash['oil_warn'], dash['water_warn']

    def test_dash_on_the_logger(self):
        src = text('RaceCapture-UNOQ', 'dash_model.py')
        self.assertEqual(numbers(r"'oil_warn': ([\d.]+)", src), [self.oil])
        self.assertEqual(numbers(r"'water_warn': ([\d.]+)", src), [self.water])

    def test_phone_app(self):
        src = text('android-logger', 'app', 'src', 'main', 'java', 'jp', 'ecorun', 'logger', 'Circuit.kt')
        self.assertEqual(numbers(r'val oilWarn: Double = ([\d.]+)', src), [self.oil])
        self.assertEqual(numbers(r'val waterWarn: Double = ([\d.]+)', src), [self.water])

    def test_pit_pages_and_grafana_put_the_warning_in_the_middle(self):
        """周回表・Grafana は（注意, 警告, ピットイン）、表紙は（注意, 警告）。注意は10℃下、ピットインは10℃上"""
        laps = text('tools', 'home_telemetry', 'laps.html')
        grafana = text('tools', 'home_telemetry', 'grafana', 'build_sugo_dashboard.py')
        home = text('tools', 'home_telemetry', 'home.html')
        three = lambda v: [v - 10, v, v + 10]
        self.assertEqual(numbers(r"const OIL = limits\('oil', \[([\d, .]+)\]\)", laps), three(self.oil))
        self.assertEqual(numbers(r"const WATER = limits\('water', \[([\d, .]+)\]\)", laps), three(self.water))
        self.assertEqual(numbers(r'\nOIL = \(([\d, .]+)\)', grafana), three(self.oil))
        self.assertEqual(numbers(r'\nWATER = \(([\d, .]+)\)', grafana), three(self.water))
        self.assertEqual(numbers(r"oil: limits\('oil', \[([\d, .]+)\]\)", home), three(self.oil)[:2])
        self.assertEqual(numbers(r"water: limits\('water', \[([\d, .]+)\]\)", home), three(self.water)[:2])

    def test_video_gauges(self):
        import hud_layout
        hud = hud_layout.load(hud_layout.DEFAULT_INI)
        table = hud_layout.alarm_table(hud, hud.preview)     # どの計器も赤になる値
        self.assertEqual(table['can_signals.OilTemp'], self.oil)
        self.assertEqual(table['values.WaterTemp'], self.water)


if __name__ == '__main__':
    unittest.main()
