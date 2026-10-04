// Explicit maintenance command only. Never invoked by boot or normal recording.
static void format16GB(){
 if(recording||sdLogging){result="FORMAT_RECORDING_REJECTED";return;}
 sdMounted=false;while(sdWorking)delay(1);
 uint8_t csd[16];int r=sdCmd(9,0,1);bool ok=r==0&&sdReadData(csd,16);sdDone();
 uint32_t total=ok&&((csd[0]>>6)==1)?((((uint32_t)csd[7]&63)<<16)|((uint32_t)csd[8]<<8)|csd[9])+1:0;
 total*=1024;
 // This command is deliberately restricted to the identified 16 GB bench card.
 if(!sdReady||!sdHighCapacity||total!=31116288UL){result="FORMAT_CAPACITY_REJECTED";return;}
 uint32_t start=2048,size=total-start,fs=(((size-32)/64+2)*4+511)/512;
 uint32_t db=start+32+2*fs,nc=(total-db)/64;
 // Exercise the physical last sector, then clear the test pattern.
 for(int i=0;i<512;i++)sectorBuf[i]=(uint8_t)(i^0xa5);
 if(!cardWrite(total-1,sectorBuf)||!cardRead(total-1,fatBuf)||memcmp(sectorBuf,fatBuf,512)){result="FORMAT_END_TEST_FAILED";return;}
 memset(sectorBuf,0,512);if(!cardWrite(total-1,sectorBuf)){result="FORMAT_WRITE_FAILED";return;}
 // Clear reserved sectors, both entire FATs, and the root directory cluster.
 for(uint32_t lba=start;lba<db+64;lba++){
  if(!cardWrite(lba,sectorBuf)||!cardRead(lba,fatBuf)||memcmp(sectorBuf,fatBuf,512)){result="FORMAT_ZERO_VERIFY_FAILED";return;}
 }
 for(unsigned f=0;f<2;f++){
  memset(sectorBuf,0,512);p32(sectorBuf,0x0ffffff8);p32(sectorBuf+4,0xffffffff);p32(sectorBuf+8,0x0fffffff);
  if(!cardWrite(start+32+f*fs,sectorBuf)){result="FORMAT_FAT_FAILED";return;}
 }
 memset(sectorBuf,0,512);p32(sectorBuf,0x41615252);p32(sectorBuf+484,0x61417272);p32(sectorBuf+488,nc-1);p32(sectorBuf+492,3);p32(sectorBuf+508,0xaa550000);
 if(!cardWrite(start+1,sectorBuf)||!cardWrite(start+7,sectorBuf)){result="FORMAT_INFO_FAILED";return;}
 memset(sectorBuf,0,512);sectorBuf[0]=0xeb;sectorBuf[1]=0x58;sectorBuf[2]=0x90;memcpy(sectorBuf+3,"ECOLOG  ",8);
 sectorBuf[12]=2;sectorBuf[13]=64;sectorBuf[14]=32;sectorBuf[16]=2;sectorBuf[21]=0xf8;sectorBuf[24]=63;sectorBuf[26]=255;
 p32(sectorBuf+28,start);p32(sectorBuf+32,size);p32(sectorBuf+36,fs);p32(sectorBuf+44,2);sectorBuf[48]=1;sectorBuf[50]=6;
 sectorBuf[64]=0x80;sectorBuf[66]=0x29;p32(sectorBuf+67,0x26100201);memcpy(sectorBuf+71,"ECOLOGGER  ",11);memcpy(sectorBuf+82,"FAT32   ",8);sectorBuf[510]=0x55;sectorBuf[511]=0xaa;
 if(!cardWrite(start,sectorBuf)||!cardWrite(start+6,sectorBuf)){result="FORMAT_BOOT_FAILED";return;}
 // Publish the new partition only after its filesystem is initialized.
 memset(sectorBuf,0,512);uint8_t*p=sectorBuf+446;p[1]=p[5]=0xfe;p[2]=p[3]=p[6]=p[7]=0xff;p[4]=12;p32(p+8,start);p32(p+12,size);sectorBuf[510]=0x55;sectorBuf[511]=0xaa;
 if(!cardWrite(0,sectorBuf)){result="FORMAT_MBR_FAILED";return;}
 sdMounted=mountCard();sdFailed=false;sdLogErrors=sdQueueDropped=sdBlocks=logBytes=logIndex=0;sdTail=sdHead;freeCursor=3;fatCached=0xffffffff;
 result=sdMounted?"FORMAT_OK_31116288_SECTORS":"FORMAT_MOUNT_FAILED";
}
