"""Async, read-only MessagePack-RPC client for Arduino Router's local socket."""
import asyncio
import msgpack
import json


class TelemetryBridge:
    def __init__(self, path='/var/run/arduino-router.sock'):
        self.path = path
        self.reader = self.writer = None
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.command_lock = asyncio.Lock()
        self.next_sector = None

    async def close(self):
        if self.writer:
            self.writer.close()
        self.reader = self.writer = None
        self.next_sector = None

    async def read(self):
        return await self.call("ecologger.read")

    async def call(self, method, args=None):
        async with self.lock:
            return await self._call(method, args or [])

    async def _call(self, method, args):
        try:
            async with asyncio.timeout(5):
                self.sequence += 1
                packet=msgpack.packb([0,self.sequence,method,args])
                if len(packet)>64:
                    raise ValueError('MCU request exceeds the 64-byte UART receive buffer')
                if self.writer is None:
                    self.reader, self.writer = await asyncio.open_unix_connection(self.path)
                self.writer.write(packet)
                await self.writer.drain()
                unpacker = msgpack.Unpacker(raw=False, max_buffer_size=65536)
                while True:
                    chunk = await self.reader.read(4096)
                    if not chunk:
                        raise ConnectionError('Arduino Router disconnected')
                    unpacker.feed(chunk)
                    for reply in unpacker:
                        if not isinstance(reply, list) or len(reply) != 4 or reply[:2] != [1, self.sequence]:
                            raise ValueError('Unexpected Arduino Router response')
                        if reply[2] is not None:
                            raise ValueError(f'Arduino Router: {reply[2]}')
                        return reply[3]
        except BaseException:
            await self.close()
            raise

    async def sector(self, lba):
        async with self.command_lock:
            if lba != self.next_sector:
                if await self._command('R'+str(lba))!='sector ready':raise OSError('SD sector not ready')
            value=await self.call('logger.sdread')
            if not isinstance(value,str) or len(value)!=1024:
                self.next_sector=None
                raise OSError('SD read failed: '+str(value))
            self.next_sector=lba+1
            return 'data:'+value

    async def command(self, text):
        async with self.command_lock:
            self.next_sector=None
            return await self._command(text)

    async def _command(self, text):
        before=json.loads(await self.call('logger.status'))['completed']
        if await self.call('logger.command',[text]) != 0:
            raise RuntimeError('MCU command queue is busy')
        for _ in range(1000):
            await asyncio.sleep(.02)
            state=json.loads(await self.call('logger.status'))
            if state['completed'] != before:return state['result']
        raise TimeoutError('MCU command did not complete')
