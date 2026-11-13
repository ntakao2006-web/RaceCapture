# Lintarohさんへ：リポジトリの名前と置き場所が変わりました（2026-11-13）

ソフトの中身の話ではなく、リポジトリの使い方の連絡です。回路・基板・PICのファームには手を入れていません。

## 1. 手元でしてほしいこと

### 1-1. リモートのURLを直す

リポジトリ名を `RaceCapture` から `EcoLogger` へ変えました。古いURLは転送されるので今のままでも動きますが、直しておいてください。

```bash
git remote set-url origin https://github.com/ntakao2006-web/EcoLogger.git
```

sshでつないでいる場合は `git@github.com:ntakao2006-web/EcoLogger.git` です。手元のフォルダー名は変えなくて構いません。

### 1-2. 最新を取り込む

資料を約80本、フォルダーへ移しました。**コミットしていない変更があれば、先にコミットするか退避してから**取り込んでください。

```bash
git status --short
```

```bash
git pull
```

移したファイルを手元で書き換えていた場合、gitが移動先へ当ててくれるはずですが、ぶつかったら知らせてください。

### 1-3. Codexに読ませるもの

直下に `AGENTS.md` を置きました。Codex向けの入口で、決まりの本体は `CLAUDE.md` です。作業の最初に `AGENTS.md` を読ませてください。

## 2. どこへ移したか

| 前の場所（直下） | 今の場所 |
|---|---|
| `lintaroh_share_*.md`・`lintaroh_answer_*.md` | `docs/share/` |
| `hardware_share_*.md`・`hardware_ans_*.md`・`hardware_meeting_agenda.md` | `docs/share/` |
| `hardware_interface_spec.md`・`logger_v2_channel_and_sensor_spec.md`・`sensorhub_defi_tap_design.md`・`brake_pressure_sensor_ncec.md`・`ncec_can_spec.md`・`kart_gnss_carrier_design.md`・`kart_parts_list_20261028.md` | `docs/design/` |
| 当日手順書・実車でのCAN測定の手順 | `docs/manual/` |
| 調査の資料（`LOGGER_V2_UNOQ_REPORT.md`・Defiのセンサー・カート・LTEなど） | `docs/research/` |
| `tools/voice_gate`・`tools/discord_bridge` | `archive/voice/` |
| `tools/lte_antenna`・`tools/unoq_spi_sd_test` ほか調べもの用 | `tools/dev/` |

**直下のままのもの**（ソフトのコメントから名指しされているため）：`lintaroh_answer_20261101_defi_volt.md`、`sensorhub_generic_spec.md`、`hardware_share_20261004_podium.md`、`unoq_video_to_shield_sd_study.md`。

**動かしていないもの**：`circuit/`、`datasheet/`、`firmware/`、`pic18f26q84_blink.X/`、`outputs/`、`EcoCapture-Web/`、`RaceCapture-UNOQ/`。

資料1本ごとの案内は `docs/README.md` にあります。

## 3. これから書くときの置き場所

- 回答・メモ：`docs/share/lintaroh_answer_<日付>_<題>.md`（これまでの直下ではなく）
- 回路・基板：`circuit/`（今までどおり）
- 確かめの記録：`outputs/<名前>_<日付>/`（今までどおり）

## 4. 知っておいてほしい方針

- **Ver.2の仕様書 `SPEC.md` を作りました。** 誰に・どの場面で・何をできるようにするかをまとめたものです。回路への新しい依頼は入っていません。
- **RaceCaptureから離れます。** 公式のRaceCaptureアプリ、値をRCPの形に変える部品（`RaceCapture-UNOQ/rcp_bridge.py` など）、公式のPodiumへ直接送る道を、Ver.2の本体から外す予定です。作業の一覧は `task_spec_rebuild_breakdown.md` のSP-9です。
  - 外す対象に、Lintarohさんが最初に作ったものが含まれます（`RaceCapture-UNOQ/` の公式アプリまわり）。仕分けは `docs/design/unoq_software_inventory.md` にあります。**残しておきたいもの・外すと困るものがあれば教えてください。**
  - 本体に手を入れるのは、展示用のファームから元へ戻したあとです。展示の間は何も変えません。
- **売るとしたらVer.2の系統だけ**、という前提で、Ver.1のファームと公式ファーム（GPL v3）の関係をこれから整理します。回路図・基板のデータの扱い（公開のままでよいか、ライセンスをどうするか）は、決める前に相談します。

## 5. 返事がほしいこと

1. 手元に、まだpushしていない変更はありますか（移した資料とぶつからないか確かめたい）。
2. `RaceCapture-UNOQ/` の公式アプリまわりで、残しておきたいものはありますか。
3. 回路図・基板のデータを公開リポジトリに置き続けることについて、希望はありますか。
