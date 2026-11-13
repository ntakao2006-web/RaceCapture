# AGENTS.md

Codexなど、Claude以外のエージェントでこのリポジトリを触るときの入口。
**決まりは`CLAUDE.md`が正**で、ここには入口と、違う所だけを書く（同じ内容を二重に持たない）。

## 最初に読むもの

1. `CLAUDE.md`：運用の決まりと、フォルダーの案内
2. `ARCHITECTURE.md`：冒頭の「いまの姿」、4章（現在地）、5章冒頭（作業の系統の一覧）、8章（更新の決まり）
3. `SPEC.md`：Ver.2が誰に何をできるようにするか。道具や画面を足す・直す・やめるときは、まずここの要求に当てはめる
4. 資料を探すときは`docs/README.md`、道具を探すときは`tools/README.md`

## 守ること（`CLAUDE.md`から、とくに大事なもの）

- **公開リポジトリ**。位置情報・車台番号・合言葉・鍵・自宅のサーバーのURL・個人が分かる情報を入れない。コミットの前に中身を見る
- `ARCHITECTURE.md`の4章は**追記だけ**。既存の記述を消さない・書き換えない。試行錯誤の過程は書かず結論だけ
- 進み具合は分解ファイル（`task_*_breakdown.md`）のチェックで持つ。同じ内容をほかの資料へ書き写さない
- 消さない。要らなく見えるものは`archive/`へ移す
- `drive_logs/`は`.gitignore`のまま触らない
- チームのリポジトリ（GitHub組織`TMCIT-Ecorun`）は読むだけ

## 置き場所（2026-11-13に整理した）

| もの | 置き場所 |
|---|---|
| 人に渡すメモ・その回答 | `docs/share/`（`lintaroh_share_*`・`lintaroh_answer_*`・`hardware_share_*`・`hardware_ans_*`。**新しいものもここ**） |
| 仕様・設計 | `docs/design/` |
| 手順書 | `docs/manual/` |
| 調査 | `docs/research/` |
| 回路・基板（KiCad） | `circuit/` |
| 確かめの記録 | `outputs/<名前>_<日付>/` |
| 開発・調べもの用の道具 | `tools/dev/` |

ソフトのコメントから名指しされている資料は直下のまま（`lintaroh_answer_20261101_defi_volt.md`・`sensorhub_generic_spec.md`・`hardware_share_20261004_podium.md` など）。

## 担当の分かれ目

- 回路・基板・電源・PICセンサーハブのファーム：Lintarohさん
- UNO QのLinux側のソフト・EcoCapture・STM32のファーム・PCの道具：リポジトリの持ち主の側（Claudeで作業）
- 相手の担当の所を変えるときは、先に相談する。**本体（UNO Q）と自宅のサーバーへ入れる作業は、持ち主の了承を取ってから**

## Claudeとの違い

- `CLAUDE.md`の「コミットしたら同時にpushする（確認不要）」は、持ち主がClaudeに与えている許可。ほかのエージェントでは、**作業している人の指示に従う**
- コミットの前に`git pull`で最新を取り込む（両方の側から同じ日に`ARCHITECTURE.md`へ追記することがある。ぶつかったら両方の追記を残す）

## いま進んでいること（2026-11-13）

- リポジトリ名を`RaceCapture`から`EcoLogger`へ変えた。古いURLは転送されるが、リモートは直しておく：
  `git remote set-url origin https://github.com/ntakao2006-web/EcoLogger.git`
- Ver.2を「RaceCaptureから離れる」方向で作り直している（`task_spec_rebuild_breakdown.md`のSP-9）。公式アプリ・RCPに変える部品（`RaceCapture-UNOQ/rcp_bridge.py`など）・公式のPodiumへ直接送る道は外す予定。**これらに手を入れる前に持ち主へ確かめる**
