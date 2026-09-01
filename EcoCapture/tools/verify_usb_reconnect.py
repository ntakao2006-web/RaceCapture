"""Bench-only USB detach test. Does not stop SD, flash, erase, or change CAN settings."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "v1_test" / ".tools"))
sys.path.insert(0, str(ROOT / "firmware" / "logger_v1" / "tools"))
from rcp_client import Client


def summary(result):
    s = result["status"]
    return {"uptime": s["system"]["uptime"], "logging": s["logging"],
            "imuErrors": s["imuErrors"], "gnssErrors": s["gnssErrors"],
            "usbDrops": s["usbDrops"], "CAN": s["CAN"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uart", default="COM8")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    client = Client(args.uart)
    try:
        before = summary(client.query({"getStatus": None}))
        with (args.output / "bench.log").open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(["dotnet", "run", "--no-build", "--project",
                str(ROOT / "EcoCapture/tests/EcoCapture.Tests.csproj"), "--", "--bench", "--seconds", "45",
                "--output", str(args.output / "connection.json")], stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                start = time.monotonic()
                events = []
                for target in (7, 19, 31):
                    while time.monotonic() - start < target:
                        if proc.poll() is not None:
                            raise RuntimeError("Bench receiver stopped early; inspect bench.log")
                        time.sleep(.1)
                    response = client.query({"testUsbReconnect": {"confirm": "LOGGER_USB_ONLY"}})
                    if response["testUsbReconnect"]["rc"] != 1:
                        raise RuntimeError("USB diagnostic rejected")
                    events.append({"atSeconds": time.monotonic() - start, "response": response})
                    print(f"USB-only detach {len(events)}/3 requested; SD left running", flush=True)
                code = proc.wait(timeout=25)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
        after = summary(client.query({"getStatus": None}))
        connection = json.loads((args.output / "connection.json").read_text(encoding="utf-8"))
        checks = {"receiver_passed": code == 0,
                  "four_connections": connection["info"]["Connections"] >= 4,
                  "no_bad_frames": connection["info"]["BadFrames"] == 0,
                  "no_reboot": after["uptime"] > before["uptime"],
                  "sd_rows_increase": after["logging"]["rows"] > before["logging"]["rows"],
                  "no_new_sd_errors": after["logging"]["errors"] == before["logging"]["errors"],
                  "no_new_sd_drops": after["logging"]["drops"] == before["logging"]["drops"],
                  "no_new_imu_errors": after["imuErrors"] == before["imuErrors"],
                  "vehicle_listen_only": after["CAN"]["vehicleListenOnly"] is True}
        result = {"checks": checks, "before": before, "after": after, "events": events}
        (args.output / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(checks, ensure_ascii=False), flush=True)
        return 0 if all(checks.values()) else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
