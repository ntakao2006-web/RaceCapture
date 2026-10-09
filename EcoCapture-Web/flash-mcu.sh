#!/bin/sh
# Shared production/test flashing order. Run on the configured UNO Q.
set -eu
if [ "$#" -ne 1 ]; then
    echo "Usage: sh flash-mcu.sh sketch.bin" >&2
    exit 2
fi
IMG=$1
test -s "$IMG"
SIZE=$(wc -c < "$IMG")
test "$SIZE" -le 65536 || {
    echo "Sketch partition is 64 KiB; refusing $SIZE-byte image" >&2
    exit 1
}
test -x /opt/openocd/bin/arduino-flash.sh
test -x /opt/openocd/bin/openocd
command -v timeout >/dev/null
host_sh() {
    docker run --rm --privileged --pid=host --user 0 \
        --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 \
        -t 1 -m -p -- /bin/sh "$@"
}
PHASE=preflight
failed() {
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "MCU update failed at $PHASE (exit $rc). Web is not restarted automatically." >&2
        echo "If ttyHS1/router is stuck, reboot Linux before retrying. Preserve the known-good backup." >&2
    fi
}
trap failed EXIT
PHASE=web-stop
timeout 30 docker stop -t 15 ecocapture-web
PHASE=router-stop
host_sh -c '
    set -eu
    timeout 25 systemctl stop arduino-router
    state=$(systemctl show arduino-router -p ActiveState --value)
    pid=$(systemctl show arduino-router -p MainPID --value)
    test "$state" = inactive && test "$pid" = 0
'
# Do not halt/reset the STM32 unless router shutdown has succeeded.
PHASE=flash
timeout 120 /opt/openocd/bin/arduino-flash.sh "$IMG"
PHASE=router-start
host_sh -c '
    set -eu
    sh /home/arduino/EcoCapture-Web/install-router.sh --no-start
    timeout 25 systemctl start arduino-router
    n=0
    until systemctl is-active --quiet arduino-router && test -S /var/run/arduino-router.sock; do
        n=$((n+1))
        test "$n" -lt 15 || exit 1
        sleep 1
    done
'
# Allow ExecStartPost/RTS-CTS to settle before Bridge sends its startup reset.
sleep 3
PHASE=mcu-reset
timeout 20 /opt/openocd/bin/openocd -d1 -s /opt/openocd \
    -f /opt/openocd/openocd_gpiod.cfg \
    -c "reset_config srst_only srst_push_pull; init; reset run; shutdown"
PHASE=web-start
# Starting again refreshes the bind mount for the recreated router socket.
timeout 30 docker start ecocapture-web
PHASE=complete
echo "Flashed: $IMG ($SIZE bytes). Check Bridge reception and SD logging."
