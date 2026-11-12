#!/bin/sh
# Records the driver's microphone for a few seconds and writes each processing step as WAV
# (mic_check.py). The voice agent holds the microphone, so it is stopped meanwhile (as root
# through Docker, like install-voice-agent.sh) and started again afterwards. Plays nothing.
#   sh mic_check.sh [seconds] [card]      → ~/audio_check/mic_check_<time>/
set -eu
SECS=${1:-10}
CARD=${2:-$(curl -s 127.0.0.1:8080/api/podium | python3 -c 'import json,sys;print((json.load(sys.stdin)["status"].get("voice_agent") or {}).get("card") or "")')}
[ -n "$CARD" ] || { echo "USBのマイクが見つかりません" >&2; exit 1; }
CH=$(sed -n '/^Capture:/,$ s/^ *Channels: *//p' /proc/asound/$CARD/stream0 2>/dev/null | head -1)
CH=${CH:-1}
OUT=$HOME/audio_check/mic_check_$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUT"
SYSTEMCTL="docker run --rm --pid=host --user 0:0 -v /:/host --entrypoint /usr/sbin/chroot ghcr.io/arduino/app-bricks/python-apps-base:0.5.0 /host systemctl"
$SYSTEMCTL stop ecocapture-voice
trap '$SYSTEMCTL start ecocapture-voice' EXIT
echo "録音中 ${SECS}秒（$CARD, ${CH}ch）…話してください"
arecord -q -D "plughw:CARD=$CARD,DEV=0" -f S16_LE -r 48000 -c "$CH" -d "$SECS" -t raw "$OUT/mic.raw"
python3 "$(dirname "$0")/mic_check.py" "$OUT/mic.raw" "$CH" "$OUT"
echo "$OUT"
