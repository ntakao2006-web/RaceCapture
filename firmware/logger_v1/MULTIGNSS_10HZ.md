# GNSSを10 Hz・複数衛星システムへ変更するf版

**後続の方針変更:** 10 Hz固定ではなく、衛星構成と更新周期の両立を探すことになりました。
最新のg版と比較手順は [GNSS_BALANCE.md](GNSS_BALANCE.md) を参照してください。以下はf版の履歴です。

2026-08-31着手、2026-09-01更新。対象: ESP32-S3実装基板、MAX-M10M-00B（ROM SPG 5.10）。

## 状態

版名は `logger-v1-multignss10-20260831f`。ソースの変更とホスト単体試験は完了しました。
ビルドも成功し、凍結イメージを保存しました。結果は本書末尾に記録しています。
**A105とロガーUSBがPCに認識されていないため、まだ実機へ書き込んでいません。**
最後に書込み・実機確認したのはe版の25 Hzです。f版で衛星数が増えた、測位が安定した、
RaceCaptureに10 Hzで表示できた、という実測結果はまだありません。

## 「25 Hzにしたら戻せない」の訂正

不可逆なのはGNSS内部クロックを高性能モードへ変更するOTP設定です。
この個体では以前に明示承認を受けて設定し、読戻し確認しています。
標準クロックには戻せませんが、**測位周期は25 Hzから10 Hzや1 Hzへ変更できます。**
受信する衛星システムの組合せも変更できます。高性能クロックを維持したまま、
10 Hzで複数の衛星システムを使うのが今回の変更です。新たなOTP書込みはありません。

## 構成と期待できること

| 構成 | 測位周期 | 受信システム |
|---|---|---|
| これまでのe版・この個体 | 40 ms / 25 Hz | GPS＋QZSS/SBAS |
| f版・高性能クロック確認済み | 100 ms / 10 Hz | GPS＋Galileo＋BeiDou B1C＋GLONASS、QZSS/SBAS |
| f版・高性能クロックを確認できない場合 | 100 ms / 10 Hz | GPS＋Galileo、QZSS/SBAS |

メーカー仕様では、4システム同時受信の最大更新周期は標準クロック4 Hz、高性能クロック10 Hzです。
単にデータ出力を間引くのではなく、測位処理を10 Hzにして受信対象を増やします。
BeiDou B1IはB1CやGLONASSと共存できないため、B1Iを明示的に無効化してB1Cを使います。

使える衛星候補は増えますが、実際の使用数や精度の改善は空の見通し、衛星配置、アンテナの
対応周波数・受信状態にも依存します。必ず増えるとは限りません。
メーカーの最大更新周期は通常条件で最低98%の測位更新を前提とする値で、全条件で欠落ゼロの保証ではありません。

IMUとSDの採取は100 Hzのままです。CSVのGNSS列は同じ測位値が約10行続くため、
軌跡解析では `GPSTow` が更新した行を新しい測位として扱います。
今回、GPS欠測をIMUの二階積分で埋める機能は追加していません。

## 実装上の保護

- 受信対象を増やす前に100 ms周期へ変更し、4システム・25 Hzという仕様外の過渡設定を避けます。
- 衛星システムと個々の信号の両方を明示設定します。信号設定後は600 ms待ってから再問い合わせします。
- UBX-CFG-VALSETはRAM層だけを対象にし、VALGETで実設定を読戻し照合します。
  ACKだけでは成功扱いにせず、不一致なら再設定します。
- 高性能クロックはメーカー指定の4項目を読取り確認するだけです。OTP設定コマンドは送りません。
- 旧NVSの18/25 Hz設定を読み込んでも、他の設定を残して実行中のGNSS周期を10 Hzにします。
  この移行のためのNVS書換えや消去はしません。
- 既存のGNSS停止監視、IMU自動復旧、SD100 Hz記録を維持します。既存ログを削除しません。
- `getGnssDiagnostics.configuration` で `verified`、`navigationHz`、`highPerformanceClock`、
  `profile` を返します。衛星診断の `systems` ではシステム別の捕捉数・測位使用数も返します。

## 実機接続後の手順

1. A105と基板電源を接続し、実際のCOM番号・版名・SD状態を確認します。通常A105はCOM8、ネイティブUSBはCOM10です。
2. RaceCaptureと復帰補助を終了します。SD記録を正常終了し、書込み前のファイル一覧を保存します。
3. 凍結したf版アプリを0x10000だけに書き込みます。全Flash消去・NVS消去・SD消去・OTP設定は実行しません。
4. 再起動後の版名と設定読戻し一致を確認し、屋外で測位を待ちます。
5. `tools/verify_gnss_health.py` で閉じたSDログを取得し、GNSS100 ms、IMU/SD100 Hz、
   エラー・欠落・既存ログ維持を検証します。システム別使用数も記録し、4系統を有効化したことと実際に使用できたことを区別します。
6. RaceCaptureの復帰補助を再起動し、測位・衛星数・IMUの表示更新を確認します。

e版へ戻すための凍結イメージは `artifacts/release_20260831_gnss_health_e/firmware.bin` です。
f版で明示的に設定保存したあと古いe版へ戻す場合、e版は10 Hzを保存値として受け付けないため、
その他の保存設定を含めた互換性確認が必要です。NVS全消去で対処しないでください。

## 根拠

- [MAX-M10M-00B Data sheet R04](https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_DataSheet_UBX-22028884.pdf): Table 2/3、更新周期とシステム組合せ。
- [Integration manual R03](https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_IntegrationManual_UBX-22038241.pdf): 2.1.3、信号の同時使用制約と変更後の待機、高性能クロックとOTP。
- [M10 SPG 5.10 Interface description](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf): CFG-SIGNAL、CFG-RATE、UBX-CFG-VALSET/VALGET、UBX-NAV-SAT。

## ビルドと検証記録（9月1日00:55）

- 凍結イメージ: `artifacts/release_20260831_multignss10_f/firmware.bin`、605,024 bytes。
- SHA-256: `117c76a4aef09068338f052ebbcb2846694cd4dddc726b5dd0f989d20fa40015`。
- 同フォルダーの `manifest.json` に未書込みであることを明記、`build.log` にビルド成功を記録しました。
- C++17、ASan/UBSan付きの設定読戻し試験・衛星/RF診断試験・既存core試験はすべて成功しました。
  `host_tests.log` に結果を保存しています。検証用Pythonの構文も確認しました。
- ビルドにはCライブラリの `times is not implemented` というリンク警告が残っています。
  ビルド成功と実機動作確認は別です。測位・衛星数・RaceCapture・SDの実機確認は未実施です。
