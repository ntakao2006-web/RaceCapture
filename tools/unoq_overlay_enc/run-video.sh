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
# 露出：窓の範囲の明るさで録画プログラムが決める（カメラ任せだと明るい日の外が白く飛ぶ）。ファイルが無ければ既定の値。
# カメラ任せに戻すときは $hud/exposure.ini に「mode = camera」と書く。録画中も約1秒ごとに見る。今の値は exposure.ini.status（手順書5-21）
export OVERLAY_EXPOSURE="$hud/exposure.ini"
# 針・弧・棒・Gボールの補間（届いた値の間をコマの時刻で補間して滑らかに動かす。手順書5-24）。
# $hud/smooth_ms に遅らせるミリ秒（既定100、0で補間しない＝前と同じ描き方）、$hud/telemetry_hz に走行データを読む回数（既定25）を書ける。録画の再起動で効く
[ -s "$hud/smooth_ms" ] && export OVERLAY_SMOOTH_MS="$(head -n 1 "$hud/smooth_ms" | tr -dc 0-9.)"
[ -s "$hud/telemetry_hz" ] && export OVERLAY_TELEMETRY_HZ="$(head -n 1 "$hud/telemetry_hz" | tr -dc 0-9.)"
# 音：カメラと同じUSB機器のマイク（ELPは内蔵）を探して録る（MP2・128kbps、手順書5-20）。録れなくても映像は録る。
# 止めたいときは $hud/audio_off を置く。別のマイクにしたいときは $hud/audio にALSAの名前（例 plughw:CARD=Pro,DEV=0）を書く
cam_mic() {  # $1：カメラの /dev/v4l/by-id/… 。同じUSB機器（インターフェースの親）にある音の入力のALSAの名前
    v=$(readlink -f "$1"); up=$(readlink -f "/sys/class/video4linux/${v##*/}/device/..")
    for c in /sys/class/sound/card*; do
        [ -e "$c/device" ] && [ "$(readlink -f "$c/device/..")" = "$up" ] && [ -e "/dev/snd/pcmC${c##*card}D0c" ] && { echo "plughw:CARD=$(cat "$c/id"),DEV=0"; return; }
    done
}
# 音の調整（$hud/audio.ini。無い・書いていない項目は既定。読むのは録画の起動時だけ。手順書5-23）
#   mic_volume = -15dB マイクの音量（amixer の値。dBで書く。ELPは0dBが最大、%は生の目盛りで30%は−66dB）。空なら触らない。大きいとカメラの中で割れ、後から直せない
#   mic_agc = off     カメラの自動の音量調整（on・off。空なら触らない）
#   highpass_hz = 100 この周波数より下（エンジン・路面・風の唸り）を削る。0で削らない
#   gain_db = 0       録画プログラムで足す音量（dB）。limiter = 1 で上限を超えそうな所だけ下げる（0で無し）
mic_volume_default=-15dB  # 11/6はカメラの既定の0dB（最大）で走行中に割れた。手順書5-23
ini() { [ -f "$hud/audio.ini" ] && sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*\([^#]*\).*/\1/p" "$hud/audio.ini" | tr -d '\r' | sed 's/[[:space:]]*$//' | tail -n 1; }
while :; do
    for d in /dev/v4l/by-id/*-video-index0; do
        [ -e "$d" ] || continue
        if [ -e "$hud/audio_off" ]; then OVERLAY_AUDIO=off
        elif [ -s "$hud/audio" ]; then OVERLAY_AUDIO=$(head -n 1 "$hud/audio" | tr -d '\r')
        else OVERLAY_AUDIO=$(cam_mic "$d"); fi
        export OVERLAY_AUDIO
        echo "audio: ${OVERLAY_AUDIO:-none (no microphone on the camera)}"
        if grep -q '^[[:space:]]*mic_volume[[:space:]]*=' "$hud/audio.ini" 2>/dev/null; then mv=$(ini mic_volume); else mv=$mic_volume_default; fi
        ma=$(ini mic_agc); card=${OVERLAY_AUDIO#*CARD=}; card=${card%%,*}
        case "$OVERLAY_AUDIO" in *CARD=*) ;; *) card= ;; esac
        export OVERLAY_AUDIO_PRE= OVERLAY_AUDIO_HPF="$(ini highpass_hz)" OVERLAY_AUDIO_GAIN_DB="$(ini gain_db)" OVERLAY_AUDIO_LIMIT="$(ini limiter)"
        case "$card$mv$ma" in *\'*) ;; *) [ -n "$card" ] && [ -n "$mv$ma" ] && OVERLAY_AUDIO_PRE="sh $bin/mic-volume.sh '$card' '$mv' '$ma'" ;; esac
        exec "$bin/overlay_rec" "$d" "$dir/%Y%m%d_%H%M%S.ts" 0 "$bin/hud_font_64.pgm"
    done
    sleep 5
done
