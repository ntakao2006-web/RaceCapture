import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import defi_temp_setup
import defi_volt_setup
import sugo_setup
from test_defi_volt_setup import OIL, SIGNALS, FakeUnoQ


class DefiTempSetupTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeUnoQ()
        self.runner, self.backups = sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS
        sugo_setup.runner = lambda use_adb, host: self.device
        self.folder = tempfile.TemporaryDirectory(); defi_volt_setup.LOCAL_BACKUPS = Path(self.folder.name)

    def tearDown(self):
        sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS = self.runner, self.backups
        self.folder.cleanup()

    def test_check_only_changes_nothing(self):
        self.assertEqual(defi_temp_setup.main([]), 0)
        self.assertEqual(self.device.posts, [])

    def test_apply_replaces_oiltemp_in_place_and_adds_water(self):
        self.assertEqual(defi_temp_setup.main(['--apply']), 0)
        self.assertEqual(self.device.posts, ['/api/log/stop', '/api/config', '/api/log/start'])
        water, oil = defi_temp_setup.temp_signals(defi_temp_setup.PULLUP_OHM)
        self.assertEqual(self.device.config['signals'], [SIGNALS[0], oil, water])
        self.assertEqual((oil['byte_offset'], water['byte_offset']), (4, 2))
        self.assertTrue(self.device.recording)
        # 2回目は何もしない
        self.assertEqual(defi_temp_setup.main(['--apply']), 0)
        self.assertEqual(len(self.device.posts), 3)

    def test_old_oiltemp_is_reported_as_different(self):
        self.assertEqual(OIL['can_id'], 0x600)
        self.assertEqual(defi_temp_setup.replaced([OIL], [{'name': 'OilTemp', 'can_id': 0x580}]),
                         [{'name': 'OilTemp', 'can_id': 0x580}])

    def test_conversion_matches_the_meter_readings(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'EcoCapture-Web'))
        try:
            from models import Signal
        except ImportError as error:  # pydanticが無いPC
            self.skipTest(str(error))
        water, oil = (Signal(**s) for s in defi_temp_setup.temp_signals(defi_temp_setup.PULLUP_OHM))
        # 2026-11-03 Defiの油温計 85℃ のときの Temp2 の60秒平均 2.1346 V（公称5 V換算）
        self.assertAlmostEqual(oil.ntc_celsius(2.1346 / 5), 85, delta=.5)
        self.assertAlmostEqual(oil.ntc_celsius(2.109 / 5), 86, delta=.5)
        # 水温はファンの周期で揺れる。平均 2.035 V ≒ メーターの87〜89℃
        self.assertAlmostEqual(water.ntc_celsius(2.035 / 5), 88, delta=1.5)
        # 表の97℃より上は同じβ式を延ばす（警告の110〜130℃）。電圧が下がるほど高温
        self.assertGreater(oil.ntc_celsius(1.6 / 5), oil.ntc_celsius(2.1 / 5))
        (t1, r1), (t2, r2) = defi_temp_setup.DEFI_POINTS
        beta = math.log(r1 / r2) / (1 / (t1 + 273.15) - 1 / (t2 + 273.15))
        for celsius in (97, 120, 130):
            ohm = r2 * math.exp(beta * (1 / (celsius + 273.15) - 1 / (t2 + 273.15)))
            self.assertAlmostEqual(oil.ntc_celsius(ohm / (ohm + oil.pullup_ohm)), celsius, places=3)


if __name__ == '__main__':
    unittest.main()
