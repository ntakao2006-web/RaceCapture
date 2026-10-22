#!/bin/sh
set -eu
export TMPDIR=/tmp
ROOT=/home/arduino
BUILD="$ROOT/ecologger_v2_can_check_build"
arduino-cli compile -b arduino:zephyr:unoq --libraries "$ROOT/ecologger_v2_libraries" --output-dir "$BUILD" "$ROOT/ecologger_v2_can_check"
"$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-objcopy" -G setup -G loop "$BUILD/ecologger_v2_can_check.ino.elf" "$BUILD/logger_compact.elf"
"$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-strip" --strip-unneeded "$BUILD/logger_compact.elf"
"$ROOT/.arduino15/packages/arduino/tools/zephyr-sketch-tool/0.2.0/zephyr-sketch-tool" "$BUILD/logger_compact.elf"
SIZE=$(wc -c < "$BUILD/logger_compact.elf-zsk.bin")
test "$SIZE" -le 65536 || { echo "Installed sketch partition is 64 KiB; image is $SIZE bytes"; exit 1; }
echo "Ready: $BUILD/logger_compact.elf-zsk.bin ($SIZE bytes)"
# Flash separately; do not interrupt voltage measurements or an SD write.
