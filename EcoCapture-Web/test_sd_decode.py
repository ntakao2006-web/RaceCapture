import io,struct,unittest,zlib
from sd_decode import records
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
if __name__=='__main__':unittest.main()
