# NCEC V1 / EcoCapture 0.3.8 実機反映完了

## 現状（2026-09-15 最終更新）

- ユーザーによるCAN切り離し後、SD安全停止を確認し新版を書き込み済み。フラッシュ照合成功。
- バージョンlogger-v1-ncec-20260915a、schema97、95チャンネルを実機読戻し。
- 設定と水平校正は書き込み前後で一致。NC受信専用・OBD送信OFFを維持。
- CAN再接続後61秒間：約692fps、SD約100Hz、SD欠落/CANエラー/USB欠落の増加0。
- 起動直後SD欠落213、再接続前後CANエラー30は累計に残る。原因は未確定、通常観測中は増加なし。完全無欠落の起動として扱わない。
- 実USB配布アプリで17項目＋燃料平均の全項目を確認。不正フレーム0、COM10で受信継続。
- SD CSVは時刻2列＋95列。末尾55行の追加項目値・冗長値一致・正常クローズを確認。
- ユーザー操作に対してブレーキ・クラッチの0→1→0を観測。サイドブレーキは1を保持。
- 通常設定をバックアップしてVehicle=roadster/CanEnabled=trueへ変更し、EcoCapture0.3.8を起動中。
- スタートメニューEcoCapture.lnkの起動先を0.3.8へ更新。旧配布物は保持。
- IMU校正は52〜53/255。車体水平校正・長時間走行・起動時欠落の原因対策は残る。

## 完成物

- firmware/logger_v1/artifacts/release_20260915_ncec/ （flash.ps1同梱）
- firmware/logger_v1/artifacts/logger-v1-ncec-20260915a.zip
- firmware.bin SHA256: 41d45c4963d775c94c426717c52c4aa8404f1242752317a86d592ca9f9c87e0f
- EcoCapture/dist/EcoCapture-0.3.8/EcoCapture.exe （付属dataフォルダーも必要）
- EcoCapture/dist/EcoCapture-0.3.8-windows-x64.zip
- EcoCapture/dist/EcoCapture-0.3.8-linux-arm64.zip
- 仕様：EcoCapture/NCEC_V1.md

既存82chの番号を保ち13ch追加、全95ch。標準schema97。
提供資料の17項目＋燃料2秒平均。NCの未確定EngineLoad換算は削除。
ECU絶対ペダル%とスロットルを分離。未知DID・OBD自動開始・外部CAN送信は追加しない。

## 検証

- final PlatformIOビルド成功（build-final.log）。firmware.bin 625056 bytes、image checksum/hash valid。
- ASan/UBSan：NCECデコード、実SD抜粋1641フレーム再生、既存C++5本。
- Python17試験、アプリ102チェック。
- 最終Windows配布版16画面を描画して目視確認（smoke-038-final）。
- Windows/ARM64 ZIP CRC、内容・ランタイム・アーキテクチャ監査合格。
- 新版の実機書き込み・USBとSDの追加項目照合は上記のとおり完了。
- 基板や回路、EcoCapture-Web、公開クラウドへは変更していない。

## 証拠と今後の注意

firmware/logger_v1/artifacts/roadster_20260915/ の upload.log、after_flash.json、settings_readback.json、
live_new_firmware.json、new_sd_verification.json、new_sd_tail.csv、switch_check.json。
EcoCapture/artifacts/ncec-live-20260915/ncec-live.json と ncec-live-*.png。

COM8=CH9102（1A86:55D4）、COM10=OTG（303A:4001）。毎回再確認する。
Python: firmware/logger_v1/artifacts/tools/ux-build-env/Scripts/python.exe
車載CANへ接続したままtestCanLoop/desk-can-loopや書き込みを実行しない。
