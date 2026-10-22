#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include <zephyr/drivers/i2c.h>

// PCB header mapping verified against the current board file.
// LTE stays powered off; CAN tests use controller internal loopback only.
K_MUTEX_DEFINE(stateMutex);
String snapshot="{}"; int pending=-1;
uint32_t pps=0,bytesRead=0,i2cErrors=0,nmeaGood=0,ubxGood=0,navCount=0;
uint32_t lastNav=0,itow=0; int fix=-1,sats=-1; bool valid=false;
int32_t lat=0,lon=0,height=0; uint32_t hacc=0; int32_t speed=0;
bool gnssAck=false,imu28=false,imu29=false;
uint8_t ledMask=0; bool ledRun=true; uint32_t ledAt=0;
String lastNmea="",monVersion="",canResult="not-tested",can1Result="not-tested",sdResult="not-tested";
const struct device *bus=DEVICE_DT_GET(DT_NODELABEL(i2c2));
void ppsISR(){pps++;}
String readStatus(){k_mutex_lock(&stateMutex,K_FOREVER);String s=snapshot;k_mutex_unlock(&stateMutex);return s;}
String command(int s){k_mutex_lock(&stateMutex,K_FOREVER);pending=s;k_mutex_unlock(&stateMutex);return "queued";}
void output(int pin,int level){digitalWrite(pin,level);pinMode(pin,OUTPUT);digitalWrite(pin,level);}
uint8_t spiByte(uint8_t v){uint8_t r=0;for(int i=7;i>=0;i--){digitalWrite(D11,(v>>i)&1);delayMicroseconds(2);digitalWrite(D13,HIGH);delayMicroseconds(2);r=(r<<1)|digitalRead(D12);digitalWrite(D13,LOW);}return r;}
void leds(uint8_t v){digitalWrite(D10,HIGH);digitalWrite(A4,HIGH);digitalWrite(D7,LOW);spiByte(v);digitalWrite(D7,HIGH);digitalWrite(D7,LOW);ledMask=v;}
uint8_t regRead(uint8_t a){digitalWrite(D10,LOW);spiByte(3);spiByte(a);uint8_t r=spiByte(255);digitalWrite(D10,HIGH);return r;}
void regWrite(uint8_t a,uint8_t v){digitalWrite(D10,LOW);spiByte(2);spiByte(a);spiByte(v);digitalWrite(D10,HIGH);}
void regModify(uint8_t a,uint8_t mask,uint8_t v){digitalWrite(D10,LOW);spiByte(5);spiByte(a);spiByte(mask);spiByte(v);digitalWrite(D10,HIGH);}
void canReset(){digitalWrite(D10,LOW);spiByte(0xc0);digitalWrite(D10,HIGH);delay(10);}
void can1Test(){
 // No bus cable attached: bounded dominant/recessive transceiver feedback.
 int low=0,high=0;
 for(int i=0;i<32;i++){digitalWrite(D4,HIGH);delayMicroseconds(100);if(digitalRead(D5)==1)high++;digitalWrite(D4,LOW);delayMicroseconds(100);if(digitalRead(D5)==0)low++;digitalWrite(D4,HIGH);delayMicroseconds(100);}
 char s[110];snprintf(s,sizeof(s),"recessive_rxd_high=%d/32 dominant_rxd_low=%d/32 (GPIO transceiver feedback, no CAN frames)",high,low);can1Result=s;
}
void canTest(){
 canReset();uint8_t initial=regRead(0x0e),initialError=regRead(0x2d);int ok=0,errors=0;
 if((initial&0xe0)==0x80){
  regWrite(0x2a,0);regWrite(0x29,0xb8);regWrite(0x28,5);regWrite(0x60,0x60);regWrite(0x70,0x60);
  regWrite(0x0f,0x40);delay(10);
  if((regRead(0x0e)&0xe0)==0x40){
   for(int n=0;n<32;n++){
    regModify(0x2c,0xff,0);regWrite(0x31,0x24);regWrite(0x32,0x60);regWrite(0x33,0);regWrite(0x34,0);regWrite(0x35,8);
    for(int i=0;i<8;i++)regWrite(0x36+i,(uint8_t)(n*7+i));
    digitalWrite(D10,LOW);spiByte(0x81);digitalWrite(D10,HIGH);
    uint32_t end=millis()+100;while(!(regRead(0x2c)&3)&&millis()<end)delay(1);
    uint8_t flags=regRead(0x2c),rx[13];bool match=flags&3;
    // READ RX BUFFER automatically releases RXnIF when CS rises.
    digitalWrite(D10,LOW);spiByte((flags&1)?0x90:0x94);
    for(int i=0;i<13;i++)rx[i]=spiByte(255);digitalWrite(D10,HIGH);
    match=match&&rx[0]==0x24&&rx[1]==0x60&&(rx[4]&15)==8;
    for(int i=0;i<8;i++)match=match&&rx[5+i]==(uint8_t)(n*7+i);
    if(match)ok++;else errors++;
   }
  } else errors++;
 }
 char s[160];snprintf(s,sizeof(s),"reset_stat=0x%02x initial_eflg=0x%02x loopback_ok=%d/32 errors=%d eflg=0x%02x tec=%u rec=%u int=%d",initial,initialError,ok,errors,regRead(0x2d),regRead(0x1c),regRead(0x1d),digitalRead(D9));canResult=s;
 canReset();leds(0);
}
int sdCmd(uint8_t cmd,uint32_t arg,uint8_t crc){
 digitalWrite(A4,HIGH);spiByte(255);digitalWrite(A4,LOW);spiByte(0x40|cmd);
 for(int i=3;i>=0;i--)spiByte((arg>>(8*i))&255);spiByte(crc);
 for(int i=0;i<16;i++){uint8_t r=spiByte(255);if(!(r&128))return r;}return 255;
}
void sdTest(){
 digitalWrite(D10,HIGH);digitalWrite(A4,HIGH);for(int i=0;i<12;i++)spiByte(255);
 int c0=sdCmd(0,0,0x95);digitalWrite(A4,HIGH);spiByte(255);
 int c8=sdCmd(8,0x1aa,0x87);uint8_t r7[4];for(int i=0;i<4;i++)r7[i]=spiByte(255);digitalWrite(A4,HIGH);spiByte(255);
 bool ready=false;int c41=255;uint32_t end=millis()+2000;
 if(c0==1)while(millis()<end){sdCmd(55,0,1);digitalWrite(A4,HIGH);spiByte(255);c41=sdCmd(41,0x40000000,1);digitalWrite(A4,HIGH);spiByte(255);if(c41==0){ready=true;break;}delay(10);}
 String cid="";if(ready){int r=sdCmd(10,0,1);uint8_t token=255;uint32_t e=millis()+300;while(token==255&&millis()<e)token=spiByte(255);if(r==0&&token==0xfe){char x[3];for(int i=0;i<16;i++){snprintf(x,3,"%02x",spiByte(255));cid+=x;}spiByte(255);spiByte(255);}digitalWrite(A4,HIGH);spiByte(255);}
 char s[180];snprintf(s,sizeof(s),"cmd0=%02x cmd8=%02x echo=%02x%02x%02x%02x acmd41=%02x ready=%d cid=%s (read-only)",c0,c8,r7[0],r7[1],r7[2],r7[3],c41,ready,cid.c_str());sdResult=s;leds(0);
}
bool probe(uint8_t a){uint8_t v;return i2c_read(bus,&v,1,a)==0;}
void ubxSend(uint8_t cls,uint8_t id,const uint8_t *data,uint16_t n){uint8_t b[128]={0xb5,0x62,cls,id,(uint8_t)n,(uint8_t)(n>>8)};if(n>120)return;for(int i=0;i<n;i++)b[6+i]=data[i];uint8_t a=0,c=0;for(int i=2;i<n+6;i++){a+=b[i];c+=a;}b[n+6]=a;b[n+7]=c;if(i2c_write(bus,b,n+8,0x42))i2cErrors++;}
uint32_t u32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
void feed(uint8_t v){
 static uint8_t frame[520];static int pos=0,total=0;static uint8_t ca=0,cb=0;static String line="";
 if(pos==0){if(v==0xb5){frame[pos++]=v;return;}if(v=='$')line="$";else if(line.length()){if(v=='\n'){int star=line.indexOf('*');if(star>0&&line.length()>=star+3){uint8_t c=0;for(int i=1;i<star;i++)c^=line[i];if(c==strtoul(line.substring(star+1,star+3).c_str(),nullptr,16)){nmeaGood++;lastNmea=line;}}line="";}else if(v!='\r'&&line.length()<180)line+=(char)v;}return;}
 if(pos==1&&v!=0x62){pos=0;return;}frame[pos++]=v;
 if(pos==6){total=6+frame[4]+((int)frame[5]<<8)+2;if(total>520){pos=0;return;}}
 if(pos>=6&&pos==total){ca=cb=0;for(int i=2;i<total-2;i++){ca+=frame[i];cb+=ca;}if(ca==frame[total-2]&&cb==frame[total-1]){
  ubxGood++;uint8_t *p=frame+6;int len=total-8;
  if(frame[2]==1&&frame[3]==7&&len>=92){navCount++;lastNav=millis();itow=u32(p);fix=p[20];valid=p[21]&1;sats=p[23];lon=(int32_t)u32(p+24);lat=(int32_t)u32(p+28);height=(int32_t)u32(p+36);hacc=u32(p+40);speed=(int32_t)u32(p+60);}
  if(frame[2]==0x0a&&frame[3]==4&&len>=40){monVersion="";for(int i=0;i<len;i++){char c=p[i];monVersion+=(c>=32&&c<=126)?c:' ';}}
 }pos=0;}
}
void pollGnss(){uint8_t count[2];if(i2c_burst_read(bus,0x42,0xfd,count,2)){i2cErrors++;return;}int n=((int)count[0]<<8)|count[1];if(n>4096)n=4096;for(int read=0;read<n;){uint8_t b[64];int take=min(64,n-read);if(i2c_burst_read(bus,0x42,0xff,b,take)){i2cErrors++;break;}for(int i=0;i<take;i++)feed(b[i]);bytesRead+=take;read+=take;}}
void publish(){char b[2100];snprintf(b,sizeof(b),"{\"source\":\"logger-v2-bench-real\",\"demo\":false,\"mcu_ms\":%lu,\"led_run\":%s,\"led_mask\":%u,\"gnss_ack\":%s,\"imu28\":%s,\"imu29\":%s,\"bytes\":%lu,\"i2c_errors\":%lu,\"nmea_ok\":%lu,\"ubx_ok\":%lu,\"nav_count\":%lu,\"nav_age_ms\":%lu,\"itow\":%lu,\"fix\":%d,\"valid\":%s,\"sats\":%d,\"lat_e7\":%ld,\"lon_e7\":%ld,\"height_mm\":%ld,\"hacc_mm\":%lu,\"speed_mm_s\":%ld,\"pps\":%lu,\"can1_rxd\":%d,\"can1\":\"%s\",\"can2\":\"%s\",\"sd\":\"%s\",\"mon_ver\":\"%s\",\"nmea\":\"%s\"}", (unsigned long)millis(),ledRun?"true":"false",ledMask,gnssAck?"true":"false",imu28?"true":"false",imu29?"true":"false",(unsigned long)bytesRead,(unsigned long)i2cErrors,(unsigned long)nmeaGood,(unsigned long)ubxGood,(unsigned long)navCount,(unsigned long)(lastNav?millis()-lastNav:0xffffffff),(unsigned long)itow,fix,valid?"true":"false",sats,(long)lat,(long)lon,(long)height,(unsigned long)hacc,(long)speed,(unsigned long)pps,digitalRead(D5),can1Result.c_str(),canResult.c_str(),sdResult.c_str(),monVersion.c_str(),lastNmea.c_str());k_mutex_lock(&stateMutex,K_FOREVER);snapshot=b;k_mutex_unlock(&stateMutex);}
void setup(){
 output(A3,LOW);output(A2,LOW);output(D4,HIGH);output(D10,HIGH);output(A4,HIGH);output(A0,HIGH);
 output(D7,LOW);output(D11,LOW);output(D13,LOW);pinMode(D12,INPUT);pinMode(D5,INPUT);pinMode(D9,INPUT);pinMode(D6,INPUT);
 leds(0);attachInterrupt(D6,ppsISR,RISING);Bridge.begin();Bridge.provide("bench.read",readStatus);Bridge.provide("bench.command",command);
 i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_STANDARD));delay(500);gnssAck=probe(0x42);imu28=probe(0x28);imu29=probe(0x29);if(gnssAck)ubxSend(0x0a,4,nullptr,0);publish();
}
void loop(){
 static uint32_t navAt=0,pubAt=0,readAt=0;int c; k_mutex_lock(&stateMutex,K_FOREVER);c=pending;pending=-1;k_mutex_unlock(&stateMutex);
 if(c==256){ledRun=true;ledAt=0;}else if(c>=0&&c<=255){ledRun=false;leds((uint8_t)c);}else if(c==257){ledRun=false;canTest();}else if(c==258){ledRun=false;sdTest();}else if(c==261){can1Test();}else if(c==259)i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_FAST));else if(c==260)i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_STANDARD));
 uint32_t now=millis();if(ledRun&&now-ledAt>=1000){ledAt=now;int phase=(now/1000)%12;leds(phase<8?(1<<phase):(phase==8?255:0));}
 if(gnssAck&&now-readAt>=20){readAt=now;pollGnss();}if(gnssAck&&now-navAt>=1000){navAt=now;ubxSend(1,7,nullptr,0);}if(now-pubAt>=100){pubAt=now;publish();}delay(1);
}
