"""Repository contract checks: no hardware, account or user settings access."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

class VehicleContractTests(unittest.TestCase):
    def test_channel_order_matches_demo(self):
        state = (ROOT/'firmware/logger_v1/src/state.cpp').read_text(encoding='utf-8')
        definitions = state.split('static const Def defs[] =',1)[1].split('static_assert',1)[0]
        firmware = re.findall(r'\{"([A-Za-z0-9_]+)",',definitions)
        demo = (ROOT/'EcoCapture/Core/DemoSource.cs').read_text(encoding='utf-8')
        names = re.findall(r'"([A-Za-z0-9_]+)"',demo.split('LoggerChannels = {',1)[1].split('};',1)[0])
        self.assertEqual(firmware,names)
        self.assertEqual(len(names),82)
        schema = int(re.search(r'LoggerSchema = (\d+)',demo)[1])
        self.assertEqual(schema,1+len(names)+1) # initial revision + channels + initial GNSS config

    def test_speed_is_not_filled_from_gnss(self):
        source=(ROOT/'firmware/logger_v1/src/sensors.cpp').read_text(encoding='utf-8')
        self.assertNotIn('putChannel(SPEED,',source)
        self.assertIn('putChannel(GPS_SPEED,',source)

    def test_transmit_surface_is_read_only_and_bounded(self):
        source=(ROOT/'firmware/logger_v1/src/can.cpp').read_text(encoding='utf-8')
        self.assertIn('request.ss = 1;',source)
        self.assertIn('TWAI_MODE_LISTEN_ONLY',source)
        self.assertIn('stats.obd_fault = true',source)
        header=(ROOT/'firmware/logger_v1/src/vehicle_obd.h').read_text(encoding='utf-8')
        self.assertIn('request.data[1] = 1;',header)

if __name__=='__main__': unittest.main()
