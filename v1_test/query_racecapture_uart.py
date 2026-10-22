import json
import sys
import time

import serial


port = serial.Serial()
port.port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
port.baudrate = 115200
port.timeout = 0.1
port.dtr = False
port.rts = False
port.open()

# The diagnostic firmware initializes the A105 RaceCapture endpoint after its
# short CAN/GNSS preflight. Opening the port does not deliberately reset it.
startup_wait = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
time.sleep(startup_wait)
port.reset_input_buffer()

for command in (
    {"getVer": {}},
    {"getCapabilities": {}},
    {"getMeta": {}},
    {"getImuCfg": {}},
    {"s": {"meta": True}},
):
    port.write((json.dumps(command, separators=(",", ":")) + "\r\n").encode())
    port.flush()
    # A metadata reply is several kilobytes at 115200 baud; leave enough time
    # before issuing the next command on the same half-duplex test workflow.
    time.sleep(0.75)

deadline = time.time() + 8
responses = []
while time.time() < deadline:
    raw = port.readline()
    if not raw:
        continue
    try:
        response = json.loads(raw.decode(errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        continue
    responses.append(response)
    print(json.dumps(response, ensure_ascii=False), flush=True)

port.close()
if len(responses) < 5:
    raise SystemExit(f"Expected 5 RaceCapture replies, received {len(responses)}")
