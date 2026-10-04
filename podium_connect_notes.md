# Podium / Podium Connect 現状まとめ（EcoLogger Ver.2 対応検討用）

> EcoCapture / EcoLogger の開発チーム共有用。「Ver.2ロガーでPodium Connectを使えるように
> したい」という要望に対して、**いま何が分かっていて、何が未確認で、どの経路を採るのが
> 現実的か**を1枚にまとめたもの。
>
> 出典は本リポジトリ内の実測記録と、`reference/`配下に取り込んである公式ソース
> （RaceCapture-Pro firmware / RaceCapture App）の実コード。
> 推測・未確認の箇所は必ず「⚠️未確認」と明記している。
>
> 作成日：2026-09-15

---

## 0. 先に結論

1. **「Podium Connect」という呼び方が2つの別物を指しているので、まずそこを分ける必要がある。**
   - ①クラウドサービス **Podium（`podium.live`）** ＋そこへ流し込むための**ライブテレメトリー機能**
   - ②Autosport Labs が売っている**セルラー内蔵のハードウェア製品「PodiumConnect」**

   公式RaceCaptureアプリの設定画面が「Podium Connect」という名前なので、
   実際にやりたいことは**ほぼ確実に①**。②の実機は必要ない見込み。
2. **①のプロトコルは完全に判明している。** 送信先は `telemetry.podium.live:8080`、
   改行区切りのJSONを平文TCPで投げるだけ。認証・チャンネル定義・サンプル送信の
   3種類しかない（3章）。**Ver.2ロガー（UNO Q）のLinux側から直接喋れる。**
3. **Ver.1（ESP32）では、公式アプリ経由でのPodium表示まで実機で動作確認済み**。
   ストリーミングキーの保存（`setConnCfg`/`getConnCfg`）もファーム側に実装済みだが、
   **実機での保持確認だけ未実施**（4章）。
4. **Ver.2で採るべき経路は「UNO Q自身がPodiumクライアントになる」（経路A）を推奨**。
   PCも公式アプリもPodiumConnect実機も要らなくなる。実装量は数百行規模（5章）。
   🔴 **2026-09-21追加：そのクライアントはLinux側である必要がない。STM32側で完結できる（経路A'、5章）。**
   LTEモデムはSTM32のUARTへ直結する設計に決まっており（`hardware_ans_20260921.md`のP-3）、
   **モデム内蔵のTCP/IPスタックをATコマンドで叩けばMCUだけでPodiumへ送れる。**
   公式RaceCaptureファーム自身がその作りになっている（5章の経路A'に根拠）。
5. **最大の注意点は「平文TCP・TLSなし」「10Hz固定」「チャンネル名はASCII前提」「車載回線が別途必要」** の4点（6章）。

---

## 1. そもそもPodiumとは何か

### 1.1 Podium（`podium.live`）＝ Autosport Labs のクラウドサービス

RaceCapture（Autosport Labs製の車載データロガー）のエコシステムの一部。

- 走行中のテレメトリーを**リアルタイムでクラウドへ送り、ブラウザから見られる**
- 「誰が今どこを走っていて、水温が何度か」をピット／自宅から見る用途
- イベント（Ad Hoc イベント）を作って、その下に走行を紐づける
- 走行後のログのアップロード・解析・共有もできる
- 各ロガーには **Device ID（＝UI上の「ストリーミングキー」）** が発行され、
  これがそのまま認証情報になる

本リポジトリでは、ダッシュカム構成の調査時に
「YouTube Live の映像とPodiumのライブテレメトリを同一画面に埋め込める」ことまで確認済み
（`DASHCAM_STREAMING_RESEARCH.md` 3章 項目10）。

### 1.2 PodiumConnect（ハードウェア製品）

**セルラー通信を内蔵した接続機器**で、スマホやPCを介さずにロガーのデータを
直接 `podium.live` へ送るためのもの。公式RaceCaptureアプリのセットアップ画面
「Device」タブに `PodiumConnect MK2` のカードが並ぶことを、こちらの実機検証で
目視確認している（`task_phase4_breakdown.md` 4-4-2 の描画復旧実験のスクリーンショット）。

> ⚠️**未確認**：PodiumConnect実機が「ロガーからデータをどう受け取るか」
> （WiFi APになるのか／シリアル接続なのか／純正RaceCapture本体としか繋がらないのか）は、
> 本リポジトリ内に一次情報がない。**自作ロガーを繋げられる保証はない**ので、
> 実機購入を検討する場合はここを先に確認する必要がある。

### 1.3 重要：ライブテレメトリーに PodiumConnect 実機は要らない

ダッシュカム調査の結論として、既に明記してある
（`DASHCAM_STREAMING_RESEARCH.md` 4.1節）：

> **PodiumConnectは不要**。②のライブテレメトリーは、PodiumConnect機のような
> 内蔵セルラー通信ではなく、**PC自体が持つインターネット接続を使って
> RaceCaptureアプリが中継する**、という昔からある仕組みを流用する

つまり **「インターネットに出られる何か」＋「Podiumのプロトコルを喋る実装」があれば足りる**。
Ver.2ではその「何か」も「実装」も UNO Q 側で完結できる。

### 1.4 用語の対応表

| 呼び方 | 実体 | Ver.2で必要か |
|---|---|---|
| Podium / podium.live | クラウドサービス本体 | **必要**（アカウントとデバイス登録） |
| ライブテレメトリー / Send Telemetry | ロガー→クラウドへ流す機能 | **必要**（実装対象） |
| ストリーミングキー / Device ID | 認証トークン（文字列） | **必要**（設定項目として持つ） |
| PodiumConnect (MK2 等) | セルラー内蔵のハード製品 | **不要の見込み**（1.2の⚠️確認後に確定） |
| RaceCapture MK2/MK3/MK4 | 純正ロガー本体 | 不要（EcoLoggerが代替） |

---

## 2. いまEcoLoggerがどうなっているか（出発点）

| | Ver.1 | Ver.2（計画） |
|---|---|---|
| ロガー本体 | ESP32（XIAO ESP32C3 / ESP32-S3） | Arduino UNO Q（Linux側＝Cortex-A53×4、MCU側と二段構成） |
| PCとの接続 | USB CDC（RCP JSONプロトコル） | 同等＋Linux側の自由度 |
| 表示アプリ | 公式RaceCaptureアプリ／自作 EcoCapture | 同左 |
| ネット接続 | 無し（PC/スマホ側に依存） | **UNO Q自身が持てる見込み**（⚠️要確認：Q-4） |
| ライブ共有 | EcoCapture Live（Firebase、1Hz、`EcoCapture/cloud/`） | 同左＋Podium |

Ver.1はUSBでPC/スマホに繋ぐ前提だったので、Podiumへ出すには必ず
「公式RaceCaptureアプリを中継役として動かす」必要があった。
**Ver.2ではUNO QのLinux側がネットに出られるため、この制約が外れる。** ここが今回の要点。

---

## 3. Podiumテレメトリープロトコル（判明済み・実装に必要な全て）

出典：

- アプリ側：`reference/RaceCapture_App/autosportlabs/telemetry/telemetryconnection.py`
- ファーム側：`reference/RaceCapture-Pro_firmware/src/devices/cellular.c`（`auth_telem_stream`）、
  `.../src/logger/loggerApi.c`（`api_send_sample_record`）、
  `.../include/logger/loggerConfig.h`（既定のホスト・ポート）

### 3.1 トランスポート

| 項目 | 値 |
|---|---|
| ホスト | `telemetry.podium.live`（`DEFAULT_TELEMETRY_SERVER_HOST`） |
| ポート | `8080`（`DEFAULT_TELEMETRY_SERVER_PORT`） |
| プロトコル | 生のTCP。**TLSなし・平文** |
| フレーミング | 1メッセージ＝1行のJSON、**`\n` 区切り**（アプリ側は `set_terminator("\n")`） |
| 文字コード | ASCII（アプリは `msg.encode('ascii')`） |
| ホスト/ポート変更 | 可（公式ファームは `telCfg.host` として保持） |

### 3.2 ① 認証（接続直後にクライアントから送る）

スキーマが2系統ある。**サーバはどちらも受け付けている**（アプリと純正ファームで別物を送っているため）。

アプリ版（schemaVer 2）:

```json
{"cmd":{"schemaVer":2,"auth":{"deviceId":"<ストリーミングキー>"}}}
```

純正ファーム版（旧スキーマ、情報が多い）:

```json
{"auth":{"deviceId":"<key>","apiVer":2.0,"device":"<機種名>","ver":"<FWバージョン>","sn":"<シリアル>"}}
```

サーバ応答:

```json
{"status":"ok","utc":<UNIX時刻>,"lt":<last tick>}
```

- `status` が `"ok"` 以外なら認証失敗＝キーが誤り。アプリは即切断し
  「Podium: invalid device id」を出し、**リトライしない**（無限リトライ防止）
- `utc` / `lt` は純正ファームが再開位置の同期に使っている。必須ではない

### 3.3 ② チャンネル定義（meta）— 認証成功後に必ず1回送る

```json
{"s":{"meta":[{"nm":"Coolant","ut":"F","sr":1,"min":0,"max":300},
              {"nm":"MAP","ut":"KPa","sr":5,"min":0,"max":110}]}}
```

| キー | 意味 |
|---|---|
| `nm` | チャンネル名（グラフの系列名になる） |
| `ut` | 単位文字列 |
| `sr` | サンプルレート[Hz] |
| `min` / `max` | 表示レンジ |

- **この配列の並び順が、次のサンプル送信のビット位置と1:1で対応する**（最重要）
- チャンネル構成が変わったら**metaを送り直す**。アプリは実際にそうしている
  （`_on_meta` → `_send_meta`）

### 3.4 ③ サンプル送信（100ms周期）

```json
{"s":{"d":[<値1>,<値2>,...,<ビットマスク1>,<ビットマスク2>]}}
```

- `d` 配列は「**その回に値があったチャンネルの値だけ**を meta の順に詰め、
  **末尾にビットマスク（32ビット＝32チャンネル分）を並べる**」という可変長形式
- ビットマスクの `bit n` が立っている＝そのチャンネルの値が `d` に入っている
- チャンネル数が32を超えるとビットマスクが2語、64超で3語…と増える
  （公式ファームは最大10語＝320チャンネルまで）
- **送信周期はアプリ側 `SAMPLE_INTERVAL = 0.1`（10Hz）固定**
- 純正ファームは `{"s":{"t":<tick>,"d":[...]}}` と `t`（連番）を付けるが、
  アプリは付けていない。**`t` は必須ではない**

### 3.5 再接続・エラー処理（アプリ実装の挙動）

| 事象 | 挙動 |
|---|---|
| 切断検知 | 指数バックオフで再接続（0.1秒 → ×10 → 上限10秒） |
| 認証失敗 | `_auth_failed` を立てて**リトライ停止**（キー誤りで叩き続けない） |
| 接続確立 | auth → `status:ok` → meta → 100msタイマー開始、の順序を厳守 |
| ソケット待ち | `asyncore.loop(timeout=3)`（切断検知を30秒→3秒に短縮している） |

### 3.6 まとめると、Ver.2が実装すべきものは

```text
TCP connect(telemetry.podium.live:8080)
  → {"cmd":{"schemaVer":2,"auth":{"deviceId":KEY}}}\n
  → 受信 {"status":"ok",...}
  → {"s":{"meta":[...]}}\n
  → 以後 100ms ごとに {"s":{"d":[...]}}\n
  → 切断されたら指数バックオフで再接続（認証失敗時を除く）
```

**これだけ。** 依存ライブラリはソケットとJSONのみ。

---

## 4. Ver.1（ESP32）で既に分かっていること・ハマったこと

Ver.2でも同じ地雷を踏む可能性があるので、そのまま引き継ぎたい項目。

### 4.1 公式アプリはUSBデバイスを VID/PID でフィルタしている

- Espressif既定の VID `0x303A` / PID `0x4001` のままでは、
  公式RaceCaptureアプリ（Android版）が**エラー表示すら出さず完全に無反応**だった
- 公式MK3ファームの値（VID `0x16D0` / PID `0x07F1`）に合わせたところ、
  アプリが自動認識し、**Podium Connect設定・LiveTelemetry表示まで到達**した
- Ver.2でも「公式アプリを中継役に使う」経路（経路B）を残すなら同じ対応が要る
- ⚠️**注意**：この VID/PID は Autosport Labs のもの。プライベート検証としての一時借用であり、
  **配布・公開する構成では `pid.codes`（VID `0x1209`）等で自前PIDを取得すべき**
  （`task_phase1_breakdown.md` 1-4-4 の倫理注記）

### 4.2 ストリーミングキーの保存（`setConnCfg` / `getConnCfg`）

- 公式アプリは接続設定を `connCfg` として読み書きする。応答は
  **`btCfg` / `cellCfg` / `telCfg` の3ブロック構成**
- **ストリーミングキーは `telCfg.deviceId`** に対応する
- Ver.1ファームはここが**ダミー応答のままだった**ため、
  「接続のたびにストリーミングキーを再入力させられる」という症状が出ていた（原因特定済み）
- 1-4-7 で `telCfg.deviceId` のみNVSへ永続化する実装を入れた
  （`firmware/src/main.cpp` の `ConnCfg` 周辺）。
  Bluetooth / Cellular は本プロジェクトでは持たないので常に無効固定
- アプリが `{"setConnCfg":{"connCfg":{...}}}` と**一段ラップして送ってくる場合がある**ため、
  ラップ有無どちらでも受理する実装にしてある
- ⚠️**未確認**：**再接続後にキーが本当に保持されるかの実機確認は未実施**。
  Ver.2で同等機能を作る場合、ここは最初に実機で潰しておきたい

### 4.3 公式アプリ側のバグ（対策不可と結論済み）

- USBを一度抜いてロガーが再起動すると、**2回目の接続でLiveTelemetry画面がフリーズ**する
- adb logcat で解析した結果、**アプリ内部のサンプル送信ワーカースレッドが
  USB切断を境に二度と再開しない**ことを確認。ロガー側ファームは正常だった
- **公式アプリ（Android/Kivy版）の状態管理バグと特定、対策不可**と結論
  （Windows版の「COMポートハンドルリーク」と同種）
- → **経路B（公式アプリ中継）は、この既知バグを抱えたまま運用することになる**。
  経路Aを推す理由のひとつ

### 4.4 その他

- `getStatus` のコマンド分岐がファームに無く、アプリの `StatusPump` が
  接続直後から恒常的にタイムアウトし続けていた（1-4-8で対応済み）
- Raspberry Pi版RaceCaptureアプリでも、ネットワーク経由のPodiumライブテレメトリーは
  動作実績あり（公式Wiki・開発者Brent Picasso氏の回答で確認済み）
- スマホ版RaceCaptureアプリでの podium.live 中継 ＋ PC版 Podium での監視は、
  **ユーザー自身が既に実動作を確認済み**（`task_dashcam_breakdown.md` DC-8）

---

## 5. Ver.2で採り得る3つの経路

### 経路A：UNO Q自身がPodiumクライアントになる 【推奨】

```text
[EcoLogger Ver.2 / UNO Q]
    MCU側 : センサ・CAN・GNSS
    Linux側: 既存のログ処理 ＋ Podiumクライアント（新規）
        └─(WiFi / テザリング / LTEドングル)──> telemetry.podium.live:8080
```

- **必要なのは3章のプロトコル実装のみ。** PCもスマホも公式アプリもPodiumConnect実機も不要
- 公式アプリのバグ（4.3）から完全に切り離される
- チャンネル定義を自分で決められる＝EcoLogger固有のチャンネル
  （エコラン用の燃費系など）もそのままPodiumに出せる
- 実装規模：ソケット＋JSON＋再接続ロジックで数百行。**難易度は低い**
- EcoCapture側には「ストリーミングキーの入力欄」と「送信ON/OFF」を足すだけでよい
  （既に `Settings → ライブ共有` があるので、その隣に並べるのが自然）

### 経路A'：**STM32（MCU）側がPodiumクライアントになる** 【2026-09-21追加・最有力】

```text
[EcoLogger Ver.2 / UNO Q]
    STM32側 : センサ・CAN・GNSS ＋ Podiumクライアント（新規）
        └─UART(AT)─> [SIM7070G] ─(内蔵TCP/IPスタック)─> telemetry.podium.live:8080
    Linux側 : 既存のログ処理・EcoCapture（インターネット接続は不要）
```

**経路Aは「Linux側に置く」と書いていたが、それは前提ではなく選択にすぎなかった。**
回路担当から「**STM32にLTEを接続しただけではLinuxがインターネット接続できるわけではない。
Linux側のPodiumクライアントとSTM32側のモデム通信をつなぐ処理は別途必要で、未実装**」
という申し送りを受けたが（`hardware_ans_20260921.md`のP-3）、
**そもそもLinuxを介在させなければ、その橋渡し自体が要らない。**

**成立する根拠（推測ではなく、手元の参照実装で確認済み）**

| # | 根拠 | 出典 |
|---|---|---|
| 1 | **Podiumテレメトリーは平文TCP＋改行区切りJSONだけ。TLSもWebSocketもHTTPも使わない。** 依存はソケットとJSONのみ（3.6章） | 3章 |
| 2 | **公式RaceCaptureファーム（MK3）は、まさにベアメタルMCUからセルラーモデムをATコマンドで叩いてPodiumへ送っている。** `auth_telem_stream()`は`json_objStart()`等でJSONを**モデムのシリアルへ直接書いている**だけで、OSもTCPスタックも介在しない | `reference/RaceCapture-Pro_firmware/src/devices/cellular.c` |
| 3 | **モデム側の実装例も2種類ある。**`AT+CIPMUX`/`AT+CSTT`/`AT+CIPSTART`＋`AT+CIPMODE=1`（透過モード）で**ソケットを素のバイトパイプにしている** | 同 `sim900.c` |
| 4 | 🔴 **LTE-M世代のモデムの実装もある。**`AT+USOCR=6`→`AT+USOCO`（接続）→`AT+USODL`（direct link＝透過モード）。**SARA-R4はSIM7070Gと同じLTE-M/NB-IoTクラス**なので、構造がそのまま対応する | 同 `sara_r4.c` |
| 5 | **SIM7070GもTCP/IPスタックを内蔵している**（`AT+CNACT`でPDP活性化 → `AT+CAOPEN`でTCP接続 → `AT+CASEND`で送信、の系統）。MCU側にlwIP等を載せる必要はない | SIMCom AT Command Manual（⚠️**透過モードの有無と正確なコマンド名は要確認**） |

**この経路の利点**

- 🔴 **回路担当が挙げた最大の未実装項目（Linux↔STM32のモデム橋渡し）が、そもそも不要になる。**
  LTEモデムはSTM32のUARTに直結している＝**クライアントを置くべき場所のすぐ隣にモデムがある**
- **Linuxが落ちていても・起動途中でも配信が続く。** 「電源を入れただけで自動接続」という要求
  （`hardware_share_20260921.md`7-2）に対して、**Linuxのブート完了を待たなくてよい**のは有利
- テレメトリーの元データ（CAN・GNSS・IMU）は**もともとSTM32側にある**。
  Linux側へ渡してから送り返す必要がない
- 認証応答の`{"status":"ok","utc":...}`で**UTC絶対時刻が手に入る**。
  7章の「ログの絶対時刻が無い」問題に対する副次的な入手経路になる（GNSSと二重化できる）

**この経路で別途詰めるべきこと**

| # | 項目 | 備考 |
|---|---|---|
| 1 | **ストリーミングキーをどこに保存し、どう入力するか** | UIはEcoCapture（Linux側）に置きたい → **キーだけをLinux→STM32へ渡す経路**が要る。ただしこれはモデム橋渡しと違い**低速・低頻度でよい**ので難易度は段違いに低い。Ver.1には`setConnCfg`/`getConnCfg`（RCP経由でNVSへ保存）が実装済みなので流用できる（4.2章） |
| 2 | **SIM7070Gに透過モードがあるか。無ければ`AT+CASEND`方式になる** | 10Hz・1回あたり数百バイトなのでATコマンドのオーバーヘッドは問題にならない見込みだが、**送信1回あたりのペイロード上限**（一般に1500バイト程度）は確認する |
| 3 | **STM32側のATコマンド状態機械の実装コスト** | Pythonのソケットより手数は多い。ただし**公式ファームに完動する実装例が2つある**（`sim900.c`・`sara_r4.c`）ので、ゼロからの設計にはならない |
| 4 | **再接続・バックオフ・認証失敗時の停止** | 3.5章の挙動をMCU側で再現する。`cellular.c`に実装例あり |

> ⚠️ **なお「Linuxをインターネットに出す」こと自体は、この経路でも解決しない。**
> EcoCapture Live（Firebase）・OTA更新・NTP・映像のアップロード等をやりたくなった時点で、
> **改めてPPP/RNDIS等の橋渡しが必要になる。**
> ただし**Podiumライブ配信の成否とは切り離せる**ので、クリティカルパスから外せるのが大きい。

### 経路B：公式RaceCaptureアプリを中継役にする

```text
[EcoLogger Ver.2] --USB(RCP)--> [PC/スマホ/Pi の公式アプリ] --> podium.live
```

- **Ver.1で実機動作確認済み**という強み。すぐ動く
- 代償：①VID/PIDを合わせる必要がある（4.1）、②再接続フリーズバグを抱える（4.3）、
  ③常に公式アプリを起動しておく必要がある（EcoCaptureと同時起動できない可能性）
- **検証用の保険として残す価値はあるが、本番構成には向かない**

### 経路C：PodiumConnect実機を買う

- ⚠️1.2の未確認事項が解けないと判断できない。
  **自作ロガーを受け付ける保証がない**うえ、経路Aで足りるなら費用も増える
- **現時点では非推奨。** 1.2の確認が取れてから再検討でよい

### 比較表

| | **A'：STM32直送** | A：Linux側から直送 | B：公式アプリ中継 | C：PodiumConnect実機 |
|---|---|---|---|---|
| 追加ハード | 車載回線のみ | 車載回線のみ | 中継PC/スマホ＋回線 | 実機＋SIM |
| 実装量 | 数百行（AT制御込み。**公式ファームに実装例2つ**） | 数百行（ソケット＋JSON） | ほぼゼロ（実績あり） | ⚠️不明 |
| **Linux↔STM32のモデム橋渡し** | **不要** | 🔴 **必須・未実装** | 不要 | 不要 |
| Linuxのインターネット接続 | **不要** | 🔴 **必須** | 不要 | 不要 |
| Linux停止時の配信継続 | **続く** | 止まる | 止まる | 続く |
| 既知バグの影響 | 受けない | 受けない | **受ける**（4.3） | ⚠️不明 |
| 独自チャンネル | **自由** | **自由** | RCPのメタに従う | ⚠️不明 |
| 運用の手数 | 電源を入れるだけ | 電源を入れるだけ | アプリ起動・接続操作 | ⚠️不明 |
| 推奨度 | 🔴 **◎（最有力）** | ○ | ○（検証用の保険） | △（要事前確認） |

---

## 6. 注意点・落とし穴

### 6.1 プロトコル面

1. **平文TCP・TLSなし。** `telemetry.podium.live:8080` は暗号化されていない。
   **ストリーミングキーが平文で流れる**。公衆WiFi経由での使用は避ける。
   キーが漏れると第三者が自分のデバイスIDとして偽データを投げられる
2. **ストリーミングキーは秘密情報。** リポジトリ・設定ファイル・スクリーンショット・
   ログに含めない。**pushする資料に貼らない**（VIN等と同じ扱い）
3. **送信は10Hz固定**（アプリ準拠）。EcoLoggerのGNSSは20〜25Hzを狙っているので、
   **Podiumへ出す分は間引きが要る**。ロガー内部のSD記録レートとは分けて考える
4. **meta の並び順とビットマスクのビット位置が1:1。**
   チャンネルを1つ足すだけで全体がずれるので、**meta生成とサンプル生成は
   必ず同じ配列から作る**こと（別々に手書きすると必ず事故る）
5. **チャンネル名はASCII推奨。** アプリは `encode('ascii')` している。
   EcoCaptureは日本語表示アプリだが、**Podiumへ送る `nm` は英数字にし、
   日本語表示はEcoCapture側の対応表で行う**のが安全
6. **認証失敗時はリトライしない**実装にすること。誤ったキーでサーバを叩き続けない
7. チャンネル数が32を超えたらビットマスクが2語になる。
   EcoLoggerのチャンネル数は32を超え得るので、**最初から可変長で実装する**

### 6.2 運用・構成面

8. **車載のインターネット回線が別途必要。** WiFiテザリング／LTEドングル／
   モバイルルータのいずれか。Ver.1のダッシュカム検討時から変わらない前提
9. **電源ON/OFFがログ開始/終了トリガー**という本プロジェクトの設計思想と、
   Podiumの「イベント」の粒度が合うかは要検討。
   セッションの区切り方（Ad Hocイベントを毎回作るのか）は運用ルールを決める必要がある
10. **EcoCapture Live（Firebase、1Hz、`EcoCapture/cloud/`）との棲み分け。**
    既に「URLを知る人だけで共有する」独自のライブ共有がある。
    Podiumと二重に持つのか、Podiumへ寄せるのかを決めないと、
    設定項目も送信経路も二重管理になる
11. ⚠️**未確認**：podium.live 側のアカウント要件・無料枠・同時ストリーム数・
    データ保持期間。本リポジトリに一次情報がない。**実運用前に要確認**
12. ⚠️**未確認**：自作デバイス（純正RaceCapture以外）をPodiumへ登録することが
    利用規約上問題ないか。プロトコル自体は公開されている公式ソースから読み取れるものなので
    技術的には可能だが、**規約の確認は別途必要**

### 6.3 Ver.2固有

13. ⚠️**未確認（Q-4）**：**UNO QのLinux側がWiFiでインターネットに出られるか**、
    Arduino配布のDebianイメージでネットワーク設定が素直に通るか。
    経路Aの大前提なので最優先で確認したい
    → **2026-09-21：経路A'（STM32直送）を採るなら、これはPodium配信の前提ではなくなる。**
    Linuxのインターネット接続が要るのはEcoCapture Live・OTA・NTP・映像アップロード等であって、
    **Podiumライブ配信のクリティカルパスからは外せる**（5章の経路A'）
14. UNO Qでは**ハードウェアエンコーダ（venus）の有効性が最優先の未確認事項**として
    既に上がっている（`LOGGER_V2_UNOQ_REPORT.md` 6章）。
    **そちらが通らないとUNO Qという選択自体が崩れる**ので、Podium対応の優先度は
    その次に置くのが妥当
15. Ver.1のRCP実装（`getConnCfg`/`setConnCfg`）をVer.2へ移植するかは、
    経路Aだけに絞るなら不要。**経路Bを保険として残すなら移植が要る**

---

## 7. 開発チームへの確認・依頼事項

| # | 内容 | 担当 | 期限感 |
|---|---|---|---|
| Q-1 | 「Podium Connectを使いたい」の意図は①クラウドへのライブ配信でよいか（②の実機購入ではない） | 企画 | 先に確定したい |
| Q-2 | podium.live のアカウント要件・無料枠・デバイス登録手順の確認 | 誰か1名 | 実装前 |
| Q-3 | 自作デバイスをPodiumへ登録することの規約確認 | 誰か1名 | 実運用前 |
| Q-4 | **UNO QのLinux側がWiFiでインターネットに出られるか実機確認** | UNO Q実機保有者 | **最優先** |
| Q-5 | EcoCapture Live（Firebase）とPodiumの棲み分け方針の決定 | 企画 | 実装前 |
| Q-6 | Podiumへ出すチャンネル一覧（英語名・単位・レンジ・送信レート）の確定 | 企画＋実装 | 実装前 |
| Q-7 | Ver.1ファームの「再接続後のストリーミングキー保持」実機確認（未実施のまま） | ファーム | いつでも |
| Q-8 | PodiumConnect実機がどうデータを受け取るのか（経路Cを残す場合のみ） | — | 保留可 |

### 実装タスクの叩き台（経路Aの場合）

- [ ] UNO QのLinux側でWiFi接続を確立（Q-4）
- [ ] Podiumクライアントの最小実装（connect → auth → meta → sample、再接続付き）
- [ ] ダミーデータでpodium.liveへ疎通確認（実車なしでできる）
- [ ] EcoLoggerの実チャンネルをmetaへマッピング（Q-6の確定後）
- [ ] 20〜25Hz → 10Hzの間引き処理
- [ ] EcoCapture Settings へ「ストリーミングキー」欄と送信ON/OFFを追加
- [ ] キーの保存先を決める（平文で置かない・リポジトリに入れない）
- [ ] 通信断・復帰・長時間走行での安定性テスト

---

## 8. 参照先（このメモの根拠）

| 内容 | ファイル |
|---|---|
| Podiumプロトコル（アプリ実装） | `reference/RaceCapture_App/autosportlabs/telemetry/telemetryconnection.py` |
| Podiumプロトコル（ファーム実装・認証） | `reference/RaceCapture-Pro_firmware/src/devices/cellular.c`（`auth_telem_stream`） |
| サンプルのビットマスク形式 | `reference/RaceCapture-Pro_firmware/src/logger/loggerApi.c`（`api_send_sample_record`） |
| connCfg（btCfg/cellCfg/telCfg）の仕様 | `reference/RaceCapture-Pro_firmware/src/logger/loggerApi.c`（`api_getConnectivityConfig`） |
| 既定のホスト・ポート | `reference/RaceCapture-Pro_firmware/include/logger/loggerConfig.h`（`DEFAULT_TELEMETRY_SERVER_*`） |
| Ver.1でのconnCfg実装 | `firmware/src/main.cpp`（`ConnCfg` / `rcpSendConnCfg` / `rcpHandleSetConnCfg`） |
| VID/PID問題・アプリ側バグの経緯 | `task_phase1_breakdown.md` 1-4-4 / 1-4-6 / 1-4-7、`ARCHITECTURE.md` 4章 |
| 「PodiumConnect不要」の結論 | `DASHCAM_STREAMING_RESEARCH.md` 3章・4.1節 |
| Ver.2（UNO Q）の前提と最優先の未確認事項 | `LOGGER_V2_UNOQ_REPORT.md` 6章 |
| EcoCapture独自のライブ共有 | `EcoCapture/cloud/README.md` |

---

## 9. 実装者向けの補足（2026-10-04追記）

3章の記述は参照ソースと照合し直して一致を確認済み。そのうえで、**3章だけ読んで実装すると
詰まりそうな点**をまとめる。

### 9.1 参照ソースはサブモジュール。クローンしただけでは中身が空

`reference/`配下の3つ（`RaceCapture-Pro_firmware` / `RaceCapture_App` / `RaceCapture_App_fork_ryandoherty`）は
**gitサブモジュール**なので、普通にクローンすると空ディレクトリになる。8章の根拠ファイルを読むには：

```bash
git submodule update --init --depth 1
```

### 9.2 チャンネル名はRaceCapture標準名に合わせる

Podiumは純正RaceCaptureの標準チャンネル名を前提に作られている。**地図表示・ラップ表示に使う
チャンネルは、純正ファームの既定名と完全一致させておく**のが安全
（⚠️Podiumのサーバー側はソース非公開のため「一致しないと地図が出ない」こと自体は未確認。
ただし外す理由も無い）。

| 名前 | 単位（純正既定） | 精度 | 出典 |
|---|---|---|---|
| `Latitude` | `Degrees` | 6 | `loggerConfig.h` `DEFAULT_GPS_LATITUDE_CONFIG` |
| `Longitude` | `Degrees` | 6 | 同 `DEFAULT_GPS_LONGITUDE_CONFIG` |
| `Speed` | （空） | 2 | 同 `DEFAULT_GPS_SPEED_CONFIG` |
| `GPSSats` | （空） | 0 | 同 `DEFAULT_GPS_SATELLITE_CONFIG` |
| `Utc` | `ms` | 0 | 同 `DEFAULT_UTC_MILLIS_CONFIG` |
| `LapCount` / `ElapsedTime` / `Distance` | — / `Min` / `mi` | | 同 `DEFAULT_LAP_COUNT_CONFIG` ほか |

緯度経度は**小数点以下6桁を落とさずに**JSONへ書くこと（`float`で丸めると地図上で数m単位でずれる）。

### 9.3 metaとサンプルの細部

- 純正ファームのmetaには`"prec"`（小数点以下桁数）も入る（`loggerApi.c` `json_channelConfig`）。
  アプリ版は付けていないので**必須ではない**が、付けても問題ない
- **ビットマスクの語数は「metaのチャンネル総数」で決まる**（その回に値があった数ではない）。
  `語数 = floor((総数 - 1) / 32) + 1`。値が1つも無い回でも、ビットマスク語（0）は送る
- サーバーから`"message"`キー付きの応答や想定外の行が来ることがある。アプリは
  **ログに出して無視**しているので、未知のメッセージで落ちない作りにする

### 9.4 SIM7070GのTCP送信は、チームに動いている実装がある

5章経路A'で「⚠️要確認」としていたSIM7070GのATコマンド手順は、**エコランチームの
`TMCIT-Ecorun/2026-logger-frontpanel`（C／pico-sdk）と`TMCIT-Ecorun/ecorun-talk`（Python）で
既にSIM7070G＋SORACOMでのTCP送信が動いている**（`ecorun_team_systems.md` 1・2章）。
`AT+CNACT`→`AT+CAOPEN`→`AT+CASEND`の実際の手順・待ち時間・エラー処理はそちらのコードを見るのが早い。

- 向こうはWSS（TLS）だが、**Podiumは平文TCPなのでTLS関連の設定（`AT+CSSLCFG`等）は不要**で、
  そのぶん手順は短くなる
- 向こうは「1フレームごとに`AT+CASEND`1回」方式。Podiumも同じ方式で、**10Hz＝100msに1回の
  `AT+CASEND`**になる（向こうの60ms周期より緩い）
- ⚠️チーム側のリポジトリは**読むだけで変更しない**こと

### 9.4.1 Podium刷新後のサーバー実測（2026-10-04、PCから直接）

Podiumのシステム刷新後も、**3章のプロトコル（8080番・改行区切りJSON）はそのまま受け付けている**ことを確認した。
ただし**認証失敗時の挙動が3.2章の記述と違う**ので注意。

- `telemetry.podium.live` は `nanomq.podium.live`（18.215.155.238）の別名になっている。
  裏側はMQTTブローカー（NanoMQ、1883番も開いている）だが、**8080番のJSON受け口は残っている**
- `{}`＋改行を送る → `{"status":"error","message":"missing auth frame"}` が返って切断
  ＝8080番は今も「最初に認証フレームを待つ」作り
- **無効なキーで認証を送る → 何も返さずに即切断**（アプリ版・純正ファーム版どちらの形式でも同じ）。
  3.2章の「`status`が`ok`以外なら失敗」という応答は来ない。
  **「認証を送った直後に無言で切られる」＝キーが通っていない**と読む
- 改行を付けずに送る → サーバーは何も返さず待ち続ける（タイムアウト）
- 有効なキーでの応答は未確認（キーを持っていないため）。`podium_test_sender.py`をキーの持ち主が
  実行すれば、Podium側の問題かロガー側の問題かを切り分けられる

ロガー側で見える症状との対応：

- TCP接続そのものができない → モデム・回線・ATコマンド側の問題
- 接続できるが認証後すぐ切られる → **キーが無効**（刷新で旧キーが使えなくなった可能性を含む）。`podium_test_sender.py`でPCから同じキーを試す
- 接続できるが何も返ってこない → **末尾の改行が送れていない**（`AT+CASEND`の長さ指定に`\n`を含め忘れる等）

### 9.5 実装前に手元で用意しておくもの

- podium.liveのアカウントと、そこで発行されたストリーミングキー（Device ID）
  → **キーはリポジトリ・ログ・スクリーンショットに入れない**（6.1章の2）
- 動作確認は実車不要。**ダミー値（固定の緯度経度＋適当な数値）を10Hzで流して
  podium.liveのライブ画面に出ればプロトコルは完成**。まずPCのPythonで3.6章の流れを
  数十行で書いて疎通させ、その後STM32へ移すと、サーバー側の問題とAT制御の問題を切り分けられる
