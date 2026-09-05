# EcoCapture 0.3.7 システム要件

この文書は現在の配布版を対象にします。Windows版は実機確認済み、Linux ARM64版はビルドと通信部の擬似端末試験までで、Raspberry Pi 4／ROCK 5B実機では未確認です。

## Windows版

| 項目 | 必須 | 推奨 |
|---|---|---|
| OS | Windows 10 64 bit | サポート中のWindows 10またはWindows 11 64 bit |
| CPU | x86-64、SSE4.2対応 | 物理4コア以上 |
| RAM | 4 GB | 8 GB |
| GPU | OpenGL 3.3またはDirect3D 11対応 | 現行のIntel／AMD内蔵GPU以上 |
| 画面 | 1000×680以上 | 1280×800以上 |
| アプリ保存領域 | 500 MiB以上の空き | 2 GiB以上＋取り込む走行ログの容量 |
| USB | EcoLoggerを接続できるUSB 2.0以上のポート | 抜けにくいデータ対応ケーブル、PC本体のUSBポート |
| 入力 | マウスまたは同等のポインティング操作、キーボード | マウスとキーボード |

Windows配布フォルダーは約188 MiB、ZIPは約76 MiBです。地図キャッシュは起動時に約128 MiBへ整理します。Solveは選択したSDログをPCへコピーするため、そのログ以上の追加空き容量が必要です。

`EcoCapture.exe` はx64専用です。`.NET 8.0.30`、Godotランタイム、日本語フォントを同梱しているため、Godotや.NETを別途インストールする必要はありません。ZIPを展開し、`data_EcoCapture_windows_x86_64` をEXEと同じ場所に残してください。実行ファイルはコード署名していないため、Windows SmartScreenが確認を表示する場合があります。

## EcoLoggerと車両

- 実測にはEcoLogger `logger_v1` と、データ通信できるUSBケーブルが必要です。現在の確認済みファームは `2.17.0 / logger-v1-ecocapture-20260901j` です。
- アプリはネイティブUSBのVID `303a` / PID `4001`だけを自動検出します。書込み機CH9102のCOMポートは対象外です。
- RaceCaptureなど、同じネイティブUSBを使用するアプリとは同時に接続できません。
- GNSS、IMU、SDはEcoLogger側に必要です。車載CANは任意で、「車載CAN接続なし」ですべての基本画面を利用できます。
- 車載CAN表示には、電気的接続、フレーム受信、車種・年式に合う信号定義が必要です。現在の車種選択は表示プリセットであり、未確認のCAN IDや換算式を自動判定しません。

## ネットワーク

Indicate、Race、Solve、USB接続、SD記録はインターネットなしでも動作します。次の場合はインターネット接続が必要です。

- 未取得地域の地図タイルを表示する。
- Firebaseへ1 Hzのライブデータを送信する。
- スマートフォンや別PCから共有URLを閲覧する。

地図は取得済みキャッシュをオフラインでも利用できます。ライブ共有が失敗してもUSB表示とEcoLoggerのSD記録は継続します。

## Web閲覧側

- 最新版に近いChrome、Edge、Firefox、Safariのいずれか。
- JavaScript、Canvas、Server-Sent Eventsを利用できること。
- インターネット接続。
- FirebaseログインやEcoCaptureのインストールは不要。

共有URLはスマートフォンとPCの両方に対応します。URLを知っている人が閲覧できる方式なので、リンクは内輪だけで共有してください。

## Linux ARM64版

| 項目 | 要件 |
|---|---|
| 対象CPU | AArch64 / ARM64 |
| OS | 64 bit、glibc系Linux |
| RAM | 4 GB以上。8 GB推奨 |
| 画面環境 | X11またはWayland |
| GPU | Godot Compatibility rendererを動かせるOpenGL 3.3対応ドライバー |
| USB | CDC ACM、VID `303a` / PID `4001`への一般ユーザー権限 |
| 保存先 | `$HOME/.config/EcoCapture`、または書込み可能な`--data-dir` |

Raspberry Pi OSは64 bit Desktop版が必要で、32 bit版とLite版単体は対象外です。Bookworm以降の標準Wayland環境を基準にします。USB権限には同梱のEcoLogger専用udevルールを利用できます。`.NET`ランタイムは同梱しますが、MesaなどのGPUドライバーとOSのネイティブライブラリは同梱しません。詳細は [RPI4_SETUP.md](RPI4_SETUP.md) を参照してください。

Raspberry Pi 4とROCK 5Bへの移植を考慮して4 GBを設計基準にしていますが、両機でのGPU、USB、タッチ操作、温度、長時間安定性は未確認です。

## 実測した負荷

Windowsでの短時間測定値です。ARM機の性能保証には使えません。

| 状態 | ピークメモリ | CPU使用率 |
|---|---:|---:|
| Home | 278.5 MiB | 論理1コア比4.3% |
| Indicate | 282.9 MiB | 論理1コア比7.2% |
| Maps | 284.2 MiB | 論理1コア比6.4% |
| 全画面・Solve・地図を含むUI試験 | 393.3 MiB | 未集計 |

描画は30 fps、表示用センサ受信は最大10 Hzです。受信履歴をRAMへ無制限に保持せず、Solveの経路は最大20万点、画像レイヤーは最大8枚に制限しています。

## 開発・再ビルド要件

- Windows 10／11 x64。
- Godot 4.7.2 .NETと同版の.NET export templates。
- .NET SDK 8。本環境では8.0.424を使用。
- Windows版だけで約2 GiB、Linux ARM64テンプレートを含める場合は4 GiB以上の空き容量を推奨。

Godotが示す単純なエクスポート済みアプリの基準は、Windows 10、x86-64 SSE4.2、OpenGL 3.3またはDirect3D 11、RAM 2 GBです。EcoCaptureではOSや地図キャッシュを含む実運用の余裕を取り、4 GBを必須値としています。

参考資料：

- [Godot Engine system requirements](https://docs.godotengine.org/en/stable/about/system_requirements.html)
- [.NET supported Windows versions](https://learn.microsoft.com/en-us/dotnet/core/install/windows)
