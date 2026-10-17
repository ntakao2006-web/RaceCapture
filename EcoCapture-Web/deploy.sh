#!/bin/sh
# Run on UNO Q after copying this directory and the production sketch/libraries.
set -eu
cd /home/arduino/EcoCapture-Web
mkdir -p /home/arduino/ecocapture-v2-data/public
python3 build_public.py
python3 test_device_agent.py
python3 -m unittest -v test_flash_mcu test_mcu_supervisor test_mcu_diagnostics
docker build --network=none -t ecocapture-web:0.2.0 .
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_server.py:/app/test_server.py:ro" ecocapture-web:0.2.0 /app/test_server.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_public.py:/app/test_public.py:ro" ecocapture-web:0.2.0 /app/test_public.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_bridge.py:/app/test_bridge.py:ro" ecocapture-web:0.2.0 /app/test_bridge.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_podium.py:/app/test_podium.py:ro" ecocapture-web:0.2.0 /app/test_podium.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_lap.py:/app/test_lap.py:ro" ecocapture-web:0.2.0 /app/test_lap.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_ncec.py:/app/test_ncec.py:ro" ecocapture-web:0.2.0 /app/test_ncec.py
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_hardware.py:/app/test_hardware.py:ro" ecocapture-web:0.2.0 -m unittest -v test_hardware
docker run --rm --network=none --entrypoint python3 \
  -v "$PWD/test_sd_decode.py:/app/test_sd_decode.py:ro" ecocapture-web:0.2.0 /app/test_sd_decode.py
if docker container inspect ecocapture-web >/dev/null 2>&1; then
  docker stop -t 15 ecocapture-web
  docker rm ecocapture-web
fi
docker run -d --name ecocapture-web --restart unless-stopped \
  --user 1000:1000 --cap-drop=ALL --security-opt=no-new-privileges \
  -p 127.0.0.1:8080:8080 \
  -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
  -v /run/ecocapture-admin:/run/ecocapture-admin \
  -v /run/ecocapture-voice:/run/ecocapture-voice \
  -v /home/arduino/ecocapture-v2-data:/data \
  --log-opt max-size=5m --log-opt max-file=2 \
  ecocapture-web:0.2.0
if docker container inspect ecocapture-viewer >/dev/null 2>&1; then
  docker stop -t 10 ecocapture-viewer
  docker rm ecocapture-viewer
fi
docker run -d --name ecocapture-viewer --restart unless-stopped \
  --user 1000:1000 --cap-drop=ALL --security-opt=no-new-privileges \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -p 8081:8081 \
  -v /home/arduino/ecocapture-v2-data/public:/telemetry:ro \
  --log-opt max-size=5m --log-opt max-file=2 \
  --entrypoint python3 ecocapture-web:0.2.0 \
  -m uvicorn public_server:app --host 0.0.0.0 --port 8081 --no-access-log
