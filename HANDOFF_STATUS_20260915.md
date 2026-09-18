# Status / CAN送信禁止 実機確認 2026-09-15

## 導入済み
- EcoCapture 0.3.9。通常起動とスタートメニューのリンクを版付きディレクトリへ更新。Statusを表示して起動。
- firmware logger-v1-status-rxonly-20260915b 書込み・書込みハッシュ照合完了。NVS保持。
- 車載CAN切離しのユーザー返答後にSDを安全停止して書込み。再接続前にlisten-onlyと送信禁止フラグを確認。
- CAN1送信APIと通常モードの経路を削除。送信キュー0。保存されたOBD有効設定も起動時無効化。車載CAN切離し中のOBD有効要求とループ試験要求は実機でrc=-1拒否。
- Statusに後輪スリップ・旋回差の参考警告、冷却系、CAN送信禁止状態。警告は他の画面にも表示。

## 検証
- C# 111チェック、Python契約17テスト合格。ファームビルド成功。
- WindowsとLinux ARM64をエクスポートしZIP・CPU種類・同梱ランタイムを監査。ARM実機は未実行。
- 最終アプリ20画面のスモークテスト合格。実機USBチェック合格、18車両項目受信、BadFrames=0。
- 再接続後35秒でCAN約695.9 frame/s。SDは約100 Hz（整数秒の稼働時間による概算100.54）。CANエラーとSD欠落の増分0、OBD送信0。
- 新版の観測時点でSD drops=0 / errors=0。前版セッションの起動時213件の欠落とは別セッション。
- 実機のStatus画面で「送信禁止・本体で固定」を確認。警告の発火・解除は模擬データで検証。実車で意図的な横滑り試験はしていない。

## 残件と範囲
- ファン信号は資料に未定義。表示は「未確認」。水温/A/Cは受信実測値。ファン状態そのものは未実装であり、既知信号の提供または実際の自然ON/OFFとの照合が必要。
- IMU取付方向は未確認、校正も加速度条件を満たしていないため旋回推定は無効。4輪の後輪スリップ監視は有効。
- 舵角なしの参考判定。実走行精度未検証。警告はPCアプリ内であり車両制御は行わない。
- 送信禁止はこのファームによる固定であり、物理配線によるTX遮断ではない。将来別ファームを書込む場合には別途確認が必要。

## 証拠
- firmware/logger_v1/artifacts/status_20260915/{build.log,upload.log,after_flash.json,live.json}
- EcoCapture/artifacts/status-live-20260915/{ncec-live.json,status-live.png,status-live-bottom.png}
- EcoCapture/artifacts/smoke-039-final/ui-smoke.json
- EcoCapture/artifacts/package-audit.json
- EcoCapture/NCEC_V1.md に判定条件。

補足：新版CANエラー累計は再接続後の観測開始時点で1件、35秒後も1件で増加なし。
