#!/bin/sh
# EcoCapture（Godot 4 / X11）を Raspberry Pi 4B（rc-dash-4B）で起動する。
#
# RaceCapture は tty1 で DRM を直接掴む（フレームバッファ直描画）ため、
# EcoCapture と同時には動かせない。稼働中なら tty1 の getty ごと停止してから起動する。
# RaceCapture 側の設定・インストールには一切手を加えない。
#
# 設置先: Pi の /usr/local/bin/ecocapture-start
# 戻すとき: racecapture_switch_rpi.sh（Pi の /usr/local/bin/racecapture-start）
set -e

APP=/opt/ecocapture/EcoCapture.arm64
[ -x "$APP" ] || { echo "EcoCapture が $APP に見つかりません" >&2; exit 1; }

if systemctl is-active --quiet getty@tty1.service; then
    echo "RaceCapture（tty1）を停止します"
    sudo systemctl stop getty@tty1.service
    i=0
    while pgrep -x race_capture >/dev/null 2>&1 && [ "$i" -lt 20 ]; do
        sleep 1
        i=$((i + 1))
    done
fi

# vt1 上に X を起動し、その唯一のクライアントとして EcoCapture を実行する。
# X の終了＝EcoCapture の終了。
exec xinit "$APP" "$@" -- :0 vt1 -nolisten tcp
