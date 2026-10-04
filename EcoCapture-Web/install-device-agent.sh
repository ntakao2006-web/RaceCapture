#!/bin/sh
# Run on UNO Q. Installs only EcoCapture's helper and service, not OS/firmware updates.
set -eu
cd /home/arduino/EcoCapture-Web
test -s /home/arduino/ecocapture-cloudflared
docker run --rm --pid=host --user 0:0 --entrypoint /bin/sh \
  -v /:/host -v "$PWD:/source:ro" -v /home/arduino/ecocapture-cloudflared:/cloudflared:ro \
  ghcr.io/arduino/app-bricks/python-apps-base:0.5.0 -c '
    set -eu
    install -d -m 755 /host/opt/ecocapture-admin
    install -d -m 700 /host/var/lib/ecocapture-admin
    install -m 644 /source/device_agent.py /host/opt/ecocapture-admin/device_agent.py
    install -m 755 /cloudflared /host/opt/ecocapture-admin/cloudflared
    install -m 644 /source/ecocapture-admin.service /host/etc/systemd/system/ecocapture-admin.service
    chroot /host systemctl daemon-reload
    chroot /host systemctl enable ecocapture-admin.service
    chroot /host systemctl restart ecocapture-admin.service
    chroot /host systemctl is-active ecocapture-admin.service
  '
