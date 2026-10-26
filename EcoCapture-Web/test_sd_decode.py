import csv,io,struct,tempfile,unittest,zlib
from pathlib import Path
from sd_decode import FIELDS,convert,records
class SDDecodeTests(unittest.TestCase):
    def block(self):
        b=bytearray(512);b[:4]=b'ELB2';struct.pack_into('<IIH',b,4,1,0,68)
        struct.pack_into('<BBI',b,16,1,46,100);struct.pack_into('<I',b,508,zlib.crc32(b[:508]));return b
    def test_record_and_crc(self):
        b=self.block();self.assertEqual(list(records(io.BytesIO(b))),[(1,100,bytes(46))])
        b[30]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):list(records(io.BytesIO(b)))
    def test_missing_block(self):
        b=self.block();struct.pack_into('<I',b,8,1);struct.pack_into('<I',b,508,zlib.crc32(b[:508]))
        with self.assertRaisesRegex(ValueError,'Missing'):list(records(io.BytesIO(b)))
    def test_partial_block(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):list(records(io.BytesIO(self.block()[:200])))
    def log(self,items):
        """One SD block holding (kind,stamp,payload) records."""
        b=bytearray(512);b[:4]=b'ELB2';pos=16
        for kind,stamp,data in items:
            struct.pack_into('<BBI',b,pos,kind,len(data),stamp);b[pos+6:pos+6+len(data)]=data;pos+=6+len(data)
        struct.pack_into('<IIH',b,4,1,0,pos);struct.pack_into('<I',b,508,zlib.crc32(b[:508]));return bytes(b)
    def can(self,stamp,can_id,payload,channel=2):
        return (3,stamp,bytes([channel])+struct.pack('<I',can_id)+bytes([0,len(payload)])+payload)
    def imu(self,stamp):return (1,stamp,bytes(46))
    def decode(self,items,config=None):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'EL000001.BIN';source.write_bytes(self.log(items))
            convert(source,Path(tmp)/'out.csv',config)
            with open(Path(tmp)/'out.csv',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
    def test_without_config_columns_are_unchanged(self):
        rows=self.decode([self.can(5,0x600,struct.pack('<hHI',2365,2065,10172)),self.imu(10)])
        self.assertEqual(list(rows[0]),FIELDS)
    def test_config_adds_oil_temperature_and_state_columns(self):
        from models import Configuration,Signal
        config=Configuration(signals=[Signal(name='OilTemp',unit='°C',channel=2,can_id=0x600,byte_offset=0,data_type='int16',scale=.01,conversion='sensorhub_oiltemp'),
                                      Signal(name='RPM',channel=1,can_id=0x201,byte_offset=0,data_type='uint16',endian='big',scale=.25)])
        opened=struct.pack('<hHI',-32768,4094,0xffffffff)
        rows=self.decode([self.imu(0),self.can(5,0x600,struct.pack('<hHI',6016,1700,13000)),self.can(6,0x201,(4000).to_bytes(2,'big')+bytes(6),channel=1),
                          self.can(7,0x201,bytes(8)),  # right ID on the wrong bus is not RPM
                          self.imu(10),self.can(20,0x600,opened),self.imu(30),self.imu(1100)],config)
        self.assertEqual(list(rows[0])[len(FIELDS):],['OilTemp','OilTempState','RPM'])
        self.assertEqual((rows[0]['OilTemp'],rows[0]['OilTempState'],rows[0]['RPM']),('','4',''))   # before any frame
        self.assertAlmostEqual(float(rows[1]['OilTemp']),60.16);self.assertEqual(rows[1]['OilTempState'],'0');self.assertEqual(rows[1]['RPM'],'1000.0')
        self.assertEqual((rows[2]['OilTemp'],rows[2]['OilTempState']),('','1'))                     # open sensor is not a temperature
        self.assertEqual((rows[3]['OilTempState'],rows[3]['RPM']),('4',''))                        # >1 s without a frame
    def test_mcu_restart_drops_previous_values(self):
        from models import Configuration,Signal
        config=Configuration(signals=[Signal(name='Boost',channel=2,can_id=0x500,byte_offset=0,data_type='uint8')])
        rows=self.decode([self.can(5000,0x500,bytes([7])),self.imu(5010),self.imu(20)],config)
        self.assertEqual([r['Boost'] for r in rows],['7',''])
    def test_shared_decoder_carries_values_across_files(self):
        from models import Configuration,Signal
        from sd_decode import new_decoder
        config=Configuration(signals=[Signal(name='OilTemp',unit='°C',channel=2,can_id=0x600,byte_offset=0,data_type='int16',scale=.01,conversion='sensorhub_oiltemp')])
        decoder=new_decoder()
        with tempfile.TemporaryDirectory() as tmp:
            for n,items in enumerate(([self.can(5,0x600,struct.pack('<hHI',6016,1700,13000)),self.imu(10)],[self.imu(110)])):
                source=Path(tmp)/f'EL{n:06}.BIN';source.write_bytes(self.log(items));convert(source,Path(tmp)/f'{n}.csv',config,decoder)
            with open(Path(tmp)/'1.csv',encoding='utf-8',newline='') as f:row=next(csv.DictReader(f))
        self.assertEqual((row['OilTemp'],row['OilTempState']),('60.16','0'))   # rounded, and still fresh in the next file
    def test_signal_name_must_not_hide_an_sd_column(self):
        from models import Configuration,Signal
        with self.assertRaisesRegex(ValueError,'clashes'):self.decode([self.imu(0)],Configuration(signals=[Signal(name='GPSSpeed',can_id=0x100,byte_offset=0)]))
if __name__=='__main__':unittest.main()
