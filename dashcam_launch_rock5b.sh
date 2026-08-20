#!/bin/bash
# ROCK 5B dashcam launcher: race_capture(watchdog) + screen recording, as a pair.
#
# Wraps the official /opt/racecapture/run_racecapture_rpi.sh (left unmodified,
# so a future RaceCapture App reinstall won't clobber our changes) and starts/stops
# the dashcam_record_rock5b.sh recording process alongside it.
#
# Installed as /opt/racecapture/dashcam_launch_rock5b.sh and invoked from ~/.bashrc
# in place of the direct run_racecapture_rpi.sh call.
#
# Both children are started in the background and joined with `wait`, not run
# in the foreground directly: bash delays signal delivery to itself until a
# foreground child exits, so a plain foreground call would leave race_capture
# (and the recorder) orphaned and still running when this script is TERM'd
# (observed in practice). `wait` is interruptible, so the trap below fires
# immediately and can forward the signal explicitly.
#
# race_capture itself (Kivy, FBmode/DRM-KMS direct rendering) does not react
# to SIGTERM or SIGINT (verified in practice: CPU usage stays pegged, process
# never exits). The trap below escalates to SIGKILL after a short grace
# period so stopping this launcher is still reliable.

FFMPEG_BIN="$HOME/ffmpeg-rockchip/ffmpeg"
RECORD_SCRIPT=/opt/racecapture/dashcam_record_rock5b.sh
RECORD_LOG="$HOME/logs/dashcam_record.log"
OUTDIR="$HOME/Videos/$(date +%Y%m%d_%H%M%S)"

mkdir -p "$HOME/logs"

sudo "$RECORD_SCRIPT" "$FFMPEG_BIN" "$OUTDIR" >> "$RECORD_LOG" 2>&1 &
RECORD_PID=$!

/opt/racecapture/run_racecapture_rpi.sh -w 1 -- -c graphics:show_cursor:0 -a -m cursor -c kivy:keyboard_mode:systemandmulti &
RC_PID=$!

trap '
  APP_PID=$(pgrep -P "$RC_PID")
  [ -n "$APP_PID" ] && kill -TERM $APP_PID 2>/dev/null
  kill -TERM "$RC_PID" 2>/dev/null
  sudo kill -TERM "$RECORD_PID" 2>/dev/null
  sleep 2
  [ -n "$APP_PID" ] && kill -KILL $APP_PID 2>/dev/null
  kill -KILL "$RC_PID" 2>/dev/null
' TERM INT

wait "$RC_PID" 2>/dev/null

sudo kill -TERM "$RECORD_PID" 2>/dev/null
wait "$RECORD_PID" 2>/dev/null
