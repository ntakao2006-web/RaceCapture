#!/bin/sh
# Install only the hard-reset diagnostics and ttyGS0 restart-loop mitigation.
set -eu

SRC=/home/arduino/RaceCapture-UNOQ

install -d /opt/logger-v2-racecapture
install -m 755 "$SRC/incident_monitor.py" /opt/logger-v2-racecapture/incident_monitor.py
install -m 644 "$SRC/logger-v2-incident-monitor.service" /etc/systemd/system/logger-v2-incident-monitor.service

install -m 755 "$SRC/arduino-router-serial-safe.sh" /usr/local/sbin/arduino-router-serial-safe
install -d /etc/systemd/system/arduino-router-serial.service.d
install -m 644 "$SRC/arduino-router-serial-wait.conf" /etc/systemd/system/arduino-router-serial.service.d/10-wait-for-ttygs0.conf

systemctl daemon-reload
systemctl enable --now logger-v2-incident-monitor.service
systemctl restart logger-v2-incident-monitor.service
systemctl restart arduino-router-serial.service
