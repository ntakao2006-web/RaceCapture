#!/usr/bin/python3
"""Configure the UNO Q HDMI/DP connector to a bounded, dashboard-friendly mode."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


CONNECTOR = os.environ.get("LOGGER_V2_DRM_CONNECTOR", "DP-1")
STATUS_PATH = Path(f"/sys/class/drm/card0-{CONNECTOR}/status")
PREFERRED_MODES = ("1280x800", "1280x720", "1024x768", "800x600")
MAX_WIDTH = 1280
MAX_HEIGHT = 800


def parse_modes(output: str, connector: str = CONNECTOR) -> list[str]:
    inside = False
    modes: list[str] = []
    for line in output.splitlines():
        if line and not line[0].isspace():
            inside = line.startswith(f"{connector} connected")
            continue
        if not inside:
            continue
        match = re.match(r"\s+(\d+x\d+)\s", line)
        if match and match.group(1) not in modes:
            modes.append(match.group(1))
    return modes


def choose_mode(modes: list[str]) -> str | None:
    for preferred in PREFERRED_MODES:
        if preferred in modes:
            return preferred
    parsed = []
    for mode in modes:
        try:
            width, height = (int(value) for value in mode.split("x", 1))
        except ValueError:
            continue
        parsed.append((width, height, mode))
    bounded = [item for item in parsed if item[0] <= MAX_WIDTH and item[1] <= MAX_HEIGHT]
    if bounded:
        return max(bounded, key=lambda item: (item[0] * item[1], item[0]))[2]
    if parsed:
        return min(parsed, key=lambda item: (item[0] * item[1], item[0]))[2]
    return None


def configure() -> dict[str, object]:
    state = STATUS_PATH.read_text().strip() if STATUS_PATH.is_file() else "missing"
    result: dict[str, object] = {"connector": CONNECTOR, "state": state, "configured": False}
    if state != "connected":
        return result
    query = subprocess.run(
        ["/usr/bin/xrandr", "--query"], capture_output=True, text=True, check=False
    )
    modes = parse_modes(query.stdout)
    mode = choose_mode(modes)
    command = ["/usr/bin/xrandr", "--output", CONNECTOR]
    if mode:
        command += ["--mode", mode, "--rate", "60", "--primary"]
        applied = subprocess.run(command, capture_output=True, text=True, check=False)
        if applied.returncode:
            command = ["/usr/bin/xrandr", "--output", CONNECTOR, "--mode", mode, "--primary"]
            applied = subprocess.run(command, capture_output=True, text=True, check=False)
    else:
        command += ["--auto", "--primary"]
        applied = subprocess.run(command, capture_output=True, text=True, check=False)
    result.update(
        configured=applied.returncode == 0,
        selected_mode=mode or "auto",
        available_modes=modes,
        error=applied.stderr.strip() or None,
    )
    return result


if __name__ == "__main__":
    print(json.dumps(configure(), ensure_ascii=False, sort_keys=True))
