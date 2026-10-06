#!/usr/bin/python3
"""Change only the RaceCapture frame-rate limit for the HDMI profile."""

import configparser
import os
from pathlib import Path


CONFIG = Path.home() / ".kivy" / "config.ini"


def apply(maxfps: int = 20) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(CONFIG)
    if not parser.has_section("graphics"):
        parser.add_section("graphics")
    parser.set("graphics", "maxfps", str(maxfps))
    temporary = CONFIG.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        parser.write(stream, space_around_delimiters=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, CONFIG)


if __name__ == "__main__":
    apply()
