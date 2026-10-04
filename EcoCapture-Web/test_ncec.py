import unittest
from ncec import Decoder,preset,decode_text
from models import Configuration
class NcecTests(unittest.TestCase):
 def test_rpm_and_speed_offset(self):
  self.assertEqual(Decoder().decode(0x201,bytes.fromhex('1F400000271000FF'),0)['values'],{'RPM':2000,'Speed':0})
 def test_wheels_preserve_ab(self):
  self.assertEqual(list(Decoder().decode(0x4B0,bytes.fromhex('2710277427D8283C'),0)['values'].values()),[0,1,2,3])
 def test_engine_and_redundant_temperature(self):
  value=Decoder().decode(0x240,bytes([0,120,0,255,65,0,0,0]),0)['values']
  self.assertEqual(value,{'WaterTemp':80,'Throttle':100,'IntakeTemp':25})
  self.assertEqual(Decoder().decode(0x420,bytes([120]),0)['values']['WaterTempBackup'],80)
 def test_clutch_is_bit1_only(self):
  self.assertEqual(Decoder().decode(0x231,bytes([255,6]),0)['values']['ClutchDisengaged'],1)
  self.assertEqual(Decoder().decode(0x231,bytes([255,4]),0)['values']['ClutchDisengaged'],0)
 def test_fuel_average_expires_and_retains_raw(self):
  d=Decoder();d.decode(0x430,b'\0',0)
  self.assertEqual(d.decode(0x430,b'\xff',100)['values']['FuelLevel'],50)
  self.assertEqual(d.decode(0x430,b'\xff',2200)['values']['FuelLevel'],100)
  self.assertAlmostEqual(Decoder().decode(0x430,bytes([237]),0)['values']['FuelLevelRaw'],92.94117647)
 def test_counter_rollover_gap_and_duplicate(self):
  d=Decoder()
  for t,c in [(0,255),(10,0),(20,2),(30,2)]:r=d.decode(0x211,bytes(7)+bytes([c]),t)
  self.assertEqual(d.anomalies,2)
  self.assertIsNone(d.decode(0x211,bytes(8),200)['counter_quality']['delta'])
 def test_invalid_frames(self):
  for text in ['0 201 00','0 800 00','-1 201 00','2 430 00\n1 430 00']:
   with self.assertRaises(ValueError):decode_text(text)
 def test_preset_and_unknown_fields(self):
  p=preset();c=Configuration(profile=p['profile'],signals=p['signals']);self.assertEqual(len(c.signals),12)
  self.assertEqual(Decoder().decode(0x200,bytes(8),0)['values'],{})
  self.assertFalse(p['obd']['enabled']);self.assertNotIn(0x5C,p['obd']['confirmed_pids'])
if __name__=='__main__':unittest.main()
