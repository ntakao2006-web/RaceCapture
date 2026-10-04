# Podium送信の実装に使う参照ソースの取り出し方

> 🔴 **2026-10-04 追記：このメモの送り方では、今のPodiumにはつながりません。**
> Podiumは2026年8月末に旧システムが廃止され、次世代システムへ移行しました。
> PCから正しいキー（再生成したものも）で試しても、認証直後に切断されることを確認しています。
> **ロガー側の実装ミスではない**ので、この方式での作業はいったん止めてください。
> 新システムの送信仕様は公開されておらず、今後の方針は `podium_connect_notes.md` 9.4.2章にまとめてあります
> （当面は公式RaceCaptureアプリを中継役にする方式が有力）。

ロガーV2でPodiumへの送信を実装するときの引き継ぎメモです（2026-10-04）。
Podiumとのやり取りの仕様は、リポジトリの `podium_connect_notes.md` の3章と9章にまとめてあります。
その根拠になっている公式のソースコードが、**リポジトリをクローンしただけでは空に見える**ので、取り出し方を書きました。

---

## 1. 何が起きているか

`reference/` の下にある次の3つのフォルダは、別のリポジトリを取り込む「サブモジュール」という仕組みで入っています。

- `reference/RaceCapture-Pro_firmware`（公式ロガーのファームウェア）
- `reference/RaceCapture_App`（公式RaceCaptureアプリ）
- `reference/RaceCapture_App_fork_ryandoherty`（上と同じもの）

普通に `git clone` すると、**フォルダはできても中身は空**です。
`podium_connect_notes.md` に「`cellular.c` を見て」などと書いてあっても、開けません。

## 2. 中身を取り出す手順

リポジトリのフォルダで、次のコマンドを1回実行してください。

```bash
git submodule update --init --depth 1
```

- `--depth 1` は履歴を取らずに必要な版だけ取る指定です（そのぶん早く終わります）
- これから新しくクローンする場合は、最初から次のようにしても同じです

```bash
git clone --recurse-submodules --shallow-submodules https://github.com/ntakao2006-web/RaceCapture.git
```

取れたかどうかは、`reference/RaceCapture-Pro_firmware/src/devices/cellular.c` が開けるかで確認できます。

## 3. コマンドを使わずにブラウザで見る方法

GitHubで直接読むこともできます（どれも公開リポジトリです）。
こちらで参照しているのと同じ版へのリンクです。

公式ファームウェア（autosportlabs/RaceCapture-Pro_firmware）
- Podiumへの認証を送る部分（`auth_telem_stream`）
  https://github.com/autosportlabs/RaceCapture-Pro_firmware/blob/fa6ecf6d71b88b9b2e751ef7745aaf4d892b53f2/src/devices/cellular.c
- LTE-Mモデム（u-blox SARA-R4）をATコマンドで動かす例。SIM7070Gと同じクラスのモデムなので構造が近い
  https://github.com/autosportlabs/RaceCapture-Pro_firmware/blob/fa6ecf6d71b88b9b2e751ef7745aaf4d892b53f2/src/devices/sara_r4.c
- 3Gモデム（SIM900）の例。透過モードの使い方の参考
  https://github.com/autosportlabs/RaceCapture-Pro_firmware/blob/fa6ecf6d71b88b9b2e751ef7745aaf4d892b53f2/src/devices/sim900.c
- サンプル送信のJSON（`api_send_sample_record`）とチャンネル定義（`json_channelConfig`）
  https://github.com/autosportlabs/RaceCapture-Pro_firmware/blob/fa6ecf6d71b88b9b2e751ef7745aaf4d892b53f2/src/logger/loggerApi.c
- 送信先のホスト・ポートと、標準チャンネル名（`Latitude` など）の既定値
  https://github.com/autosportlabs/RaceCapture-Pro_firmware/blob/fa6ecf6d71b88b9b2e751ef7745aaf4d892b53f2/include/logger/loggerConfig.h

公式アプリ（ryandoherty/RaceCapture_App）
- Podiumとのやり取りが1ファイルにまとまっていて、いちばん読みやすい
  https://github.com/ryandoherty/RaceCapture_App/blob/2738967a864af20e04b6e864e1f45279bc21c497/autosportlabs/telemetry/telemetryconnection.py

**最初に読むなら `telemetryconnection.py` の `_send_auth` / `_handle_msg` / `_send_meta` / `_send_sample` の4つ**です（合わせて60行ほど）。

## 4. 詰まりやすい点（`podium_connect_notes.md` 9章の要約）

1. **送信の流れはこの順番を必ず守る**
   TCP接続（`telemetry.podium.live` の 8080番、暗号化なし）
   → 認証 `{"cmd":{"schemaVer":2,"auth":{"deviceId":"<ストリーミングキー>"}}}` と改行
   → サーバーから `{"status":"ok",...}` が返るのを待つ
   → チャンネル定義 `{"s":{"meta":[...]}}` を1回送る
   → 以後 100msごとに `{"s":{"d":[...]}}` を送る
   どのメッセージも**1行のJSON＋改行（`\n`）**です。改行が無いとサーバーが受け取りません
2. **`d` の中身は「値 → 最後にビットマスク」の順**。値は、その回に値があったチャンネルのものだけをmetaの順に並べます。ビットマスクの語数は**metaのチャンネル総数**で決まります（32チャンネルまでなら1語）。値が1つも無い回でも、ビットマスク（0）は送ります
3. **チャンネル名は純正と同じにする**。地図表示に使う `Latitude` / `Longitude`（小数点以下6桁）、`Speed`、`Utc` などです。名前が違うと地図が出ない可能性があります
4. **サーバーから想定外の行が来ても止まらないようにする**。公式アプリはログに出して無視しています
5. **SIM7070Gの手順はチームに動いている実装がある**。`TMCIT-Ecorun/2026-logger-frontpanel` と `TMCIT-Ecorun/ecorun-talk` で、`AT+CNACT` → `AT+CAOPEN` → `AT+CASEND` によるTCP送信が動いています。向こうは暗号化あり（WSS）ですが、Podiumは暗号化なしなので、SSL関係の設定を省くぶん手順が短くなります

## 4.5 【追記】刷新後のPodiumサーバーの実際の反応（2026-10-04 PCから実測）

Podiumのシステムが刷新されたあとも、上の送り方（8080番・1行JSON＋改行）はそのまま受け付けていました。
ただし、**キーが通らなかったときの反応が古い資料と違います**。

- **認証を送った直後に、何も返さず切断される** → キーが通っていない
  （古い資料では `{"status":...}` のエラーが返ることになっていますが、今は返ってきません）
- **接続はできるのに何も返ってこない** → 末尾の改行が届いていない。`AT+CASEND` の長さに `\n` の1バイトを入れ忘れていないか確認してください
- **接続自体ができない** → モデム・回線・ATコマンド側の問題

キーそのものが生きているかは、リポジトリの `podium_test_sender.py` をPCで動かせば確かめられます（キーは画面に出ない入力で聞かれます）。
**PCからでも切られるならPodium側（キー）の問題、PCからは通るならロガー側の問題**です。

## 5. 切り分けのおすすめ

いきなりSTM32で書くと、「Podiumへの送り方が違う」のか「ATコマンドの扱いが違う」のかが区別できません。

1. 先にPCのPythonで、上の流れを数十行で書き、ダミー値（固定の緯度経度など）を10Hzで流す
2. podium.liveのライブ画面に出たら、送り方は正解
3. そのあと同じバイト列をSTM32＋SIM7070Gから出す

## 6. 注意

- **ストリーミングキーは暗号化なしで流れる認証情報**です。リポジトリ・ログ・スクリーンショット・Discordの公開チャンネルには載せないでください
- 状況が分かったら、どこで止まっていたかを教えてもらえると資料に反映します
