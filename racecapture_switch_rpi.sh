#!/bin/sh
# EcoCapture を終了し、Raspberry Pi 4B（rc-dash-4B）を RaceCapture 側へ戻す。
#
# 設置先: Pi の /usr/local/bin/racecapture-start
set -e

pkill -f '/opt/ecocapture/EcoCapture.arm64' 2>/dev/null || true
pkill -x xinit 2>/dev/null || true
sleep 2

# tty1 へ自動ログイン → ~/.bashrc から race_capture が起動する（従来どおり）
sudo systemctl start getty@tty1.service
echo "RaceCapture（tty1）を起動しました"
