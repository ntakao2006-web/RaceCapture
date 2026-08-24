#!/bin/bash
# ROCK 5B dashcam launcher (2-screen edition, DC-9-8): two race_capture
# instances - a driving-display dash and a streaming dash, each with its own
# gauge layout - running as independent Zaphod screens (:0.0 / :0.1) of a
# single Xorg process, sharing the one ESP32 serial port via
# serial_fanout_bridge.py, plus recording of the streaming dash only.
#
# Why one Xorg + Zaphod instead of two plain Xorg/FB-mode processes: race_capture
# is Kivy (1 process = 1 window), so two independent instances need two
# separate rendering surfaces. Two DRM masters on the same GPU (two FB-mode
# processes, or two separate Xorg processes) collide with EBUSY / "Could not
# queue pageflip" - verified in practice on this hardware. A single Xorg
# process with ZaphodHeads splitting HDMI-1/HDMI-2 into independent screens
# avoids that: each screen has exactly one DRM master (Xorg itself).
# See task_dashcam_breakdown.md DC-9-1-b/DC-9-1-e for the verification history.
#
# Why a fan-out bridge instead of both instances opening the ESP32 port
# directly: pyserial's SerialConnection.open() takes no OS-level exclusive
# lock, so two instances reading/writing the same port corrupt each other's
# framing (SampleMetaException, SQLite IntegrityError - reproduced in
# practice, DC-9-1-c). The bridge is the single RCP client to the real port
# and fans the cached responses out to two virtual ports (pty), one per
# instance.
#
# Why XDG_CONFIG_HOME must differ per instance: race_capture's user_data_dir
# (prefs.json - including last_known_device and the gauge layout - and
# datastore.sq3) is keyed off XDG_CONFIG_HOME, not KIVY_HOME (DC-9-1-c). Each
# instance's prefs.json MUST live at "$XDG_CONFIG_HOME/racecapture/prefs.json"
# (a "racecapture" subdirectory under XDG_CONFIG_HOME, matching the default
# ~/.config/racecapture layout) - placing it directly under XDG_CONFIG_HOME
# silently falls back to defaults and last_known_device is lost (this was
# the DC-9-1-e blocker, root-caused via strace rather than being an actual
# quirk of the app's USB auto-detect logic).
#
# Why recording targets a specific DRM plane (-plane_id, see
# dashcam_record_rock5b.sh): with two screens active, kmsgrab's plane
# auto-select is no longer guaranteed to pick the streaming dash's screen.
# Plane 93 = HDMI-2 (streaming dash) on this hardware, confirmed via
# `sudo modetest -M rockchip -p` (plane 57 = HDMI-1 = driving-display dash).
# This mapping is a fixed DRM CRTC/plane wiring, not something the Xorg
# config changes, so it's hardcoded here rather than probed at runtime.
#
# Why race_capture is invoked directly instead of via the official
# run_racecapture_rpi.sh wrapper: that wrapper assumes a single instance on
# the default display; running it twice under different DISPLAY/
# XDG_CONFIG_HOME hasn't been verified and isn't needed - direct invocation
# with the same app arguments works (verified in practice, DC-9-1-e).
#
# race_capture itself (Kivy) does not reliably react to SIGTERM/SIGINT
# (observed in practice on the single-instance launcher this replaces: CPU
# usage stays pegged, process doesn't exit). The trap below escalates to
# SIGKILL after a grace period for both instances.
#
# Installed as /opt/racecapture/dashcam_launch_rock5b.sh and invoked from
# ~/.bashrc in place of the direct run_racecapture_rpi.sh call.

set -u

HOME_DIR="$HOME"
FFMPEG_BIN="$HOME_DIR/ffmpeg-rockchip/ffmpeg"
RECORD_SCRIPT=/opt/racecapture/dashcam_record_rock5b.sh
RECORD_LOG="$HOME_DIR/logs/dashcam_record.log"
BRIDGE_SCRIPT=/opt/racecapture/serial_fanout_bridge.py
BRIDGE_LOG="$HOME_DIR/logs/serial_fanout_bridge.log"
XORG_CONF=/opt/racecapture/xorg_zaphod_rock5b.conf
XORG_LOG="$HOME_DIR/logs/xorg_zaphod.log"
LAUNCH_LOG="$HOME_DIR/logs/dashcam_launch.log"
OUTDIR="$HOME_DIR/Videos/$(date +%Y%m%d_%H%M%S)"
VPORT_DISPLAY=/tmp/rc_vport_display
VPORT_STREAM=/tmp/rc_vport_stream
CFG_DISPLAY="$HOME_DIR/.config/racecapture_display"
CFG_STREAM="$HOME_DIR/.config/racecapture_stream"
STREAM_PLANE_ID=93
# --size must match each screen's actual resolution (HDMI-1=1280x800,
# HDMI-2=1920x1080, confirmed via `xrandr` on this hardware/Zaphod config).
# Without it, race_capture defaults to a small fixed window (observed:
# 1024x576) instead of filling the screen - Kivy's own fullscreen config
# keys (graphics:fullscreen auto/1) do NOT override this, only --size does.
DISPLAY_SIZE=1280x800
STREAM_SIZE=1920x1080
RC_APP_ARGS_COMMON=(-c graphics:show_cursor:0 -a -m cursor -c kivy:keyboard_mode:systemandmulti)

mkdir -p "$HOME_DIR/logs"

find_esp32_device() {
  local dev vid
  for dev in /dev/ttyACM*; do
    [ -e "$dev" ] || continue
    vid=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -m1 '^ID_VENDOR_ID=' | cut -d= -f2)
    # Espressif's USB VID (ESP32-C3's built-in USB-JTAG/serial descriptor).
    if [ "$vid" = "303a" ]; then
      echo "$dev"
      return 0
    fi
  done
  return 1
}

ESP32_DEVICE=$(find_esp32_device)
if [ -z "$ESP32_DEVICE" ]; then
  echo "$(date -Iseconds) dashcam_launch_rock5b: ESP32 device not found, aborting" >> "$LAUNCH_LOG"
  exit 1
fi

# 1. Xorg, single process, two independent Zaphod screens.
sudo Xorg :0 -config "$XORG_CONF" > "$XORG_LOG" 2>&1 &
XORG_PID=$!
for _ in $(seq 1 50); do
  [ -S /tmp/.X11-unix/X0 ] && break
  sleep 0.1
done

# 2. Fan-out bridge: sole RCP client to the real ESP32 port, fans cached
#    responses out to two virtual ports.
python3 "$BRIDGE_SCRIPT" --device "$ESP32_DEVICE" \
    --link "$VPORT_DISPLAY" --link "$VPORT_STREAM" >> "$BRIDGE_LOG" 2>&1 &
BRIDGE_PID=$!
for _ in $(seq 1 50); do
  [ -L "$VPORT_DISPLAY" ] && [ -L "$VPORT_STREAM" ] && break
  sleep 0.1
done

# 3. Driving-display dash (HDMI-1 / :0.0) and streaming dash (HDMI-2 / :0.1).
#    Each instance's last_known_device (set via its own prefs.json) points
#    at its own virtual port, not the real ESP32 device.
DISPLAY=:0.0 XDG_CONFIG_HOME="$CFG_DISPLAY" /opt/racecapture/race_capture \
    --size "$DISPLAY_SIZE" "${RC_APP_ARGS_COMMON[@]}" &
RC_DISPLAY_PID=$!

DISPLAY=:0.1 XDG_CONFIG_HOME="$CFG_STREAM" /opt/racecapture/race_capture \
    --size "$STREAM_SIZE" "${RC_APP_ARGS_COMMON[@]}" &
RC_STREAM_PID=$!

# 4. Recording: streaming dash's screen only.
sudo "$RECORD_SCRIPT" "$FFMPEG_BIN" "$OUTDIR" "$STREAM_PLANE_ID" >> "$RECORD_LOG" 2>&1 &
RECORD_PID=$!

shutdown_all() {
  kill -TERM "$RC_DISPLAY_PID" "$RC_STREAM_PID" 2>/dev/null
  sudo kill -TERM "$RECORD_PID" 2>/dev/null
  kill -TERM "$BRIDGE_PID" 2>/dev/null
  sudo kill -TERM "$XORG_PID" 2>/dev/null
  sleep 2
  kill -KILL "$RC_DISPLAY_PID" "$RC_STREAM_PID" 2>/dev/null
  kill -KILL "$BRIDGE_PID" 2>/dev/null
  sudo kill -KILL "$XORG_PID" 2>/dev/null
}

trap shutdown_all TERM INT

# Driving-display instance is the primary "this launcher is done" signal
# (it's the one the driver actually looks at). If it exits on its own
# (crash, etc.) tear the rest down the same way a TERM would.
wait "$RC_DISPLAY_PID" 2>/dev/null

shutdown_all
wait 2>/dev/null
