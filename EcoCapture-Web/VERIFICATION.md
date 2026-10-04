# EcoLogger V2 / EcoCapture-Web 実機検証 2026-09-06

## 結果

UNO Q上でWebイメージとMCUスケッチをビルドし、MCUへ書き込み、WindowsからUSB経由でHTTP/WebSocketへ接続できた。

| 項目 | 確認結果 |
|---|---|
| 実機 | UNO Q / 4 GB / Debian 13.2 ARM64 / serial 3263089125 |
| USB | UDC `4e00000.usb` の `current_speed = super-speed`。ADB + CDC Serial |
| MCUビルド | 成功。コード19,800 bytes、グローバル変数4,708 bytes |
| MCU書き込み | UNO Q内のOpenOCDによるスケッチ書き込み後、実MCUからのseq・時刻・25チャンネルを受信 |
| Webビルド | UNO Q上のDockerで成功。Windowsでクロスビルドはしていない |
| 単体/APIテスト | 6件すべて成功（最終デプロイ0.757秒） |
| 実機連続試験 | 20.22秒、CSV 379行、15秒間のWebSocket固有サンプル279件 |
| 受信更新率 | 試験末尾18.9 Hz（目標20 Hz、MCU生成目標50 Hz） |
| データ変化 | GNSS速度26.001〜40.470 km/h、MCUのseqが増加 |
| Bridgeエラー | 連続試験中0件 |
| WSクライアント終了 | 試験クライアント終了後の5秒間で95行追加 |
| USBポート転送切断 | Windows側ADB forwardを4秒削除。記録が継続し81行を取得。forward再設定で再接続 |
| CSV整合 | 保存行数とAPIの記録件数が一致。全行 `demo=1` / `source=stm32-dummy`、seq増加 |
| 警告表示除去 | 配信HTMLのDEMO警告帯・バッジ・見出しDEMOラベルは0件。生成元はSettingsに記載 |
| HTTP | Windows `http://127.0.0.1:8080/` が200 |
| 実行資源 | 瞬間値：CPU 10.45%（Docker表示）、RAM 61.7 MiB |
| 起動設定 | コンテナ `unless-stopped`、実行UID/GID 1000:1000。UNO Qループバックへ8080公開 |

保存した試験ログ：

- `DEMO_20260906T034226Z_55e5dc7a.csv`：379行の連続試験。
- `DEMO_20260906T034320Z_cbe4d68e.csv`：USB forward切断中の継続試験。

両方ともUNO QのLogging画面から取得できる。試験後は記録停止状態。

証跡：

- [artifacts/live-verification.json](artifacts/live-verification.json)
- [artifacts/deploy.log](artifacts/deploy.log)
- [artifacts/mcu-build.log](artifacts/mcu-build.log)

## 検証範囲

テストでは一時保存先で欠測無効化、未接続時の記録拒否、記録中ファイルの削除・取得拒否、記録中設定変更拒否、設定保存・読出し、不正CAN信号と非有限値拒否、別サイトからの操作拒否、容量不足時の停止を確認した。

ブラウザ向けHTML/JavaScriptは配信と構文を確認し、画面をCodex内ブラウザに開いた。全画面・全サイズのブラウザ操作試験や視覚検証を済ませたという意味ではない。

USB Ethernet、USB速度のスループット計測、別電源での物理USB抜去、ボード電源再投入、実センサ、CAN通信、SD、カメラ、車載環境は未検証。USB転送試験は給電を維持したADB forwardの切断であり、物理ケーブル抜去とは区別する。

MCUでは最新値を生成し、Linuxが目標20 Hzで取得する。MCUの全50 Hzサンプルの完全保存・リアルタイム性・車載向け耐障害性を保証する試験ではない。独立したMCUのSD記録は後続開発。

## 航空写真・地図操作の追加確認

2026-09-06に地理院地図のseamlessphotoへ変更。Google APIキー・Google Mapsへの依存はない。

- 公式タイル `16/57344/25958.jpg` がHTTP 200 / image/jpeg。localhostをOriginとして送ったリクエストに `Access-Control-Allow-Origin: *` を確認。
- Nodeによる投影・逆投影、カーソル固定ズーム、移動量、全体表示、日付変更線付近、倍率上下限、中ドラッグ、手動表示の維持、現在地復帰、z18超の拡大、欠測状態のテストが成功。
- UNO Q上のビルド、既存APIテスト6件が成功。HTTP 200、map-view.js配信、GSI画像のCSP許可を確認。
- 更新後の実MCU受信18.3 Hz、記録停止。写真取得はPCブラウザ側。
- ブラウザの実マウス操作や全サイズの視覚検証は今回実施していない。

ビルド記録：[artifacts/maps-deploy.log](artifacts/maps-deploy.log)。

## 管理・公開機能のローカル検証（実機反映待ち）

2026-09-06：ADBでシリアル3263089125がoffline。以下の追加変更はUNO Q上では未ビルド・未検証。

- Python：private API 8件、公開専用API 4件、デバイス管理 5件、合計17件が成功。
- 公開サーバーの管理経路404・変更操作403、公開画面に管理操作がないこと、スナップショットから内部情報を除くこと、古い計測値を現在値として表示しないことを確認。
- Wi-Fiのエスケープ、入力検証、パスワードをコマンド引数に含めないこと、接続失敗時の新規プロファイルだけの片付け、CPU・メモリ計算をモックで確認。実NetworkManager接続は未確認。
- Node地図テスト、JavaScript構文、PowerShell構文を確認。
- Windowsのログイン時ショートカットを登録し、USB監視を起動。既定HTTPブラウザはVivaldi。実機再接続後の自動起動は未確認。
- Cloudflared 2026.8.3 ARM64を公式リリースから取得し、公開SHA-256と一致。トンネル起動と外部公開は未実施。
- タスクマネージャは管理画面を表示中だけ3秒ごとに収集。UNO Q上での追加CPU・メモリ負荷は未測定。

復帰後の更新手順はREADMEの `Update-UNOQ.ps1` を参照。

## USB復帰後の実機確認と設定タブ（2026-09-06）

- 管理・公開用イメージをUNO Q上でビルド。17件のPythonテスト成功。
- 「Settings / CAN」配下に「基本設定 / CAN」「UNO Q」タブを実装し、後者にWi-Fi・公開・タスクマネージャを集約。HTTP配信HTMLで各項目を確認。
- Wi-Fi検索10件、メモリ・温度・プロセス一覧取得成功。Wi-Fiは未接続、公開URL未発行。
- 管理APIを3秒間隔で約31.59秒取得：管理サービスCPU 2.19%（1コア換算）、MemoryCurrent 12820480 bytes。閲覧コンテナの単発値はCPU 0.42%、53.77MiB。測定中の全体CPU平均6.13%。
- 閲覧用8081の /api/device/system、/api/device/wifi、/api/config、/api/logs は404。
- USB監視ログ 15:00:51 に既定ブラウザ起動を記録。ユーザーも表示確認。
- MCUが再接続後に配信していなかったため、既定Startup modeで再ビルド・再書き込みし18.4Hz受信に復帰。Immediateモードと単独リセットは復帰できず採用していない。試作した起動時リセットサービスは無効化済み。電源再投入時の自動復帰は追加確認が必要。

## Wi-Fi選択操作の改善（2026-09-06）

UNO Qタブ初回表示で自動検索し、検索中は選択欄を無効化。再検索・0件・エラーの案内を追加し、再検索時は選択を維持。未対応の802.1Xネットワークは選択不可とした。
UNO Q上でビルドとPython17件成功。実ブラウザでタブ表示→検索中→12件の一覧表示→選択後SSID・wpa-psk反映まで確認。接続ボタンは押していない。更新後MCU受信18.8Hz。

## 保存領域整理・CPU削減（2026-09-06）

- ログ用 `/home/arduino` とOS用 `/` は別パーティション。ログ用から開発ツール等約605MiBをPC退避後に削除、OS用から未使用InfluxDB・AI runnerイメージ約1.7GiBを削除。ログ用空き18372771840 bytes（約17.11GiB）、OS用空き4872519680 bytes（約4.54GiB）。
- バックアップと復元手順：`../other/uno_q_tools/backup-20260906/RESTORE.md`。PCとUNO QのSHA-256一致を確認済み。MCU再ビルド時は開発用アーカイブを復元する必要がある。Webビルドは引き続きUNO Q上で可能。
- MCU通信は `telemetry_bridge.py` の非同期MessagePack-RPCに変更。Arduino Router・MCUの公開メソッドは変更せず、Pythonスレッド・キュー経由の往復を除去。
- 私用WebSocketは10Hz、同一フレームのJSONを共有、圧縮なし。MCU生成50Hz・収集目標20Hz・CSV記録は維持。公開用1Hzを維持。
- 25秒窓の本体CPU（1コア換算）：変更前8.57%、圧縮停止のみ10.29%、非同期通信7.50%、最終5.54%。画面閲覧状態や負荷で変動する実測値であり保証値ではない。全4コア換算では最終約1.39%。コンテナメモリ最終45.24MiB（変更前65MiB前後）。Pythonそのものと必須のOSサービスは削除していない。
- UNO Q上の自動テスト19件成功。実MCUの20.18秒記録で383行、受信19.2Hz、通信エラー0。試験WebSocketを閉じた5秒間も96行記録。CSV: DEMO_20260906T064619Z_3f0bf05a.csv。記録試験は停止済み。
- 外部公開URLの計測API HTTP200を確認。公開トンネルは再起動せず維持した。

## NCEC対応検証（2026-09-06）

- 提供仕様から確定12信号のみ採用。元資料をncec_can_spec.mdとして保存。
- 新規8件：RPM/車速オフセット、4輪のA/B順、温度/スロットル、クラッチbit1、燃料平均と窓期限/満タン生値、カウンタ折り返し/重複/間隔、入力異常、未解明IDをデコードしないこと。
- UNO Q上で既存19件＋NCEC8件=27件成功。
- 設定の退避先はPC other/uno_q_tools/pre-ncec-config.json。
- 実CANバス受信・OBD送信は未実装、解析機能は貼り付けテキストのオフライン検証。

## USB自動起動の復旧（2026-09-07）

PCの監視プロセスが停止、UNO QはUSB offline。Wi-Fiの閲覧APIはHTTP200で本体は稼働。監視プロセスを再起動しログイン時ショートカットを再登録。監視停止の原因は未特定。
監視に30秒間隔の対象デバイス再接続、15秒間隔の転送経路再設定、状態変化のログ、ADB起動の待機時間延長、標準出力/エラーの非同期読み取り、放棄されたmutexの回復を追加。
ユーザーのUSB抜き差し後、01:53:51 ready、01:53:59既定ブラウザ起動を記録。localhost API正常、MCU受信19.8Hzを確認。Windows PowerShell 5構文確認済み。Windows再ログインによる自動開始は今回未検証。
