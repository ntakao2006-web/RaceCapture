import time
import sys

import serial


port = serial.Serial("COM8", 115200, timeout=0.1)

# A105 RTS drives EN. Keep GPIO0/DTR released and issue a normal reset.
port.dtr = False
port.rts = True
time.sleep(0.12)
port.rts = False

# Allow the caller to cover GNSS cold-start acquisition and the remaining tests.
capture_seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
deadline = time.time() + capture_seconds
pending = bytearray()
print("UART_MONITOR_READY", flush=True)

while time.time() < deadline:
    chunk = port.read(1024)
    if not chunk:
        continue
    pending.extend(chunk)
    while b"\n" in pending:
        raw, _, pending = pending.partition(b"\n")
        print(raw.decode("utf-8", errors="replace").rstrip("\r"), flush=True)

if pending:
    print(pending.decode("utf-8", errors="replace"), flush=True)
port.close()
