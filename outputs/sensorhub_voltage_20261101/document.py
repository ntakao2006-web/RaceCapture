from pathlib import Path
p=Path('pic18f26q84_blink.X/README.md');s=p.read_text();history=s[s.index('## 2026-10-19 hardware check'):]
p.write_text('''# PIC18F26Q84 Defi voltage-input firmware (v8, 2026-11-01)

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

## Historical evidence (earlier firmware, superseded)

'''+history)
