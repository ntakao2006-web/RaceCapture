#!/bin/sh
set -eu
install -d /etc/systemd/system/arduino-router.service.d
install -m 644 /home/arduino/EcoCapture-Web/ecologger-router.conf /etc/systemd/system/arduino-router.service.d/ecologger.conf
systemctl daemon-reload
systemctl restart arduino-router
