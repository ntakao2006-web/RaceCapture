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
while :; do
    for d in /dev/v4l/by-id/*-video-index0; do
        [ -e "$d" ] && exec "$bin/overlay_rec" "$d" "$dir/%Y%m%d_%H%M%S.ts" 0 "$bin/hud_font_64.pgm"
    done
    sleep 5
done
