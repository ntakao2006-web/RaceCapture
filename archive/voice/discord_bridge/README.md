# Discord中継Bot（ER-10-8）

ピットはDiscordのボイスチャンネル、ドライバーはロガー（自宅サーバーの`/ws/audio/<room>`）で話す。
このBotが両方に参加して音声を橋渡しする。仕組みは`bridge.js`冒頭のコメントを参照。

## 自宅サーバー（ROCK 5B）での配置
- Node 22はOSに入れず、公式バイナリを`~/node22`に置いている（discord.jsの依存がNode 22.12以上を要求するため）
- `~/discord-bridge/`に`bridge.js`と`package.json`を置き、`PATH=~/node22/bin:$PATH npm install`
- `/etc/ecorun-discord-bot.env`（権限600、**トークンはここにだけ置く**）：
  ```
  DISCORD_TOKEN=...
  DISCORD_GUILD_ID=...
  DISCORD_CHANNEL_ID=...
  ```
- `ecorun-discord-bridge.service`を`/etc/systemd/system/`へ置いて`systemctl enable --now`。
  つなぐroomは`ECORUN_ROOM`（大会ではロガーのroom名に合わせる）

## トークン無しでの試験
```
DRY_RUN=listen ECORUN_ROOM=bridge-test node bridge.js   # ミックスの受信数を2秒ごとに表示
DRY_RUN=tone   ECORUN_ROOM=bridge-test node bridge.js   # Discordの人が3秒話した想定の440Hzを送る
```
2026-10-15：自宅サーバーで、toneの3秒分がlisten側にミックスとして25パケット（120ms×25）届くことを確認。

## Discordでの操作（`/ecologger`）
先輩のBot（`ecorun-talk`）の`/join`・`/leave`と被らないよう、1つの親コマンドにまとめている。返事は呼んだ本人にだけ見える。
- `/ecologger join` … 呼んだ人がいるボイスチャンネルに入る。`channel:`で入る先を指定、`room:`でつなぐロガーの部屋（車）を切り替え。
  部屋はサーバーに登録済みの名前だけ（未登録なら元の部屋のまま、と返事する）
- `/ecologger leave` … ボイスチャンネルから出る（部屋とのつながりは残す。再起動しても入り直さない）
- `/ecologger status` … いまの部屋・ボイスチャンネル・Discord→部屋で送信中か
- `/ecologger audio` … 部屋のロガーの音声の設定を見る（何も指定しない）・変える（2026-10-22）。
  `level:` ドライバーの声の大きさの目標（dBFS、-30〜-6、標準-16）、`max_gain:` 増幅の上限（dB、0〜40、標準30）、
  `lowcut:` 低音カット（Hz、0〜400、標準250、上げると風切り音が減る）、`bitrate:` ドライバーの声のビットレート
  （kbps、6〜16、標準6、上げるとLTEの通信量が増える）、`volume:` ドライバーのイヤホンの音量（%、標準80）。
  中継サーバーの`logger.config`でロガーへ届き、ロガーが今の値を返す（LTEで最大数秒）。値はロガーの再起動後も残る。
  **中継サーバーが`logger.config`に対応している必要がある**（自宅版のみ、2026-10-22）
- 最後のコマンドの結果は`~/discord-bridge/state.json`に残り、再起動後は`DISCORD_CHANNEL_ID`・`ECORUN_ROOM`よりこちらが優先される
- コマンドは起動時にそのDiscordサーバー専用として登録する（すぐ出る）。Botは1つのDiscordサーバーで同時に1つのボイスチャンネルにしか入れない

## Discordサーバー側の設定
- ボイスチャンネルの権限で`@everyone`の「音声検出を使用」をオフ（ピットはプッシュトゥトーク強制）
- Botには「音声検出を使用」「接続」「発言」を許可（招待URLの`permissions=36701184`がこの4つ＋チャンネルを見る）

## 既知の制約
- 音声の変換は`opusscript`（WASM）。変換器を作るたびにメモリが広がり、広がると古い変換器が壊れる（2026-10-22に7回落ちた）ので、
  変換器は起動時に作ったものを使い続ける（部屋→Discordは無音を挟んだ1本の流れ）。ネイティブ版`@discordjs/opus`は
  自宅サーバー（arm64・GCC 14）ではビルドできなかった
- room→Discordの音はロガー向けと同じ8kHz・6kbpsのミックスなので、Discord側では電話程度の音質になる
- Discordの音声受信はDiscordの公式文書に無い機能で、安定は保証されていない（複数人の実通話で確認が要る）
