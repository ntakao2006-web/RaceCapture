# Podiumライブテレメトリの流用方法

本ドキュメントは、AutosportLabsのクラウドサービス**Podium（podium.live）のライブテレメトリ**を、
本プロジェクトの自作ロガー／表示ユニットからどう流用できるかを1か所にまとめたもの。
プロトコルの実体は公式ソース（`reference/`配下のサブモジュール）から読み取った内容であり、
推測ではなく実コードを根拠にしている（根拠は8章に一覧）。

---

## 1. 結論（先に3行）

1. Podiumライブテレメトリの実体は**`telemetry.podium.live:8080`へのプレーンTCP＋改行区切りJSON**であり、
   送るJSONは**本プロジェクトが既に実装済みのRCPの`{"s":{...}}`（meta同送＋ビットマスク）とほぼ同一**。
   つまり「新しいプロトコルを覚える」必要はほぼ無く、**送り先を変えるだけ**に近い。
2. 流用ルートは3つ。**A: アプリ中継（現状の実装で既に完成。追加開発ゼロ）**、
   **B: ロガーから直送（ESP32のWi-Fi/LTEで直接Podiumへ）**、**C: プロトコルだけ流用して自前サーバへ**。
3. 直近の実運用（DC-10-3のROCK 4 SE軽量構成、ROCK 5B、スマホ）は**すべてルートAで足りる**。
   ルートB/Cは「表示ユニットを積まない・アプリを起動しない構成でも遠隔監視したい」場合に初めて必要になる。

---

## 2. Podiumライブテレメトリの実体（プロトコル仕様）

### 2.1 接続

| 項目 | 値 | 根拠 |
|---|---|---|
| ホスト | `telemetry.podium.live` | 公式FW `include/logger/loggerConfig.h:508` ／ 公式App `telemetryconnection.py:33` |
| ポート | `8080` | 同上 `:509` ／ `:34` |
| トランスポート | 素のTCP（**TLSなし**）、**改行`\n`区切りのJSON 1行＝1メッセージ** | App `telemetryconnection.py:288`（`set_terminator("\n")`） |
| 認証 | **ストリーミングキー（deviceId）のみ**。パスワード等は無い | 下記2.2 |

podium.live上で車両（デバイス）を登録すると発行される文字列が「ストリーミングキー」で、
これがRCPプロトコル上の`connCfg.telCfg.deviceId`に対応する。

### 2.2 ハンドシェイク（auth）— **方言が2つある点に注意**

- **アプリ中継（RaceCapture App）が送る形**
  ```json
  {"cmd":{"schemaVer":2,"auth":{"deviceId":"<ストリーミングキー>"}}}
  ```
- **ロガー直送（公式MK3のセルラー）が送る形**（`cmd`ラップ無し・`schemaVer`無し）
  ```json
  {"auth":{"deviceId":"<キー>","apiVer":<API_REV>,"device":"<機種名>","ver":"<FWバージョン>","sn":"<シリアル>"}}
  ```
- **サーバ応答**（どちらも共通）
  ```json
  {"status":"ok","utc":<UNIX時刻ms>,"lt":<last tick>}
  ```
  `status`が`"ok"`以外なら認証失敗で、`message`に理由が入る。公式FWは`utc`/`lt`を
  「接続時刻」「サーバ側が最後に受け取ったtick」として取り込む（＝再接続時の続きから送る用途）。

つまり**サーバは両方の方言を受け付ける**。自作で実装する場合、素直なのはアプリ側と同じ`cmd`ラップ形。

### 2.3 meta（チャンネル定義）

auth成功直後に**必ず1回送る**。これを送るまで値は解釈されない。

```json
{"s":{"meta":[{"nm":"Coolant","ut":"F","sr":1,"min":0,"max":300}, ...]}}
```

公式FWは`{"s":{"t":<tick>,"meta":[...],"d":[...]}}`のように**サンプルと同じメッセージへmetaを同送**する
（接続直後の`tick==0`、およびオプションで100サンプルごと）。本プロジェクトのファームウェアの
`rcpSendSample()`が既にこの「meta同送」形式で実装済み。

### 2.4 サンプル（値）

```json
{"s":{"d":[v1, v2, ..., vN, <bitmask1>, <bitmask2>...]}}
```

- 値は**metaで宣言した順**に並べ、**値が無いチャンネルは配列に入れない**。
- 代わりに配列末尾へ**ビットマスク**を置き、「metaの何番目のチャンネルが今回入っているか」を示す。
  32チャンネルごとにビットマスクが1個増える（33ch以上ならマスクは2個）。
- 送信レートは**アプリ中継は0.1秒固定＝10Hz**（`SAMPLE_INTERVAL = 0.1`）。
  公式FW側の上限は**セルラー経由10Hz／それ以外50Hz**（`SLOW_LINK_MAX_TELEMETRY_SAMPLE_RATE`＝10Hz、
  `FAST_LINK_MAX_TELEMETRY_SAMPLE_RATE`＝50Hz）。

### 2.5 セッション境界（ロガー直送のときだけ）

公式FWは記録開始／終了で`{"logStart":1}` / `{"logEnd":1}`を送り、tickを0へ戻す。
アプリ中継の実装（2016年時点のfork）はこれを送っておらず、**auth→meta→サンプル連投だけ**。

### 2.6 切断時のバッファリング（公式FWの作り）

セルラー経路では、圏外・切断中のサンプルを**SDカード上の`tele.buf`へ退避**し、再接続後に
バックログとして送り直す（`connectivityTask.c`）。「ピットに戻ったら欠測期間が埋まる」挙動はこれ。
ルートBを自作する場合、ここは**任意（後回しでよい）**。

---

## 3. 流用ルート3案の比較

| | **A: アプリ中継** | **B: ロガー直送** | **C: プロトコル流用・自前サーバ** |
|---|---|---|---|
| データ経路 | ロガー →(USB/RCP)→ RaceCaptureアプリ →(ネット)→ Podium | ロガー →(Wi-Fi/LTE)→ Podium | ロガー or アプリ → 自前サーバ |
| ロガー側の追加実装 | **不要（実装済み）** | TCPクライアント＋auth＋再接続（中〜小） | Bと同じ（送り先が変わるだけ） |
| ネット回線を持つ機器 | 表示ユニット（ROCK/スマホ/PC） | ロガー本体 | 任意 |
| 表示ユニットの要否 | **必要**（アプリが動いていること） | 不要 | 構成次第 |
| 監視画面 | podium.live（既製） | 同左 | 自作（要開発） |
| データの持ち主 | Podium | Podium | 自分 |
| 現状の検証状況 | **DC-8で実証済み**（スマホ版アプリ＋PodiumLiveで確認） | 未着手 | 未着手 |

**選び方の目安**
- 表示ユニット（ROCK 5B / ROCK 4 SE / スマホ）を必ず積む構成 → **A一択**。追加開発ゼロ。
- 「ロガーだけ載せて遠隔から見たい」（表示なし・エコランマシン等） → **B**。
- 遅延・データ所有・独自ダッシュ（Podium非依存）を重視 → **C**。ただし受信側と可視化を自作する分の工数が要る。

---

## 4. ルートA（アプリ中継）— 今すぐ使う手順

ロガー側の実装は**すでに揃っている**。必要なのは設定だけ。

1. **podium.liveでデバイスを登録し、ストリーミングキーを取得する**。
2. 表示ユニットのRaceCaptureアプリでロガーへ接続し、**Setup → Podium** の画面でストリーミングキーを入力、
   **Write（`setConnCfg`）**する。→ ファームウェアがNVSへ永続化する（Phase1-4-7で実装済み。
   これ以前は接続の度に再入力が必要だった）。
3. アプリの設定で**「Send Telemetry」をON**にする（アプリ内プリファレンス`preferences/send_telemetry`）。
4. 表示ユニット側にインターネット接続（テザリング／モバイルルータ／セルラードングル）を用意する。
5. podium.liveの画面（またはAd Hocイベント）でライブ表示を確認する。

### アプリが中継を開始する条件（1つでも欠けると無言で繋がらない）

`TelemetryManager._should_connect`（`telemetryconnection.py:134`）が要求する条件：

- `data_connected`：ロガーとアプリが接続済み
- `telemetry_enabled`：上記3の「Send Telemetry」がON
- **`cell_enabled == False`**：ロガーが返す`connCfg.cellCfg.cellEnabled`が0であること
  （**ロガー自身がセルラーで送っているならアプリは中継しない**という排他制御。
  本プロジェクトのファームウェアは常に0固定なので好都合）
- `device_id != ""`：ロガーが返す`connCfg.telCfg.deviceId`が空でないこと（＝手順2が効いている）
- `channels`：`getMeta`でチャンネル定義を取得済みであること

**トラブル時はこの5条件を上から順に潰すのが最短**。特に「キーを入れたのに繋がらない」場合、
`getConnCfg`が空の`deviceId`を返していないかを疑う。

### 既知の制約

- 公式アプリ（Android/Kivy版）の**2回目接続時フリーズ**（ARCHITECTURE.md 7章、Phase1-4-6で
  アプリ側バグと特定・対策不可）。サンプル送信ワーカーが再開しないバグなので、
  **中継テレメトリも道連れで止まる**可能性が高い。運用回避（電源投入順を固定し、途中でUSBを抜かない）が前提。
- 中継レートは10Hz固定。ロガー側を50Hzで回しても、Podiumへ行くのは10Hz。

---

## 5. ルートB（ロガー直送）— 実装する場合のタスク分解案

現状のファームウェアからの差分は思っているより小さい。**JSONを作る部分は流用できる**ため、
実質「出力先の切り替え」「authの追加」「回線管理」の3点。

- **B-1**：`ConnCfg`へ`host`/`port`を追加する。現状`rcpSendConnCfg()`は`telCfg.host`を空文字で返しており、
  deviceIdのみNVS永続化している（`firmware/src/main.cpp`）。公式は`telemetryServerHost`を設定値として持つので、
  ここを実データ化すればルートCへもそのまま伸ばせる。
- **B-2**：Wi-Fi STA接続とSSID/パスフレーズのNVS保存。ESP32-C3/S3はWi-Fi内蔵のため**追加ハードは不要**
  （ただしサーキット走行中の実用にはテザリング元＝LTE回線が要る）。
- **B-3**：TCPクライアントを実装し、接続直後に**auth送信 → `{"status":"ok"}`待ち**を行う（2.2の形式）。
- **B-4**：既存の`rcpSendSample()`の出力先を抽象化する（現状はUSB CDCへ直書き）。
  同じJSONをTCPソケットへも書けるようにし、**接続直後の1回はmetaを同送**する。
- **B-5**：レート制御（10Hz）と切断検知・指数バックオフ再接続。
  アプリ側の実装は0.1s→×10→最大10秒間隔でリトライしている（`RETRY_*`定数）。
- **B-6**（任意）：切断中のバッファリング。公式FWの`tele.buf`相当をSDへ。まずは無しで実用可。
- **B-7**：podium.liveのAd Hocイベントで実機確認する。

> ロードマップ上の位置づけ：現行のPhase 1〜6にテレメトリ送信は含まれていない。着手するなら
> **新規Phase（Phase 7相当）として起票**し、ARCHITECTURE.md 5章へ追加するのが筋。
> ただし優先度は高くない（ルートAで実用要件は満たせているため）。

---

## 6. ルートC（プロトコルだけ流用して自前サーバへ）

- 送信側は**ルートBと完全に同一**。`host`を自前サーバへ向けるだけ。
- 受信側は「TCPで待ち受け、1行JSONを読み、`auth`が来たら`{"status":"ok"}`を返し、以後`s.meta`で
  チャンネル定義を、`s.d`＋ビットマスクで値を復元する」だけなので、Python/Nodeで数十行。
- 利点：Podium非依存（サービス終了・仕様変更の影響を受けない）、遅延を自分で詰められる、データを自分で保持できる。
- 欠点：可視化UIを自作する必要がある。**まずはPodiumで運用し、必要になったら差し替える**のが現実的。
- なお`rcp_mock_device.py`があるので、**受信サーバ側の試作はハードウェア無しで完結できる**
  （モックの`s`出力をそのままTCPへ流せばよい）。

---

## 7. 注意点・落とし穴

1. **ストリーミングキーは実質パスワード**。平文TCPで流れ、これ1つで他人がそのデバイス枠へ
   データを投げられる。CLAUDE.mdの「個人特定情報をpushしない」ルールと同じ扱いとし、
   **コミット・ログ・スクリーンショットに含めない**（NVSに置くのは可）。
2. **チャンネル数32の壁**。現行ファームウェアはビットマスクを`(1 << 23) - 1`と**23ch決め打ち**で
   出している（`firmware/src/main.cpp`）。Phase 6でチャンネルを動的化・拡張する際、
   **33ch以上になったらビットマスクは配列（複数個）になる**。ここはPodium側もアプリ側も同じ仕様。
3. **metaと`d`の順序は一致必須**。metaを更新したら値の並びも変わる。アプリ側はmeta変更時に
   再送している（`_on_meta` → `_send_meta`）。
4. **ルートAとルートBは排他**。ロガーが`cellEnabled=1`を返すとアプリは中継しない（4章参照）。
   将来ルートBを実装したら、**どちらで送るかをconnCfgで明示的に切り替える**設計にすること。
5. **根拠にしたAppソースは2016年のfork**（`reference/RaceCapture_App_fork_ryandoherty`、Python 2系）。
   `schemaVer:2`は当時の値であり、現行アプリ（v2.19.0）で変わっていない保証はない。
   実際に自作クライアントを書く前に、**現行アプリの通信を1回キャプチャして確認する**のが安全
   （公式FW側は2022年時点のコードで、`cmd`ラップ無しauthのままサーバに受理されている）。
6. **Podiumのライブ表示≠動画への焼き込み**。Podium単体では動画へのデータ焼き込みは行えず、
   RaceRender等の別ツールが必要（`DASHCAM_STREAMING_RESEARCH.md`）。ROCK 5B構成の
   `video-streamer`相当（画面キャプチャ＋エンコード）とは**独立した経路**である点を混同しないこと。

---

## 8. 根拠にしたソース

| 内容 | ファイル |
|---|---|
| ホスト・ポートの既定値、レート上限 | `reference/RaceCapture-Pro_firmware/include/logger/loggerConfig.h:508-509`, `:76-77` |
| ロガー直送のauth／`status`応答の扱い | `reference/RaceCapture-Pro_firmware/src/devices/cellular.c`（`auth_telem_stream`） |
| サンプル／metaのJSON生成（`s`・`d`・ビットマスク） | `reference/RaceCapture-Pro_firmware/src/logger/loggerApi.c`（`api_send_sample_record` / `write_sample_meta`） |
| meta同送の条件、`logStart`/`logEnd`、`tele.buf`バッファリング | `reference/RaceCapture-Pro_firmware/src/logger/connectivityTask.c` |
| アプリ中継のauth（`cmd`/`schemaVer`）・meta・サンプル・10Hz・再接続 | `reference/RaceCapture_App_fork_ryandoherty/autosportlabs/telemetry/telemetryconnection.py:33,34,134,260,288,456,461,484` |
| 中継開始条件・`send_telemetry`設定 | 同上 `:134`、`autosportlabs/racecapture/settings/prefs.py:166`, `main.py:447` |
| 本プロジェクト側のConnCfg実装（deviceIdのNVS永続化、host空文字） | `firmware/src/main.cpp`（`ConnCfg` / `rcpSendConnCfg` / `rcpHandleSetConnCfg`） |
| 本プロジェクト側のサンプル送信（meta同送・23chビットマスク） | `firmware/src/main.cpp`（`rcpSendSample`） |
| ルートAの実証記録 | `task_dashcam_breakdown.md` DC-8、`DASHCAM_STREAMING_RESEARCH.md` 4.1節 |
| アプリ側の既知バグ（2回目接続フリーズ） | `ARCHITECTURE.md` 4章（Phase1-4-6）・7章 |
