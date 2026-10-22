import time

import serial


pattern = bytes.fromhex("55 aa 00 ff 12 34 56 78 43 4f 44 45 58")
port = serial.Serial("COM8", 115200, timeout=1.0)
port.reset_input_buffer()
port.write(pattern)
port.flush()
time.sleep(0.1)
received = port.read(len(pattern))
port.close()

print("TX", pattern.hex(" "))
print("RX", received.hex(" "))
print("LOOPBACK_PASS" if received == pattern else "LOOPBACK_FAIL")
