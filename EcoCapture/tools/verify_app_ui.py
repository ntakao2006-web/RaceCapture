"""Run the actual app UI against EcoLogger without vehicle CAN, with one USB-only interruption."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "v1_test/.tools"))
sys.path.insert(0, str(ROOT / "firmware/logger_v1/tools"))
from rcp_client import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--godot", type=Path)
    parser.add_argument("--exe", type=Path, default=ROOT / "EcoCapture/dist/EcoCapture/EcoCapture.exe")
    parser.add_argument("--uart", default="COM8")
    parser.add_argument("--reset-mode", choices=("usb", "full"), default="usb")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "ready-for-usb.json"
    if marker.exists():
        marker.unlink()
    command = ([str(args.godot), "--path", str(ROOT / "EcoCapture")] if args.godot else [str(args.exe.resolve())])
    command += ["--", "--hardware-test-dir", str(output)]
    if args.reset_mode == "full":
        command += ["--reconnect-test-only"]
    uart = Client(args.uart)
    before = uart.query({"getStatus": None})["status"]
    sent = False
    reset_at = None
    try:
        with (output / "app.log").open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            from windows_metrics import WindowsMetrics
            metrics = WindowsMetrics(proc.pid) if os.name == "nt" else None
            try:
                deadline = time.monotonic() + 180
                while proc.poll() is None and time.monotonic() < deadline:
                    if metrics:
                        metrics.sample()
                    if marker.exists() and not sent:
                        if args.reset_mode == "usb":
                            response = uart.query({"testUsbReconnect": {"confirm": "LOGGER_USB_ONLY"}})
                            if response["testUsbReconnect"]["rc"] != 1:
                                raise RuntimeError("USB-only test was rejected")
                        else:
                            # The CH9102 programming port owns EN/RTS. Pulse EN without
                            # entering the bootloader or writing flash.
                            uart.serial.dtr = False
                            uart.serial.rts = True
                            time.sleep(.15)
                            uart.serial.rts = False
                            reset_at = time.monotonic()
                        sent = True
                        print("App Race screen: " + ("USB-only interruption requested" if args.reset_mode == "usb" else "full logger reset requested"), flush=True)
                    time.sleep(.1)
                if proc.poll() is None:
                    raise TimeoutError("UI test did not finish in 180 seconds")
                code = proc.returncode
                performance = metrics.finish() if metrics else None
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)
        after = uart.query({"getStatus": None})["status"]
        report = json.loads((output / "hardware-ui.json").read_text(encoding="utf-8"))
        full_reset = args.reset_mode == "full"
        checks = {"app_passed": code == 0 and report["passed"], "reset_test_sent": sent,
            "no_can_rx": after["CAN"]["vehicleRx"] == 0 and after["CAN"]["hubRx"] == 0,
            "no_can_tx": after["CAN"]["hubTx"] == (0 if full_reset else before["CAN"]["hubTx"]) and after["CAN"]["vehicleListenOnly"],
            "sd_recording_healthy": after["logging"]["status"] == 1 and after["logging"]["rows"] > 0,
            "no_sd_drops": after["logging"]["drops"] == (0 if full_reset else before["logging"]["drops"]),
            "no_sd_errors": after["logging"]["errors"] == (0 if full_reset else before["logging"]["errors"]),
            "imu_healthy": (after["IMU"]["status"] == 5 and after["IMU"]["validSamples"] > 0) if full_reset else after["imuErrors"] == before["imuErrors"],
            "reset_lifecycle": (reset_at is not None and after["system"]["uptime"] <= time.monotonic() - reset_at + 5) if full_reset else after["system"]["uptime"] > before["system"]["uptime"]}
        # Every opaque pixel must be grayscale or the single red emphasis color.
        try:
            from PIL import Image, ImageChops
            differences = {}
            for path in output.glob("*.png"):
                image = Image.open(path).convert("RGB")
                invalid = sum(1 for r,g,b in image.getdata() if not (max(r,g,b)-min(r,g,b)<=2 or (abs(g-b)<=2 and r>=g+3)))
                differences[path.name] = invalid
            checks["panda_and_red_only"] = bool(differences) and max(differences.values()) == 0
        except ImportError:
            differences = {"note": "Pillow unavailable; inspect screenshots manually"}
        result = {"checks": checks, "reset_mode": args.reset_mode,
                  "sd_rows_after": after["logging"]["rows"],
                  "sd_rows_added": None if full_reset else after["logging"]["rows"] - before["logging"]["rows"],
                  "screenshots": differences, "ui_check_count": len(report["checks"]), "performance": performance,
                  "exe_sha256": hashlib.sha256(args.exe.read_bytes()).hexdigest() if not args.godot else None}
        (output / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if all(checks.values()) else 1
    finally:
        uart.close()


if __name__ == "__main__":
    raise SystemExit(main())
