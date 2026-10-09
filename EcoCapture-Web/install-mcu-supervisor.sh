#!/bin/sh
set -eu
install -m 644 /home/arduino/EcoCapture-Web/ecocapture-mcu-supervisor.service /etc/systemd/system/ecocapture-mcu-supervisor.service
systemctl daemon-reload
systemctl enable ecocapture-mcu-supervisor.service
systemctl restart ecocapture-mcu-supervisor.service
