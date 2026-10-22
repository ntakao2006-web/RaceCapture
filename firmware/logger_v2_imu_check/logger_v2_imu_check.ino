#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/gpio.h>
// Temporary diagnostic service. Commands execute in the main loop.
// No automatic OTP programming, disk writes, modem power-on or RF activation.
K_MUTEX_DEFINE(lock);
String queued="",state="{}",gnssRx="",uartRx="",result="idle";
uint32_t ledTick=0;bool ledSweep=false;
uint32_t completed=0,gnssBytes=0,gnssErrors=0,uartBytes=0,lastPoll=0;bool power=false;
uint32_t queueOverruns=0;
const struct device *bus=DEVICE_DT_GET(DT_NODELABEL(i2c2));
static String readState(){k_mutex_lock(&lock,K_FOREVER);String s=state;k_mutex_unlock(&lock);return s;}
static String takeRx(int lane){k_mutex_lock(&lock,K_FOREVER);String s=lane?uartRx:gnssRx;if(lane)uartRx="";else gnssRx="";k_mutex_unlock(&lock);return s;}
static int submit(String c){k_mutex_lock(&lock,K_FOREVER);if(queued.length()){k_mutex_unlock(&lock);return -1;}queued=c;k_mutex_unlock(&lock);return 0;}
static void out(int p,int v){digitalWrite(p,v);pinMode(p,OUTPUT);digitalWrite(p,v);}
static uint8_t sp(uint8_t v){uint8_t r=0;for(int i=7;i>=0;i--){digitalWrite(D11,(v>>i)&1);delayMicroseconds(2);digitalWrite(D13,HIGH);delayMicroseconds(2);r=(r<<1)|digitalRead(D12);digitalWrite(D13,LOW);}return r;}
static void leds(uint8_t v){digitalWrite(D10,HIGH);digitalWrite(A4,HIGH);sp(v);digitalWrite(D7,HIGH);delayMicroseconds(2);digitalWrite(D7,LOW);}
static void hexByte(String &s,uint8_t v){const char *h="0123456789abcdef";s+=h[v>>4];s+=h[v&15];}
static void gnssPoll(){uint8_t n[2];if(i2c_burst_read(bus,0x42,0xfd,n,2)){gnssErrors++;return;}int count=min(1024,((int)n[0]<<8)|n[1]);String s="";for(int i=0;i<count;){uint8_t b[64];int take=min(64,count-i);if(i2c_burst_read(bus,0x42,0xff,b,take)){gnssErrors++;break;}for(int j=0;j<take;j++)hexByte(s,b[j]);gnssBytes+=take;i+=take;}k_mutex_lock(&lock,K_FOREVER);if(gnssRx.length()+s.length()<=32768)gnssRx+=s;else queueOverruns++;k_mutex_unlock(&lock);}

uint8_t imuAddr=0,imuRaw[46]={0};uint32_t imuSeq=0,imuErrors=0,imuAt=0;bool imuSampling=false;String imuState="{}";
volatile uint32_t irqRise=0,irqFall=0;uint8_t irqStatus=0;uint32_t irqSeen=0;int interruptSetup=-999;
static void imuISR(){if(digitalRead(A5))irqRise++;else irqFall++;}

static int iw(uint8_t r,uint8_t v){int rc=i2c_reg_write_byte(bus,imuAddr,r,v);if(rc)imuErrors++;return rc;}
static int ir(uint8_t r,uint8_t *b,int n){int rc=i2c_burst_read(bus,imuAddr,r,b,n);if(rc)imuErrors++;return rc;}
static void imuCommand(String c){
 if(c=="I"){imuSampling=false;imuAddr=0;uint8_t id=0;for(int a=0x28;a<=0x29;a++)if(!i2c_reg_read_byte(bus,a,0,&id)&&id==0xa0){imuAddr=a;break;}result="address=";result+=String(imuAddr);}
 else if(c=="H"){imuSampling=false;out(A1,LOW);delay(100);out(A1,HIGH);delay(750);result="hardware reset released";}
 else if(c=="Q"){imuSampling=!imuSampling;result=imuSampling?"sampling on":"sampling off";}
 else if(c=="A"){iw(7,0);uint8_t trig=0;ir(0x3f,&trig,1);iw(0x3f,(trig&0x80)|0x40);result="interrupt reset";}
 else if(c.startsWith("J")){int page=0,r=0,n=0;char *end;page=strtoul(c.c_str()+1,&end,10);r=strtoul(end+1,&end,10);n=strtoul(end+1,nullptr,10);uint8_t b[64];if(n>0&&n<=64&&!iw(7,page)&&!ir(r,b,n)){result="data:";for(int i=0;i<n;i++)hexByte(result,b[i]);}else result="read error";}
 else if(c.startsWith("K")){int page=0,r=0,v=0;char *end;page=strtoul(c.c_str()+1,&end,10);r=strtoul(end+1,&end,10);v=strtoul(end+1,nullptr,10);result=!iw(7,page)&&!iw(r,v)?"written":"write error";}
}
static void imuPoll(){
 if(imuAddr&&imuSampling){iw(7,0);if(!ir(8,imuRaw,46))imuSeq++;if(irqRise!=irqSeen){irqSeen=irqRise;ir(0x37,&irqStatus,1);}}
 char b[220];snprintf(b,sizeof(b),"{\"mcu_ms\":%lu,\"address\":%u,\"seq\":%lu,\"errors\":%lu,\"int_pin\":%d,\"irq_rise\":%lu,\"irq_fall\":%lu,\"irq_status\":%u,\"raw\":\"",(unsigned long)millis(),imuAddr,(unsigned long)imuSeq,(unsigned long)imuErrors,digitalRead(A5),(unsigned long)irqRise,(unsigned long)irqFall,irqStatus);String t=b;for(int i=0;i<46;i++)hexByte(t,imuRaw[i]);t+="\"}";k_mutex_lock(&lock,K_FOREVER);imuState=t;k_mutex_unlock(&lock);
}

static void execute(String c){
 if(c=="OFF"){out(A2,LOW);out(A3,LOW);power=false;result="LTE disabled";}
 else if(c=="E"){int rc=gpio_pin_interrupt_configure(DEVICE_DT_GET(DT_NODELABEL(gpiob)),1,GPIO_INT_EDGE_RISING);result="PPS_interrupt_rc=";result+=String(rc);if(!rc){gpio_pin_interrupt_configure(DEVICE_DT_GET(DT_NODELABEL(gpiob)),1,GPIO_INT_DISABLE);gpio_pin_interrupt_configure(DEVICE_DT_GET(DT_NODELABEL(gpioa)),1,GPIO_INT_EDGE_BOTH);}}
 else if(c=="Z"){i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_STANDARD));result="I2C 100k";}
 else if(c=="F"){i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_FAST));result="I2C 400k";}
 else if(c.startsWith("I")||c.startsWith("J")||c.startsWith("K")||c=="A"||c=="H"||c=="Q"){imuCommand(c);}

 else result="unknown command";
 completed++;
}

static void ubxConfig(uint8_t *p,int n){uint8_t f[160]={0xb5,0x62,6,0x8a,(uint8_t)n,0};memcpy(f+6,p,n);uint8_t a=0,b=0;for(int i=2;i<n+6;i++){a+=f[i];b+=a;}f[n+6]=a;f[n+7]=b;i2c_write(bus,f,n+8,0x42);delay(200);}
static void profile(){
 uint8_t safe[]={0,1,0,0,1,0,0x21,0x30,0xe8,3};ubxConfig(safe,sizeof(safe));
 uint32_t keys[]={0x1031001f,0x10310001,0x10310021,0x10310007,0x10310022,0x1031000d,0x1031000f,0x10310025,0x10310018,0x10310024,0x10310012,0x10310020,0x10310005};
 uint8_t p[80]={0,1,0,0};for(int i=0;i<13;i++){memcpy(p+4+5*i,keys+i,4);p[8+5*i]=i==5?0:1;}ubxConfig(p,69);
 uint8_t rate[]={0,1,0,0,1,0,0x72,0x10,1,2,0,0x72,0x10,0,6,0,0x91,0x20,1,1,0,0x21,0x30,100,0,2,0,0x21,0x30,1,0,0x21,0,0x11,0x20,4};ubxConfig(rate,sizeof(rate));
}

void setup(){out(A3,LOW);out(A2,LOW);out(D4,HIGH);out(D10,HIGH);out(A4,HIGH);out(A0,HIGH);out(D3,HIGH);out(D2,LOW);out(D7,LOW);out(D11,LOW);out(D13,LOW);pinMode(D12,INPUT);pinMode(D8,INPUT);out(A1,HIGH);pinMode(A5,INPUT);attachInterrupt(A5,imuISR,CHANGE);leds(255);Bridge.begin();Bridge.provide("bench.read",readState);Bridge.provide("diag.rx",takeRx);Bridge.provide("diag.tx",submit);i2c_configure(bus,I2C_MODE_CONTROLLER|I2C_SPEED_SET(I2C_SPEED_FAST));profile();}
void loop(){String c;k_mutex_lock(&lock,K_FOREVER);c=queued;queued="";k_mutex_unlock(&lock);if(c.length())execute(c);if(millis()-lastPoll>=10){lastPoll=millis();gnssPoll();}if(millis()-imuAt>=10){imuAt=millis();imuPoll();}String rx="";char h[240];snprintf(h,sizeof(h),"{\"mcu_ms\":%lu,\"completed\":%lu,\"lte_power\":%s,\"cts\":%d,\"gnss_bytes\":%lu,\"i2c_errors\":%lu,\"queue_overruns\":%lu,\"uart_bytes\":%lu,\"result\":\"",(unsigned long)millis(),(unsigned long)completed,power?"true":"false",digitalRead(D8),(unsigned long)gnssBytes,(unsigned long)gnssErrors,(unsigned long)queueOverruns,(unsigned long)uartBytes);k_mutex_lock(&lock,K_FOREVER);if(uartRx.length()+rx.length()<=16384)uartRx+=rx;state=h;state+=result;state+="\",\"imu\":";state+=imuState;state+="}";k_mutex_unlock(&lock);delay(1);}

