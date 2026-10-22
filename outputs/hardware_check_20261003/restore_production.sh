#!/bin/sh
set -eu
/opt/openocd/bin/arduino-flash.sh /home/arduino/ecologger_v2_build/logger_compact.elf-zsk.bin
docker rm ecocapture-web
docker run -d --name ecocapture-web --restart unless-stopped \
 --user 1000:1000 --cap-drop=ALL --security-opt=no-new-privileges \
 -p 127.0.0.1:8080:8080 \
 -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
 -v /run/ecocapture-admin:/run/ecocapture-admin \
 -v /home/arduino/ecocapture-v2-data:/data \
 --log-opt max-size=5m --log-opt max-file=2 ecocapture-web:0.2.0
systemctl start ecocapture-web-start.service
