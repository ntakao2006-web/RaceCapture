"""Bounded FAT32 copies over MCU SPI. Internal logs remain the authoritative copy."""
import asyncio
import hashlib
import io
import os
import json
import struct
import threading
from pathlib import Path
from collections import OrderedDict

class CardIO(io.RawIOBase):
    def __init__(self, call, start, sectors, journal, progress):
        super().__init__();self.call=call;self.start=start;self.size=sectors*512;self.pos=0
        self.cache=OrderedDict();self.dirty={};self.journal=journal;self.progress=progress
    def readable(self):return True
    def writable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        value=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        if value<0 or value>self.size:raise OSError('SD partition seek outside bounds')
        self.pos=value;return value
    def sector(self,index):
        if index in self.dirty:return self.dirty[index]
        if index in self.cache:return self.cache[index]
        result=self.call('R'+str(self.start+index))
        if not result.startswith('data:'):raise OSError('SD read failed: '+result)
        value=bytes.fromhex(result[5:])
        if len(value)!=512:raise OSError('SD short sector')
        self.cache[index]=value
        self.progress['read_sectors']=self.progress.get('read_sectors',0)+1
        # Keep both FAT copies of the bench card during mount/flush. The old
        # 2 MiB cache evicted the first FAT while loading the second, forcing
        # repeated full-card metadata transfers over RPC. Bound RAM to 8 MiB.
        while len(self.cache)>16384:self.cache.popitem(last=False)
        return value
    def read(self,size=-1):
        if size<0:size=self.size-self.pos
        size=min(size,self.size-self.pos);out=bytearray()
        while size:
            index,offset=divmod(self.pos,512);n=min(size,512-offset)
            out.extend(self.sector(index)[offset:offset+n]);self.pos+=n;size-=n
        return bytes(out)
    def readinto(self,b):
        value=self.read(len(b));b[:len(value)]=value;return len(value)
    def write(self,data):
        data=memoryview(data);total=len(data)
        if self.pos+total>self.size:raise OSError('SD write outside partition')
        while data:
            index,offset=divmod(self.pos,512);n=min(len(data),512-offset)
            old=self.sector(index);new=bytearray(old);new[offset:offset+n]=data[:n]
            if bytes(new)!=old:self.dirty[index]=bytes(new)
            data=data[n:];self.pos+=n
        return total
    def flush(self):
        if not hasattr(self,'dirty'):return
        for index,data in list(self.dirty.items()):
            absolute=self.start+index
            old=self.cache.get(index)
            if old is None:
                result=self.call('R'+str(absolute));old=bytes.fromhex(result[5:])
            self.journal.write(json.dumps({'sector':absolute,'original':old.hex(),'new_sha256':hashlib.sha256(data).hexdigest()})+'\n');self.journal.flush();os.fsync(self.journal.fileno())
            # Serial1's Zephyr RX ring is 64 bytes. A 16-byte upload including
            # RPC headers fits even with a uint32 message id and offset 496.
            for offset in range(0,512,16):
                if self.call(f'H{offset}:'+data[offset:offset+16].hex())!='loaded':raise OSError('SD upload rejected')
            result=self.call('W'+str(absolute))
            if 'accepted=1 busy_done=1' not in result:raise OSError('SD write failed: '+result)
            readback=self.call('R'+str(absolute))
            if readback!='data:'+data.hex():raise OSError('SD write verification failed')
            self.cache[index]=data;del self.dirty[index]
            self.progress['written_sectors']=self.progress.get('written_sectors',0)+1

class SDStorage:
    def __init__(self,root):self.root=Path(root);self.status={'active':False};self.task=None
    def start(self,path,bridge):
        if self.status.get('active'):raise RuntimeError('SD copy already in progress')
        self.status={'active':True,'name':path.name,'written_sectors':0,'error':None,'verified':False}
        loop=asyncio.get_running_loop()
        def call(text):
            action=bridge.sector(int(text[1:])) if text.startswith('R') else bridge.command(text)
            return asyncio.run_coroutine_threadsafe(action,loop).result(30)
        self.task=asyncio.create_task(self.run(path,call))
    async def run(self,path,call):
        try:await asyncio.to_thread(self.copy,path,call)
        except Exception as exc:self.status['error']=str(exc) or type(exc).__name__
        finally:self.status['active']=False
    def copy(self,path,call):
        from pyfatfs.PyFatFS import PyFatBytesIOFS
        if call('SD')!='SD ready':raise OSError('SD not detected')
        mbr=bytes.fromhex(call('R0')[5:])
        if mbr[510:]!=b'\x55\xaa' or mbr[450] not in (0x0b,0x0c):raise OSError('A primary FAT32 partition is required; formatting is not automatic')
        start,sectors=struct.unpack_from('<II',mbr,454)
        if not start or not sectors or start+sectors>0xffffffff:raise OSError('Invalid SD partition')
        self.root.mkdir(exist_ok=True,parents=True)
        with (self.root/(path.name+'.sd-journal.jsonl')).open('w') as journal:
            card=CardIO(call,start,sectors,journal,self.status)
            fs=PyFatBytesIOFS(card,utc=True)
            fs.makedirs('/ECOLOG',recreate=True)
            target='/ECOLOG/'+path.name
            if fs.exists(target):raise OSError('This log already exists on SD')
            with path.open('rb') as source,fs.openbin(target,'w') as dest:
                while chunk:=source.read(65536):dest.write(chunk)
            fs.fs.flush_fat();card.flush()
            with fs.openbin(target,'r') as dest:
                h=hashlib.sha256()
                while chunk:=dest.read(65536):h.update(chunk)
            # Discard cache so verification reads the actual card.
            fs.close()
            self.status['verified']=h.hexdigest()==hashlib.sha256(path.read_bytes()).hexdigest()
            if not self.status['verified']:raise OSError('SD file digest mismatch')
            self.status['sd_path']=target
