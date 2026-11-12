# CAN受信 + OBD限定送信 / ファン解析 2026-09-15

## 導入結果
- firmware `logger-v1-obdonly-20260915c` 実機へ書込み、ハッシュ照合、版の読戻し完了。NVS保持。
- EcoCapture 0.3.10を起動しStatusを表示。スタートメニューも更新。
- OBD有効を本体へ保存・読戻し。CAN受信を継続しながら標準OBDと限定した2つのMazda読取を送信。
- 任意CAN・制御命令は禁止。Mode01は対応照会00/20/40とPID0C/0D/11/04/05/0F/42/5C。Mode22は0x7E0宛てDID1103/0967だけ（NCEC時のみ）。送信関数の直前に宛先/形式/サービス/項目/パディングを検査。
- 1要求ずつ、全体最大10要求/秒。single-shot、無応答時に要求間隔を延長。CAN異常でOBD停止。通常CANの高精度RPM/速度などはOBD値で上書きしない。
- CANループ試験コマンドは引き続き拒否。ユーザーのOBD停止操作でlisten-onlyへ戻る。

## 検証
- C#115チェック、Python17テスト、C++ASan/UBSanのOBDスケジューラ・許可/拒否・2項目診断読取テスト合格。
- Windows/Linux ARM64ビルド・ZIP監査合格。Linux ARM64実機未実行。
- 20画面スモーク合格。実機USBチェック合格、18車両値受信、BadFrames=0。Statusに「CAN受信＋OBD読取のみ送信」。
- 49秒で受信約700 frame/s、SD約100 Hz（整数秒と更新単位による概算100.88）。CANエラーとSD欠落の増加0。
- OBD要求258、応答186（ファン候補応答11を含む）。標準要求タイムアウト66、ファン候補タイムアウト5。全要求が返答されるわけではなく、失敗時は間隔を延長している。
- 送信受付エラー0。CANエラー累計394はOBD開始直後の観測開始時から存在し、観測中の増加0。全セッションでエラーゼロとは扱わない。
- 生ログ末尾4,252フレームを読み戻し、送信要求36本が全て許可した読取のみ、最小要求間隔100,004 usを検査。TX_REQはドライバ受付記録で、バス上の送信成功/ACKそのものの証明ではない。
- 追加取得：EngineLoad=43.53%、BatteryVolt=13.469V（観測例）。OilTempは未受信。

## ファンの解析結果
- 旧セッション64MBの生CANから65区間・33,173フレームを抽出し16IDを調査。全量連続解析ではない。
- 0x420 byte5/6の0x40はエンジン停止/再始動と同時に変化。ファンを特定する根拠にはできない。byte1/3は多値。
- 公開OBD定義にファンリレー候補あり：DID1103 A bit2/3、DID0967 A bit2（bit0=LSB）。実車で両DIDの応答が得られた。
- 生応答例：7E8 `04 62 11 03 00 00 00 00`、7E8 `05 62 09 67 00 00 00 00`。取得時の候補ビットはすべて0。
- Statusに「リレー指令候補1/2/3」を表示。応答未受信・古い場合 --。ファンの実際の回転は「未確認」を維持。
- ファンON時の実物照合が残る。ユーザーは以前のON/OFF時刻を覚えていない。次の安全な停車時に「いまファンON」と知らせてもらう質問を送信済み。走行中の操作・空ぶかしは依頼していない。
- 将来の照合ではSDの生CANとOBD応答を同じ時計で比較する。ファン状態の変化を自然に観測し、リレー指令と実回転を区別する。未確定のビットを確定として扱わない。

## 資料と証拠
- 公開候補：https://www.mazda-forum.info/threads/thermostat-mx-5ncfl.79214/
- 使用者の照合報告：https://forum.miata.net/vb/archive/index.php/t-631418-p-2.html
- `firmware/logger_v1/artifacts/fan_20260915/FAN_ANALYSIS.md`
- `firmware/logger_v1/artifacts/obdonly_20260915/{after_flash.json,live_obd.json,obd_raw_tail.csv,audit.json,upload.log}`
- `EcoCapture/artifacts/obd-live-20260915/{ncec-live.json,status-live-bottom.png}`
- `EcoCapture/artifacts/smoke-0310/ui-smoke.json`
- パッケージ：`firmware/logger_v1/artifacts/logger-v1-obdonly-20260915c.zip`、`EcoCapture/dist/EcoCapture-0.3.10-windows-x64.zip`。
