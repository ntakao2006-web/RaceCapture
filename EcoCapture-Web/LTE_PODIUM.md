# LTEでセンサ値をPodiumへ共有する準備

2026-10-03追記: SORACOM planX3 X3-5MB、Pluto付属アンテナでドコモLTE-M Band 19に接続。実回線のDNS/TCP/短いHTTPヘッダー受信と、修正後5回の電源再投入接続を確認。CFUN=1直後のCPIN?一時ERRORを期限付きで待ち、PSM/eDRX設定を回線登録後に行うよう修正。CAN/SD同時試験を含めた結果は `outputs/hardware_check_20261003/RESULT.txt`。Podium認証・送信はキー未設定のため未検証。LTE自動送信はOFF。以下は10月2日時点の準備記録で、SD満杯などの記載は現在の状態ではありません。

2026-10-02。`podium_connect_notes.md`（a636114）と公式RaceCapture Appの実装を根拠に実装。
リモート更新の取得はSSHのホスト鍵確認、HTTPSの認証で失敗したため、最新のntakao資料との比較はできていない。

## 経路と実装

STM32がLTE電源・PWRKEY・UART IRQ・GPIO RTS/CTSを担当し、UNO Q内のEcoCapture-WebがSIM7070のATコマンドでTCP接続を操作する。
PCやWi-Fiのインターネット接続は不要。UNO QのLinux/EcoCaptureプロセスは必要。
資料の「STM32だけで送信するA'」は今回の実装範囲外。SDの独立記録を維持したまま既存のLinux側信号デコード・設定を使う構成にした。

送信形式はASCIIの改行区切りJSON。認証成功応答の後でmetaを送り、同じチャンネル配列を使って値と32ビット単位の可変長マスクを生成する。
初期選択は位置・速度・衛星数とIMUの15項目。既存の車両信号も選択可能。生CANフレーム、CSV、画像、音声、管理情報は送らない。
10Hzを目標に最新の実機値を送信する。欠測・非有限値はマスクから外し、受信が0.5秒以上古い値とダミーデータは送らない。
遅延時は過去値を溜めず、送信周期を落とす。通信量・実回線の持続10Hzは未測定。
認証拒否は設定が変わるまで再試行を止める。その他の通信異常は2/4/8/16/30秒の待機で再接続する。
SDの読出し・コピー中はLTEを閉じて休止する。ローカルCSV記録とLTE送信のON/OFFは独立。

## 設定

Settings → UNO Q → LTE / Podiumで、APN、必要ならAPNユーザー名・パスワード、Podium送信キー、送信する信号を設定する。
SIMとLTEアンテナを接続済みにチェックしてから送信ONにする。保存した設定で起動後も再接続する。
送信先の初期値は `telemetry.podium.live:8080`。変更先も同じPodiumプロトコルが必要。
「送信OFF」で直ちに停止。「LTEを点検（電波OFF）」はSIMなしでAT応答、RF停止、UART制御を確認し、最後に電源を切る。

キーとAPNパスワードは `/data/private/podium.json` に保存する（ディレクトリ0700、ファイル0600）。暗号化保存ではない。
設定APIは秘密を返さず、空欄は保存済み値を維持する。APIの `clear_key` / `clear_password` で削除できる。
検証エラー、通常ログ、CSVメタデータ、閲覧専用サイトには秘密を含めない。
Podiumの既存方式はTLSなしなので、送信キー自体は回線上で平文になる。

## MCU通信と保護

57600bps UART IRQでRX4096バイト、TX512バイトの上限を持つ。Bridge要求は18バイトのHEXチャンクで既存の64バイト受信制限内に収める。
通常収集・LTE・SD操作は全て同じRPCクライアントのロックを使う。別クライアントから同時にRPCを送らない。
MCUはPWRKEYを待機・パルス状態で操作し、センサループを待たせない。LinuxからLTE専用操作が20秒途絶えるとモデム電源を切る。
LTEのLEDはモデム電源ONを示す。クラウド到達を保証する表示ではない。
64KiBの書込み制限は維持。ビルド時に未参照のARMマッピングシンボルだけを除去し、再配置のシンボル番号を更新する。コード・データ・参照対象は保持してサイズを検査する。

## 検証範囲と残件

自動試験: マスクの31/32/64境界、欠測・NaN、ASCII・順序、秘密の秘匿と権限、認証拒否時の再試行停止、10Hzへの間引き、分割AT応答、CASEND分割、UARTバックプレッシャーと溢れ検出。
実機: SIM7070応答、CFUN=0、IFC=2,2、20回のUART応答、UART溢れ0、20秒の通信監視による電源OFF。実行中もIMU/GNSSと内蔵記録は約100Hz、追加エラー0。
この個体のRF停止状態ではTCPコマンドの一覧を確認できなかった。メーカーのTCPUDPアプリケーションノートに基づく接続処理は模擬モデムで確認したが、現物のPDP/TCP動作は未確認。

次に必要なのは対応するSIM・LTEアンテナ・APN・Podiumアカウント/送信キー。登録→PDP→TCP→認証→10Hzの到達、切断復帰、長時間の電源・回線安定性を確認する。
現在の16GBカードは既存256MiB FAT32領域が満杯。既存データを削除せず残した。今回SDへ記録が継続する証拠は追加できていないが、内蔵eMMC記録は継続。
TVS交換と実車CAN・車体向き/IMU校正は別作業。LTE GNSSの0.4m精度は確認していない。

結果: `outputs/lte_podium_20261002/live_report.json`。
AT根拠: [SIMCom TCPUDP(S) application note V1.03](https://files.waveshare.com/upload/7/75/SIM7070_SIM7080_SIM7090_Series_TCPUDP(S)_Application_Note_V1.03.pdf)
