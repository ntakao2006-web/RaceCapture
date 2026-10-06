#!/bin/sh
# Run as root on the connected UNO Q after installing the official ARM64 package.
set -eu
SRC=/home/arduino/RaceCapture-UNOQ
install -d /opt/logger-v2-racecapture /opt/logger-v2-racecapture/web
install -m 644 "$SRC/rcp_bridge.py" /opt/logger-v2-racecapture/
install -m 755 "$SRC/launch.sh" /opt/logger-v2-racecapture/
install -m 755 "$SRC/display_transport.sh" /opt/logger-v2-racecapture/
install -m 755 "$SRC/hdmi_display.py" /opt/logger-v2-racecapture/
install -m 644 "$SRC/display_load_control.py" /opt/logger-v2-racecapture/
install -m 755 "$SRC/configure_hdmi_profile.py" /opt/logger-v2-racecapture/
install -m 755 "$SRC/fit_window.py" /opt/logger-v2-racecapture/
install -m 755 "$SRC/touch_launcher.py" /opt/logger-v2-racecapture/
install -m 755 "$SRC/ecocapture-native" /opt/logger-v2-racecapture/
install -m 755 "$SRC/incident_monitor.py" /opt/logger-v2-racecapture/
install -m 644 "$SRC/xorg.conf" /opt/logger-v2-racecapture/
install -m 644 "$SRC/fastnav.py" /opt/racecapture/_internal/kivy_install/modules/fastnav.py
install -m 755 "$SRC/arduino-router-serial-safe.sh" /usr/local/sbin/arduino-router-serial-safe
install -d /etc/systemd/system/arduino-router-serial.service.d
install -m 644 "$SRC/arduino-router-serial-wait.conf" /etc/systemd/system/arduino-router-serial.service.d/10-wait-for-ttygs0.conf
cp -a /usr/share/novnc/. /opt/logger-v2-racecapture/web/
install -m 644 "$SRC/index.html" /opt/logger-v2-racecapture/web/index.html
for service in logger-v2-rcp racecapture-display racecapture-vnc racecapture-web racecapture-app ecocapture-native racecapture-touch logger-v2-incident-monitor; do
    install -m 644 "$SRC/$service.service" /etc/systemd/system/
done
systemctl disable --now lightdm.service
systemctl daemon-reload
systemctl enable --now logger-v2-rcp.service racecapture-display.service racecapture-vnc.service racecapture-web.service racecapture-app.service ecocapture-native.service racecapture-touch.service logger-v2-incident-monitor.service
systemctl restart logger-v2-incident-monitor.service
systemctl restart arduino-router-serial.service
