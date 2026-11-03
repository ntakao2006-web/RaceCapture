#include <stdint.h>
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
static uint8_t rail_flags(const uint16_t adc[INPUT_COUNT])
{
    uint8_t flags = 0;
    uint8_t i;
    for (i = 0; i < INPUT_COUNT; ++i) {
        if (adc[i] <= ADC_LOW_MAX) flags |= (uint8_t)(1u << i);
        if (adc[i] >= ADC_HIGH_MIN) flags |= (uint8_t)(1u << (i + 3u));
    }
    return flags; /* Rail proximity only, NOT open/short detection. */
}

static unsigned char can_send_voltages(const uint16_t adc[INPUT_COUNT])
{
    volatile uint8_t *object;
    uint8_t i;
    if (!C1TXQSTALbits.TXQNIF) return 0;
    object = (volatile uint8_t *)(uintptr_t)C1TXQUA;
    if (object == 0) return 0;
    object[0] = 0x80; /* Standard identifier 0x580. */
    object[1] = 0x05;
    object[2] = 0;
    object[3] = 0;
    object[4] = 8; /* DLC=8, Classic CAN standard data frame. */
    object[5] = 0;
    object[6] = 0;
    object[7] = 0;
    for (i = 0; i < INPUT_COUNT; ++i) {
        object[8u + 2u*i] = (uint8_t)adc[i];
        object[9u + 2u*i] = (uint8_t)(adc[i] >> 8);
    }
    object[14] = rail_flags(adc);
    object[15] = 1; /* Voltage-only protocol version; no physical calibration. */
    C1TXQCONH = 0x03;
    return 1;
}

static uint16_t nominal_millivolts(uint16_t adc)
{
    return (uint16_t)(((uint32_t)adc * NOMINAL_VDD_MV + ADC_MAX / 2u) / ADC_MAX);
}

int main(void) {
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
