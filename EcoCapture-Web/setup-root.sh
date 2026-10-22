#!/bin/sh
# Root half of moving EcoLogger onto a fresh UNO Q (first used 2026-10-21, new board).
# Run on the UNO Q after ~/EcoCapture-Web, ~/ecologger_v2* and the data folder are copied
# and deploy.sh has built the container:
#   sudo sh /home/arduino/EcoCapture-Web/setup-root.sh "<UTC time, YYYY-MM-DD HH:MM:SS>" <sketch.bin>
# A fresh board has no network time, and its clock starts months behind.
set -eu
test "$(id -u)" = 0 || { echo "sudo で実行してください" >&2; exit 1; }
test "$#" = 2 || { echo "Usage: setup-root.sh '<UTC time>' <sketch.bin>" >&2; exit 2; }
cd /home/arduino/EcoCapture-Web
date -u -s "$1"
hwclock -w 2>/dev/null || true
sh install-router.sh --no-start
# A stalled serial reader otherwise delays boot recovery for 90 seconds (as on the first board).
printf '[Service]\nTimeoutStopSec=8s\n' > /etc/systemd/system/arduino-router.service.d/stop-timeout.conf
sh install-boot.sh
sh install-mcu-supervisor.sh
# The admin helper (Wi-Fi status and the numeric address for the course-walk QR) was missed on
# the 2026-10-21 move; without it phones only get uno-q.local, which Android cannot open.
sh install-device-agent.sh
# Boot handshake check and touch UI from the first board (Lintaroh), if copied.
if [ -f /home/arduino/opt.tar ]; then
  tar xf /home/arduino/opt.tar -C /
  systemctl daemon-reload
  systemctl enable ecocapture-boot-check.service ecocapture-native.service
fi
# A fresh board ships with ssh and mDNS off; development over the phone's tethering
# needs both (ssh unoq = uno-q.local). Joining the tethering itself is per-user:
#   nmcli -w 300 --ask dev wifi connect <SSID>
# The image also has no host keys, so sshd -t fails until they are made.
ssh-keygen -A
systemctl enable --now ssh avahi-daemon
# flash-mcu.sh stops the web and router, flashes, restarts the router at 921600, resets the MCU.
su arduino -c "sh /home/arduino/EcoCapture-Web/flash-mcu.sh '$2'"
echo "完了しました"
