// MCU-owned FAT32 append-only logger. Files are never formatted or overwritten.
// 512-byte ELB2 blocks: 16-byte header, TLV records, CRC32 at offset 508.
static uint32_t freeCursor=2,sdAllocMs=0;
static uint32_t partStart,partSize,fatBase,fatSize,dataBase,clusters,rootCluster;
static uint8_t clusterSectors,fatCopies,fatBuf[512],sectorBuf[512],logBuf[512];
static uint32_t fatCached=0xffffffff,logFirst,logCluster,logSector,logCapacity,logBytes,logIndex,dirSector;
static uint16_t dirOffset,logUsed=16;
static uint32_t sdLogErrors=0,sdBlocks=0,sdFlushAt=0,sdMetaAt=0;
static bool sdMounted=false;
// Yield after each SD sector so the acquisition thread can service the two CAN2 RX buffers.
// When recording is stopped, the worker stays idle so read-only sector RPCs see stable state.
static volatile bool sdLogging=false,sdWorking=false;
static uint16_t u16(const uint8_t*p){return p[0]|(p[1]<<8);}
static uint32_t u32(const uint8_t*p){return p[0]|(p[1]<<8)|(p[2]<<16)|((uint32_t)p[3]<<24);}
static void p32(uint8_t*p,uint32_t v){for(int i=0;i<4;i++)p[i]=v>>(i*8);}
static bool cardRead(uint32_t lba,uint8_t*b){int r=sdCmd(17,sdHighCapacity?lba:lba*512,1);bool ok=r==0&&sdReadData(b,512);sdDone();k_msleep(1);return ok;}
static bool cardWrite(uint32_t lba,const uint8_t*b){
 int r=sdCmd(24,sdHighCapacity?lba:lba*512,1);if(r){sdDone();return false;}
 sp(255);sp(0xfe);for(int i=0;i<512;i++)sp(b[i]);sp(255);sp(255);int token=sp(255);
 // SPI cards keep programming with CS high. Free the bus while busy so CAN2 can be read.
 sdDone();uint32_t end=millis()+1000;int v=0;
 do{k_msleep(1);k_mutex_lock(&spiLock,K_FOREVER);digitalWrite(D10,HIGH);digitalWrite(A4,LOW);sp(255);v=sp(255);sdDone();if(v==255)break;}while(millis()<end);
 return (token&31)==5&&v==255;
}
static bool partitionWrite(uint32_t lba,const uint8_t*b){return lba>=partStart&&lba-partStart<partSize&&cardWrite(lba,b);}
static uint32_t fatGet(uint32_t c){uint32_t sec=c/128;if(sec>=fatSize)return 0xffffffff;if(fatCached!=sec){if(!cardRead(fatBase+sec,fatBuf))return 0xffffffff;fatCached=sec;}return u32(fatBuf+(c%128)*4)&0x0fffffff;}
static bool mountCard(){if(!sdReady||!cardRead(0,sectorBuf)||sectorBuf[510]!=0x55||sectorBuf[511]!=0xaa)return false;const uint8_t*p=sectorBuf+446;if(p[4]!=11&&p[4]!=12)return false;partStart=u32(p+8);partSize=u32(p+12);if(!partStart||!partSize||partStart+partSize<partStart)return false;if(!cardRead(partStart,sectorBuf)||u16(sectorBuf+11)!=512||u16(sectorBuf+17)!=0)return false;uint16_t info=u16(sectorBuf+48),backup=u16(sectorBuf+50),reserved=u16(sectorBuf+14);clusterSectors=sectorBuf[13];fatCopies=sectorBuf[16];fatSize=u32(sectorBuf+36);rootCluster=u32(sectorBuf+44);fatBase=partStart+u16(sectorBuf+14);dataBase=fatBase+fatCopies*fatSize;if(!clusterSectors||(clusterSectors&(clusterSectors-1))||fatCopies<1||fatCopies>2||!fatSize||dataBase>=partStart+partSize)return false;clusters=(partStart+partSize-dataBase)/clusterSectors;if(rootCluster<2||rootCluster>=clusters+2)return false;fatCached=0xffffffff;uint32_t rootNext=fatGet(rootCluster);if(rootNext<2||rootNext==0xffffffff||rootNext==0x0ffffff7)return false;if(info&&info<reserved){for(unsigned i=0;i<2;i++){uint32_t rel=info+(i?backup:0);if(rel>=reserved)continue;if(cardRead(partStart+rel,sectorBuf)&&u32(sectorBuf)==0x41615252&&u32(sectorBuf+484)==0x61417272){p32(sectorBuf+488,0xffffffff);p32(sectorBuf+492,0xffffffff);if(!partitionWrite(partStart+rel,sectorBuf))return false;}}}return true;}
static bool logMetadata(){if(!sdLogging)return true;if(!cardRead(dirSector,sectorBuf))return false;p32(sectorBuf+dirOffset+28,logBytes);return partitionWrite(dirSector,sectorBuf);}
static bool fatSet(uint32_t c,uint32_t value){uint32_t sec=c/128;if(!cardRead(fatBase+sec,fatBuf))return false;p32(fatBuf+(c%128)*4,value);for(unsigned f=0;f<fatCopies;f++)if(!partitionWrite(fatBase+f*fatSize+sec,fatBuf))return false;fatCached=0xffffffff;return true;}
static bool newSDLog(){
 if(!sdMounted)return false;uint32_t allocationAt=millis();
 uint32_t maxIndex=0,freeSec=0;uint16_t freeOff=0;uint32_t c=rootCluster,lastRoot=c;
 for(unsigned hop=0;hop<128&&c>=2&&c<clusters+2;hop++){
  for(unsigned s=0;s<clusterSectors;s++){uint32_t lba=dataBase+(c-2)*clusterSectors+s;if(!cardRead(lba,sectorBuf))return false;
   for(unsigned off=0;off<512;off+=32){uint8_t*p=sectorBuf+off;if((p[0]==0||p[0]==0xe5)&&!freeSec){freeSec=lba;freeOff=off;}if(p[0]=='E'&&p[1]=='L'&&!memcmp(p+8,"BIN",3)){uint32_t n=0;for(int j=2;j<8;j++){if(p[j]<'0'||p[j]>'9'){n=0;break;}n=n*10+p[j]-'0';}if(n>maxIndex)maxIndex=n;}}
  }lastRoot=c;c=fatGet(c);if(c>=0x0ffffff8)break;
 }
 if(maxIndex>=999999)return false;
 if(!freeSec){uint32_t extra=0;for(uint32_t i=freeCursor;i<clusters+2;i++){if(fatGet(i)==0){extra=i;break;}}if(!extra)return false;memset(sectorBuf,0,512);for(unsigned j=0;j<clusterSectors;j++)if(!partitionWrite(dataBase+(extra-2)*clusterSectors+j,sectorBuf))return false;if(!fatSet(extra,0x0fffffff)||!fatSet(lastRoot,extra))return false;freeSec=dataBase+(extra-2)*clusterSectors;freeOff=0;freeCursor=extra+1;}

 // Reserve a contiguous 1 MiB file. Only free clusters are changed.
 uint32_t count=(1UL*1024*1024)/(clusterSectors*512UL),run=0,first=0;
 if(freeCursor<2||freeCursor>=clusters+2)freeCursor=2;
 for(int pass=0;pass<2&&run<count;pass++){
  run=0;uint32_t begin=pass?2:freeCursor,end=pass?freeCursor:clusters+2;
  for(uint32_t i=begin;i<end;i++){uint32_t v=fatGet(i);if(v==0){if(!run)first=i;if(++run==count)break;}else{if(v==0xffffffff)return false;run=0;}}
 }
 if(run<count)return false;
 for(uint32_t sec=first/128;sec<=(first+count-1)/128;sec++){
  fatCached=0xffffffff;if(!cardRead(fatBase+sec,fatBuf))return false;
  for(unsigned j=0;j<128;j++){uint32_t k=sec*128+j;if(k>=first&&k<first+count)p32(fatBuf+j*4,k==first+count-1?0x0fffffff:k+1);}
  for(unsigned f=0;f<fatCopies;f++)if(!partitionWrite(fatBase+f*fatSize+sec,fatBuf))return false;
 }
 fatCached=0xffffffff;if(!cardRead(freeSec,sectorBuf))return false;uint8_t*p=sectorBuf+freeOff;memset(p,0,32);char name[12];snprintf(name,sizeof(name),"EL%06luBIN",(unsigned long)(maxIndex+1));memcpy(p,name,11);p[11]=0x20;p[20]=first>>16;p[21]=first>>24;p[26]=first;p[27]=first>>8;
 if(!partitionWrite(freeSec,sectorBuf))return false;
 dirSector=freeSec;dirOffset=freeOff;logIndex=maxIndex+1;logFirst=logCluster=first;logSector=logBytes=0;logCapacity=count*clusterSectors*512UL;logUsed=16;memset(logBuf,0,512);freeCursor=first+count;sdAllocMs=millis()-allocationAt;sdLogging=true;return true;
}
static uint32_t blockCRC(const uint8_t*p,int n){uint32_t crc=0xffffffff;for(int i=0;i<n;i++){crc^=p[i];for(int j=0;j<8;j++)crc=(crc>>1)^((crc&1)?0xedb88320:0);}return ~crc;}
static void sdFailure(){sdLogErrors++;sdLogging=false;}
static bool flushSDLog(){if(!sdLogging||logUsed==16)return true;memcpy(logBuf,"ELB2",4);p32(logBuf+4,logIndex);p32(logBuf+8,logBytes/512);logBuf[12]=logUsed;logBuf[13]=logUsed>>8;p32(logBuf+508,blockCRC(logBuf,508));uint32_t lba=dataBase+(logFirst-2)*clusterSectors+logBytes/512;if(!partitionWrite(lba,logBuf)){sdFailure();return false;}logBytes+=512;sdBlocks++;logUsed=16;memset(logBuf,0,512);if(logBytes>=logCapacity){if(!logMetadata()){sdFailure();return false;}sdLogging=false;if(!newSDLog()){sdFailure();return false;}}return true;}
static void sdAppend(uint8_t type,uint32_t ms,const uint8_t*p,int n){if(!sdLogging)return;if(logUsed+6+n>508&&!flushSDLog())return;logBuf[logUsed++]=type;logBuf[logUsed++]=n;p32(logBuf+logUsed,ms);logUsed+=4;if(n)memcpy(logBuf+logUsed,p,n);logUsed+=n;}
static void sdTick(uint32_t now){if(sdLogging&&now-sdFlushAt>=100){sdFlushAt=now;flushSDLog();}if(sdLogging&&now-sdMetaAt>=1000){sdMetaAt=now;if(!logMetadata())sdFailure();}}
static void sdStop(){flushSDLog();if(!logMetadata())sdFailure();sdLogging=false;}
static void sdFiles(unsigned skip=0){result="[";uint32_t c=rootCluster;unsigned found=0;for(unsigned hop=0;hop<128&&c>=2&&c<clusters+2;hop++){for(unsigned s=0;s<clusterSectors;s++){if(!cardRead(dataBase+(c-2)*clusterSectors+s,sectorBuf)){result="SD_READ_ERROR";return;}for(unsigned off=0;off<512;off+=32){uint8_t*p=sectorBuf+off;if(p[0]!='E'||p[1]!='L'||memcmp(p+8,"BIN",3)||p[11]!=0x20)continue;char n[7];memcpy(n,p+2,6);n[6]=0;uint32_t index=strtoul(n,nullptr,10);char line[100];snprintf(line,sizeof(line),"%s{\"index\":%lu,\"cluster\":%lu,\"size\":%lu,\"active\":%s}",result.length()>1?",":"",(unsigned long)index,(unsigned long)((u16(p+20)<<16)|u16(p+26)),(unsigned long)u32(p+28),sdLogging&&index==logIndex?"true":"false");unsigned order=found++;if(order>=skip&&order<skip+16)result+=line;}}c=fatGet(c);if(c>=0x0ffffff8)break;}result+="]";}

// Single acquisition producer and SD consumer. No sensor work waits for filesystem writes.
static uint8_t sdQueue[65536];
static volatile uint32_t sdHead=0,sdTail=0,sdQueueDropped=0;
static bool sdFailed=false;
static void sdRecord(uint8_t type,uint32_t ms,const uint8_t*p,int n){
 if(!recording||!sdMounted||sdFailed)return;
 uint32_t h=__atomic_load_n(&sdHead,__ATOMIC_RELAXED),t=__atomic_load_n(&sdTail,__ATOMIC_ACQUIRE);
 if(h-t+6+n>=sizeof(sdQueue)){sdQueueDropped++;return;}
 uint8_t hdr[6]={type,(uint8_t)n};p32(hdr+2,ms);
 for(int i=0;i<6;i++)sdQueue[(h++)&65535]=hdr[i];
 for(int i=0;i<n;i++)sdQueue[(h++)&65535]=p[i];
 __atomic_store_n(&sdHead,h,__ATOMIC_RELEASE);
}
K_THREAD_STACK_DEFINE(sdStack,4096);
static struct k_thread sdThread;
static void sdWorker(void*,void*,void*){
 uint8_t packet[98];
 while(true){
  if(sdMounted&&!sdFailed&&(recording||sdLogging||sdHead!=sdTail)){sdWorking=true;
   if(recording&&!sdLogging&&!newSDLog()){sdFailure();sdFailed=true;}
   for(int batch=0;batch<32;batch++){
    uint32_t t=__atomic_load_n(&sdTail,__ATOMIC_RELAXED),h=__atomic_load_n(&sdHead,__ATOMIC_ACQUIRE);
    if(t==h)break;
    int n=sdQueue[(t+1)&65535];for(int i=0;i<n+6;i++)packet[i]=sdQueue[(t+i)&65535];__atomic_store_n(&sdTail,t+n+6,__ATOMIC_RELEASE);sdAppend(packet[0],u32(packet+2),packet+6,n);
   }
   if(!recording&&sdLogging&&sdHead==sdTail)sdStop();
   sdTick(millis());if(sdLogErrors){sdFailed=true;sdTail=sdHead;}sdWorking=false;
  }
  k_msleep(1);
 }
}
static void startSDWorker(){k_thread_create(&sdThread,sdStack,K_THREAD_STACK_SIZEOF(sdStack),sdWorker,nullptr,nullptr,nullptr,6,0,K_NO_WAIT);}
