from service_client import Client
import pathlib,json,struct,hashlib,os
c=Client();base=pathlib.Path('/data/bench-20261001');report={};restore=None
def read(sector):
 r=c.command('R'+str(sector));assert r['result'].startswith('data:'),r
 b=bytes.fromhex(r['result'][5:]);assert len(b)==512;return b
def write(sector,data):
 r=c.command('W'+str(sector)+':'+data.hex());assert 'accepted=1 busy_done=1' in r['result'],r;return r['result']
def u16(b,n):return struct.unpack_from('<H',b,n)[0]
def u32(b,n):return struct.unpack_from('<I',b,n)[0]
try:
 report['init']=c.command('SD')['result'];assert 'ready=1' in report['init']
 csd=bytes.fromhex(report['init'].split('csd=')[1]);assert csd[0]>>6==1
 report['capacity_bytes']=((((csd[7]&63)<<16)|(csd[8]<<8)|csd[9])+1)*512*1024
 mbr=read(0);assert mbr[-2:]==b'\x55\xaa';(base/'sd_sector0.bin').write_bytes(mbr)
 if u16(mbr,11)==512 and mbr[13] in [1,2,4,8,16,32,64,128]:start=0;vbr=mbr
 else:
  partitions=[]
  for i in range(4):
   o=446+16*i;partitions.append({'type':mbr[o+4],'lba':u32(mbr,o+8),'sectors':u32(mbr,o+12)})
  report['partitions']=partitions;part=next(p for p in partitions if p['sectors'] and p['type'] in [0xb,0xc,6,0xe]);start=part['lba'];vbr=read(start)
 assert u16(vbr,11)==512 and vbr[-2:]==b'\x55\xaa'
 spc=vbr[13];reserved=u16(vbr,14);fats=vbr[16];fat_size=u16(vbr,22) or u32(vbr,36);root_entries=u16(vbr,17);total=u16(vbr,19) or u32(vbr,32)
 root_sectors=(root_entries*32+511)//512;data_start=start+reserved+fats*fat_size+root_sectors;clusters=(total-reserved-fats*fat_size-root_sectors)//spc;fat32=clusters>=65525;fat_start=start+reserved
 report['filesystem']={'type':'FAT32' if fat32 else 'FAT16','partition_lba':start,'total_sectors':total,'sectors_per_cluster':spc,'data_clusters':clusters,'fat_copies':fats}
 assert fat32,'Write test limited to recognized FAT32'
 root_cluster=u32(vbr,44);root=read(data_start+(root_cluster-2)*spc);report['root_directory_read']=True;report['root_entries_in_first_sector']=sum(root[i] not in (0,0xe5) and root[i+11]!=15 for i in range(0,512,32))
 info=read(start+u16(vbr,48));hint=u32(info,492) if info[:4]==b'RRaA' and info[484:488]==b'rrAa' else 3
 if not 2<=hint<clusters+2:hint=3
 candidates=[hint,3,130,258,386,514];free=None
 for candidate in candidates:
  index=candidate//128;fat=read(fat_start+index)
  for offset in range(candidate%128,128):
   cl=index*128+offset
   if cl>=3 and cl<clusters+2 and u32(fat,offset*4)&0xfffffff==0:
    if all(u32(read(fat_start+copy*fat_size+index),offset*4)&0xfffffff==0 for copy in range(1,fats)):
     free=cl;break
  if free is not None:break
 if free is None:
  assert start>0 and report.get('partitions') and not any(p['type']==0xee for p in partitions)
  sector=max(p['lba']+p['sectors'] for p in partitions if p['sectors'])+8
  assert sector<report['capacity_bytes']//512 and all(not(p['lba']<=sector<p['lba']+p['sectors']) for p in partitions if p['sectors'])
 else:sector=data_start+(free-2)*spc
 original=read(sector);backup=base/f'sd_scratch_sector_{sector}_backup.bin'
 with backup.open('xb') as f:f.write(original);f.flush();os.fsync(f.fileno())
 report['scratch']={'cluster':free,'sector':sector,'location':'unpartitioned area' if free is None else 'free FAT cluster','original_sha256':hashlib.sha256(original).hexdigest(),'backup':str(backup)}
 pattern=b''.join(hashlib.sha256(b'Logger_V2 SD check 20261001'+struct.pack('<I',i)).digest() for i in range(16))
 restore=(sector,original);report['test_write']=write(sector,pattern);actual=read(sector);report['test_readback_matches']=actual==pattern;assert actual==pattern
finally:
 if restore:
  try:
   report['restore_write']=write(*restore);report['original_restored']=read(restore[0])==restore[1]
  except Exception as e:report['restore_error']=str(e)
 (base/'sd_checks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
