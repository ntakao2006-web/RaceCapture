# logger_v1 実装基板用ファームウェア

対象は ESP32-S3-WROOM-1-N16R8、BNO055、MAX-M10M-00B、ATA6561、MCP25625 を搭載した
`circuit/logger_v1` の実装基板です。古いDevKit/LSM6向け `firmware/src/main.cpp` や
診断専用 `v1_test` と混同しないでください。

基準要求: ユーザーが取得したGit `cf1c711`。GPIO/パルス/外部アナログセンサーはCANハブ経由です。
回路・配線・既存の診断版は変更していません。
書込み済みイメージの識別と検証範囲は [VERIFICATION.md](VERIFICATION.md) を参照してください。
今回の完了範囲・残作業・次回再開手順は [HANDOFF.md](HANDOFF.md) にまとめています。

## 動作

- 電源投入でSDへ100 Hzの全チャンネルCSVと、受信した生CANフレームを記録します。
  `/logs/Lxxxxxxxx_nnnn.csv` と対応する `_can.csv` を作成します。
  USB切断やアプリ終了ではSD記録を停止しません。
- 500 msごとに `fflush` と `fsync` を実行します。これは電源瞬断時の損失量の保証ではありません。
  電源投入・明示的な区切り・チャンネル定義変更・256 MiB到達でファイルを分けます。
  既存ログの削除、自動フォーマット、満杯時の自動上書きは行いません。
- ATA6561/J5: CAN1、500 kbps、listen-only（送信もACKも行わない）。
  MCP25625/J4: CAN2、500 kbps、外部センサーハブ用。
  車載フレームを無条件に別バスへ中継しません。
- BNO055: 100 Hz、I2C。`AccelX/Y/Z` は重力を含むm/s²、`GravityX/Y/Z` は推定重力、
  `GForceX/Y/Z` は重力を除いた加速度をG単位で記録します。X/Yに一律+0.3を加算しません。
  `IMUCal` はBNO055の校正状態ビットです。完全校正255になれば22バイトの補正値を保存します。
- GNSS: GPS+QZSS+SBAS、不要なNMEA出力を停止、UART115200、UBX-NAV-PVTを毎測位出力。
  通常クロックの最大18 Hzに対して56 ms周期（約17.86 Hz）。高性能クロック設定を読み取り確認できた場合は40 ms（25 Hz）。
  **このファームウェアは不可逆なOTP設定を書き込みません。**
  この実機は2026-08-31の明示承認後、メーカー指定のOTP設定を一度実施・読戻し済みです。
  通常ファームウェアが設定を自動検出し、現在は40 ms（25 Hz）で動作します。
  別個体に適用するときは、OTPが元に戻せないことを理解した明示承認が別途必要です。
  GPSのUTC補正情報は12.5分周期のため、完全リセット後には位置測位よりUTC同期が遅れる場合があります。
- `GPSTow` と `GPSUTC` は測位時点、CSV先頭の `monotonic_us` はロガー採取時点です。
  `utc_us` はPPSを利用できるときに同期し、利用できないときはUART受信時点による粗い推定です。
  正確な測位時刻の評価には `GPSUTC`、`GPSTAcc`、`PPSAge` を併せて使用してください。
- ラップ・距離・予測差分は設定したコースの実測GNSS位置から計算します。
  コース未設定時に仮想ラップを生成しません。ベスト軌跡はコース情報と一緒に保存します。
  セクター分割は未対応です。
- RPMや水温はCANデータが来るまで欠測です。デモ用RPM/速度/温度は生成しません。
  AFRは元データ `AFRRaw` を残し、RPM欠測・停止・再始動後2秒は `AFR` を欠測にします。

`GNSSHz`/`IMUHz` は実受信頻度です。SDの100 Hz行には前回の有効な低速データも保持されます。
欠測はCSVでは空欄、RCPでは有効ビットを落として表します。生CANの時刻は受信処理時点であり、
バス上のエッジをハードウェアで刻印した時刻ではありません。

## USBと表示

Windowsで従来のCOM10を保持するため VID/PID=303A:4001、serial=`LOGGER-V1-TEST` を維持しています。
ファームウェア名は `logger_v1 real-sensor SD logger` です。
COM8は書き込み機兼診断UARTです。書き込み機のDTR/RTSはリセット線なので通常診断では操作しません。

RaceCaptureアプリは接続失敗後に再起動が必要になる既知の問題があります。
このVID/PIDのままではAndroid版アプリの独自USBフィルタは未対応です。
Wi-Fi/Bluetooth/携帯モデムは本構成では未使用です。

LEDは診断版のナイトライダーから状態表示に変わります。
SYS=動作点滅、ERR=異常、LOG=SD記録中、GPS=測位時点灯/未測位点滅、TLM=USB接続、
WIFI/BT=消灯、CAN=受信実績あり。

## 設定と診断API

改行区切りJSON。標準の `getVer/getCapabilities/getStatus/getMeta/s/log` と各設定取得に応答します。
`log` は通信ストリームの開始/停止であり、SDの停止ではありません。

| コマンド | 用途 |
|---|---|
| `getLoggerCfg` / `setLoggerCfg` | NC車種プロファイル、CAN抽出定義、ハブ送信設定 |
| `getTrackCfg` / `setTrackCfg` | `rad`（度）、`track.id`、`track.sf`（緯度経度）、`minLapSeconds` |
| `getConnCfg` / `setConnCfg` | 表示クライアント用 `telCfg.deviceId` 保持。ロガーから外部送信はしない |
| `flashCfg` | 設定を専用NVSへ保存 |
| `resetLap` | 現在/ベストラップをリセット |
| `saveImuCalibration` | 完全校正状態のBNO055補正保存を要求 |
| `setLogging` | SD記録の開始/停止（bool） |
| `rotateLog` | 記録を続けたまま現在ファイルを閉じ、新ファイルへ切替 |
| `listLogs` | 32件ずつファイル一覧。続きは `offset` |
| `readLog` | 閉じたログを `name`/`offset` で2048バイトずつ読取 |
| `testCanLoop` | 卓上の物理ループ専用。下記注意参照 |

未対応の設定変更は成功したふりをせずエラーを返します。
RaceCapture純正のIMU軸割当/フィルタ設定、任意CANボーレート、アクティブOBDポーリングはこの版では未対応です。

### CANマッピング

`setLoggerCfg` の `mappings` は配列全体の置換です。最大24項目。
`bus`=1/2、`id`=数値、`extended`=bool、`bit`=開始ビット、`width`=1〜32、
`little`=bool、`signed`=bool、`scale`/`offset`、`channel`=既存入力チャンネル名、`staleMs`=有効期限。
littleのbit0はbyte0のLSB、bigのbit0はbyte0のMSBです。DBCのMotorola sawtooth番号ではありません。
ECU/センサーハブのIDと数値変換が確定するまでは、推測値を初期設定に入れません。

`ncProfile` はNCロードスター用で既定false。別のECUへ流用しないでください。
`hubBroadcast` は既定false。trueにするとCAN2へ各チャンネルを送信します。
標準ID=`broadcastBase`+チャンネル番号、8バイト=`version=1,index,valid,schema低8bit,float32LE`。
既定base=0x600、5 Hz、上限500フレーム/秒。ハブ機器の既存IDと衝突しない設定が必要です。

卓上試験 `{"testCanLoop":{"confirm":"DESK_CAN1_CAN2_LOOP"}}` は、MCPの内部ループに1フレーム、
外部線に1フレームだけ0x6EFを送ります。車両へ接続中は実行禁止です。
この明示的な試験中だけ、CAN1のACKを最長1秒有効にします。終了またはタイムアウト後はlisten-onlyへ戻ります。
`getStatus.CAN.benchStatus`=2が両受信確認、3が失敗です。
生CANの `TX_REQ` は送信要求を意味し、相手側の受信確認そのものではありません。

### 任意のLua互換機能

要求上はLuaを必須にしていませんが、追加チャンネル用の限定互換機能を用意しています。
`getScriptCfg/setScriptCfg/runScript`、256バイトの順序付きページ、最大16 KiB。
`addChannel(name,rate,precision,min,max,unit)`、`getChannel`、`setChannel`、`rxCAN(bus,0)`、
`setTickRate`、`getUptime`、`onTick`。欠測getChannelはnil。
センサーハブ用入力とカスタムチャンネルのみ書込可能、GNSS/IMU/状態値は読取専用です。
512 KiBメモリ上限、初期実行50 ms/onTick 5 ms上限。危険な標準ライブラリは公開しません。
純正Lua API全体との互換はありません。既定スクリプトは空です。

## ビルド・確認

PlatformIO Core 6.1.19、espressif32 7.0.1、ESP-IDF 6.0.1。
ArduinoJson 7.4.2、esp_tinyusb 1.7.6~2 を固定。C++本体とCのLuaは別コンポーネントです。
Windowsではこの環境の `v1_test/.tools` にPlatformIO/PySerialがあります。

```text
python -m platformio run -d firmware/logger_v1
python -m platformio run -d firmware/logger_v1 -t upload --upload-port COM8
python firmware/logger_v1/tools/rcp_client.py --port COM8
python firmware/logger_v1/tools/verify_board.py --port COM8 --seconds 15 --desk-can-loop --output <新しい結果フォルダ>
```

ホスト単体テストは `tests/core_test.cpp`（C++17、ASan/UBSan付きで実行）。
SD生CANを既存解析ツールへ渡す場合は `tools/export_can.py input.csv output.csv --bus 1` を使います。
2本のバスを混ぜたり、送信要求を受信データとして解析したりしないための変換です。

## バックアップと未検証事項

書込み前の16 MiB全Flash: `artifacts/before_logger_v1_full_16MB.bin`
SHA-256: `59dc9d13d963ee50ec08653e2765dd656ffca10ff485205a2320d7cce6f343ab`。
既存NVS(0x9000〜0xefff)は保持し、新しい設定は未使用確認済み0x810000からの専用領域を使います。
バックアップには設定を含むため、公開しないでください。

実車・外部ECU/センサーハブのID・未接続の温度/AFR変換回路・実走ラップ・電源瞬断耐性は、
卓上でのビルド/試験だけでは確認できません。個別の試験結果は `artifacts` の検証記録を参照してください。
旧I2Cドライバは動作確認済み経路を維持しており、ESP-IDF 7へ移行するときは更新が必要です。

根拠: [MAX-M10M-00B データシート](https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_DataSheet_UBX-22028884.pdf)、
[高性能クロック/OTP手順](https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_IntegrationManual_UBX-22038241.pdf)、
[M10 UBXインターフェース](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf)、
[BNO055](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bno055-ds000.pdf)。
