#!/bin/sh
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$HERE/EcoCapture.arm64"

if [ "$(uname -m)" != "aarch64" ]; then
    echo "EcoCapture: Raspberry Pi OS 64-bit (aarch64) is required." >&2
    exit 2
fi
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; then
    echo "EcoCapture: start this from Raspberry Pi OS Desktop (Wayland or X11)." >&2
    exit 3
fi
if [ ! -f "$APP" ]; then
    echo "EcoCapture: EcoCapture.arm64 is missing beside this launcher." >&2
    exit 4
fi
if [ ! -x "$APP" ]; then
    chmod u+x "$APP" || {
        echo "EcoCapture: copy the folder to a writable location, then retry." >&2
        exit 5
    }
fi

for dev in /dev/ttyACM*; do
    [ -e "$dev" ] || continue
    if [ ! -r "$dev" ] || [ ! -w "$dev" ]; then
        echo "EcoCapture: $dev is not accessible. See RPI4_SETUP.md." >&2
    fi
done

# Pi 4 Mesa exposes native OpenGL ES 3.0. Godot Compatibility is the low-end
# renderer and avoids making Vulkan a requirement. Override only for diagnosis.
DRIVER=${ECOCAPTURE_RENDERING_DRIVER:-opengl3_es}
exec "$APP" --rendering-method gl_compatibility --rendering-driver "$DRIVER" -- "$@"
