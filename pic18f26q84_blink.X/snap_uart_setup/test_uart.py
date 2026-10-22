"""Real PIC UART challenge/response test through this bench's Snap only."""
import argparse
import datetime
import json
from pathlib import Path
import secrets
import time

import serial
from serial.tools import list_ports

SNAP_SERIAL = "021038102RYN014624"
IDENTITY = b"PIC18F26Q84 UART1 RC6-TX RC7-RX 115200 8N1 v1\r\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("count must be positive")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log = Path(__file__).parent / f"uart_test_{stamp}.jsonl"
    passed = 0
    with log.open("x", encoding="utf-8") as output:
        def record(event, **details):
            entry = {"time": datetime.datetime.now().isoformat(),
                     "event": event, **details}
            output.write(json.dumps(entry, ensure_ascii=False) + "\n")
            output.flush()
            print(json.dumps(entry, ensure_ascii=False), flush=True)

        try:
            ports = [p for p in list_ports.comports()
                     if p.serial_number == SNAP_SERIAL
                     and p.vid == 0x04D8 and p.pid == 0x90B1]
            if len(ports) != 1:
                raise RuntimeError(f"Expected one Snap CDC port, found {ports!r}")
            port = ports[0]
            record("port", device=port.device, hwid=port.hwid,
                   baud=115200, format="8N1", flow_control=False)
            with serial.Serial(port.device, 115200, timeout=0.2,
                               write_timeout=2, rtscts=False, dsrdtr=False,
                               xonxoff=False) as uart:
                uart.dtr = True
                uart.rts = False
                time.sleep(0.3)
                uart.reset_input_buffer()

                def exchange(command, expected):
                    nonlocal passed
                    record("tx", text=command.decode("ascii"))
                    uart.write(command)
                    uart.flush()
                    deadline = time.monotonic() + 3
                    pending = bytearray()
                    while time.monotonic() < deadline:
                        pending.extend(uart.read(max(1, uart.in_waiting)))
                        while b"\n" in pending:
                            end = pending.index(10) + 1
                            line = bytes(pending[:end])
                            del pending[:end]
                            record("rx", text=line.decode("ascii", "backslashreplace"),
                                   hex=line.hex())
                            if line.startswith(b"READY PIC18F26Q84 UART1"):
                                continue
                            if line != expected:
                                raise RuntimeError(f"Response mismatch: {line!r} != {expected!r}")
                            passed += 1
                            return
                    raise TimeoutError(f"No matching PIC response; partial={bytes(pending)!r}")

                # A MCU-generated response excludes a passive TX/RX loopback.
                exchange(b"ID?\r\n", IDENTITY)
                for index in range(args.count):
                    size = (1, 8, 31, 64, 120)[index % 5]
                    token = secrets.token_hex(60)[:size].encode("ascii")
                    if index % 2:
                        exchange(b"ECHO " + token + b"\r\n", b"OK " + token + b"\r\n")
                    else:
                        exchange(b"PING " + token + b"\r\n", b"PONG " + token + b"\r\n")
                exchange(b"INVALID\r\n", b"ERR COMMAND\r\n")
                exchange(b"ECHO " + b"x" * 150 + b"\r\n", b"ERR LENGTH\r\n")
                exchange(b"ID?\r\n", IDENTITY)
                record("PASS", exchanges=passed, log=str(log))
        except Exception as error:
            record("FAIL", exchanges=passed, error=repr(error), log=str(log))
            raise


if __name__ == "__main__":
    main()
