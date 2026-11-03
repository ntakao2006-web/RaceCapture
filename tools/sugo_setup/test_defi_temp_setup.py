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
        water, oil = (Signal(**s) for s in defi_temp_setup.temp_signals())
        celsius = lambda signal, volt: signal.ntc_celsius(round(volt / 5 * 4095) * signal.scale)  # 公称5 V換算の電圧から
        # Defiのメーターと並べて読んだ点（Temp1・Temp2の30〜60秒平均）。水温はファンの周期で揺れるので平均
        for signal, meter, volt in ((oil, 85, 2.1346), (oil, 86, 2.109), (oil, 72, 2.655),
                                    (water, 88, 2.035), (water, 70.75, 2.67), (water, 36, 4.0165)):
            self.assertAlmostEqual(celsius(signal, volt), meter, delta=1.5)
        # 表の97℃より上は同じβ式を延ばす（警告の110〜130℃）。電圧が下がるほど高温
        self.assertGreater(celsius(oil, 1.6), celsius(oil, 2.1))
        # Defiの電圧は公称5 Vより高いので、ADCの上限（センサーが外れたとき）は約6℃に出る（警告は鳴らない側）
        self.assertLess(celsius(oil, 5.0), 10)
        (t1, r1), (t2, r2) = defi_temp_setup.DEFI_POINTS
        beta = math.log(r1 / r2) / (1 / (t1 + 273.15) - 1 / (t2 + 273.15))
        for celsius in (97, 120, 130):
            ohm = r2 * math.exp(beta * (1 / (celsius + 273.15) - 1 / (t2 + 273.15)))
            self.assertAlmostEqual(oil.ntc_celsius(ohm / (ohm + oil.pullup_ohm)), celsius, places=3)


if __name__ == '__main__':
    unittest.main()
