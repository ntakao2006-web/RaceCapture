# このPCのフォルダー名を `RaceCapture` から `EcoLogger` へ変える手順

2026-11-13作成（`task_spec_rebuild_breakdown.md` SP-9-9）。GitHubのリポジトリ名は同じ日に `EcoLogger` へ変えてある。
ここで扱うのは、このPCの作業フォルダー `%USERPROFILE%\Documents\ClaudeCode\RaceCapture` の名前だけ。

**2026-11-13に実行済み（ユーザー）。** 結果は10章。通り道（`RaceCapture`）は残してあり、外すのは7章。

## 1. なぜ手順が要るか

Claude Codeの項目名は、このフォルダーの名前から付く。フォルダー名を変えれば項目名も `EcoLogger` になるが、次のものが今のパスを見ている（2026-11-13に調べた）。

| 今のパスを見ているもの | 変えるとどうなるか | 手当て |
|---|---|---|
| デスクトップのショートカット「EcoLogger Ver.2」 | 開かなくなる | 作り直す（手順5） |
| Claudeの記憶（46件）とこのプロジェクトの会話の記録（358本）。置き場は `%USERPROFILE%\.claude\projects\C--Users-<ユーザー名>-Documents-ClaudeCode-RaceCapture\` | 新しいフォルダーは別のプロジェクトとして、記憶が空で始まる | 記憶を新しい置き場へ写す（手順4） |
| `%USERPROFILE%\.claude.json` の中のこのプロジェクトの設定（信頼・許可） | 新しいフォルダーで、信頼するかをもう一度聞かれる | 聞かれたら答える |
| 作業用の写し（worktree）`.claude\worktrees\strange-chatterjee-6703df` | gitが場所を見失う | 直す（手順3） |
| 別のリポジトリ `emc-engine-crankcase\ARCHITECTURE.md` の記述 | 文章の中の案内だけ。動きには関係しない | 直す（手順6） |
| リポジトリの中の記録（`outputs\` の下のログ・古いメモ）に残るパス | 記録なのでそのまま | 何もしない |

タスクスケジューラと、Windowsの自動起動には、このフォルダーを指すものは無かった。
デスクトップの「RaceCapture」のショートカットは公式アプリ（`Program Files (x86)\RaceCapture`）のもので、このフォルダーとは関係ない。

## 2. 方針：名前を変え、古い名前は「通り道」として残す

古い名前 `RaceCapture` を、新しいフォルダーを指す通り道（ジャンクション）として残す。
こうすると、古いパスを見ているものが残っていても動き続け、古い会話も古い項目から開ける。通り道は、困らないと分かってから外す。

## 3. フォルダー名を変える

**このフォルダーを開いているものを全部閉じる**：Claudeのアプリ（このプロジェクトの会話）、操作メニュー、回収アプリ、エディター、エクスプローラーの窓、ターミナル。
開いたままだと「アクセスが拒否されました」と出て名前を変えられない（壊れはしない。名前は元のまま）。**メモ帳でこのフォルダーのファイルを開いているだけでも拒否される。Claudeのアプリは窓を閉じても裏に残るので、通知領域のアイコンから終了する。** 残っているかは `(Get-Process claude -ErrorAction SilentlyContinue).Count` が0かで分かる。**Claudeにこのプロジェクトの会話の中から頼むことはできない**（その会話自身がフォルダーを使っているため）。

先に、コミットしていない変更が無いことを確かめる（このフォルダーで）。

```powershell
git status --short
```

PowerShellを新しく開き（場所は `%USERPROFILE%` のまま）、1行ずつ実行する。

```powershell
Rename-Item "$env:USERPROFILE\Documents\ClaudeCode\RaceCapture" EcoLogger
```

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\Documents\ClaudeCode\RaceCapture" -Target "$env:USERPROFILE\Documents\ClaudeCode\EcoLogger"
```

```powershell
git -C "$env:USERPROFILE\Documents\ClaudeCode\EcoLogger" worktree repair .claude\worktrees\strange-chatterjee-6703df
```

（場所を名指ししないと、通り道ごしに古いパスのまま通ってしまい、直らない。`git worktree list` が新しいパスを出せば直っている）

## 4. Claudeの記憶を新しい置き場へ写す

置き場の名前は、フォルダーのパスの `:` `\` を `-` に置き換えたもの。写すのは記憶（`memory`）だけにする。

```powershell
$old = Get-ChildItem "$env:USERPROFILE\.claude\projects" -Directory | Where-Object Name -like '*-Documents-ClaudeCode-RaceCapture'
```

```powershell
$new = Join-Path $old.Parent.FullName ($old.Name -replace 'RaceCapture$','EcoLogger')
```

```powershell
New-Item -ItemType Directory -Force "$new\memory" | Out-Null; Copy-Item "$($old.FullName)\memory\*" "$new\memory\" -Recurse
```

- 古い置き場は消さない。古い会話の記録はそこに残り、通り道（`RaceCapture`）の側の項目から開ける。
- 写したあと、記憶の中に古いパスを書いているものがあれば、新しい会話の最初に「記憶の中の古いパスを直して」とClaudeに頼む。

## 5. 入口を作り直して確かめる

1. `EcoLogger\tools\ecologger_menu\Make-Shortcut.cmd` を動かす（デスクトップのショートカットが新しいパスになる）。
2. デスクトップの「EcoLogger Ver.2」を開き、窓が出ることを見る。
3. Claudeのアプリで、新しいフォルダー `Documents\ClaudeCode\EcoLogger` を開いて会話を始める。項目名が `EcoLogger` になっていること、記憶が読めていること（「いま何を覚えている？」と聞く）を見る。
4. その会話で、道具の試験を1つ流してもらう（例：操作メニューの試験）。

## 6. 残りの直し

- `emc-engine-crankcase\ARCHITECTURE.md` の「`ClaudeCode/RaceCapture`」を新しい名前へ（そのリポジトリの会話で）。
- ファームを組んだときの作業用のフォルダー（`firmware\` の下の `.pio`）は古いパスを抱えていることがある。次に組むときに作り直される。

## 7. 通り道を外す（急がない）

数週間使って困らなければ外す。**外すと、古い項目（`RaceCapture`）からは会話を開けなくなる。**

```powershell
(Get-Item "$env:USERPROFILE\Documents\ClaudeCode\RaceCapture").Delete()
```

通り道だけが消え、中身（`EcoLogger`）は消えない。`Remove-Item -Recurse` は使わない（中身まで消しに行くおそれがある）。

## 8. 元へ戻すとき

Claudeのアプリと道具を閉じてから、通り道を外し（7章の1行）、名前を戻す。

```powershell
Rename-Item "$env:USERPROFILE\Documents\ClaudeCode\EcoLogger" RaceCapture
```

そのあと `Make-Shortcut.cmd` をもう一度動かす。古い置き場の記憶と会話の記録には手を付けていないので、そのまま元どおり使える。

## 9. 確かめていないこと

- **Claudeのアプリ（デスクトップ版）の横の一覧が、名前を変えたあとどう見えるか。** 古い会話が古い項目のまま残るのか、通り道の側と新しい側で二重に見えるのかは、やってみないと分からない。
- **会話の記録（358本）を新しい置き場へ写して続きから使えるか。** 記録の中に古いパスが書き込まれているので、この手順では写さず、古い置き場に残す形にした。
- この手順そのものを、まだ1度も通していない。

## 10. 実行した結果（2026-11-13）

- 1回目は「アクセスが拒否されました」で止まった。メモ帳がこのフォルダーのファイルを開いていたのと、Claudeのアプリが動いていたため（3章に書き足した）。閉じてやり直して通った。
- 確かめたこと：`EcoLogger`が本体で`RaceCapture`がそこを指す通り道になっている、記憶46件が新しい置き場にある（古いパスを書いた記憶は無い）、デスクトップのショートカットが新しいパスを指している、リモートは`EcoLogger`、コミットしていない変更は無い、操作メニューの試験が通る。
- 作業用の写しは古いパスのまま登録されていたので、場所を名指しして直した（3章の3行目を書き換えた）。
- **Claudeのアプリは、開いていた会話を新しいフォルダーの側へそのまま引き継いだ**（この手順を作った会話が、名前を変えたあと新しいフォルダーで続いた）。ほかの古い会話が横の一覧でどう見えるかは見ていない。
- 残り：6章（別のリポジトリの記述）と7章（通り道を外す）。

