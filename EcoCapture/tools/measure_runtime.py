"""Measure stationary, real-USB pages in the exported Windows executable. Does not reset hardware."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import time
from windows_metrics import WindowsMetrics


def close_window(pid):
    user = ctypes.WinDLL("user32")
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

    def visit(hwnd, _):
        found = ctypes.c_ulong()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
        if found.value == pid:
            user.PostMessageW(hwnd, 0x10, 0, 0)  # Normal WM_CLOSE, not process termination.
        return True

    callback = callback_type(visit)
    user.EnumWindows(callback, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exe", type=Path, default=Path(__file__).resolve().parents[1]/"dist/EcoCapture/EcoCapture.exe")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for page in ("home", "indicate", "maps"):
        with (output/(page+".log")).open("w") as log:
            proc = subprocess.Popen([str(args.exe.resolve()), "--", "--screen", page, "--data-dir", str(output/"profile")],
                                    stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            meter = WindowsMetrics(proc.pid)
            try:
                time.sleep(5)
                meter.sample()
                initial_cpu = meter.cpu
                start = time.monotonic()
                for _ in range(200):
                    if proc.poll() is not None:
                        raise RuntimeError("App exited during measurement")
                    meter.sample()
                    time.sleep(.1)
                seconds = time.monotonic()-start
                result = meter.finish()
                result["steady_cpu_percent_of_one_core"] = round((meter.cpu-initial_cpu)/seconds*100, 1)
                result["steady_seconds"] = round(seconds, 2)
                result["page"] = page
                result["note"] = "Windows real EcoLogger, no CAN, 5 seconds warmup + 20 seconds stationary. CPU percentage uses one logical core as 100%."
                results[page] = result
                print(json.dumps(result), flush=True)
            finally:
                close_window(proc.pid)
                proc.wait(timeout=10)
    (output/"performance.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
