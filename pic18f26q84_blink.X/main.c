#include <xc.h>
#include <stdint.h>

/* PIC18F26Q84, 28-pin package: external voltage inputs only.
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

/* Internal 64 MHz oscillator; no external oscillator required. */
#pragma config FEXTOSC = OFF
#pragma config RSTOSC = HFINTOSC_64MHZ
#pragma config CLKOUTEN = OFF
#pragma config PR1WAY = ON
#pragma config CSWEN = ON
#pragma config JTAGEN = OFF
#pragma config FCMEN = OFF
#pragma config FCMENP = OFF
#pragma config FCMENS = OFF

/* Reset and basic safety settings. */
#pragma config MCLRE = EXTMCLR
#pragma config PWRTS = PWRT_64
#pragma config MVECEN = OFF
#pragma config IVT1WAY = ON
#pragma config LPBOREN = OFF
#pragma config BOREN = SBORDIS
#pragma config BORV = VBOR_2P45
#pragma config ZCD = OFF
#pragma config PPS1WAY = ON
#pragma config STVREN = ON
#pragma config LVP = ON
#pragma config XINST = OFF

/* Watchdog disabled for this deterministic hardware test. */
#pragma config WDTCPS = WDTCPS_31
#pragma config WDTE = OFF
#pragma config WDTCWS = WDTCWS_7
#pragma config WDTCCS = SC

/* No boot block, protection, debugger, or boot-time CRC. */
#pragma config BBSIZE = BBSIZE_512
#pragma config BBEN = OFF
#pragma config SAFEN = OFF
#pragma config DEBUG = OFF
#pragma config WRTB = OFF
#pragma config WRTC = OFF
#pragma config WRTD = OFF
#pragma config WRTSAF = OFF
#pragma config WRTAPP = OFF
#pragma config BOOTPINSEL = RA4
#pragma config BPEN = OFF
#pragma config ODCON = OFF
#pragma config CP = OFF
#pragma config BOOTSCEN = OFF
#pragma config BOOTCOE = CONTINUE
#pragma config APPSCEN = OFF
#pragma config SAFSCEN = OFF
#pragma config DATASCEN = OFF
#pragma config CFGSCEN = OFF
#pragma config COE = CONTINUE
#pragma config BOOTPOR = OFF

static void uart_init(void)
{
    ANSELA &= (unsigned char)~0x01u;
    LATA &= (unsigned char)~0x01u;
    TRISA &= (unsigned char)~0x01u;

    PMD6bits.U1MD = 0;
    ANSELC &= (unsigned char)~0xC0u;
    LATCbits.LATC6 = 1;
    ODCONCbits.ODCC6 = 0;
    TRISCbits.TRISC6 = 0;
    TRISCbits.TRISC7 = 1;

    /* Interrupts are disabled; unlock PPS once, configure, then relock. */
    PPSLOCK = 0x55;
    PPSLOCK = 0xAA;
    PPSLOCKbits.PPSLOCKED = 0;
    RC6PPS = 0x20; /* Q84 TX1 output function (not the K42 value). */
    U1RXPPS = 0x17; /* RC7. */
    RB0PPS = 0; /* Remove any digital output assignment on voltage inputs. */
    RB1PPS = 0;
    RC4PPS = 0;
    CAN_TX_PPS = 0x46; /* CANTX -> MCP2561 TXD; keep the existing wire. */
    CANRXPPS = 0x0B; /* RB3. */
    PPSLOCK = 0x55;
    PPSLOCK = 0xAA;
    PPSLOCKbits.PPSLOCKED = 1;

    U1CON1 = 0;
    U1CON0 = 0xB0; /* BRGS=1, TXEN=1, RXEN=1, 8-bit asynchronous. */
    U1CON2 = 0x80; /* Continue after RX overflow; normal polarity, 1 stop. */
    U1BRG = 138; /* 64 MHz / (4 * 139) = 115107.9 baud, -0.08%. */
    U1CON1bits.ON = 1;
}

static void can_init(void)
{
    PMD2bits.CANMD = 0;
    ANSELB &= (uint8_t)~((1u << CAN_TX_BIT) | 0x08u);
    LATB |= (uint8_t)(1u << CAN_TX_BIT);
    TRISB &= (uint8_t)~(1u << CAN_TX_BIT);
    TRISBbits.TRISB3 = 1;

    C1CONHbits.ON = 1;
    C1CONT = 0x04;
    C1CONU = 0x90; /* Enable TX queue. */
    C1CONTbits.REQOP = 4; /* Configuration mode. */
    while (C1CONUbits.OPMOD != 4) { }

    C1FIFOBAL = (uint8_t)CAN_FIFO_BASE;
    C1FIFOBAH = (uint8_t)(CAN_FIFO_BASE >> 8);
    C1CONH = 0x87;
    C1CONL = 0x60;
    C1CONU = 0x10; /* TXQ enabled, TEF disabled, unlimited retries. */

    /* 64 MHz / (1 + 100 + 27) = 500 kbit/s, 78.9% sample point. */
    C1NBTCFGL = 0x1A; /* SJW = 27 TQ. */
    C1NBTCFGH = 0x1A; /* TSEG2 = 27 TQ. */
    C1NBTCFGU = 0x63; /* TSEG1 = 100 TQ. */
    C1NBTCFGT = 0x00; /* BRP = 1. */

    C1TXQCONL = 0x80; /* TX queue enabled. */
    C1TXQCONH = 0x04; /* Reset queue. */
    C1TXQCONU = 0x60; /* Unlimited retransmission, priority 0. */
    C1TXQCONT = 0x01; /* Two messages, 8-byte payload. */

    C1CONTbits.REQOP = 6; /* Classic CAN 2.0 normal mode. */
    while (C1CONUbits.OPMOD != 6) { }
    while (C1TXQCONHbits.FRESET) { }
}

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

static void uart_puts(const char *text)
{
    while (*text) {
        while (U1FIFObits.TXBF) { }
        U1TXB = (unsigned char)*text++;
    }
}

static void uart_put_uint32(uint32_t value)
{
    char digits[10];
    unsigned char count = 0;

    do {
        digits[count++] = (char)('0' + (value % 10u));
        value /= 10u;
    } while (value != 0u);
    while (count != 0u) {
        while (U1FIFObits.TXBF) { }
        U1TXB = (unsigned char)digits[--count];
    }
}

static void report_can_diagnostics(void)
{
    uart_puts("CAN op=");uart_put_uint32(C1CONUbits.OPMOD);
    uart_puts(" txerr=");uart_put_uint32(C1TRECH);
    uart_puts(" rxerr=");uart_put_uint32(C1TRECL);
    uart_puts(" trecu=");uart_put_uint32(C1TRECU);
    uart_puts(" txq=");uart_put_uint32(C1TXQSTAL);
    uart_puts(" req=");uart_put_uint32(C1TXQCONH);
    uart_puts(" ua=");uart_put_uint32(C1TXQUA);
    uart_puts(" conl=");uart_put_uint32(C1CONL);
    uart_puts(" conh=");uart_put_uint32(C1CONH);
    uart_puts(" conu=");uart_put_uint32(C1CONU);
    uart_puts(" cont=");uart_put_uint32(C1CONT);
    uart_puts(" rb3=");uart_put_uint32(PORTBbits.RB3);
    uart_puts(" nmsg=");uart_put_uint32((uint16_t)C1BDIAG1L | ((uint16_t)C1BDIAG1H<<8));
    uart_puts(" qsize=");uart_put_uint32(C1TXQCONT);
    uart_puts(" qcfg=");uart_put_uint32(C1TXQCONU);
    uart_puts(" qenable=");uart_put_uint32(C1TXQCONL);
    uart_puts(" diag1u=");uart_put_uint32(C1BDIAG1U);
    uart_puts(" diag1t=");uart_put_uint32(C1BDIAG1T);
    uart_puts(" txpps=");uart_put_uint32(CAN_TX_PPS);
    uart_puts(" rxpps=");uart_put_uint32(CANRXPPS);
    uart_puts(" tris=");uart_put_uint32(TRISB);
    uart_puts(" ansel=");uart_put_uint32(ANSELB);
    uart_puts("\r\n");
}

static void adc_init(void)
{
    PMD3bits.ADCMD = 0;
    TRISCbits.TRISC4 = 1;
    ANSELCbits.ANSELC4 = 1;
    WPUCbits.WPUC4 = 0;
    TRISB |= 0x03u;
    ANSELB |= 0x03u;
    WPUB &= (uint8_t)~0x03u;
    ADPCH = 0x14; /* PRESS: ANC4. */
    ADREF = 0x00;  /* VDD/VSS reference. Absolute voltage needs the actual VDD. */
    ADCLK = 31;    /* FOSC/64 = 1 MHz ADC clock at 64 MHz FOSC. */
    ADACQ = 64;    /* 64 ADC clocks of acquisition time. */
    ADCON1 = 0x00;
    ADCON2 = 0x00; /* Basic single conversion mode. */
    ADCON3 = 0x00;
    ADCON0 = 0x84; /* ADC on, right justified, FOSC/ADCLK, single conversion. */
}

static uint16_t adc_read_average(uint8_t channel)
{
    uint32_t sum = 0;
    unsigned char index;

    ADPCH = channel;
    __delay_us(100); /* Allow the new external source to settle after mux switch. */
    ADCON0bits.GO = 1; /* Discard the first conversion after changing channel. */
    while (ADCON0bits.GO) { }
    for (index = 0; index < 32u; ++index) {
        ADCON0bits.GO = 1;
        while (ADCON0bits.GO) { }
        sum += (uint16_t)(ADRES & 0x0FFFu);
    }
    return (uint16_t)((sum + 16u) / 32u);
}

static uint16_t nominal_millivolts(uint16_t adc)
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
    uart_puts("\r\n");
}

void main(void)
{
    uint8_t cycle = 0;
    uart_init();
    adc_init();
    can_init();
    uart_puts("READY PIC18F26Q84 VOLTAGE3 v8 PRESS_RC4 TEMP1_RB0 TEMP2_RB1 "
              "NO_PULLUPS VDD_NOMINAL_5000mV CANTX_RB2 CANRX_RB3 CAN500 ID580\r\n");
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
            uart_puts(sent ? "queued\r\n" : "busy\r\n");
            report_can_diagnostics();
        }
        __delay_ms(100);
    }
}
