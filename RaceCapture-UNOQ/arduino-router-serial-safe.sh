#!/bin/sh
# Keep the serial proxy idle until the USB gadget node is actually available.
set -eu

device=${ARDUINO_ROUTER_SERIAL_DEVICE:-/dev/ttyGS0}
socat=${ARDUINO_ROUTER_SOCAT:-/usr/bin/socat}

while [ ! -c "$device" ]; do
    sleep 2
done

exec "$socat" "file:$device,raw,echo=0,b9600,crtscts=0" tcp:127.0.0.1:7500
