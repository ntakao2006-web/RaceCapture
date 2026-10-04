#!/bin/sh
set -eu

MODE=${1:?vnc or web}
STATUS=/sys/class/drm/card0-DP-1/status
child=
last_state=

stop_child() {
    if [ -n "$child" ] && kill -0 "$child" 2>/dev/null; then
        kill "$child"
        wait "$child" 2>/dev/null || true
    fi
    child=
}

trap 'stop_child; exit 0' INT TERM EXIT

while :; do
    state=disconnected
    [ -r "$STATUS" ] && state=$(cat "$STATUS")

    if [ "$MODE" = vnc ] && [ "$state" = connected ] && [ "$last_state" != connected ]; then
        DISPLAY=:2 /usr/bin/xrandr --output DP-1 --auto --primary >/dev/null 2>&1 || true
    fi
    last_state=$state

    if [ "$state" = connected ]; then
        stop_child
    elif [ -z "$child" ] || ! kill -0 "$child" 2>/dev/null; then
        [ -n "$child" ] && wait "$child" 2>/dev/null || true
        if [ "$MODE" = vnc ]; then
            /usr/bin/x11vnc -display :2 -localhost -rfbport 5902 -forever -shared -nopw -quiet -wait 10 -defer 10 &
        elif [ "$MODE" = web ]; then
            /usr/bin/websockify --web=/opt/logger-v2-racecapture/web 127.0.0.1:6080 127.0.0.1:5902 &
        else
            exit 2
        fi
        child=$!
    fi
    sleep 3
done
