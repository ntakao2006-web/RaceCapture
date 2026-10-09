#!/bin/sh
set -eu
case "${1:-}" in
    '') start_router=true ;;
    --no-start) start_router=false ;;
    *) echo "Usage: install-router.sh [--no-start]" >&2; exit 2 ;;
esac
test "$#" -le 1
install -d /etc/systemd/system/arduino-router.service.d
install -m 644 /home/arduino/EcoCapture-Web/ecologger-router.conf /etc/systemd/system/arduino-router.service.d/ecologger.conf
systemctl daemon-reload
if [ "$start_router" = true ]; then
    systemctl restart arduino-router
fi
