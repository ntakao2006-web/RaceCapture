#!/bin/sh
set -eu
systemctl stop ecocapture-web-start.service
docker stop ecocapture-web >/dev/null
/opt/openocd/bin/arduino-flash.sh /home/arduino/hardware-check-20261003/bench_build/logger_compact.elf-zsk.bin
