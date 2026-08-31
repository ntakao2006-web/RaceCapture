# logger_v1 統合ファームウェアの要件・検証表

基準: ユーザーがpullした `cf1c711` (2026-08-31確認)、ARCHITECTURE.md、
hardware_interface_spec.md、HANDOFF.md、task_phase1/2/5/6_breakdown.md、
OBD2_SURVEY.md、実回路 circuit/logger_v1/logger_v1.net、および当日のv1_test合格版。
この実装の完了を示すものではなく、以下の各項目に実装と証拠が必要です。
回路とv1_testは変更しません。古いLSM6DSV16X/UART-IMU/DevKitピンは採用しません。

| 要件 | 実装・検証の完了条件 |
|---|---|
| 実装基板 | ESP32-S3 N16R8、16MB Flash/8MB PSRAM、実ネットリスト一致 |
| IMU | BNO055 I2C GPIO17/18・reset7。100Hz、姿勢/角速度/生加速度/重力/線形加速度。定数0.3の盲目的加算なし |
| IMU校正 | 校正状態を公開、校正レジスタ保存/復元。静止確認なしの自動ゼロ補正禁止 |
| GNSS | MAX-M10M UART RX15/TX16、起動時設定、連続PVT、UTC/精度/欠測管理、PPSは入力のみ |
| 車載CAN | ATA6561/TWAI RX1/TX2、500k、既定listen-only。無断のOBD送信なし |
| ハブCAN | MCP25625 SPI39/40/41/42 reset4 IRQ47、20MHz水晶、500k。GPIO/パルス/センサ値はCAN経由 |
| LED共存 | 74HC595はCAN2と同一SPIバスで直列化し、ラッチ45だけを制御。SYS/ERR/LOG/GPS/TLM/WIFI/BT/CAN |
| CAN記録 | 11/29bit、RTR、バス番号、受信時刻us、全生フレーム、取りこぼしカウンタ |
| 車種/ハブ拡張 | 車種固有式を別車両へ適用しない。設定可能なビット抽出・較正とLuaで未確定IDを扱う |
| SD | 起動時自動記録、100Hz全チャンネルCSV+生CAN、セッション分割、単調時刻+UTC、500ms fsync |
| SD異常 | 満杯/未挿入/書込失敗/キュー欠落を可視化、自動フォーマット/既存ログ削除禁止、復帰可能 |
| USB/RCP | COM10の互換識別、設定読み書き・NVS保存、可変メタデータ/32ch超ビットマップ、log/s、USB断でもSD継続 |
| ラップ | 実GPSのみ、トラック設定・通過判定・距離/ラップ/予測、異常短周回拒否、トラック紐付け保存・リセット |
| 任意Lua互換機能（必須要件外） | add/get/setChannel、rxCAN、onTick、実スクリプトのページ転送・保存・再実行 |
| 任意Luaの保護 | メモリ上限・命令/時間上限、危険な標準ライブラリ非公開、異常スクリプトでもセンサ/SD継続 |
| 外部CAN出力 | 計算値をハブCANにのみ送信。CAN1へ転送しない。ID衝突を設定で避ける |
| AFR | 元値と有効値を区別し、RPM欠測/停止および再始動後2秒をマスク |
| 未実装外部ハード | EGT/CHT/AFR変換IC・ECU/ハブ側IDは未確定。偽の値で動作済みにしない |
| 書込・確認 | 現行Flashバックアップ、ビルド/テスト、書込み照合、起動/USB/IMU/GNSS/CAN/SD読戻し証拠 |

外部CANが現在ループ線で車載CANと接続されている点を明確に区別し、
試験フレームの出力は卓上試験として明示したときだけにします。
実走行・電源瞬断・未接続センサの確認を、卓上試験の合格で代用しません。
