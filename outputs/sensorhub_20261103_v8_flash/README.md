# PIC v8 の書き込み（2026-11-03）

SensorHubのPIC18F26Q84へ、Lintarohさんのv8（Defi電圧入力、CAN2 0x580）を書き込んだときの記録。

## 使ったもの

- 書き込み器：MPLAB Snap（S/N 021038102RYN014624）。書く間だけMPLAB用ファームへ切り替え、終わったらCMSIS-DAPへ戻した（`../../pic18f26q84_blink.X/snap_uart_setup/switch_*_20261103_*.log`）
- MPLAB X / IPE 6.35（このPCへ新しく入れた。インストーラーのSHA-256は公式ページの値 `64a5247d…2061` と一致）、PIC18F-Q_DFP 1.30.487
- HEX：`pic18f26q84_blink.X/dist/default/production/pic18f26q84_blink.X.production.hex`（SHA-256 `F4238F83…6E6E`、引継ぎの値と一致）

## したこと

1. 書く前に中身を読み出した：`firmware_v7_readback.hex`。リポジトリのv7（`outputs/sensorhub_20261019/oiltemp_status/firmware_v7.hex`）とプログラム8287バイト・設定ワード11バイトとも一致。v7へ戻すときはこれを書く
2. v8を書き込み・照合：`ipe_logs/program_v8_224512.log`（`-M -Y -OL`、Program Succeeded／Verification successful）
3. PICのUART（COM16）：`uart_v8_first.txt`。PRESS adc=0（LOW_RAIL、未接続）、TEMP1 約2.02 V、TEMP2 約2.15 V（UNQUALIFIED）、CANの送受信エラー0
4. UNO Q：0x580を約108 ms間隔（約9.3 Hz）で受信。`Temp1Volt` 2.03 V・`Temp2Volt` 2.17 V（未校正）、`PressVolt` 0.0 V（下限付近）。旧0x600は止まり、`OilTemp`は通信途絶。20秒でCAN2のオーバーフロー・dropped・SDエラーの増加なし

## まだのこと

- TEMP1・TEMP2のどちらが油温・水温か（TEMP1に赤黒っぽいカプラー、TEMP2にピンクのカプラー。Defiの資料に色の記載は無い）
- 油圧（PRESS、15番ピン）はハーネスが未作成でつないでいない
- 3入力のテスターとの照合、℃・kPaへの換算
