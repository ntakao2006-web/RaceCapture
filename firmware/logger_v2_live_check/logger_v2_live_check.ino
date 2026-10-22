#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include <zephyr/drivers/i2c.h>
// Temporary diagnostic service. Commands execute in the main loop.
// No automatic OTP programming, disk writes, modem power-on or RF activation.
K_MUTEX_DEFINE(lock);
String queued="",state="{}",gnssRx="",uartRx="",result="idle";
uint32_t ledTick=0;bool ledSweep=false;
uint32_t completed=0,gnssBytes=0,gnssErrors=0,uartBytes=0,lastPoll=0;bool power=false;
uint32_t queueOverruns=0;
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
void gnssPoll(){uint8_t n[2];if(i2c_burst_read(bus,0x42,0xfd,n,2)){gnssErrors++;return;}int count=min(1024,((int)n[0]<<8)|n[1]);String s="";for(int i=0;i<count;){uint8_t b[64];int take=min(64,count-i);if(i2c_burst_read(bus,0x42,0xff,b,take)){gnssErrors++;break;}for(int j=0;j<take;j++)hexByte(s,b[j]);gnssBytes+=take;i+=take;}k_mutex_lock(&lock,K_FOREVER);if(gnssRx.length()+s.length()<=32768)gnssRx+=s;else queueOverruns++;k_mutex_unlock(&lock);}
uint8_t rr(uint8_t a){digitalWrite(D10,LOW);sp(3);sp(a);uint8_t v=sp(255);digitalWrite(D10,HIGH);return v;}
void wr(uint8_t a,uint8_t v){digitalWrite(D10,LOW);sp(2);sp(a);sp(v);digitalWrite(D10,HIGH);}
void bm(uint8_t a,uint8_t m,uint8_t v){digitalWrite(D10,LOW);sp(5);sp(a);sp(m);sp(v);digitalWrite(D10,HIGH);}
void canCheck(){
 digitalWrite(D10,LOW);sp(0xc0);digitalWrite(D10,HIGH);delay(10);
 wr(0x2a,0);wr(0x29,0xb8);wr(0x28,5);wr(0x60,0x60);wr(0x70,0x60);wr(0x0f,0x40);delay(10);
 int ok=0,overflow=0;
 for(int n=0;n<32;n++){
  // Do not clear receive flags before draining pending buffers.
  bm(0x2c,0x1c,0);wr(0x31,0x24);wr(0x32,0x60);wr(0x33,0);wr(0x34,0);wr(0x35,8);for(int i=0;i<8;i++)wr(0x36+i,n*7+i);
  digitalWrite(D10,LOW);sp(0x81);digitalWrite(D10,HIGH);uint32_t end=millis()+200;while(!(rr(0x2c)&3)&&millis()<end)delay(1);
  uint8_t flags=rr(0x2c);bool match=false;
  for(int buf=0;buf<2;buf++)if(flags&(1<<buf)){uint8_t rx[13];digitalWrite(D10,LOW);sp(buf?0x94:0x90);for(int i=0;i<13;i++)rx[i]=sp(255);digitalWrite(D10,HIGH);bool same=rx[0]==0x24&&rx[1]==0x60&&(rx[4]&15)==8;for(int i=0;i<8;i++)same=same&&rx[5+i]==(uint8_t)(n*7+i);match|=same;}
  if(match)ok++;if(rr(0x2d)&0xc0)overflow++;
  bm(0x2c,3,0);bm(0x2d,0xc0,0);

 }
 char t[140];snprintf(t,sizeof(t),"can2_match=%d/32 overflow_iterations=%d eflg=%02x tec=%u rec=%u ",ok,overflow,rr(0x2d),rr(0x1c),rr(0x1d));result=t;
 digitalWrite(D10,LOW);sp(0xc0);digitalWrite(D10,HIGH);
}
void execute(String c){
 if(c=="ON"){out(A3,HIGH);delay(200);out(A2,HIGH);delay(1200);out(A2,LOW);power=true;result="LTE power enable + PWRKEY pulse completed";}
 else if(c=="OFF"){out(A2,LOW);out(A3,LOW);power=false;result="LTE power disabled";}
 else if(c.startsWith("B")){Serial.begin(strtoul(c.substring(1).c_str(),nullptr,10));result="UART baud set";}
 else if(c.startsWith("T")){Serial.print(c.substring(1));Serial.print("\r");result="UART command sent";}
 else if(c=="RTS0"||c=="RTS1"){out(D2,c=="RTS1"?HIGH:LOW);result="RTS changed";}
 else if(c=="CAN"){canCheck();}
 else if(c.startsWith("G")){uint8_t b[256];int n=decode(c.substring(1),b,256);int r=n>0?i2c_write(bus,b,n,0x42):-1;result=r==0?"GNSS sent":"GNSS write failed";}
 else if(c=="RESETG"){out(D3,LOW);delay(100);out(D3,HIGH);result="GNSS reset completed";}
 else if(c.startsWith("L")){ledSweep=c=="LS";leds(ledSweep?0:strtoul(c.substring(1).c_str(),nullptr,10));result="LED set";}
 else result="unknown command";
 completed++;
}

void ubxConfig(uint8_t *p,int n){uint8_t f[160]={0xb5,0x62,6,0x8a,(uint8_t)n,0};memcpy(f+6,p,n);uint8_t a=0,b=0;for(int i=2;i<n+6;i++){a+=f[i];b+=a;}f[n+6]=a;f[n+7]=b;i2c_write(bus,f,n+8,0x42);delay(200);}
void profile(){
 uint8_t safe[]={0,1,0,0,1,0,0x21,0x30,0xe8,3};ubxConfig(safe,sizeof(safe));
 uint32_t keys[]={0x1031001f,0x10310001,0x10310021,0x10310007,0x10310022,0x1031000d,0x1031000f,0x10310025,0x10310018,0x10310024,0x10310012,0x10310020,0x10310005};
 uint8_t p[80]={0,1,0,0};for(int i=0;i<13;i++){memcpy(p+4+5*i,keys+i,4);p[8+5*i]=i==5?0:1;}ubxConfig(p,69);
 uint8_t rate[]={0,1,0,0,1,0,0x72,0x10,1,2,0,0x72,0x10,0,6,0,0x91,0x20,1,1,0,0x21,0x30,100,0,2,0,0x21,0x30,1,0,0x21,0,0x11,0x20,4};ubxConfig(rate,sizeof(rate));
}

void setup(){out(A3,LOW);out(A2,LOW);out(D4,HIGH);out(D10,HIGH);out(A4,HIGH);out(A0,HIGH);out(D3,HIGH);out(D2,LOW);out(D7,LOW);out(D11,LOW);out(D13,LOW);pinMode(D12,INPUT);pinMode(D8,INPUT);leds(255);Serial.begin(115200);Bridge.begin();Bridge.provide("bench.read",readState);Bridge.provide("diag.rx",takeRx);Bridge.provide("diag.tx",submit);i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_FAST));profile();}
void loop(){String c;k_mutex_lock(&lock,K_FOREVER);c=queued;queued="";k_mutex_unlock(&lock);if(c.length())execute(c);if(ledSweep&&millis()/1000!=ledTick){ledTick=millis()/1000;leds(ledTick%10<8?1<<(ledTick%10):ledTick%10==8?255:0);}if(millis()-lastPoll>=10){lastPoll=millis();gnssPoll();}String rx="";while(Serial.available()){hexByte(rx,Serial.read());uartBytes++;}char h[240];snprintf(h,sizeof(h),"{\"mcu_ms\":%lu,\"completed\":%lu,\"lte_power\":%s,\"cts\":%d,\"gnss_bytes\":%lu,\"i2c_errors\":%lu,\"queue_overruns\":%lu,\"uart_bytes\":%lu,\"result\":\"",(unsigned long)millis(),(unsigned long)completed,power?"true":"false",digitalRead(D8),(unsigned long)gnssBytes,(unsigned long)gnssErrors,(unsigned long)queueOverruns,(unsigned long)uartBytes);k_mutex_lock(&lock,K_FOREVER);if(uartRx.length()+rx.length()<=16384)uartRx+=rx;state=h;state+=result;state+="\"}";k_mutex_unlock(&lock);delay(1);}

