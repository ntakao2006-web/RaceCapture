# LoggerV2 / UNO Q の RaceCapture

公式 **RaceCapture App 2.19.0 ARM64** をUNO QのDebian Linux上で実行します。WindowsはUSB経由で画面を受け取り、既定ブラウザ（現在Vivaldi）で表示します。

## 開く

USBを接続すると既定ブラウザで **http://127.0.0.1:6080/** が開きます。起動には約1分かかります。手動で開く場合は `Open-RaceCapture.ps1`、再登録は `Install-USB-Autostart.ps1` を実行してください。

画面下の左右矢印、または上部の「‹ 前」「次 ›」で車両、IMU、診断、全チャンネルのページを切り替えられます。Dashboardの切替アニメーションは0.10秒に短縮しています。上部の「RaceCapture」「EcoCapture」で同じブラウザ内を往復でき、「ログ・SD」「設定」はEcoCaptureの該当画面を開きます。常に上部のRaceCaptureボタンから戻れます。Vivaldiのタブを閉じてもUNO Qの取得・SD記録は続きます。

接続はUSB ADBのTCP転送です。EthernetドライバやLAN設定は不要です。RaceCaptureはLinux側で描画し、noVNCでブラウザへ転送します。初回検証のためのCodex内蔵ブラウザは通常運用には不要です。

## 引き継いだ内容

- MCUファーム・100Hzのセンサー取得・独立SD記録を維持。
- 既存の `ecocapture-v2-data/config.json`、NCEC/CAN信号定義、ログ、SD内データを保持。
- GNSS、IMU、CAN定義と校正・四元数・SD診断を50チャンネルとしてRaceCaptureへ提供。設定したCAN信号の追加は5秒以内に反映。
- 画面への送信は最大10Hz。元のSD取得100Hzは変えません。
- RaceCapture自身のセッション記録は `/home/arduino/.config/racecapture/datastore.sq3`。既存CSV/BINは従来画面で管理し、過去ログのRaceCapture DBへの自動移行は行いません。
- LTE/Podium送信OFFを維持。2.19.0には次世代Podiumへの対応が含まれますが、ログイン、送信、実回線確認は今回行いません。

## 構成

STM32 → Arduino RouterBridge → 既存取得サービス → `rcp_bridge.py` → RaceCapture。
既存取得サービスだけがRouterBridgeを使用し、複数のRPC読出しによる取得競合を避けます。

UNO Q内の待受はRCP `127.0.0.1:7223`、画面HTTP `127.0.0.1:6080`、VNC `127.0.0.1:5902`。今回追加した画面とRCP接続はループバック限定です。

常駐サービスは `logger-v2-rcp`、`racecapture-display`、`racecapture-vnc`、`racecapture-web`、`racecapture-app`。公式アプリは `/opt/racecapture`、接続部分は `/opt/logger-v2-racecapture`、ソースは `/home/arduino/RaceCapture-UNOQ` にあります。

突然の電源断やハードリセットに備え、`logger-v2-incident-monitor` が30秒ごとに温度、メモリ、ストレージ、記録状態、主要サービス状態を `/var/lib/logger-v2-incident/current.json` へ原子的に保存します。正常停止時は終了マーカーを保存し、次回起動でマーカーが無ければ前回ブート末尾のjournalと利用可能なpstoreを `incidents/` に退避します。保存件数は直近10件に制限しています。走行ログやSDカードは変更しません。

`arduino-router-serial` は `/dev/ttyGS0` が無い間、エラー終了せず静かに待機します。USB gadgetが後から現れれば自動的にsocatへ切り替わるため、従来の約3秒周期の再起動ループとjournal汚染を避けつつ、シリアルMonitor機能は維持します。

主表示はHDMI（Linux上では`DP-1`）を想定します。接続を2回連続で確認してから出力を切り替え、1920×1080・60Hzを最優先し（2026-10-21交換後の基板では、HDMIドック経由だと1280×720で映像が出ず、1080p60で出た）、それが無い画面では1280×800・1280×720などを選んで4K等の高負荷モードを避けます。HDMI接続中はUSB画面転送を停止し、RaceCaptureは20fps上限で動作します。RaceCaptureとEcoCaptureのうち画面の裏側にあるUIプロセスだけを一時停止し、センサー取得、eMMC記録、SD記録、RCP変換は停止しません。障害記録にはHDMI接続状態、利用可能モード、GPU周波数も含めます。

`install.sh` は導入済みUNO Q用のサービス配置です。公式ARM64パッケージ、Xorg/modesetting、Mesa freedreno、x11vnc/noVNC/websockify等が必要です。専用XorgがGPUを使うため、標準ログイン画面のLightDMは停止・自動起動無効にしています。初回表示設定は `configure_display.py`、初回ダッシュボード設定はアプリ停止中に `configure_app.py` を使います。後者は作成済みのLoggerV2ページを初期配置に戻すため、ユーザーがカスタマイズした後は通常更新で実行しないでください。

描画はAdreno FD702のGPUを使用します。当初のXvfb/llvmpipeによるCPU描画は操作が重かったため廃止しました。10秒測定でアプリCPUは176.0%から38.1%へ低下し、再起動後の最終測定では19.7%でした（1コア=100%、画面・操作状態は固定した厳密ベンチマークではありません）。描画上限30fps、画面転送の待機/まとめ時間は各10ms。RaceCapture既定のDashboardスライドはKivyモジュール `fastnav.py` で0.10秒に短縮します。x11vncのXDamage更新検知を有効にし、GPUで画面を切り替えた後に古いDashboardが残る現象を防ぎます。取得100HzとSD記録は維持します。GPU構成で再起動後に5サービス・取得・SD記録が約54秒で復帰し、実アプリのFD702使用と画面復帰を確認。30秒で280サンプル、SDブロック592増加、通信/SDエラー・欠落増加0でした。

## EcoCapture DASH（車載画面、2026-11-04）

SUGO 120分耐久向けに、HDMIにはRaceCaptureアプリの代わりに見るだけの専用画面を出します（`task_sugo_20261108_breakdown.md` SG-2-6）。
出すのは今の周・ベスト比・前周と前周比（ピットを通った周は「PIT」）・ベスト・周・経過・時刻と、記録／GNSS／油温センサーの表示です。油温・水温は警告のときだけ出します：油温120℃（水温110℃）を超えたら中段が赤い帯になって温度を大きく出し、警報を1回鳴らします。
ふつうのピットは「今の周」の下の青い札（止まっている間は「PIT IN」、動き出すと「PIT OUT」）です。

| ファイル | 役割 |
|---|---|
| `ecocapture_dash.py` | 画面（Python＋GTK、Xorg `:2`）。`--demo`で作り物の走行、`--state warn`等で決まった画面（送信の印は`--state sendwait`・`sendoff`）、`--sound warn`で音だけ |
| `dash_model.py` | 表示する中身の計算（GTKなし）。試験は`python -m unittest test_dash_model` |
| `ecocapture-dash.service` | 自動起動。`racecapture-app`・`racecapture-touch`とは同時に動かない |
| `install-dash.sh` | rootで実行。DASHを入れて、今と次の電源ONからDASHにする |
| `dash_switch.sh` | `dash`／`racecapture`（`--boot`で電源ON時も）。`ecocapture-dash.sudoers`で`arduino`から使える |

警告の温度・音の出し方は`~/.config/ecocapture-dash.json`で変えられます（`dash_model.py`の`DEFAULTS`。送信の印が「未送信」になるまでの秒数は`send_stale_s`、既定5。例：`{"oil_warn": 120, "water_warn": 110, "sound": {"device": "default", "volume": 0.8}}`）。
ベスト比は、ベストの周の軌跡を`~/.cache/ecocapture-dash/lapref.json`に残し、DASHを起動し直しても続きから使います。

PCでは、WSLなどGTKのあるLinuxで`GDK_BACKEND=x11 python3 ecocapture_dash.py --state warn --size 1920x1080`のように見た目を確かめられます。

本体での確かめ方と入れ方は`tools/sugo_setup/dash_check.py`（PCから`ssh unoq`で動かす）：

| コマンド | すること |
|---|---|
| `python dash_check.py` | 入れずに確かめる。本体の`/tmp`で試験・全部の状態の描画・本物の走行データでの1枚・30秒の負荷・HDMIへの音の出口を無音で開ける。画像は`outputs/dash_check_<日時>/` |
| `python dash_check.py --sound warn --volume 0.3` | モニターをつないで、HDMIから警告音（2音の警報、約2秒）を1回鳴らす。3秒数えてから鳴る |
| `python dash_check.py --install` | 本体へ入れて、今と次の電源ONからDASHにする（rootはEcoCaptureのDockerイメージからnsenter） |

音は、本体のサウンドの4番目の出口（`plughw:CARD=ArduinoImolaHPH,DEV=3`、内部の経路`SEC_MI2S_RX Audio Mixer MultiMedia4`）から、映像変換チップANX7625のI2Sを通ってHDMIへ出す作りです（デバイスツリーの`sound/hdmi-i2s-dai-link`、2026-11-04に確認）。DASHは起動時にこの経路をつなぎ直します。PipeWireはこのサウンドを使っていません。

## 確認範囲と制限

実測ストリーム、実アプリの数値更新、アプリ内DB記録、USBブラウザ表示、既定ブラウザ起動を検証しています。証拠は `../outputs/racecapture_unoq_20261002/`。

ユーザーがVivaldiでの動作とRaceCaptureのGNSS受信を確認済みです。その後屋内へ戻ったため、性能検証中はGNSS未測位として扱います。車両CANは今回未検証です。未取得値をダミーの位置や回転数で埋めません。RCPのstatus応答の未測位座標だけは公式アプリの仕様に合わせて0とし、測位無効フラグを付け、表示・記録用のLat/Lonチャンネルには出しません。

RaceCapture Setupからのハード設定書き込み、MCU更新、LapDelta/BestLap等のラップ計算はこの変換部分では未実装です。センサー・CAN・記録設定は上部のLoggerV2設定を使用します。非対応の書込要求は成功を返さずエラーにします。RCPバージョン2.17.0は既存の互換プロトコル番号で、アプリバージョン2.19.0とは別です。

## バックアップ・元に戻す

作業前の設定・Webソースは `../outputs/racecapture_unoq_20261002/ecocapture-before-racecapture-20261002.tgz` とUNO Qの同名ファイルに保存しました。SDは変更・消去していません。元の自動起動ショートカットも同じ証拠フォルダに退避しています。

従来画面は引き続き http://127.0.0.1:8080/ から利用できます。新しいWindowsスタートアップは `RaceCapture LoggerV2 USB.lnk`、実行スクリプトは本フォルダの `Watch-RaceCapture-USB.ps1` です。

## 配布元

- 公式リリース説明: https://www.autosportlabs.com/racecapture-app-2-19-0-huge-number-of-new-features/
- パッケージ: https://autosportlabs-software.s3.us-west-2.amazonaws.com/racecapture_linux_raspberrypi_2.19.0.deb
- 取得ファイルSHA-256: `7032d8b867e9ccc94fd456d68f8dea134f90a3722ab047166d568dea60af8c64`

配布名はRaspberry Piですが、ELFがAArch64 Linux用であることを確認してUNO Qで実行しています。古い `reference/RaceCapture_App` の2016年版ソースは採用していません。
