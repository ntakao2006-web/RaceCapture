#!/bin/sh
set -eu

MODE=${1:?vnc or web}
STATUS=/sys/class/drm/card0-DP-1/status
child=
last_state=
stable_state=
stable_count=0

stop_child() {
    if [ -n "$child" ] && kill -0 "$child" 2>/dev/null; then
        kill -TERM -- "-$child" 2>/dev/null || kill "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
    fi
    child=
}

trap 'stop_child; exit 0' INT TERM EXIT

while :; do
    state=disconnected
    [ -r "$STATUS" ] && state=$(cat "$STATUS")

    if [ "$state" = "$stable_state" ]; then
        stable_count=$((stable_count + 1))
    else
        stable_state=$state
        stable_count=1
    fi
    # Ignore one-sample HDMI hotplug glitches that would otherwise start/stop
    # both transport processes repeatedly.
    if [ "$stable_count" -lt 2 ]; then
        sleep 2
        continue
    fi

    if [ "$MODE" = vnc ] && [ "$state" = connected ] && [ "$last_state" != connected ]; then
        DISPLAY=:2 /usr/bin/python3 /opt/logger-v2-racecapture/hdmi_display.py >/dev/null 2>&1 || true
    fi
    last_state=$state

    if [ "$state" = connected ]; then
        stop_child
    elif [ -z "$child" ] || ! kill -0 "$child" 2>/dev/null; then
        [ -n "$child" ] && wait "$child" 2>/dev/null || true
        if [ "$MODE" = vnc ]; then
            /usr/bin/setsid /usr/bin/x11vnc -display :2 -localhost -rfbport 5902 -forever -shared -nopw -quiet -wait 20 -defer 20 &
        elif [ "$MODE" = web ]; then
            /usr/bin/setsid /usr/bin/websockify --web=/opt/logger-v2-racecapture/web 127.0.0.1:6080 127.0.0.1:5902 &
        else
            exit 2
        fi
        child=$!
    fi
    sleep 3
done
