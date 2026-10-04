#!/bin/sh
set -eu
sh /home/arduino/ecologger_v2/build.sh
docker stop -t 15 ecocapture-web
docker run --rm --privileged --pid=host --user 0 --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 -t 1 -m -p -- /bin/sh /home/arduino/EcoCapture-Web/install-router.sh
/opt/openocd/bin/arduino-flash.sh /home/arduino/ecologger_v2_build/logger_compact.elf-zsk.bin
# Router recreates its socket: refresh the container mount.
docker start ecocapture-web
