# EcoLogger V2 実測ファーム

2026-10-03 実機確認: CAN2の20MHz発振子に合わせたビットタイミング、SDの書込み待ち中のSPI解放、停止中のSD読出し競合を修正。125/250/500/1000kbpsの外部折返しと約100フレーム/秒の継続試験で計14,400フレームが一致。SDファイル切替を含む同時取得でも欠落0。試験送信は一時ファームのみ。通常ファームはCAN1がリッスンオンリー、CAN2がセンサーハブ受信とACKのための通常モードで、アプリケーション用CANフレームは送信しない。詳細は `outputs/hardware_check_20261003/RESULT.txt`。

`ecologger_v2.ino` → `logger_impl.h` と `sd_logger.h`。UNO Q STM32U585 / Arduino Zephyr core 0.52.0。

- BNO055: I2C2 0x28/29、400kHz、NDOF 100Hz、A5の高加速度割り込み。
- MAX-M10M: I2C 0x42、4衛星系統/10HzのRAM設定。OTPの再書き込みなし。
- CAN1: FDCAN1、D4/D5、リッスンオンリー。CAN2: MCP25625、D10 CS / A0 reset、センサーハブ受信（ACKあり、データ送信なし）。
- SD: A4 CS、SPI共有。FAT32にCRC付きELB2ブロックを保存。65,536Bの取得待ち行列と専用保存スレッドを使用。
- Bridge: 460800bps、取得処理とは別スレッドで登録。LinuxがいなくてもSD取得・記録を開始。取得メインループが30秒以上停止した場合は監視スレッドがMCUを再起動して自動復旧します。SDフォーマット等の明示的な長時間コマンド中は監視を一時停止します。
- LTE: A3/A2は初期状態LOW。UART IRQでRX4096/TX512バイト、GPIO RTS/CTS。LinuxのLTE専用操作が20秒途絶えたら電源OFF。設定とTCP/Podium処理はUNO Q内のEcoCapture-Webが担当。詳細は `EcoCapture-Web/LTE_PODIUM.md`。

LED: CAN=直近の受信、LTE=モデム電源ON（クラウド到達はWebで確認）、UNO Q=Linuxによる受信継続、TRM=OFF、GPS=測位時点灯/未測位受信時点滅、LOG=記録指示、ERR=I2C/SDエラー、SYS=稼働。

`sh build.sh` でビルド。64KiBを超える画像は書き込みません。更新と書き込みは `EcoCapture-Web/build-mcu.sh`、Windows側は `Update-UNOQ.ps1 -Firmware`。

Bridge RPC: `logger.status` / `logger.take` / `logger.command` / `logger.sdread`。コマンドはメイン処理で実行してcompleted番号で確認します。`LOG1/LOG0`、`C500000`等、停止中の`FILES`、`SD`、`R<sector>`、`H<offset>:<hex>`、`W<sector>`。`R<sector>`は読出し位置を設定して`sector ready`を返します。`logger.sdread`は512バイトを16進形式で返し、次のセクタへ進みます。各読出しで停止状態・パーティション境界を検査します。書き込みAPIは記録中に拒否します。外部へRPCを公開しません。

SDファイルは `EcoCapture-Web/sd_decode.py` でCRC・ブロック連番を確認しCSVへ変換できます。保存時刻はMCU経過時刻で、GNSSの元メッセージも保持します。
