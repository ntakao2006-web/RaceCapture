# 移行チェックリスト: Google Drive → ローカルドライブ

> 親ドキュメント: [`task_migrate_off_googledrive.md`](task_migrate_off_googledrive.md)
> 1ステップずつ上から実行し、終わったら `[x]` にする。作業を中断して新しいセッションで
> 再開する場合も、このチェック状態をそのまま信じてよい。
> コマンド例は PowerShell 前提。

**移行先パス(確定): `C:\Users\ntaka\Documents\ClaudeCode\RaceCapture`**
(`C:\Users\ntaka\Documents` はOneDriveの「フォルダーバックアップ」対象になっていないことを
レジストリ(`HKCU:\...\User Shell Folders\Personal`)で確認済み。純粋ローカルパス)

## 0. 事前準備

- [x] 移行先パスを決める → `C:\Users\ntaka\Documents\ClaudeCode\RaceCapture`
- [x] 稼働中のモックプロセスを停止する(停止し忘れていたPID 9352を発見・停止済み)
- [x] 公式 RaceCapture アプリを完全終了する → 確認済み(未起動)

## 1. クリーンアップ(移行前)

- [x] `rcp_capture.jsonl`(通信ログ、18MB超まで肥大化していた)を削除
- [x] `mock_stdout.log`(5MB超)を削除
- [x] `Autosport Labs community - ...json`(Discordエクスポート)→ 判断: そのまま移行
      (整理は今回見送り。必要になったら `references/` 等への整理を検討)

## 2. 移動 — 完了

- [x] `robocopy /MOVE`(除外: `rcp_capture.jsonl`, `mock_stdout.log`)でフォルダごと移動済み
      ```powershell
      robocopy "G:\マイドライブ\RaceCapture" "C:\Users\ntaka\Documents\ClaudeCode\RaceCapture" /E /MOVE /XF "rcp_capture.jsonl" "mock_stdout.log"
      ```
- [x] 移動先でファイル一覧を確認済み。`.claude/`含め全ファイル揃っている
- [x] 移動元 `G:\マイドライブ\RaceCapture` は中身が空になっていることを確認済み
      (フォルダ自体はGoogle Drive側が同期処理中でロックしており即座には削除できなかった。
      実害なし。Drive の同期が落ち着いてから手動で削除してよい)

## 3. Git初期化(移行先で) — 完了

- [x] `git init` 実行済み
- [x] `.gitignore` 作成済み(内容は当初案通り)
- [x] `git add -A` → `git status` で内容確認済み(ログ・個人設定の混入なし)
- [x] 初回コミット作成済み(コミットハッシュ `0aecc80`)
- [x] GitHubにプライベートリポジトリを作成しpush済み
      → https://github.com/ntakao2006-web/RaceCapture
      (GitHub CLI (`gh`) をインストールし、個人メールで作成していた既存アカウント
      `ntakao2006-web` で認証。学校メールのアカウントは今回使わず据え置き)

## 4. 動作確認(移行先で) — 一部完了・残タスクあり

- [x] 新しい Claude Code セッションを移行先ディレクトリ
      (`C:\Users\ntaka\Documents\ClaudeCode\RaceCapture`)で開始済み(このセッション)
- [x] `rcp_mock_device.py` が新しい場所からでも問題なく起動することを確認済み
      (旧セッションからPowerShell経由で起動→即停止して確認。実際の作業再開時は
      改めて `python rcp_mock_device.py --port COM4 --baud 115200` で起動すること)
- [x] 公式 RaceCapture アプリを起動し、以前と同様にテレメトリーが表示されることを確認済み
      (COM3/COM4ペア健在、`rcp_mock_device.py`をCOM4で起動→公式アプリがCOM3経由で
      接続し、テレメトリー表示を確認)
- [x] `git log` / `git status` が正常に動作し、ロックエラー等が出ないことを確認済み(問題なし)

## 5. 後片付け

- [x] 移行元フォルダは中身が空になっている。フォルダ自体はGoogle Driveがロック中で
      即座には削除できなかった → 同期が落ち着いてから手動で削除してよい(実害なし)
- [x] `ARCHITECTURE.md` の「4. 現状ステータス」に移行完了(ファイル移動部分)を追記
- [x] このチェックリストと `task_migrate_off_googledrive.md` は削除せず、
      完了した記録として残す
