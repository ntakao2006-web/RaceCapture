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

STOP=0
FFMPEG_PID=""
trap 'STOP=1; [ -n "$FFMPEG_PID" ] && kill -TERM "$FFMPEG_PID" 2>/dev/null' TERM INT

PLANE_ARGS=()
[ -n "$PLANE_ID" ] && PLANE_ARGS=(-plane_id "$PLANE_ID")

while [ "$STOP" -eq 0 ]; do
  "$FFMPEG_BIN" -hide_banner -f kmsgrab -device /dev/dri/card0 "${PLANE_ARGS[@]}" -framerate 15 -i - \
    -c:v h264_rkmpp -b:v 4M \
    -f segment -segment_time 60 -reset_timestamps 1 -strftime 0 \
    -segment_format mp4 -segment_format_options movflags=+frag_keyframe+empty_moov+default_base_moof \
    "$OUTDIR/video_%04d.mp4" &
  FFMPEG_PID=$!
  wait "$FFMPEG_PID"
  FFMPEG_PID=""
  if [ "$STOP" -eq 0 ]; then
    echo "dashcam_record_rock5b: ffmpeg exited, restarting in 2s..."
    sleep 2
  fi
done
