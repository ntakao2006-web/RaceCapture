#!/bin/sh
# tty1 への自動ログイン（getty@tty1 + agetty --autologin）から ~/.bashrc 経由で呼ばれ、
# /etc/dash-mode の内容に応じて EcoCapture か RaceCapture のどちらかを起動する。
#
# モードの切替は dash-switch（ecocapture-start / racecapture-start）で行う。
# ファイルが無い／読めない場合は EcoCapture を起動する（EcoCapture が既定）。
#
# 設置先: Pi の /usr/local/bin/dash-autostart

MODE_FILE=/etc/dash-mode
MODE=ecocapture
if [ -r "$MODE_FILE" ]; then
    MODE=$(tr -d ' \t\r\n' < "$MODE_FILE")
fi

case "$MODE" in
racecapture)
    echo "Starting RaceCapture!"
    exec /opt/racecapture/run_racecapture_rpi.sh -w 1 -- \
        -c graphics:show_cursor:0 -a -m cursor -c kivy:keyboard_mode:systemandmulti
    ;;
*)
    APP=/opt/ecocapture/EcoCapture.arm64
    if [ ! -x "$APP" ]; then
        echo "EcoCapture が $APP に見つかりません。シェルに留まります。" >&2
        exit 1
    fi
    echo "Starting EcoCapture!"
    # vt1 上に X を起動し、その唯一のクライアントとして EcoCapture を実行する。
    # X の終了＝EcoCapture の終了。
    exec xinit "$APP" -- :0 vt1 -nolisten tcp
    ;;
esac
