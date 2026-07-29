# Phase 0 タスク分解・作業ログ（完了・アーカイブ済み）

> Phase 0は0-1〜0-7完了済み。残るは0-8のみで、粒度としてはこれ以上分解不要な
> 1チャット=1タスクの大きさのため、他タスクへの分解はせずここに作業ログのみ残した。
> 0-8完了により、Phase 0は全タスク完了。結論はARCHITECTURE.md 4章へ転記済み。

## 0-8: センサーキャリブレーション設定コマンド（getAnalogCfg/setAnalogCfg）→ 完了

### やったこと
- `reference/RaceCapture-Pro_firmware`の`test/json_api_files/get|setAnalogCfg*.json`
  および`test/loggerApi_test.cpp`でリクエスト/レスポンスの実仕様を確認。
- `rcp_mock_device.py`に実装：
  - `capabilities.channels.analog`を0→1に変更（`getAnalogCfg`を公式アプリに
    自動要求させるため。他chan(imu/gpio/timer/pwm/can/obd2/canChan)は引き続き0のまま）。
  - `make_default_analog_cfg()`：nm/ut/min/max/sr/prec/scalMod/scaling/offset/alpha/cal/
    map(raw/scal 5点)のデフォルト値。
  - `getAnalogCfg`ハンドラ：index指定(int)なら単一ch、`null`なら全ch分を
    `{"analogCfg":{"<idx>":{...}, ...}}`で返す。
  - `setAnalogCfg`ハンドラ：`{"<idx>":{フィールド部分更新}}`を受け取り、
    既存設定にマージして保存（mapはネストされたdictなので個別update）。
    応答は`{"setAnalogCfg":{"rc":1}}`。
  - `flashCfg`ハンドラ：setAnalogCfgでWrite操作をすると公式アプリは続けて
    `{"flashCfg":<val>}`を送ってくる（NVSコミット相当）。これに応答しないと
    `Timeout waiting for 'flashCfg'`でWrite全体がエラーになるため追加。
    応答は`{"flashCfg":{"rc":1}}`。
  - **重要な仕様修正**：`API_SUCCESS`は`0`ではなく`1`と判明
    （`reference/RaceCapture-Pro_firmware/include/api/api.h`より）。
    `rcp_mock_device.py`内の`API_SUCCESS`定数を1に修正。

### 確認できたこと（最終検証まで完了）
- ロジック単体（フェイクシリアルでの直接呼び出し）でget/setの読み書き往復が
  正しく動作することを確認。
- 公式アプリ実機(Windows版、COM3⇔COM4のcom0com仮想ペア)との接続で：
  - 接続確立時に自動で`getAnalogCfg`が呼ばれ、Setup > Analog Sensors画面に
    デフォルト値(Analog0, 0-5V, sr:10Hz等)が正しく表示されることを確認。
  - Readボタンでの明示的な再読み込みも成功。
  - Mode変更(Raw→Linear)・scaling値変更 → Write実行 →
    `rcp_capture.jsonl`ログで`{"setAnalogCfg":{"rc":1}}`→`{"flashCfg":{"rc":1}}`
    の順で正しく応答し、アプリ側にエラーダイアログが出ないことを確認。
  - Write後にReadで再読み込みし、`scalMod:1, scaling:1.025`が正しく
    永続化されていることを確認（`analogCfg`応答の値で検証）。
  - → **公式アプリとの読み書き疎通、完全に確認完了**。

### 作業中に遭遇した環境上のトラブル（参考記録）
- RaceCaptureアプリ側で「一度失敗したCOMポートのハンドルをリークし続ける
  バグ」(`HANDOFF.md`既知の問題)に再度遭遇。対処法は「モック側を正しい状態で
  先に起動 → アプリを完全終了(プロセス確認) → アプリを再起動」の順序を守ること。
- 作業中、実機ESP32のUSBケーブルを抜いた際にモックデバイスプロセスが
  意図せず終了する事象があった。原因は特定できていないが、モックデバイスの
  生存確認をしてからアプリを起動する運用でワークアラウンド済み。
- タスクマネージャー等の他ウィンドウがRaceCaptureウィンドウの前面に残ると
  操作不能になることがあった。その場合は該当ウィンドウを閉じる。
