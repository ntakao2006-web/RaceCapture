# Raspberry Pi 4Bへの導入

## 対象

- Raspberry Pi 4 Model B（4 GB以上を推奨）
- Raspberry Pi OS 64-bit Desktop。32-bit版や画面環境のないLite版単体は対象外
- HDMIまたはDSI画面、1000×680以上
- EcoLoggerのUSB-OTGをPiへ接続。A105はアプリ接続には使用しない

Pi 4Bは64-bit ARMv8とOpenGL ES 3.0に対応し、Godot 4.7の最小CPU例にも挙げられています。先行するLinux ARM64版はPi 4B実機のX11環境で起動とUI描画まで確認済みです。0.3.7配布物そのものの起動回帰とEcoLogger USB接続はまだ未検証です。

## 最短手順

1. `EcoCapture-0.3.7-linux-arm64.zip`をPi上の書込み可能なフォルダーへ展開する。
2. 展開フォルダーで次を実行する。

```sh
sh run-raspberry-pi-4.sh
```

ランチャーはaarch64、画面セッション、実行ファイル、USB権限を事前確認し、Pi 4のMesa向けにGodot Compatibility + OpenGL ES 3.0で起動します。.NET 8ランタイムは同梱済みです。

## EcoLoggerのUSB権限

権限エラーが出る場合は、同梱の`99-ecologger.rules`を管理者がudevへ設置します。

```sh
sudo install -m 0644 99-ecologger.rules /etc/udev/rules.d/99-ecologger.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

その後EcoLoggerのUSB-OTGを抜き差しします。ルールはVID `303a` / PID `4001`だけを対象にし、A105/CH9102へ権限を広げません。アプリをrootで常用しないでください。

## 初回確認

```sh
uname -m
ls -l /dev/ttyACM*
```

`uname -m`が`aarch64`であることを確認します。EcoCaptureの設定で車体を選び、「EcoLogger 接続中」とネイティブUSBのデバイス名、更新するセンサ値を確認します。車両OBD要求は停車中に明示操作した場合だけ開始してください。

地図とライブ共有以外はインターネットなしで動作します。設定・地図キャッシュ・取得ログは通常`$HOME/.config/EcoCapture`へ保存されます。別の書込み可能な場所を使う場合：

```sh
sh run-raspberry-pi-4.sh --data-dir /path/to/EcoCapture-data
```

## まだ必要なPi実機試験

- 0.3.7配布物の起動回帰、Wayland上での文字・マウス・タッチ、全画面表示
- EcoLogger USBの抜き差し復帰と、その間のSD記録継続
- Maps/Solveを含むCPU、メモリ、GPU、温度、長時間安定性
- 電源瞬断をUSB切断と取り違えないこと

一次資料：Raspberry Pi公式OS資料、Raspberry Pi 4B Product Brief、Godot 4.7 system requirements、Godot 4.7 rendering architecture。
