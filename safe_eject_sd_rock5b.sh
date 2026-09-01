#!/bin/bash
# Stop recording and unmount the SD card so it can be pulled without corrupting
# it, while leaving the dashes on screen.
#
# Why this exists: the card is exFAT and has no journal, and the recorder writes
# to it continuously (~1.3 MB/s measured). Pulling it live costs the segment
# being written and can leave the filesystem dirty enough that Windows wants to
# repair it before the card can be read. Powering the machine down first is the
# normal way to take the card out - this script is for the case where the dash
# needs to stay up.
#
# Recording does NOT resume when the card goes back in: the launcher decides
# once, at startup, whether to record (see dashcam_launch_rock5b.sh). Put the
# card back and power-cycle to start recording again. That matches how the rest
# of the system treats a power cycle as the session boundary.
#
# Installed as /opt/racecapture/safe_eject_sd_rock5b.sh. Run it over SSH:
#   ssh ntakao@192.168.137.50 sudo /opt/racecapture/safe_eject_sd_rock5b.sh

set -u

MOUNT_POINT=/media/recordings
RECORD_MATCH=dashcam_record_rock5b
GRACE_SECONDS=10

say() { echo "$*"; }

if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
  say "SDカードはマウントされていません。そのまま抜いて構いません。"
  exit 0
fi

# 1. Stop the recorder first, and by SIGTERM rather than SIGKILL: the record
#    script traps TERM and passes it to ffmpeg, which finalises the segment it
#    is writing. Killing ffmpeg outright would leave that segment truncated -
#    still playable thanks to fragmented mp4, but needlessly damaged.
# Signal exactly one process, and let it cascade. ffmpeg must receive SIGTERM
# once and only once: the second signal makes it exit immediately instead of
# finishing the fragment it is writing, which truncates that segment ("partial
# file" on probe). The record script already traps TERM and forwards it to
# ffmpeg, so signalling the wrapper is enough - and signalling every matching
# pid (sudo, the script, its pruner subshell) is what produced the duplicate,
# because sudo forwards the signal to the script as well as the script getting
# it directly, running the trap twice.
record_pid=$(pgrep -f "$RECORD_MATCH" 2>/dev/null | head -1 || true)
if [ -n "$record_pid" ]; then
  say "録画を停止しています..."
  kill -TERM "$record_pid" 2>/dev/null
fi

# Wait for ffmpeg itself, not just the wrapper: closing the file is what takes
# the time, and only ffmpeg's exit tells us it finished.
if pgrep -x ffmpeg > /dev/null; then
  say "  ffmpegが書き込み中のセグメントを閉じるのを待っています..."
  for _ in $(seq 1 $((GRACE_SECONDS * 2))); do
    pgrep -x ffmpeg > /dev/null || break
    sleep 0.5
  done
fi

if pgrep -x ffmpeg > /dev/null; then
  say "  ffmpegが${GRACE_SECONDS}秒で終了しませんでした。強制終了します"
  say "  （書き込み中だったセグメントは途中で切れますが、再生は可能です）"
  pkill -KILL -x ffmpeg 2>/dev/null
  sleep 1
fi
pkill -KILL -f "$RECORD_MATCH" 2>/dev/null

# 2. Flush everything the kernel is still holding for that filesystem.
say "書き込みを同期しています..."
sync

# 3. Unmount. Anything still holding the mount point is reported rather than
#    forced, so a stuck process can be identified instead of silently losing
#    its writes to a lazy unmount.
for attempt in 1 2 3; do
  if umount "$MOUNT_POINT" 2>/dev/null; then
    say ""
    say "完了。SDカードを抜いて構いません。"
    say "（録画を再開するには、カードを戻してから電源を入れ直してください）"
    exit 0
  fi
  sleep 1
done

say ""
say "アンマウントできませんでした。まだ何かが使用中です:"
fuser -vm "$MOUNT_POINT" 2>&1 | sed 's/^/  /'
say ""
say "この状態では抜かないでください。電源を切ってから抜くのが安全です。"
exit 1
