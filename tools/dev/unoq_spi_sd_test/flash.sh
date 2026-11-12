#!/bin/sh
# STM32 へスケッチを書き込む（試験用。Linux側のシリアルを固めない順番にしたもの）
#   試験ファーム:  sh flash.sh ~/spi_sd_test_build/test_compact.elf-zsk.bin
#   元に戻す:      sh flash.sh ~/fw_backup/sketch_0x80F0000.bin
#
# 2026-10-09 実機で起きたこと：ルーターが動いたまま STM32 を止めて書き込むと、
#   ・Linux側のUART（ttyHS1、RTS/CTS付き）に送りかけのデータが残り、ルーターの停止が時間切れ→SIGKILLでも消えない
#   ・以後どのファームでも Bridge が繋がらない（ドライバが固まる）。復旧には Linux の再起動が要った
# そこで「Web停止 → ルーター停止 → 書き込み → ルーター起動 → STM32リセット → Web起動」の順にする。
# 最後のリセットは、ルーターが待ち受けてから STM32 に $/reset を送り直させるため（Bridge は返事が来ないと永久に待つ）。
set -eu
# Keep one implementation, including exit-status checks (no grep/|| true).
exec sh /home/arduino/EcoCapture-Web/flash-mcu.sh "$@"
