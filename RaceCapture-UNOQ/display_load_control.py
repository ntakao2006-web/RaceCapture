"""Pause only the covered display application; logging services remain untouched."""

from __future__ import annotations

import os
import signal
from pathlib import Path


CGROUP_ROOT = Path("/sys/fs/cgroup/system.slice")
DISPLAY_SERVICES = frozenset({"racecapture-app", "ecocapture-native"})


def service_pids(service: str) -> list[int]:
    if service not in DISPLAY_SERVICES:
        raise ValueError(f"unsupported display service: {service}")
    path = CGROUP_ROOT / f"{service}.service" / "cgroup.procs"
    try:
        return [int(value) for value in path.read_text().split() if int(value) > 1]
    except (OSError, ValueError):
        return []


def set_paused(service: str, paused: bool) -> int:
    selected_signal = signal.SIGSTOP if paused else signal.SIGCONT
    changed = 0
    for pid in service_pids(service):
        try:
            os.kill(pid, selected_signal)
            changed += 1
        except (ProcessLookupError, PermissionError):
            continue
    return changed


def resume_all() -> None:
    for service in DISPLAY_SERVICES:
        set_paused(service, False)
