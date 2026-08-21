# Phase 6 サブタスク分解（計算チャンネルの汎用化・CANブロードキャスト & Luaスクリプティング機構の実装）

> ARCHITECTURE.md「5. 開発ロードマップ」のPhase 6は粒度が粗いため、
> 実作業はこのファイルの単位（1チャット=1タスク）で進める。
> 完了したタスクはこのファイル内でチェックし、Phase全体が終わったらARCHITECTURE.mdへ
> 結論だけ転記してarchive/へ移動する運用（8章のルールに準拠）。
>
> 背景：走行中でも視認できる高輝度サブディスプレイ（デルタタイム等の表示用）を、ロガー本体
> （ESP32）とは別のMCUを積んだ拡張アクセサリーとしてCANバスに接続する構成で検討している。
> 「拡張アクセサリーは各自MCUを積んでCANのノードとして生きる」方針のもと、ロガー本体で計算した
> 全チャンネル（LapTime/PredTime等の既存チャンネルに加え、将来追加するオーバー/アンダーステア
> 検出等の新チャンネルも含む）をCANバスへ流せるようにする。
>
> 併せて、計算チャンネルの追加を「ファームウェアを触れる人（開発者）」に限定せず、公式
> RaceCaptureと同様に「アプリのScript画面からLuaスクリプトを書くことで非開発者でも追加できる」
> 形にする（省エネカー研究部への引き継ぎを見据えた判断、詳細は本チャットでの議論を参照）。
> 公式ファームウェアのLua処理系（`reference/RaceCapture-Pro_firmware/lib/lua`、`src/lua/`）を
> 参考にするが、ソースの直接移植ではなく本プロジェクト独自のFreeRTOSタスク構成に合わせて
> 作り直す。バインディング関数は公式の全量（約50個）を再現せず、`addChannel`/`getChannel`/
> `setChannel`を中心とした必要最小限のみを初期スコープとする。
>
> ハードウェア（アクセサリー側MCU本体）は友人へ製作を依頼中で未調達のため、本Phaseは
> **ロガー本体（ESP32）側の実装まで**をスコープとする。アクセサリー側MCUの実装・実機結合試験は
> ハードウェア到着後に別Phaseとして分解する（保留）。
>
> 送信先の物理バスについて（`ARCHITECTURE.md`「CANゲートウェイ構成」参照）：6-3で実装する
> CANブロードキャストの送信先は**外部CAN（センサーハブ／アクセサリー用）バスのみ**とする。
> 車載CAN（OBD2タップ）側は引き続き**受信専用（listen-only）**のまま変更せず、送信は行わない
> （純正ECU側への影響を避けるため）。ロガー本体は車載CAN・外部CANの両方に接続し、車載CANで
> 受信した値もあわせて外部CAN側へ中継する「ゲートウェイ」役を兼ねる。

---

## 6-1: 共通チャンネルテーブルの設計・実装 ※追加ハードウェア不要、今すぐ着手可
- [x] 6-1-1: RCPシリアル送信・CAN送信・Luaバインディングの3経路が共有する内部チャンネルテーブル（チャンネル名・現在値・単位・精度等）のデータ構造を設計する → 完了（下記「6-1-1設計結果」参照）
- [x] 6-1-2: 既存のLapTime/PredTime等9チャンネル（Phase 5で実装済み、`firmware/src/main.cpp`にハードコードされた個別送信処理）を、6-1-1のテーブル方式へ移行する → 完了（下記「6-1-2実装結果」参照）
- [ ] 6-1-3: 共通チャンネルテーブルを出力元とするSDカードCSVライターを実装し、現状の固定13列CSV（`kSdCsvHeader`）とテレメトリーチャンネル群（LapTime/PredTime/Roll/Pitch等23ch）のスキーマ乖離を解消する ※2026-08レビューで発見（ARCHITECTURE.md 7章「SDログのスキーマがテレメトリーチャンネル群から乖離」参照）。セッション区切り・絶対時刻の設計（同7章、`task_phase1_breakdown.md`の1-2-6）と整合を取ること
- [ ] 6-1-4: 100チャンネル級のスループットを実機で実測する ※2026-08の検討で「帯域計算上は100ch×100Hzでも0.1〜0.2MB/秒程度でSDMMC(4bit/20MHz)の余力に収まるはず」という試算をしたが、実測はまだ行っていない。6-1-3実装後、実機（ESP32-S3-DevKitC-1）でダミー値による100チャンネル級・高頻度（50〜100Hz、1-1関連の高速化タスクとも整合）の書き込みを一定時間走らせ、①`fsync`込みの実際の書き込み所要時間がサイクル周期に収まるか、②キュー溢れ(dropped)が発生しないか、③1-2-1で確認済みのSDMMC 4bit信号品質問題(GNDリターン電流経路不足によるCRCエラー)が高頻度書き込みで再発しないか、を確認する

### 6-1-1設計結果

**現状確認**：`firmware/src/main.cpp`のチャンネル定義は`kDummyChannels`(6ch)/`kLapChannels`(9ch)/
`kImuChannels`(6ch)/`kAttitudeChannels`(2ch)の4つの独立した`RcpChannelMeta`（`nm`/`ut`/`min`/`max`/
`prec`/`sr`のメタデータのみ、値は保持しない）静的配列に分散している。`rcpSendMeta()`はこの4配列を
順に走査してメタデータを送るだけだが、`rcpSendSample()`側は各チャンネルの値を配列とは独立に
1行ずつ手書きしており（`d.add(...)`の羅列、ダミーチャンネルは`sin(t/N)`のその場計算、ラップ/IMU/
姿勢チャンネルはグローバル変数`g_lapDetector`/`g_imuAccel*`/`g_attitude*Deg`を直接参照）、
**配列の並び順とハードコードされた`d.add()`呼び出し順が一致していることに暗黙で依存**している
（ビットマスクも`(1 << 23) - 1`の決め打ち）。CAN送信（6-3）・Luaバインディング（6-5）が今後
「同じ値」を必要とする際、この手書きコードを経由しないと値を得られず、経路ごとに同じ計算を
再実装することになってしまう。これが解消したい問題。

**設計方針**：メタデータ（既存の`RcpChannelMeta`相当）に加えて「現在値を格納・取得する仕組み」を
持つ`ChannelDef`構造体を新設し、固定長配列＋使用数カウンタ（本プロジェクトで一貫している
`kMaxLapSamples`等と同じ、動的確保を避ける組み込み向けパターン）で管理する。

```c
// イメージ（6-1-2で実際の移行と併せて確定）
struct ChannelDef {
    const char *nm;
    const char *ut;
    int min, max, prec, sr;

    // 値の取得方法は2通りをサポートする：
    // (a) sample != nullptr: 既存のグローバル変数(taskA等が継続更新)やその場計算(sin波等)を
    //     ラップする関数。呼ぶたびに最新値を返す。既存23チャンネルはすべてこちら側になる見込み。
    // (b) sample == nullptr: valueフィールドを直接読み書きする。Lua addChannel(6-5-3)で
    //     動的追加されるチャンネルはこちら（他に継続更新してくれる場所が無いため、
    //     setChannelがこのvalueへ直接書き込む）。
    double (*sample)();
    double value; // sample()が無い場合の実値。sample()がある場合も直近値のキャッシュとして
                  // channelTableSync()実行時に書き込まれ、CAN送信(6-3)等が使い回せる。
};

constexpr size_t kMaxChannels = 64; // 既存23ch + Lua動的追加分の余裕
static ChannelDef g_channelTable[kMaxChannels];
static size_t g_channelCount = 0; // 起動時に既存チャンネルで初期化、addChannelで増える

// 全sample()持ちチャンネルを1回ずつ呼び出し、valueキャッシュを最新化する。
// rcpSendSample()の冒頭・CANブロードキャストの送信直前等、値を使う直前に呼ぶ想定。
void channelTableSync();

// 名前引き(Lua addChannel/getChannel/setChannel用)。チャンネル数が小規模(数十件)な
// 組み込み用途のため線形探索で十分と判断、ハッシュテーブル等は導入しない。
int channelFindByName(const char *nm); // 見つからなければ-1
```

**ID・参照方法**：チャンネルIDは配列インデックスをそのまま使う（本セッション中は安定、
NVS等での永続参照は現時点で不要と判断）。CAN送信（6-3）のフレームエンコードもLuaバインディング
（6-5-3）の`getChannel`/`setChannel`も、このインデックスまたは`channelFindByName()`で引いた
インデックス経由でテーブルへアクセスする。

**移行方針（6-1-2以降で段階的に実施）**：6-1-2は`kLapChannels`(9ch)を対象に、`sample`関数
（例：`LapTime`用に`g_lastLapTimeSec / 60.0`を返す関数）でラップし`g_channelTable`へ登録する
形で移行する。この時点では`rcpSendMeta`/`rcpSendSample`は新旧混在（`kLapChannels`分だけ新方式、
残りは既存のまま）でよく、既存の応答内容が変わらないことをビルド＋可能なら実機/`rcp_mock_device.py`
比較で確認する。残り3グループ（`kDummyChannels`/`kImuChannels`/`kAttitudeChannels`）の移行は
6-1-2の中で続けて行うか、6-2（`getMeta`の完全動的化、全チャンネルがテーブル化されている必要あり）
着手までに済ませるかは、6-1-2着手時に作業量を見て判断する（無理に1タスクへ詰め込まない）。

**あえて採用しなかった案**：値の取得を全チャンネル`sample()`関数方式に統一する案（`value`
フィールドを持たせない案）も検討したが、Lua `addChannel`で動的追加されるチャンネルには
「継続的に値を更新してくれる既存のグローバル変数・タスク」が存在しないため、`setChannel`が
直接書き込める`value`スロットが必要と判断し、`sample`/`value`のハイブリッド方式を採用した。

### 6-1-2実装結果

`firmware/src/main.cpp`に6-1-1設計通りの`ChannelDef`/`g_channelTable`/`channelRegister`/
`channelTableSync`/`channelFindByName`を実装し、`kLapChannels`(9ch: LapCount/LapTime/Sector/
SectorTime/PredTime/ElapsedTime/CurrentLap/Distance/SessionTime)を対象に移行した。

- 各チャンネルの値計算（従来`rcpSendSample()`内に手書きされていたもの）を`sampleLapCount()`
  等9個の`sample`関数へ切り出し、`channelTableInitLapChannels()`（`app_main()`冒頭で1回呼び出し）
  で`g_channelTable`へ登録する。
- `rcpSendMeta()`は`kLapChannels`配列への直接ループを、`g_channelTable`（現状はこの9ch分のみ）
  へのループに置き換えた。
- `rcpSendSample()`は9個の`d.add()`手書き呼び出しを`channelTableSync()`＋テーブルループに
  置き換えた。JSON上の型（int/double）は元の実装と同じになるよう、`prec==0`のチャンネル
  （LapCount/Sector/CurrentLap）のみintで送る規則で統一した。
- `kDummyChannels`(6ch)/`kImuChannels`(6ch)/`kAttitudeChannels`(2ch)の3グループは今回は
  移行せず`RcpChannelMeta`のまま据え置き（6-1-1設計結果の想定通り、新旧混在）。
- `esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認。ハードウェア未接続のため
  実機/`rcp_mock_device.py`との応答比較は未実施（次回実機検証時に確認）。

## 6-2: `getMeta`の動的化 ※6-1完了後に着手
- [ ] 6-2-1: 現状の静的配列(`kDummyChannels`/`kLapChannels`)を、6-1のチャンネルテーブルから動的に生成する方式へ変更する
- [ ] 6-2-2: 実機・公式アプリでチャンネル数が変動しても`getMeta`応答が正しく追従することを確認する

## 6-3: 計算チャンネルのCANブロードキャスト実装 ※6-1完了後に着手
- [ ] 6-3-1: チャンネル値をCANフレームとして定期送信するためのメッセージID割り当て・フォーマット（1フレームに詰める値の数、スケーリング等）を設計する
- [ ] 6-3-2: 6-3-1の設計に基づき、ESP32側のCAN送信（TX）処理を実装する（現状ESP32はCAN受信専用、TXパス自体が新規）
- [ ] 6-3-3: 実機でCAN送信フレームをロジックアナライザ/CANスニファ等で観測し、設計通りの内容が流れていることを確認する
- [ ] （保留）アクセサリー側MCUでの受信・デコード・表示実装：ハードウェア未調達のため本Phaseでは分解しない。到着後に別Phaseとして分解する

## 6-4: Lua VM移植 ※6-1と並行着手可
- [x] 6-4-1: `reference/RaceCapture-Pro_firmware/lib/lua/src`相当の標準Lua本体（プラットフォーム非依存のANSI C部分）をfirmwareへ組み込み、PlatformIOビルドが通ることを確認する → 完了（下記「6-4-1実装結果」参照）
- [x] 6-4-2: Lua用メモリアロケータをESP-IDFのヒープAPI（`heap_caps_malloc`等）に差し替える → 完了（下記「6-4-2実装結果」参照）
### 6-4-2実装結果

`firmware/src/main.cpp`に`luaEspAlloc()`（`lua_Alloc`シグネチャ、`heap_caps_realloc`/
`heap_caps_free`で標準`malloc`/`free`/`realloc`ベースの既定実装`l_alloc`(`lauxlib.c`)を置換、
`MALLOC_CAP_DEFAULT`指定）を実装した。`nsize==0`のケースは`heap_caps_realloc`に0バイト
reallocとして委ねず、明示的に`heap_caps_free()`へ分岐する（標準realloc実装の慣例通り）。

動作確認として`luaAllocSelfTest()`を追加し、`app_main()`起動時に(1)`lua_newstate(luaEspAlloc, ...)`
でVM生成、(2)`luaL_openlibs()`で標準ライブラリを開く（この過程で多数のアロケーションが発生）、
(3)`return 1 + 41`を実行して結果が42であることを確認、(4)`lua_close()`で解放、という一連の
自己診断を行う（1-1-1のhelloTask等と同じ「起動時に動かして確かめる」パターン）。専用FreeRTOS
タスクでの周期実行は6-4-3で実装するため、現時点は起動時1回のみの自己診断。

`esp32-c3-proto`/`esp32-s3`両環境でビルド成功を確認。Flashサイズが6-4-1完了時点
（277140/406277 bytes）から390896/496313 bytesへ増加しており、リンカの`--gc-sections`で
除去されず`liblua.a`が実際にリンクされ動作していることを裏付けている。ハードウェア未接続
（ESP32実機がこのセッションでは接続されていない）のため、シリアル出力での`lua OK`ログ確認は
次回実機接続時の課題。

- [x] 6-4-3: Luaスクリプトを定期実行する独立FreeRTOSタスク（公式の`luaTask.c`の`onTick`呼び出しループに相当）を、本プロジェクトの既存タスク構成（taskA/B/C）に影響しない優先度・スタックサイズで実装する → 完了（下記「6-4-3/6-4-4実装結果」参照）
- [ ] 6-4-4: スクリプト本体は起動時（またはスクリプト書き込み時）に一度だけ実行し、以降は`onTick`関数のみを周期呼び出しする、という公式の実行契約を再現する → 「起動時に一度だけ実行＋以降onTickのみ周期呼び出し」の部分は6-4-3実装と同時に完了済み（下記参照）。「スクリプト書き込み時の再実行」は6-6（`setScriptCfg`実データ化）でスクリプト書き込みの実イベント自体が実装されてから対応するため、6-6着手時まで未完了のまま残す

### 6-4-1実装結果

**vendoring方針**：`reference/RaceCapture-Pro_firmware/lib/lua/src`のうち、同ディレクトリの
`Makefile`が定義する`CORE_O`（VM本体）＋`LIB_O`（標準ライブラリ）相当に、`luaconf.h`が実際に
要求する`modp_numtoa.c`（数値→文字列変換、`lua_number2str`マクロが無条件で使用）を加えた
計31ソース＋24ヘッダーを`firmware/lib/lua/`へ直接vendoringした（`firmware/lib/minmea/`と
同じ「PlatformIOのlib/配下フラット配置」パターン）。以下は対象外とした：
- `liolib.c`（ファイルI/Oライブラリ）：元の`Makefile`の`LIB_O`にも含まれておらず、
  vendoring元自体がこのプロジェクト向けに除外済みだった。
- `lua.c`/`luac.c`/`print.c`：スタンドアロンCLI(`lua`)・バイトコードコンパイラ(`luac`)用。
  本プロジェクトは独自のFreeRTOSタスクからVMを直接呼ぶ設計（6-4-3）のため不要。
- `mod_string.c`/`mod_string.h`：`lib/lua/src`内のどのファイルからも参照されておらず
  （`lstrlib.c`等からincludeされていない、リンク対象にもなっていない）、vendoring元の
  実験的コード・不要ファイルと判断し除外した。

**`main.cpp`側の変更**：`extern "C" { #include "lua.h" / "lauxlib.h" / "lualib.h" }`を追加。
これはVMを実際に使うためではなく、PlatformIOのLibrary Dependency Finder（chainモード）に
`lib/lua/`の存在を認識させ、実際にコンパイルさせて`-Werror`込みのビルド確認を行うための
最小限の変更（`lib/minmea`と同じ扱い）。VM初期化・スクリプト実行呼び出しは未実装。

**`-Werror`起因で判明した、vendoring元の問題と対応**（いずれも動作を変えない最小修正）：
- `bit.c`（ビット演算ライブラリ）：`BIT_OP`マクロ内の`for`文と後続文が同一行にあり
  `-Werror=misleading-indentation`で停止 → `for`の本体を`{}`で明示。
- `ldebug.c`/`ltable.c`：`case`文末の意図的なfallthroughが`/* go through */`
  `/* else go through */`というコメントで書かれていたが、GCCが認識するfallthrough
  コメント文言（`fall through`等）と一致せず`-Werror=implicit-fallthrough`で停止
  → `ldebug.c`はコメントを`/* fall through */`に修正、`ltable.c`はcaseブロックの閉じ括弧
  との間にコメントを挟む形だったため認識されず、`__attribute__((fallthrough));`文に置換。
- `llex.c`：`luaX_lexerror()`（内部で`longjmp`相当のエラー投げのみ、`noreturn`指定なし）
  呼び出し後にswitchのcaseが続き`-Werror=implicit-fallthrough`で停止 → 到達しないことを
  明示する`break;`を追加。
- `lstrlib.c`：`string.format`の`%x`/`%X`書式指定子が`modp_itoaX()`を呼ぶが、この関数は
  vendoring元（`reference/RaceCapture-Pro_firmware`）にも実装が存在しない呼び出しのみの
  状態（`-Wimplicit-function-declaration`で停止）。同ファイル内で`%c`/`%o`/`%u`が既に
  「使うまで無効化」されている前例に倣い、`%x`/`%X`も同様にコメントアウトして対応。
- `modp_numtoa.c`：内部の定数配列`pow10`が、riscv32ツールチェーン(picolibc)が提供する
  非標準関数`pow10(double)`と名前衝突（`-Werror=unused-const-variable`込みで停止）
  → `kModpPow10`へリネーム。

**ビルド確認**：`esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認。リンカの
`--gc-sections`により、現時点では`main.cpp`側がLuaのシンボルを一切呼び出していないため
`liblua.a`は最終バイナリサイズに影響していない（6-4-3で実際にVMを初期化・呼び出す段になって
初めて計測に現れる）。

### 6-4-3/6-4-4実装結果

`firmware/src/main.cpp`に専用タスク`luaTask`を実装し、`app_main()`から
`xTaskCreate(luaTask, "task_lua", 8192, nullptr, tskIDLE_PRIORITY, nullptr)`で起動する。

- **優先度**：既存タスク（taskB=`tskIDLE_PRIORITY+3`／taskA=`+2`／taskC=`+1`）に一切影響
  しないよう、アイドルタスクと同じ最低優先度(`tskIDLE_PRIORITY`)とした。
- **スタックサイズ**：公式`luaTask.c`のコメント「Luaパーサはスタックを大量消費する」を踏まえ、
  taskC(8192バイト)と同じ値を暫定採用（実測チューニングは実機到着後の課題）。
- **実行契約(6-4-4)**：`luaTask`起動直後に`luaL_dostring()`でスクリプト本体を一度だけ実行し、
  以降はforループで`onTick`グローバル関数の有無を確認し、存在すれば`lua_pcall()`で呼び出す
  （1Hz、`vTaskDelay`）。`onTick`未定義はエラー扱いしない（公式実装のIssue #707対応を踏襲、
  「onTickを持たないスクリプトも合法」という判断）。
- **未実装部分**：6-6（`setScriptCfg`/`getScriptCfg`の実データ化）が未着手のため、スクリプト
  本文は`kLuaPlaceholderScript`（`tickCount`をインクリメントするだけのダミー）をハードコード
  している。「スクリプト書き込み時の再実行」（公式は書き込み検知でスクリプトを再ロードする）は
  6-6でスクリプト書き込みイベント自体が実装されてから対応する（現状の設計では、書き込み検知の
  シグナルを受けたら同じ`luaL_dostring()`ロジックを再実行するだけで済む見込み）。

`esp32-c3-proto`/`esp32-s3`両環境でビルド成功を確認。ハードウェア未接続のため、実機での
`tickCount`の増加確認・スタックサイズの妥当性確認は次回実機接続時の課題。

## 6-5: Luaバインディング層の実装（CAN生フレーム読み取り＋チャンネル登録に特化） ※6-1・6-4完了後に着手
> 方針（本チャット議論より確定）：外部アクセサリーはCANバスを読むだけの構成とするため、Luaが
> GPIOやPWM等のハードウェアを直接操作する必要はない。一方、「まだファームウェアがデコードして
> いない生のCAN ID」もLuaスクリプト側で自由にデコードして新チャンネルとして命名・公開したい
> （Pattern B）ため、`rxCAN`相当（生CANフレーム読み取り）は必要。GPIO/PWM/アナログ出力/
> シリアルI/O/ShiftX/セルラー等、公式バインディングの大半（約45個）は恒久的に非対応とする。
- [x] 6-5-1: （6-1・6-4いずれにも依存せず今すぐ着手可）生CANフレームの共有リングバッファを設計・実装する。ESP32(TWAI)のハードウェア受信
      フィルタが1系統のみ（`sdkconfig.esp32-s3`の`CONFIG_SOC_TWAI_MASK_FILTER_NUM=1`で確認済み）
      という制約があるため、ハードウェアフィルタは素通し設定にし、全フレームをバッファへ蓄積、
      ID単位のフィルタリングはLua側（ソフトウェア）で行う方式とする。既存のOBD2/車速デコード
      処理（Phase 2実装分）もこのバッファ経由に統一できないか合わせて検討する
      → 完了。`firmware/src/main.cpp`に車載CAN(内蔵TWAI)受信を実装した。
      - 🔴 **実装時に判明した重要な訂正**：本プロジェクトのESP-IDF（`framework-espidf 6.0.1`）では
        レガシーTWAIドライバ（`driver/twai.h`、`twai_receive()`によるポーリング型）が非推奨化され
        `#warning`が発せられ、本プロジェクトの`-Werror`設定によりビルド停止することが判明した。
        新ドライバ（`esp_twai.h`/`esp_twai_onchip.h`、`twai_new_node_onchip()`）へ切り替えて対応。
        新ドライバは**イベントコールバック方式**（`twai_node_register_event_callbacks()`の
        `on_rx_done`がISRコンテキストで呼ばれ、その中で`twai_node_receive_from_isr()`により
        フレームを取り出す設計）のため、当初想定していた「専用の受信タスク（ブロッキング
        ポーリングループ）」は不要と判明し、ISRコールバック内で直接`xQueueSendFromISR()`により
        共有キュー（`g_canRxQueueHandle`、FreeRTOSキューをリングバッファとして使用、既存の
        `taskAToTaskCQueueHandle`等と同じパターン）へ書き込む設計に変更した
      - GPIO割り当て（`kCanTxPin`=GPIO4、`kCanRxPin`=GPIO5）は友人による最終基板配線
        （`logger_v1.net`）がまだGPIO番号レベルまで確定していないため、`kImuSdaPin`等と同じ
        考え方でSDMMC/IMU I2Cと衝突しない空きピンを暫定選定した（実配線確定時に見直す）
      - フィルタは`mask=0`（全ビットdon't care）の標準(11bit)ID全域受信に設定。ハードウェア
        フィルタが1系統のみという制約上、標準ID全域と拡張ID全域を同時には受信対象にできない
        ため、OBD2診断通信が標準ID主体という想定に基づき標準ID側を採用した（実車で拡張ID
        主体と判明した場合は要見直し、コード内にコメントで明記済み）
      - 車載CANは`enable_listen_only`のまま維持（送信は行わない、`task_phase6_breakdown.md`
        冒頭の背景注記の方針通り）。ボーレートは`hardware_interface_spec.md`記載の500kbps固定
      - `esp32-c3-proto`/`esp32-s3`両環境でクリーンビルド成功を確認。外部トランシーバ
        (MCP2562FD-E/P)は実機に未接続のため、`twai_new_node_onchip()`自体の成功可否・実際の
        フレーム受信確認はハードウェア接続後の実機検証が必要（初期化失敗時も`app_main`は
        継続する設計にしたため、他機能への影響なく安全に試せる）
      - 読み出しAPI`canRxPop()`は6-5-2（Luaの`rxCAN`相当バインディング）で使用する想定のため
        現時点では未呼び出し。`[[maybe_unused]]`を付与し`-Werror`の未使用関数警告を回避した
- [ ] 6-5-2: 6-5-1のバッファから生CANフレーム（ID・データバイト列）をLuaへ渡す`rxCAN`相当の
      バインディング関数を実装する
- [ ] 6-5-3: `addChannel`/`getChannel`/`setChannel`を、6-1の共通チャンネルテーブルへの読み書き
      として実装する。Luaスクリプトから任意の名前で新チャンネルを登録できることを確認する

## 6-6: `setScriptCfg`/`getScriptCfg`の実データ化 ※6-4・6-5と並行着手可（公式アプリでの実機観測が必要）
- [ ] 6-6-1: 公式アプリ（Windows版）のScript編集画面での送受信をシリアルログ等で観測し、スクリプト本文のページ分割・チャンク転送フォーマットを確定する
- [ ] 6-6-2: 6-6-1の仕様に基づき、現状ダミー応答のスタブになっている`setScriptCfg`/`getScriptCfg`を実データ化する（受信したスクリプトの保存先はNVS想定、Phase 5のTrackCfg等と同じ`nvs_set_blob`/`nvs_get_blob`パターンを踏襲）

## 6-7: スクリプト実行の信頼性設計 ※6-4完了後に着手
- [ ] 6-7-1: 不正なLuaスクリプト（無限ループ・実行時エラー）が発生した場合でも、taskA/B（CAN受信・GPS/IMU処理・SD書き込み等のコア機能）に影響しないことを設計する
- [ ] 6-7-2: 公式の「3回連続失敗でLED点滅ループに入り、watchdogリセット+ボタン長押しでバイパス」という復旧手段を再現するか、簡略版（例：シリアルコマンドでのスクリプトクリア）にするかを判断し実装する
- [ ] 6-7-3: 実機で意図的に壊れたスクリプトを書き込み、コア機能（記録・CAN受信）が継続することを確認する

## 6-8: 実機での統合動作確認 ※6-1〜6-7完了後に着手
- [ ] 6-8-1: 公式アプリのScript画面から実際にLuaスクリプトを書き、`addChannel`/`setChannel`で計算チャンネルを追加し、`getMeta`/Dashboard表示に正しく反映されることを実機で確認する
- [ ] 6-8-2: 6-3で実装したCANブロードキャストに、6-8-1で追加したLua計算チャンネルの値も正しく乗ることを確認する
