#include <Arduino_RouterBridge.h>
K_MUTEX_DEFINE(sampleMutex);
String sample="{}";
String readSample(){k_mutex_lock(&sampleMutex,K_FOREVER);String s=sample;k_mutex_unlock(&sampleMutex);return s;}
void setup(){
 Bridge.begin();Bridge.provide("bench.read",readSample);
 pinMode(A3,OUTPUT);digitalWrite(A3,LOW);pinMode(A2,OUTPUT);digitalWrite(A2,LOW);
 pinMode(D4,OUTPUT);digitalWrite(D4,HIGH);pinMode(D10,OUTPUT);digitalWrite(D10,HIGH);
 pinMode(A4,OUTPUT);digitalWrite(A4,HIGH);pinMode(D7,OUTPUT);digitalWrite(D7,LOW);
 pinMode(D11,OUTPUT);pinMode(D13,OUTPUT);digitalWrite(D13,LOW);
}
void loop(){
 int p=(millis()/1000)%12;uint8_t mask=p<8?(1<<p):(p==8?255:0);
 digitalWrite(D7,LOW);
 for(int i=7;i>=0;i--){digitalWrite(D13,LOW);digitalWrite(D11,(mask>>i)&1);delayMicroseconds(10);digitalWrite(D13,HIGH);delayMicroseconds(10);}
 digitalWrite(D13,LOW);digitalWrite(D7,HIGH);delayMicroseconds(10);digitalWrite(D7,LOW);
 char b[120];snprintf(b,sizeof(b),"{\"source\":\"logger-v2-led-test\",\"mcu_ms\":%lu,\"led_mask\":%u}",(unsigned long)millis(),mask);
 k_mutex_lock(&sampleMutex,K_FOREVER);sample=b;k_mutex_unlock(&sampleMutex);delay(20);
}
