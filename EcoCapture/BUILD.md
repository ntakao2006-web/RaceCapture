# ビルドと検証

## 環境

- Godot **4.7.2 .NET** と同版の.NET export templates。
- .NET SDK 8（本環境は8.0.424）。
- Windows x64で開発・Windows export、Linux ARM64へクロスexport。

本環境のGodotエクスポートテンプレートは公式 `godot-builds/4.7.2-stable` のmono版です。ダウンロード済みアーカイブのSHA-256：

```text
92f8681e349ef1f90891b792da95e3b2b0bd1ed610b78018c58feb2d87e15a9d
```

## 通常ビルド

EcoCaptureフォルダーで実行します。

```powershell
dotnet run --project tests/EcoCapture.Tests.csproj
dotnet build EcoCapture.csproj
Godot_v4.7.2-stable_mono_win64_console.exe --editor --path .
```

Windows配布用：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1
```

Linux ARM64も生成する場合：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -LinuxArm64
```

`-Godot` でGodot実行ファイルのパスを指定できます。署名は行いません。ビルドはUSBを操作せず、既存の配布先に上書きします。実行中のEcoCaptureを終了してからビルドしてください。

## ソース配置

- `Core`：RCP疎配列デコード、設定、位置推定、ラップ、デモ。
- `Transport`：接続ライフサイクルとOS別USB処理。
- `UI`：Godot C#の画面。UI試験モードを含む。
- `tests`：Godotに依存しないコア／通信試験。
- `tools`：ビルド、実機ベンチ、実機UI試験ドライバー。
- `artifacts`：実測結果、画面、位置を含む試験設定。Git・配布物から除外。
- `dist`：生成した実行ファイルと配布ZIP。Gitから除外。

## 卓上実機試験

通常ビルドでは行いません。EcoLoggerが起動しSD記録中、車載CAN／センサCANが未接続の環境で実行します。RaceCapture/EcoCaptureなど、USBを占有する既存アプリは終了してください。PythonでPillowとpyserialが利用でき、親リポジトリの `firmware/logger_v1/tools/rcp_client.py` が必要です。

```powershell
python tools/verify_app_ui.py --output artifacts/exe-ui --uart COM8
python tools/verify_usb_reconnect.py --help
```

`verify_app_ui.py` は配布用EXEを起動し、独立した試験用設定フォルダーを使います。実機のセンサ値を受信し、表示・設定・計測・デモ切替・地図・保存を操作します。地図のオフライン試験は試験中のHTTP応答を差し替えるだけで、PC全体のネットワーク設定は変えません。

USB切断試験は書込み機の診断UARTから `testUsbReconnect` の `LOGGER_USB_ONLY` を1回だけ送り、ネイティブUSBを1秒外して復帰させます。ファーム書込み、再起動、SD停止、CAN送信は行いません。診断コマンドのないファームや、異なる機種に対しては使用しないでください。COM番号は環境に合わせて確認してください。

## Linux通信の試験

```powershell
dotnet publish tests/EcoCapture.Tests.csproj -r linux-x64 --self-contained true -c Release -o artifacts/linux-tests
```

生成した `EcoCapture.Tests` をLinux x86_64で実行します。LinuxではsysfsのID照合に加え、実際のPTY、glibc termios、pollで読み書き・切断を確認します。これはARM64ハードウェア試験の代用ではありません。

## ロガーへの操作境界

通常表示は `getVer` / `getCapabilities` / `s` / `getStatus` / USB用 `setTelemetry` を使います。Solveは `listLogs` / `readLog` / `rotateLog`、水平補正は `getLevelCalibration` / `setLevelCalibration` を使います。RaceCapture互換の既存チャンネル番号は変更していません。

ファームウェアは `firmware/logger_v1` のみを更新します。旧DevKitコード、回路図、PCB、GNSS OTPは変更しません。
