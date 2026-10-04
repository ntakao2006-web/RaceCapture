#!/usr/bin/python3
"""Resize the RaceCapture X11 window to the current display framebuffer."""
import ctypes
import os
import re
import subprocess
import time

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XMoveResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
x11.XMapRaised.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]

display_name = os.environ.get("DISPLAY", ":2")
top = int(os.environ.get("RACECAPTURE_TOP", "64"))
display = x11.XOpenDisplay(display_name.encode())
if not display:
    raise SystemExit("cannot open X display")

for _ in range(20):
    tree = subprocess.run(
        ["/usr/bin/xwininfo", "-display", display_name, "-root", "-tree"],
        text=True, capture_output=True, check=False,
    ).stdout
    match = re.search(r'^\s*(0x[0-9a-f]+).*\("race_capture" "race_capture"\)', tree, re.MULTILINE)
    if match:
        window = int(match.group(1), 16)
        screen = x11.XDefaultScreen(display)
        width = x11.XDisplayWidth(display, screen)
        height = x11.XDisplayHeight(display, screen)
        x11.XMoveResizeWindow(display, window, 0, top, width, height - top)
        x11.XMapRaised(display, window)
        x11.XFlush(display)
        print(f"RaceCapture resized to {width}x{height - top}+0+{top}")
        raise SystemExit(0)
    time.sleep(1)
raise SystemExit("RaceCapture window not found")
