#!/bin/sh
set -eu
install -m 644 /home/arduino/EcoCapture-Web/ecocapture-mcu-start.service /etc/systemd/system/ecocapture-mcu-start.service
install -m 644 /home/arduino/EcoCapture-Web/ecocapture-web-start.service /etc/systemd/system/ecocapture-web-start.service
systemctl daemon-reload
systemctl enable ecocapture-web-start.service ecocapture-mcu-start.service
