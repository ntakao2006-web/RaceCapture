from pathlib import Path
p=Path('pic18f26q84_blink.X/main.c');s=p.read_text(); block='''    RB0PPS = 0; /* Remove any digital output assignment on voltage inputs. */
    RB1PPS = 0;
    RC4PPS = 0;
''';s=s.replace(block,'');s=s.replace('    CAN_TX_PPS = 0x46;',block+'    CAN_TX_PPS = 0x46;');p.write_text(s)
start=s.index('static uint8_t rail_flags');end=s.index('static void uart_puts',start)
a=s.index('static uint16_t nominal_millivolts');b=s.index('static void report_voltage',a)
prefix='''#include <stdint.h>
#include <assert.h>
#include <string.h>
#define INPUT_COUNT 3u
#define ADC_MAX 4095u
#define ADC_LOW_MAX 4u
#define ADC_HIGH_MIN 4091u
#define NOMINAL_VDD_MV 5000UL
struct { unsigned TXQNIF; } C1TXQSTALbits;
uintptr_t C1TXQUA;
uint8_t C1TXQCONH;
'''
test='''int main(void) {
 uint8_t obj[16]; uint16_t adc[3]={0,2048,4095};
 C1TXQUA=(uintptr_t)obj; C1TXQSTALbits.TXQNIF=1;
 assert(can_send_voltages(adc)==1);
 assert(obj[0]==0x80 && obj[1]==5 && obj[4]==8);
 assert(obj[8]==0 && obj[9]==0 && obj[10]==0 && obj[11]==8);
 assert(obj[12]==255 && obj[13]==15 && obj[14]==33 && obj[15]==1);
 assert(C1TXQCONH==3);
 memset(obj,0x55,sizeof(obj)); C1TXQSTALbits.TXQNIF=0;
 assert(can_send_voltages(adc)==0 && obj[0]==0x55);
 C1TXQSTALbits.TXQNIF=1; C1TXQUA=0; assert(can_send_voltages(adc)==0);
 adc[0]=adc[1]=adc[2]=4; assert(rail_flags(adc)==7);
 adc[0]=adc[1]=adc[2]=5; assert(rail_flags(adc)==0);
 adc[0]=adc[1]=adc[2]=4090; assert(rail_flags(adc)==0);
 adc[0]=adc[1]=adc[2]=4091; assert(rail_flags(adc)==56);
 assert(nominal_millivolts(0)==0 && nominal_millivolts(4095)==5000);
 for(unsigned i=1;i<=4095;i++) assert(nominal_millivolts(i)>=nominal_millivolts(i-1));
 return 0;
}
'''
Path('outputs/sensorhub_voltage_20261101/test_payload.c').write_text(prefix+s[start:end]+s[a:b]+test)
