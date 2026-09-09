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
- `HANDOFF.md`：RCP JSONプロトコルの実測仕様の詳細
- `ncec_can_spec.md`：NCEC（本番車両）のCAN通信仕様（ID・バイトマップ・デコード式・OBD2）。実装・共有用の独立ファイル
- `ncec_next_session_checklist.md`：**NCECに実車接続する前に必ず開く**。実車が無いと解けない宿題の一覧
- `podium_live_telemetry.md`：Podiumライブテレメトリ（podium.live）のプロトコル実体と流用ルート3案のまとめ
- `external_can_spec.md`：**外部CANバス（自作バス）の共通規約**。CAN ID採番・フレームフォーマット・チャンネル別レート・設定フレーム。**ハブ／表示モジュールの製作着手前に未決事項を確定させること**
- `logger_v2_policy.md`：Ver.2の構成方針（RaceCaptureアプリを本番から外す判断、CAN接続の専用表示モジュール、EcoCaptureのUNO Q内蔵、LTEテレメトリ必須化、ROCK 5Bの去就）
- `task_phaseX_breakdown.md`：各フェーズのサブタスク分解（1チャット=1タスク粒度）
- `firmware/`：ESP32（Seeed Studio XIAO ESP32C3）向けPlatformIO（ESP-IDF）プロジェクト
- `rcp_mock_device.py`：PC上で動くRCPプロトコルのモックデバイス実装
