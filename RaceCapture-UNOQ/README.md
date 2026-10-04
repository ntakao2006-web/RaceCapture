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

`install.sh` は導入済みUNO Q用のサービス配置です。公式ARM64パッケージ、Xorg/modesetting、Mesa freedreno、x11vnc/noVNC/websockify等が必要です。専用XorgがGPUを使うため、標準ログイン画面のLightDMは停止・自動起動無効にしています。初回表示設定は `configure_display.py`、初回ダッシュボード設定はアプリ停止中に `configure_app.py` を使います。後者は作成済みのLoggerV2ページを初期配置に戻すため、ユーザーがカスタマイズした後は通常更新で実行しないでください。

描画はAdreno FD702のGPUを使用します。当初のXvfb/llvmpipeによるCPU描画は操作が重かったため廃止しました。10秒測定でアプリCPUは176.0%から38.1%へ低下し、再起動後の最終測定では19.7%でした（1コア=100%、画面・操作状態は固定した厳密ベンチマークではありません）。描画上限30fps、画面転送の待機/まとめ時間は各10ms。RaceCapture既定のDashboardスライドはKivyモジュール `fastnav.py` で0.10秒に短縮します。x11vncのXDamage更新検知を有効にし、GPUで画面を切り替えた後に古いDashboardが残る現象を防ぎます。取得100HzとSD記録は維持します。GPU構成で再起動後に5サービス・取得・SD記録が約54秒で復帰し、実アプリのFD702使用と画面復帰を確認。30秒で280サンプル、SDブロック592増加、通信/SDエラー・欠落増加0でした。

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
