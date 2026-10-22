#!/bin/sh
set -eu
export TMPDIR=/tmp
ROOT=/home/arduino
CORE="$ROOT/.arduino15/packages/arduino/hardware/zephyr/0.52.0"
STRIP="$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-strip"
ZSK="$ROOT/.arduino15/packages/arduino/tools/zephyr-sketch-tool/0.2.0/zephyr-sketch-tool"
arduino-cli compile -b arduino:zephyr:unoq --libraries "$ROOT/ecologger_v2_libraries" --output-dir "$ROOT/logger_v2_bench_build" "$ROOT/logger_v2_bench"
"$STRIP" --strip-unneeded "$ROOT/logger_v2_bench_build/logger_v2_bench.ino.elf" -o "$ROOT/logger_v2_bench_build/bench_compact.elf"
"$ZSK" "$ROOT/logger_v2_bench_build/bench_compact.elf"
FILE="$ROOT/logger_v2_bench_build/bench_compact.elf-zsk.bin"
SIZE=$(wc -c < "$FILE")
test "$SIZE" -le 65536 || { echo "Sketch exceeds the installed 64 KiB partition: $SIZE"; exit 1; }
echo "Ready to flash: $FILE ($SIZE bytes)"
# Flash separately after stopping any diagnostic capture.
