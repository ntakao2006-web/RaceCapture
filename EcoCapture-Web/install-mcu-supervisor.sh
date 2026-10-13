#!/bin/sh
set -eu
# Do not replace this file; flash/recovery may already hold a lock on its inode.
touch /run/lock/ecocapture-mcu.lock
chown arduino:gpiod /run/lock/ecocapture-mcu.lock
chmod 660 /run/lock/ecocapture-mcu.lock
install -m 644 /home/arduino/EcoCapture-Web/ecocapture-mcu-supervisor.service /etc/systemd/system/ecocapture-mcu-supervisor.service
systemctl daemon-reload
systemctl enable ecocapture-mcu-supervisor.service
systemctl restart ecocapture-mcu-supervisor.service
