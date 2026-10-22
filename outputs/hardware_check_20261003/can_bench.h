// Temporary bench-only firmware. Finite burst, single-shot TX, automatic listen-only restore.
static bool benchActive=false;
static uint32_t benchRate=500000,benchAt=0,benchSent=0,benchStart=0;
static void benchEnd(){
 FDCAN1->TXBCR=7;bm(0x30,8,0);benchActive=false;
 can1Init(500000);can2Init(500000);
 char s[200];snprintf(s,sizeof(s),"BENCH_DONE sent=%lu rate=%lu psr=%lx ecr=%lx mcp_eflg=%x",(unsigned long)benchSent,(unsigned long)benchRate,(unsigned long)FDCAN1->PSR,(unsigned long)FDCAN1->ECR,rr(0x2d));result=s;
}
static void benchBegin(uint32_t rate){
 if(rate!=125000&&rate!=250000&&rate!=500000&&rate!=1000000){result="bad bench rate";return;}
 can1Init(rate);can2Init(rate);benchRate=rate;
 // The assembled board BOM specifies a 20 MHz MCP25625 crystal.
 wr(0x0f,0x80);delay(2);wr(0x2a,rate==1000000?0:10000000UL/(rate*20)-1);wr(0x29,rate==1000000?0x9a:0xbe);wr(0x28,rate==1000000?1:3);
 FDCAN1->CCCR|=FDCAN_CCCR_INIT;uint32_t end=millis()+50;while(!(FDCAN1->CCCR&1)&&millis()<end){}
 FDCAN1->CCCR|=FDCAN_CCCR_CCE;FDCAN1->CCCR=(FDCAN1->CCCR|FDCAN_CCCR_DAR)&~(FDCAN_CCCR_MON|FDCAN_CCCR_TEST);FDCAN1->CCCR&=~FDCAN_CCCR_INIT;
 wr(0x0f,8);delay(10);benchActive=true;benchSent=0;benchStart=benchAt=millis();result="BENCH_RUNNING";
}
static void benchTick(){
 if(!benchActive)return;
 uint32_t now=millis();
 if(now-benchStart>25000){benchEnd();return;}
 if(now-benchAt<10)return;
 if(benchSent>=1200){if(now-benchAt>=100)benchEnd();return;}
 unsigned n=benchSent;bool ext=(n/2)&1;uint32_t id=(ext?0x18ff0000UL:0x100UL)+n;unsigned dlc=(n/4)%9;
 uint8_t d[8];for(int i=0;i<8;i++)d[i]=(n*17+i*29)&255;
 if(!(n&1)){
  if(FDCAN1->TXBRP)return;
  unsigned tx=(FDCAN1->TXFQS>>16)&3;if(tx>2)return;
  volatile uint32_t*m=(volatile uint32_t*)(SRAMCAN_BASE+632+tx*72);
  m[0]=ext?(id|(1UL<<30)):id<<18;m[1]=dlc<<16;memcpy((void*)(m+2),d,8);FDCAN1->TXBAR=1UL<<tx;
 }else{
  if(rr(0x30)&8)return;
  wr(0x30,0);wr(0x31,ext?id>>21:id>>3);wr(0x32,ext?((id>>13)&0xe0)|8|((id>>16)&3):(id&7)<<5);wr(0x33,ext?id>>8:0);wr(0x34,ext?id:0);wr(0x35,dlc);for(int i=0;i<8;i++)wr(0x36+i,d[i]);
  k_mutex_lock(&spiLock,K_FOREVER);digitalWrite(D10,LOW);sp(0x81);digitalWrite(D10,HIGH);k_mutex_unlock(&spiLock);
 }
 benchSent++;benchAt=now;
}
