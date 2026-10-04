"""Reject formatting if the SD root contains anything except logger EL files."""
import asyncio,json,struct,sys,re
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
async def main():
    b=TelemetryBridge()
    assert await b.command('LOG0')=='stopped'
    async def sector(n):
        r=await b.sector(n);assert r.startswith('data:');return bytes.fromhex(r[5:])
    m=await sector(0);part,size=struct.unpack_from('<II',m,454)
    assert (part,size)==(2048,31114240)
    boot=await sector(part);spc=boot[13];fat=part+struct.unpack_from('<H',boot,14)[0]
    base=fat+boot[16]*struct.unpack_from('<I',boot,36)[0];cluster=struct.unpack_from('<I',boot,44)[0]
    count=0;seen=set()
    while cluster<0xffffff8:
        assert cluster>=2 and cluster not in seen and len(seen)<128
        seen.add(cluster)
        for i in range(spc):
            block=await sector(base+(cluster-2)*spc+i)
            for p in range(0,512,32):
                e=block[p:p+32]
                if e[0]==0:
                    print(json.dumps({'only_logger_files':True,'files':count}));await b.close();return
                if e[0]==0xe5:continue
                assert re.fullmatch(rb'EL[0-9]{6}BIN',e[:11]) and e[11]==32,repr(e[:12])
                count+=1
        f=await sector(fat+cluster//128);cluster=struct.unpack_from('<I',f,(cluster%128)*4)[0]&0xfffffff
    print(json.dumps({'only_logger_files':True,'files':count}));await b.close()
asyncio.run(main())
