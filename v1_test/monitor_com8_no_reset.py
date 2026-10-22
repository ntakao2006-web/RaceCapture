import sys
import time

import serial


seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
port = serial.Serial()
port.port = "COM8"
port.baudrate = 115200
port.timeout = 0.1
port.dtr = False
port.rts = False
port.open()

deadline = time.time() + seconds
pending = bytearray()
while time.time() < deadline:
    chunk = port.read(1024)
    if not chunk:
        continue
    pending.extend(chunk)
    while b"\n" in pending:
        raw, _, pending = pending.partition(b"\n")
        print(raw.decode("utf-8", errors="replace").rstrip("\r"), flush=True)

port.close()
