# RaceCapture モックデバイス作業 引き継ぎメモ

## ステータス: 解決済み(テレメトリー表示成功)
公式 RaceCapture App(Windows)がモックデバイスに接続し、ダッシュボードに
テレメトリー(RPM/Speed等のダミー値)が表示され、値が動くことを確認できた。

## ゴール
実機なしで、公式 RaceCapture App(Windows)がテレメトリー表示のために最低限
何を受信する必要があるかを、JSON プロトコルのやり取りを実測しながら特定する。

## 環境
- OS: Windows
- 仮想COMポート: com0com で作成した `COM3` ⇔ `COM4` のペア
  - `COM3` = 公式アプリが接続する側
  - `COM4` = モックデバイス(`rcp_mock_device.py`)が listen する側
- 公式アプリのインストール先: `C:\Program Files (x86)\RaceCapture\racecapture.exe`
  (PyInstaller onedir ビルド。`pyinstxtractor-ng` + `pydisasm`(xdis)で
  逆コンパイルしてプロトコルの正確な挙動を解析した)
- Kivyログ: `%USERPROFILE%\.kivy\logs\kivy_YY-MM-DD_N.txt`
  (`%USERPROFILE%\.kivy\config.ini` の `log_level` を `debug` にすると
  シリアル通信の詳細な例外やコマンドシーケンスが見える。デバッグ後は
  `info` に戻すことを推奨)
- 作業フォルダ: `G:\マイドライブ\RaceCapture`
  - `rcp_mock_device.py` … モックデバイス本体(最終版)
  - `rcp_capture.jsonl` … 通信ログ(TX=モック→アプリ, RX=アプリ→モック,
    RAW=行として確定する前の生バイト)

## 実測で判明したプロトコル仕様(公式アプリ実機との通信ログより)
- 1メッセージ = 1行の JSON + **`\r`(CRのみ)終端**。
  `\r\n` でも `\n` 単体でもない点に注意(ファームウェアソースの解析結果
  `loggerApi.c` から当初 `\r\n` だろうと推測していたが誤りだった)。
  モック→アプリ方向のレスポンスは `\r\n` で送っても問題ない
  (アプリの受信パーサは `\n` 区切りで見ているため)。
- コマンドの値は `{}` ではなく **`null`** (例: `{"getVer":null}`)。
- 接続確立に必須のコマンドシーケンス(`rcpapi.py` の `cmdSequence`
  相当。1つでも応答がないと `Command sequence exception` で
  切断・サーチングループに戻る):
  1. `{"getVer":null}` → `{"ver":{...}}`
  2. `{"getCapabilities":null}` → `{"capabilities":{...}}`
  3. `{"getLapCfg":null}` → `{"lapCfg":{}}`
  4. `{"getTrackCfg":null}` → `{"trackCfg":{}}`
  5. `{"getCanCfg":null}` → `{"canCfg":{}}`
  6. `{"getObd2Cfg":null}` → `{"obd2Cfg":{}}`
  7. `{"getConnCfg":null}` → `{"connCfg":{}}`
  - 各設定オブジェクトは中身が空 `{}` でも問題ない
    (アプリ側の `fromJson` は全フィールド `dict.get(key, default)` の
    形で書かれており、トップレベルの値が falsy ならまるごとスキップされる)。
  - `capabilities.flags` を空リスト `[]` にし、`channels.*` と
    `db.tracks/sectors` を全て `0` にしておくと、`has_gps`/`has_analog`/
    `has_gpio`/`has_pwm`/`has_timer`/`has_can_channel`/`getTrackDb` などの
    条件付き追加コマンドが一切トリガーされず、上記7個だけで接続完了する。
    (`has_gps`等は `capabilities.flags` へのキー存在チェック、
    `has_analog`等は `capabilities.channels.X > 0` のチェック)
- `{"getMeta":null}` → `{"meta":[{"nm":..,"ut":..,"min":..,"max":..,
  "prec":..,"sr":..}, ...]}` : チャンネル定義。一度返せばアプリ側で
  キャッシュされる(Kivyログに `DashboardView: sample metas did not
  change, skipping` と出る)。
- `{"getStatus":null}` → `{"status":{...}}` : 接続後は約1Hzでポーリングされる。
- `{"s":0}` → `{"s":{"t":<tick>,"d":[v1,v2,...,<bitmask>]}}` : 単発サンプル
  要求。これも接続後は約1Hzで `getStatus` と交互にポーリングされる。
- `{"getLapCfg":null}` は上記7コマンドの中でも定期的に再送されてくる
  (Level 2 retry の仕組みがあるらしいが、都度空応答を返せば問題ない)。

## 公式アプリの接続方式(実測で確認)
- `serial.tools.list_ports.comports()` で列挙したポートを順番に開いて
  `getVer` 等を送り、応答があったものをデバイスと判断
- 「前回接続したポートを最初に試す → だめなら他を巡回」という挙動

## 見つかったアプリ自身のバグ(回避策込み)
`racecapture\comms\serialcomms.py` の `SerialComms.close()` は
reader/writer スレッドを止めるだけで、**実際のシリアルポートハンドル
(`self._connection.ser`)を一度も close() していない**。
そのため、一度でも `open()` に成功したポートで応答待ちタイムアウト等が
発生して `close()` が呼ばれると、Windows 上の実ハンドルはリークしたまま
残り、以後そのポートは**アプリが生きている間ずっと**再オープンできなくなる
(`serial.Serial()` が `SerialException` → アプリ内部で
`PortNotOpenException` に変換されて握りつぶされ、ログにも出ない)。
- 症状: `getVer` 送信直後に
  `racecapture.comms.commscommon.PortNotOpenException: caused by 'Port Closed'`
  が (DEBUGログでのみ)出て、"Giving up on COMx" を繰り返す。
- 外部から `New-Object System.IO.Ports.SerialPort` で該当ポートを開こうと
  すると "Access to the port 'COMx' is denied" になることで、アプリ自身が
  ハンドルをリークしていることを確認できる。
- **回避策**: モック側を正しい状態にしてから、公式アプリを完全終了
  (プロセスが本当に終了しているか `Get-Process racecapture` で確認)して
  再起動する。プロセスを再起動しない限り、一度壊れた接続状態は直らない。

## 成果物
- `rcp_mock_device.py`: RCPプロトコルのモックデバイス(最終版)。
  対応コマンド: `getVer`, `getCapabilities`, `getMeta`, `getStatus`,
  `getLapCfg`, `getTrackCfg`, `getCanCfg`, `getObd2Cfg`, `getConnCfg`,
  `s`(単発サンプル), `log`(ストリーミング開始/終了)。
  未知のコマンドはログに出すだけで通信を切らない。
  受信は `\r` / `\n` どちらの区切りにも対応。生バイトは行が完成する前に
  即座に `RAW` としてログされるため、プロトコル不明点の切り分けに使える。
- `rcp_capture.jsonl`: 全セッションの通信ログ。

## 今後の発展(必要なら)
- 現状は `{"s":0}` への単発応答のみでテレメトリーが表示されている。
  `--always-stream` や `log` コマンドによる連続ストリーミングを使った
  場合の挙動(1Hzポーリングとどちらが優先されるか等)は未検証。
- GPS/IMU/CAN等、`capabilities.channels` を非ゼロにした場合に追加で
  要求される `getXCfg` 系コマンド(`getAnalogCfg`, `getGpioCfg`,
  `getPwmCfg`, `getTimerCfg`, `getCanChanCfg` 等)の応答形式は未調査。
  必要になったら `racecapture\config\rcpconfig.py` 相当の逆コンパイル
  結果(各設定クラスの `fromJson`)を見れば同じ要領で特定できる。
