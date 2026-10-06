#!/bin/sh
# Install the bounded HDMI profile without stopping LoggerV2 acquisition or SD recording.
set -eu

SRC=/home/arduino/RaceCapture-UNOQ
DEST=/opt/logger-v2-racecapture

install -m 755 "$SRC/display_transport.sh" "$DEST/display_transport.sh"
install -m 755 "$SRC/hdmi_display.py" "$DEST/hdmi_display.py"
install -m 644 "$SRC/display_load_control.py" "$DEST/display_load_control.py"
install -m 755 "$SRC/configure_hdmi_profile.py" "$DEST/configure_hdmi_profile.py"
install -m 755 "$SRC/touch_launcher.py" "$DEST/touch_launcher.py"
install -m 755 "$SRC/incident_monitor.py" "$DEST/incident_monitor.py"

systemctl stop racecapture-app.service
runuser -u arduino -- /usr/bin/python3 "$DEST/configure_hdmi_profile.py"
systemctl start racecapture-app.service
systemctl restart racecapture-touch.service racecapture-vnc.service racecapture-web.service
systemctl restart logger-v2-incident-monitor.service
