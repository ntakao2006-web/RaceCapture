#!/bin/sh
set -eu
systemctl stop ecocapture-web-start.service
systemctl restart arduino-router.service
docker stop ecocapture-web ecocapture-viewer >/dev/null
/opt/openocd/bin/arduino-flash.sh /home/arduino/ecologger_v2_build/logger_compact.elf-zsk.bin
