#!/bin/sh
set -eu
export DISPLAY=:2
export XDG_RUNTIME_DIR=/run/racecapture-app
mkdir -p "$HOME/.config/racecapture" "$HOME/.kivy"
export KIVY_NO_ARGS=1
export KIVY_NO_CONSOLELOG=0
export KIVY_GL_BACKEND=gl
export TMPDIR=/tmp
export SDL_AUDIODRIVER=dummy
# Prefer the attached 1280x800 touch display. If no display is connected,
# Xorg keeps the virtual framebuffer available for the existing noVNC path.
# Use the mode policy in hdmi_display.py (1080p60 first; 720p gives no picture
# through the USB-C dock) rather than --auto, which may pick 4K.
if /usr/bin/xrandr --query | /usr/bin/grep -q '^DP-1 connected'; then
    /usr/bin/python3 /opt/logger-v2-racecapture/hdmi_display.py >/dev/null 2>&1 ||
        /usr/bin/xrandr --output DP-1 --auto --primary
fi
cd /opt/racecapture
exec dbus-run-session ./race_capture --conn_type wifi -p 127.0.0.1
