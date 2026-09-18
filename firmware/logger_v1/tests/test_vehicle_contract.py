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
        self.assertEqual(len(names),95)
        self.assertEqual(names[81], 'SteeringAngle') # existing stored channel indices remain stable
        self.assertEqual(names[82], 'WheelSpeedFL')
        self.assertEqual(names[-1], 'FuelLevel')
        schema = int(re.search(r'LoggerSchema = (\d+)',demo)[1])
        self.assertEqual(schema,1+len(names)+1) # initial revision + channels + initial GNSS config

    def test_speed_is_not_filled_from_gnss(self):
        source=(ROOT/'firmware/logger_v1/src/sensors.cpp').read_text(encoding='utf-8')
        self.assertNotIn('putChannel(SPEED,',source)
        self.assertIn('putChannel(GPS_SPEED,',source)

    def test_transmit_surface_is_read_only_and_bounded(self):
        source=(ROOT/'firmware/logger_v1/src/can.cpp').read_text(encoding='utf-8')
        self.assertIn('TWAI_MODE_LISTEN_ONLY',source)
        self.assertIn('if (!allowedObdRequest(frame)) return false;',source)
        self.assertEqual(source.count('twai_transmit('),1)
        self.assertNotIn('const bool active = bench_mode',source)
        self.assertIn('config.nc_profile && !vehicle_acquisition.toyota_steering',source)
        protocol=(ROOT/'firmware/logger_v1/src/protocol.cpp').read_text(encoding='utf-8')
        self.assertIn('Arbitrary vehicle CAN TX is prohibited',protocol)
        state=(ROOT/'firmware/logger_v1/src/state.cpp').read_text(encoding='utf-8')
        self.assertIn('if (!validAcquisition(candidate)) return false',state)

if __name__=='__main__': unittest.main()
