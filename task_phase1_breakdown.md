# Phase 1 サブタスク分解（卓上動作検証）

> ARCHITECTURE.md「5. 開発ロードマップ」のPhase 1（1-1〜1-5）は粒度が粗いため、
> 実作業はこのファイルの単位（1チャット=1タスク）で進める。
> 完了したタスクはこのファイル内でチェックし、Phase全体が終わったらARCHITECTURE.mdへ
> 結論だけ転記してarchive/へ移動する運用（8章のルールに準拠）。

---

## 買い物（最優先・すぐ発注可能）
- [ ] P-1: 3.3V専用・SD信号8ピン全出し（DAT0-3/CMD/CLK/VDD/VSS）のmicroSDブレイクアウトモジュールを購入する（SPI/SDMMC両対応。C3試験用・S3本番用として同一型番を2台）
- [ ] P-2: 高耐久microSDカード（SanDisk High Endurance等、32GB程度）を購入する

---

## 1-1: タスク分離基盤（FreeRTOS雛形）※追加ハードウェア不要、今すぐ着手可
- [x] 1-1-1: `xTaskCreate()`で最小のタスクを1つ起動し、一定間隔でシリアルにログを出す（Hello Taskレベルの疎通確認）※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。シリアルログに`[helloTask] alive`が一定間隔で出力されることを確認
- [x] 1-1-2: タスク間通信用のキュー（`QueueHandle_t`）を1本作り、別タスクからPush/Popできることを確認する ※実機書き込み・動作確認済み。`[queuePushTask] pushed: N`→`[queuePopTask] popped: N`の対応を確認
- [x] 1-1-3: タスクA（受信役）の雛形を作る。中身はダミーのカウンタ値を生成し、一定間隔でキューにPushするだけ ※実機書き込み・動作確認済み。`[taskA] pushed dummy value: N`が継続出力されることを確認
- [x] 1-1-4: タスクC（USB/シリアル送信役）の雛形を作る。キューからPopした値をSerialへ出力するだけ ※実機書き込み・動作確認済み。`[taskC] sent to serial: N`が継続出力されることを確認
- [x] 1-1-5: タスクAとタスクCを同時起動し、A→キュー→Cの流れが途切れず動くことを確認する（タスク分離の最小形が完成） ※1-1-3/1-1-4の時点でapp_main内に両タスクが統合済みのためコード変更なし。実機書き込み・動作確認済み。taskA/taskCの値が一致し途切れず流れることを確認（"queue full, dropped"のようなキュー溢れログは未観測）
- [x] 1-1-6: ARCHITECTURE.md記載のタスク優先度（タスクB=最優先／タスクA=高優先／タスクC=低優先）を実コードに反映し、狙い通りの優先度で動いているか確認する ※タスクBはSDモジュール未調達のため優先度検証用のダミー処理（ビジーループ）で雛形実装。実機書き込み・動作確認済み。taskB/taskA/taskCが破綻なく並行動作することを確認。ただし意図的な高負荷時のプリエンプション厳密検証までは未実施

---

## 1-3: RCPプロトコルのESP32移植 ※追加ハードウェア不要、今すぐ着手可
- [x] 1-3-1: USB CDCシリアル経由で1行分のJSONを受信し、`\r`区切りで1メッセージとして切り出す受信パーサを実装する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`rcpReceiveTask`として追加。1バイトずつ受信し`\r`区切りで切り出したメッセージを`printf`でログ出力する雛形（タスクA/B/Cとは独立。1-3-7でタスクCへ統合予定）。PCから直接`{"getVer":null}\r`を送信し、`[rcpReceiveTask] message: {"getVer":null}`が返ることを確認。なお手動テストがしやすいよう1-1の常時ログ出力タスク（helloTask/queuePushTask/queuePopTask/taskA/taskB/taskC）の起動は一時的にコメントアウト中（1-3-7で復活予定）。また`platformio.ini`に`monitor_eol = CR`/`monitor_echo = yes`を追加し、シリアルモニターでEnterを押した際に`\r`のみ送信・入力文字をエコー表示するようにした
- [x] 1-3-2: `getVer`受信時に`{"ver":{...}}`を返す最小実装を作り、PCのシリアルターミナルから手動送信して応答を確認する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`rcpReceiveTask`にJSONパース(`rcpHandleMessage`)と応答送信(`rcpSendJsonLine`/`rcpSendVer`)を追加（`firmware/usb_otg_test/src/main.cpp`の実装を参考に、行末は`\r\n`で送信）。PCから`{"getVer":null}\r`を送信し、`{"ver":{"name":"RCPMK3","fname":"RaceCapture/Pro MK3 (esp32-c3 proto fw)","major":2,"minor":16,"bugfix":1,"serial":"C3PROTO01","git_info":"esp32-c3-proto-build","release_type":"release"}}`が返ることを確認
- [x] 1-3-3: 残り6つの接続必須コマンド（`getCapabilities`/`getLapCfg`/`getTrackCfg`/`getCanCfg`/`getObd2Cfg`/`getConnCfg`）に空応答を実装する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`rcpSendCapabilities()`（HANDOFF.md記載の通り`flags`を空リスト、`channels.*`と`db.tracks/sectors`を全て0にして条件付き追加コマンドを回避）と`rcpSendEmptyObjectResponse()`（`lapCfg`/`trackCfg`/`canCfg`/`obd2Cfg`/`connCfg`共通の空オブジェクト応答）を追加し、`rcpHandleMessage`にディスパッチを追加。PCから6コマンドを順に送信し、`{"capabilities":{...}}`および各`{"xxxCfg":{}}`が期待通り返ることを確認
- [x] 1-3-4: 実機（XIAO ESP32C3）をPCに接続し、公式RaceCaptureアプリが実機を認識・接続完了するか確認する（Phase1-3の最重要マイルストーン）※`firmware/src/main.cpp`（1-3-1〜1-3-3実装済みのRCP受信タスク）をビルドし実機（COM5）へ書き込み・動作確認済み。PCの公式RaceCaptureアプリ(Windows版)を起動したところ、`Searching COM5`表示後に自動接続し、タイトルバーに実機の`getVer`応答由来のバージョン文字列（`RaceCapture/Pr...32-c3-proto-build`）が表示され、接続状態インジケーターが点灯。セットアップウィザードをスキップしてメイン画面（Dashboard/Analysis/Setup）まで到達し、SetupのFirmwareタブでReboot/Update Firmware/Factory Reset（いずれも実機接続時のみ有効化される操作）が有効表示されていることを確認し、実機との接続完了を確認した
- [x] 1-3-5: `getMeta`応答（ダミーチャンネル定義）を実装する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`rcpSendMeta()`を追加し、`rcp_mock_device.py`のCHANNELSと同内容のダミーチャンネル定義(RPM/Speed/WaterTemp/OilPress/Lat/Lon)を`{"meta":[...]}`として返す実装（1-3-6でも同じ定義を流用予定）。PCから`{"getMeta":null}\r`を直接送信し、`{"meta":[{"nm":"RPM",...},...,{"nm":"Lon",...}]}`が正しく返ることを確認。**副産物として重要なバグを1件修正**：`usb_serial_jtag_write_bytes`は内部のTXリングバッファ(デフォルト256バイト)を超えるサイズを一度に渡すと、`portMAX_DELAY`で待っても入る余地がないため即座に失敗する(`getVer`/`getCapabilities`等256バイト未満の既存応答では顕在化していなかった)。`rcpSendJsonLine`を128バイトチャンク分割送信に修正して解消。既存コマンド(`getVer`/`getCapabilities`/`getLapCfg`/`getConnCfg`)への影響がないことも回帰確認済み。
- [x] 1-3-6: `s`コマンドへダミーテレメトリ値を返す実装をし、公式アプリのダッシュボードに数値が表示・変動することを確認する（Phase0のモックで確認できた内容を実機で再現） ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`rcpSendSample()`を追加し、`rcp_mock_device.py`の`sample_values()`と同じ考え方（sin波ベースの緩やかな変動）でkDummyChannels（RPM/Speed/WaterTemp/OilPress/Lat/Lon）6ch分のダミー値を`{"s":{"t":<tick>,"d":[...],}}`形式で生成し、`s`コマンド受信の都度返す実装（HANDOFF.md記載の通り、接続後アプリが`{"s":0}`を約1Hzでポーリングしてくる仕様に合わせ、自発的なストリーミング送信ではなく応答ベースで実装）。公式アプリ(Windows版)でダッシュボードに数値が表示され、変動することを確認した。
- [x] 1-3-7: 1-1で作ったタスク構成に、1-3のRCP応答処理をタスクC側へ統合する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。それまで独立タスク`rcpReceiveTask`として動いていたUSB CDC受信・RCP応答処理（`firmware/src/main.cpp`）を、1-1で作ったタスクC本体へ統合（`rcpReceiveTask`は削除）。統合後のタスクCは1ループ内で(1)タスクAのダミー値キューを非ブロッキングでPopしてログ出力、(2)USB CDC経由のRCPメッセージ受信・応答、の両方を行う。あわせてapp_mainで1-3-1時点でコメントアウトしていたhelloTask/queuePushTask/queuePopTask/taskA/taskB/taskCの起動を復活（1-1-6の優先度設計：タスクB=最優先／タスクA=高優先／タスクC=低優先のまま）。PCから直接`{"getVer":null}\r`を送信し、他タスクのデバッグログ（`[helloTask] alive`等）が混在する中でも`[taskC] rcp message: {"getVer":null}`のログと共に正しい`{"ver":{...}}`応答が返ることを確認。公式アプリでの見た目確認はユーザー側で実施し、他タスクのデバッグログ混在下でも正常に接続・動作することを確認済み。

---

## 1-2: SD保存の信頼性検証 ※P-1/P-2の到着待ち（C3試験段階はSPIモード。C3はSDMMCホスト非搭載のため）
- [ ] 1-2-1: SDモジュールをSPIモードで配線し、ESP-IDFのFATFSサンプルでマウント・簡単な書き込みテストができることを確認する
- [ ] 1-2-2: リングバッファ（タスクA→タスクB間）のデータ型・サイズを設計する
- [ ] 1-2-3: タスクB（SD書き込み役）の雛形を作り、ダミーデータをCSV形式でSDに書き込む
- [ ] 1-2-4: `flush()`のタイミング（何行毎/何ms毎）を決めて実装する
- [ ] 1-2-5: 通電中にUSBケーブルを強制的に抜く（擬似電源断）テストを複数回行い、直前まで書いたデータが壊れずファイルに残っているか確認する

---

## 1-4 / 1-5（後続フェーズ）
GPS・IMU・ESP32-S3が未調達のため、現時点では分解しない。1-2完了後、調達状況を見て改めて分解する。
※1-4（ESP32-S3への切り替え）には、SD接続をSPIからネイティブSDMMC（4bit）へ切り替える作業を含める予定（要プルアップ抵抗の確認、ARCHITECTURE.md「7. 未解決事項」参照）。

---

## 1-6: スマホ版RaceCaptureアプリとのUSB OTG通信検証 ※追加ハードウェア不要 → 完了（結論：ESP32-S3移行が必須）
- [x] 1-6-1: RCPプロトコル応答ロジックを検証用ファームウェア(`firmware/usb_otg_test/`。Phase1本開発とは別のPlatformIOプロジェクトとして分離)としてESP32-C3のネイティブUSBへ移植する
- [x] 1-6-2: PCの公式RaceCaptureアプリ(Windows版)を実機ESP32C3へ接続し、プロトコル応答が正しいことを確認する
- [x] 1-6-3: 同じ書き込み済み実機をスマホ(Pixel 9a)へUSB OTG接続し、スマホ版RaceCaptureアプリで接続できるか検証する
- [x] 1-6-4: RaceCaptureアプリで接続できなかったため、Android汎用USBシリアルターミナルアプリ(Serial USB Terminal)で代替検証し、プロトコル応答自体はAndroid経由でも正しく動作することを確認する（Android OS自体はデバイスを正しく認識・列挙できていることも確認）
- [x] 1-6-5: RaceCaptureアプリが接続できない根本原因を特定する
  → 結論：ESP32-C3のネイティブUSB(USB Serial/JTAGコントローラ)は、シリアル通信とJTAGデバッグを1つの複合USBデバイスとして同居させる**固定機能ハードウェアペリフェラル**であり、ソフトウェア(TinyUSB等)でJTAGを持たないシンプルなCDC専用ディスクリプタに作り変えることができない。RaceCaptureアプリはこの想定と異なる複合ディスクリプタ構成のデバイスを「利用可能なUSBデバイスがない」として拒否する。
  → Bluetooth接続も代替案として検討したが、ESP32-C3はBLEのみ対応でClassic Bluetooth(SPP)非対応。RaceCaptureアプリのBluetooth実装はClassic Bluetooth(SPP)方式とみられ、C3では同様に実現困難と判断。
  → **結論：ESP32-S3への移行(Phase1-4)が必須。以後はS3実機での再検証に進む。**

※検証過程で、テスト用スマホ本体のAndroid OSレベルの不具合（無関係な第三者アプリの`device_filter.xml`不正記述によるUSBデバイス解決処理のクラッシュ）にも遭遇し、これが原因でRaceCapture以外のアプリも含めてUSBデバイスの権限付与が機能しない状態になっていた。該当アプリを無効化し端末を再起動することで解消したが、プロジェクトのコードとは無関係な当該スマホ固有の環境要因のため詳細は割愛する。

---

## 1-7: センサーキャリブレーション設定コマンドのESP32実装 ※追加ハードウェア不要（ダミー値で検証）、Phase0の0-8完了後に着手推奨
> 背景：`HANDOFF_claudeai_chat_gap.md`由来の議論より、公式アプリでの較正操作にはロガー側での`getAnalogCfg`/`setAnalogCfg`（5点マップ`map.raw`/`map.scal`＋線形式`scaling`/`offset`/`cal`等）の実データ読み書きが必要と判明。現状（1-3-3時点）は接続確立に必要な範囲のみ空応答で済ませており、この系統のコマンドは未実装。仕様は`reference/RaceCapture-Pro_firmware`（`test/json_api_files/setAnalogCfg*.json`等）を参照し、実際の確定はPCでの実機観測（Wireshark／シリアルログ）を優先する（`reference/RaceCapture_App_fork_ryandoherty`はバージョン不一致の可能性がある参考情報として扱う）。

- [x] 1-7-1: 0-8で確定したJSON形式に基づき、`setAnalogCfg`受信時にチャンネル定義・較正値をESP32側のメモリ上（まずはRAM、永続化は1-7-2）に保存する実装を追加する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`AnalogChannelCfg`構造体（0-8の`rcp_mock_device.py`と同じフィールド構成：nm/ut/min/max/sr/prec/scalMod/scaling/offset/alpha/cal/map.raw[5]/map.scal[5]）とRAM上のグローバル配列`g_analogCfg[kAnalogChannelCount]`（`kAnalogChannelCount=1`、疎通確認用ダミー1ch）を追加。`rcpSendCapabilities()`の`channels.analog`を0-8と同様に`kAnalogChannelCount`へ変更し、公式アプリから`getAnalogCfg`/`setAnalogCfg`が要求されるようにした。`setAnalogCfg`受信時は送られてきたフィールドのみ既存設定へ部分マージする（`analogCfgApplyFields`）。あわせて`flashCfg`応答（`API_SUCCESS=1`固定、0-8で確認済みの通りこれがないと公式アプリがWriteをタイムアウトエラー扱いにする）も実装。PCからシリアル経由で`setAnalogCfg`→`flashCfg`→`getAnalogCfg`を送信し、変更した値（`scaling:2.5, scalMod:1`）が正しく読み返されることを確認した。
- [x] 1-7-2: 保存した較正値をNVS（不揮発領域）へ書き込み、再起動後も保持されることを確認する ※実機（Seeed XIAO ESP32C3, COM5）書き込み・動作確認済み。`firmware/src/main.cpp`に`analogCfgSaveToNvs()`/`analogCfgLoadFromNvs()`を追加し、`nvs_set_blob`/`nvs_get_blob`で`AnalogChannelCfg`構造体（POD、ポインタなし）をそのままblobとして`analogcfg`namespaceの`ch<index>`キーへ保存・復元する方式にした。保存タイミングは`flashCfg`受信時（Writeボタン相当、1-7-1のコメント通りNVSコミット相当のタイミング）。`app_main`冒頭で`nvs_flash_init()`（`ESP_ERR_NVS_NO_FREE_PAGES`/`ESP_ERR_NVS_NEW_VERSION_FOUND`時は`nvs_flash_erase()`して再初期化するESP-IDF定型パターン）を追加し、`analogCfgInitAll()`はデフォルト値セット後にNVSがあれば上書きするよう変更。PCから`setAnalogCfg`(`scaling:3.75, offset:0.5, scalMod:1`)→`flashCfg`で書き込み後、pyserialでDTR/RTSリセットパルスを送り実機を再起動、`getAnalogCfg`で同じ値が正しく読み返されることを確認した。
- [x] 1-7-3: `getAnalogCfg`受信時に保存済みの値を正しく返す実装を追加する ※1-7-1と同時に実装・実機確認済み（`rcpSendGetAnalogCfg()`。`getAnalogCfg:null`で全ch、整数指定で単一chに対応）。詳細は1-7-1参照。
- [x] 1-7-4: 実機（ESP32）でダミーチャンネルに対し、公式アプリの較正UIから値を設定→保存→再読み込みという一連の流れが正しく動作することを確認する ※実機（Seeed XIAO ESP32C3, COM5）・公式RaceCaptureアプリ(Windows版)で確認済み。**副産物として重要な不具合を1件修正**：Analog SensorsタブのWrite操作は、開いているタブに関わらず`setLapCfg`等の他カテゴリのset系コマンドも一括で送信するため、未実装のままだと`Timeout waiting for 'setLapCfg'`でWrite全体がエラーになった。既に空応答を返している`getLapCfg`/`getTrackCfg`/`getCanCfg`/`getObd2Cfg`/`getConnCfg`と対になる`setLapCfg`/`setTrackCfg`/`setCanCfg`/`setObd2Cfg`/`setConnCfg`を`{"<cmd>":{"rc":1}}`を返すだけのスタブとして追加し解消（`rcpSendSetCfgAck()`）。修正後、公式アプリでAnalog0の較正値（`scaling:3.5, offset:0.3, scalMod:2`、5点マップも変更）をUIから設定・Write・画面遷移後の再読み込みで正しく表示されることをユーザー確認。念のためPCから直接`getAnalogCfg`を送信し、同じ値がNVS経由で正しく保持されていることも確認した。
