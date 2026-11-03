#!/bin/sh
# Which app is on the HDMI screen: dash (EcoCapture DASH) or racecapture (the RaceCapture app).
# The two conflict, so starting one stops the other; logging is not touched either way.
#   dash_switch.sh dash|racecapture [--boot]   --boot: also what comes up at the next power-on
#   dash_switch.sh status
# Runs as arduino through ecocapture-dash.sudoers (install-dash.sh puts it in place).
set -eu
SYSTEMCTL="sudo -n /usr/bin/systemctl"
[ "$(id -u)" = 0 ] && SYSTEMCTL=/usr/bin/systemctl
case "${1:-status}" in
dash)
    if [ "${2:-}" = --boot ]; then
        $SYSTEMCTL disable racecapture-app.service racecapture-touch.service
        $SYSTEMCTL enable ecocapture-dash.service
    fi
    $SYSTEMCTL start ecocapture-dash.service
    ;;
racecapture)
    if [ "${2:-}" = --boot ]; then
        $SYSTEMCTL disable ecocapture-dash.service
        $SYSTEMCTL enable racecapture-app.service racecapture-touch.service
    fi
    $SYSTEMCTL start racecapture-app.service
    $SYSTEMCTL start racecapture-touch.service
    ;;
status) ;;
*)
    echo "usage: $0 dash|racecapture [--boot] | status" >&2
    exit 2
    ;;
esac
for unit in ecocapture-dash racecapture-app; do
    echo "$unit: $(systemctl is-active "$unit.service" || true) (power-on: $(systemctl is-enabled "$unit.service" 2>/dev/null || true))"
done
