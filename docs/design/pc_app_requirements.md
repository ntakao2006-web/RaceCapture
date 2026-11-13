# PCの道具が前提にしているものの一覧と、ほかの人のPCへの入れ方の案

2026-11-13 作成。`task_spec_rebuild_breakdown.md` の SP-3-10「ほかの人のPCへ1回の操作で入る形にする」（`SPEC.md` の S-6）の最初の一歩。

- この資料は**調べた結果と案**。入れ方はまだ決めていない（決めるのはユーザー）
- pip で入れるものの一覧は `tools/requirements.txt`（この資料と一緒に作った）
- 道具そのものは何も変えていない

## 0. 先に結論

1. **新しい入口のアプリ（`EcoLogger-App.cmd`）は、Pythonの標準ライブラリだけで動く。** pip で入れるものは1つも要らない。Python以外で要るのは adb（USBでつなぐとき）と ssh（テザリングでつなぐとき。Windowsに初めから入っている）だけ。ffmpeg も tkinter も要らない
2. pip で入れるものが要るのは、**走行解析・1周の動画・HUDをPCで見る・レンズをPCで見る**の4か所だけ。数は5つ（numpy・pandas・scipy・opencv-python・Pillow）で、入れると約390 MB
3. ffmpeg を呼ぶのは **`tools/lap_video/` だけ**
4. いまの道具は「リポジトリのフォルダーの形のまま置いてあること」を前提にしている（道具どうしが相対の場所で呼び合い、回収したデータもリポジトリの中の `drive_logs/` に置く）
5. 入れ方のおすすめは **案①の変形：フォルダー1つで持ち運ぶ形にし、中身（Python・adb）は相手のPCで初回に公式の配布元から自動で取ってくる**（7章）

## 1. どう洗ったか

| 見たもの | 方法 |
|---|---|
| Pythonの import | `tools/` 以下の `.py` 78本すべてを、Pythonの構文解析（`ast`）にかけて import を全部抜き出し、Python自身が持っている標準ライブラリの一覧（`sys.stdlib_module_names`）と、リポジトリの中のファイル名を引いた残りを「外部パッケージ」とした。関数の中にある import（その機能を使うときだけ読まれる）と、`try` の中の import も区別した |
| 道具が読みに行く、`tools/` の外のファイル | `sys.path.insert` を全部拾い、行き先（`EcoCapture-Web/`）のファイルの import も同じ方法で見た |
| Python以外のプログラム | `.py`・`.cmd`・`.ps1` を `adb`・`ssh`・`scp`・`ffmpeg`・`ffprobe`・`powershell`・`os.startfile`・`ctypes`・`tkinter`・`webbrowser`・`LOCALAPPDATA`・`.ecologger` などの語で検索し、当たった行を読んだ |
| Pythonの最低の版 | 構文解析で、新しい版でしか使えない書き方（`:=`、`match`、`Path.is_relative_to`、`str.removeprefix`、`asyncio.to_thread`、`datetime.UTC`、辞書の `\|`、f文字列の中の `\`）を探した |
| 大きさ | このPCに入っている実物のフォルダーを測った（パッケージ・adb・ffmpeg） |
| 画面のページ | `video_collect.html` に、外のサイトから読み込むもの（`src=`・`href=`・`http`）が無いことを検索で確かめた |

**確かめていないこと**

- 実際に動かしたことがあるのは、このPCの **Python 3.14** と、`tools/requirements.txt` に「確かめた版」と書いた版だけ。「3.9以上」「numpy 1.24以上」などの下限は**書き方から読んだもので、古い版で動かしてはいない**
- まっさらなPC（Pythonもadbも無い）での確かめは、していない。SP-3-11（ほかの人に手順書だけで回収までしてもらう）で確かめることになる
- ライセンスの欄は、各配布元の条件を覚えている範囲で書いた。**配り方を決める前に、原文をもう一度読むこと**

## 2. Pythonの外部パッケージ（道具ごと）

「必須」＝ファイルの頭で import していて、無いと道具が開かない。「使うときだけ」＝関数の中で import していて、その機能を使ったときに初めて要る。

### 2-1. ふだん使う道具（`tools/dev/`・`tools/unoq_overlay_enc/` 以外）

| 道具 | 外部パッケージ | 必須か |
|---|---|---|
| `video_collect/`（EcoLoggerアプリ・回収アプリ・`now_status.py`・`app_ops.py`・`sd_card.py`・`dev_app.py`） | なし | — |
| `collect_logs/`（`collect_logs.py`・`unoq_link.py`・`unoq_ssh.py`） | なし。ただし `collect_logs.py --config <設定>` を付けたときだけ pydantic（`EcoCapture-Web/models.py` 経由） | `--config` のときだけ。回収アプリは `--config` を渡さないので要らない |
| `ecologger_menu/`（操作メニュー） | なし（tkinter は3章） | — |
| `remote_command/`（`remote_command_pc.py`・`phone_key.py`・`qr.py`） | なし。中継サーバーとのやりとり（WebSocket）もQRの絵も自前で書いてある | — |
| `sugo_setup/`（6本） | なし | — |
| `video_hud/hud_apply.py`・`hud_layout.py`（HUDを本体へ送る） | なし | — |
| `video_hud/hud_preview.py`（HUDをPCで見る） | numpy・Pillow | 必須 |
| 同上 | opencv-python | 使うときだけ（背景に動画ファイルを使うとき） |
| `lens_view/lens_view.py`（レンズをPCで見る） | opencv-python・numpy | 必須（カメラと窓を使うので、窓の無い headless 版は不可） |
| `lens_view/lens_apply.py`・`lens_preview_remote.py`（本体へ送る・本体のモニターに出す） | なし | — |
| `lens_view/lens_preview.py` | gi（PyGObject・GStreamer） | **本体（UNO Q）の上で動く**。PCには要らない |
| `video_exposure/exposure_apply.py` | なし | — |
| `race_analysis/race_analysis.py`・`lap_survey.py`・`sd_gnss.py` | numpy・pandas・scipy | 必須 |
| `lap_video/lap_video.py` | numpy（と `wind_reduce.py` 経由で scipy） | 使うときだけ。`laps`（周の一覧）と `clip --no-clean`（風切りを下げない）は無くても動く |
| `lap_video/wind_reduce.py` | numpy・scipy | 必須 |
| `lap_video/incidents.py` | numpy・pandas・scipy | 必須 |
| 同上 | opencv-python | 使うときだけ（`sheet`＝コマを並べた画像） |
| `home_telemetry/live_bridge.py` | websockets（13以上） | 必須。**自宅のサーバーの上で動く**もの |
| `home_telemetry/dev_home.py`・`replay_sender.py` | websockets | 必須（PCで動かす確かめ用。このPCには websockets が入っていない） |
| `home_telemetry/` のほか（`compare_replication.py`・`demo_loop.py`・`lap_passes.py`・`grafana/` の4本） | なし | — |

### 2-2. 試験（`test_*.py`、19本）

- 試験の仕組みは標準の `unittest`。pytest は使っていない
- `remote_command/test_phone_key.py`：qrcode、pyzbar＋Pillow。**無ければその試験だけ飛ばす**作り
- `lap_video/test_lap_video.py`：numpy（必須）、pandas（使うときだけ）
- `sugo_setup/test_defi_temp_setup.py`・`test_defi_volt_setup.py`：pydantic（`EcoCapture-Web/models.py` 経由）。`try` の中にあり、無ければその確かめを飛ばす
- `home_telemetry/test_live_bridge.py`：websockets（`live_bridge.py` を読むので）

### 2-3. 開発用（`tools/dev/`）

| 道具 | 外部パッケージ | Python以外 |
|---|---|---|
| `imagery_check/imagery_check.py` | numpy・pandas・Pillow（必須） | インターネット（航空写真を取りに行く） |
| `lte_antenna/radio_walk_pc.py` | なし | adb か ssh |
| `lte_antenna/antenna_compare.py`・`radio_walk_log.py` | なし | 本体の上で動く |
| `race_replay/emulator_replay.py` | なし | Androidのエミュレーターと adb（`%LOCALAPPDATA%` の下の決め打ちの場所） |
| `race_replay/race_csv.py`・`snapshot.py` | なし | — |
| `podium_replay/podium_replay.py` | なし | adb。**場所がこのPCのユーザー名入りの決め打ち**になっている（ほかのPCでは動かない。公開リポジトリなので、直すときに `find_adb` へ寄せたい） |
| `can1_loss/can1_loss.py` | なし | ssh |
| `unoq_spi_sd_test/` の2本 | なし | 本体の上で動く |

### 2-4. 本体で動くもの・その試験用（`tools/unoq_overlay_enc/`）

| 道具 | 外部パッケージ | Python以外 |
|---|---|---|
| `make_font_atlas.py`（PCで動かす。HUDの字の絵を作る） | Pillow（必須） | — |
| `make_preview_mp4.py`（PCで動かす） | なし | **VLC**（`C:\Program Files\VideoLAN\VLC\vlc.exe` の決め打ち） |
| `audio_mux_check.py` | なし | ffmpeg・ffprobe（PCならWSLで、と書いてある） |
| `audio_beep.py`・`fake_telemetry.py`・`replay_telemetry.py` | なし | 本体の上で動く |

### 2-5. まとめ

- 外部パッケージは全部で **9種類**。内訳：
  - PCの道具で要るもの **5**：numpy・pandas・scipy・opencv-python・Pillow（`SPEC.md` S-6 に書いてあった5つと同じ。漏れは無かった）
  - 一部の道具だけ **2**：pydantic（`--config` のとき）、websockets（自宅のサーバーとその確かめ用）
  - 試験だけ **2**：qrcode・pyzbar
  - （数えないもの：gi は本体の上だけ）
- 5つを入れたときの大きさ（このPCの実測）：numpy 55 MB、pandas 70 MB、scipy 136 MB、opencv-python 113 MB、Pillow 16 MB、**合わせて約390 MB**

## 3. Python以外の前提

### 3-1. 外のプログラム

| もの | 使う道具 | 探し方 | 無いとき |
|---|---|---|---|
| **Python本体** | 全部 | どの `.cmd` も、PATHにある `python` をそのまま呼ぶ。デスクトップのショートカットは `pythonw`（`make_shortcut.ps1` がPATHから探す） | 何も開かない |
| **adb**（Androidのplatform-tools。このPCのものは 37.0.1、フォルダーごとで17 MB） | USBで本体につなぐ道具すべて（`unoq_link.py` 経由） | `collect_logs.py` の `find_adb`：①PATHの `adb` → ②`%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` → ③`%LOCALAPPDATA%\AndroidSdkTools\platform-tools\adb.exe` → ④Claudeのアプリが振り替えた先（`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Local` の下の②③と同じ場所）→ ⑤**リポジトリの `other\uno_q_tools\platform-tools\adb.exe`**（`other/uno_q_tools` はGitに入っていない） | USBの道は使えず、「adb がPCに入っていません」と出てテザリング（ssh）を試す |
| **ssh・scp**（OpenSSHクライアント） | テザリングで本体につなぐ道具すべて（`unoq_link.py`・`unoq_ssh.py`）。回収アプリの「控え」を `ssh:<ホスト>:<フォルダー>` へ写すとき。`sugo_setup/install_sectors.py`（自宅のサーバーへ）。`dev/can1_loss` | PATHの `ssh`・`scp`。Windows 10/11 には `C:\Windows\System32\OpenSSH\` に初めから入っているのがふつう | 「ssh がPCに入っていません → Windowsの『OpenSSH クライアント』を入れる」と出る |
| **sshの設定と鍵** | 同上 | `%USERPROFILE%\.ssh\config` に `Host unoq`（行き先の名前は `uno-q.local`、本体のユーザー名、鍵のファイル）。**このPCの公開鍵が本体に登録してあること**。本体の鍵は `known_hosts` に `uno-q.local` の名前で覚えている。名前が引けないときは `unoq_ssh.py` が同じネットワークからIPで探し、覚えている鍵と照らし合わせる（前回のIPは `%USERPROFILE%\.ecologger\unoq_ip.txt`） | 「鍵が合わず入れません」などと理由つきで出る。**この設定と鍵の登録を自動でする道具は、まだ無い**（手作業） |
| **ffmpeg・ffprobe** | **`tools/lap_video/` だけ**（`lap_video.py` の `clip`、`incidents.py`）。ほかに開発用の `unoq_overlay_enc/audio_mux_check.py` | `lap_video.py` の `ffbin`：①PATH → ②wingetで入れた `Gyan.FFmpeg` の場所（`%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\`）→ ③Claudeのアプリが振り替えた先の同じ場所 | 「ffmpeg が見つからない（winget install …）」と出て止まる |
| **PowerShell**（Windowsに付いている 5.1） | `collect_logs/phone_mtp.ps1`（USBでつないだスマホからCSVを取る。エクスプローラーの仕組みを使う）、`video_collect/sd_card.py`（SDのフォーマット。管理者の確認＝UACが出る）、`ecologger_menu/make_shortcut.ps1`（デスクトップのショートカット） | `powershell.exe` | スマホからの回収・SDのフォーマット・ショートカット作りができない |
| **ブラウザ** | EcoLoggerアプリ・回収アプリ・`hud_preview.py` | PCの既定のブラウザ（`webbrowser`）。ページはPCの中（`127.0.0.1` の8791番。ふさがっていれば空いている番号）から出し、外のサイトからは何も読み込まない | 画面が開かない |
| **VLC** | `unoq_overlay_enc/make_preview_mp4.py` だけ | 決め打ちの場所 | その道具だけ動かない |
| **Acrobat** | 道具からは呼んでいない（手順書を刷るときに人が使うだけ） | — | — |

### 3-2. Windowsだけの仕組み

| 仕組み | 使う所 | Windows以外では |
|---|---|---|
| `ctypes`（Windowsの `kernel32`）：ドライブの一覧、ドライブの名前・大きさ・形式 | `collect_logs.py`（`candidate_drives`。Windows以外なら空を返す）、`sd_card.py`（SDカードの確かめ） | SDカードを自分で見つけられない |
| `os.startfile`（フォルダーを開く） | `video_collect.py`（無ければ何もしない作り）、`ecologger_menu.py` | メニューの「フォルダーを開く」が動かない |
| `cmd /c` で `.cmd` を開く、黒い窓を出さない指定（`CREATE_NO_WINDOW` など） | `ecologger_menu.py` | メニューから道具を開けない |
| 同じ番号で2つ目のアプリが待てないようにする指定（`SO_EXCLUSIVEADDRUSE`） | `video_collect.py`（あるときだけ使う作り） | 問題なし |
| `.cmd` の中の `chcp 65001`・`PYTHONIOENCODING=utf-8` | すべての `.cmd` | — |

**いまの道具はWindows専用**と考えてよい（入口が `.cmd`、SDカードとスマホの回収がWindowsの仕組み）。

### 3-3. tkinter（Pythonに付いてくる窓の部品）

- 使うのは2か所：`ecologger_menu.py`（操作メニュー。必須）と、`phone_key.py` の窓（`Phone-Key.cmd` で開いたときだけ。関数の中で読む）
- **EcoLoggerアプリは使わない**（QRもブラウザの画面に描く。`app_ops.py` は `phone_key.py` の「アドレスを作る」所だけを使う）
- ふつうのインストーラーで入れたPythonには付いてくる。**埋め込み版（embeddable）には入っていない**（6章の案①に関わる）

### 3-4. PCの置き場とデータ

| 場所 | 中身 |
|---|---|
| `%USERPROFILE%\.ecologger\remote_command.json` | LTEの命令の合言葉と、中継サーバーのアドレス（`remote_command_pc.py setup` が作る。リポジトリには入れない） |
| `%USERPROFILE%\.ecologger\unoq_ip.txt` | 前回見つけた本体のIP |
| `%USERPROFILE%\.ecologger\ecologger_menu.log` | 操作メニューの記録 |
| `%USERPROFILE%\.ssh\` | sshの設定・鍵・`known_hosts` |
| リポジトリの `drive_logs\`（Gitには入れない） | 回収した走行記録・動画・SDの写しと、その一覧（`collected.json`・`v2_sd_index.json`・`v2_video\index.json`）。**道具は自分の置き場所から2つ上＝リポジトリの直下を見て、そこの `drive_logs\` へ書く** |

- `%LOCALAPPDATA%` は使わない決まり（Claudeのアプリから動かしたときだけ別の場所に振り替えられるため）。古い置き場（`%LOCALAPPDATA%\EcoLogger\`）は読むだけ残してある

### 3-5. リポジトリの形そのものが前提

道具どうしが「自分の2つ上がリポジトリ」として相対の場所で呼び合っている。`tools/` だけを抜き出しても動かない。

- `tools/` の外で読むファイル（`EcoCapture-Web/` の中、どれも標準ライブラリだけ）：
  - `video_store.py`（動画の一覧と消し方。回収アプリ）
  - `remote_command.py`（署名の作り方。LTEの命令）
  - `sd_decode.py`・`imu_mount.py`（SDの `.BIN` をCSVにする。回収のとき）
  - `hardware.py`・`models.py`（`--config` のときだけ。`models.py` が pydantic を使う）
- `ecologger_menu.py` は `tools/` の中のほかのフォルダーの `.cmd` を場所で呼ぶ

### 3-6. PCの外で要るもの

- USBケーブル（データが通るもの）。ドックをつないだまま起動した本体はUSBでつながらない（`unoq_link.py` の案内にある）
- テザリングの道：PCと本体が同じテザリング（スマホ）にいること
- LTEの命令：PCがインターネットにつながっていること、合言葉の準備が済んでいること
- **まっさらなPCで、USBをつないだだけで adb が本体を見つけるか（ドライバーが要るか）は確かめていない**

## 4. Pythonの最低の版

**3.9 以上**（PCで動かす道具について）。`SPEC.md` S-6 の「3.9以上」と合っていた。

| 根拠（書き方） | 要る版 | ある所 |
|---|---|---|
| `:=`（代入しながら比べる） | 3.8 | `collect_logs.py` 107・121行、`video_collect.py` 155・544・735行、`lap_video.py` 165行、`EcoCapture-Web/sd_decode.py` 22・43行 |
| `unlink(missing_ok=True)` | 3.8 | `video_collect.py` 326行ほか |
| **`Path.is_relative_to`** | **3.9** | `video_collect.py` 859行（アプリの本体） |
| `str.removeprefix` | 3.9 | `sugo_setup` の試験2本、`EcoCapture-Web/models.py` |
| 辞書の `\|`、`asyncio.to_thread` | 3.9 | `home_telemetry/live_bridge.py` |
| `datetime.UTC` | 3.11 | `home_telemetry/compare_replication.py` 44行（この1本だけ） |
| f文字列の `{}` の中に `\` | 3.12 | `home_telemetry/live_bridge.py` 406行（**自宅のサーバーで動くもの**。PCの道具ではない） |

- `match` 文、型の `X | Y`、`list[int]` のような新しい型の書き方は、`tools/` には無かった
- pydantic を使う `EcoCapture-Web/models.py` には型の `X | Y` があり、そこは 3.10 以上が要る（`--config` のときだけ読まれる）
- 配るPythonを選ぶなら、**3.12 か 3.13 を1つに決めて全員同じにする**のが無難（3.9 はもう直しが出ない版。外部パッケージの新しい版も 3.9 を切っている）。このPCで確かめたのは 3.14 だけ

## 5. 新しい入口のアプリだけを動かすのに要るもの

対象：`tools/video_collect/EcoLogger-App.cmd`（`video_collect.py --tab now`）。「いまの様子」「回収」の段と、操作（ラップ・LTEの命令・合言葉・QR）。

### 5-1. ファイル（18本、どれも標準ライブラリだけ）

| 場所 | ファイル |
|---|---|
| `tools/video_collect/` | `EcoLogger-App.cmd`・`Collect-Video.cmd`・`video_collect.py`・`video_collect.html`・`now_status.py`・`app_ops.py`・`sd_card.py` |
| `tools/collect_logs/` | `collect_logs.py`・`unoq_link.py`・`unoq_ssh.py`・`phone_mtp.ps1` |
| `tools/remote_command/` | `remote_command_pc.py`・`phone_key.py`・`qr.py` |
| `EcoCapture-Web/` | `video_store.py`・`remote_command.py`・`sd_decode.py`・`imu_mount.py` |

フォルダーの形（`tools/…` と `EcoCapture-Web/…` が同じ親の下）は保つこと。データは同じ親の下の `drive_logs\` にできる。

### 5-2. 最低限要るもの

| もの | 要るか |
|---|---|
| Python 3.9以上（標準ライブラリだけ） | **要る** |
| pip で入れるもの | **要らない（0個）** |
| tkinter | 要らない |
| ffmpeg | 要らない（「1本につなげる」も ffmpeg を使わず、ファイルをそのままつなぐ） |
| adb | USBでつなぐなら要る（走行記録・動画の回収はUSBが主。動画はUSBのときだけ回収する） |
| ssh・scp と `Host unoq`・鍵 | テザリングでつなぐなら要る。USBだけで使うなら無くてよい |
| PowerShell | スマホからの回収・SDのフォーマットのときだけ（Windowsに付いている） |
| ブラウザ | 要る（どのPCにもある） |
| インターネット | LTEの命令のときだけ |

### 5-3. 標準ライブラリだけで動く範囲

| 範囲 | 道具 |
|---|---|
| **標準ライブラリだけで動く** | EcoLoggerアプリ、回収（本体・SD・スマホ）、操作メニュー（tkinter）、LTEの命令と合言葉・QR、SUGOの設定とDASHの確かめ、HUD・レンズ・露出を本体へ送る、本体のモニターでレンズを決める |
| **pip のものが要る** | 走行解析（`race_analysis/`）、1周の動画・切り抜き（`lap_video/`。ffmpeg も）、HUDをPCで見る（`hud_preview.py`）、レンズをPCで見る（`lens_view.py`） |

つまり、**「当日ピットで使うもの」は全部、Python本体＋adb（＋ssh）だけで足りる**。重いもの（約390 MBのパッケージと ffmpeg）が要るのは「あとで解析する・動画を作る人」だけ。入れ方を2段（まず軽い分、解析もする人だけ追加）に分けられる。

## 6. 入れ方の案

大きさは、このPCの実物を測ったもの（パッケージ390 MB、adb 17 MB、ffmpeg はいま入っている「全部入り」の版で `ffmpeg.exe`・`ffprobe.exe` が各約228 MB）と、覚えている範囲の目安（Pythonの埋め込み版は展開して約25 MB、ふつうのインストーラーで入れると100 MB強）。

### 案① フォルダーごと持ち運ぶ（Pythonの埋め込み版＋道具＋adb＋ffmpeg）

| 項目 | 内容 |
|---|---|
| 相手のPCですること | フォルダー（かzip）を置いて、中の `.cmd` をダブルクリック。Windowsには何も入れない。管理者の権限も要らない |
| 大きさの目安 | アプリだけ：約45 MB（Python 25＋adb 17＋道具）。解析・動画まで：＋パッケージ約390 MB＋ffmpeg（小さい版を選べば100 MB台、いまの版なら約450 MB） |
| 更新の仕方 | 道具（`.py`）のフォルダーだけ入れ替える。Python・adb は入れ替えなくてよい。**回収したデータ（`drive_logs\`）が同じフォルダーの中にあるので、上書きで消さない手順が要る** |
| 再配布の条件 | Pythonの埋め込み版：配ってよい（Pythonのライセンス）。ssh：Windowsのものを使うので配らない。**adb：Googleが配っている出来合いのもの（platform-tools）は、利用規約で配り直しが認められていない**（元のプログラム自体は Apache 2.0）。**ffmpeg：配ってよいが、ライセンス（出来合いの版は多くがGPL）の文面を付け、元のプログラムの入手先を示す義務がある**。どちらも**公開リポジトリには入れない**ほうがよい（大きさの面でも） |
| 困りそうな点 | ①埋め込み版には **tkinter が無い**→操作メニューと `Phone-Key.cmd` の窓が動かない（アプリは動く）。②埋め込み版には pip が無く、「動かした `.py` のあるフォルダーを探す」ふつうの動きもしない設定になっている→道具が隣のファイルを読めないおそれ。**設定ファイル（`python3xx._pth`）の手直しと実験が要る**。③`.cmd` がPATHの `python` を呼んでいるので、フォルダーの中のPythonを呼ぶように変える。④ffmpeg を探す所（`ffbin`）がPATHとwingetの場所しか見ない→フォルダーの中も見るように変える。⑤adb は `other\uno_q_tools\platform-tools\` に置けば**今のままで見つかる** |

### 案② インストーラー1つ（PyInstaller などで `.exe` に固める）

| 項目 | 内容 |
|---|---|
| 相手のPCですること | `.exe` を1つもらって実行する |
| 大きさの目安 | アプリだけなら30〜50 MB。解析・動画まで入れると500 MB以上 |
| 更新の仕方 | **直すたびに、こちらで固め直して配り直す**。`.py` を1行直しただけでも作り直し |
| 再配布の条件 | PyInstaller 自体は、固めたものを自由に配ってよい。adb と ffmpeg を中に入れるなら、条件は案①と同じ（adb は配り直し不可、ffmpeg は文面と入手先を付ける） |
| 困りそうな点 | ①いまの道具は「リポジトリのフォルダーの形」と「`.cmd` から `python` を呼ぶ」を前提にしているので、**固めるには道具の側の作り替えが大きい**（ファイルの探し方、データの置き場、メニューから別の道具を開く所）。②署名の無い `.exe` は、Windowsの警告（SmartScreen）やウイルス対策ソフトに止められやすい。学校や会社のPCではとくに。③中身が見えないので、うまく動かないときに相手のPCで調べにくい。④固める道具と手順を、こちらで持ち続けることになる |

### 案③ winget やスクリプトで、公式の配布元から入れる

| 項目 | 内容 |
|---|---|
| 相手のPCですること | リポジトリ（かそのzip）を置いて、`Setup.cmd` のようなものを1回ダブルクリック。中で winget が Python・adb（platform-tools）・ffmpeg を入れ、`pip install -r tools/requirements.txt` をし、ショートカットを作る |
| 大きさの目安 | 配るものはリポジトリだけ（道具は数MB）。相手のPCには Python 100 MB強＋adb 17 MB＋（解析もするなら）パッケージ390 MB＋ffmpeg |
| 更新の仕方 | 道具はリポジトリを取り直す（`git pull` かzipの入れ直し）。Python などは winget で上げられる |
| 再配布の条件 | **どれも相手のPCが公式の配布元から直接取るので、こちらは何も配り直さない**。ライセンスの心配がいちばん小さい |
| 困りそうな点 | ①入れるときにインターネットが要る。②**Windowsそのものに入れる**ので、相手のPCにもう入っているPython・PATHとぶつかることがある（Windowsには、`python` と打つとストアが開くだけの仕掛けもある）。入れた直後はPATHが効かず、開き直しが要る。③winget が使えないPC（古いWindows 10、学校・会社の制限）がある。④人によって入る版が違ってくる（「あの人のPCだけ動かない」が起きやすい）。⑤途中で止まったときに、どこまで入ったかが分かりにくい |

### どの案でも別に要ること

- **sshの `Host unoq` と鍵**：PCごとに鍵を作り、公開鍵を本体に登録する。秘密の鍵を人から人へ写して配ってはいけない。USB（adb）でつないだときに、鍵作り・`config` への書き足し・本体への登録を1回でする道具を作れば、手作業を無くせる（**まだ無い**）。USBだけで使う人には要らない
- **LTEの合言葉**：`remote_command_pc.py setup`（アプリの「合言葉の準備」）で本体から受け取る形がもうある。配るものには入れない
- **回収したデータの置き場**：いまはリポジトリの中の `drive_logs\`。ほかの人のPCで、道具を入れ替えてもデータが残る置き場（例：ドキュメントの下）に変えるかどうかを、入れ方と一緒に決める
- **adb のドライバー**：まっさらなPCで要るかどうかを、1台で確かめる

## 7. おすすめ（案）

**案①の変形：「フォルダー1つ」の形にし、中身は相手のPCで初回に自動で取ってくる。2段に分ける。**

- 配るのはリポジトリ（かそのzip）だけ。中の `Setup.cmd`（新しく作る）を1回ダブルクリックすると、**そのフォルダーの中の `runtime\` に**、版を決めたPythonの埋め込み版と adb を公式の配布元から取ってきて置く。Windowsには何も入れない（PATHも変えない、管理者の権限も要らない）
- `.cmd` は「`runtime\` にPythonがあればそれを、無ければ今までどおりPATHの `python`」を呼ぶ。開発しているこのPCは今のまま動く
- **1段目（全員）**：Python＋adb だけ。約45 MB。これでEcoLoggerアプリ（いまの様子・回収・操作）が動く
- **2段目（解析・動画を作る人だけ）**：`Setup.cmd` に「解析も入れる」を足し、パッケージ5つ（約390 MB）と ffmpeg を同じ `runtime\` へ足す

**理由**

1. **新しいアプリは標準ライブラリだけで動く**（5章）ので、1段目がとても軽く、失敗する所が少ない。「当日ピットで使う人」は1段目だけで足りる
2. **adb と ffmpeg を配り直さずに済む**（相手のPCが公式の配布元から取る）。公開リポジトリに大きなファイルも、配ってはいけないものも入れなくてよい（案③の良い所）
3. **Windowsに入れないので、相手のPCのPythonやPATHとぶつからず、全員が同じ版になる**。要らなくなったらフォルダーを消すだけ（案①の良い所）
4. 道具を直したときは `.py` を入れ替えるだけで、固め直しが要らない（案②の弱い所を避ける）。いまの「フォルダーの形のまま動く」作りを変えなくてよい
5. 一度できあがったフォルダーは、そのままUSBメモリーで運べば、インターネットの無い場所のPCでも動く

**この案の弱い所（決める前に知っておくこと）**

- 初回だけインターネットが要る
- 埋め込み版には tkinter が無いので、**操作メニュー（`ecologger_menu.py`）と `Phone-Key.cmd` の窓は、ほかの人のPCでは動かない**。新しい入口はEcoLoggerアプリ（`SPEC.md` 8章）なので、ほかの人に渡すのはアプリだけ、と割り切る前提。メニューも渡したいなら、Pythonをふつうのインストーラーで入れる案③のほうが合う
- 埋め込み版で道具が隣のファイルを読めるようにする設定と、2段目の pip の入れ方は、**実験して確かめる必要がある**（うまくいかなければ、2段目だけ案③のやり方＝ふつうのPythonを入れる、に切り替える手がある）
- `Setup.cmd`・`.cmd` の書き換え・`ffbin` の探し先の追加・sshの鍵の道具は、これから作る

**決めてほしいこと**

1. 入れ方（案①の変形／案②／案③）
2. ほかの人に渡す範囲（アプリだけか、操作メニューや解析・動画の道具もか）
3. 回収したデータの置き場（リポジトリの中の `drive_logs\` のままか、道具と分けるか）
4. 配るPythonの版（3.12 か 3.13 のどちらかに決める）
