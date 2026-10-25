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
- **コミットしたら同時に`git push`もする（都度確認不要）**。このリポジトリはプライベートだが
  チームメンバーへの進捗共有に使われているため、コミットとpushをセットで行う運用とする。
  ただし、区切りがついておらずコミットしていない作業途中の変更を無理にpushする必要はない
  （コミットした分だけをpushすればよい）。
- push対象に個人を特定しうる情報（車台番号(VIN)等）を含めない。コミット前に必ず内容を確認する。

## よく使うコマンド
- ファームウェアのビルド：`cd firmware && python -m platformio run`
- RaceCaptureモックデバイスの起動（実機なしでのプロトコル検証用）：`python rcp_mock_device.py`

## ファイル構成
- `ARCHITECTURE.md`：プロジェクト全体のマスターファイル
- `hardware_interface_spec.md`：電気・回路系担当の友人と認識合わせをするための入出力インターフェース仕様書
- `hardware_meeting_agenda.md`：友人とのミーティングをどの順番で進めるかの道しるべ（`hardware_interface_spec.md`各章への案内役）
- `hardware_share_YYYYMMDD.md`：回路担当へ渡すための日付つきメモ。**最新は`hardware_share_20260921.md`**で、これは差分メモではなく「いま未回答の依頼・質問を全部1枚に集約したもの」（それ以前の資料はどれも未送だったため）。**2026-09-21に送付済み・回答受領済み**で、各「回答欄」に結論を転記してある。`hardware_share_20260915.md`はバス負荷・CAN周期・4輪特定・基板まわりの訂正をまとめたもので、20260921版の5-2章から判断材料として参照している。`hardware_share_20261004.md`はLTEアンテナ（市販貼り付け品FXUB63＋SMA接続）の発注依頼だけをまとめた単発メモ。`hardware_share_20261004_podium.md`はV2のPodium送信を実装する回路担当向けの**次世代Podiumの確定版プロトコル**（2026-10-04実測。認証形式が旧資料から変わっている）
- `hardware_ans_YYYYMMDD.md`：**回路担当からの回答の一次資料**。最新は`hardware_ans_20260921.md`。回答原文をそのまま残し、確定したこと／確定しなかったこと・**こちら側の記述が訂正された箇所**・**この回答で新たに発生したこちらの宿題**を整理してある。ハード側の話が出たら`hardware_share_*`とセットで読む
- `HANDOFF.md`：RCP JSONプロトコルの実測仕様の詳細
- `ncec_can_spec.md`：NCEC（本番車両）のCAN通信仕様（ID・バイトマップ・デコード式・OBD2）。実装・共有用の独立ファイル
- `sensorhub_defi_tap_design.md`：既設Defiの油温・油圧センサーを読むセンサーハブ基板の設計（v2：油温はサーミスタを直接測りデジタルポテンショメータでDefiへ再現、ピン単位の接続表・LCSC品番つき部品表・換算式・校正手順）。使用サーミスタの特性は`datasheet/defi_temp_sensor_rt.csv`
- `sensorhub_generic_spec.md`：**汎用センサーハブ**（アナログ8ch・デジタル4ch・出力2ch、PIC＋外部CAN数珠繋ぎ）のLintarohさん向け要求仕様。Defi傍受基板とは別物で併用する。**外部CANバス全体のID割り当て表（5章）と、設定をロガー側に置く運用ルール（6章）もここが正**
- `ecorun_team_systems.md`：エコランチーム（GitHub組織`TMCIT-Ecorun`）の既存システム（フロントパネル・通話試作・ダッシュボード）とEcoLoggerの関係、通話・中継サーバーの構成方針。**チーム側リポジトリは読むだけで変更しない**（例外：`ecorun-logger-server`はMaruo.Sさんの依頼でブランチ＋PRで変更する。2026-10-14〜）
- `unoq_video_check_procedure.md`：UNO Qの映像確認（V-1〜V-5）の手順と実測結果。5-6章に走行映像へのプロット焼き込みの模擬試験（試験プログラムは`tools/unoq_overlay_enc/`）
- `unoq_video_to_shield_sd_study.md`：焼き込み映像をシールド側SDへ保存できるか（E-6）の調査。Linux→STM32の内部SPI、ビットレートと画質の実測、SD側のボトルネック
- `lintaroh_share_YYYYMMDD.md`：Lintarohさんへの共有メモ。**Lintarohさんは回路担当と同一人物**で、回路・UNO Qのソフト・STM32ファームのすべてを担当している（`hardware_share_*`・`hardware_ans_*`の「回路担当」も同じ人）。最新は`lintaroh_share_20261009_2.md`（稼働中ソースの確定、CAN2のACKとループ監視の導入、**内部リセット後にLinuxとの通信路が戻らない件の相談**、Linux側の監視役`mcu-supervisor.py`、RAMの実際の限界）。その前が`lintaroh_share_20261009.md`（ファーム書き込みでLinux側UARTが固まる件、UNO Q上でしたこと、ソースの食い違い、E-6の結果と相談）と`lintaroh_share_20261009_power.md`（カメラ・モニターの機材構成案、UPSモジュールとの組み合わせで確認したいこと）、`lintaroh_share_20261010_sensorhub.md`（汎用センサーハブの仕様の要点と判断してほしい8項目。本体は`sensorhub_generic_spec.md`）、`lintaroh_share_20261013_oiltemp.md`（エコラン大会向けにユニバーサル基板版ハブで油温を読むための確認事項）、`lintaroh_share_20261015_audio.md`（ドライバーの音声を音声基板からUSBオーディオへ変える相談、未送）、`lintaroh_share_20261018_unoq_damage.md`（今のUNO Qの裏面のチップ部品が脱落している件と、内蔵Bluetoothが固まった件、買い替えの相談。未送・写真を貼る欄あり）
- `maruo_share_YYYYMMDD_*.md`：Maruo.Sさん（チームの通話サーバー`ecorun-logger-server`の作者）への相談。`maruo_share_20261015_discord.md`はピットの通話をDiscordに戻す相談（未送）、`maruo_share_20261025_dashboard.md`はピット用ダッシュボードを主サーバーでも5Bと完全に同じに立てるための連絡（未送。10/24版`maruo_share_20261024_grafana.md`の差し替え）、`maruo_share_20261025_cluster.md`は先輩のサーバー→5Bの複製が約21時間止まっていた件と、5Bの再起動後に複製の接続・Ver.2の接続が先輩側から切られた件の報告と質問（未送）、`maruo_share_20261025_podium_rows.md`は先輩のサーバーの「skipping Podium sample…」の警告の原因（ロガーはPodium本来の詰めた形で送り、サーバーのデコードが固定長を前提にしている）と5B側ログの照合結果（未送）、`maruo_share_20261017_rock5b.md`は大会用の予備サーバーのお願いと、先輩がPR#1へ入れた実装（`4482ede`）にロガーから合わせるための相談（地図に位置を出す方法・ロガー向け音声。2026-10-18送付済み）
- `maruo_answer_YYYYMMDD.md`：**Maruo.Sさんからの回答の一次資料**。最新は`maruo_answer_20261025.md`（ダッシュボード引き継ぎの確認事項への回答：入口は先輩が手で用意済み、ポートも先輩が直した、画面の更新はまだ。外から見た先輩のサーバーの状態と5Bとの違い）。その前が`maruo_answer_20261018.md`（予備は先輩宅のラックサーバー、分散構成・Grafana不採用の方向、GitHub上の`4482ede`ではロガーの位置・音声がまだ出ないことの確認、こちらの宿題）
- `ogata_share_YYYYMMDD_*.md`：緒方さん（GitHub `ktrogt`、走行戦略ツールを作っているチームメンバー）への返信。`ogata_share_20261024_issues_reply.md`は緒方さんがChatGPTで出した「既存の不具合と注意点」（`existing-issues.md`）への確認結果と、ブリッジのWebSocketの読み口（`kind=clock`）の説明
- `lintaroh_answer_YYYYMMDD.md`：**Lintarohさんからの回答の一次資料**（本人がリポジトリへ直接push）。最新は`lintaroh_answer_20261009.md`（ファーム更新手順を共通の`EcoCapture-Web/flash-mcu.sh`へ統一、稼働中ファームの正しいソースは未確定、**STM32のRAMは現状でも映像用リングを足す余地が無い**、E-6の段階的な統合手順と本番採用の判定条件）
- `enclosure_ecorun_20261024.md`：エコラン大会用の3Dプリント筐体の設計材料（Ver.2・Ver.1の基板寸法と縁の部品位置、STEPの場所、要件、未確定事項）。耐衝撃の考え方は`case_shock_design.md`
- `ecorun_day_manual_20261024.html`：エコラン大会の当日用A4手順書（取付・記録の確認・コースウォーク・停止・回収・困ったとき）。ブラウザでA4縦に印刷する。回収は`tools/collect_logs/Collect-Logs.cmd`
- `er12_mpp_soc_harness_bom.md`：EV二輪のMPP充電器からSOCを読む測定用ハーネスの部品表（秋月版・千石版）と結線表（ER-12）
- `server_deploy_grafana_x86.md`：自宅ROCK 5Bのピット用Grafana（EcoRun Live）・「周回・時間」のページ・地図を、別のLinuxサーバー（主サーバーにする先輩のラックサーバー）で**5Bと同じに立てる**ための引き継ぎ資料（2026-10-25 10時の5Bの実物と照合した版）。画面の構成・ブリッジがしていること・10/18以降のUI変更・5Bの設定との対応表・手順。実際のファイルは`tools/home_telemetry/deploy/`（VictoriaMetrics・Grafana・ブリッジのDocker Compose）。チームの`latest`がJSON Linesを書くのでサーバー本体の変更は不要。先輩へ送る文面は`maruo_share_20261025_dashboard.md`
- `ncec_next_session_checklist.md`：**NCECに実車接続する前に必ず開く**。実車が無いと解けない宿題の一覧
- `task_phaseX_breakdown.md`：各フェーズのサブタスク分解（1チャット=1タスク粒度）
- `firmware/`：ESP32（Seeed Studio XIAO ESP32C3）向けPlatformIO（ESP-IDF）プロジェクト
- `rcp_mock_device.py`：PC上で動くRCPプロトコルのモックデバイス実装
- `RaceCapture-UNOQ/`：Ver.2ロガー（Arduino UNO Q）のLinux側一式（RCP変換・公式アプリ表示・HDMI表示・障害記録・検証スクリプト）。**主にLintarohさんが更新している**。入口は`README.md`
- `EcoCapture-Web/`：UNO Q上のEcoCapture（設定・ログ管理・Podium送信`podium.py`）
- `drive_logs/`：走行ログ（SDの`EL*.BIN`とデコード結果）。位置情報を含むため`.gitignore`済みでリポジトリに入れない
