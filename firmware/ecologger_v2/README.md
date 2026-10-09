# EcoLogger V2 実測ファーム

2026-10-03 実機確認: CAN2の20MHz発振子に合わせたビットタイミング、SDの書込み待ち中のSPI解放、停止中のSD読出し競合を修正。125/250/500/1000kbpsの外部折返しと約100フレーム/秒の継続試験で計14,400フレームが一致。SDファイル切替を含む同時取得でも欠落0。試験送信は一時ファームのみ。通常ファームはCAN1がリッスンオンリー、CAN2がセンサーハブ受信とACKのための通常モードで、アプリケーション用CANフレームは送信しない（CAN2の通常モードを実機へ書き込んだのは2026-10-09。それまでの稼働版はCAN2も受信専用だった）。詳細は `outputs/hardware_check_20261003/RESULT.txt`。

`ecologger_v2.ino` → `logger_impl.h` と `sd_logger.h`。UNO Q STM32U585 / Arduino Zephyr core 0.52.0。

- BNO055: I2C2 0x28/29、400kHz、NDOF 100Hz、A5の高加速度割り込み。
- MAX-M10M: I2C 0x42、4衛星系統/10HzのRAM設定。OTPの再書き込みなし。
- CAN1: FDCAN1、D4/D5、リッスンオンリー。CAN2: MCP25625、D10 CS / A0 reset、センサーハブ受信（ACKあり、データ送信なし）。
- SD: A4 CS、SPI共有。FAT32にCRC付きELB2ブロックを保存。65,536Bの取得待ち行列と専用保存スレッドを使用。
- Bridge: 921600bps、取得処理とは別スレッドで登録。LinuxがいなくてもSD取得・記録を開始。
- ループ監視（2026-10-09）：取得メインループが30秒以上止まると、5秒周期の`k_timer`が`NVIC_SystemReset()`でMCUを再起動する（`sys_reboot`はスケッチ側へ公開されておらずリンクできない。スレッド方式はRAM枠を超えた）。SDフォーマット等の明示的な長時間コマンド中は監視を止める。
- ⚠️ Linuxとの通信中にSTM32内部からリセットすると、再起動後もSD記録は続くが、Linuxとの通信路は戻らない（原因未特定）。Linux側の`EcoCapture-Web/mcu-supervisor.py`が30秒以上の切断を検知し、NRSTリセット手順で復帰させる。
- `build.sh`はRouterBridgeの受信スレッドを`$/reset`完了前から動かすよう修正する。修正前は完了を待つ間`k_yield()`で空回りし、優先度の低いSD保存スレッドが止まっていた（内部リセット後にSDが0バイトになった原因）。
- 試験用ビルド：`logger_impl.h`の先頭に`#define LOGGER_STALL_TEST`を足すと、`logger.command`の`STALLTEST`（ループ停止）と`RESETNOW`（即リセット）が使える。本番イメージには入れない。
- RAM：静的集計130,365Bまでは起動、130,601Bはエラーを出さずに起動しなかった（ローダー追加領域ぶん、128KiBより手前が実際の限界）。
- LTE: A3/A2は初期状態LOW。UART IRQでRX4096/TX512バイト、GPIO RTS/CTS。LinuxのLTE専用操作が20秒途絶えたら電源OFF。設定とTCP/Podium処理はUNO Q内のEcoCapture-Webが担当。詳細は `EcoCapture-Web/LTE_PODIUM.md`。

LED: CAN=直近の受信、LTE=モデム電源ON（クラウド到達はWebで確認）、UNO Q=Linuxによる受信継続、TRM=OFF、GPS=測位時点灯/未測位受信時点滅、LOG=記録指示、ERR=I2C/SDエラー、SYS=稼働。

`sh build.sh` でビルド。64KiBを超える画像は書き込みません。更新と書き込みは `EcoCapture-Web/build-mcu.sh`、Windows側は `Update-UNOQ.ps1 -Firmware`。

ビルド時に `image-audit.json`（書き込みサイズとELF静的領域）と `source-manifest.json`（ソースのSHA256）を出力します。静的領域の集計にはコード・定数・BSSを含みますが、LLEXTローダーの追加領域や実行時ヒープの増加を含まないため、ロード成功の保証ではありません。更新時の停止・起動順は共通の `EcoCapture-Web/flash-mcu.sh` で管理します。

ソースを置き換える前にUNO Q側のコピーを確保し、`python compare_sources.py <保存したecologger_v2ディレクトリ>` で改行コードを除いた差分を確認します。比較結果だけで正しい版を自動選択しません。

Bridge RPC: `logger.status` / `logger.take` / `logger.command` / `logger.sdread`。コマンドはメイン処理で実行してcompleted番号で確認します。`LOG1/LOG0`、`C500000`等、停止中の`FILES`、`SD`、`R<sector>`、`H<offset>:<hex>`、`W<sector>`。`R<sector>`は読出し位置を設定して`sector ready`を返します。`logger.sdread`は512バイトを16進形式で返し、次のセクタへ進みます。各読出しで停止状態・パーティション境界を検査します。書き込みAPIは記録中に拒否します。外部へRPCを公開しません。

SDファイルは `EcoCapture-Web/sd_decode.py` でCRC・ブロック連番を確認しCSVへ変換できます。保存時刻はMCU経過時刻で、GNSSの元メッセージも保持します。
