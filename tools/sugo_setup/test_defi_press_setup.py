import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import defi_press_setup
import defi_volt_setup
import sugo_setup
from test_defi_volt_setup import SIGNALS, FakeUnoQ

PRESS_VOLT = defi_volt_setup.DEFI_SIGNALS[0]


class FakeCar(FakeUnoQ):
    """PressVolt と回転数を返す本体（volts は読むたびに順にくり返す電圧、None は読めない）"""
    def __init__(self, volts=(0.62,), rpm=0.0):
        super().__init__()
        self.config['signals'] = list(SIGNALS) + [PRESS_VOLT]
        self.files['config.json'] = json.dumps(self.config)
        self.volts, self.rpm, self.reads = list(volts), rpm, 0

    def api(self, path, body):
        if path != '/api/telemetry':
            return super().api(path, body)
        volt = self.volts[self.reads % len(self.volts)]; self.reads += 1
        code = 4 if volt is None else 0
        sample = {'can_signals': {'PressVolt': volt, 'RPM': self.rpm}, 'can_states': {'PressVolt': {'code': code}}}
        return json.dumps({'sample': sample}) + '\n200'


class DefiPressSetupTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeCar()
        self.runner, self.backups, self.sleep = sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS, defi_press_setup.time.sleep
        sugo_setup.runner = lambda use_adb, host: self.device
        defi_press_setup.time.sleep = lambda s: None
        self.folder = tempfile.TemporaryDirectory(); defi_volt_setup.LOCAL_BACKUPS = Path(self.folder.name)

    def tearDown(self):
        sugo_setup.runner, defi_volt_setup.LOCAL_BACKUPS = self.runner, self.backups
        defi_press_setup.time.sleep = self.sleep
        self.folder.cleanup()

    def oilpress(self):
        return next(s for s in self.device.config['signals'] if s['name'] == 'OilPress')

    def test_the_conversion_is_the_defi_sensor_line_in_pic_volts(self):
        k = defi_press_setup.per_volt()
        self.assertAlmostEqual(k, 250 * 5 / 5.544, places=6)        # about 225.5 kPa per PIC volt
        self.assertAlmostEqual(defi_press_setup.ZERO_V, 0.632, places=3)  # 0.570 V of the Defi 5 V, in PIC volts
        # Type-RA's 50 psi (344.7 kPa) at 1.954 V of the Defi 5 V reads as 1.954 * 5.544 / 5 on the PIC
        signal = defi_press_setup.press_signal()
        adc = round(1.954 * 5.544 / 5 / 5 * 4095)
        self.assertAlmostEqual(adc * signal['scale'] + signal['offset'], 344.7, delta=5)
        self.assertEqual(defi_press_setup.params(signal), (signal['scale'] * 4095 / 5, defi_press_setup.ZERO_V))

    def test_check_only_changes_nothing(self):
        self.assertEqual(defi_press_setup.main([]), 0)
        self.assertEqual(self.device.posts, [])

    def test_needs_the_voltage_signal_first(self):
        self.device.config['signals'] = list(SIGNALS)
        self.assertEqual(defi_press_setup.main(['--apply']), 1)
        self.assertEqual(self.device.posts, [])

    def test_zero_now_with_the_engine_stopped(self):
        self.device.volts = [0.618, 0.622, 0.620]
        self.assertEqual(defi_press_setup.main(['--apply', '--zero-now']), 0)
        self.assertEqual(self.device.posts, ['/api/log/stop', '/api/config', '/api/log/start'])
        k, zero = defi_press_setup.params(self.oilpress())
        self.assertAlmostEqual(zero, 0.620, places=6)
        self.assertAlmostEqual(k, defi_press_setup.per_volt(), places=6)
        self.assertEqual(self.device.config['signals'][:3], list(SIGNALS) + [PRESS_VOLT])  # the others kept, OilPress added
        self.assertTrue(self.device.recording)
        # a plain --apply later keeps the measured zero
        self.device.volts = [1.9]
        self.assertEqual(defi_press_setup.main(['--apply']), 0)
        self.assertEqual(len(self.device.posts), 3)
        self.assertAlmostEqual(defi_press_setup.params(self.oilpress())[1], 0.620, places=6)

    def test_zero_now_refused_with_the_engine_running_or_no_sensor(self):
        self.device.rpm = 850.0
        self.assertEqual(defi_press_setup.main(['--apply', '--zero-now']), 1)
        self.device.rpm, self.device.volts = 0.0, [0.0]  # the harness not connected: near 0 V, out of the sensor's zero
        self.assertEqual(defi_press_setup.main(['--apply', '--zero-now']), 1)
        self.device.volts = [None]  # PRESS not read
        self.assertEqual(defi_press_setup.main(['--apply', '--zero-now']), 1)
        self.device.volts = [0.60, 0.70]  # moving
        self.assertEqual(defi_press_setup.main(['--apply', '--zero-now']), 1)
        self.assertEqual(self.device.posts, [])

    def test_meter_sets_the_slope_and_keeps_the_zero(self):
        self.device.volts = [0.620]
        defi_press_setup.main(['--apply', '--zero-now'])
        self.device.volts, self.device.rpm, self.device.reads = [1.95, 1.97], 2000.0, 0  # idle pulses; 1.96 on average
        self.assertEqual(defi_press_setup.main(['--apply', '--meter', '300']), 0)
        k, zero = defi_press_setup.params(self.oilpress())
        self.assertAlmostEqual(zero, 0.620, places=6)
        self.assertAlmostEqual(k * (1.96 - zero), 300, places=6)
        # a slope far from the sensor's 250 kPa/V is refused
        self.device.volts = [1.0]
        self.assertEqual(defi_press_setup.main(['--apply', '--meter', '300']), 1)

    def test_the_signal_is_valid_for_the_logger(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'EcoCapture-Web'))
        try:
            from hardware import defivolt_packet
            from models import Signal
        except ImportError as error:  # pydanticが無いPC
            self.skipTest(str(error))
        signal = Signal(**defi_press_setup.press_signal(0.62))
        frame = bytes([0x00, 0x00, 0x00, 0x08, 0x00, 0x08, 0x01, 0x01])  # PRESS 0 (the harness off), TEMP1/TEMP2 2048
        adc, code = defivolt_packet(frame, 0)
        self.assertEqual((adc, code), (0, 1))  # near the lower rail: a value, not None
        self.assertLess(adc * signal.scale + signal.offset, -100)  # so the DASH must not take it as low pressure


if __name__ == '__main__':
    unittest.main()
