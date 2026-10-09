#!/bin/sh
# UNO Q上で試験ファームをビルドする（ロガー本体の firmware/ecologger_v2/build.sh の後半と同じ手順）。
# RouterBridge/RPClite への修正は ecologger_v2/build.sh が適用済みの前提（ライブラリを直接書き換える方式のため）。
# 書き込み:  sh ~/unoq_spi_sd_test/flash.sh ~/spi_sd_test_build/test_compact.elf-zsk.bin
# 元に戻す:  sh ~/unoq_spi_sd_test/flash.sh ~/fw_backup/sketch_0x80F0000.bin
# 共通手順 ~/EcoCapture-Web/flash-mcu.sh を先に更新すること。
set -eu
export TMPDIR=/tmp
ROOT=/home/arduino
SRC="$ROOT/unoq_spi_sd_test/unoq_spi_sd_test"
BUILD="$ROOT/spi_sd_test_build"
T="$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-"
arduino-cli compile -b arduino:zephyr:unoq --libraries "$ROOT/ecologger_v2_libraries" --output-dir "$BUILD" "$SRC"
"${T}objcopy" -G setup -G loop "$BUILD/unoq_spi_sd_test.ino.elf" "$BUILD/test_compact.elf"
"${T}strip" --strip-unneeded "$BUILD/test_compact.elf"
python3 "$ROOT/ecologger_v2/compact_symbols.py" "$T" "$BUILD/test_compact.elf" "$BUILD/test_short.elf"
mv "$BUILD/test_short.elf" "$BUILD/test_compact.elf"
"$ROOT/.arduino15/packages/arduino/tools/zephyr-sketch-tool/0.2.0/zephyr-sketch-tool" "$BUILD/test_compact.elf"
SIZE=$(wc -c < "$BUILD/test_compact.elf-zsk.bin")
test "$SIZE" -le 65536 || { echo "Installed sketch partition is 64 KiB; image is $SIZE bytes"; exit 1; }
echo "Ready: $BUILD/test_compact.elf-zsk.bin ($SIZE bytes)"
