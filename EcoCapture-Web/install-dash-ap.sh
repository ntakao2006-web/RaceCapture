#!/bin/sh
# The UNO Q's Wi-Fi as an access point (no internet) for the car's dash phone
# (android-logger LoggerLink.kt, ER-11-17). The phone reads the logger's position
# from the course-walk server (field.py, :8082) at 10.42.0.1. Telemetry keeps
# going out over LTE; it never used this Wi-Fi.
#
#   sudo sh install-dash-ap.sh <ssid> <password>   access point on, client Wi-Fi off
#   sudo sh install-dash-ap.sh --off                back to the client Wi-Fi (tethering)
#
# Client profiles are kept; only their autoconnect is turned off while the access
# point is on, and the ones turned off are listed in $STATE for --off.
set -eu
NAME=ecologger-dash
STATE=/var/lib/ecocapture/dash-ap-client-profiles

if [ "${1:-}" = "--off" ]; then
    nmcli connection delete "$NAME" >/dev/null 2>&1 || true
    if [ -f "$STATE" ]; then
        while read -r uuid; do nmcli connection modify "$uuid" connection.autoconnect yes || true; done < "$STATE"
        rm -f "$STATE"
    fi
    nmcli device connect wlan0 || true
    exit 0
fi

SSID=${1:?ssid}; PASS=${2:?password}
[ "${#PASS}" -ge 8 ] || { echo "password must be 8 characters or more" >&2; exit 1; }

nmcli radio wifi on
nmcli connection delete "$NAME" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname wlan0 con-name "$NAME" autoconnect yes ssid "$SSID" \
    802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
    ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" \
    connection.autoconnect-priority 100 >/dev/null

mkdir -p "$(dirname "$STATE")"
: > "$STATE.new"
for uuid in $(nmcli -t -f UUID,TYPE connection show | awk -F: '$2=="802-11-wireless"{print $1}'); do
    [ "$(nmcli -g connection.id connection show "$uuid")" = "$NAME" ] && continue
    [ "$(nmcli -g connection.autoconnect connection show "$uuid")" = "yes" ] || continue
    nmcli connection modify "$uuid" connection.autoconnect no
    echo "$uuid" >> "$STATE.new"
done
# Keep the list from a first run if this is a re-run (the profiles are already off by then).
[ -s "$STATE" ] && [ ! -s "$STATE.new" ] && rm -f "$STATE.new" || mv "$STATE.new" "$STATE"

nmcli connection up "$NAME"
nmcli -t -f GENERAL.STATE,IP4.ADDRESS device show wlan0
