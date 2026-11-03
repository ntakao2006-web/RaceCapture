# PIC18F26Q84 oil-temperature sensor hub

This project reads the Sense0 thermistor and publishes it to LoggerV2 CAN2 as the
oil-temperature channel used by RaceCapture.

## Behavior and wiring

- Device: PIC18F26Q84
- Clock: internal HFINTOSC at 64 MHz
- Schematic baseline: `circuit/SensorHub/SensorHub.kicad_sch`, saved 2026-10-19
- Divider: +5V -> R1/R2 (20 kOhm each in parallel = 10 kOhm) ->
  J3 pin 1 / Sense0 / RC3/ANC3 (PIC pin 14) -> NTC -> J3 pin 2 / GND
- ADC: 12-bit, VDD/VSS reference, 32-sample averaging
- Calibration: -1 C at 27.6 kOhm and 97 C at 1.145 kOhm
- UART: 115200 baud, 8N1, no flow control; reports every 500 ms
- CAN: Classic CAN 2.0 at 500 kbit/s, deployed bench RB2/TX (pin 23, MCP2561 pin 1)
  and RB3/RX (pin 24, MCP2561 pin 4), 10 Hz including fault notifications
- CAN standard ID `0x600`: signed little-endian `int16` oil temperature at
  bytes 0..1 with 0.01 C/bit; ADC at bytes 2..3; resistance ohms at bytes 4..7
- PIC pin 17 RC6/TX -> Snap pin 7
- PIC pin 18 RC7/RX <- Snap pin 8
- RA0 is held low; the former LED blink is not retained
- Programmer: MPLAB Snap

The old RC5 input (pin 16) is unconnected in this schematic. RB2 (pin 23)
is drawn as the 74LS595 clock in the saved schematic. The actual bench CAN
wire was retained at the user's request: V7 uses RB2 as CANTX and does not
operate the 74LS595. The current saved schematic instead specifies RB0 TX;
`CAN_TX_BIT` can select RB0 when the physical hardware is changed to match.
Sense1..4 use RA1..4 and manually switched 2.2 kOhm pull-ups; they are not
sampled by this single-channel firmware. The 74LS595 is not used to control
the Sense0 pull-up: R1/R2 are permanently connected to +5V.

An open Sense0 should read close to VDD (about 5 V with a 5 V supply).
ADC >= 4091 is reported as `OPEN_OR_OVER_RANGE`; ADC <= 4 is reported as
`SHORT_OR_UNDER_RANGE`. These are rail proximity checks, not a proof of the
particular electrical fault. V6 sends a reserved int16 temperature of -32768
in CAN 0x600 on faults. Open has ADC >=4091 and resistance 0xffffffff;
short has ADC <=4 and resistance 0. These are status packets, not -327.68 C.
The matching logger conversion `sensorhub_oiltemp` invalidates temperature
immediately and exposes a Japanese status label plus OilTempState and
OilTempOpen channels. After 1 second without a frame, the state is LINK loss
and temperature/Open flag are invalid. State codes: 0=OK, 1=OPEN, 2=SHORT,
3=bad packet, 4=LINK loss. OilTempOpen is 1 for OPEN and 0 for OK/SHORT.
The ADC is ratiometric and does not measure the absolute supply voltage.

ID 0x600 and its payload are retained for compatibility with the existing
OilTemp bench receiver. This is the legacy bench protocol, not the newer
generic SensorHub protocol/0x500 ID allocation in `sensorhub_generic_spec.md`.

The firmware emits `THERM adc=... r_ohm=... temp_c=... can_0x600=queued|busy`
or `THERM adc=... status=... can_0x600=queued|busy` every 500 ms.
`queued` means accepted by the PIC transmit queue; it does not prove CAN ACK
or reception by LoggerV2. `read_thermistor.py --seconds 10` accepts valid
measurements and fault reports. The
temperature is a two-point beta-model estimate from the handwritten sensor data;
it is not a production calibration. With a nearby reference thermometer at
24.3 C after about 10 minutes, the firmware reported about 23.6--23.7 C on
2026-10-03. The UART wiring and Snap CDC path are validated; evidence is under
`snap_uart_setup`.

## Installed official toolchain

- MPLAB X IDE / IPE 6.35
- MPLAB XC8 4.00
- Microchip PIC18F-Q_DFP 1.30.487

Run `build.ps1` to rebuild the HEX file. Run `program.ps1` to rebuild and
program the target through the connected Snap (MPLAB mode required). Restore
Snap CMSIS mode afterward for UART measurement with
`snap_uart_setup/read_thermistor.py --seconds 10`.
`test_uart.py` is for the former UART challenge/response firmware and is not
compatible with the current thermistor firmware.

V6 fixes the inherited CAN FIFO base address: PIC18F26/46/56Q84 CAN RAM is
0x2600..0x2dff. The previous 0x3800 address belongs to the larger x7Q84 memory
map and is unimplemented on this device. The TX queue uses two 8-byte objects
at 0x2600 and 0x2610. CAN diagnostic UART lines expose mode, error counters,
queue state and message count for future fault isolation.

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
