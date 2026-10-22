#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include <zephyr/drivers/i2c.h>
// Temporary diagnostic service. Commands execute in the main loop.
// No automatic OTP programming, disk writes, modem power-on or RF activation.
K_MUTEX_DEFINE(lock);
String queued="",state="{}",gnssRx="",uartRx="",result="idle";
uint32_t completed=0,gnssBytes=0,gnssErrors=0,uartBytes=0,lastPoll=0;bool power=false;
uint8_t sdScratch[512];
const struct device *bus=DEVICE_DT_GET(DT_NODELABEL(i2c2));
String readState(){k_mutex_lock(&lock,K_FOREVER);String s=state;k_mutex_unlock(&lock);return s;}
String takeRx(int lane){k_mutex_lock(&lock,K_FOREVER);String s=lane?uartRx:gnssRx;if(lane)uartRx="";else gnssRx="";k_mutex_unlock(&lock);return s;}
int submit(String c){k_mutex_lock(&lock,K_FOREVER);if(queued.length()){k_mutex_unlock(&lock);return -1;}queued=c;k_mutex_unlock(&lock);return 0;}
void out(int p,int v){digitalWrite(p,v);pinMode(p,OUTPUT);digitalWrite(p,v);}
uint8_t sp(uint8_t v){uint8_t r=0;for(int i=7;i>=0;i--){digitalWrite(D11,(v>>i)&1);delayMicroseconds(2);digitalWrite(D13,HIGH);delayMicroseconds(2);r=(r<<1)|digitalRead(D12);digitalWrite(D13,LOW);}return r;}
void leds(uint8_t v){digitalWrite(D10,HIGH);digitalWrite(A4,HIGH);sp(v);digitalWrite(D7,HIGH);delayMicroseconds(2);digitalWrite(D7,LOW);}
void hexByte(String &s,uint8_t v){const char *h="0123456789abcdef";s+=h[v>>4];s+=h[v&15];}
int nib(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;}
int decode(String s,uint8_t *b,int max){if(s.length()%2||s.length()/2>(unsigned)max)return -1;for(unsigned i=0;i<s.length()/2;i++){int a=nib(s[2*i]),c=nib(s[2*i+1]);if(a<0||c<0)return -1;b[i]=(a<<4)|c;}return s.length()/2;}
void gnssPoll(){uint8_t n[2];if(i2c_burst_read(bus,0x42,0xfd,n,2)){gnssErrors++;return;}int count=min(1024,((int)n[0]<<8)|n[1]);String s="";for(int i=0;i<count;){uint8_t b[64];int take=min(64,count-i);if(i2c_burst_read(bus,0x42,0xff,b,take)){gnssErrors++;break;}for(int j=0;j<take;j++)hexByte(s,b[j]);gnssBytes+=take;i+=take;}k_mutex_lock(&lock,K_FOREVER);if(gnssRx.length()+s.length()<=16384)gnssRx+=s;else gnssErrors++;k_mutex_unlock(&lock);}
int sdCmd(uint8_t cmd,uint32_t arg,uint8_t crc){digitalWrite(A4,HIGH);sp(255);digitalWrite(A4,LOW);sp(0x40|cmd);for(int i=3;i>=0;i--)sp((arg>>(8*i))&255);sp(crc);for(int i=0;i<32;i++){uint8_t r=sp(255);if(!(r&128))return r;}return 255;}
void sdDone(){digitalWrite(A4,HIGH);sp(255);}
bool sdReadData(uint8_t *b,int n){uint32_t end=millis()+1500;uint8_t token;do{token=sp(255);if(token!=255)break;}while(millis()<end);if(token!=0xfe)return false;for(int i=0;i<n;i++)b[i]=sp(255);sp(255);sp(255);return true;}
bool sdReady=false,sdHighCapacity=false;
void sdInit(){digitalWrite(D10,HIGH);digitalWrite(A4,HIGH);for(int i=0;i<12;i++)sp(255);int r0=sdCmd(0,0,0x95);sdDone();int r8=sdCmd(8,0x1aa,0x87);uint8_t r7[4];for(int i=0;i<4;i++)r7[i]=sp(255);sdDone();int r=255;uint32_t end=millis()+3000;if(r0==1)do{sdCmd(55,0,1);sdDone();r=sdCmd(41,0x40000000,1);sdDone();if(r==0)break;delay(10);}while(millis()<end);sdReady=r==0;int ro=sdCmd(58,0,1);uint8_t ocr[4];for(int i=0;i<4;i++)ocr[i]=sp(255);sdDone();sdHighCapacity=ocr[0]&0x40;uint8_t cid[16],csd[16];bool ci=false,cs=false;if(sdReady){if(sdCmd(10,0,1)==0)ci=sdReadData(cid,16);sdDone();if(sdCmd(9,0,1)==0)cs=sdReadData(csd,16);sdDone();}char t[100];snprintf(t,sizeof(t),"cmd0=%02x cmd8=%02x acmd41=%02x ocr_rc=%02x ready=%d sdhc=%d cid=",r0,r8,r,ro,sdReady,sdHighCapacity);result=t;if(ci)for(int i=0;i<16;i++)hexByte(result,cid[i]);result+=" csd=";if(cs)for(int i=0;i<16;i++)hexByte(result,csd[i]);}
void sdRead(uint32_t sector){uint8_t b[512];int r=sdCmd(17,sdHighCapacity?sector:sector*512,1);if(r==0&&sdReadData(b,512)){result="data:";for(int i=0;i<512;i++)hexByte(result,b[i]);}else result="SD_READ_ERROR";sdDone();}
void sdWrite(String c){uint32_t sector=strtoul(c.substring(1).c_str(),nullptr,10);if(!sdReady){result="SD_WRITE_REJECTED";return;}int r=sdCmd(24,sdHighCapacity?sector:sector*512,1);if(r){result="SD_WRITE_CMD_ERROR";sdDone();return;}sp(255);sp(0xfe);for(int i=0;i<512;i++)sp(sdScratch[i]);sp(255);sp(255);uint8_t token=sp(255);uint32_t end=millis()+3000;uint8_t busy;do{busy=sp(255);if(busy==255)break;}while(millis()<end);char t[90];snprintf(t,sizeof(t),"write_token=0x%02x accepted=%d busy_done=%d",token,(token&0x1f)==5,busy==255);result=t;sdDone();}
uint8_t rr(uint8_t a){digitalWrite(D10,LOW);sp(3);sp(a);uint8_t v=sp(255);digitalWrite(D10,HIGH);return v;}
void wr(uint8_t a,uint8_t v){digitalWrite(D10,LOW);sp(2);sp(a);sp(v);digitalWrite(D10,HIGH);}
void bm(uint8_t a,uint8_t m,uint8_t v){digitalWrite(D10,LOW);sp(5);sp(a);sp(m);sp(v);digitalWrite(D10,HIGH);}
void canCheck(){
 digitalWrite(D10,LOW);sp(0xc0);digitalWrite(D10,HIGH);delay(10);
 wr(0x2a,0);wr(0x29,0xb8);wr(0x28,5);wr(0x60,0x60);wr(0x70,0x60);wr(0x0f,0x40);delay(10);
 int ok=0,overflow=0;String trace="";
 for(int n=0;n<32;n++){
  // Do not clear receive flags before draining pending buffers.
  bm(0x2c,0x1c,0);wr(0x31,0x24);wr(0x32,0x60);wr(0x33,0);wr(0x34,0);wr(0x35,8);for(int i=0;i<8;i++)wr(0x36+i,n*7+i);
  digitalWrite(D10,LOW);sp(0x81);digitalWrite(D10,HIGH);uint32_t end=millis()+200;while(!(rr(0x2c)&3)&&millis()<end)delay(1);
  uint8_t flags=rr(0x2c);bool match=false;
  for(int buf=0;buf<2;buf++)if(flags&(1<<buf)){uint8_t rx[13];digitalWrite(D10,LOW);sp(buf?0x94:0x90);for(int i=0;i<13;i++)rx[i]=sp(255);digitalWrite(D10,HIGH);bool same=rx[0]==0x24&&rx[1]==0x60&&(rx[4]&15)==8;for(int i=0;i<8;i++)same=same&&rx[5+i]==(uint8_t)(n*7+i);match|=same;}
  if(match)ok++;if(rr(0x2d)&0xc0)overflow++;
  if(n<4){char t[100];snprintf(t,sizeof(t),"[%d flags=%02x after=%02x eflg=%02x txctrl=%02x]",n,flags,rr(0x2c),rr(0x2d),rr(0x30));trace+=t;}
 }
 char t[140];snprintf(t,sizeof(t),"can2_match=%d/32 overflow_iterations=%d eflg=%02x tec=%u rec=%u ",ok,overflow,rr(0x2d),rr(0x1c),rr(0x1d));result=t;result+=trace;
 digitalWrite(D10,LOW);sp(0xc0);digitalWrite(D10,HIGH);
}
void execute(String c){
 if(c=="ON"){out(A3,HIGH);delay(200);out(A2,HIGH);delay(1200);out(A2,LOW);power=true;result="LTE power enable + PWRKEY pulse completed";}
 else if(c=="OFF"){out(A2,LOW);out(A3,LOW);power=false;result="LTE power disabled";}
 else if(c.startsWith("B")){Serial.begin(strtoul(c.substring(1).c_str(),nullptr,10));result="UART baud set";}
 else if(c.startsWith("T")){Serial.print(c.substring(1));Serial.print("\r");result="UART command sent";}
 else if(c=="RTS0"||c=="RTS1"){out(D2,c=="RTS1"?HIGH:LOW);result="RTS changed";}
 else if(c=="SD"){sdInit();}
 else if(c.startsWith("R")){sdRead(strtoul(c.substring(1).c_str(),nullptr,10));}
 else if(c.startsWith("W")){sdWrite(c);}
 else if(c.startsWith("H")){int colon=c.indexOf(':');unsigned offset=strtoul(c.substring(1,colon).c_str(),nullptr,10);int n=(c.length()-colon-1)/2;result=colon>0&&offset+n<=512&&decode(c.substring(colon+1),sdScratch+offset,n)==n?"loaded":"rejected";}
 
 else if(c.startsWith("G")){uint8_t b[256];int n=decode(c.substring(1),b,256);int r=n>0?i2c_write(bus,b,n,0x42):-1;result=r==0?"GNSS sent":"GNSS write failed";}
 else if(c=="RESETG"){out(D3,LOW);delay(100);out(D3,HIGH);result="GNSS reset completed";}
 else if(c.startsWith("L")){leds(strtoul(c.substring(1).c_str(),nullptr,10));result="LED set";}
 else result="unknown command";
 completed++;
}
void setup(){out(A3,LOW);out(A2,LOW);out(D4,HIGH);out(D10,HIGH);out(A4,HIGH);out(A0,HIGH);out(D3,HIGH);out(D2,LOW);out(D7,LOW);out(D11,LOW);out(D13,LOW);pinMode(D12,INPUT);pinMode(D8,INPUT);leds(0);Serial.begin(115200);Bridge.begin();Bridge.provide("bench.read",readState);Bridge.provide("diag.rx",takeRx);Bridge.provide("diag.tx",submit);i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_FAST));}
void loop(){String c;k_mutex_lock(&lock,K_FOREVER);c=queued;queued="";k_mutex_unlock(&lock);if(c.length())execute(c);if(millis()-lastPoll>=10){lastPoll=millis();gnssPoll();}String rx="";while(Serial.available()){hexByte(rx,Serial.read());uartBytes++;}char h[240];snprintf(h,sizeof(h),"{\"mcu_ms\":%lu,\"completed\":%lu,\"lte_power\":%s,\"cts\":%d,\"gnss_bytes\":%lu,\"i2c_errors\":%lu,\"uart_bytes\":%lu,\"result\":\"",(unsigned long)millis(),(unsigned long)completed,power?"true":"false",digitalRead(D8),(unsigned long)gnssBytes,(unsigned long)gnssErrors,(unsigned long)uartBytes);k_mutex_lock(&lock,K_FOREVER);if(uartRx.length()+rx.length()<=16384)uartRx+=rx;state=h;state+=result;state+="\"}";k_mutex_unlock(&lock);delay(1);}
