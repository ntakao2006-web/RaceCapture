# EcoLogger — 自作の車載データロガー

サーキット走行とエコラン大会で使う、自作の車載データロガーのリポジトリです。
走行中の値（回転数・車速・水温・油温・油圧・G・位置・ラップ）を記録し、車載画面に出し、LTEでピットへ送り、走行映像に計器を焼き込んで録画します。

## いまの姿（2026-11）

| | 中身 | 状態 |
|---|---|---|
| **Ver.2（本番機）** | Arduino UNO Q（Linux＋STM32）＋自作シールド＋UPS基板。車載画面（DASH）、LTE、焼き込み録画つき | 2026-11-08のSUGO 120分耐久を走った形 |
| Ver.1 | ESP32-S3の自作基板。RaceCaptureのアプリにつないで使う | 保険機として据え置き（機能の追加は凍結） |
| カート用 試作0号 | 画面つきの一体型（ESP32-S3） | 2026-11-29の走行に向けて準備中 |

もともとは「RaceCaptureのロガー端末だけを自作のハードウェアに置き換える」計画として始まりました（Ver.1）。
リポジトリ名と`ARCHITECTURE.md`の1〜3章はその頃のままです。

## 読む人ごとの入口

### 使う人（係・ドライバー）

- 当日の手順書（A4で印刷）：[`docs/manual/sugo_day_manual_20261108.html`](docs/manual/sugo_day_manual_20261108.html)（サーキット）、[`docs/manual/ecorun_day_manual_20261024.html`](docs/manual/ecorun_day_manual_20261024.html)（エコラン）
- 困ったとき：[`docs/manual/ecologger_troubleshooting.html`](docs/manual/ecologger_troubleshooting.html)
- PCの操作メニュー：`tools/ecologger_menu/`（デスクトップの「EcoLogger Ver.2」）
- 走行ログ・動画の回収：`tools/video_collect/Collect-Video.cmd`

### チーム

- ハードウェアとソフトウェアの構成図：[`v2_hardware_overview.html`](v2_hardware_overview.html)
- 仕様書（誰に・どの場面で・何をできるようにするか）：[`SPEC.md`](SPEC.md)

### 開発者

- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — 現在地とロードマップ（このリポジトリの一次情報源）
- 作業の分解：直下の`task_*_breakdown.md`（一覧は`ARCHITECTURE.md` 5章の冒頭「タスクの置き場所」）
- 資料1本ごとの案内：[`docs/README.md`](docs/README.md)、道具ごとの案内：[`tools/README.md`](tools/README.md)
- 各フォルダーの`README.md`

## フォルダー

| 場所 | 中身 |
|---|---|
| `RaceCapture-UNOQ/` | Ver.2のLinux側（車載画面DASH・見守り役など） |
| `EcoCapture-Web/` | Ver.2の上で動くEcoCapture（設定・ログ管理・LTE送信） |
| `tools/` | PCで使う道具（操作メニュー・回収・解析・動画）と、本体の録画のソフト`tools/unoq_overlay_enc/` |
| `tools/dev/` | 開発・調べもの用の道具 |
| `firmware/` | Ver.1のファームウェア（PlatformIO / ESP-IDF） |
| `android-logger/` | スマホのアプリ（エコランの車載画面） |
| `circuit/` | 回路・基板（KiCad） |
| `docs/design/` | 仕様・設計 |
| `docs/manual/` | 手順書 |
| `docs/research/` | 調査 |
| `docs/share/` | 人に渡したメモと、その回答 |
| `ecorun/` | エコランチームの用事（記録表） |
| `outputs/` | 確かめの記録（日付つき） |
| `archive/` | 閉じた系統の資料（ダッシュカム・通話など） |

走行ログ（`drive_logs/`）は位置情報を含むため、リポジトリには入れていません。
