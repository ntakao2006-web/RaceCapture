import asyncio,json,tempfile,unittest
from pathlib import Path
import msgpack
from telemetry_bridge import TelemetryBridge
class BridgeTests(unittest.IsolatedAsyncioTestCase):
 async def test_fragmented_reply_and_reconnect(self):
  connections=0
  async def handle(reader,writer):
   nonlocal connections
   connections+=1
   data=msgpack.unpackb(await reader.read(4096),raw=False)
   self.assertEqual(data[2:],["ecologger.read",[]])
   result=msgpack.packb([1,data[1],None,json.dumps({'seq':connections})])
   writer.write(result[:3]);await writer.drain();await asyncio.sleep(.01);writer.write(result[3:]);await writer.drain();writer.close()
  with tempfile.TemporaryDirectory() as folder:
   path=str(Path(folder)/'router.sock');server=await asyncio.start_unix_server(handle,path)
   async with server:
    client=TelemetryBridge(path)
    self.assertEqual(json.loads(await client.read())['seq'],1)
    with self.assertRaises(ConnectionError):await client.read()
    self.assertEqual(json.loads(await client.read())['seq'],2)
    await client.close()
 async def test_timeout(self):
  client=TelemetryBridge('/no-such-ecocapture-socket')
  with self.assertRaises(OSError):await client.read()
  self.assertIsNone(client.writer)
 async def test_uart_limit_rejects_oversized_request_before_connecting(self):
  client=TelemetryBridge('/no-such-ecocapture-socket')
  with self.assertRaisesRegex(ValueError,'64-byte'):
   await client.call('logger.command',['H0:'+'ff'*128])
  self.assertIsNone(client.writer)
  self.assertLessEqual(len(msgpack.packb([0,0xffffffff,'logger.command',['H496:'+'ff'*16]])),64)
 async def test_sector_stream_seeks_and_invalidates_after_commands_and_reconnect(self):
  class FakeCardBridge(TelemetryBridge):
   def __init__(self):super().__init__();self.cursor=0;self.seeks=[]
   async def _command(self,text):
    if text.startswith('R'):
     self.cursor=int(text[1:]);self.seeks.append(self.cursor);return 'sector ready'
    self.cursor=0;return 'loaded'
   async def call(self,method,args=None):
    self.assert_method=method
    data=bytes([self.cursor%256])*512;self.cursor+=1;return data.hex()
  card=FakeCardBridge()
  for sector in (100,101,200):
   self.assertEqual(await card.sector(sector),'data:'+(bytes([sector])*512).hex())
  self.assertEqual(card.seeks,[100,200])
  await card.command('H0:00')
  self.assertEqual(await card.sector(201),'data:'+(b'\xc9'*512).hex())
  await card.close();card.cursor=0
  self.assertEqual(await card.sector(202),'data:'+(b'\xca'*512).hex())
  self.assertEqual(card.seeks,[100,200,201,202])
if __name__=='__main__':unittest.main()
