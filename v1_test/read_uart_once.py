import time

import serial


port = serial.Serial("COM8", 115200, timeout=0.2)
deadline = time.time() + 60
received = bytearray()

print("UART_MONITOR_READY", flush=True)
while time.time() < deadline:
    chunk = port.read(512)
    if chunk:
        received.extend(chunk)
        print("RX", chunk.hex(" "), flush=True)

print(f"UART_BYTES {len(received)}", flush=True)
port.close()
