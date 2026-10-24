# ピット用Grafana・地図ページの引き継ぎ（自宅ROCK 5B → 別のLinuxサーバー）

自宅のROCK 5Bで動かしているピット用の画面（Grafanaのダッシュボード「EcoRun Live」と、その中に
埋め込んでいる地図・G-Gのページ）を、**別のサーバーで5Bと同じ見た目・同じ動きで立てる**ための資料です。
主サーバー（先輩のラックサーバー）も、**Grafanaを含めて5Bとまったく同じ構成にする**（2026-10-24決定）ためのものです。

- 2026-10-24 3時時点の5Bの実際の状態（Grafanaの内部のDBまで）を元にしています。画面の定義・地図ページ・ブリッジは、
  **5B上の実物とこのリポジトリのファイルが同一であることをsha256で確認済み**です（4章）
- 5Bはsystemdで直接動かしています。ここではそれを**Docker Composeへそのまま写した一式**
  （`tools/home_telemetry/deploy/`）を用意しました。5Bの設定との対応は5章に全部並べています
- `ecorun-logger-server`本体はこの一式に含めません。**今動いているサーバーの隣に足す**形です
- 文中の`<公開ホスト名>`は自分のサーバーの名前（Tailscale Funnelなら`<マシン名>.<tailnet名>.ts.net`）に読み替えてください

---

## 1. 画面の構成（EcoRun Live）

ダッシュボードは1枚（uid `ecorun-live`）で、Grafanaを開くと最初にこれが出ます（ホームに設定）。
左上の`room`で車を選びます（`ecorun_Speed`が来ているroomが並ぶ）。表示範囲は直近5分、更新は5秒ごとです。

```
 横24マス  0         5               13      17      21  24
 高さ6   │ 周回     │ 経過・残り時間 │平均速度│この周の│速度 │
         │ 走行中／ │（/live/clock を│(スタート│平均／  │Live │
         │ 残り周回 │  埋め込み）    │ から)  │前の周  │     │
 高さ4   │前回ラップ│この周の│GPS │GNSS精度│ 油温   │サーバー到着│
         │          │経過    │衛星│        │(状態付)│までの遅れ  │
 高さ14  │ 地図（/live/map を埋め込み）     │ G-G（/live/gg を埋め込み）│
         │  0〜14マス                       │  14〜24マス               │
 高さ9   │ 通過時刻の表（スタート・各コントロール・ゴールの時刻、ラップ秒、その周の平均速度）│
 高さ1   │ ▶ 詳細（たたんだ行。開くと「速度の推移」と「全チャンネル」が出て問い合わせが始まる）│
```

| パネル | 何を出しているか | 元のデータ |
| --- | --- | --- |
| 周回 | 走行中の周と残り周回 | ロガーの`CurrentLap`・`LapsLeft` |
| 経過・残り時間 | 経過、「目標まで」＝規定時間−余裕−経過、「規定まで」＝規定時間−経過（5分を切ると赤）。**スタート時刻だけを受け取り、見ている端末の時計で進める**ので、回線が詰まっても止まらない。一番下はこの画面が持つ最新データの古さ（ロガー→サーバー→この画面、10秒を超えると赤） | ブリッジの`/live/clock`（WebSocket `/live/ws?kind=clock`、毎秒約150バイト）。スタート時刻は`RaceTime`から、規定時間・余裕は`TimeLimit`・`Margin`（ドライバーのアプリで設定し、走行前にロガーへ書き込まれた値。二輪はアプリが直接送る） |
| 平均速度（スタートから） | 速度を時間で積算した平均 | **ブリッジが計算**（`RaceAvgSpeed`） |
| この周の平均／前の周 | 同上 | **ブリッジが計算**（`LapAvgSpeed`・`LastLapAvgSpeed`） |
| 速度 | 0.1秒ごとに動く速度 | **Grafana Live**（ブリッジが押し出す。トークンが無いと空。6-3） |
| 前回ラップ・この周の経過 | | `LapTime`・`ElapsedTime` |
| GPS衛星数・GNSS精度 | 精度は受信機の水平精度m（大きいほど悪い） | `GPSSats`・`GPSAcc` |
| 油温 | センサーハブの油温。状態が「正常」以外は温度を出さない。油温の無い車は「—」 | `OilTemp`・`OilTempState` |
| サーバー到着までの遅れ | ロガーが測った時刻（GNSS）から、そのデータがサーバーで検索できるようになるまでの秒数。**この画面の回線の遅れは含まない**（そちらは「経過・残り時間」の一番下） | `Interval`の時刻（測位が無くても届く） |
| 地図 | 航空写真に車の位置と軌跡。車を中央に追従（ドラッグで解除）、点の間を補間して滑らかに動かす。図形を描いて保存・見ている人の位置共有もできる | ブリッジの`/live/map`（WebSocket `/live/ws`） |
| G-G | 丸い目盛り。**下が加速・上が減速**（体が押される向き）・左右が横G、点が今・線が直近3秒、外の輪が0.5G。数値は＋が加速。埋め込みURLに`&flip=1`で左右反転（※パネルの説明文（ⓘ）は直し忘れで「上が加速」のまま。5Bも同じ） | ブリッジの`/live/gg` |
| 通過時刻の表 | タイム管理表へ写すための各ラインの通過時刻 | **ブリッジが計算**（周回の切り替わりから。`ecorun_lap_at`） |

地図・G-Gは、Grafanaの「テキスト」パネルにHTMLで`<iframe src="/live/map?room=$room">`のように埋め込んでいます。
**Grafanaと地図ページが同じホスト名の下にある**ことが前提です（`/grafana/`と`/live/`）。

### 10/18以降に変わった点（UIの変更履歴）

| 日付 | 変更 |
| --- | --- |
| 10/23 | 大会用の画面に作り直し：上段に周回・経過／残り時間・平均速度、中段に地図、通過時刻の表を追加 |
| 10/23 | 通話パネル（ピットはDiscordに一本化）とベストラップ（エコランでは無意味）を外した |
| 10/23 | GNSS精度と油温（状態つき）を追加。最終受信は測位が無くても届く`Interval`で判定 |
| 10/23 | 加速度の時系列をやめ、G-G表示（`gg.html`）を地図の隣に。同日、向きを「加速で下・減速で上」（体で感じる向き）に変更 |
| 10/23 | 画面の更新を0.5秒→2秒（速度・地図・G-Gはプッシュ配信なので遅れない）。Grafanaをgzip配信に |
| 10/24 | 規定時間・余裕を画面の入力欄で入れる方式をやめ、**ロガーから届く値を表示するだけ**に（ドライバーのアプリとずれないように） |
| 10/24夜 | 大会初日の指摘（もてぎでピットの回線が遅く、経過時間が約30秒遅れて見えた）を受けて：経過・残り時間を**端末の時計で進むページ**（`clock.html`）に置き換え、「最終受信」を「サーバー到着までの遅れ」に改名。地図・G-Gは描く項目だけを受け取る形にし（1ページ約2.4KB/秒→約0.4KB/秒）、Grafana Liveへは速度だけを送る。速度の推移・全チャンネルはたたんだ行へ。更新は5秒ごと |

---

## 2. 全体の構成

```
      ロガー・スマホ ──▶ ecorun-logger-server（今動いているもの）
                              │ ECORUN_TELEMETRY_DIR に <room>/<日時>Z.jsonl を書く
                              ▼
                        bridge（live_bridge.py）──▶ VictoriaMetrics（履歴。Grafanaのグラフ・表の元）
                              │                └──▶ Grafana Live（速度パネルの0.1秒更新）
                              └─ 地図ページ・G-Gページ・地図用WebSocket を配る

  外からの入口（1つのホスト名にまとめる）
    /          → ecorun-logger-server   通話画面・ロガーの受け口 /ws/audio（今のまま）
    /grafana   → Grafana   :3001        前段で /grafana を削って渡す
    /live      → bridge    :3002        前段で /live を削って渡す（/live/map・/live/gg・/live/ws）
```

**サーバー本体への変更は要りません。** 2026-10-24時点のチームの`ghcr.io/tmcit-ecorun/ecorun-logger-server:latest`
（`397facf`）が`ECORUN_TELEMETRY_DIR`へJSON Linesを書いていて、5Bもそのイメージのまま、このファイルを読んで画面を出しています。

---

## 3. 用意するもの

- Docker Engineと`docker compose`（v2）
- 今動いている`ecorun-logger-server`の`ECORUN_TELEMETRY_DIR`を、ホストから読めること
- 外からの入口で、パスごとに振り分けられること（Tailscale Funnel／Caddy／nginxなど。6-4）

---

## 4. ファイル一覧

すべてRaceCaptureリポジトリの`tools/home_telemetry/`にあります。

| ファイル | 役割 | 5Bの実物との一致 |
| --- | --- | --- |
| `grafana/ecorun-live.json` | ダッシュボードの定義（パネル・配置・クエリ・変数のすべて） | sha256一致 |
| `grafana/build_dashboard.py` | 上のJSONを作るスクリプト（画面を直すときはこちらを直して実行） | ― |
| `live_bridge.py` | ブリッジ本体（VictoriaMetricsへの書き込み、平均速度・通過時刻の計算、地図・G-Gの配信、Grafana Live） | sha256一致 |
| `map.html` | 地図ページ（Leaflet＋Esriの航空写真。ライブラリ・地図タイルはネットから読む） | sha256一致 |
| `gg.html` | G-Gページ | sha256一致 |
| `clock.html` | 経過・残り時間のページ（10/24夜に追加。端末の時計で進む） | sha256一致（10/24夜） |
| `owntracks.html` | スマホアプリOwnTracksの登録ページ（5Bでは外に公開していない） | sha256一致 |
| `replay_sender.py` | 試験用：走行ログ（CSV）を「今走っている」形でサーバーへ送る（デモ再生もこれ） | sha256一致 |
| `deploy/compose.yaml` | VictoriaMetrics・Grafana・ブリッジの3つ＋デモ再生（既定では起動しない） | 5Bの設定を写したもの（5章） |
| `deploy/bridge.Dockerfile` | ブリッジのイメージ（Python 3.13.5＋websockets 15.0.1。5Bと同じ版） | 〃 |
| `deploy/grafana/provisioning/` | データソース（uid `ecorun-vm`）とダッシュボードの読み込み設定 | 〃 |
| `deploy/.env.example` | 公開ホスト名・テレメトリの場所・管理者パスワード・ポート | ― |

---

## 5. 5Bの設定とこの一式の対応（これで全部）

| 5Bでの場所 | 設定 | この一式での場所 |
| --- | --- | --- |
| Grafana 13.2.3（deb） | | `grafana/grafana:13.2.3` |
| `grafana-server.service.d/ecorun.conf` | `GF_SERVER_HTTP_PORT=3001` | ホストの`127.0.0.1:${GRAFANA_PORT}` |
| 〃 | `GF_DASHBOARDS_MIN_REFRESH_INTERVAL=500ms` | `compose.yaml`の`grafana.environment` |
| 〃 | `GF_AUTH_ANONYMOUS_ENABLED=true`・`GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` | 〃 |
| 〃 | `GF_ANALYTICS_REPORTING_ENABLED=false` | 〃 |
| 〃 | `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=…/ecorun-live.json` | 〃（コンテナ内の場所に） |
| 〃 | `GF_PANELS_DISABLE_SANITIZE_HTML=true`（地図・G-GのiframeのHTMLを通す） | 〃 |
| 〃 | `GF_SERVER_ROOT_URL=https://<公開ホスト名>/grafana/` | 〃（`.env`の`PUBLIC_HOST`から） |
| `grafana-server.service.d/gzip.conf` | `GF_SERVER_ENABLE_GZIP=true` | 〃 |
| `/etc/grafana/grafana.ini` | 変更なし（既定のまま） | ― |
| `provisioning/datasources/ecorun-vm.yaml` | 名前`EcoRun VictoriaMetrics`、uid `ecorun-vm`、prometheus型、既定、`timeInterval: 100ms` | `deploy/grafana/provisioning/datasources/ecorun.yaml` |
| `provisioning/dashboards/ecorun.yaml` | ファイルから読む（画面での保存は不可） | `deploy/grafana/provisioning/dashboards/ecorun.yaml` |
| Grafanaのプラグイン | 追加なし（同梱のものだけ） | ― |
| Grafanaの中身（`grafana.db`） | 画面から作ったものは**管理者`admin`と、サービスアカウント`live-bridge`（Editor、トークン1本）だけ**。フォルダ・ユーザー設定・スター・注釈・アラート・公開ダッシュボードはすべて0件（2026-10-24に5BのDBを確認）。ダッシュボードはファイルから読んだ1枚だけ | 6-3で同じ名前・同じロールで作る |
| `/etc/ecorun-grafana-token` | 上のサービスアカウントのトークン | `deploy/secrets/grafana-token`（6-3で作る） |
| `victoria-metrics.service` v1.154.0 | `-retentionPeriod=5y -search.latencyOffset=0s -dedup.minScrapeInterval=1ms` | `compose.yaml`の`victoria-metrics.command` |
| `ecorun-vm-bridge.service`（Python 3.13.5、websockets 15.0.1） | `live_bridge.py --dir <ECORUN_TELEMETRY_DIR>`（他は既定値。OwnTracksの受け口は`127.0.0.1:3003`で外には出していない） | `compose.yaml`の`bridge.command`（行き先だけコンテナ名に。OwnTracksも同じく外に出ない） |
| `ecorun-demo-replay.service`（**disabled・停止中**） | `replay_sender.py <大黒埠頭→品川のCSV> ws://127.0.0.1:3000/ws/audio/home-test`、終わったら10秒後に再起動 | `compose.yaml`の`demo-replay`（`--profile demo`のときだけ起動） |
| Tailscale Funnel | `/`→:3000、`/grafana`→:3001、`/live`→:3002（パスの頭は削られて渡る） | 6-4 |

5Bの機材に結びついていて、そのまま写していないもの：

- **microSDへのバックアップ**（`ecorun-backup`：走行データを1分ごと、Grafana DB・設定を1日1回）：5BのeMMCが壊れたとき用。
  先輩のサーバーはディスクが冗長構成なので、必要なら8章のボリュームのバックアップを定期実行してください
- 地図に描いた図形・OwnTracksの登録（`map.db`）：**どちらも0件**なので移す物はありません
- VictoriaMetricsの過去データ（約34MB）：画面は直近5分（通過時刻の表は24時間）しか見ないので、無くても画面は同じに出ます。
  過去のグラフまで同じにしたいときは6-5で移せます。なお、ブリッジは**起動後に増えた分だけ**を読みます

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

`Grafana Live push: off (no token file)`と出ていれば、ブリッジは動いています（トークンは次で入れる）。

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
WebSocket（地図の`/live/ws`、Grafana Live）も通る必要があります。

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

5Bの`tailscale funnel status`はこうなっています（ホスト名だけ伏せた）：

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
別途受け渡し）を`deploy/demo/replay_daikoku_shinagawa.csv`に置いて、

```bash
docker compose --profile demo up -d demo-replay
```

room `home-test`へ約18分の走行を繰り返し流します。サーバーに1周約1.3MBずつ保存されるので、終わったら止めます。

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
| `https://<公開ホスト名>/live/map?room=<room>` | 航空写真の地図が出る |
| `https://<公開ホスト名>/live/gg?room=<room>` | G-Gの丸い目盛りが出る |
| ロガーかアプリをつなぐ | 左上の`room`にそのroomが出て、上段の数字・地図・G-Gが動く |
| 速度パネル | 6-3の後、0.1秒刻みで動く |
| `docker compose logs bridge` | エラーが続いていない |

ロガー無しで試すときは、`replay_sender.py`で走行ログを流せます（走行ログは位置情報を含むので別途受け渡し）。

```bash
python3 replay_sender.py <走行ログ>.csv wss://<公開ホスト名>/ws/audio/<room>
```

---

## 8. 知っておいてほしいこと

- **画面に出るのは、そのサーバーに直接つながったロガーの分だけ**です（ブリッジは自分のサーバーが書いたファイルを読む）。
  冗長構成で別のノードから同期されてきたデータがファイルにも書かれるかは**未確認**です。
  ロガーが予備へ切り替わったら、ピットは予備のGrafanaを見ることになります
- 平均速度・通過時刻はブリッジが**起動してから受けたデータで**計算しています。走行の途中でブリッジを再起動したり、
  ロガーが別のサーバーへ移ったりすると、そのレースの平均速度・通過時刻の表は途中からになります
- 画面を直すときは`grafana/build_dashboard.py`を直して`python build_dashboard.py`で`ecorun-live.json`を作り直します。
  Grafanaは数秒で読み直すので再起動は要りません（ファイルの置き場所が共有されていれば、`git pull`だけで反映されます）。
  ブリッジ（`live_bridge.py`・`map.html`・`gg.html`・`clock.html`）を変えたときは`docker compose up -d --build bridge`
- サーバーのログに出る`skipping Podium sample without usable metadata…`の警告は、サーバー内のPodium用の変換が
  ロガーの詰めた形式の行を扱えないためのもので、この画面には影響しません
- **公開範囲は5Bと同じ**：Grafana・地図はURLを知っていれば誰でも見られます（Grafanaは閲覧のみ）。
  地図に図形を描く・位置を共有するのに認証はありません。URLはチーム外に出さないでください
- 地図のライブラリ（unpkg.com）と航空写真（Esri）はブラウザがネットから直接読みます

### 残すべきデータ

| ボリューム | 中身 | 消えると |
| --- | --- | --- |
| `ecorun-telemetry_grafana-data` | 管理者・サービスアカウント | 6-3のやり直し（ダッシュボードはファイルにある） |
| `ecorun-telemetry_bridge-data` | 地図に描いた図形・OwnTracksの登録 | 図形の描き直し |
| `ecorun-telemetry_vm-data` | 履歴（5年保持） | 過去のグラフが消える（元のファイルから作り直せる） |
