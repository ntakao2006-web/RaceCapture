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
# The recorder captures one DRM plane, and it must be the streaming dash's.
# This used to be hardcoded to 93 from a one-off `modetest` reading, on the
# assumption that the CRTC/plane wiring is fixed. It is fixed for a given set of
# connected outputs - but not across changes to that set, and an HDMI cable is
# something that gets unplugged. A stale id costs more than a wrong resolution:
# kmsgrab dies with "Plane N no longer has an associated framebuffer", or worse,
# silently records the other screen. Derive it from the connector instead, and
# keep the old value only as a last-resort fallback.
STREAM_CONNECTOR=HDMI-A-2
STREAM_PLANE_ID_FALLBACK=93
# --size must match each screen's actual resolution: without it race_capture
# defaults to a small fixed window (observed: 1024x576) instead of filling the
# screen, and Kivy's own fullscreen config keys (graphics:fullscreen auto/1) do
# NOT override this - only --size does. The sizes are probed from the running
# Xorg rather than hardcoded, because they depend on whichever monitor is
# plugged in: a hardcoded 1280x800 against a 1920x1080 panel leaves the dash as
# a small window surrounded by the bare X root window (and its X-shaped
# cursor), which is exactly what a monitor swap produced in practice.
DISPLAY_SIZE_FALLBACK=1920x1080
STREAM_SIZE_FALLBACK=1920x1080
# Keep this much room on the rootfs. A 4 Mbps recording eats ~1.8 GB/hour and
# nothing used to delete anything, so the 14 GB eMMC filled up - and a full disk
# breaks far more than recording: race_capture's datastore then fails to
# initialise ("database or disk is full") and prefs.json can no longer be saved.
MIN_FREE_MB=3000
# datastore.sq3 grows without bound as sessions are recorded (1.4 GB per
# instance observed). Rotate it rather than let it consume the disk.
MAX_DATASTORE_MB=512
# maxfps/multisamples are passed here rather than left in ~/.kivy/config.ini so
# they live with the rest of the launch configuration instead of only on the
# eMMC, where reimaging would silently lose them.
#
# maxfps 30 (Kivy's default is 60): the recording is 30 fps, so rendering faster
# buys nothing downstream. Measured on this hardware by counting DRM page flips
# on the streaming screen's plane: 38.2 fps at maxfps=30 vs 45.0 fps at
# maxfps=60 - both comfortably above the 30 fps the recorder samples at, so the
# extra frames were pure waste.
#
# multisamples 0 (Kivy's default is 2): this is where most of the GPU saving
# came from. With 60 fps + 2x MSAA the Mali sat pinned at its 1000 MHz ceiling
# (load 42-80%); with 30 fps and MSAA off the governor drops it to 300-400 MHz
# (load 15-44%). Antialiasing is a poor trade here - it costs the most GPU of
# anything on the dash and is barely visible on gauge text at 1080p.
RC_APP_ARGS_COMMON=(-c graphics:show_cursor:0 -a -m cursor -c kivy:keyboard_mode:systemandmulti
                    -c graphics:maxfps:30 -c graphics:multisamples:0)

mkdir -p "$HOME_DIR/logs"

free_mb() { df -Pm "$HOME_DIR" | awk 'NR==2 {print $4}'; }

# DRM connector name (as modetest prints it) -> the plane currently driving it,
# via connector -> encoder -> CRTC -> plane. Prints nothing if the connector has
# no encoder/CRTC attached (i.e. nothing is plugged into it).
find_plane_for_connector() {
  local conn="$1" enc crtc
  enc=$(sudo modetest -M rockchip -c 2>/dev/null \
        | awk -v c="$conn" '$3 ~ /^(connected|disconnected)$/ && $4 == c {print $2; exit}')
  [ -n "$enc" ] && [ "$enc" != "0" ] || return 1
  crtc=$(sudo modetest -M rockchip -e 2>/dev/null | awk -v e="$enc" '$1 == e {print $2; exit}')
  [ -n "$crtc" ] && [ "$crtc" != "0" ] || return 1
  sudo modetest -M rockchip -p 2>/dev/null \
    | awk -v c="$crtc" '/^Planes:/{p=1;next} p && /^[0-9]+\t/ && $2 == c {print $1; exit}'
}

probe_screen_size() {
  # $1 = Zaphod X screen number. Prints that screen's current mode as WxH.
  local screen="$1"
  DISPLAY=":0.$screen" xrandr 2>/dev/null \
    | sed -n "s/^Screen $screen: .*current \([0-9]\+\) x \([0-9]\+\),.*/\1x\2/p" \
    | head -1
}

# race_capture writes whichever port it actually connected to back into
# prefs.json. If an instance ever falls through to the real ESP32 port (e.g.
# the bridge was slow to create its pty), that real port becomes its
# last_known_device from then on, so it bypasses the fan-out bridge on every
# subsequent boot and fights the bridge over the same port - producing
# SerialTimeoutException and an endless reconnect loop (observed in practice on
# the streaming instance, which had pinned itself to /dev/ttyACM0). The setting
# poisons itself, so re-pin it on every launch.
pin_last_known_device() {
  local prefs="$1/racecapture/prefs.json" vport="$2"
  mkdir -p "$(dirname "$prefs")"
  python3 - "$prefs" "$vport" <<'PY'
import json, os, sys
path, vport = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        prefs = json.load(f)
except (OSError, ValueError):
    prefs = {}
prefs.setdefault("general_prefs", {}).setdefault("preferences", {})["last_known_device"] = vport
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(prefs, f)
os.replace(tmp, path)
PY
}

prune_datastores() {
  local cfg db
  for cfg in "$CFG_DISPLAY" "$CFG_STREAM"; do
    db="$cfg/racecapture/datastore.sq3"
    [ -f "$db" ] || continue
    if [ "$(du -m "$db" | cut -f1)" -gt "$MAX_DATASTORE_MB" ]; then
      echo "$(date -Iseconds) dashcam_launch_rock5b: rotating oversized $db" >> "$LAUNCH_LOG"
      rm -f "$db" "$db-journal"
    fi
  done
}

prune_old_recordings() {
  local dir
  while [ "$(free_mb)" -lt "$MIN_FREE_MB" ]; do
    # Timestamped directory names sort chronologically, so the first is oldest.
    dir=$(ls -1d "$HOME_DIR"/Videos/*/ 2>/dev/null | sort | head -1)
    [ -n "$dir" ] || break
    echo "$(date -Iseconds) dashcam_launch_rock5b: low disk, removing $dir" >> "$LAUNCH_LOG"
    sudo rm -rf "$dir"
  done
}

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

# 0. Make room before anything starts. Both instances need to be able to write
#    their datastore and prefs, and the recorder needs somewhere to put footage.
prune_datastores
prune_old_recordings
echo "$(date -Iseconds) dashcam_launch_rock5b: $(free_mb) MB free before start" >> "$LAUNCH_LOG"

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
#    Each instance's last_known_device points at its own virtual port, not the
#    real ESP32 device - re-pinned here so a previous run cannot have left it
#    pointing at the real port.
pin_last_known_device "$CFG_DISPLAY" "$VPORT_DISPLAY"
pin_last_known_device "$CFG_STREAM" "$VPORT_STREAM"

DISPLAY_SIZE=$(probe_screen_size 0); DISPLAY_SIZE=${DISPLAY_SIZE:-$DISPLAY_SIZE_FALLBACK}
STREAM_SIZE=$(probe_screen_size 1); STREAM_SIZE=${STREAM_SIZE:-$STREAM_SIZE_FALLBACK}
echo "$(date -Iseconds) dashcam_launch_rock5b: screens :0.0=$DISPLAY_SIZE :0.1=$STREAM_SIZE" >> "$LAUNCH_LOG"

DISPLAY=:0.0 XDG_CONFIG_HOME="$CFG_DISPLAY" /opt/racecapture/race_capture \
    --size "$DISPLAY_SIZE" "${RC_APP_ARGS_COMMON[@]}" &
RC_DISPLAY_PID=$!

DISPLAY=:0.1 XDG_CONFIG_HOME="$CFG_STREAM" /opt/racecapture/race_capture \
    --size "$STREAM_SIZE" "${RC_APP_ARGS_COMMON[@]}" &
RC_STREAM_PID=$!

# 4. Recording: streaming dash's screen only.
STREAM_PLANE_ID=$(find_plane_for_connector "$STREAM_CONNECTOR")
STREAM_PLANE_ID=${STREAM_PLANE_ID:-$STREAM_PLANE_ID_FALLBACK}
echo "$(date -Iseconds) dashcam_launch_rock5b: recording $STREAM_CONNECTOR via plane $STREAM_PLANE_ID" >> "$LAUNCH_LOG"
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
