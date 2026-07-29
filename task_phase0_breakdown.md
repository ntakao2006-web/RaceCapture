# Phase 0 タスク分解・作業ログ

> Phase 0は0-1〜0-7完了済み。残るは0-8のみで、粒度としてはこれ以上分解不要な
> 1チャット=1タスクの大きさのため、他タスクへの分解はせずここに作業ログのみ残す。

## 0-8: センサーキャリブレーション設定コマンド（getAnalogCfg/setAnalogCfg）

### やったこと
- `reference/RaceCapture-Pro_firmware`の`test/json_api_files/get|setAnalogCfg*.json`
  および`test/loggerApi_test.cpp`でリクエスト/レスポンスの実仕様を確認。
- `rcp_mock_device.py`に実装済み：
  - `capabilities.channels.analog`を0→1に変更（`getAnalogCfg`を公式アプリに
    自動要求させるため。他chan(imu/gpio/timer/pwm/can/obd2/canChan)は引き続き0のまま）。
  - `make_default_analog_cfg()`：nm/ut/min/max/sr/prec/scalMod/scaling/offset/alpha/cal/
    map(raw/scal 5点)のデフォルト値。
  - `getAnalogCfg`ハンドラ：index指定(int)なら単一ch、`null`なら全ch分を
    `{"analogCfg":{"<idx>":{...}, ...}}`で返す。
  - `setAnalogCfg`ハンドラ：`{"<idx>":{フィールド部分更新}}`を受け取り、
    既存設定にマージして保存（mapはネストされたdictなので個別update）。
    応答は`{"setAnalogCfg":{"rc":1}}`。
  - `flashCfg`ハンドラ：**今回新たに必要と判明**。setAnalogCfgでWrite操作をすると
    公式アプリは続けて`{"flashCfg":<val>}`を送ってくる（NVSコミット相当）。
    これに応答しないと`Timeout waiting for 'flashCfg'`でWrite全体がエラーになる。
    応答は`{"flashCfg":{"rc":1}}`。
  - **重要な仕様修正**：`API_SUCCESS`は`0`ではなく`1`と判明
    （`reference/RaceCapture-Pro_firmware/include/api/api.h`より）。
    `rcp_mock_device.py`内の`API_SUCCESS`定数を1に修正済み。

### 確認できたこと
- ロジック単体（フェイクシリアルでの直接呼び出し）ではget/setの読み書き往復が
  正しく動作することを確認済み。
- 公式アプリ実機(Windows版、COM3⇔COM4のcom0com仮想ペア)との接続で：
  - 接続確立時に自動で`getAnalogCfg`が呼ばれ、Setup > Analog Sensors画面に
    デフォルト値(Analog0, 0-5V, sr:10Hz等)が正しく表示されることを確認。
  - Setup > Analog Sensors > Readボタンでの明示的な再読み込みも成功。
  - チャンネル名変更 → Writeボタン押下 → **flashCfg未実装の状態では
    "Could not write configuration: Timeout waiting for 'flashCfg'"エラーで失敗**
    （これが上記flashCfgハンドラ追加のきっかけ）。

### 未完了・次回やること
- **flashCfgハンドラ追加後の再検証が未完了**。Writeボタン押下で正常に
  `{"setAnalogCfg":{"rc":1}}` → `{"flashCfg":{"rc":1}}`の順で応答し、
  エラーダイアログが出ずに書き込みが成功することを実機アプリで確認する。
- 作業中、RaceCaptureアプリ側で「一度失敗したCOMポートのハンドルをリークし
  続けるバグ」(`HANDOFF.md`既知の問題)に再度遭遇。対処法は同じく
  「モック側を正しい状態で先に起動 → アプリを完全終了(プロセス確認)
  → アプリを再起動」の順序を守ること。
- 作業終盤、RaceCaptureアプリのハンバーガーメニュー等のUIクリックが
  反応しなくなる現象が発生（原因未特定。アプリ再起動で解消する可能性が高い）。
  再開時はアプリを一度完全終了してから再起動して試すこと。
- 上記が確認でき次第、0-8を完了とし、ARCHITECTURE.mdの該当チェックボックスを
  更新する。

### 再開手順（作業を中断・シャットダウンした場合）
1. `Get-Process racecapture, python | Stop-Process -Force`で残存プロセスを一掃
2. モックデバイスを先に起動：
   `python rcp_mock_device.py --port COM4 --baud 115200`
3. モックが安定稼働している(数秒待って生きているか確認)のを確かめてから
   公式アプリ(`C:\Program Files (x86)\RaceCapture\racecapture.exe`)を起動
4. 接続確立後、Setup > Analog Sensors > 値を変更 > Write を試し、
   `rcp_capture.jsonl`のログで`setAnalogCfg`→`flashCfg`の応答が
   正しく返っているか、アプリ側にエラーダイアログが出ないかを確認
