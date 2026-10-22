"""Read live thermistor reports from this bench's MPLAB Snap CDC port."""
import argparse
import re
import statistics
import time

import serial
from serial.tools import list_ports


SNAP_SERIAL = "021038102RYN014624"
REPORT = re.compile(
    r"^THERM adc=(\d+) r_ohm=(\d+) temp_c=(-?\d+\.\d{2}) "
    r"can_0x600=(sent|queued|busy)$"
)
FAULT = re.compile(
    r"^THERM adc=(\d+) status=(OPEN_OR_OVER_RANGE|SHORT_OR_UNDER_RANGE)"
    r"(?: can_0x600=(?:idle|queued|busy))?$"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")

    ports = [
        port
        for port in list_ports.comports()
        if port.serial_number == SNAP_SERIAL
        and port.vid == 0x04D8
        and port.pid == 0x90B1
    ]
    if len(ports) != 1:
        raise RuntimeError(f"Expected one Snap CDC port, found {ports!r}")

    samples = []
    faults = []
    with serial.Serial(ports[0].device, 115200, timeout=1) as uart:
        uart.reset_input_buffer()
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            line = uart.readline().decode("ascii", "replace").strip()
            if not line:
                continue
            print(line, flush=True)
            match = REPORT.match(line)
            if match:
                samples.append(
                    (int(match.group(1)), int(match.group(2)), float(match.group(3)),
                     match.group(4))
                )
            else:
                match = FAULT.match(line)
                if match:
                    faults.append((int(match.group(1)), match.group(2)))

    if not samples and not faults:
        raise RuntimeError("No valid thermistor reports received")
    if faults:
        print(
            "FAULT_SUMMARY "
            f"port={ports[0].device} reports={len(faults)} "
            f"open={sum(s[1] == 'OPEN_OR_OVER_RANGE' for s in faults)} "
            f"short={sum(s[1] == 'SHORT_OR_UNDER_RANGE' for s in faults)} "
            f"adc_min={min(s[0] for s in faults)} "
            f"adc_max={max(s[0] for s in faults)} "
            f"status_last={faults[-1][1]}"
        )
    if not samples:
        return
    temperatures = [sample[2] for sample in samples]
    print(
        "SUMMARY "
        f"port={ports[0].device} samples={len(samples)} "
        f"temp_mean_c={statistics.fmean(temperatures):.2f} "
        f"temp_min_c={min(temperatures):.2f} "
        f"temp_max_c={max(temperatures):.2f} "
        f"adc_last={samples[-1][0]} r_ohm_last={samples[-1][1]} "
        f"can_last={samples[-1][3]}"
    )


if __name__ == "__main__":
    main()
