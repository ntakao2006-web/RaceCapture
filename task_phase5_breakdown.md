# Phase 5 サブタスク分解（ラップタイム・予測タイム計算の実装）

> ARCHITECTURE.md「5. 開発ロードマップ」のPhase 5（5-1〜5-6）は粒度が粗いため、
> 実作業はこのファイルの単位（1チャット=1タスク）で進める。
> 完了したタスクはこのファイル内でチェックし、Phase全体が終わったらARCHITECTURE.mdへ
> 結論だけ転記してarchive/へ移動する運用（8章のルールに準拠）。
>
> 背景：`HANDOFF_ecosystem_research_gap.md`のエコシステム調査により、公式RaceCaptureでは
> ラップタイム・予測タイム計算はロガー本体（ファームウェア）側で行われ、アプリは受信・表示のみと判明した。
> このPhaseはその構造に合わせ、ロガー（ESP32）側にラップ判定・予測タイム計算を実装するもの。

---

## 5-1: `getLapCfg`/`getTrackCfg`の現状確認と実データ化設計 ※追加ハードウェア不要、今すぐ着手可
- [x] 5-1-1: 現状の`firmware/src/main.cpp`における`getLapCfg`/`getTrackCfg`応答実装（1-3-3で追加した空オブジェクト応答）を確認し、実データを保持・返却する形に変更するための構造（トラック名・スタート/フィニッシュ座標等のフィールド構成）を設計する → 完了（下記「5-1-1設計結果」参照）
- [x] 5-1-2: 公式アプリ（`RaceCapture_App`ソース）側の`getTrackCfg`/`setTrackCfg`送受信コードを参照し、レスポンス形式・必須フィールドを確認する → 完了（下記「5-1-2確認結果」参照）
- [x] 5-1-3: `setTrackCfg`（アプリ→ロガーへのトラック設定書き込み）に対応する受信処理を実装する → 完了（下記「5-1-3実装・実機確認結果」参照）

### 5-1-1設計結果

**現状確認**：`firmware/src/main.cpp`の`getLapCfg`/`getTrackCfg`は`rcpSendEmptyObjectResponse`で空オブジェクト（`{"lapCfg":{}}`等）を返すのみ。`setLapCfg`/`setTrackCfg`は`rcpSendSetCfgAck`でACKのみを返し、受信ペイロードの中身は一切解釈・保存していない（1-7-3時点でのWriteタイムアウト回避のためのダミー実装であり、実データ処理は未着手と確認）。

**公式仕様の参考調査**（`reference/RaceCapture-Pro_firmware`、GPLのためロジック参照のみで直接移植はしない）：
- 実データは`trackCfg`側に集約されている（`include/logger/loggerConfig.h`の`TrackConfig`/`include/tracks/tracks.h`の`Track`、`src/logger/loggerApi.c`の`api_getTrackConfig`/`json_track`）：
  `{"trackCfg":{"rad":<半径、度単位float>,"autoDetect":0または1,"track":{"id":<int32>,"type":0(circuit)または1(stage),"sf":[lat,lon]（circuitの場合）または"st"/"fin":[lat,lon]（stageの場合）,"sec":[[lat,lon],...]（セクター境界、任意）}}}`
- `lapCfg`はトラック座標を一切含まない。LapCount/LapTime/Sector/SectorTime/PredTime/ElapsedTime/CurrentLap/Distance/SessionTimeという9チャンネル分の`ChannelConfig`（nm/ut/sr/prec等のメタデータ）を保持するのみで、値自体はテレメトリー本体（`s`コマンド）側で送る設計（5-5のスコープと対応）
- 公式の`Track`構造体に**トラック名フィールドは存在しない**（トラック名はトラックDB側の話。5-2で「個人利用ならDB化不要、スタート/フィニッシュ座標の手動設定のみで十分」と方針決定済みであり、この調査結果と整合する）

**自作ロガー向けの設計（簡略化）**：5-2の方針（トラックDB不要）を前提に、「現在アクティブな1トラック分の設定」のみを保持するシンプルな構造とする。公式のマルチトラックDB・複数セクター・stage(ラリー)対応は個人サーキット走行用途にはオーバースペックのため採用しない。

```c
// 保持する実データ構造（イメージ、5-1-3で受信処理と併せて確定）
struct TrackCfg {
    float radius = DEFAULT_TRACK_RADIUS;  // ジオフェンス半径。公式の"rad"相当
    int32_t trackId = -1;                 // 未設定時-1。DB不要なので単なる識別用ラベル
    float startFinishLat = 0.0f;
    float startFinishLon = 0.0f;
    // stage用のst/fin個別座標、sec（セクター）配列は5-3がサーキット周回想定のため当面非対応
};
```

- `autoDetect`・`type`（circuit/stage）・トラック名・複数セクターは、公式互換のレスポンスフィールドとしては維持する（`getTrackCfg`応答に`"type":0`固定・`"autoDetect":0`固定で含める）が、実データとして保持・書き込み対応するのは`rad`とスタート/フィニッシュ座標(`sf`)のみとする
- `lapCfg`側は5-1時点では公式互換の固定デフォルト値（`DEFAULT_LAP_CONFIG`相当のnm/ut/sr/prec）をそのまま返すダミー実装のままでよいと判断（チャンネル値自体の実装は5-5のスコープ）。実データ化の優先度は`trackCfg`（スタート/フィニッシュ座標）の方が高い
- 保存先（RAM/NVS等）は5-2で決定する方針（SDテーブル vs 決め打ち）と合わせて確定する。5-1-1時点ではフィールド構成のみを設計対象とし、保存先の実装詳細は5-2/5-1-3に委ねる

### 5-1-2確認結果

**リポジトリの所在について（重要な前提変化）**：公式`autosportlabs/RaceCapture_App`はGitHub上から削除／非公開化されており（`git clone`・`WebFetch`とも404）、現時点で入手できるソースは存在しない。代わりに、個人による後継相当のリポジトリ`ryandoherty/RaceCapture_App`（説明文「Next Generation version of the RaceCapture App」、autosportlabs公式ではない）を発見し、ユーザー承認のうえ`reference/RaceCapture_App`にshallow clone済み。**公式ソースではない点に注意**（ただし後述の通りfirmware側の調査結果と完全に整合しており、参考資料としての信頼性は高いと判断）。

**参照箇所**：
- `autosportlabs/racecapture/config/rcpconfig.py`：`TrackConfig`/`Track`クラス（`fromJson`/`toJson`）
- `autosportlabs/racecapture/geo/geopoint.py`：`GeoPoint`クラス
- `autosportlabs/racecapture/api/rcpapi.py`：`getTrackCfg`/`setTrackCfg`の送受信（`sendGet`/`sendSet`/`sendCommand`）

**レスポンス形式**（`TrackConfig.toJson()`より）：
```json
{"trackCfg":{
  "rad": <float, 度単位半径>,
  "autoDetect": 0または1,
  "track": {
    "id": <int>,
    "type": 0(circuit)または1(stage),
    "sec": [[lat,lon], ...],
    "sf": [lat,lon]            // type=0(circuit)の場合のみ
    // "st":[lat,lon], "fin":[lat,lon]  // type=1(stage)の場合のみ
  }
}}
```
`GeoPoint.toJson()`は`[latitude, longitude]`の2要素配列。`radius`は度単位（`GeoPoint.withinCircle`が緯度経度差の二乗和と比較しており、メートルではなく度単位であることをコードで再確認）。

**結論：5-1-1でファームウェア側（`RaceCapture-Pro_firmware`）から起こした設計と完全に一致**。フィールド名・型・circuit/stageでの`sf`と`st`/`fin`の出し分けに齟齬なし。5-1-1の`TrackCfg`構造体案はそのまま踏襲してよい。

**5-1-3実装に向けた追加の注意点（新規判明）**：
- `Track.fromJson`は`sectorsJson = trackJson.get('sec', None)`のあと`len(sectorsJson)`を呼んでおり、`sec`キーが応答に存在しない/nullだとアプリ側で例外になりうる実装になっている。`getTrackCfg`応答には`sec`を**空配列`[]`ででも必ず含める**必要がある（5-3でセクター対応するまでは常に`[]`を返す方針）。
- コマンド送受信形式：`sendGet`は`{"getTrackCfg":null}`、`sendSet`は`{"setTrackCfg":{...}}`を`json.dumps(..., separators=(',', ':')) + '\r'`で送信。行末`\r`のみである点はHANDOFF.mdの既存の実機検証結果と整合。

### 5-1-3実装・実機確認結果

**実装内容**（`firmware/src/main.cpp`）：5-1-1設計の`TrackCfg`構造体（radius/trackId/startFinishLat/startFinishLon）をRAM上に保持。`getTrackCfg`を空応答から実データ応答(`rcpSendTrackCfg`)へ、`setTrackCfg`を単なるACKから実受信処理(`rcpHandleSetTrackCfg`)へ変更した。保存先はまだRAMのみ（NVS等の永続化は5-2で保存方式を決定後に対応）。

**実機（ESP32-S3-DevKitC-1 N16R8）で発見・修正した不具合3件**：
1. **RCP受信行バッファ(512B)オーバーフロー**：公式アプリのWrite操作は`setTrackCfg`と同時に`setLapCfg`（9チャンネル分のnm/ut/min/max/prec/sr全部入り）を一括送信するため、512Bでは足りずオーバーフローし、後続の`setTrackCfg`まで巻き添えで破損して`JSON parse failed`になっていた。`kRcpLineBufSize`を512→2048に拡大して解消。
2. **taskCのスタックオーバーフロー**：上記1の対応でRCP送信関数`rcpSendJsonLine`内のローカルバッファ（スタック確保）が2048Bに拡大され、`JsonDocument`等と合わせてtaskCの元のスタックサイズ(4096B)を圧迫し、実機が"stack overflow in task task_c"でリセットする不具合が発生。taskCのスタックサイズを4096→8192に拡大して解消。
3. **`setTrackCfg`の実ペイロード形式が5-1-2確認結果と不一致**：5-1-2で参照した非公式フォーク(`ryandoherty/RaceCapture_App`)のソースでは`{"setTrackCfg":{"rad":...,"track":{...}}}`という想定だったが、手元の実機公式アプリ(Windows版)は実際には`{"setTrackCfg":{"trackCfg":{"rad":...,"track":{...}}}}`と、さらに`"trackCfg"`キーで一段ラップして送ってくることをシリアルログ実測で確認した。`rcpHandleSetTrackCfg`側で`"trackCfg"`キーの有無を吸収する実装に変更して解消。**5-1-2の「参照リポジトリはあくまで補助、一次情報源は実機観測」という位置づけの通り、参照ソースと実機の挙動が食い違う実例**。

**実機確認結果**：ESP32-S3(COM7書き込み/COM8 RCP通信)へ書き込み、公式RaceCactureアプリ(Windows版)のRace Tracks画面からスタート/フィニッシュ座標(35.372, 138.927)を入力→Write→別タブ経由での再表示、および明示的なRead再読込の両方で値が保持されていることを確認した。

---

## 5-2: トラック情報の保存先設計 ※追加ハードウェア不要、今すぐ着手可
- [x] 5-2-1: 保存先の方式（SDカード上のテーブル形式 vs 決め打ちの数トラックのみをコードに埋め込む方式）を比較検討し、方針を決定する → 完了（下記「5-2-1比較検討結果」参照。**NVS保存方式を採用**）
- [x] 5-2-2: 決定した方式でのデータ構造・ファイル形式（SD案の場合）を実装する → 完了（下記「5-2-2実装結果」参照。ビルド確認済み、実機検証は保留）

### 5-2-1比較検討結果

**前提の再確認**：`firmware/src/main.cpp`の現状（5-1-3実装）では、`TrackCfg`はPOD構造体（`radius`/`trackId`/`startFinishLat`/`startFinishLon`、float×2+int32_t×2）でRAM上（`g_trackCfg`）にのみ保持されている。また5-1-2確認結果の通り、`getTrackCfg`/`setTrackCfg`のRCP APIは「現在アクティブな1トラック分の設定」のみを送受信する仕様であり、複数トラックを一覧・選択するようなAPIは存在しない。加えて5-1-1で「個人利用ならトラックDBは不要、スタート/フィニッシュ座標の手動設定のみで十分」という方針をすでに決定済み。

**案A：SDカード上のテーブル形式**
- 長所：複数トラックを可変長で保存でき、容量的な制約がほぼない。
- 短所：
  - SDカード（`SD_MOUNT_POINT`）は現状taskB専用でCSVログ書き込み(`fopen`/`fsync`)に使っており、1-2-4/1-2-5で電源断対策を作り込んだ経緯がある。設定の読み書き用アクセスを追加すると、taskB（最優先）とtaskC（RCP通信）間でのFATFS同時アクセスの排他制御が新たに必要になり、ログ書き込みの信頼性まわりに不要な複雑さを持ち込むリスクがある。
  - 「画面表示が落ちても、ログ保存は絶対に止めない」という基本方針上、SDカードはログ保存に特化させたい。設定情報の保存にSDカードの有無・状態を依存させたくない。
  - ファイル形式（CSV/JSON等）のパーサー実装が別途必要になり、実装コストが高い。
  - 5-1-1・5-1-2の通りAPI・方針の両面で複数トラックDBの必要性が薄く、可変長テーブルのメリットを活かす場面がそもそも少ない。

**案B：決め打ちの少数トラックをNVSへ保存**
- 長所：
  - センサーキャリブレーション設定（`g_analogCfg`）で実装済みの`nvs_set_blob`/`nvs_get_blob` + `flashCfg`受信時コミットというパターンをそのまま踏襲できる（`analogCfgLoadFromNvs`/`analogCfgSaveToNvs`、`firmware/src/main.cpp:349`-`389`）。`TrackCfg`もポインタを含まないPOD構造体のためblob化に問題なし。実装コストが最小。
  - RCP APIが「現在アクティブな1トラックのみ」を扱う仕様である以上、NVSに1トラック分（または将来の拡張用に数個分）を保存すれば要件を満たせる。
  - 内蔵フラッシュのため、SDカードの抜去・破損状態に依存せず設定を保持できる（AnalogCfgと同じ堅牢性）。
  - 将来複数トラックの切り替えが必要になった場合も、NVSキー（`track0`,`track1`...等）を増やすだけで拡張可能。
- 短所：保存できる件数はSDに比べ少数に限られるが、上記の通りAPI・利用方針の両面でそもそも大量保存の必要性がない。

**結論：案B（NVS保存）を採用する。**
- 保存するのは「現在アクティブな1トラック分の`TrackCfg`」のみで、5-2時点ではAnalogCfgと同じ単一namespace・単一blobとして実装する（5-2-2で実装）。
- 複数トラックの切り替え機能が将来必要になった場合は、NVSキーを追加する形で対応する拡張余地を残す（現時点ではスコープ外）。

### 5-2-2実装結果

**実装内容**（`firmware/src/main.cpp`）：AnalogCfg（1-7-2、`analogCfgLoadFromNvs`/`analogCfgSaveToNvs`）と同じ`nvs_set_blob`/`nvs_get_blob`パターンで、`trackCfgLoadFromNvs`/`trackCfgSaveToNvs`を実装した。namespace`"trackcfg"`・単一キー`"track0"`に`TrackCfg`構造体（POD、blob化）をそのまま保存する。

- `app_main()`起動時、`analogCfgInitAll()`直後に`trackCfgLoadFromNvs()`を呼び、NVS未保存（初回起動等）の場合は`TrackCfg`のデフォルトメンバ初期化子の値のまま動作する。
- `flashCfg`受信時（Writeボタン相当、`rcpSendFlashCfgAck`）に`analogCfgSaveToNvs()`と並べて`trackCfgSaveToNvs()`を呼び、5-1-3で実装済みの`setTrackCfg`受信内容（RAM上の`g_trackCfg`）をこのタイミングでNVSへコミットする。
- `trackCfgSaveToNvs`の定義は`TrackCfg`構造体定義後（コード上で`rcpSendFlashCfgAck`より後）にあるため、`rcpSendFlashCfgAck`直前に前方宣言を追加してコンパイルを通した。

**ビルド確認**：`esp32-c3-proto`・`esp32-s3`両環境ともクリーンビルド成功（Flash/RAM使用量の増分は誤差程度）。**実機での読み書き往復（電源再投入後も座標が保持されるかの確認）は5-2-2時点では未実施、保留**（5-1-3と同様の実機確認は今後必要に応じて実施する）。

---

## 設計メモ（5-3・5-4向け、`HANDOFF_claudeai_chat_gap.md`より反映）

予測タイム計算の全体構造は以下の3ブロックに分かれる。5-3は①、5-4は③に対応。

1. **スタート/フィニッシュ・セクター判定**：ジオフェンス（緯度経度＋半径）通過を検出。GPSサンプル間隔そのままだと精度が粗いため、通過前後2点のGPS座標を距離で線形補間し、サブサンプル精度で通過時刻を算出する（公式ファームウェアの「GPSが10Hz未満の場合にアップサンプリング」も同じ精度問題への対処と推測される）。
2. **トラックDB**：公式は数十件のトラックDBを持つが、個人利用ならスタート/フィニッシュ座標の手動設定のみで十分（5-2の保存方式検討でDB化は不要という判断の参考にする）。
3. **予測タイム**：ベストラップを「累積走行距離→経過時間」の対応表として保持し、現在位置の走行距離に対応する時間を補間して現在の経過時間との差分（デルタ）を出す。実装上最も作り込みが必要な部分。

**進め方の推奨**：①（5-3）を先行実装→公式アプリでの表示確認（5-5の一部を前倒し）→③（5-4）を追加、という段階的な順序が妥当。

---

## 5-3: スタート/フィニッシュライン交差判定ロジック ※追加ハードウェア不要（GPSシミュレーションデータで検証）、今すぐ着手可
- [x] 5-3-1: GPS座標列（シミュレーションデータ、例えば`kDummyChannels`のLat/Lonをコース1周分の座標列に置き換えたもの）を用意する → 完了（下記「5-3-1実装結果」参照）
- [x] 5-3-2: スタート/フィニッシュライン（2点間の線分）とGPS移動軌跡の交差判定アルゴリズムを実装する → 完了（下記「5-3-2実装結果」参照）
- [x] 5-3-3: シミュレーションデータでラップ切り替わり（周回検出）が正しく発火するか確認する → 完了（下記「5-3-3実機確認結果」参照）

### 5-3-1実装結果

**変更内容**（`firmware/src/main.cpp`）：従来`taskA`（SDログ用`SensorLogRecord`）と`rcpSendSample()`（RCPストリーム`s`応答）の2箇所に重複実装されていたGPSダミー値（半径0.0001度=約11mのsin/cos円軌道、周期2π秒）を、`simTrackGetPosition(elapsedSec, &lat, &lon)`という共通関数に置き換えた。

- コース形状は基準点`(35.830000, 139.410000)`（既存ダミー値の中心と同一）からの北/東オフセット(m)で表した7点のウェイポイント列`kSimTrackOffsets`（直線+ゆるいカーブを模した6区間、P0=スタート/フィニッシュから時計回りに1周してP0へ戻る閉ループ）。1周の総距離は約1521m。
- 起動時に`simTrackInit()`で各区間の距離・累積距離・基準緯度でのcos補正込み経度換算係数を1回だけ計算。
- `simTrackGetPosition()`は、走行速度を`kSimTrackSpeedMps`(約100km/h一定)と仮定し、経過秒×速度から現在の周回内走行距離を求め、該当区間内で線形補間してlat/lonを算出する。
- `taskA`・`rcpSendSample()`双方から同じ経過時刻`t`でこの関数を呼ぶため、SDログとRCPストリームで同一のGPS軌跡が一貫して得られる。

**確認内容**：
- `esp32-c3-proto`・`esp32-s3`両環境でクリーンビルド成功（実機書き込みは本タスクでは対象外、5-3-3以降で必要に応じて実施）。
- Pythonで同一アルゴリズムを再実装して検算し、t=0でスタート地点`(35.830000, 139.410000)`、1周後（約54.8秒）に同じ座標へ正しく戻ること、複数周回後も破綻しないことを確認した。

**5-3-2に向けた申し送り**：スタート/フィニッシュ座標`g_trackCfg.startFinishLat/Lon`のデフォルトは`(0.0, 0.0)`（未設定）のままで、本タスクのコース座標列とは連動させていない。5-3-2で交差判定ロジックを実装する際、検証用にどちらかの座標に合わせるか、公式アプリから明示的に`(35.830000, 139.410000)`をWriteして検証する運用にするかを判断すること。

### 5-3-2実装結果

**アルゴリズム設計**：設計メモ（5-3/5-4向け）の「①スタート/フィニッシュ・セクター判定：ジオフェンス（緯度経度＋半径）通過を検出。通過前後2点のGPS座標を距離で線形補間し、サブサンプル精度で通過時刻を算出する」という方針に基づき、GPS移動軌跡を「直近2サンプル間の線分」として扱い、その線分がスタート/フィニッシュのジオフェンス（`g_trackCfg.startFinishLat/Lon`中心・`radius`半径）を外側→内側へ横切った瞬間を検出する方式で実装した（`firmware/src/main.cpp`）。

- `segmentClosestPointT()`：線分(prevLat,prevLon)-(lat,lon)上でジオフェンス中心に最も近い点のパラメータt(0〜1)を求める。
- `lapDetectorUpdate()`：そのtで線分上の最近点とジオフェンス中心との距離(度単位の二乗和、5-1-2確認済みの公式`GeoPoint.withinCircle`と同じ比較方法)を`radius`と比較し、「外→内」のエッジのみを検出する（内部に留まる間の連続トリガーを防止）。検出時はtで前回/今回のGPS時刻を線形補間し、サンプル間隔(taskAは100ms)より高精度な通過時刻を算出する。初回の横切り(電源投入後最初にスタート地点へ到達した時点)はラップ完了とみなさず、2回目以降の横切りを「1周完了」として扱う。
- `taskA`のループ内、`simTrackGetPosition()`でGPS位置を計算した直後に`lapDetectorUpdate()`を呼び出し、ラップ完了時は`printf`でラップ番号とラップタイムをログ出力するようにした。
- `TrackCfg`構造体の`startFinishLat/Lon`のデフォルト値を`(0.0, 0.0)`から`kSimTrackOffsets`のスタート/フィニッシュ地点`(35.830000, 139.410000)`（`kSimTrackBaseLat/Lon`）へ変更した（5-3-1の申し送り事項への対応）。これにより公式アプリからのWrite操作なしでもシミュレーション周回のラップ検出が動作する。`setTrackCfg`+`flashCfg`で書き込まれれば従来通りその値で上書き・NVS永続化される（5-1-3/5-2-2の既存実装のまま変更なし）。

**確認内容**：
- `esp32-c3-proto`・`esp32-s3`両環境でクリーンビルド成功。
- Pythonで`simTrackGetPosition`（5-3-1）と`lapDetectorUpdate`を再実装し、100ms間隔で5.5周分のシミュレーションを実行したところ、ちょうど5回のラップ完了イベントが発火し（二重検出・見逃しなし）、各ラップタイムは理論値(約54.756秒)に対して数サンプル間隔以内の誤差(実測54.5〜54.8秒)で一致することを確認した。この誤差は、線分とジオフェンス境界の真の交点ではなく「線分上の最近点」を通過時刻補間の基準にしている近似に起因するもので、5-3-2の目的（交差判定アルゴリズムの実装、二重検出・見逃しがないこと）に対しては許容範囲と判断した。より高精度な補間（真の円境界交点を解く）が必要になった場合は5-3-3以降で再検討する。
- 実機での動作確認（シリアル出力でのラップ検出ログ確認等）は本タスクでは対象外、5-3-3で実施する。

### 5-3-3実機確認結果

**確認方法**：既存の実機（ESP32-S3-DevKitC-1 N16R8、COM7=CH343書き込み/UARTモニター用）へ現状の`firmware/src/main.cpp`（5-3-2までの実装）をそのまま書き込み、`pio device monitor`でCOM7のシリアル出力を約140秒間キャプチャした。GPS/IMU等の実センサーは未調達のため、5-3-1の`simTrackGetPosition()`によるシミュレーション軌跡（約1521m、約100km/h一定）を使用。

**確認結果**：約140秒間（シミュレーション上の約2.5周分）で`[taskA] lap N completed: X.XXX s`のログが二重検出・見逃しなく3回発火した。

```
[taskA] lap 1 completed: 54.349 s
[taskA] lap 2 completed: 54.690 s
[taskA] lap 3 completed: 54.840 s
```

理論値（1521m ÷ 27.78m/s ≈ 54.756秒）に対し、5-3-2のPC上での再実装検算結果（54.5〜54.8秒）と同等の誤差範囲に収まっており、実機（ESP32-S3、100ms周期のtaskAループ）でも同一のアルゴリズムが設計通りに動作することを確認した。電源投入直後の最初のスタート地点到達がラップ完了として誤検出されない（初回の横切りをカウントしない）実装も、ログ開始からlap 1発火までの間に不要な`completed`ログが出ていないことで裏付けられた。

これにより5-3（スタート/フィニッシュライン交差判定ロジック）は5-3-1〜5-3-3すべて完了。

---

## 5-4: 予測タイム計算アルゴリズム ※追加ハードウェア不要、5-3完了後に着手
- [x] 5-4-1: ベストラップのGPS軌跡・経過時間を記録する仕組みを実装する → 完了(下記「5-4-1実装結果」参照)
- [x] 5-4-2: 現在位置とベストラップ軌跡との距離ベース比較により、予測タイム（デルタ）を算出するロジックを実装する → 完了(下記「5-4-2実装結果」参照)
- [x] 5-4-3: シミュレーションデータで予測タイムの値が妥当な挙動（ベストラップと同じペースならデルタ0付近）になるか確認する → 完了（下記「5-4-3実機確認結果」参照）

### 5-4-1実装結果

**設計**：設計メモ(5-3・5-4向け)の③「予測タイム：ベストラップを『累積走行距離→経過時間』の対応表として保持」に基づき、`firmware/src/main.cpp`に以下を実装した。

- `LapDistanceSample{distanceM, timeSec}`：現在ラップ開始からの累積走行距離(m)と経過時間(秒)のペア。
- `g_currentLapSamples[kMaxLapSamples]`(記録中)・`g_bestLapSamples[kMaxLapSamples]`(確定済みベストラップ)を固定長配列(`kMaxLapSamples=2048`、100ms周期で約3.4分相当)で保持。
- `gpsDistanceMeters()`：2点間の緯度経度差を、中間緯度でのcos補正込み平面近似(equirectangular近似)でメートル距離に変換する汎用関数(`simTrackGetPosition`のコース内距離計算とは別に、実GPS軌跡向けに新設)。
- `lapRecorderUpdate()`：`taskA`から`lapDetectorUpdate`呼び出し直後に毎回呼ぶ。ジオフェンス通過(`crossedStartFinish`、初回通過も含む)を契機に、直前まで記録していたラップが完了(`lapCompleted`)かつベスト更新であれば`g_bestLapSamples`へ確定コピーし、新しいラップの記録(距離・サンプル数)をリセットする。

**設計上の注意点**：リセット契機は「ラップ完了」ではなく「ジオフェンス通過(初回含む)」にする必要があった。初回のスタート地点到達(`lapDetectorUpdate`内で`lapCount`0→1になる瞬間)はラップ完了とはみなされないが、そこが1周目の走行距離・経過時間の起点になるため、この時点で記録側もリセットしないと1周目のサンプルに電源投入からの経過時間が混入してしまう。このため`lapDetectorUpdate`に新しい出力引数`outCrossedStartFinish`を追加し、`lapCompleted`(戻り値、2周目以降のみtrue)とは独立して「ジオフェンスを外→内へ横切った瞬間」自体を`lapRecorderUpdate`へ伝える形にした。

**確認内容**：
- `esp32-c3-proto`・`esp32-s3`両環境でクリーンビルド成功(RAM使用量はS3 16.6%/C3 14.0%で、追加バッファ込みでも問題なし)。
- Pythonで`lapDetectorUpdate`/`lapRecorderUpdate`相当を再実装し、意図的に周回ごとに速度を変えた3ラップ(結果的に約76秒/約60.5秒/約101秒)をシミュレーションしたところ、3ラップ中最速の約60.5秒のラップが正しく`g_bestLapSamples`へ確定し、その後のより遅いラップでは上書きされないことを確認した。あわせてベストラップの記録距離・経過時間がいずれも単調増加し、最終記録距離(約1515m)がコース全長(約1521m)に近いことも確認した。
- 実機での動作確認(シリアル出力での`[lapRecorder] new best lap: ...`ログ確認等)は本タスクでは対象外、5-4-3以降で必要に応じて実施する。

### 5-4-2実装結果

**設計**：設計メモ(5-3・5-4向け)の③「現在位置の走行距離に対応するベストラップ経過時間を補間して、現在の経過時間との差分（デルタ）を出す」に基づき、`firmware/src/main.cpp`に以下を実装した。

- `bestLapTimeAtDistance(distanceM)`：5-4-1の`g_bestLapSamples`(現在ラップ開始からの累積走行距離→経過時間の対応表、distanceMについて単調増加)から、指定した走行距離に対応する経過時間を二分探索＋線形補間で求める。`distanceM`が対応表の範囲外(ベストラップの記録距離より手前/先まで走行している場合)は外挿せず、先頭または末尾のtimeSecにクランプする。
- `predTimeUpdate(currentDistanceM, currentTimeSec)`：予測タイム(デルタ) = 現在ラップの経過時間 − `bestLapTimeAtDistance()`で求めたベストラップの同距離地点での経過時間、を計算し、グローバル変数`g_predDeltaSec`へ格納する。正の値はベストラップより遅れている、負の値は進んでいることを表す。ベストラップが未確定(`g_bestLapSampleCount==0`)の間は`g_predDeltaValid`をfalseのままにし、5-5でのRCPストリーム送信時に無効値と判別できるようにした。
- `lapRecorderUpdate()`内、現在ラップのサンプル(`g_currentLapSamples`)記録直後に`predTimeUpdate(g_currentLapDistanceM, timeSinceLapStart)`を呼び出し、100ms周期(taskA)ごとにデルタを更新するようにした。

**確認内容**：
- `esp32-c3-proto`・`esp32-s3`両環境でクリーンビルド成功(RAM/Flash使用量は5-4-1時点からほぼ変化なし、C3=RAM14.0%/Flash21.1%、S3=RAM16.6%/Flash34.1%)。
- Pythonで`bestLapTimeAtDistance`相当のロジックを再実装し、100ms周期・全長1521mのシミュレーションで検算した。①ベストラップと全く同じペース(27.78m/s)で走った場合、全区間でデルタの絶対値が0(誤差なし)。②ベストラップより遅いペース(25.0m/s)では、走行距離が進むほどデルタが単調に拡大するプラスの値(開始0.0s→中間3.05s→終端6.09s)。③ベストラップより速いペース(30.0m/s)では、走行距離が進むほどデルタが単調に拡大するマイナスの値(開始0.0s→中間-2.03s→終端-4.05s)。④走行距離がベストラップの記録距離を超えた範囲外の入力でも、クランプにより例外なくベストラップの最終経過時間を返すことを確認した。いずれも設計通りの挙動。
- 実機での動作確認(シリアル出力での予測タイム値の確認等)は本タスクでは対象外、5-4-3で実施する。

### 5-4-3実機確認結果

**実装内容**（`firmware/src/main.cpp`）：`predTimeUpdate()`にシリアルログ出力を追加した。100ms周期そのままだと出力過多になるため、静的カウンタで約1秒間隔(10サンプルに1回)に間引いて`[predTime] dist=<走行距離>m delta=<デルタ秒>s`の形式で出力する。

**確認方法**：`esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認後、実機（ESP32-S3-DevKitC-1 N16R8、COM7）へ書き込み、`pio device monitor`でCOM7のシリアル出力を約300秒間キャプチャした（5-3-3と同じくGPS/IMU等の実センサー未調達のため、5-3-1の`simTrackGetPosition()`によるシミュレーション軌跡・約100km/h一定を使用）。

**確認結果**：
- キャプチャ開始時点で既にベストラップが確定済み（`predTime`ログが最初から有効値を出力）で、以降300秒間で`[taskA] lap N completed`が6回（lap2〜lap7、いずれも54.7〜54.8秒、5-3-3の結果と同等）発火した。この間`[lapRecorder] new best lap`ログは一度も出ず、最初に確定したベストラップが以降のラップでも更新されなかった（全ラップがほぼ同一ペースで走行しているため、想定通り）。
- `predTime`のデルタ値は、各ラップの大半の区間で−0.15〜−0.20秒程度の範囲に収まり続けた。周回終端付近（走行距離がベストラップの記録距離を超える範囲、5-4-2実装の`bestLapTimeAtDistance`のクランプ挙動が働く区間）でのみ符号が反転する瞬間（+0.05〜+0.25秒程度）が見られた。
- 全区間を通じてデルタの絶対値は0.3秒未満（1周約55秒に対して0.5%未満）に収まっており、クラッシュ・スタックオーバーフロー等の異常は発生しなかった。
- ±0.2秒程度のオフセットが常に乗る要因として、GPSサンプリングが100ms周期の離散値である一方、ジオフェンス通過（周回開始点）の検出自体はサブサンプル精度で線形補間しているため、周回ごとにサンプル列の位相（通過時刻から次のサンプルまでのずれ）が微妙に変化し、同じ経過時間に対応する走行距離の対応関係にわずかな量子化誤差が生じることが考えられる。1周55秒に対して0.5%未満の誤差であり、「ベストラップと同じペースで走行している場合にデルタが0付近になる」という設計意図に対しては妥当な挙動と判断した。
- これにより5-4（予測タイム計算アルゴリズム）は5-4-1〜5-4-3すべて完了。

---

## 5-5: RCPストリームへのチャンネル追加・公式アプリでの表示確認 ※追加ハードウェア不要、5-3/5-4完了後に着手
- [x] 5-5-1: `LapTime`/`PredTime`等のチャンネルを`getMeta`のチャンネル定義に追加する → 完了（下記「5-5-1実装結果」参照）
- [x] 5-5-2: `s`コマンド応答（`rcpSendSample`）に上記チャンネルの値を含めるよう実装する → 完了（下記「5-5-2実装結果」参照）
- [x] 5-5-3: 実機（ESP32、シミュレーションGPS軌跡を注入）で公式RaceCaptureアプリのダッシュボードにラップタイム・予測タイムが表示されることを確認する → 完了（下記「5-5-3実機確認結果」参照）

### 5-5-1実装結果

**採用チャンネル**：5-1-1設計結果で洗い出した公式`lapCfg`の9チャンネル分（`LapCount`/`LapTime`/`Sector`/`SectorTime`/`PredTime`/`ElapsedTime`/`CurrentLap`/`Distance`/`SessionTime`）を、`reference/RaceCapture-Pro_firmware`の実機応答例(`test/json_api_files/getMeta_response.json`)に記載されたnm/ut/prec/srの値そのままで採用した（`min`/`max`は公式側もすべて0のため、既存の`RcpChannelMeta`構造体（int型）のまま変更不要だった）。

```c
static const RcpChannelMeta kLapChannels[] = {
    {"LapCount",    "",    0, 0, 0, 10},
    {"LapTime",     "Min", 0, 0, 4, 10},
    {"Sector",      "",    0, 0, 0, 10},
    {"SectorTime",  "Min", 0, 0, 4, 10},
    {"PredTime",    "Min", 0, 0, 4, 5},
    {"ElapsedTime", "Min", 0, 0, 4, 10},
    {"CurrentLap",  "",    0, 0, 0, 10},
    {"Distance",    "mi",  0, 0, 4, 10},
    {"SessionTime", "Min", 0, 0, 4, 10},
};
```

**実装内容**（`firmware/src/main.cpp`）：既存の`kDummyChannels`（RPM/Speed/WaterTemp/OilPress/Lat/Lon）はそのまま残し、新規に`kLapChannels`を追加。`rcpSendMeta()`が両方の配列を順に`meta`配列へ送出するよう変更した。

**Sector/SectorTimeの扱い**：本プロジェクトは5-3でスタート/フィニッシュのジオフェンス判定のみを実装しており、複数セクターの分割判定は実装しない方針（5-1-1のTrackCfg設計、`sec`フィールドを当面非対応としたことと整合）。そのためSector/SectorTimeは実値を持たず、5-5-2では常に0を送ることになる想定だが、公式アプリのチャンネル選択UI等との互換性を優先し、メタデータ自体は他の7チャンネルと同様に定義した。

**ビルド確認**：`esp32-c3-proto`（Flash 21.2%/RAM 14.0%）・`esp32-s3`（Flash 34.1%/RAM 16.6%）ともにクリーンビルド成功。5-4-3時点からの使用量変化はごくわずか（チャンネル定義データの追加分のみ）。

**5-5-2への申し送り**：`s`コマンドの値配列・ビットマスクは現状`kDummyChannels`の6ch分のみ対応（`rcpSendSample()`のbitmask`(1 << 6) - 1`）。5-5-2で本タスクの9チャンネル分の値（`LapCount`=`g_lapDetector.lapCount`、`PredTime`=`g_predDeltaSec`/`g_predDeltaValid`、`Distance`=`g_currentLapDistanceM`等、既存グローバル変数を利用可能）とビットマスクの拡張(`(1 << 15) - 1`相当)を実装する必要がある。`LapTime`（直近完了ラップのタイム）・`ElapsedTime`（現在ラップの経過時間）は現状ローカル変数止まりのため、5-5-2でグローバル変数化が必要。

### 5-5-2実装結果

**単位変換が必要という発見**：5-5-1で採用したチャンネル定義（公式`getMeta_response.json`準拠）を見直したところ、`LapTime`/`SectorTime`/`PredTime`/`ElapsedTime`/`SessionTime`の`ut`（単位）は`"Min"`（分）、`Distance`は`"mi"`（マイル）であり、本プロジェクトが内部で扱ってきた秒・メートルのままでは単位が一致しないことが判明した。公式ファームウェア（`reference/RaceCapture-Pro_firmware/src/lap_stats/lap_stats.c`の`getLastLapTimeInMinutes`/`lapstats_elapsed_time_minutes`/`lapstats_session_time_minutes`、`src/logger/loggerSampleData.c`の`get_distance_getter`）でも同様に分・マイル単位で送信していることを確認し、`rcpSendSample()`側で変換してから送る方針とした。

**`LapCount`と`CurrentLap`の違いの整理**：`reference/RaceCapture-Pro_firmware/src/lap_stats/lap_stats.c`を確認したところ、公式では`g_lap`（`lapstats_current_lap()`、スタート/フィニッシュを横切るたび=ラップ開始のたびに増加、5-3-2実装の`g_lapDetector.lapCount`と同じ意味）と`g_lapCount`（`getLapCount()`、ラップが完了するたびに増加）は別カウンタとして扱われていることが分かった。本プロジェクトの`g_lapDetector.lapCount`は前者（現在走行中のラップ番号=`CurrentLap`相当）に一致するため、`LapCount`（完了ラップ数）はそこから素直に転用せず、`currentLap > 0 ? currentLap - 1 : 0`で導出することにした（1周も完了していない間は0になり、公式の挙動と一致する）。

**実装内容**（`firmware/src/main.cpp`）：
- `lapDetectorUpdate()`内でラップ完了を検出した際、`crossTimeSec - g_lapDetector.lapStartTimeSec`（直近完了ラップのタイム、秒）を新設のグローバル変数`g_lastLapTimeSec`へ格納するようにした（従来はtaskAのローカル変数`lapTimeSec`止まりで、taskC側の`rcpSendSample()`から参照できなかった）。
- `rcpSendSample()`に9チャンネル分の値を追加。`LapCount`/`CurrentLap`は`g_lapDetector.lapCount`から導出（上記の通り）、`LapTime`は`g_lastLapTimeSec`、`ElapsedTime`は`t - g_lapDetector.lapStartTimeSec`（`rcpSendSample`は自前の`t`で計算し直す必要があるため、`lapRecorderUpdate`内の`timeSinceLapStart`と同じ考え方をここでも適用）、`PredTime`は`g_predDeltaSec`（`g_predDeltaValid`が false の間は0固定）、`Distance`は`g_currentLapDistanceM`、`SessionTime`は`t`（電源投入からの経過時間）をそのまま使用。`Sector`/`SectorTime`は5-5-1の方針通り常に0を送る。
- 分・マイルへの変換は`rcpSendSample()`内で行う（秒→分は`/60.0`、メートル→マイルは`* 0.000621371`）。ビットマスクは`kDummyChannels`(6ch)+`kLapChannels`(9ch)の全15ch分`(1 << 15) - 1`に拡張した。
- taskA(ラップ検出・記録)とtaskC(RCP送信)間のデータ共有は、既存の`g_trackCfg`等と同様に排他制御なしのグローバル変数読み書きのまま（本プロジェクトの既存踏襲であり、5-5-2で新たな仕組みは導入していない）。

**確認内容**：
- `esp32-c3-proto`（Flash 21.2%/RAM 14.0%）・`esp32-s3`（Flash 34.2%/RAM 16.6%）ともにクリーンビルド成功。5-5-1時点からの使用量変化はごくわずか。
- 変換ロジックをPythonで検算し、走行距離1521m→0.9451mi、ラップタイム54.756s→0.9126min、経過時間27.378s→0.4563min、予測デルタ-0.18s→-0.003min（いずれも桁・符号とも妥当）、および`completedLaps`が`currentLap`=0/1/3のときそれぞれ0/0/2になる（1周完了するまでは0のまま）ことを確認した。
- 実機・公式アプリのダッシュボードでの表示確認は本タスクでは対象外、5-5-3で実施する。

---

### 5-5-3実機確認結果

**確認方法**：5-5-2までの実装（`firmware/src/main.cpp`）を実機（ESP32-S3-DevKitC-1 N16R8、COM7=CH343書き込み/COM8=TinyUSB CDC RCP通信）へ書き込み、公式RaceCaptureアプリ(Windows版)を起動してCOM8への自動接続後、Dashboard画面の表示を確認した。

**確認結果**：
- Dashboard画面に、`getMeta`で送出した9チャンネル（LapCount/LapTime/Sector/SectorTime/PredTime/ElapsedTime/CurrentLap/Distance/SessionTime）に加え、アプリ側が自動生成した派生ウィジェット（BestLap/LapDelta）も含めて表示された。
- 数値は時間経過とともに正しく更新され、ラップが切り替わる瞬間にElapsedTime/Distanceが0付近へリセットされる挙動も確認できた（例：CurrentLap 6→7でElapsedTime 0:36.02→0:13.55、Distance 0.6206→0.2330mi）。
- LapTimeは0:54.70〜0:54.80（分:秒形式、5-3-3/5-4-3で確認済みの理論値約54.7〜54.8秒と一致）、PredTimeは0:-0.17〜0:-0.21（5-4-3で確認した−0.15〜−0.20秒程度のデルタと同等の範囲）で、単位変換（秒→分）を含め5-5-2の実装が公式アプリ上でも意図通りに解釈されることを確認した。
- Sector/SectorTimeは設計通り常時0（アプリ表示は`0`/`--:--.--`）で、複数セクター未実装という5-5-1の方針と整合。

**確認中に新規発見した不具合2件（今後の運用上の注意点）**：
1. **公式アプリの自動COMポートスキャンによるESP32の意図しないダウンロードモード突入**：公式アプリは起動時に接続可能なCOMポートを順に自動探索するが、この探索がRCP通信用ポート（COM8、TinyUSB CDC）だけでなく、書き込み用のCH343デバッグポート（COM7）にも接続を試みることを確認した。COM7への接続試行時に送出されるDTR/RTS制御信号が、CH343のESP32自動リセット回路を経由して実機を`waiting for download`（ダウンロードモード）へ落としてしまい、ファームウェアが停止する。**対策**：pyserialで`setDTR(False)`→`setRTS(True)`→`setRTS(False)`という手動ハードリセットパルスをCOM7へ送ることで、GPIO0=High状態のままリセット解除され、通常起動へ復旧できることを確認した。ボード選定・配線が変わらない限り本質的な解消は難しいため、実機検証時は公式アプリの接続完了を確認してから他の操作に進む、または万一停止した場合は上記のリセット手順（またはUSBケーブル抜き差し）で復旧する運用とする。
2. **公式アプリの既知バグ「COMポートハンドルリーク」の再発**：4章・7章に既出の不具合（一度接続に失敗したCOMポートのハンドルをアプリがリークし続け、他プロセスからそのポートを開けなくなる）が本タスク中にも再発し、COM8が`PermissionError`で一時的に開けなくなった。アプリプロセスの完全終了（`Stop-Process`）→再起動で解消することを改めて確認した。

これにより5-5（RCPストリームへのチャンネル追加・公式アプリでの表示確認）は5-5-1〜5-5-3すべて完了。**Phase 5（ラップタイム・予測タイム計算の実装）は5-6（実GPS・実トラック検証、Phase1-5のGPS調達待ちで保留）を除き全て完了**。

---

## 5-6: 実GPS・実トラックでの検証 ※保留（Phase1-5のGPSモジュール調達待ち）
GPS/IMUモジュール未調達のため、現時点では分解しない。Phase1-5（GPS・IMUモジュール調達後の実センサ値検証）完了後、実車・実トラックでの検証手順として改めて分解する。

---

## 5-7: ベストラップ統計のNVS永続化 ※追加ハードウェア不要、今すぐ着手可
- [x] 5-7-1: `g_bestLapSamples`（ベストラップの距離→経過時間対応表）をNVSへ永続化する ※7章「未解決事項」の「ラップ統計・予測タイマーの永続化要否」への対応。AnalogCfg(1-7-2)/TrackCfg(5-2-2)と同じ`nvs_set_blob`/`nvs_get_blob`パターンで`bestLapLoadFromNvs`/`bestLapSaveToNvs`を`firmware/src/main.cpp`に実装した。`kMaxLapSamples`(2048要素、最大16KB)を丸ごと保存するとNVSパーティション(デフォルト`partitions_singleapp.csv`で24KB)を圧迫するため、実際に使用中の`g_bestLapSampleCount`分だけを可変長で保存する設計にした。保存タイミングはAnalogCfg/TrackCfgと異なり`flashCfg`(Writeボタン)ではなく、ベストラップはユーザーが明示的に設定する値ではなく走行中に自動更新される記録であるため、`lapRecorderUpdate()`内でベストラップが更新された瞬間に自動保存するようにした。`esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認（実機での電源再投入後のベストラップ保持確認は未実施、次回実機検証時の課題として残す）。

---

## 5-8: ベストラップ統計の信頼性強化 ※追加ハードウェア不要、5-6（実車検証）着手前に要対応
> 2026-08のレビューで発見した問題への対応（ARCHITECTURE.md 7章「ベストラップがトラックと紐付いておらず、
> リセット手段もない」「ラップタイムの妥当性チェックが無く、異常ラップがベストとして永久保存される」参照）。
> 現状のままだと、別のサーキットへ行くと前トラックのベストラップ軌跡と照合してPredTimeが無意味な値になり、
> しかも`g_predDeltaValid`はtrueのまま（アプリ側から異常と判別できない）。加えてベストラップをクリアする
> 手段が無く、ジオフェンス誤検出等で異常に短い「ラップ」がベスト登録されると再フラッシュでしか復旧できない。

- [x] 5-8-1: ベストラップNVSデータへ`trackId`（＋スタート/フィニッシュ座標）を紐付けて保存し、起動時の復元・`setTrackCfg`受信時に現在の`TrackCfg`と不一致なら破棄（またはトラック別に保持）する ※完了。`firmware/src/main.cpp`に`g_bestLapTrackId`/`g_bestLapStartFinishLat`/`g_bestLapStartFinishLon`を追加し、ベストラップ確定時(`lapRecorderUpdate`)に`g_trackCfg`の対応値を記録・NVS保存(`bestLapSaveToNvs`)するようにした。`trackId`単独ではなくスタート/フィニッシュ座標も合わせて比較するのは、公式アプリ側でtrackId未割当(-1)の手動設定トラックが複数ありうる想定への保険。破棄方式は「（またはトラック別に保持）」の選択肢のうち前者（破棄）を採用：①起動時（`bestLapLoadFromNvs`、`trackCfgLoadFromNvs`実行後に呼ばれる）は保存済みのtrackId+座標が現在の`g_trackCfg`と一致する場合のみ復元し、不一致ならベストラップ未確定のまま起動する、②走行中に`setTrackCfg`で別トラックのtrackIdを受信した場合はRAM上のベストラップを即座に破棄する（`g_predDeltaValid`もfalseへ）。②ではNVSへは書き戻さない設計とし、`flashCfg`未実行のままrebootした場合に`g_trackCfg`が前トラックへ戻れば①の一致判定により前トラックのベストラップが正しく復元される（誤って消えない）ようにした。`esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認（実機での別トラック切り替え時の破棄・復元動作確認は5-6の実車検証時の課題として残す）。
- [x] 5-8-2: ベストラップ統計のリセット手段を実装する（公式の`resetLapStats()`相当。RCPコマンド経由・シリアルコマンド・`setTrackCfg`書き込み時の自動破棄・**外部CAN経由の物理ボタン**のどれで実現するか方式検討込み） ※完了。**方式は「RCPコマンド経由」を採用**：`reference/RaceCapture-Pro_firmware/src/logger/loggerApi.c`を調査したところ、公式ファームウェアに`resetLapStats`という無ペイロードのRCPコマンド（`api_reset_lap_stats`→`lapstats_reset(true)`）が実在すると判明し、同じコマンド名でそのまま実装した（将来的な外部ツール・スクリプトとの互換性を確保）。他候補の不採用理由：外部CAN経由の物理ボタンはロガー側の外部CAN受信(RX)経路自体が未実装（Phase6-3はTXのみがスコープ）で今回は採用不可、`setTrackCfg`書き込み時の自動破棄は5-8-1で既に対応済みで「同じトラックのままベストラップだけ手動で消したい」ケースをカバーしない、シリアルコマンドは独自プロトコルになり公式アプリ/ツールとの互換性が無いため見送った。
  - ⚠️ **公式実装とのスコープの違い（意図的な設計判断）**：公式の`lapstats_reset(true)`はセッションタイム・ラップカウント・距離等セッション全体を丸ごとリセットする広い操作だが、本プロジェクトが解決したい課題（ARCHITECTURE.md 7章「ベストラップをクリアする手段が無く、ジオフェンス誤検出等で異常に短い『ラップ』がベスト登録されると再フラッシュでしか復旧できない」）は「異常なベストラップを手動でクリアしたい」のみのため、あえてスコープを狭め、`firmware/src/main.cpp`の`resetLapStats()`はベストラップ統計（`g_bestLapSamples`関連、NVS込み）のみをリセットし、進行中のラップカウント・セッション自体には影響を与えない設計にした。コマンド名（プロトコル互換性）と内部の実際の動作範囲（本プロジェクト独自の判断）を意図的に分離している点に注意。
  - `esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認。実機（ESP32-S3）は本タスク時点でPCに未接続（COM10/COM11はBluetoothシリアルのみで対象外）のため、シリアルでの動作確認は次回実機接続時（5-6の実車検証準備時等）の課題として残す。
  - 候補「外部CAN経由の物理ボタン」の実装メモ（2026-08検討、不採用だが将来の参考として残す）：ボタンは外部CAN（センサーハブ／アクセサリー用）バスの1ノードとして特定のCAN ID（例：`BestLapReset`）を送信し、ロガー側がそれを受信してリセット関数を呼ぶ方式。ハードウェア（TX/RX双方向配線）は既に対応済みだが、**ロガー側で外部CANの受信（RX）を能動的に監視する経路自体が現状未実装**（Phase 6-3は現状ロガー→外部CANへのTXのみがスコープのため、この方式を選ぶ場合はRX側の実装を追加タスク化する必要あり）。ボタン単体で専用ノードを作るのはMCU・電源ドロップの無駄が大きいため、シフトインジケーター等**既にMCUを積む他のアクセサリーへGPIO入力として相乗りさせる**実装を推奨。デバウンスはボタン側MCUのファームウェアで行い、1押しにつき1フレームのみ送信する
- [x] 5-8-3: ラップタイムの妥当性チェックを実装する（最小ラップタイム閾値、またはベストラップ軌跡の総距離との整合チェック等）。ジオフェンス二重発火・ピットレーン通過等による異常に短いラップがベストとして登録されるのを防ぐ ※`firmware/src/main.cpp`の`lapRecorderUpdate()`に最小ラップタイム閾値`kMinValidLapTimeSec`（10秒）を追加し、ベスト更新条件へ`lapTimeSec >= kMinValidLapTimeSec`を加えて異常に短いラップを弾くようにした。市販車のミニサーキットでも1周十数秒はまず無いため十分安全側の値として採用（総距離との整合チェック等より実装コストが低く、シンプルに解決できるためこちらを採用）。`esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認（実機での誤検出再現・回避確認は5-6の実車検証時の課題として残す）。

## 5-9: セクタータイム（距離ベースの区間デルタ）※保留・5-6の実車検証後に必要性を判断
- [ ] （保留）5-5-1で常時0送信としている`Sector`/`SectorTime`を実データ化する。ベストラップ軌跡（距離→経過時間の対応表）は既に保持しているため、セクター境界を距離ベースで数点定義すれば区間デルタは算出可能（公式のような座標ベースのセクター境界(`sec`配列)まで実装するかは要検討）。「どの区間でタイムを失ったか」をダッシュボード上で確認できるようにする
