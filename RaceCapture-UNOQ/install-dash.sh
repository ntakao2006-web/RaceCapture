#!/bin/sh
# Run as root on the UNO Q (after install.sh): installs EcoCapture DASH and makes it the HDMI
# screen from now on and at power-on. The RaceCapture app stays installed; dash_switch.sh
# racecapture --boot brings it back. Acquisition, SD recording and RCP keep running.
set -eu
SRC=/home/arduino/RaceCapture-UNOQ
DEST=/opt/logger-v2-racecapture
install -m 755 "$SRC/ecocapture_dash.py" "$DEST/"
install -m 644 "$SRC/dash_model.py" "$DEST/"
install -m 644 "$SRC/display_load_control.py" "$DEST/"
install -m 755 "$SRC/dash_switch.sh" "$DEST/"
install -m 644 "$SRC/ecocapture-dash.service" /etc/systemd/system/
install -m 440 "$SRC/ecocapture-dash.sudoers" /etc/sudoers.d/ecocapture-dash.tmp
if visudo -cf /etc/sudoers.d/ecocapture-dash.tmp; then
    mv /etc/sudoers.d/ecocapture-dash.tmp /etc/sudoers.d/ecocapture-dash
else
    rm -f /etc/sudoers.d/ecocapture-dash.tmp
    echo "sudoers rejected; dash_switch.sh needs root until fixed" >&2
fi
systemctl daemon-reload
"$DEST/dash_switch.sh" dash --boot
