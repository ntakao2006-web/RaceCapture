#!/bin/sh
# 走行映像の焼き込み録画（ecologger-video.service から起動する）。USBカメラが見えるまで5秒ごとに待つ
#   保存先：~/ecocapture-v2-data/video/YYYYMMDD_HHMMSS.ts（OVERLAY_SEGMENT_MIN分ごとに分割）と、同じ名前の .csv（1秒ごとの時刻）
#   カメラはUSBのものだけが /dev/v4l/by-id/ に出る（エンコーダ等の /dev/video0・1 は出ない）ので、そこから最初の1台を使う
dir=/home/arduino/ecocapture-v2-data/video
bin=/opt/ecologger-video
mkdir -p "$dir"
# 計器の設定：自分の配置（PCの Apply-HUD.cmd が置く）があればそれ、無ければ元の配置（install-video.sh が置く）。
# 録画中も約1秒ごとに見て、書き換わっていれば次のコマから変わる。読んだ結果は hud_status.txt（手順書5-14）
hud=/home/arduino/ecologger-video
mkdir -p "$hud"
export OVERLAY_HUD="$hud/hud.ini" OVERLAY_HUD_DEFAULT="$bin/hud_default.ini" OVERLAY_HUD_STATUS="$hud/hud_status.txt"
# ベストの周の軌跡（ベストとの差・コース図。録画をやり直しても lap.BestLap と同じ時間なら続きから使う。手順書5-16）
export OVERLAY_LAPREF="$hud/lap_ref.txt"
# レンズの歪みの補正＋ズーム（PCの tools/lens_view/ で決めて Apply-Lens.cmd が置く）。無ければ補正しない。録画中も約1秒ごとに見る
export OVERLAY_LENS="$hud/lens.json"
# 音：カメラと同じUSB機器のマイク（ELPは内蔵）を探して録る（MP2・128kbps、手順書5-20）。録れなくても映像は録る。
# 止めたいときは $hud/audio_off を置く。別のマイクにしたいときは $hud/audio にALSAの名前（例 plughw:CARD=Pro,DEV=0）を書く
cam_mic() {  # $1：カメラの /dev/v4l/by-id/… 。同じUSB機器（インターフェースの親）にある音の入力のALSAの名前
    v=$(readlink -f "$1"); up=$(readlink -f "/sys/class/video4linux/${v##*/}/device/..")
    for c in /sys/class/sound/card*; do
        [ -e "$c/device" ] && [ "$(readlink -f "$c/device/..")" = "$up" ] && [ -e "/dev/snd/pcmC${c##*card}D0c" ] && { echo "plughw:CARD=$(cat "$c/id"),DEV=0"; return; }
    done
}
while :; do
    for d in /dev/v4l/by-id/*-video-index0; do
        [ -e "$d" ] || continue
        if [ -e "$hud/audio_off" ]; then OVERLAY_AUDIO=off
        elif [ -s "$hud/audio" ]; then OVERLAY_AUDIO=$(head -n 1 "$hud/audio" | tr -d '\r')
        else OVERLAY_AUDIO=$(cam_mic "$d"); fi
        export OVERLAY_AUDIO
        echo "audio: ${OVERLAY_AUDIO:-none (no microphone on the camera)}"
        exec "$bin/overlay_rec" "$d" "$dir/%Y%m%d_%H%M%S.ts" 0 "$bin/hud_font_64.pgm"
    done
    sleep 5
done
