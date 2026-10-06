"""Persist bounded evidence that distinguishes a clean shutdown from a hard reset."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_DIR = Path("/var/lib/logger-v2-incident")
CURRENT_STATE = STATE_DIR / "current.json"
INCIDENT_DIR = STATE_DIR / "incidents"
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")
PSTORE_DIR = Path("/sys/fs/pstore")
STATUS_URL = "http://127.0.0.1:8080/api/status"
MAX_INCIDENTS = 10
MAX_JOURNAL_BYTES = 512 * 1024
MAX_PSTORE_FILE_BYTES = 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_boot_id() -> str:
    return BOOT_ID_PATH.read_text(encoding="ascii").strip()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def classify_previous(previous: dict[str, Any] | None, current_boot_id: str) -> str:
    if not previous or not previous.get("boot_id"):
        return "none"
    if previous["boot_id"] == current_boot_id:
        return "same_boot_restart"
    if previous.get("clean_shutdown") is True:
        return "clean_reboot"
    return "unclean_reboot"


def read_uptime_seconds() -> float | None:
    try:
        return round(float(Path("/proc/uptime").read_text().split()[0]), 1)
    except (OSError, ValueError, IndexError):
        return None


def read_memory() -> dict[str, int]:
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    result: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, raw = line.partition(":")
            if key in wanted:
                result[f"{key.lower()}_kb"] = int(raw.strip().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return result


def read_thermal() -> dict[str, Any]:
    zones = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            zones.append(
                {
                    "type": (zone / "type").read_text().strip(),
                    "celsius": round(int((zone / "temp").read_text().strip()) / 1000, 1),
                }
            )
        except (OSError, ValueError):
            continue
    return {
        "max_celsius": max((zone["celsius"] for zone in zones), default=None),
        "zones": zones,
    }


def read_display() -> dict[str, Any]:
    connector = Path("/sys/class/drm/card0-DP-1")
    gpu = Path("/sys/class/devfreq/5900000.gpu")
    result: dict[str, Any] = {"connector": "DP-1"}
    try:
        result["state"] = (connector / "status").read_text().strip()
        result["modes"] = (connector / "modes").read_text().split()
    except OSError:
        result["state"] = "unavailable"
    for name in ("cur_freq", "min_freq", "max_freq", "governor"):
        try:
            raw = (gpu / name).read_text().strip()
            result[f"gpu_{name}"] = int(raw) if raw.isdigit() else raw
        except OSError:
            continue
    return result


def read_api_status() -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=2) as response:
            status = json.load(response)
    except Exception as error:  # The recorder must survive an unavailable UI service.
        return {"available": False, "error": f"{type(error).__name__}: {error}"}
    hardware = status.get("hardware") or {}
    logging = status.get("logging") or {}
    return {
        "available": True,
        "connected": status.get("connected"),
        "receive_hz": status.get("receive_hz"),
        "bridge_errors": status.get("bridge_errors"),
        "mcu_resets": status.get("mcu_resets"),
        "logging_active": logging.get("active"),
        "logging_name": logging.get("name"),
        "logging_rows": logging.get("rows"),
        "sd_ready": hardware.get("sd_ready"),
        "sd_mounted": hardware.get("sd_mounted"),
        "sd_logging": hardware.get("sd_logging"),
        "sd_errors": hardware.get("sd_errors"),
        "sd_queue_dropped": hardware.get("sd_queue_dropped"),
    }


def service_state(name: str) -> dict[str, str]:
    try:
        output = subprocess.run(
            [
                "systemctl",
                "show",
                name,
                "--property=ActiveState,SubState,NRestarts,Result",
                "--no-pager",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def collect_snapshot(boot_id: str) -> dict[str, Any]:
    try:
        disk = shutil.disk_usage("/")
        disk_state = {"free_bytes": disk.free, "total_bytes": disk.total}
    except OSError:
        disk_state = {}
    return {
        "timestamp_utc": utc_now(),
        "boot_id": boot_id,
        "uptime_seconds": read_uptime_seconds(),
        "kernel": platform.release(),
        "memory": read_memory(),
        "root_disk": disk_state,
        "thermal": read_thermal(),
        "display": read_display(),
        "logger": read_api_status(),
        "services": {
            name: service_state(name)
            for name in (
                "arduino-router.service",
                "arduino-router-serial.service",
                "ecocapture-web-start.service",
                "racecapture-app.service",
            )
        },
    }


def bounded_journal(boot_id: str) -> bytes:
    try:
        completed = subprocess.run(
            [
                "journalctl",
                "--boot",
                boot_id,
                "--lines=400",
                "--output=short-iso-precise",
                "--no-pager",
            ],
            check=False,
            capture_output=True,
            timeout=15,
        )
        data = completed.stdout or completed.stderr
        return data[-MAX_JOURNAL_BYTES:]
    except (OSError, subprocess.SubprocessError) as error:
        return f"journal capture failed: {type(error).__name__}: {error}\n".encode()


def copy_pstore(destination: Path) -> list[str]:
    copied = []
    if not PSTORE_DIR.is_dir():
        return copied
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted(PSTORE_DIR.iterdir()):
        if not source.is_file():
            continue
        try:
            data = source.read_bytes()[:MAX_PSTORE_FILE_BYTES]
            (destination / source.name).write_bytes(data)
            copied.append(source.name)
        except OSError:
            continue
    if not copied:
        destination.rmdir()
    return copied


def prune_incidents() -> None:
    reports = sorted(INCIDENT_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime)
    for report in reports[:-MAX_INCIDENTS]:
        stem = report.stem
        for candidate in INCIDENT_DIR.glob(f"{stem}*"):
            if candidate.is_dir():
                shutil.rmtree(candidate, ignore_errors=True)
            else:
                candidate.unlink(missing_ok=True)


def record_unclean_reboot(previous: dict[str, Any], detected_at: str) -> Path:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    previous_boot_id = str(previous.get("boot_id", "unknown"))
    safe_timestamp = detected_at.replace(":", "").replace("+", "_")
    stem = f"{safe_timestamp}_{previous_boot_id[:12]}"
    journal_path = INCIDENT_DIR / f"{stem}.journal.log"
    journal_path.write_bytes(bounded_journal(previous_boot_id))
    report = {
        "classification": "unclean_reboot",
        "detected_at_utc": detected_at,
        "previous_boot": previous,
        "journal_file": journal_path.name,
        "pstore_files": copy_pstore(INCIDENT_DIR / f"{stem}.pstore"),
    }
    report_path = INCIDENT_DIR / f"{stem}.json"
    atomic_write_json(report_path, report)
    prune_incidents()
    return report_path


def monitor(interval: float) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    boot_id = read_boot_id()
    previous = read_json(CURRENT_STATE)
    previous_class = classify_previous(previous, boot_id)
    detected_at = utc_now()
    if previous_class == "unclean_reboot" and previous is not None:
        report = record_unclean_reboot(previous, detected_at)
        print(f"Recorded unclean reboot: {report}", flush=True)

    state: dict[str, Any] = {
        "schema": 1,
        "boot_id": boot_id,
        "started_at_utc": detected_at,
        "clean_shutdown": False,
        "previous_state": previous_class,
        "monitor_restarts_this_boot": (
            int(previous.get("monitor_restarts_this_boot", 0)) + 1
            if previous_class == "same_boot_restart" and previous
            else 0
        ),
    }
    stop = threading.Event()

    def handle_shutdown(signum: int, _frame: Any) -> None:
        state["clean_shutdown"] = True
        state["stopped_at_utc"] = utc_now()
        state["shutdown_signal"] = signal.Signals(signum).name
        atomic_write_json(CURRENT_STATE, state)
        stop.set()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    while not stop.is_set():
        try:
            state["last_snapshot"] = collect_snapshot(boot_id)
            state.pop("last_monitor_error", None)
        except Exception as error:  # Never let diagnostics destabilize logging.
            state["last_monitor_error"] = f"{type(error).__name__}: {error}"
        atomic_write_json(CURRENT_STATE, state)
        stop.wait(interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    monitor(args.interval)


if __name__ == "__main__":
    main()
