#!/bin/sh
# Run on UNO Q. Builds RNNoise v0.1.1 (the newer v0.2 is too slow here, see
# tools/voice_gate/README.md) and installs the driver-voice helper as a service.
# Needs the internet once for the RNNoise sources (or an existing ~/rnnoise_v011).
set -eu
cd /home/arduino/EcoCapture-Web
RN=/home/arduino/rnnoise_v011
if [ ! -d "$RN" ]; then
  git clone -q https://github.com/xiph/rnnoise.git "$RN"
fi
git -C "$RN" checkout -q v0.1.1
gcc -O2 -fPIC -shared -I"$RN/include" -I"$RN/src" -o /tmp/librnnoise_old.so \
  "$RN/src/denoise.c" "$RN/src/rnn.c" "$RN/src/rnn_data.c" "$RN/src/pitch.c" "$RN/src/kiss_fft.c" "$RN/src/celt_lpc.c" -lm
# Bluetooth headsets: PipeWire must run without anyone logged in (linger, below)
# and must not keep Bluetooth for a local seat nor grab the USB card.
install -D -m 644 wireplumber-ecologger-bluetooth.conf /home/arduino/.config/wireplumber/wireplumber.conf.d/80-ecologger-bluetooth.conf
docker run --rm --pid=host --user 0:0 --entrypoint /bin/sh \
  -v /:/host -v "$PWD:/source:ro" -v /tmp/librnnoise_old.so:/rnnoise.so:ro \
  ghcr.io/arduino/app-bricks/python-apps-base:0.5.0 -c '
    set -eu
    mkdir -p /host/var/lib/systemd/linger && touch /host/var/lib/systemd/linger/arduino
    chroot /host systemctl start user@1000.service
    install -d -m 755 /host/opt/ecocapture-voice
    install -m 644 /source/voice_agent.py /host/opt/ecocapture-voice/voice_agent.py
    install -m 644 /rnnoise.so /host/opt/ecocapture-voice/librnnoise_old.so
    install -m 644 /source/ecocapture-voice.service /host/etc/systemd/system/ecocapture-voice.service
    chroot /host systemctl daemon-reload
    chroot /host systemctl enable ecocapture-voice.service
    chroot /host systemctl restart ecocapture-voice.service
    sleep 2
    chroot /host systemctl is-active ecocapture-voice.service
  '
