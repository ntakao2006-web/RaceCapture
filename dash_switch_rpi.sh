#!/bin/sh
# rc-dash-4B の tty1 に出す画面を EcoCapture / RaceCapture 間で切り替える。
#
#   dash-switch ecocapture   … EcoCapture へ切替
#   dash-switch racecapture  … RaceCapture へ切替
#
# 選んだモードは /etc/dash-mode に書き込まれ、次回以降の電源投入時も維持される
# （tty1 の自動ログイン → ~/.bashrc → dash-autostart が /etc/dash-mode を読む）。
#
# RaceCapture は tty1 で DRM を直接掴む（フレームバッファ直描画）、
# EcoCapture(Godot 4) は X11 必須のため、両者は同時には動かせない。
# 切替の実体は tty1 のセッションを畳んで張り直すこと。
#
# 設置先: Pi の /usr/local/bin/dash-switch
set -e

MODE=$1
case "$MODE" in
ecocapture)
    [ -x /opt/ecocapture/EcoCapture.arm64 ] || {
        echo "EcoCapture が /opt/ecocapture/EcoCapture.arm64 に見つかりません" >&2
        exit 1
    }
    ;;
racecapture)
    [ -x /opt/racecapture/run_racecapture_rpi.sh ] || {
        echo "RaceCapture が /opt/racecapture に見つかりません" >&2
        exit 1
    }
    ;;
*)
    echo "使い方: $(basename "$0") {ecocapture|racecapture}" >&2
    exit 2
    ;;
esac

echo "$MODE" | sudo tee /etc/dash-mode >/dev/null

# 現在 tty1 に出ているものを畳む。getty@.service は KillMode=process なので
# 子プロセス（race_capture / xinit）は自前で落とす。
sudo systemctl stop getty@tty1.service || true
pkill -x race_capture 2>/dev/null || true
pkill -f '/opt/ecocapture/EcoCapture.arm64' 2>/dev/null || true
pkill -x xinit 2>/dev/null || true

i=0
while pgrep -x race_capture >/dev/null 2>&1 || pgrep -x xinit >/dev/null 2>&1; do
    [ "$i" -lt 20 ] || break
    sleep 1
    i=$((i + 1))
done

sudo systemctl start getty@tty1.service
echo "$MODE へ切り替えました（次回の電源投入時も $MODE が起動します）"
