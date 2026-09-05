# Linux ARM64 / Raspberry Pi 4 / ROCK 5B

## 状態

同じC#ソースからLinux ARM64版をエクスポート済みです。Linux x86_64の実環境（WSL）で、コア処理およびLinux用USB処理の擬似端末試験を実施しました。

**Raspberry Pi 4 / ROCK 5Bそのものにはまだ転送・起動していません。** GPUドライバー、USB権限、モニター／タッチ操作、実機でのメモリ・CPU・温度は要確認です。ARM64版のビルド成功を実機動作確認とは扱っていません。

## 必要な構成

- 64 bitのLinux / AArch64、glibc系ディストリビューション。
- グラフィカルデスクトップ（X11またはWayland）と、Godot Compatibility rendererを動かせるMesa等のGPUドライバー。
- RAMは4 GBを設計基準。8 GBを前提にした処理や大容量メモリ確保はありません。
- USB CDC ACMドライバーと、EcoLoggerのネイティブUSBへのアクセス権。
- 未取得の地図を見る場合はインターネット接続。

.NETランタイムは同梱しています。OSのネイティブ依存ライブラリやGPUドライバーは同梱していません。32 bit Raspberry Pi OSは対象外です。

## 起動

`EcoCapture-linux-arm64` をフォルダーごとコピーします。中の `data_EcoCapture_linuxbsd_arm64` を移動・削除しないでください。Pi 4Bでは同梱ランチャーが64-bit OS、画面、実行権限、USB権限を確認します。

```sh
cd EcoCapture-linux-arm64
sh run-raspberry-pi-4.sh
```

Pi用ランチャーはCompatibility rendererとMesaのOpenGL ES 3.0を指定します。ほかのARM64 Linuxでは`chmod +x EcoCapture.arm64 && ./EcoCapture.arm64`で起動できます。既定の描画が動かない場合、利用中のGodotビルドが対応する描画ドライバーを `./EcoCapture.arm64 --help` で確認し、`ECOCAPTURE_RENDERING_DRIVER=opengl3`などを診断時だけ指定します。Pi 4とROCK 5Bで同じGPUドライバー設定を決め打ちしないでください。

アプリは `/sys/class/tty/ttyACM*/device` の親デバイスをたどり、VID `303a` / PID `4001` のみを探します。`ttyACM0` を固定していないため番号変更後も再検出できます。書込み機の `ttyUSB*` は探索しません。

通常ユーザーがUSBを開けない場合、ディストリビューションのシリアル用グループ（Debian系では通常 `dialout`）またはデバイスを限定したudevルールでアクセス権を付け、ログインし直してください。例：

```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="4001", GROUP="dialout", MODE="0660", TAG+="uaccess"
```

システムへルールを設置する操作は移植先の管理者権限が必要です。本タスクでは移植先OSを変更していません。アプリをrootで常用する構成は不要です。

保存先は .NETのApplicationData配下の `EcoCapture`（通常 `$HOME/.config/EcoCapture`）です。変更する場合：

```sh
./EcoCapture.arm64 -- --data-dir /path/to/writable/EcoCapture
```

## 4 GBを前提にした実装

| 処理 | 制限・方式 |
|---|---|
| 描画 | GL Compatibility、30 fps上限、静止時省電力処理 |
| 表示用センサ受信 | 最大10 Hz、バックグラウンド1タスク |
| UIへの受渡し | 最新フレームだけを保持。受信履歴を蓄積しない |
| JSON入力 | 1行64 KiB上限、最大128チャンネル |
| Solve | SDを約24 KiBずつディスクへ保存。経路描画は最大20万点、画像レイヤーは最大8枚 |
| 地図 | 同時取得2、待ち24、画像保持72タイル（通常RGBAで約18 MiB） |
| 地図ネットワーク | Maps表示中にのみ新規取得。失敗後30秒待機、HTTPは8秒でタイムアウト |
| 地図ディスク | 起動時に約128 MiBへ整理。長時間走行中の追加分は次回起動時に整理 |
| 生データ記録 | アプリでは常時記録せずEcoLoggerのSDに任せる |
| IMU補完 | 最大3秒。無制限に位置履歴や推定を蓄積しない |
| USB | poll/termios。読取り50 ms、書込み500 ms上限。切断でハンドルを閉じる |

UI、プロトコル、位置／ラップ処理、OS別通信を分離しています。WindowsのレジストリやDLLをLinuxの受信経路から呼びません。日本語フォントは同梱なのでOSのインストール済みフォントに依存しません。

## 移植先で残る受入確認

1. 4 GB環境で起動し、全画面と小さい画面で文字や入力を確認。
2. 実EcoLoggerをつなぎ、Indicateとセンサ状態の受信を確認。
3. USB抜き差しで復帰し、SD記録が継続することを確認。
4. Mapsを移動させ、CPU／メモリ／GPU／温度と長時間の安定性を測定。
5. 取付軸を確定し、GNSS欠測時の補完と実コースのラップを安全な条件で検証。

一次資料：[Godot Linux export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_linux.html)、[Godot system requirements](https://docs.godotengine.org/en/stable/about/system_requirements.html)、[Microsoft .NET ARM deployment](https://learn.microsoft.com/en-us/dotnet/iot/deployment)。
