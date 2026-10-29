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
# Use the bounded mode from hdmi_display.py: --auto would pick a monitor's
# preferred 1080p (e.g. the 7-inch HD7H) and undo the 1280x720 choice.
if /usr/bin/xrandr --query | /usr/bin/grep -q '^DP-1 connected'; then
    /usr/bin/python3 /opt/logger-v2-racecapture/hdmi_display.py >/dev/null 2>&1 ||
        /usr/bin/xrandr --output DP-1 --auto --primary
fi
cd /opt/racecapture
exec dbus-run-session ./race_capture --conn_type wifi -p 127.0.0.1
