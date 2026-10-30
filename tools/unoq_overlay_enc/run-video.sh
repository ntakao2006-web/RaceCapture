#!/bin/sh
# 走行映像の焼き込み録画（ecologger-video.service から起動する）。USBカメラが見えるまで5秒ごとに待つ
#   保存先：~/ecocapture-v2-data/video/YYYYMMDD_HHMMSS.ts（OVERLAY_SEGMENT_MIN分ごとに分割）と、同じ名前の .csv（1秒ごとの時刻）
#   カメラはUSBのものだけが /dev/v4l/by-id/ に出る（エンコーダ等の /dev/video0・1 は出ない）ので、そこから最初の1台を使う
dir=/home/arduino/ecocapture-v2-data/video
bin=/opt/ecologger-video
mkdir -p "$dir"
while :; do
    for d in /dev/v4l/by-id/*-video-index0; do
        [ -e "$d" ] && exec "$bin/overlay_rec" "$d" "$dir/%Y%m%d_%H%M%S.ts" 0 "$bin/hud_font_64.pgm"
    done
    sleep 5
done
