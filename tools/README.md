# 道具の案内（tools/）

道具ごとの説明。`CLAUDE.md`の「ファイル構成」にあった文面を2026-11-13にここへ移した（文面はそのまま）。
**道具を足した・入口や置き場所を変えたときは、ここを直す。** 資料の説明は`docs/README.md`、道具をこの先どうまとめるかは`SPEC.md` 8章。

## フォルダーの一覧

| フォルダー | 中身 |
|---|---|
| `ecologger_menu/` | PCの操作メニュー（デスクトップの「EcoLogger Ver.2」）。下に説明 |
| `video_collect/`・`collect_logs/` | 走行ログ・動画の回収。下に説明。**本体とのつなぎ方の共通の部品`collect_logs/unoq_link.py`**（USB → テザリングを自分で探し、つながらない理由と直し方を返す。本体につなぐ道具を足すときはこれを使う）もここ |
| `race_analysis/` | 大会後の走行解析。下に説明 |
| `lap_video/` | 1周だけの動画・切り抜き。下に説明 |
| `sugo_setup/` | Ver.2をSUGO用の設定へ切り替える道具、DASHの確かめ（`dash_check.py`）。説明は`docs/README.md`の`sugo_day_manual_20261108.html`の項目 |
| `setups/` | **車の設定とコースの設定**（`vehicles/*.json`・`courses/*.json`）と、形を確かめる・本体や控えと比べる道具`setups.py`（読むだけ）、違う所だけを本体へ入れる道具`setups_apply.py`（既定は確かめるだけ。本体で使うのは展示のあと）。SP-4 |
| `remote_command/` | ピットからLTEで決まった命令を送る（PC側）。本体側は`EcoCapture-Web/remote_command.py`。スマホへ合言葉を渡すQRは`Phone-Key.cmd`（`phone_key.py`、QRの絵は`qr.py`）。合言葉の作り直しは`setup --new` |
| `video_hud/`・`lens_view/`・`video_exposure/` | 焼き込みの計器・レンズの補正・露出の設定をPCから見る・送る。説明は`unoq_video_check_procedure.md` 5-14・5-19・5-21 |
| `unoq_overlay_enc/` | **本体の録画のソフト**（走行映像への計器の焼き込み）。本体へ入れるスクリプトがこの場所を見ているので動かさない |
| `home_telemetry/` | 自宅のサーバーに入れるもの（LTEの値の受け取り・ピットのページ）。`deploy/`の説明は`server_deploy_grafana_x86.md` |
| `dev/` | 開発・調べもの用：`race_replay`（エミュレーターでの走行の再生）・`podium_replay`・`unoq_spi_sd_test`（E-6の試験）・`lte_antenna`（電波の記録。操作メニューの「設定・調べもの」から呼ぶ）・`can1_loss`（車載CANの取りこぼしを数える） |

通話の道具（`voice_gate`・`discord_bridge`）は`archive/voice/`、エコランの記録表は`ecorun/record_sheet/`へ移した（2026-11-13）。

## 道具ごとの説明

- `tools/ecologger_menu/`：**Ver.2の操作メニュー**（デスクトップの「EcoLogger Ver.2」、作り直しは`Make-Shortcut.cmd`）。本体の状態を30秒ごとに表示し、窓にはふだん使うもの（回収・HDMIの画面の切り替え・ラップのリセット・LTEで状態を聞く）だけを出す。HUD・レンズ・露出・電波・LTEのほかの命令は「設定・調べもの（ふだんは触らない）…」で開く別の窓（2026-11-11）。つなぎ方はUSBのadb→テザリングのssh。つながらないときの記録は`%USERPROFILE%\.ecologger\ecologger_menu.log`（PC側の合言葉・前回のIPも同じ場所。**`%LOCALAPPDATA%`はClaudeのアプリから動かしたときだけ`Packages\Claude_*\LocalCache\Local`へ振り替えられ、ショートカットから開いた道具と食い違うので使わない**。adbもその振り替え先にある）。**新しい`.cmd`を作ったらここの`TOOL_GROUPS`（設定・調べものの窓）にも足す。ふだんの窓へは足さない**。「LTEで」のボタンは`tools/remote_command/remote_command_pc.py`（ピットからLTE経由で決まった命令を送る。本体側は`EcoCapture-Web/remote_command.py`、合言葉はPCと本体にだけ置きリポジトリに入れない）
- `tools/video_collect/EcoLogger-App.cmd`：**PCの新しいアプリ（作りかけ、SP-3）**。下の回収アプリに「コースと線」の段（`course_lines.py`・`course_lines.js`：航空写真の上の線の図と引き直し）、「走行を見る」の段（`run_index.py`：回収した走行を走った日ごとに並べ、同じ時刻の動画を結ぶ索引）、「いまの様子」の段と操作（`app_ops.py`：ラップ・LTEの命令・合言葉・QR）を足したもの（`now_status.py`。ロガーが無くても開き、つなぐと自分で切り替わる）。本体なしで画面を見る道具は`dev_app.py`
- `tools/video_collect/Collect-Video.cmd`：**走行ログ・動画の回収アプリ**（回収の入口はこれ1つ。`tools/collect_logs/Collect-Logs.cmd`も引数なしならこの画面を開く。メニューのボタンは「走行ログ・動画を回収」）。**「回収する」ボタン1つで、本体の走行記録（eMMC）・本体の動画（USBのときだけ）・PCに挿したSDカードを、まだPCに無いものだけ取り、どれも消さない**（`collect_everything`。手順は「USBでつないで回収する→電源を切ってSDを抜き、カードリーダーへ挿してもう一度回収する」の2段、`unoq_video_check_procedure.md` 5-28）。走行記録とSDは`drive_logs/<日付>/runNN_<時刻>/`。下の細かい操作は画面の「詳しい操作」に畳んである。ネット不要（USB直結のadb、予備にテザリングのssh）。走行ごとの一覧・あと何分録れるか・吸い出し（本体とPCのSHA-256を比べて本体に回収済みの印）・本体から消す（印のあるものだけ）・保護・1本につなげる・控え。保存先は`drive_logs/v2_video/<走行>/`。`Collect-Logs.cmd`の動画の回収も同じ処理。**シールドのSDカード**（PCのカードリーダー）の確かめる・回収・空にする・フォーマットもここ（`sd_card.py`）。SDの回収済みは中身で見る（`drive_logs/v2_sd_index.json`）
- `tools/race_analysis/`：**大会後の走行解析**（SG-5-3）。`race_analysis.py <設定.json>`が本体のCSVと5BのLTEの記録の写しから、周・セクター・油温・油圧×G・水温の照合・燃料・周の比較（道のり）・コーナー・ギア・タイヤの滑り（車体の横滑り角＝GyroZの積分とGNSSの進む向きの差、後輪の空転、前輪のロックぎみ）・ロガーの採点を出す。**ログの`Yaw`の列は車の向きではなくGNSSの進む向き**なので、車の向きが要るときは`GyroZ`から出す。大会ごとの決めごと（ライン・決勝の周・スティント・ピット・出来事の周）は設定ファイル（例`sugo_20261108.json`）、出来事の周の下調べは`lap_survey.py`。**11/9より前の本体の記録はGNSSの位置が1秒に約6回しか変わらない**ので、回収したシールドのSDがあれば設定に`sd_dir`を書いてSDの解（10Hz全部）で置き換える（`sd_gnss.py`、例`sugo_20261108_sd.json`）。出力は位置を含むので`drive_logs/<日付>/analysis/`。レポートのページ（Claudeのダッシュボード）の本体は`report_page.html`
- `tools/lap_video/`：**走行映像から1周だけを切り出し、風切りを下げた公開用のMP4を作る**（PCで動かす。`lap_video.py laps <日付>`で周の一覧、`clip <日付> --best`か`--lap N`）。周の数え方は`tools/race_analysis`と同じ。風切りは記録の回転数でエンジンの倍音だけを残し、間を下げる（`wind_reduce.py`、ユーザーが聴き比べて決めた「8番」の設定。ふつうの雑音取りは効かなかった）。出力は`drive_logs/v2_video/laps/`。ffmpegはwingetの`Gyan.FFmpeg`。手順は`unoq_video_check_procedure.md` 5-25。**スピン・コースアウト・後ろが出た所の切り抜きを1本につなぐ**のは同じ場所の`incidents.py`（`find`で候補→`sheet`のコマで本物を選んで設定の`clips`へ→`build`。例`incidents_sugo_20261107-08.json`、出力`drive_logs/v2_video/incidents/`、手順5-26）
- `tools/dev/imagery_check/imagery_check.py`：航空写真の位置の正しさを、走った跡を重ねて測る（SP-4-12）。SDの10Hzの解（`sd_gnss.py`が作る`sd_nav.pkl`）を国土地理院とEsriの写真に重ね、舗装とのずれを数える。出力は位置を含むので`drive_logs/`の下へ出す
- `tools/home_telemetry/home.html`：**ピットの表紙**（スマホで開く入口。SP-6-1・SP-6-3、2026-11-13）。いまの要点・ほかの画面への行き先・合言葉を入れた人のロガーへの操作（今ある5つの命令）。`live_bridge.py`が`/home`と`/`で出す。**自宅のサーバーにはまだ入れていない**（了承のあと）。PCの中だけで確かめるのは`tools/home_telemetry/dev_home.py`（作りものの車と中継。`websockets`が要る）
