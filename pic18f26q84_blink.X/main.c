#include <xc.h>
#include <math.h>
#include <stdint.h>

/*
 * PIC18F26Q84 thermistor bench test.
 * SensorHub.kicad_sch (2026-10-19): J3 Sense0 is RC3/ANC3, pin 14.
 * VDD -- (R1 20 kohm || R2 20 kohm) -- Sense0 -- NTC -- GND.
 * RC6/pin17=TX, RC7/pin18=RX at 115200 baud, 8N1, no flow control.
 * Existing bench: RB2/pin23=CANTX and RB3/pin24=CANRX. The saved schematic
 * uses RB0/pin21 instead; keep the user's existing wire and select TX in software.
 * Classic CAN 2.0, 500 kbit/s, standard ID
 * 0x600, 10 Hz.  Bytes 0..1 are signed oil temperature in 0.01 C,
 * bytes 2..3 are the ADC result, and bytes 4..7 are resistance in ohms.
 * The temperature conversion is a two-point beta fit from the handwritten
 * sensor data: -1 C at 27.6 kohm and 97 C at 1.145 kohm.
 */

#define _XTAL_FREQ 64000000UL
#define THERM_PULLUP_OHM 10000UL
#define THERM_SHORT_ADC_MAX 4u
#define THERM_OPEN_ADC_MIN 4091u
#define THERM_INVALID_CENTI_C (-32768L)
#define CAN_FIFO_BASE 0x2600u /* PIC18F26/46/56Q84 CAN RAM: 0x2600..0x2DFF. */
/* Existing bench wiring is retained at the user's request. Saved schematic
 * TX is RB0; the earlier wired bench uses RB2. Select in firmware only. */
#define CAN_TX_BIT 2u
#if CAN_TX_BIT == 0u
#define CAN_TX_PPS RB0PPS
#define CAN_TX_NAME "RB0"
#elif CAN_TX_BIT == 2u
#define CAN_TX_PPS RB2PPS
#define CAN_TX_NAME "RB2"
#else
#error Unsupported bench CAN TX pin
#endif

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

static unsigned char can_send_oil_temperature(int32_t centi_c,
                                               uint16_t adc,
                                               uint32_t resistance)
{
    volatile uint8_t *object;
    int16_t oil_temp;

    if (!C1TXQSTALbits.TXQNIF) return 0;
    if (centi_c > 32767) centi_c = 32767;
    if (centi_c < -32768) centi_c = -32768;
    oil_temp = (int16_t)centi_c;
    object = (volatile uint8_t *)(uintptr_t)C1TXQUA;
    if (object == 0) return 0;

    object[0] = 0x00; /* Standard identifier 0x600. */
    object[1] = 0x06;
    object[2] = 0x00;
    object[3] = 0x00;
    object[4] = 0x08; /* DLC=8, standard data frame, Classic CAN. */
    object[5] = 0x00;
    object[6] = 0x00;
    object[7] = 0x00;
    object[8] = (uint8_t)oil_temp;
    object[9] = (uint8_t)((uint16_t)oil_temp >> 8);
    object[10] = (uint8_t)adc;
    object[11] = (uint8_t)(adc >> 8);
    object[12] = (uint8_t)resistance;
    object[13] = (uint8_t)(resistance >> 8);
    object[14] = (uint8_t)(resistance >> 16);
    object[15] = (uint8_t)(resistance >> 24);
    C1TXQCONH = 0x03; /* Increment queue and request transmission. */
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
    TRISCbits.TRISC3 = 1;
    ANSELCbits.ANSELC3 = 1;
    WPUCbits.WPUC3 = 0; /* Only the external 10 kohm pull-up sets the divider. */

    ADPCH = 0x13;  /* ANC3 / RC3, Sense0 at J3/1. */
    ADREF = 0x00;  /* VDD and VSS references: divider result is ratiometric. */
    ADCLK = 31;    /* FOSC/64 = 1 MHz ADC clock at 64 MHz FOSC. */
    ADACQ = 64;    /* 64 ADC clocks of acquisition time. */
    ADCON1 = 0x00;
    ADCON2 = 0x00; /* Basic single conversion mode. */
    ADCON3 = 0x00;
    ADCON0 = 0x84; /* ADC on, right justified, FOSC/ADCLK, single conversion. */
}

static uint16_t adc_read_average(void)
{
    uint32_t sum = 0;
    unsigned char index;

    for (index = 0; index < 32u; ++index) {
        ADCON0bits.GO = 1;
        while (ADCON0bits.GO) { }
        sum += (uint16_t)(ADRES & 0x0FFFu);
    }
    return (uint16_t)((sum + 16u) / 32u);
}

static int32_t thermistor_centi_c(uint32_t resistance_ohm)
{
    const double hot_kelvin = 370.15;
    const double hot_resistance = 1145.0;
    const double beta_kelvin = 3271.26933158336;
    double inverse_kelvin;
    double centi_c;

    inverse_kelvin = (1.0 / hot_kelvin)
                   + log((double)resistance_ohm / hot_resistance) / beta_kelvin;
    centi_c = ((1.0 / inverse_kelvin) - 273.15) * 100.0;
    return (int32_t)(centi_c + (centi_c >= 0.0 ? 0.5 : -0.5));
}

static void report_measurement(uint16_t adc, uint32_t resistance,
                               int32_t centi_c, unsigned char can_sent)
{
    uint32_t magnitude;

    uart_puts("THERM adc=");
    uart_put_uint32(adc);
    if (adc >= THERM_OPEN_ADC_MIN) {
        uart_puts(" status=OPEN_OR_OVER_RANGE can_0x600=");
        uart_puts(can_sent ? "queued\r\n" : "busy\r\n");
        return;
    }
    if (adc <= THERM_SHORT_ADC_MAX) {
        uart_puts(" status=SHORT_OR_UNDER_RANGE can_0x600=");
        uart_puts(can_sent ? "queued\r\n" : "busy\r\n");
        return;
    }

    magnitude = (uint32_t)(centi_c < 0 ? -centi_c : centi_c);

    uart_puts(" r_ohm=");
    uart_put_uint32(resistance);
    uart_puts(" temp_c=");
    if (centi_c < 0) uart_puts("-");
    uart_put_uint32(magnitude / 100u);
    uart_puts(".");
    if ((magnitude % 100u) < 10u) uart_puts("0");
    uart_put_uint32(magnitude % 100u);
    uart_puts(" can_0x600=");
    /* Enqueue success alone does not prove bus acknowledgement or reception. */
    uart_puts(can_sent ? "queued" : "busy");
    uart_puts("\r\n");
}

void main(void)
{
    uart_init();
    adc_init();
    can_init();
    uart_puts("READY PIC18F26Q84 OILTEMP SENSE0 RC3 PU10000 CANTX_" CAN_TX_NAME " CANRX_RB3 CAN500 ID600 v7 FAULT_CAN RAM2600\r\n");

    while (1) {
        unsigned char cycle;
        unsigned char sent = 0;
        for (cycle = 0; cycle < 5u; ++cycle) {
            uint16_t adc = adc_read_average();
            uint32_t resistance;
            int32_t centi_c;

            if (adc <= THERM_SHORT_ADC_MAX || adc >= THERM_OPEN_ADC_MIN) {
                /* Reserved invalid temperature; ADC and resistance distinguish faults.
                 * Open: resistance=UINT32_MAX. Short: resistance=0. */
                resistance = adc >= THERM_OPEN_ADC_MIN ? UINT32_MAX : 0;
                sent = can_send_oil_temperature(THERM_INVALID_CENTI_C, adc, resistance);
                if (cycle == 4u) {
                    report_measurement(adc, resistance, THERM_INVALID_CENTI_C, sent);
                }
            } else {
                resistance = (THERM_PULLUP_OHM * adc + ((4095u - adc) / 2u)) /
                             (4095u - adc);
                centi_c = thermistor_centi_c(resistance);
                sent = can_send_oil_temperature(centi_c, adc, resistance);
                if (cycle == 4u) {
                    report_measurement(adc, resistance, centi_c, sent);
                }
            }
            __delay_ms(100);
        }
        report_can_diagnostics();
    }
}
