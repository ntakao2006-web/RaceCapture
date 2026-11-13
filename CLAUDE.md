# CLAUDE.md

## このリポジトリについて
RaceCapture互換の車載データロガーを自作するプロジェクト。詳細・現状・ロードマップは
すべて`ARCHITECTURE.md`に集約されている（このリポジトリの唯一の一次情報源）。

## 最初にすること（必須）
作業に入る前に、必ず以下を確認する。
- `ARCHITECTURE.md`の「4. 現状ステータス」「5. 開発ロードマップ」
- `ARCHITECTURE.md`「8. Claude運用ガイド」に記載の運用ルール
  （更新ルール、タスク分割の目安、フェーズ開始時の自動タスク分解ルール等）をすべて遵守する

## タスクの進め方
- タスクの系統（Phase・`ER-`・`SG-`・`KT-`・`DC-`等）と、それぞれの分解ファイル・状態の一覧は
  `ARCHITECTURE.md` 5章冒頭「タスクの置き場所」が正。イベント用の分解ファイルはイベント後にそこへ書いた手順で閉じる
- ユーザーから`1-1-3`のようなタスクIDのみを指定された場合、対応する
  `task_phaseX_breakdown.md`（例：`task_phase1_breakdown.md`）を参照し、その説明に沿って作業する
- 該当フェーズの分解ファイルがまだ存在しない場合は、ARCHITECTURE.md 8章の
  「フェーズ開始時の自動タスク分解ルール」に従い、着手前にそのフェーズを分解してから作業を始める
- タスク完了時は、対応する`task_phaseX_breakdown.md`のチェックボックスを更新する
- ARCHITECTURE.mdを更新する際は、8章「更新ルール（事故防止）」に厳密に従う
  （4章は追記のみ・既存記述を消さない、試行錯誤ログは書かない、更新後は変更箇所を要約する）

## コミットの粒度
- タスク（`task_phaseX_breakdown.md`の`X-Y-Z`単位）が完了し、対応するチェックボックス・
  ARCHITECTURE.mdの更新まで終わったら、その時点でその変更をコミットする。
  ユーザーへ都度確認せず自動的にコミットしてよい。
- コミットメッセージは`PhaseX-Y-Z完了: 概要`の形式（既存コミットのスタイルに合わせる）。
- **コミットしたら同時に`git push`もする（都度確認不要）**。このリポジトリは**公開（public）**で、
  チームメンバーへの進捗共有に使われているため、コミットとpushをセットで行う運用とする。
  ただし、区切りがついておらずコミットしていない作業途中の変更を無理にpushする必要はない
  （コミットした分だけをpushすればよい）。
- push対象に個人を特定しうる情報（車台番号(VIN)等）を含めない。コミット前に必ず内容を確認する。

## よく使うコマンド
- ファームウェアのビルド：`cd firmware && python -m platformio run`
- RaceCaptureモックデバイスの起動（実機なしでのプロトコル検証用）：`python rcp_mock_device.py`

## ファイル構成

資料1本ごとの説明は`docs/README.md`、道具ごとの説明は`tools/README.md`にある（2026-11-13にここから移した）。
**資料の話が出たら`docs/README.md`、道具の話が出たら`tools/README.md`を先に開く。** 足した・変えたときもそちらを直し、ここはフォルダーの案内だけにする。

### 直下

- `ARCHITECTURE.md`：プロジェクト全体のマスターファイル。現在地（4章。頭に「いまの姿」の要約）とロードマップ（5章）
- `AGENTS.md`：Codexなど、Claude以外のエージェント向けの入口（Lintarohさんの側）。決まりの本体はこの`CLAUDE.md`で、**決まりを変えたら`AGENTS.md`の「守ること」と食い違わないか見る**
- `SPEC.md`：Ver.2の仕様書（下書き）。**道具や画面を足す・直す・やめるときは、まずここの要求に当てはめる**
- `task_*_breakdown.md`：作業の分解（Phase・`SP-`・`SG-`・`KT-`・`ER-`・`DC-`）。一覧は`ARCHITECTURE.md` 5章冒頭。`SP-x`のうち**本体に入れる分は展示用のファームから戻したあと、自宅のサーバーに入れる分はユーザーの了承のあと**
- `v2_hardware_overview.html`：Ver.2のハードウェアとソフトウェアの構成図（チームに見せる用）。**構成やソフトの役割を変えたらここも直す。公開リポジトリなので5BのURLは書かない**
- `v2_firmware_backup_20261110.md`：Ver.2のファームの控えと戻し方。**展示のあとで元へ戻すときはまずこれを開く**
- `ncec_next_session_checklist.md`：**NCECに実車接続する前に必ず開く**
- `unoq_video_check_procedure.md`：録画・焼き込み・回収の手順と実測（5章が長い。章ごとの案内は`docs/README.md`）
- `HANDOFF.md`（RCPのプロトコル）、`sensorhub_generic_spec.md`（汎用センサーハブ。**外部CANのID割り当て表もここが正**）、`server_deploy_grafana_x86.md`、`unoq_video_to_shield_sd_study.md`、`hardware_share_20261004_podium.md`、`lintaroh_answer_20261101_defi_volt.md`：ソフトのコメントから名指しされているので直下のまま
- `rcp_mock_device.py`：PC上で動くRCPプロトコルのモックデバイス実装。直下のほかのスクリプト・`.json`・`.log`はVer.1の頃のCAN調査

### フォルダー

- `docs/share/`：人に渡したメモ（`hardware_share_*`・`lintaroh_share_*`・`maruo_share_*`・`ogata_share_*`）と、その回答の一次資料（`hardware_ans_*`・`lintaroh_answer_*`・`maruo_answer_*`）。**新しいメモ・回答もここへ置く。ハード側の話が出たらメモと回答をセットで読む**
  - **Lintarohさんは回路担当と同一人物**（回路・基板・電源）。**UNO QのLinux側のソフト・EcoCapture・STM32のファームは基本こちらで作るので、ソフトを変えても報告用のメモは作らない**（記録は分解ファイルと`ARCHITECTURE.md`だけ）
  - エコランチーム（GitHub組織`TMCIT-Ecorun`）の**リポジトリは読むだけで変更しない**（例外：`ecorun-logger-server`はMaruo.Sさんの依頼でブランチ＋PR）。詳しくは`docs/design/ecorun_team_systems.md`
- `docs/design/`：仕様・設計（`ncec_can_spec.md`＝NCECのCAN、`hardware_interface_spec.md`、センサー・筐体・カートの部品と基板、本体のソフトの仕分け一覧）
- `docs/manual/`：手順書（SUGO・エコランの当日用A4、実車でのCAN測定の手順）
- `docs/research/`：調査（OBD2・車両CAN、Ver.2の構想`LOGGER_V2_UNOQ_REPORT.md`、LTE、Podium、Defiのセンサー、カート）
- `tools/`：PCで使う道具と、本体の録画のソフト`tools/unoq_overlay_enc/`（本体へ入れるスクリプトがパスを見ているので動かさない）
  - 入口は`tools/ecologger_menu/`（操作メニュー）と`tools/video_collect/Collect-Video.cmd`（回収）。**新しい`.cmd`を作ったら操作メニューの`TOOL_GROUPS`（設定・調べものの窓）に足す。ふだんの窓へは足さない**
  - PC側の合言葉・記録の置き場は`%USERPROFILE%\.ecologger`。**`%LOCALAPPDATA%`はClaudeのアプリから動かしたときだけ振り替えられるので使わない**
  - `tools/dev/`：開発・調べもの用
- `firmware/`：ESP32（Seeed Studio XIAO ESP32C3）向けPlatformIO（ESP-IDF）プロジェクト
- `RaceCapture-UNOQ/`：Ver.2ロガー（Arduino UNO Q）のLinux側一式（RCP変換・公式アプリ表示・HDMI表示・障害記録・検証スクリプト）。最初はLintarohさんが作ったもので、今は基本こちらで更新する。入口は`README.md`。SUGO用の車載画面**EcoCapture DASH**（`ecocapture_dash.py`・`dash_model.py`、SG-2-6）もここ
- `EcoCapture-Web/`：UNO Q上のEcoCapture（設定・ログ管理・Podium送信`podium.py`）
- `android-logger/`：スマホのアプリ（エコランの車載画面、予備の車載画面「サーキット」）
- `circuit/`：回路・基板（KiCad）。`datasheet/`：部品の資料
- `ecorun/`：エコランチームの用事（記録表）
- `outputs/`：確かめの記録（`<名前>_<日付>/`）
- `archive/`：閉じた系統の資料（ダッシュカム・通話・Phase 0）。消さずにここへ移す
- `drive_logs/`：走行ログ（SDの`EL*.BIN`とデコード結果）。位置情報を含むため`.gitignore`済みでリポジトリに入れない
