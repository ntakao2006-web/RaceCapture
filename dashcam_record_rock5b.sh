#!/bin/bash
# ROCK 5B dashcam recording process (RKMPP hardware encode via ffmpeg-rockchip)
#
# kmsgrab requires root (CAP_SYS_ADMIN) to read DRM framebuffer handles,
# so this script is invoked via `sudo` by dashcam_launch_rock5b.sh.
#
# Wraps ffmpeg in a watchdog loop: kmsgrab can throw a transient
# "Input/output error" when the DRM plane's framebuffer handle changes
# (observed in practice during the console(XR24)->Kivy window(AR24) handoff
# right after race_capture starts), which kills the ffmpeg process outright.
# Auto-restarting keeps recording going instead of silently stopping forever.
#
# Segments are 30 seconds rather than a minute because the recording target is
# an exFAT SD card, chosen so the card can be pulled and read directly on a PC.
# exFAT has no journal, and this system is powered down by cutting power - that
# is the intended way to end a session, not a fault - so every shutdown lands
# mid-write. A shorter segment halves how much footage is exposed to that, and
# closing a segment is also when the directory entry for the finished file gets
# written out.
#
# Uses fragmented mp4 (movflags=+frag_keyframe+empty_moov+default_base_moof)
# instead of a plain moov-at-end mp4: a plain mp4 only writes its moov atom
# on clean shutdown, so a hard kill (SIGKILL, power loss) leaves the current
# segment permanently unplayable ("moov atom not found"). Verified in
# practice that a killed fragmented-mp4 segment still probes/plays fine.
# Passed via -segment_format_options rather than a top-level -movflags:
# with -f segment, a top-level -movflags is not reliably propagated to the
# per-segment mp4 sub-muxer (verified: top-level flag produced a segment
# that failed with "moov atom not found" even on a clean SIGTERM exit).
#
# Usage: dashcam_record_rock5b.sh <ffmpeg_binary> <output_dir> [plane_id]
#
# plane_id (optional): restricts kmsgrab to a single DRM plane instead of
# whatever plane happens to be active. Needed once two race_capture
# instances share the GPU (DC-9-8, Zaphod dual-screen setup): without it
# kmsgrab can grab whichever screen currently owns the primary plane it
# defaults to, which may not be the streaming dash. Omit to keep the old
# single-screen auto-select behavior.

set -u

FFMPEG_BIN="$1"
OUTDIR="$2"
PLANE_ID="${3:-}"
mkdir -p "$OUTDIR"

# Retention floor, in MB of free rootfs. Nothing used to delete old footage, so
# a continuous 4 Mbps recording (~1.8 GB/hour) eventually filled the 14 GB eMMC,
# which broke race_capture itself rather than just recording: its datastore
# failed to initialise with "database or disk is full" and prefs.json could no
# longer be saved. Recording is the expendable data here, so it yields first.
MIN_FREE_MB="${MIN_FREE_MB:-2000}"
VIDEO_ROOT=$(dirname "$OUTDIR")

STOP=0
FFMPEG_PID=""
PRUNE_PID=""
trap 'STOP=1; [ -n "$FFMPEG_PID" ] && kill -TERM "$FFMPEG_PID" 2>/dev/null; [ -n "$PRUNE_PID" ] && kill -TERM "$PRUNE_PID" 2>/dev/null' TERM INT

free_mb() { df -Pm "$OUTDIR" | awk 'NR==2 {print $4}'; }

# Delete oldest-first across all session directories (timestamped names sort
# chronologically, and segments are zero-padded, so a plain sort of the paths is
# already oldest-first). `head -n -1` holds back the newest segment, which is
# the one ffmpeg is currently writing.
prune_to_free_space() {
  local oldest
  while [ "$(free_mb)" -lt "$MIN_FREE_MB" ]; do
    oldest=$(ls -1 "$VIDEO_ROOT"/*/video_*.mp4 2>/dev/null | sort | head -n -1 | head -1)
    [ -n "$oldest" ] || break
    echo "dashcam_record_rock5b: low disk ($(free_mb) MB), removing $oldest"
    rm -f "$oldest"
  done
  find "$VIDEO_ROOT" -mindepth 1 -maxdepth 1 -type d -empty -not -path "$OUTDIR" \
    -exec rmdir {} + 2>/dev/null
}

prune_to_free_space
( while true; do sleep 30; prune_to_free_space; done ) &
PRUNE_PID=$!

PLANE_ARGS=()
[ -n "$PLANE_ID" ] && PLANE_ARGS=(-plane_id "$PLANE_ID")

# Each ffmpeg invocation restarts -f segment's counter at 0000, so a restart
# used to reopen video_0000.mp4 and overwrite everything recorded so far in this
# session. kmsgrab does fail and restart in normal operation (the console->Kivy
# framebuffer handoff alone triggers it once at every launch), so the run index
# keeps each attempt's segments in their own, still chronologically sortable,
# filename space.
RUN=0

while [ "$STOP" -eq 0 ]; do
  RUN=$((RUN + 1))
  SEGMENT_PATTERN=$(printf '%s/video_%02d_%%04d.mp4' "$OUTDIR" "$RUN")
  # -nostats: the per-frame progress line is what grew this log to 35 MB on a
  # disk that was already full. Warnings and errors still come through.
  #
  # 30 fps, not the telemetry's 10 Hz: the dash carries a live camera image, and
  # the recording is a video deliverable in its own right, so it is paced for
  # motion rather than for the gauge update rate.
  #
  # 6 Mbps rather than 4: at 15 fps the encoder was already sitting on the 4 Mbps
  # ceiling (measured 3.5-4.0 Mbps on real segments), so keeping it there while
  # doubling the frame rate would have spent the same bits on twice the frames.
  # 30 fps needs roughly 1.5x, not 2x, because consecutive frames are more alike.
  # Costs about 2.7 GB/hour; the retention loop above is what keeps that bounded.
  "$FFMPEG_BIN" -hide_banner -nostats -f kmsgrab -device /dev/dri/card0 "${PLANE_ARGS[@]}" -framerate 30 -i - \
    -c:v h264_rkmpp -b:v 6M \
    -f segment -segment_time 30 -reset_timestamps 1 -strftime 0 \
    -segment_format mp4 -segment_format_options movflags=+frag_keyframe+empty_moov+default_base_moof \
    "$SEGMENT_PATTERN" &
  FFMPEG_PID=$!
  wait "$FFMPEG_PID"
  FFMPEG_PID=""
  if [ "$STOP" -eq 0 ]; then
    echo "dashcam_record_rock5b: ffmpeg exited, restarting in 2s..."
    sleep 2
  fi
done

kill -TERM "$PRUNE_PID" 2>/dev/null
