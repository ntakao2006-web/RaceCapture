#!/bin/sh
set -eu
sh /home/arduino/ecologger_v2/build.sh
sh /home/arduino/EcoCapture-Web/flash-mcu.sh /home/arduino/ecologger_v2_build/logger_compact.elf-zsk.bin
