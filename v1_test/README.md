# logger_v1 独立実機診断

`circuit/logger_v1` と製品ファームウェアを変更せず、ESP32-S3基板を実機診断するためのESP-IDFプロジェクトです。

## 実施する試験

- ESP32-S3 CPU 240 MHz、Octal PSRAM 80 MHz、デュアルコア連続演算負荷
- 内蔵温度センサー（20～100°Cレンジ）監視、85°Cで負荷を安全停止
- microSD：現行回路のSDMMC 4-bit配線、40 MHz、8 MiB書込・読込・全バイト照合・一時ファイル削除
- GNSS：GPIO15/16、UBX-MON-VERを9600/38400/115200 baudで照会、RESET_N制御とアイドルレベル診断
- CAN1：ESP32 TWAI + ATA6561、500 kbit/s、No-Ack自己受信
- CAN2：MCP25625のSPIレジスタ疎通、20 MHz水晶用500 kbit/s設定、内部ループバック
- CAN外部バス：J4/J5接続時、CAN1→CAN2とCAN2→CAN1を各32フレーム送信し、ACK・ID・全データ・エラーカウンタを検査
- 74HC595：D4～D11ナイトライダー継続表示
- USB-OTG：TinyUSB CDCとRaceCapture互換JSON応答
- USBダミーテレメトリー：`RPM`、`Speed`、`WaterTemp`、`OilPress`、`Lat`、`Lon`を時間変化させ、RaceCapture Dashboardへ送信

IMUは未実装のためアクセスしません。CAN外部バス試験ではJ4/J5の同番号を接続します（pin 1=+5V、pin 2=CANH、pin 3=CANL、pin 4=GND）。車両側との実バス通信は別試験です。GNSSの通信試験にアンテナは不要ですが、測位試験にはアンテナが必要です。

## 現行回路から採用したピン

| 機能 | GPIO |
|---|---|
| SD CLK / CMD / D0 / D1 / D2 / D3 | 11 / 10 / 12 / 13 / 14 / 21 |
| GNSS RX / TX / RESET_N | 15 / 16 / 9 |
| CAN1 RX / TX | 1 / 2 |
| CAN2 SCK / MOSI / MISO / CS / RESET | 39 / 40 / 41 / 42 / 4 |
| 74HC595 SER / SRCLK / RCLK | 40 / 39 / 45 |
| OTG VBUS sense / ROLE / OC_N | 6 / 48 / 38 |

## ビルド・書き込み

```powershell
$env:PYTHONPATH=(Resolve-Path '.tools').Path
& 'C:\Users\lintaroh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m platformio run -e logger-v1-board-test
& 'C:\Users\lintaroh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m platformio run -e logger-v1-board-test -t upload --upload-port COM8
```

UART0ログはA105のCOM8/115200 baudです。ネイティブUSB CDCはRaceCapture App専用です。

RaceCapture Appで確認するときはDashboardを開き、Raw Channels表示を選びます。`RPM`、`Speed`などが連続して変化します。デバイス名には実測値ではないことを示す`simulated telemetry`を表示します。
