from pathlib import Path
p=Path('pic18f26q84_blink.X/main.c')
s=p.read_text()
a=s.index('/*'); b=s.index('/* Internal 64 MHz')
s=s[:a]+'''/* PIC18F26Q84, 28-pin package: external voltage inputs only.
 * PRESS=pin15 RC4/ANC4, TEMP1=pin21 RB0/ANB0, TEMP2=pin22 RB1/ANB1.
 * No internal pull-ups or assumed external divider/sensor calibration.
 * UART RC6/RC7 115200; CAN RB2/RB3 500 kbit/s.
 * CAN 0x580, 10 Hz: three uint16 LE ADC codes, rail flags, version=1.
 * Legacy thermistor packet 0x600 is deliberately no longer transmitted.
 */
#define _XTAL_FREQ 64000000UL
#define INPUT_COUNT 3u
#define ADC_MAX 4095u
#define ADC_LOW_MAX 4u
#define ADC_HIGH_MIN 4091u
#define NOMINAL_VDD_MV 5000UL /* Estimate only; actual VDD is not measured. */
#define CAN_FIFO_BASE 0x2600u
#define CAN_TX_BIT 2u
#define CAN_TX_PPS RB2PPS
#define CAN_TX_NAME "RB2"

'''+s[b:]
a=s.index('static unsigned char can_send_oil_temperature'); b=s.index('static void uart_puts',a)
s=s[:a]+'''static uint8_t rail_flags(const uint16_t adc[INPUT_COUNT])
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

'''+s[b:]
a=s.index('    TRISCbits.TRISC3 = 1;');b=s.index('    ADREF =',a)
s=s[:a]+'''    TRISCbits.TRISC4 = 1;
    ANSELCbits.ANSELC4 = 1;
    WPUCbits.WPUC4 = 0;
    TRISB |= 0x03u;
    ANSELB |= 0x03u;
    WPUB &= (uint8_t)~0x03u;
    RB0PPS = 0; /* Remove any digital output assignment on voltage inputs. */
    RB1PPS = 0;
    RC4PPS = 0;
    ADPCH = 0x14; /* PRESS: ANC4. */
'''+s[b:]
s=s.replace('/* VDD and VSS references: divider result is ratiometric. */','/* VDD/VSS reference. Absolute voltage needs the actual VDD. */')
s=s.replace('static uint16_t adc_read_average(void)','static uint16_t adc_read_average(uint8_t channel)')
s=s.replace('    for (index = 0; index < 32u; ++index) {','''    ADPCH = channel;
    __delay_us(100); /* Allow the new external source to settle after mux switch. */
    ADCON0bits.GO = 1; /* Discard the first conversion after changing channel. */
    while (ADCON0bits.GO) { }
    for (index = 0; index < 32u; ++index) {''')
a=s.index('static int32_t thermistor_centi_c')
s=s[:a]+'''static uint16_t nominal_millivolts(uint16_t adc)
{
    return (uint16_t)(((uint32_t)adc * NOMINAL_VDD_MV + ADC_MAX / 2u) / ADC_MAX);
}

static void report_voltage(const char *name, uint16_t adc)
{
    uart_puts(name);
    uart_puts(" adc=");
    uart_put_uint32(adc);
    uart_puts(" mv_nominal=");
    uart_put_uint32(nominal_millivolts(adc));
    uart_puts(" status=");
    uart_puts(adc <= ADC_LOW_MAX ? "LOW_RAIL" :
              adc >= ADC_HIGH_MIN ? "HIGH_RAIL" : "UNQUALIFIED");
    uart_puts("\\r\\n");
}

void main(void)
{
    uint8_t cycle = 0;
    uart_init();
    adc_init();
    can_init();
    uart_puts("READY PIC18F26Q84 VOLTAGE3 v8 PRESS_RC4 TEMP1_RB0 TEMP2_RB1 "
              "NO_PULLUPS VDD_NOMINAL_5000mV CANTX_RB2 CANRX_RB3 CAN500 ID580\\r\\n");
    while (1) {
        uint16_t adc[INPUT_COUNT];
        unsigned char sent;
        adc[0] = adc_read_average(0x14); /* PRESS, pin 15. */
        adc[1] = adc_read_average(0x08); /* TEMP1, pin 21. */
        adc[2] = adc_read_average(0x09); /* TEMP2, pin 22. */
        sent = can_send_voltages(adc);
        if (++cycle == 5u) {
            cycle = 0;
            report_voltage("PRESS", adc[0]);
            report_voltage("TEMP1", adc[1]);
            report_voltage("TEMP2", adc[2]);
            uart_puts("VOLTAGE can_0x580=");
            uart_puts(sent ? "queued\\r\\n" : "busy\\r\\n");
            report_can_diagnostics();
        }
        __delay_ms(100);
    }
}
'''
s=s.replace('#include <math.h>\n','')
p.write_text(s)
