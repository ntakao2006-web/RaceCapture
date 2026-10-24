# Maruo.Sさんへ：ピット用Grafana・地図の引き継ぎ（2026-10-24、未送）

主サーバー（先輩のラックサーバー）でも、自宅のROCK 5Bと同じピット用の画面を出せるようにするための連絡。
DiscordのDMにそのまま貼る想定。本体は`server_deploy_grafana_x86.md`（RaceCaptureリポジトリ。先輩はcollaboratorなので見られる）。

---

お疲れ様です！
主サーバー（先輩のラックサーバー）も、Grafanaを含めて自宅のROCK 5Bと**まったく同じ構成**にしたいので、
ピット用の画面（Grafanaの「EcoRun Live」と、中に埋め込んでいる地図・G-G）を立てるための一式をまとめました。
5Bの設定ファイル・起動オプション・Grafanaの中身（DB）まで確認して、同じになるように写してあります。

- 手順書（画面の構成・10/18以降の変更点・5Bの設定との対応表・手順）
  https://github.com/ntakao2006-web/RaceCapture/blob/master/server_deploy_grafana_x86.md
- ファイル一式（ダッシュボードのJSON・地図とG-Gのページ・ブリッジ・Docker Compose）
  https://github.com/ntakao2006-web/RaceCapture/tree/master/tools/home_telemetry

要点です。

1. **サーバー本体の変更は要りません。** 今の`latest`（397facf）が`ECORUN_TELEMETRY_DIR`に書くJSON Linesを読むだけです（5Bも今そのイメージで動いています）
2. 足すのはVictoriaMetrics・Grafana・ブリッジ（Python）の3つで、`tools/home_telemetry/deploy/`で`docker compose up -d --build`すれば立ちます。Grafanaの設定・データソース・VictoriaMetricsの起動オプションは5Bの実物から写しました
3. 外からは今の公開URLに`/grafana`と`/live`の2つのパスを足すだけです（Funnelなら`tailscale funnel --bg --set-path=/grafana …`を2回。手順書6-4）
4. Grafanaの中で手で作るのは、速度パネル用のサービスアカウント`live-bridge`（Editor）とそのトークンだけです（5Bもこれだけ。手順書6-3）
5. 5Bに入っているデモ再生（普段は止めている）も、`--profile demo`で同じように動かせます。過去のグラフのデータも移せます（手順書6-5。どちらも任意）

確認させてください。

- 先輩のサーバーの外からの入口は、Tailscale Funnelですか？（nginx・Caddyの例も手順書に入れてあります）
- チームの`compose.yaml`の例はホストの3001・3002を使っていますが、同じマシンなら番号を変えてもらう必要があります（`.env`で変えられます）
- （確認済みのこと）冗長構成で別のノードから同期されてきたテレメトリも、`ECORUN_TELEMETRY_DIR`のファイルに書かれていました。
  10/24の朝、ロガーの送り先を先輩のサーバーへ移したとき、5Bが複製分をファイルに書き、5BのGrafanaがそのまま動き続けました。
  なので、ロガーがどちらにつながっていても両方のGrafanaに出るはずです（部屋が両方のノードにあれば）

こちらのPCでコンテナを実際に起動しての確認はまだできていません（構文の確認まで）。詰まったら教えてください！
