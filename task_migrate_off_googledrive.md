# タスク: 作業環境を Google Drive からローカルドライブへ移行

> 親ドキュメント: [`ARCHITECTURE.md`](ARCHITECTURE.md)(プロジェクト全体のマスター。4章「現状ステータス」にこの移行の開始を追記済み)
> 実行手順(サブタスク・チェックリスト): [`task_migrate_off_googledrive_checklist.md`](task_migrate_off_googledrive_checklist.md)

## 背景・目的

現在の作業フォルダ `G:\マイドライブ\RaceCapture` は Google Drive for Desktop の同期対象フォルダ。
今後 Git を本格的に使う運用に切り替えるにあたり、クラウド同期フォルダ上での Git 運用は
以下の理由で不安定になりやすいため、完全にローカルなドライブへ作業環境を移す。

### なぜ Google Drive 上の Git が不安定になりうるか
- Git は `.git/` 配下に大量の小さいファイル(index、ロックファイル `index.lock`、
  loose object、参照ファイル等)を高頻度で作成・書き換え・リネームする。
- Google Drive 等のクラウド同期クライアントはファイルシステムをリアルタイム監視しており、
  この頻繁な変更と競合しやすい。具体的に起きうる問題:
  - `.git/index.lock` の取得に失敗し `Unable to create '.git/index.lock': File exists` 等で
    git コマンドが失敗する
  - 同期処理中のファイルを git が書き換えようとして「別のプロセスが使用中です」エラーになる
  - 同期の「競合コピー (conflicted copy)」ファイルが誤って作られ、リポジトリの整合性が壊れる
  - ストリーミングモード(オンデマンドダウンロード)だと、ファイルの実体がローカルに
    存在しないタイミングがあり、git が前提とするファイルシステムのアトミック性
    (rename等)が保証されない
  - `.git/objects` 以下の大量の小ファイルまで同期監視対象になり、Drive自体も重くなる
- これらは「たまに失敗する」程度で気づきにくく、後になってリポジトリ破損として
  表面化しやすいため、早い段階でローカルドライブに移すのが安全。

## この移行タスクの位置づけ

- **`ARCHITECTURE.md`**: プロジェクト全体のマスター。移行の決定事項はここに1〜3行で反映する。
- **`HANDOFF.md`**: RaceCapture モックデバイスのプロトコル解析・接続確立までの詳細な作業ログ。
  内容はこのファイルとは独立しており、移行後もそのまま持っていく(移行がその内容を変えることはない)。
- **`task_migrate_off_googledrive_checklist.md`**(このファイルの子): 実際に移行作業をするときは
  このチェックリストを上から順に消化する。チェック状態がそのまま進捗になるので、
  作業を中断して別セッション(別PC・別Claudeセッション)で再開する場合もこれを信じてよい。

## 新しいセッション/別の環境で作業を再開するとき、最初にやること

1. このファイルを読んで全体像(なぜ移行するか)を把握する
2. `task_migrate_off_googledrive_checklist.md` を開き、どこまで終わっているかチェックボックスで確認する
3. 未完了のステップから再開する
4. 移行そのものが完了していたら、このファイルと `ARCHITECTURE.md` に完了を反映し、
   `task_migrate_off_googledrive_checklist.md` はチェック済み状態のまま残しておく
   (完了タスクは削除せずアーカイブする、という `ARCHITECTURE.md` 自身のルールに従う)

## この文書を書いた時点の状態

- 移行先ディレクトリ: **未定**(推奨: `C:\dev\RaceCapture` 等、OneDrive/Google Drive/Dropbox
  いずれの同期対象パスにも含まれないローカルドライブ配下。ユーザーに確認して確定させること)
- 実際のファイルコピー・`git init`: **未実施**
- 移行元 `G:\マイドライブ\RaceCapture` の状態:
  - `rcp_mock_device.py` (モックデバイス本体、getVer/getMeta/getStatus/s/getLapCfg/
    getTrackCfg/getCanCfg/getObd2Cfg/getConnCfg に対応済み、最終版)が稼働中の場合がある
  - `rcp_capture.jsonl`(通信ログ)が肥大化しやすい(執筆時点で13MB超)。
    内容の要点は `HANDOFF.md` に転記済みなので基本的に移行不要
  - `mock_stdout.log` も同様に肥大化しやすく移行不要
  - `Autosport Labs community - ...json`(Discordエクスポート、1.3MB超)は参照資料であり
    プロジェクトのソースではない。Git管理に含めるか要検討
  - `.claude/settings.local.json` はこのマシン固有のClaude Code権限設定
