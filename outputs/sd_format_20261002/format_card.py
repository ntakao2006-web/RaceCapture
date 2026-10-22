import asyncio,json,struct,time,sys
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
async def main():
    b=TelemetryBridge()
    print('stop:',await b.command('LOG0'),flush=True)
    before=json.loads(await b.call('logger.status'))['completed']
    assert await b.call('logger.command',['FORMAT16'])==0
    started=time.monotonic()
    while time.monotonic()-started<900:
        await asyncio.sleep(2)
        state=json.loads(await b.call('logger.status'))
        if state['completed']!=before:break
    assert state['result']=='FORMAT_OK_31116288_SECTORS',state['result']
    print('formatted:',state['result'],int(time.monotonic()-started),'seconds',flush=True)
    async def read(lba):return bytes.fromhex((await b.sector(lba))[5:])
    m=await read(0);assert m[510:]==b'\x55\xaa'
    start,size=struct.unpack_from('<II',m,454);assert (start,size)==(2048,31114240)
    boot=await read(start);assert boot==await read(start+6)
    spc=boot[13];reserved=struct.unpack_from('<H',boot,14)[0];fs=struct.unpack_from('<I',boot,36)[0]
    assert boot[11:13]==b'\x00\x02' and spc==64 and reserved==32 and boot[16]==2
    assert struct.unpack_from('<I',boot,32)[0]==size
    a=await read(start+reserved);c=await read(start+reserved+fs)
    assert a==c and struct.unpack_from('<III',a)==(0x0ffffff8,0xffffffff,0x0fffffff)
    assert a[12:]==bytes(500)
    db=start+reserved+2*fs
    for i in range(spc):assert await read(db+i)==bytes(512)
    assert await read(31116287)==bytes(512)
    assert await b.command('FILES')=='[]'
    result=dict(total_bytes=31116288*512,partition_bytes=size*512,cluster_bytes=spc*512,fat_sectors=fs,root_empty=True,last_sector_read_write_verified=True,recording=False)
    print(json.dumps(result),flush=True)
    await b.close()
asyncio.run(main())
