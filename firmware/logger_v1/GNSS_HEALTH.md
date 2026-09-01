# GNSS通信の監視と受信状態の記録

2026-08-31、A105経由で `logger-v1-gnss-health-20260831e` を書込み・照合済みです。
イメージは `artifacts/release_20260831_gnss_health_e/firmware.bin`、603,280 bytes、SHA-256は
`469cf96826fbf68fe1a38034aece56ec458e0c4d9d8ab89cdfeb2aaa9235d47f` です。
書込みはESP32のアプリ領域 `0x10000` のみです。SDは正常クローズしてから書込み、
既存ログ・NVS・GNSS OTP・回路は変更していません。

## 変更内容

- GNSSの測位時刻（iTOW）が3秒以上進まないとき、通信速度を探索してGNSSを再設定します。
  同じ時刻のパケットが繰り返し届いていても、正常更新とは扱いません。
  再設定中は位置などを欠測にし、古い位置を現在値として表示しません。
- 衛星0・未測位でもiTOWが進んでいれば再設定しません。屋内や電波の弱い場所で探索を繰り返し中断しないためです。
- UBX-NAV-SATとUBX-MON-RFを毎秒問い合わせ、受信状態をSDとRaceCapture向けのチャンネルへ追加しました。
  応答待ちで測位処理を止めることはありません。3秒間更新されない診断値はCSVでは空欄になります。
- GNSS用UARTを115200から460800へ変更しました。最大1024バイトの診断パケットでも約23msで転送でき、
  40ms周期の測位データと併用する帯域を確保します。A105の診断UARTは従来の115200のままです。
  受信機の変更はRAM設定のみです。電源投入時の9600、旧版の115200、現行460800などを探索します。
- `getStatus.GPS` の無効な緯度・経度・精度は `null` にしました。
  d版で実装したIMU内部異常からの復旧と、SD単体の記録機能も維持しています。

## SDで確認できる追加列

| 列 | 意味 |
|---|---|
| GNSSAcq / GNSSTrack | 検出・捕捉した衛星数（利用不能も含む、quality≥2） / コードがロックし時刻同期した衛星数（quality≥4） |
| GNSSCNoMax | 受信強度C/N0の最大値（dB-Hz） |
| GNSSCNoTop4 | C/N0が強い上位4機の平均。非ゼロが4機未満ならその機数で平均 |
| RFNoise / RFAGC | 受信機内部のノイズ指標 / AGC指標（%） |
| RFJam | 受信機の妨害監視状態。0=不明または無効、1=OK、2=警告、3=重大 |
| RFCW | 連続波妨害指標（0～255）。単独で良否を断定しない |
| GNSSRetry | 測位時刻停止を検出して再設定した回数 |
| GNSSAge | 最後に新しい測位時刻を受信してからの時間（ms） |
| GNSSBad | UBXパーサーで検出した破損・過大長フレームの累計 |

従来の `GPSSats` は測位に使用した衛星数です。`GNSSAcq` などと同じ値になるとは限りません。
旧64列のチャンネル番号は維持し、診断11列を後ろへ追加しています。
SDの列名・単位・ファーム版は対応する `.meta.json` でも確認できます。

読取り専用の `getGnssDiagnostics` でも取得できます。`satellitesFresh`、`radioFresh`、`pvtFresh` を確認してください。
この応答の診断オブジェクトには最後の値が残るため、Fresh=falseの値を現在値として解釈しないでください。
`reported` は受信機が列挙した衛星数で、信号を捕捉できた数ではありません。
`antennaStatus` や `antennaPower` は受信機の報告値です。外部バイアス回路やJCA002の実際の給電を測定した証拠にはなりません。
RFJam=0も「妨害なし」という意味ではありません。

## 検証と制約

GNSS監視の境界・重複時刻・週の折返し・未測位時の継続、NAV-SAT/MON-RFの解析と不正長をホスト試験しました。
既存コア・IMUの回帰試験もAddressSanitizer/UndefinedBehaviorSanitizer付きで通過しています。
実機の連続取得・CSV読戻し結果は [acceptance/verification.json](artifacts/release_20260831_gnss_health_e/acceptance/verification.json) に保存しました。

90秒の観測と前後のファイル区切りを含む9,121行を読み戻し、次を確認しました。

- SDは100.00009Hz、正常クローズ、列定義一致、記録欠落・書込みエラー0。
- GNSSは2,281個の測位時刻すべてが40ms間隔で25Hz。全行3D測位・UTC有効。
- IMUは全行で有効100Hz。今回の観測中は内部異常・復旧回数も0。
- 診断11列は全行に保存。180回の診断問合せもすべて新鮮な応答。
- GNSS再設定・重複時刻・破損フレームは0。GNSS用UART速度変更後も欠測なし。
- 問合せでの測位使用衛星は7～10、最大C/N0は34～37dB-Hz、上位4機平均は31～35.25dB-Hz。
- 書込み直前の56ファイルは、書込み後も全て同じ名前・サイズで保持。

試験ログは `20260831_215752_JST_LE17DFD8E_0003.csv` です。
電源投入時刻を推定したJST日時がファイル名に付き、PCで位置とIMUを解析できます。
RaceCaptureを自動復帰補助付きで再起動し、[実画面](artifacts/release_20260831_gnss_health_e/racecapture.png)で
e版・緯度経度・衛星8・GPSFix=3・GNSS25Hz・UTCValid=1・IMU100Hz・LogDrops=0を確認しました。

今回の屋外未測位は、変更前にも自然に測位へ復帰しています。
その経緯は [GNSS_OUTDOOR_CHECK.md](GNSS_OUTDOOR_CHECK.md) に残しています。
e版は通信停止への対応と原因を調べるための記録を改善したものです。
アンテナの感度、遮蔽、給電、ノイズの問題をファームウェアだけで解消したとは言えません。
GNSS通信停止を実機へ故意に発生させる試験は行っていません。

旧d版へ戻す場合、受信機が460800のままだと旧版は探索できません。旧版書込み後にGNSSを含む電源を入れ直してください。
通常起動でOTPを変更する処理はありません。過去のOTPプロビジョニングを再実行しないでください。

参照：u-blox [SPG 5.10 Interface Description（UBX-21035062 R03）](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf)、
ローカル `artifacts/sources/m10-integration.pdf`（MAX-M10M-00B Integration Manual、UBX-22038241 R03、UART表16）。
