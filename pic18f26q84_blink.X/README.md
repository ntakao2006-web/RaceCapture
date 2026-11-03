# PIC18F26Q84 Defi voltage-input firmware (v8, 2026-11-01)

## v8 files published on 2026-11-03

- Source: [main.c](main.c)
- Ready-to-program HEX: [pic18f26q84_blink.X.production.hex](dist/default/production/pic18f26q84_blink.X.production.hex)
- UNO Q handoff: [Defi voltage-input handoff](../UNOQ_Defi電圧入力対応_引継ぎ.md)
- HEX SHA-256: `F4238F8361CE4D4A2475EC8BCACC12AB2C6E32A040AD6FC2DE612291688B6E6E`

The published HEX matches the original handoff hash. On 2026-11-03 its Intel
HEX record checksums and embedded `VOLTAGE3 v8` banner were verified. XC8 was
unavailable in the publishing environment, so the existing HEX was preserved
without rebuilding. Publication does not mean the PIC has been programmed or
that v8 has passed hardware validation. The latest GitHub UNO Q receiver
changes were retained when publishing these files.

Current wiring supersedes the historical thermistor bench configuration below.
Only the PIC firmware project is changed; KiCad and logger software are untouched.

| Signal | PIC physical pin (28-pin package) | GPIO / ADC selector |
| --- | --- | --- |
| PRESS | 15 | RC4 / ANC4 / 0x14 |
| TEMP1 | 21 | RB0 / ANB0 / 0x08 |
| TEMP2 | 22 | RB1 / ANB1 / 0x09 |

All three pins are analog inputs with weak pull-ups disabled. No internal
pull-up, resistance measurement, thermistor conversion, or pressure calibration
is applied. External pull-ups and sensors are currently absent: a floating
input can produce any ADC value, including apparently plausible values. The
firmware cannot identify an open circuit without an external bias network.
HIGH_RAIL and LOW_RAIL report only rail proximity, never a confirmed open/short.

ADC: 12 bit, VDD/VSS reference, 100 us mux settling, one discarded conversion,
then 32-sample rounded average per channel. UART reports nominal millivolts as
round(ADC * 5000 / 4095); actual input voltage is ADC * actual VDD / 4095.
VDD is not measured, so nominal millivolts are an estimate, not a calibrated
absolute voltage. Unknown external pull-up values and pressure transfer curves
are deliberately not inferred from the Defi gauge's display ranges.

## Output

CAN: Classic CAN, 500 kbit/s, RB2 pin23 TX / RB3 pin24 RX unchanged.
Standard ID **0x580**, DLC 8, approximately 10 Hz. This uses the Defi accessory
allocation in `sensorhub_generic_spec.md`, not its generic discovery protocol.

| Bytes | Meaning |
| --- | --- |
| 0..1 | PRESS unsigned 12-bit ADC code in uint16 little-endian |
| 2..3 | TEMP1 unsigned ADC code, same format |
| 4..5 | TEMP2 unsigned ADC code, same format |
| 6 | bits 0/1/2: PRESS/TEMP1/TEMP2 <=4; bits 3/4/5: >=4091; bits 6/7 zero |
| 7 | Voltage-only payload version 1; no physical-unit calibration |

Legacy oil-temperature ID **0x600 is no longer sent**: the old OilTemp decoder
must not interpret an uncalibrated voltage as temperature. The existing logger
has not been configured for 0x580 by this change. Three readings arrive together
in one frame, so a two-object transmit queue does not drop the third channel.
UART RC6 pin17 TX / RC7 pin18 RX stays at 115200 8N1. Every five cycles it emits
PRESS/TEMP1/TEMP2 adc=... mv_nominal=... status=UNQUALIFIED|LOW_RAIL|HIGH_RAIL,
then enqueue state and CAN diagnostics. `queued` does not prove CAN reception.
The historical `read_thermistor.py` parser is not compatible with v8 output;
use a plain serial terminal for voltage reports.

## Build and validation

Run `build.ps1` with XC8 4.00 / PIC18F-Q_DFP 1.30.487 to generate
`dist/default/production/pic18f26q84_blink.X.production.hex`.
`program.ps1` builds, programs and verifies through Snap in MPLAB mode.
This revision was built successfully; host tests exercised the actual packet
encoder, queue-busy/null-address behavior, all rail boundaries, and nominal
voltage monotonicity for all 4096 ADC codes. No device programming or hardware
voltage accuracy/CAN-reception validation was performed for v8.

Defi reference: https://defi.nippon-seiki.co.jp/wp-content/uploads/2025/03/manual_dinstyle21_98.pdf

## 2026-11-03 programming

- Programmed this v8 HEX (SHA-256 `F4238F83...6E6E`) with MPLAB IPE 6.35 through the
  Snap in MPLAB mode, then returned the Snap to CMSIS-DAP. Device ID 0xa300;
  program and verify succeeded.
- Before programming, the device was read back and matched the v7 HEX exactly.
  Readback, IPE logs and the first UART output are in
  `outputs/sensorhub_20261103_v8_flash/`.
- UART: PRESS adc=0 (LOW_RAIL, not wired yet), TEMP1 about 2.02 V, TEMP2 about
  2.15 V with the Defi temperature harnesses attached; CAN txerr/rxerr 0.
  LoggerV2 received 0x580 at about 9.3 Hz with no CAN2 overflow increase.
- `snap_uart_setup/Set-SnapFirmware.ps1` now finds the switcher under
  `%LOCALAPPDATA%` and no longer aborts midway in Windows PowerShell 5.1.

## Historical evidence (earlier firmware, superseded)

## 2026-10-19 hardware check

- Built v4 with XC8 4.00 / Q_DFP 1.30.487, programmed PIC18F26Q84 device
  ID 0xa300, and completed full IPE verification successfully.
- Restored Snap CMSIS-DAP mode and read COM16 for 10 seconds: 21/21 reports
  were `OPEN_OR_OVER_RANGE`, ADC 4093..4095 with J3 open.
- The schematic SHA-256 stayed
  `38E444C0D34F06A30F4A4C307D943FD223C3B9A5FA1BDD29C8716BE65AD016D4`.
- Temperature with an attached thermistor and CAN ACK/logger reception were
  not verified. UNO Q serial 3263089125 was intermittently offline/absent in
  ADB after USB reconnection; logger firmware/configuration were not changed.
- Evidence, previous source/HEX, and the deployed v4 HEX are in
  `outputs/sensorhub_20261019/` at repository root.

### Follow-up: OilTemp registration and V6 fault reporting

OilTemp was registered on LoggerV2 CAN2 ID 0x600 with the explicit
`sensorhub_oiltemp` decoder. EcoCapture web/native displays Japanese fault
labels; RaceCapture has an added OilTemp/Open/State dashboard and receives
the auxiliary channels through RCP. Other dashboards and CAN definitions
were preserved. Decoder/RCP/server tests passed (11 + 5 + 21 tests).

Initially no frames reached LoggerV2 while trying the schematic's RB0 TX.
The PIC's recorded NBIT0ERR/TXBOERR indicates failed dominant-bit feedback.
A temporary 20 us GPIO probe before PPS setup read RB3 high in all three
phases (idle/high, TXD low, released/high: result 7; expected 5). PPS readback
was TX=0x46/RX=0x0b, TRISB=0xfe, ANSELB=0xf6. The probe was removed from
the final V6 release. Check PIC pin21 -> MCP2561 pin1, MCP2561 pin4 -> PIC
pin24, and MCP2561 power/GND/STBY (pins3/2/8). The user confirmed the CAN
cable, termination, and CAN-cable power supply to the PIC.

The user then asked to retain the earlier physical wiring. Selecting RB2 TX
and RB3 RX in V7 restored real CAN2 reception, with no physical wire changes.
The actual logger received OPEN packets: OilTemp=null, OilTempState=1,
OilTempOpen=1, and EcoCapture displayed オープン. The 0x2600 FIFO-base fix
is also required; the old 0x3800 base was outside this PIC's implemented RAM.
Normal/open/short/malformed/timeout transitions were verified with packet-level
tests; a physical thermistor temperature and a physical short remain unverified.
Follow-up evidence and
backups are in `outputs/sensorhub_20261019/oiltemp_status/`; the logger-side
backup is `/home/arduino/sensorhub-oiltemp-backup-20261019/`.
