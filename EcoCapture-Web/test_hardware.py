import unittest,struct,tempfile,json
from pathlib import Path
from hardware import HardwareDecoder
from models import Configuration,Signal,validate_sample
from sd_storage import SDStorage
class HardwareTests(unittest.TestCase):
 def oil_config(self):
  return Configuration(signals=[Signal(name='OilTemp',unit='°C',channel=2,can_id=0x600,byte_offset=0,data_type='int16',scale=.01,conversion='sensorhub_oiltemp')])
 def oil_sample(self,decoder,packets,stamp=2000):
  batch={'rows':[[1,stamp,'']],'can':[[at,2,0x600,0,0,data] for at,data in packets]}
  state=self.state();state['mcu_ms']=stamp
  return decoder.decode(state,batch,self.oil_config())[0][0]
 def test_pic_oiltemp_open_invalidates_prior_temperature_and_recovers(self):
  decoder=HardwareDecoder();valid=struct.pack('<hHI',2365,2065,10172).hex();opened=struct.pack('<hHI',-32768,4094,0xffffffff).hex()
  sample=self.oil_sample(decoder,[(1990,valid),(2010,opened)],2000)
  self.assertAlmostEqual(sample['can_signals']['OilTemp'],23.65)
  sample=self.oil_sample(decoder,[],2020)
  self.assertIsNone(sample['can_signals']['OilTemp']);self.assertEqual(sample['can_signals']['OilTempOpen'],1)
  self.assertEqual(sample['can_states']['OilTemp'],{'code':1,'label':'オープン'})
  sample=self.oil_sample(decoder,[(2030,valid)],2040)
  self.assertAlmostEqual(sample['can_signals']['OilTemp'],23.65);self.assertEqual(sample['can_signals']['OilTempState'],0)
 def test_pic_oiltemp_short_bad_frame_timeout_and_mcu_reset(self):
  decoder=HardwareDecoder()
  sample=self.oil_sample(decoder,[(1990,struct.pack('<hHI',-32768,0,0).hex())])
  self.assertEqual(sample['can_states']['OilTemp']['code'],2);self.assertIsNone(sample['can_signals']['OilTemp'])
  for payload in ('0080',struct.pack('<hHI',-32768,2048,0xffffffff).hex(),struct.pack('<hHI',2500,4095,10000).hex()):
   sample=self.oil_sample(decoder,[(2010,payload)],2020)
   self.assertEqual(sample['can_states']['OilTemp']['code'],3);self.assertIsNone(sample['can_signals']['OilTemp'])
  sample=self.oil_sample(decoder,[],3020)
  self.assertEqual(sample['can_states']['OilTemp']['code'],4);self.assertIsNone(sample['can_signals']['OilTempOpen'])
  sample=self.oil_sample(decoder,[],10)
  self.assertEqual(sample['can_states']['OilTemp']['code'],4)
 def test_pic_oiltemp_layout_and_channel_name_validation(self):
  oil=self.oil_config().signals[0]
  for bad in ({'channel':1},{'scale':1},{'data_type':'uint16'},{'byte_offset':1},{'endian':'big'}):
   with self.assertRaises(ValueError):Signal(**{**oil.model_dump(),**bad})
  with self.assertRaises(ValueError):Configuration(signals=[oil,Signal(name='OilTempOpen',can_id=0x123)])
 def defi_config(self):
  return Configuration(signals=[Signal(name=name,unit='V',channel=2,can_id=0x580,byte_offset=at,data_type='uint16',scale=5/4095,conversion='defi_volt') for name,at in (('PressVolt',0),('Temp1Volt',2),('Temp2Volt',4))])
 def defi_frame(self,press,temp1,temp2,flags=None,version=1):
  if flags is None:flags=sum(1<<i for i,adc in enumerate((press,temp1,temp2)) if adc<=4)|sum(1<<3+i for i,adc in enumerate((press,temp1,temp2)) if adc>=4091)
  return struct.pack('<3HBB',press,temp1,temp2,flags,version).hex()
 def defi_sample(self,decoder,frames,stamp=2000):
  # frames: (mcu_ms, channel, id, extended, rtr, hex)
  batch={'rows':[[1,stamp,'']],'can':[list(f) for f in frames]}
  state=self.state();state['mcu_ms']=stamp
  return decoder.decode(state,batch,self.defi_config())[0][0]
 def test_defi_voltage_packet_from_handoff_example(self):
  # lintaroh_answer_20261101_defi_volt.md: PRESS=0, TEMP1=2048, TEMP2=4095 -> 00 00 00 08 FF 0F 21 01
  self.assertEqual(self.defi_frame(0,2048,4095),'00000008ff0f2101')
  s=self.defi_sample(HardwareDecoder(),[(1990,2,0x580,0,0,'00000008ff0f2101')])
  self.assertEqual(s['can_signals']['PressVolt'],0);self.assertAlmostEqual(s['can_signals']['Temp1Volt'],2.501,places=3);self.assertAlmostEqual(s['can_signals']['Temp2Volt'],5)
  self.assertEqual({k:v['label'] for k,v in s['can_states'].items()},{'PressVolt':'下限付近','Temp1Volt':'未校正','Temp2Volt':'上限付近'})
  self.assertEqual([s['can_signals'][n+'State'] for n in ('PressVolt','Temp1Volt','Temp2Volt')],[1,0,2])
  self.assertNotIn('PressVoltOpen',s['can_signals'])  # a rail flag never proves an open/short
 def test_defi_voltage_rail_boundaries(self):
  for adc,code in ((4,1),(5,0),(4090,0),(4091,2)):
   s=self.defi_sample(HardwareDecoder(),[(1990,2,0x580,0,0,self.defi_frame(adc,2048,2048))])
   self.assertEqual(s['can_states']['PressVolt']['code'],code,adc);self.assertAlmostEqual(s['can_signals']['PressVolt'],adc*5/4095)
 def test_defi_voltage_bad_frames_never_keep_the_previous_value(self):
  good=self.defi_frame(1000,2000,3000)
  bad=[good[:14],good+'00',self.defi_frame(1000,2000,3000,version=2),self.defi_frame(1000,2000,3000,version=0),
   struct.pack('<3HBB',4096,2000,3000,0,1).hex(),struct.pack('<3HBB',1000,2000,3000,0x40,1).hex(),struct.pack('<3HBB',1000,2000,3000,0x80,1).hex(),
   struct.pack('<3HBB',1000,2000,3000,0x01,1).hex(),struct.pack('<3HBB',4,2000,3000,0,1).hex(),struct.pack('<3HBB',1000,2000,4095,0,1).hex(),
   struct.pack('<3HBB',1000,2000,3000,0x08,1).hex()]
  for payload in bad:
   decoder=HardwareDecoder();self.defi_sample(decoder,[(1980,2,0x580,0,0,good)],1985)
   s=self.defi_sample(decoder,[(1990,2,0x580,0,0,payload)])
   self.assertEqual({v['code'] for v in s['can_states'].values()},{3},payload)
   self.assertEqual([s['can_signals'][n] for n in ('PressVolt','Temp1Volt','Temp2Volt')],[None]*3,payload)
  s=self.defi_sample(decoder,[(2010,2,0x580,0,0,good)],2020)
  self.assertAlmostEqual(s['can_signals']['Temp2Volt'],3000*5/4095);self.assertEqual(s['can_states']['Temp2Volt']['code'],0)
 def test_defi_voltage_ignores_rtr_extended_id_and_can1(self):
  for frame in ((1990,2,0x580,0,1,''),(1990,2,0x580,1,0,self.defi_frame(1000,2000,3000)),(1990,1,0x580,0,0,self.defi_frame(1000,2000,3000))):
   s=self.defi_sample(HardwareDecoder(),[frame])
   self.assertEqual(s['can_states']['PressVolt'],{'code':4,'label':'通信途絶'},frame);self.assertIsNone(s['can_signals']['PressVolt'])
 def test_defi_voltage_timeout_and_mcu_reset(self):
  decoder=HardwareDecoder();good=self.defi_frame(1000,2000,3000)
  s=self.defi_sample(decoder,[(1990,2,0x580,0,0,good)],2990);self.assertEqual(s['can_states']['PressVolt']['code'],0)  # 1.0 s old: still fresh
  s=self.defi_sample(decoder,[],2991);self.assertEqual(s['can_states']['PressVolt']['code'],4);self.assertIsNone(s['can_signals']['PressVolt'])
  self.defi_sample(decoder,[(2995,2,0x580,0,0,good)],3000)
  s=self.defi_sample(decoder,[],10)  # MCU restarted: the frame from before is not current
  self.assertEqual(s['can_signals']['PressVoltState'],4);self.assertIsNone(s['can_signals']['PressVolt'])
 def test_defi_voltage_layout_and_columns(self):
  from models import signal_columns
  sig=self.defi_config().signals[0]
  for bad in ({'channel':1},{'extended':True,'can_id':0x580},{'byte_offset':1},{'byte_offset':6},{'data_type':'int16'},{'endian':'big'},{'scale':0},{'scale':-1}):
   with self.assertRaises(ValueError):Signal(**{**sig.model_dump(),**bad})
  Signal(**{**sig.model_dump(),'scale':1,'unit':''})  # ADC counts are allowed too
  with self.assertRaises(ValueError):Configuration(signals=[sig,Signal(name='PressVoltState',can_id=0x123)])
  self.assertEqual(signal_columns(self.defi_config()),['PressVolt','PressVoltState','Temp1Volt','Temp1VoltState','Temp2Volt','Temp2VoltState'])
  self.assertEqual(Configuration.model_validate_json(self.defi_config().model_dump_json()),self.defi_config())
 def test_gnss_cadence_does_not_halve_when_status_skips_one_solution(self):
  decoder=HardwareDecoder();state=self.state();nav=bytearray(92);nav[20]=3;nav[21]=1
  for itow,expected in [(1000,None),(1100,10),(1300,10),(1500,10)]:
   struct.pack_into('<I',nav,0,itow);state.update(nav=nav.hex(),gnss_at=1900)
   samples,_=decoder.decode(state,self.batch(),Configuration())
   self.assertEqual(samples[0]['values']['GNSSHz'],expected)
 def state(self):return {'mcu_ms':2000,'gnss_at':0,'nav':'00'*92,'imu_address':40,'sd_ready':1,'can_counts':[0,0]}
 def batch(self):
  raw=bytearray(46);struct.pack_into('<h',raw,4,981);struct.pack_into('<h',raw,24,16384)
  return {'rows':[[1,2000,raw.hex()]],'can':[]}
 def test_absent_gps_vehicle_channels_and_finite_imu(self):
  samples,sensors=HardwareDecoder().decode(self.state(),self.batch(),Configuration())
  s=validate_sample(samples[0]);self.assertIsNone(s['values']['RPM']);self.assertIsNone(s['values']['Lat']);self.assertAlmostEqual(s['values']['AccelZ'],9.81);self.assertEqual(s['quaternion'],[1,0,0,0])
 def test_full_sd_card_says_it_keeps_recording(self):
  # 2026-11-07: the MCU removes the oldest EL files when the card is full and reports how many
  state=self.state();state.update(sd_mounted=1,sd_logging=1,sd_file=4801)
  _,sensors=HardwareDecoder().decode(state,self.batch(),Configuration());self.assertEqual(sensors['sd'],'記録中 EL004801.BIN')
  state['sd_deleted']=3
  _,sensors=HardwareDecoder().decode(state,self.batch(),Configuration())
  self.assertEqual(sensors['sd'],'記録中 EL004801.BIN（いっぱいのため古い順に3本消して記録中）')
 def test_missing_imu_keeps_real_time_and_gnss(self):
  state=self.state();state['imu_address']=0
  samples,_=HardwareDecoder().decode(state,{'rows':[[1,2000,'']],'can':[]},Configuration())
  self.assertEqual(samples[0]['mcu_ms'],2000);self.assertIsNone(samples[0]['values']['AccelZ']);self.assertIsNone(samples[0]['quaternion'])
 def test_fix_validity_and_expiration(self):
  state=self.state();nav=bytearray(92);nav[20]=3;nav[21]=1;nav[23]=19;struct.pack_into('<i',nav,28,350000000);state.update(nav=nav.hex(),gnss_at=1900)
  decoder=HardwareDecoder();s,_=decoder.decode(state,self.batch(),Configuration());self.assertEqual(s[0]['values']['Lat'],35)
  state['mcu_ms']=4000;s,_=decoder.decode(state,self.batch(),Configuration());self.assertIsNone(s[0]['values']['Lat'])
 def test_signed_extended_can_and_expiration(self):
  config=Configuration(signals=[Signal(name='RPM',channel=2,can_id=0x1234,extended=True,byte_offset=0,data_type='int16',scale=.25)])
  batch=self.batch();batch['can']=[[1990,2,0x1234,1,0,'fcff']]
  decoder=HardwareDecoder();s,_=decoder.decode(self.state(),batch,config);self.assertEqual(s[0]['values']['RPM'],-1)
  batch['can']=[];batch['rows'][0][1]=4000;s,_=decoder.decode(self.state(),batch,config);self.assertIsNone(s[0]['values']['RPM'])
 def test_sensor_hub_ntc_oil_temperature(self):
  # 10 kΩ pull-up, beta-like sensor: 25 °C = 10 kΩ, 85 °C = 1.1 kΩ.
  oil=Signal(name='OilTemp',unit='°C',channel=2,can_id=0x500,byte_offset=2,data_type='uint16',scale=1/65535,conversion='ntc',pullup_ohm=10000,ntc_points=[(85,1100),(25,10000)])
  self.assertAlmostEqual(oil.ntc_celsius(.5),25,places=6)            # R = 10 kΩ
  self.assertAlmostEqual(oil.ntc_celsius(1100/11100),85,places=6)    # R = 1.1 kΩ
  self.assertTrue(25<oil.ntc_celsius(.3)<85);self.assertLess(oil.ntc_celsius(.7),25)  # between / colder (extrapolated)
  self.assertIsNone(oil.ntc_celsius(0));self.assertIsNone(oil.ntc_celsius(1))      # shorted / open
  frame=bytes([0,0])+int(.5*65535).to_bytes(2,'little')+bytes([7,1])
  batch=self.batch();batch['can']=[[1990,2,0x500,0,0,frame.hex()],[1991,1,0x500,0,0,'00000000']]
  s,_=HardwareDecoder().decode(self.state(),batch,Configuration(signals=[oil]))
  self.assertAlmostEqual(s[0]['can_signals']['OilTemp'],25,places=2)
  batch['can']=[[1990,2,0x500,0,0,(bytes(2)+(65535).to_bytes(2,'little')+bytes(2)).hex()]]
  s,_=HardwareDecoder().decode(self.state(),batch,Configuration(signals=[oil]))
  self.assertIsNone(s[0]['can_signals'].get('OilTemp'))  # open circuit is not a temperature
  for bad in ({'pullup_ohm':None},{'ntc_points':[(25,10000)]},{'ntc_points':[(25,1000),(85,2000)]}):
   with self.assertRaises(ValueError):Signal(**{**oil.model_dump(),**bad})
  self.assertEqual(Configuration.model_validate_json(Configuration(signals=[oil]).model_dump_json()).signals[0],oil)
 def test_sd_copy_real_fat_preserves_existing_file(self):
  from pyfatfs.PyFat import PyFat
  from pyfatfs.PyFatFS import PyFatFS
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);image=folder/'fat.img';image.touch();fat=PyFat();fat.mkfs(str(image),fat_type=32,size=64*1024*1024);fat.close()
   with PyFatFS(str(image)) as fs:fs.writetext('/KEEP.TXT','existing data')
   mbr=bytearray(512);mbr[450]=0x0c;struct.pack_into('<II',mbr,454,2048,image.stat().st_size//512);mbr[510:]=b'\x55\xaa'
   scratch=bytearray(512)
   def call(text):
    if text=='SD':return 'SD ready'
    if text.startswith('H'):
     at,data=text[1:].split(':');data=bytes.fromhex(data);scratch[int(at):int(at)+len(data)]=data;return 'loaded'
    if text.startswith('R'):
     sector=int(text[1:])
     if sector==0:return 'data:'+mbr.hex()
     with image.open('rb') as f:f.seek((sector-2048)*512);return 'data:'+f.read(512).hex()
    if text.startswith('W'):
     with image.open('r+b') as f:f.seek((int(text[1:])-2048)*512);f.write(scratch)
     return 'write_token=0x05 accepted=1 busy_done=1'
    raise AssertionError(text)
   source=folder/'LOG_TEST.csv';source.write_text('seq,value\n1,9.81\n');storage=SDStorage(folder/'journals');storage.status={};storage.copy(source,call)
   self.assertTrue(storage.status['verified'])
   with PyFatFS(str(image),read_only=True) as fs:
    self.assertEqual(fs.readtext('/KEEP.TXT'),'existing data');self.assertEqual(fs.readbytes('/ECOLOG/LOG_TEST.csv'),source.read_bytes())
 def test_can_batch_uses_value_at_each_sample_not_future_frame(self):
  config=Configuration(signals=[Signal(name='RPM',channel=1,can_id=256,byte_offset=0,data_type='uint16')])
  decoder=HardwareDecoder();batch=self.batch()
  batch['can']=[[1990,1,256,0,0,'e803'],[2020,1,256,0,0,'d007']]
  batch['rows']=[[1,2000,''],[2,2030,'']]
  samples,_=decoder.decode(self.state(),batch,config)
  self.assertEqual([s['values']['RPM'] for s in samples],[1000,2000])
  batch={'can':[[2050,1,256,0,0,'b80b']], 'rows':[[3,2040,''],[4,2060,''],[5,3100,'']]}
  samples,_=decoder.decode(self.state(),batch,config)
  self.assertEqual([s['values']['RPM'] for s in samples],[2000,3000,None])
