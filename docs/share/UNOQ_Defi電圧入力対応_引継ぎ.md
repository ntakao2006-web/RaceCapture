# UNO Q の Defi 電圧入力対応と更新手順

作成日：2026年11月1日。作業場所：`C:\Users\lintaroh\Documents\RaceCapture`。

UNO Qの既存ロガーを、PICセンサハブの新しいPRESS・TEMP1・TEMP2電圧入力パケットに対応させる。今回の依頼は引継ぎ資料の作成であり、この資料の作成時点ではUNO Qのコード変更・更新・設定登録は行っていない。

## 現在の接続と作業状況

- ユーザー申告では、現在PCに接続しているのはUNO Qだけ。PIC・Snapの接続や給電を前提にしない。
- 資料作成時の `other/uno_q_tools/platform-tools/adb.exe devices -l` はデバイス一覧が空だった。更新担当者は最初に接続を回復し、`device` 状態を確認する。以前のシリアル番号 `3263089125` は候補であり、実際の一覧を優先する。
- PICファームv8はソース修正・XC8ビルド・ホスト上のパケットテストまで完了。**PICへの書き込みは未実施**。UNO Qを更新しただけでは新パケットは届かない。
- 新PICファームは `pic18f26q84_blink.X/main.c`。詳細は同ディレクトリの `README.md`。
- HEX：`pic18f26q84_blink.X/dist/default/production/pic18f26q84_blink.X.production.hex`。
- 上記HEXの作成時SHA-256：`F4238F8361CE4D4A2475EC8BCACC12AB2C6E32A040AD6FC2DE612291688B6E6E`。再ビルド時は再確認する。
- 過去のPIC油温の実機成功記録は旧仕様0x600のもの。v8の実機動作を証明しない。

## PIC側の確定仕様

対象はPIC18F26Q84の28ピン品。ピン番号は物理ピン番号。

| 信号 | 物理ピン | GPIO | ADC選択値 |
| --- | --- | --- | --- |
| PRESS | 15 | RC4 / ANC4 | 0x14 |
| TEMP1 | 21 | RB0 / ANB0 | 0x08 |
| TEMP2 | 22 | RB1 / ANB1 | 0x09 |

外部プルアップとセンサーはまだ接続されていない。PICの内部プルアップは無効。浮いた入力は0V、5V、中間電圧のいずれにもなり得るので、値だけで「オープン」「正常接続」と断定しない。

ADCは12bit、VDD/VSS基準。各入力で切替後100µs待機し、最初の変換を捨てて32回平均。電圧は `ADC × 実際のVDD / 4095`。5.000Vを使う換算値は公称値に基づく推定で、PICはVDD自体を測定していない。入力までの外部回路の倍率も未確定。

温度用のプルアップ抵抗値とPRESSの電圧対圧力特性は未確定。温度℃や圧力kPaへは換算しない。Defiの表示レンジを入力の電圧特性として流用しない。

Defi参考資料：[DIN Gauge Style21 Style98取扱説明書](https://defi.nippon-seiki.co.jp/wp-content/uploads/2025/03/manual_dinstyle21_98.pdf)。実装する通信仕様は次の表とローカルPICソースを正とする。

## CANパケット

Classic CAN、500kbit/s、標準ID **0x580（十進1408）**、DLC=8、約10Hz。UNO Q側では外部センサハブ用の**CAN2**を使う。PICはRB2（23番）TX、RB3（24番）RXを維持。

| バイト位置 | 内容 |
| --- | --- |
| 0–1 | PRESS ADC、uint16 little endian、0〜4095 |
| 2–3 | TEMP1 ADC、同上 |
| 4–5 | TEMP2 ADC、同上 |
| 6 | bit0/1/2：PRESS/TEMP1/TEMP2が4以下。bit3/4/5：同じ順で4091以上。bit6/7：0 |
| 7 | プロトコルバージョン1 |

レール近傍フラグは電圧の上下端だけを表す。断線・短絡を証明しない。フラグなしでも浮いた入力の可能性がある。

例：ADCがPRESS=0、TEMP1=2048、TEMP2=4095のとき、データは `00 00 00 08 FF 0F 21 01`。公称5V換算は約0V、2.501V、5V。

旧0x600の「int16温度＋ADC＋抵抗値」はv8では送信しない。`sensorhub_oiltemp` デコーダに0x580を流さない。

## UNO Q側の構成と変更箇所

データ経路はSTM32 → Arduino RouterBridge → EcoCapture取得サービス → 表示・記録・RCP → RaceCapture。RouterBridgeの取得担当は既存サービス1つに保つ。

| 対象 | パス | 対応内容 |
| --- | --- | --- |
| STM32ファーム | `firmware/ecologger_v2/logger_impl.h` | 既存のCAN2受信を確認。現ソースはIDを固定せず生フレームを渡し、CAN2はnormalモードでACKする。新IDのためだけの変更・再書き込みは原則不要 |
| デコード | `EcoCapture-Web/hardware.py` | 0x580の長さ・version・ADC範囲・予約bitを検証する専用処理を追加。データ不正時は前回値を正常値として保持しない |
| 設定モデル | `EcoCapture-Web/models.py` | 専用conversionを追加する場合はLiteralとレイアウト検証も対応 |
| 設定登録 | `RaceCapture-UNOQ/Configure-OilTemp.ps1` を参考に新規手順作成 | 既存設定をGETして、対象信号だけ追加・更新。旧スクリプトは0x600専用なので今回そのまま実行しない |
| Web表示・記録 | `EcoCapture-Web/web/app.js`、関連サーバー処理 | 電圧／ADCと状態を表示。無受信は欠測にする |
| RaceCapture接続 | `RaceCapture-UNOQ/rcp_bridge.py` | 新チャンネルと状態を公開。既存は設定信号を動的に取り込む。自動追加されるState/Openは旧油温conversion限定なので新形式の状態公開を実装・確認 |
| ネイティブ表示 | `RaceCapture-UNOQ/ecocapture_native.cpp` | 使用している画面に新信号を表示。油温℃の欄への誤表示を避ける |
| テスト | `EcoCapture-Web/test_hardware.py`、`RaceCapture-UNOQ/test_bridge.py` ほか | デコード、欠測、状態、RCPの試験を追加 |

MCUのCAN1はlisten-onlyのままにする。CAN2は送信アプリを追加せずnormal受信でACKできる状態を保つ。GNSS・IMU・独立SD記録・既存CAN定義・ユーザーの画面設定を保持する。

### 表示と設定の提案

初期名は `PressVolt`、`Temp1Volt`、`Temp2Volt`、単位V。必要なら `PressADC`、`Temp1ADC`、`Temp2ADC` も公開する。TEMP1とTEMP2を油温・水温のどちらかに決めつけない。

基本レイアウトはCAN2、標準0x580、uint16、little、オフセット0/2/4。公称電圧のscaleは `5.0 / 4095.0`、offset=0。ただしlinear設定だけではDLC/version/ADC範囲を検証できないため、正式対応では専用デコーダを通す。

新状態は少なくとも「未校正」「下限付近」「上限付近」「データ異常」「通信途絶」を区別する。無受信が1秒を超えたら数値はnullにする。未校正は電圧取得の故障ではなく、物理量換算や接続状態を確認できていないことを表す。

旧OilTempの0x600登録は、実機の既存設定をバックアップしてから旧式と分かるよう無効化・整理する。今回の電圧をOilTempへ上書きして℃で表示しない。

## 更新担当者の手順

### 1 接続確認と退避

PowerShellでリポジトリルートから実行する。

```powershell
$adb = '.\other\uno_q_tools\platform-tools\adb.exe'
& $adb devices -l
# 一覧の実機シリアルを設定する
$serial = '実機のシリアル'
& $adb -s $serial get-state
& $adb -s $serial forward tcp:8080 tcp:8080
Invoke-RestMethod http://127.0.0.1:8080/api/status
```

`device`になるまでは更新しない。空一覧なら電源・データ対応USBケーブル・ポート・起動待ちを確認する。サービスが動くことを確認したら、`/api/config`、使用中のソース、設定フォルダー `/home/arduino/ecocapture-v2-data` と画面設定を退避する。退避には新しい日時付きフォルダーを使い、既存のバックアップを上書きしない。

実機側の `/home/arduino/EcoCapture-Web`、`/home/arduino/RaceCapture-UNOQ`、`/home/arduino/ecologger_v2` とPC側を比較する。PCが最新と決めつけず、実機の追加修正を保つ。記録中なら停止してから更新し、作業前の記録状態を記録する。

### 2 実装と机上試験

上記デコーダ・表示・設定登録を実装して必要なテストを通す。最低限、正常パケット、ADCの4/5/4090/4091境界、DLC違い、version違い、ADC>4095、予約bit非ゼロ、矛盾するレールフラグ、RTR、拡張ID、CAN1の同ID、1秒超の途絶、MCU時刻巻き戻りを確認する。

試験値を使うときはテストコード内に限定し、実機の取得値として画面・ログに混入させない。PICがない現在は、実受信件数0・電圧欠測・通信途絶が期待値。

### 3 UNO Qへの反映

既存更新入口は以下。これは実行例であり、この資料作成時には実行していない。

```powershell
# EcoCapture側のみ。実装・試験・退避・記録停止のあとに実行
.\EcoCapture-Web\Update-UNOQ.ps1 -Serial $serial
```

このスクリプトはEcoCaptureの転送・ビルド・サービス配置も行う。**RaceCapture-UNOQ側の変更はこのコマンドだけでは配布されない**。変更したRCP・ネイティブUIを別途ビルド／配置し、導入先 `/opt/logger-v2-racecapture` とサービス `logger-v2-rcp` 等を確認する。`RaceCapture-UNOQ/install.sh` は複数サービスや画面設定を更新する広い導入処理なので、差分を読んで必要な更新だけを反映する。`configure_app.py` で既存ダッシュボードを初期化しない。

STM32側の修正が実際に必要になった場合に限り、次を使う。

```powershell
.\EcoCapture-Web\Update-UNOQ.ps1 -Serial $serial -Firmware
```

`-Firmware`は単なるビルドではない。`build-mcu.sh`経由でSTM32への書き込みまで実行する。実機ソースの退避は更新スクリプト内にもあるが、設定と復旧用の既知良好ファームは別途確保する。

### 4 確認と復旧

更新後は `/api/status`、`/api/telemetry`、EcoCapture画面、RaceCaptureの新チャンネルを確認する。UNO Q単体では新信号が欠測になり、GNSS/IMU/既存チャンネル・記録系に回帰がないことを確認する。

後日、PICにv8を書き込んでCAN2へ再接続したら、0x580標準DLC8・約10Hzの実受信、`can_counts[1]`の増加、CAN2モード、overflow・bridge error・記録欠落の増加なしを確認する。既知電圧とテスターで3入力を照合して、ピンの取り違えと公称VDD換算の誤差を確認する。プルアップ未接続の値を校正データにしない。

問題があれば退避したサービスのソース・設定へ戻し、変更したサービスだけを再起動する。STM32を書き換えた場合は既知良好ファームへ戻す。SDのFORMAT・ログ削除・OS再インストールは復旧手段にしない。

## 完了時に残す記録

UNO Qの実機シリアル、反映ファイルと版、退避先、設定差分、テスト結果、単体確認結果を残す。「UNO Q更新済み」「PIC v8未書き込み」「PIC接続による実CAN検証未実施」を別々に記録し、未確認事項を完了扱いにしない。
