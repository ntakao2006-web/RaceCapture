"""Stamp existing EL logger directory entries, without renaming or touching data/FAT.

Caller must stop recording, reserve the SD operation and hold record_lock.
Each directory-sector original is durably journaled before writing and read back.
"""
import json
import os
import struct
from datetime import datetime, timedelta, timezone

def stamp_entry(entry, started, ended):
    out=bytearray(entry)
    def packed(dt):
        dt=dt.astimezone(timezone(timedelta(hours=9)))
        if not 1980<=dt.year<=2107:raise ValueError('FAT date out of range')
        return (dt.hour<<11)|(dt.minute<<5)|(dt.second//2), ((dt.year-1980)<<9)|(dt.month<<5)|dt.day
    ct,cd=packed(started);mt,md=packed(ended)
    struct.pack_into('<HHH',out,14,ct,cd,md)
    struct.pack_into('<HH',out,22,mt,md)
    return bytes(out)

async def stamp_logs(bridge, first, last, started, ended, journal_path):
    if not 0<first<=last<=999999 or last-first>4096:raise ValueError('Invalid log range')
    async with bridge.command_lock:
        bridge.next_sector=None
        async def read(lba):
            if await bridge._command('R'+str(lba))!='sector ready':raise OSError('SD read rejected')
            value=bytes.fromhex(await bridge.call('logger.sdread'))
            if len(value)!=512:raise OSError('Short SD sector')
            return value
        state=json.loads(await bridge.call('logger.status'))
        if state.get('sd_logging'):raise OSError('Recording still active')
        mbr=await read(0)
        if mbr[510:]!=b'\x55\xaa' or mbr[450] not in (11,12):raise OSError('Expected FAT32 MBR')
        start,size=struct.unpack_from('<II',mbr,454)
        bpb=await read(start)
        spc=bpb[13];reserved=struct.unpack_from('<H',bpb,14)[0]
        fats=bpb[16];fat_size=struct.unpack_from('<I',bpb,36)[0]
        cluster=struct.unpack_from('<I',bpb,44)[0]
        base=start+reserved+fats*fat_size
        if struct.unpack_from('<H',bpb,11)[0]!=512 or not spc or spc&(spc-1) or not fat_size or not 1<=fats<=2 or base>=start+size:
            raise OSError('Invalid FAT32 geometry')
        max_cluster=(start+size-base)//spc+2
        found=set();seen=set()
        journal_path.parent.mkdir(parents=True,exist_ok=True)
        with journal_path.open('a') as journal:
            for _ in range(128):
                if cluster in seen or not 2<=cluster<max_cluster:raise OSError('Invalid root chain')
                seen.add(cluster)
                for offset in range(spc):
                    lba=base+(cluster-2)*spc+offset
                    original=await read(lba);changed=bytearray(original)
                    for pos in range(0,512,32):
                        entry=original[pos:pos+32]
                        if entry[:2]!=b'EL' or entry[8:11]!=b'BIN' or entry[11]!=0x20 or not entry[2:8].isdigit():continue
                        index=int(entry[2:8])
                        if first<=index<=last:
                            changed[pos:pos+32]=stamp_entry(entry,started,ended);found.add(index)
                    if changed!=original:
                        journal.write(json.dumps({'sector':lba,'original':original.hex(),'replacement':changed.hex()})+'\n');journal.flush();os.fsync(journal.fileno())
                        for pos in range(0,512,16):
                            if await bridge._command(f'H{pos}:'+changed[pos:pos+16].hex())!='loaded':raise OSError('SD timestamp upload failed')
                        if 'accepted=1 busy_done=1' not in await bridge._command('W'+str(lba)):raise OSError('SD timestamp write failed')
                        if await read(lba)!=changed:raise OSError('SD timestamp verify failed')
                    if len(found)==last-first+1:return sorted(found)
                fat_lba=start+reserved+(cluster*4)//512
                if fat_lba>=start+reserved+fat_size:raise OSError('FAT outside bounds')
                fat=await read(fat_lba)
                cluster=struct.unpack_from('<I',fat,(cluster*4)%512)[0]&0x0fffffff
                if cluster>=0x0ffffff8:break
        raise OSError('Some session logs were not found')
