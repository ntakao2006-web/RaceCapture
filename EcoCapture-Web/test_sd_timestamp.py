import asyncio
import json
import struct
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sd_timestamp import stamp_logs, stamp_entry

class TimestampTests(unittest.IsolatedAsyncioTestCase):
    def test_jst_date_rollover_and_unrelated_bytes(self):
        entry=bytes(range(32))
        stamp=datetime(2026,12,31,18,59,59,tzinfo=timezone.utc)
        result=stamp_entry(entry,stamp,stamp)
        t,d=struct.unpack_from('<HH',result,14)
        self.assertEqual((1980+(d>>9),(d>>5)&15,d&31),(2027,1,1))
        self.assertEqual((t>>11,(t>>5)&63,(t&31)*2),(3,59,58))
        for i in set(range(32))-set(range(14,20))-set(range(22,26)):
            self.assertEqual(result[i],entry[i])

    async def test_only_matching_directory_entry_changes_and_readback(self):
        sectors={i:bytearray(512) for i in range(8)}
        sectors[0][510:]=b'\x55\xaa';sectors[0][450]=12
        struct.pack_into('<II',sectors[0],454,1,100)
        b=sectors[1];struct.pack_into('<H',b,11,512);b[13]=1;b[16]=1
        struct.pack_into('<H',b,14,1);struct.pack_into('<I',b,36,1);struct.pack_into('<I',b,44,2)
        root=sectors[3];root[:11]=b'EL000001BIN';root[11]=32
        root[32:43]=b'EL000002BIN';root[43]=32
        before=bytes(root)
        class Bridge:
            command_lock=asyncio.Lock()
            next_sector=None
            scratch=bytearray(512)
            async def call(self,method):
                if method=='logger.status':return json.dumps({'sd_logging':0})
                return self.scratch.hex()
            async def _command(self,c):
                if c.startswith('R'):self.scratch=bytearray(sectors[int(c[1:])]);return 'sector ready'
                if c.startswith('H'):
                    off,data=c[1:].split(':');v=bytes.fromhex(data);self.scratch[int(off):int(off)+len(v)]=v;return 'loaded'
                if c.startswith('W'):sectors[int(c[1:])]=bytearray(self.scratch);return 'accepted=1 busy_done=1'
        with tempfile.TemporaryDirectory() as tmp:
            stamp=datetime(2026,10,4,tzinfo=timezone.utc)
            found=await stamp_logs(Bridge(),2,2,stamp,stamp,Path(tmp)/'journal.jsonl')
            self.assertEqual(found,[2]);self.assertEqual(sectors[3][:32],before[:32])
            self.assertEqual(sectors[3][64:],before[64:])
            self.assertEqual(sectors[3][32:64],stamp_entry(before[32:64],stamp,stamp))

if __name__=='__main__':unittest.main()
