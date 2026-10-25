# ピット用ダッシュボードの引き継ぎ（自宅ROCK 5B → 先輩のラックサーバー）

自宅のROCK 5Bで動かしているピット用の画面（Grafanaのダッシュボード「EcoRun Live」と、その中に
埋め込んでいる「周回・時間」のページ・地図）を、**別のサーバーで5Bと同じ見た目・同じ動きで立てる**ための資料です。
主サーバー（先輩のラックサーバー）も、**Grafanaを含めて5Bとまったく同じ構成にする**（2026-10-24決定）ためのものです。

- **2026-10-25 10時40分時点の5Bの実際の状態**を元にしています（10/24 3時版から、大会初日の指摘を受けた作り直しと、
  10/25 10:33のブリッジの修正（複製のつなぎ直しで混ざった古い行を捨てる。1-3）を全部反映）。
  画面の定義・3つのページ・ブリッジは、**5B上の実物とこのリポジトリのファイルが同一であることをsha256で確認済み**です（4章）。
  Grafanaの設定・データソース・中身（DB）・VictoriaMetricsの起動オプション・Funnelのパスも同日に5Bで読み直し、10/24から変わっていないことを確認しました（5章）
- 5Bはsystemdで直接動かしています。ここではそれを**Docker Composeへそのまま写した一式**
  （`tools/home_telemetry/deploy/`）を用意しました。5Bの設定との対応は5章に全部並べています
- `ecorun-logger-server`本体はこの一式に含めません。**今動いているサーバーの隣に足す**形です
- 文中の`<公開ホスト名>`は自分のサーバーの名前（Tailscale Funnelなら`<マシン名>.<tailnet名>.ts.net`）に読み替えてください
- **まだ確かめていないこと**：この一式をコンテナで実際に起動すること。こちらのPCのDocker Desktopが起動時に落ちるため
  `docker compose config`の構文検証まで、5Bは大会のピット画面を出しているので試験に使っていません。詰まったら教えてください

---

## 1. 画面の構成（EcoRun Live、2026-10-25時点）

ダッシュボードは1枚（uid `ecorun-live`）で、Grafanaを開くと最初にこれが出ます（ホームに設定）。
左上の`room`で車を選びます（`ecorun_Speed`が来ているroomが並ぶ）。表示範囲は直近5分、更新は5秒ごとです。
**1280×720の画面で、サイドメニューを開いたままでも1画面に収まる**大きさにしてあります。

```
 横24マス  0                                14              24
 高さ12  │ 周回・時間（/live/clock を埋め込み） │ 地図（/live/map を埋め込み）│
         │  0〜14マス                         │  14〜24マス                 │
 高さ3   │ 速度 │GPS衛星数│GNSS精度│ 油温 │ サーバー到着までの遅れ │
         │ 0〜4 │  4〜8   │ 8〜12  │12〜16│        16〜24          │
 高さ1   │ ▶ 詳細（たたんだ行。開くまで問い合わせない。開くと通信量が増える）            │
           ├ 前回ラップ／この周の経過／平均速度（スタートから）／この周の平均・前の周（各6マス）
           ├ 通過時刻の表（24時間分。サーバーの記録）
           ├ 速度の推移
           └ 全チャンネル（最新）
```

**大事な考え方**：もてぎのピットの回線がとても遅く、Grafanaの問い合わせ方式の欄が約30秒遅れて止まり、それを信じた指示で
タイムオーバー寸前になった（10/24）ので、**時間と周回に関わるものは全部「周回・時間」のページに移し、見ている端末の時計で進める**
ようにしました。Grafanaの問い合わせに頼る欄は、遅れても困らないものだけです。

### 1-1. 「周回・時間」のページ（`/live/clock?room=<room>`）

ブリッジから**スタート時刻・各ラインの通過・規定時間・余裕だけ**を毎秒受け取り（7周で約0.8KB/秒）、
**この端末の時計で進めます**。回線が詰まっても時計とこの周の経過は止まりません。

| 行 | 中身 |
| --- | --- |
| 1行目 | 状態（「スタート前」「走行中」（緑）「ゴール」（オレンジの札））と周回「走行中の周 / 規定周回数」（ゴール後は「完了周回数 / 規定周回数」） |
| 経過 | スタートからの経過。ゴール後はゴール時刻で止まり、0.1秒まで出す |
| 規定まで・目標まで | 規定まで＝規定時間−経過、目標まで＝規定まで−余裕。15分を切るとオレンジ、5分を切ると赤 |
| 規定と余裕の行 | 「規定 39:20.1　余裕 30秒」。**届いていなければオレンジの札で「規定時間・余裕がまだ届いていません（ドライバーのアプリで大会の設定をロック／Ver.2は記録中か確認）」** |
| この周・前の周 | この周＝最後にラインを通ってからの時間（端末の時計で進む）、前の周＝最後のラップ |
| この周の平均・スタートからの平均 | ブリッジが速度を時間で積算した平均（km/h） |
| 通過の表 | 新しい順に「周・ライン（スタート／コントロール／ゴール）・通過時刻・ラップ・その周の平均」。ゴールの行は太いオレンジ |
| 一番下の左 | 「この画面のデータ：n秒前」＝この画面が持つ最新データの古さ（ロガー→サーバー→この画面）。10秒を超えると赤で「最新のデータがn秒前のまま（時計は進み続けます）」 |
| 一番下の右 | 「回線 n秒」＝サーバーからこの画面までの今の遅れ（直近10分で一番速く届いた通知との差、または通知が途絶えている秒数）。5秒を超えると赤 |

- 端末の時計がずれていても、サーバーの時刻との差を**直近10分の最大値**で補正します（遅れて届いた通知は差を小さく見せるだけなので、
  最大値が一番正しい）。端末の時計が設定し直されたり、端末がスリープから戻ったりしたら測り直します。
  限界：ページを開いた時からずっと遅い回線は時計の差と見分けられず、経過が遅れの分だけ小さく出ます
- 規定時間・余裕はGrafanaで入力しません。**ドライバーのアプリで設定してロックした値**（Ver.2はアプリが走行前にロガーへ書き込み、
  ロガーが`TimeLimit`・`Margin`として送る。二輪はアプリが直接送る）を表示するだけです（ドライバーとピットで数字がずれないように）

### 1-2. その他のパネル

| パネル | 何を出しているか | 元のデータ |
| --- | --- | --- |
| 地図 | 航空写真に車の位置と軌跡。車を中央に追従（ドラッグで解除）、点の間を補間して滑らかに動かす。図形を描いて保存・見ている人の位置共有もできる | ブリッジの`/live/map`（WebSocket `/live/ws?…&fields=Latitude,Longitude,Speed`、約0.4KB/秒） |
| 速度 | 0.1秒ごとに動く速度 | **Grafana Live**（ブリッジが速度だけを押し出す。トークンが無いと空。6-3） |
| GPS衛星数・GNSS精度 | 精度は受信機の水平精度m（大きいほど悪い） | `GPSSats`・`GPSAcc` |
| 油温 | センサーハブの油温。状態が「正常」以外は温度を出さない。油温の無い車は「—」 | `OilTemp`・`OilTempState` |
| サーバー到着までの遅れ | ロガーが測った時刻（GNSS）から、そのデータがサーバーで検索できるようになるまでの秒数。**この画面の回線の遅れは含まない**（そちらは「周回・時間」の一番下） | `Interval`の時刻（測位が無くても届く） |
| 詳細（たたんだ行）の中 | 前回ラップ・この周の経過（ロガーの`LapTime`・`ElapsedTime`）、平均速度（ブリッジが計算した`RaceAvgSpeed`・`LapAvgSpeed`・`LastLapAvgSpeed`）、通過時刻の表（ブリッジが出す`ecorun_lap_at`、24時間分）、速度の推移、全チャンネル。どれもGrafanaの問い合わせ方式なので、回線が遅いと遅れる | VictoriaMetrics |

地図・「周回・時間」は、Grafanaの「テキスト」パネルにHTMLで`<iframe src="/live/clock?room=$room">`のように埋め込んでいます。
**Grafanaとページが同じホスト名の下にある**ことが前提です（`/grafana/`と`/live/`。ポートが違うとブラウザがiframeを遮断する）。

G-Gのページ（`/live/gg?room=<room>`）は10/24夜にダッシュボードから外しましたが、ページ自体は今も配っています
（丸い目盛り、下が加速・上が減速、`&flip=1`で左右反転）。

### 1-3. ブリッジ（`live_bridge.py`）がしていること

- サーバーが書くJSON Lines（`<ECORUN_TELEMETRY_DIR>/<room>/<日時>Z.jsonl`）を追いかけて読み、全チャンネルを
  `ecorun_<チャンネル名>{room="…"}`としてVictoriaMetricsへ書く。時刻はロガーのGNSSの`Utc`（無ければサーバーの受信時刻）
- ロガーは0.5秒ごとに5行まとめて送るので、少し待ってから10Hzの間隔で流し直す（地図・速度が滑らかに動く）。時計・周回は待たずに毎秒送る
- ページは自分が描く項目だけを`&fields=`で頼み、最初に送る履歴も`&history=`で決める（地図は5分、G-Gは3秒）
- 平均速度：速度を時間で積算。**5秒を超え15分までのデータの欠けは前後の速度の平均でつなぐ**（欠けを数えないと平均が低く出ていた）。
  欠けの中でラインを通ったときは通過時刻で前後の周に分ける。周回が一度に2つ以上増えたときは時間と距離を同じように分ける。
  線から30秒以内に始まった周・レースは最初の点の速度で補って線から数える（スマホはスタートの通過を数秒遅れて送るため）
- **起動時に、直近6時間に書かれた保存ファイルを読み直して周回の状態（スタート・通過・ラップ・平均）を作り直す**。
  走行中にブリッジを再起動しても通過の表は消えません（VictoriaMetricsへは書き直さない。地図の軌跡は戻らない）
- **その部屋で取り込んだ最新の行より古い行は捨てる**（`Bridge.only_new`、10/25 10:33）。冗長構成の相手がつなぎ直すと、
  サーバーが相手の履歴を今開いている部屋のファイルへ書くことがあり、10/25 10:29に5Bで、前夜の試験走行の行を今の走行として数え、
  偽の通過（7周・3周）が出ました。これで古い行は周回にもVictoriaMetricsにも入りません
- WebSocketの読み口（`/live/ws?room=<room>&kind=clock`）は、ピット画面以外からも使えます（走行戦略ツールの緒方さんへ説明済み、
  `ogata_share_20261024_issues_reply.md`）。`{"clock": {start, end, limit, margin, lap, count, total, lap_start, last_lap, passes, lap_avg, race_avg, data_t}, "now": サーバー時刻ms}`が毎秒届きます

### 1-4. 10/18以降に変わった点（UIの変更履歴）

| 日付 | 変更 |
| --- | --- |
| 10/23 | 大会用の画面に作り直し：上段に周回・経過／残り時間・平均速度、中段に地図、通過時刻の表を追加 |
| 10/23 | 通話パネル（ピットはDiscordに一本化）とベストラップ（エコランでは無意味）を外した |
| 10/23 | GNSS精度と油温（状態つき）を追加。最終受信は測位が無くても届く`Interval`で判定 |
| 10/23 | 加速度の時系列をやめ、G-G表示（`gg.html`）を地図の隣に。同日、向きを「加速で下・減速で上」（体で感じる向き）に変更 |
| 10/23 | 画面の更新を0.5秒→2秒（速度・地図・G-Gはプッシュ配信なので遅れない）。Grafanaをgzip配信に |
| 10/24 | 規定時間・余裕を画面の入力欄で入れる方式をやめ、**ロガーから届く値を表示するだけ**に（ドライバーのアプリとずれないように） |
| 10/24夜 | 大会初日の指摘（もてぎでピットの回線が遅く、経過時間が約30秒遅れて見えた）を受けて：経過・残り時間を**端末の時計で進むページ**（`clock.html`）に置き換え、「最終受信」を「サーバー到着までの遅れ」に改名。地図・G-Gは描く項目だけを受け取る形にし（1ページ約2.4KB/秒→約0.4KB/秒）、Grafana Liveへは速度だけを送る。速度の推移・全チャンネルはたたんだ行へ。更新は5秒ごと |
| 10/24夜 | 指摘（二輪の1周目が「残り3」、余裕が見えない、**ラップが約30秒遅れて出てタイムオーバー寸前**）を受けて：周回を「1 / 3」の形に、規定と余裕の行を常に表示、**前回ラップ・この周・通過の表・平均も「周回・時間」のページへ移して端末の時計で進める**。G-Gをダッシュボードから外し、問い合わせ方式の欄はたたんだ行へ。欠けをまたぐ平均速度の不具合も修正 |
| 10/24夜 | 文字とパネルを一回り小さく（1280×720で1画面に収まるように） |
| 10/24深夜 | 時計の差を測る時間幅を1分→10分に（回線の遅れが1分続くと時計の差と取り違えて経過が小さく出ていた。KTR-OCTの指摘）。端末の時計が設定し直されたら測り直す。一番下の右に「回線」の遅れを表示 |
| 10/25 1時 | 「周回・時間」の文字をパネルに合わせて約1.4倍に（パネルの大きさは同じ）。「ゴール」をオレンジの札に、通過の表のゴールの行を太いオレンジに |
| 10/25 1時半 | ブリッジの再起動時に直近6時間の保存ファイルから周回の状態を作り直す。周回が一度に複数増えたときに平均が約2倍に出る件、スマホのスタート判定の遅れで1周目・全体の平均が出ない件を修正 |
| 10/25 10:33 | ブリッジが、部屋ごとに取り込んだ最新の行より古い行を捨てるように（複製のつなぎ直しで混ざった前夜の行を周回に数えた件。1-3）。画面の見た目は変わらない |

---

## 2. 全体の構成

```
      ロガー・スマホ ──▶ ecorun-logger-server（今動いているもの）
                              │ ECORUN_TELEMETRY_DIR に <room>/<日時>Z.jsonl を書く
                              ▼
                        bridge（live_bridge.py）──▶ VictoriaMetrics（履歴。Grafanaの数字・表の元）
                              │                └──▶ Grafana Live（速度パネルの0.1秒更新）
                              └─ 周回・時間／地図／G-Gのページと、そのWebSocket を配る

  外からの入口（1つのホスト名にまとめる）
    /          → ecorun-logger-server   通話画面・ロガーの受け口 /ws/audio（今のまま）
    /grafana   → Grafana   :3001        前段で /grafana を削って渡す
    /live      → bridge    :3002        前段で /live を削って渡す（/live/clock・/live/map・/live/gg・/live/ws）
```

**サーバー本体への変更は要りません。** 画面はサーバーが`ECORUN_TELEMETRY_DIR`へ書くJSON Linesを読むだけです。
5Bは冗長構成の2台目`takao-secondary`で、10/25朝まで先輩と同じ`ghcr.io/tmcit-ecorun/ecorun-logger-server:latest`（`397facf`）、
**10/25 10:27からは試しに先輩のPR#13のイメージ**（`sha-72ed244d…`＝`397facf`＋`cluster.rs`の無通信監視）で動いています。
どちらでもJSON Linesの書き方は同じで、画面はそのまま出ています。

---

## 3. 用意するもの

- Docker Engineと`docker compose`（v2）
- 今動いている`ecorun-logger-server`の`ECORUN_TELEMETRY_DIR`を、ホストから読めること
- 外からの入口で、パスごとに振り分けられること（Tailscale Funnel／Caddy／nginxなど。6-4）

---

## 4. ファイル一覧（5Bの実物との照合は2026-10-25 10時40分）

すべてRaceCaptureリポジトリの`tools/home_telemetry/`にあります。

| ファイル | 役割 | 5Bの実物とのsha256（先頭12桁、一致） |
| --- | --- | --- |
| `grafana/ecorun-live.json` | ダッシュボードの定義（パネル・配置・クエリ・変数のすべて） | `ac1e62f1f676` |
| `grafana/build_dashboard.py` | 上のJSONを作るスクリプト（画面を直すときはこちらを直して実行） | ― |
| `live_bridge.py` | ブリッジ本体（1-3）。10/25 10:33の修正（古い行を捨てる）込み | `d9c34320d9bb` |
| `clock.html` | 「周回・時間」のページ（1-1） | `0e1f178f4d1c` |
| `map.html` | 地図ページ（Leaflet＋Esriの航空写真。ライブラリ・地図タイルはブラウザがネットから読む） | `88c235f00558` |
| `gg.html` | G-Gページ（ダッシュボードからは外してある） | `f32ade17fe47` |
| `owntracks.html` | スマホアプリOwnTracksの登録ページ（5Bでは外に公開していない） | `455f97395019` |
| `replay_sender.py` | 試験用：走行ログ（CSV）を「今走っている」形でサーバーへ送る（デモ再生もこれ） | `febb9a09400e` |
| `compare_replication.py` | 試験用：2台のサーバーの記録のevent_idを数えて、複製が届いているかを比べる | ― |
| `deploy/compose.yaml` | VictoriaMetrics・Grafana・ブリッジの3つ＋デモ再生（既定では起動しない） | 5Bの設定を写したもの（5章） |
| `deploy/bridge.Dockerfile` | ブリッジのイメージ（Python 3.13.5＋websockets 15.0.1。5Bと同じ版を確認済み） | 〃 |
| `deploy/grafana/provisioning/` | データソース（uid `ecorun-vm`）とダッシュボードの読み込み設定 | 〃 |
| `deploy/.env.example` | 公開ホスト名・テレメトリの場所・管理者パスワード・ポート | ― |

---

## 5. 5Bの設定とこの一式の対応（これで全部）

2026-10-25 10時に5Bで読み直した値です（10/24 3時から変わっていない）。

| 5Bでの場所 | 設定 | この一式での場所 |
| --- | --- | --- |
| Grafana 13.2.3（deb、arm64） | | `grafana/grafana:13.2.3` |
| `grafana-server.service.d/ecorun.conf` | `GF_SERVER_HTTP_PORT=3001` | ホストの`127.0.0.1:${GRAFANA_PORT}` |
| 〃 | `GF_DASHBOARDS_MIN_REFRESH_INTERVAL=500ms` | `compose.yaml`の`grafana.environment` |
| 〃 | `GF_AUTH_ANONYMOUS_ENABLED=true`・`GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` | 〃 |
| 〃 | `GF_ANALYTICS_REPORTING_ENABLED=false` | 〃 |
| 〃 | `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=…/ecorun-live.json` | 〃（コンテナ内の場所に） |
| 〃 | `GF_PANELS_DISABLE_SANITIZE_HTML=true`（地図・周回・時間のiframeのHTMLを通す） | 〃 |
| 〃 | `GF_SERVER_ROOT_URL=https://<公開ホスト名>/grafana/` | 〃（`.env`の`PUBLIC_HOST`から） |
| `grafana-server.service.d/gzip.conf` | `GF_SERVER_ENABLE_GZIP=true` | 〃 |
| `/etc/grafana/grafana.ini` | 変更なし（既定のまま） | ― |
| `provisioning/datasources/ecorun-vm.yaml` | 名前`EcoRun VictoriaMetrics`、uid `ecorun-vm`、prometheus型、既定、`timeInterval: 100ms` | `deploy/grafana/provisioning/datasources/ecorun.yaml` |
| `provisioning/dashboards/ecorun.yaml` | ファイルから読む（画面での保存は不可） | `deploy/grafana/provisioning/dashboards/ecorun.yaml` |
| `provisioning/`のその他 | パッケージに付いてくる`sample.yaml`だけ（中身は全部コメント） | ― |
| Grafanaのプラグイン | 追加なし（同梱のものだけ） | ― |
| Grafanaの中身（`grafana.db`） | 画面から作ったものは**管理者`admin`と、サービスアカウント`live-bridge`（Editor、トークン1本）だけ**。フォルダ・スター・注釈・ユーザー設定・公開ダッシュボード・アラート・ライブラリパネル・チームはすべて0件。データソースは上の1つ、ダッシュボードはファイルから読んだ1枚だけ（2026-10-25に5BのDBを読んで確認） | 6-3で同じ名前・同じロールで作る |
| `/etc/ecorun-grafana-token` | 上のサービスアカウントのトークン | `deploy/secrets/grafana-token`（6-3で作る） |
| `victoria-metrics.service` v1.154.0 | `-retentionPeriod=5y -httpListenAddr=127.0.0.1:8428 -search.latencyOffset=0s -dedup.minScrapeInterval=1ms` | `compose.yaml`の`victoria-metrics.command` |
| `ecorun-vm-bridge.service`（Python 3.13.5、websockets 15.0.1、`Restart=always`） | `live_bridge.py --dir <ECORUN_TELEMETRY_DIR>`（他は既定値。OwnTracksの受け口は`127.0.0.1:3003`で外には出していない） | `compose.yaml`の`bridge.command`（行き先だけコンテナ名に。OwnTracksも同じく外に出ない） |
| `ecorun-demo-replay.service`（**disabled・停止中**） | `replay_sender.py <大黒埠頭→品川のCSV> ws://127.0.0.1:3000/ws/audio/home-test`、終わったら10秒後に再起動 | `compose.yaml`の`demo-replay`（`--profile demo`のときだけ起動） |
| Tailscale Funnel | `/`→:3000、`/grafana`→:3001、`/live`→:3002（パスの頭は削られて渡る） | 6-4 |

5Bの機材に結びついていて、そのまま写していないもの：

- **microSDへのバックアップ**（`ecorun-backup`）：5BのeMMCが壊れたとき用。先輩のサーバーはディスクが冗長構成なので、
  必要なら8章のボリュームのバックアップを定期実行してください
- 地図に描いた図形・OwnTracksの登録（`map.db`）：**どちらも0件**（10/25確認）なので移す物はありません
- VictoriaMetricsの過去データ（約41MB）：画面は直近5分（たたんだ行の通過時刻の表は24時間）しか見ないので、無くても画面は同じに出ます。
  過去のグラフまで同じにしたいときは6-5で移せます

---

## 6. 手順

### 6-1. ファイルを取ってくる

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/ntakao2006-web/RaceCapture.git
```

```bash
cd RaceCapture && git sparse-checkout set tools/home_telemetry
```

```bash
cd tools/home_telemetry/deploy
```

### 6-2. `.env`を作って起動

```bash
cp .env.example .env
```

`.env`の`PUBLIC_HOST`・`TELEMETRY_DIR`・`GRAFANA_ADMIN_PASSWORD`を書き換えます。

- `TELEMETRY_DIR`：サーバーを名前付きボリュームで動かしているなら、
  `docker volume inspect -f '{{ .Mountpoint }}' <ボリューム名>`で出る場所（`ECORUN_TELEMETRY_DIR=/data`なら
  その`_data`そのもの、`/data/telemetry`なら`_data/telemetry`）
- `GRAFANA_PORT`・`BRIDGE_PORT`：チームの`compose.yaml`（logger-a／b）は**ホストの3001・3002を使う**ので、
  同じマシンで動かすなら空いている番号に変えてください（6-4の振り分け先も合わせる）

```bash
docker compose up -d --build
```

```bash
docker compose logs bridge
```

`Grafana Live push: off (no token file)`と`rebuild: … rows from the last 6 h`と出ていれば、ブリッジは動いています（トークンは次で入れる）。

### 6-3. 速度パネルのトークン（Grafana Live）

速度パネルだけはVictoriaMetricsを通さず、ブリッジがGrafana Liveへ0.1秒ごとに押し出しています。トークンが無いと
**このパネルだけ空**になります（他は全部動く）。

1. `https://<公開ホスト名>/grafana/` を開き、`admin`と`.env`のパスワードでログイン
2. Administration → Users and access → Service accounts → Add service account（名前`live-bridge`、ロール**Editor**。5Bと同じ）
3. Add service account token → 表示されたトークンをコピー
4. サーバーで保存して、ブリッジを再起動

```bash
mkdir -p secrets && install -m 600 /dev/null secrets/grafana-token
```

```bash
nano secrets/grafana-token
```

```bash
sudo chown 1000:1000 secrets/grafana-token
```

```bash
docker compose restart bridge
```

ログに`Grafana Live push: on`と出れば有効です。

### 6-4. 外からの入口（パスの振り分け）

5Bと同じく、**`/grafana`と`/live`は頭を削って渡します**（Grafanaは`ROOT_URL`でリンクに`/grafana/`を付けて返す）。
WebSocket（`/live/ws`、Grafana Live）も通る必要があります。

**Tailscale Funnel（5Bと同じ方式）**：今の`/`→サーバーの設定はそのままで、2つ足すだけです。

```bash
sudo tailscale funnel --bg --set-path=/grafana http://127.0.0.1:3001
```

```bash
sudo tailscale funnel --bg --set-path=/live http://127.0.0.1:3002
```

```bash
tailscale funnel status
```

5Bの`tailscale funnel status`はこうなっています（ホスト名だけ伏せた。10/25確認）：

```
https://<公開ホスト名> (Funnel on)
|-- /        proxy http://127.0.0.1:3000
|-- /live    proxy http://127.0.0.1:3002
|-- /grafana proxy http://127.0.0.1:3001
```

Funnel以外で受ける場合も、Funnelと同じく「`/grafana`ちょうど、または`/grafana/…`を、頭の`/grafana`を削って渡す」
（`/grafana`ちょうどは`/`になる）ようにします。`/live`も同じです。

**Caddyの場合**：

```caddyfile
<公開ホスト名> {
	@grafana path /grafana /grafana/*
	handle @grafana {
		uri strip_prefix /grafana
		reverse_proxy 127.0.0.1:3001
	}
	@live path /live /live/*
	handle @live {
		uri strip_prefix /live
		reverse_proxy 127.0.0.1:3002
	}
	handle {
		reverse_proxy 127.0.0.1:3000
	}
}
```

**nginxの場合**：

```nginx
# http{} の中に
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

# server{} の中に
location ~ ^/grafana(/.*)?$ {
    rewrite ^/grafana/?(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:3001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
}
location ~ ^/live(/.*)?$ {
    rewrite ^/live/?(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:3002;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
}
```

### 6-5. （任意）デモ再生と過去データ

**デモ再生**（5Bの`ecorun-demo-replay`と同じ。5Bでも普段は止めている）：走行ログのCSV（位置情報を含むのでGitには無い。
必要なら別途受け渡し）を`deploy/demo/replay_daikoku_shinagawa.csv`に置いて、

```bash
docker compose --profile demo up -d demo-replay
```

room `home-test`へ約18分の走行を繰り返し流します。サーバーに1周約1.3MBずつ保存され、冗長構成ならもう1台にも複製されるので、終わったら止めます。

```bash
docker compose stop demo-replay
```

**VictoriaMetricsの過去データ**：5Bでスナップショットを取り、その中身を新しいボリュームへ入れます（データの形式はCPUの種類に関係ありません）。

5Bで（スナップショット名が返る）：

```bash
curl -s http://127.0.0.1:8428/snapshot/create
```

スナップショットの中はシンボリックリンクなので、`-h`で実体をまとめます。

```bash
sudo tar -czhf vm-snapshot.tgz -C /var/lib/victoria-metrics/snapshots/<スナップショット名> .
```

```bash
curl -s "http://127.0.0.1:8428/snapshot/delete?snapshot=<スナップショット名>"
```

先輩のサーバーで（`vm-snapshot.tgz`を`deploy/`に置いて）：

```bash
docker compose stop victoria-metrics
```

```bash
docker run --rm -v ecorun-telemetry_vm-data:/storage -v "$PWD":/in busybox sh -c "rm -rf /storage/* && tar -xzf /in/vm-snapshot.tgz -C /storage"
```

```bash
docker compose start victoria-metrics
```

---

## 7. 確認

| 確認 | どうなれば良いか |
| --- | --- |
| `https://<公開ホスト名>/grafana/` | ログインなしで「EcoRun Live」が開く（ホーム） |
| `https://<公開ホスト名>/live/clock?room=<room>` | 「周回・時間」のページが出る（走っていなければ「スタート前」か「<room>: データなし」） |
| `https://<公開ホスト名>/live/map?room=<room>` | 航空写真の地図が出る |
| ロガーかアプリをつなぐ | 左上の`room`にそのroomが出て、「周回・時間」・地図・2段目の数字が動く |
| 「周回・時間」の一番下 | 「この画面のデータ」が数秒以内、「回線」が1秒前後 |
| 速度パネル | 6-3の後、0.1秒刻みで動く |
| 1280×720の画面 | サイドメニューを開いたままでも1画面に収まる |
| `docker compose logs bridge` | エラーが続いていない |

ロガー無しで試すときは、`replay_sender.py`で走行ログを流せます（走行ログは位置情報を含むので別途受け渡し）。
試験用のroomで流し、終わったらそのroomのファイルを消してください（5Bでも`clock-test`などで試して消している）。

```bash
python3 replay_sender.py <走行ログ>.csv wss://<公開ホスト名>/ws/audio/<room>
```

---

## 8. 知っておいてほしいこと

- **画面に出るのは、そのサーバーのJSON Linesに書かれた分だけ**です（ブリッジは自分のサーバーが書いたファイルを読む）。
  冗長構成で別のノードから複製されてきたデータも、受けたノードのJSON Linesに書かれます（2026-10-24 10:29、
  もてぎでmajestaの送り先を主＝先輩のサーバーへ移したとき、5Bが複製分をファイルに書き、5BのGrafanaがそのまま動き続けたことで確認）。
  ただし、**複製が流れているときだけ**です。10/24夜〜10/25は先輩のサーバー→5Bの複製が止まっていて
  （`maruo_share_20261025_cluster.md`）、**大会2日目はVer.2の主の送り先を5Bにしています**。両方の画面を同じにするには複製が流れていることが前提です
- 平均速度・通過時刻はブリッジが保存ファイルから計算しています。再起動しても直近6時間分は作り直しますが、
  **ロガーがレースの途中で別のサーバーへ移り、そのサーバーに複製が来ていない**と、そのレースの平均速度・通過の表は途中からになります
- 10/25 10:29に5Bで出た偽の通過（前夜の行を数えたもの）は、5BのVictoriaMetricsの`ecorun_lap_at`（たたんだ行の通過時刻の表）に、
  レース欄が01:02・03:13・03:20の行として残っています（消していない）。6-5で過去データを移すと、これも一緒に移ります
- 画面を直すときは`grafana/build_dashboard.py`を直して`python build_dashboard.py`で`ecorun-live.json`を作り直します。
  Grafanaは数秒で読み直すので再起動は要りません（ファイルの置き場所が共有されていれば、`git pull`だけで反映されます）。
  ブリッジ・ページ（`live_bridge.py`・`clock.html`・`map.html`・`gg.html`）を変えたときは`docker compose up -d --build bridge`
- **5Bと同じに保つ**：こちらで5Bの画面・ブリッジを直したときは、同じ変更をこのリポジトリへコミットしています（コミットの頭は`ER-8-…`、
  本文に「5Bへ反映済み」と書く）。先輩のサーバーでは`git pull`→上の手順で同じになります。4章のsha256で照合できます
- パネルの説明文（ⓘ）に古い記述が残っています（地図パネルの「tailscale serve の :8443」）。5Bも同じで、動きには影響しません
- サーバーのログに出る`skipping Podium sample without usable metadata…`の警告は、サーバー内のPodium用の変換が
  ロガーの詰めた形式の行を扱えないためのもので（`maruo_share_20261025_podium_rows.md`）、この画面には影響しません
- **公開範囲は5Bと同じ**：Grafana・ページはURLを知っていれば誰でも見られます（Grafanaは閲覧のみ）。
  地図に図形を描く・位置を共有するのに認証はありません。URLはチーム外に出さないでください
- 地図のライブラリ（unpkg.com）と航空写真（Esri）はブラウザがネットから直接読みます

### 残すべきデータ

| ボリューム | 中身 | 消えると |
| --- | --- | --- |
| `ecorun-telemetry_grafana-data` | 管理者・サービスアカウント | 6-3のやり直し（ダッシュボードはファイルにある） |
| `ecorun-telemetry_bridge-data` | 地図に描いた図形・OwnTracksの登録 | 図形の描き直し |
| `ecorun-telemetry_vm-data` | 履歴（5年保持） | 過去のグラフが消える（元のファイルから作り直せる） |
