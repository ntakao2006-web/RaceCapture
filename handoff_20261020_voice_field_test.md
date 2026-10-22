# 引き継ぎ：ロガー（UNO Q）＋Discordで有人の通話試験（2026-10-20）

新しいチャットの最初に、下の「貼り付ける文」をそのまま貼ってください。詳しい状況は、その下の各章に書いてあります。

---

## 貼り付ける文

```
handoff_20261020_voice_field_test.md を読んで、そこに書いた有人の通話試験を一緒に進めてほしい。
試験は2人（僕＝ドライバー役、作業アシスタント＝ピット役）で行う。
まず2章「試験の前に確かめること」を順に確認して、準備ができたら3章のT1から始めよう。
音を出す前には、何を何秒鳴らすかを先に言うこと。
```

---

## 0. 2026-10-22時点の準備状況（1〜4章より新しい）

**UNO Qは10/21に新品へ交換済み**（1章の「基板が傷んでいる」は旧個体の話）。新個体へ音声エージェントが入ったかは未確認なので、試験の最初に下のチェックを流す。

| 項目 | 状態（10/22夜） |
|---|---|
| 自宅サーバー `ecorun-logger-server` | 稼働中（`deploy/rock5b`＋声の取りこぼし修正 `32c6703`） |
| Discord Bot `ecorun-discord-bridge` | 稼働中・部屋`voice-test`につながっている。**ボイスチャンネルからは抜けた状態**（`/ecologger leave`の記憶が残っている）。試験前にピット役がボイスチャンネルに入ってから **`/ecologger join`**（部屋は省略で`voice-test`）。確認は`/ecologger status` |
| デモ再生 `ecorun-demo-replay` | 動いたまま（部屋`home-test`なので試験の邪魔はしないが、保存が増える）。止めるなら `ssh ecorun-home sudo systemctl stop ecorun-demo-replay` |
| UNO Q | 10/22にテザリング`Pixel_1167`で`ssh unoq`可。送信設定は試験用（中継・`voice-test`・Wi-Fi・受ける/送るON）になっていた |
| UNO Qの音声エージェント | 10/22に新個体へ導入（ホストに`python3-numpy`を追加、`install-voice-agent.sh`をDockerビルドで実行）。単体テスト5件OK、`ecocapture-voice`稼働・Webと応答あり。Bluetoothイヤホンは新個体では未ペアリング |
| マイク・耳 | 本番に近いUSB-Cのイヤホン（ALSA名`Audio`＝Synaptics Hi-Res Audio、マイク・再生・Sidetoneあり）。**音声エージェントは名前を決め打ちしない形に直した**（10/22）：USBオーディオのうちマイク＋再生のあるものを自動で選ぶ。`ECOVOICE_CARD`は「複数挿したときにどれを優先するか」だけ。音量のつまみ名も`Speaker`/`PCM`/`Headphone`の順に試す |
| UNO Q ⇔ 中継 | 10/22 21:33からUNO Q（`ecologger-v2`）が`voice-test`に接続、ピットの音声を受ける側（`mix_listener=true`）で入っている |

### T1の段取り（Wi-Fi・室内、ピット→ドライバー）
1. ピット役：Discordの個人テストサーバーのボイスチャンネルに入り、`/ecologger join`。`/ecologger status`で部屋`voice-test`につながったことを見る
2. ドライバー役：イヤホンはまだ耳に入れず手に持つ（音量は80%で鳴る。初回は大きさを確かめてから耳へ）
3. ピット役が「1、2、3…」と数える → ドライバー役がイヤホンで聞く。「せーの」で同時に数えて遅れを測る
4. 確かめ：`ssh unoq 'sh -s' < tools/voice_gate/precheck.sh` の`played`が増えていること
| 送信まわりの未コミット変更（LTEの電波品質`radio`を`/api/podium`に出す） | 自宅サーバー上で`test_podium`が通ることを確認。UNO Qへは未配置 |

UNO Qに入れたら、まずこれ（読むだけで何も変えない）：
```
ssh unoq 'sh -s' < tools/voice_gate/precheck.sh
```
`NG`が出たときの対処：
- RNNoise未配置・`ecocapture-voice`が動いていない → UNO Qの`~/EcoCapture-Web`で`sh install-voice-agent.sh`（新個体はgccが無いので、Dockerでビルドする版に直してある）
- numpyが無い → 旧個体でどう入れたか要確認（`apt install python3-numpy`はsudoが要る）
- 送り先・部屋・音声のON/OFF → 管理画面の送信設定で直す（中継のURLはメモリ参照、リポジトリに書かない）。新個体には`~/audio_check/podium_set.sh`が無い可能性がある

## 1. いまの状態（2026-10-20 4時時点）

やりたい構成：**UNO Qでノイキャン → 声のある間だけ自宅サーバーへ送る → Discord Botが中継 → Discordのピット。逆にDiscordの声をUNO Qで聞く。テレメトリは今まで通りWebSocketで送る。**

| 区間 | 状態 | 記録 |
|---|---|---|
| UNO Qでノイキャン（RNNoise旧版）→声のある間だけOpus 6kbpsで送る | 実機で動作（10/17）。**実際の車内の騒音・ヘルメット越しは未確認** | ER-10-9 |
| UNO Q ⇔ 自宅サーバー（LTE） | 屋外で、**片方向ずつなら上り・下りとも全部届いた**（10/19夜）。上りの声は代役（ユーザーの読み上げの録音）で、**本物のマイクでは未確認** | ER-10-9、`EcoCapture-Web/LTE_PODIUM.md` |
| 自宅サーバー ⇔ Discord | **Botで双方向に通った**（10/20 3時、ユーザーの個人テストサーバー）。**UNO Qとつないだ通しは未確認** | ER-10-8 |
| UNO Qで鳴らす | USBオーディオ・Bluetoothイヤホン（音楽用の方式）で耳で聞けた（10/17〜18、Wi-Fi） | ER-10-4 |
| 電源ONから最初のテレメトリ | 99秒（起動時の立て直しを早めた後、2回続けて） | ER-1-4 |

分かっている制限：
- **両方が同時に話し続けると`VoiceGuard`が音声を止める**（LTEでは「声なしの6割」を切ったら止める。ユーザー判断で、話している間テレメトリが約5件/秒に落ちるのは許容）
- 内蔵Bluetoothでは**イヤホンのマイクが使えない**（通話音声がLinuxへ来ない）。今の組み合わせは「耳はBluetoothイヤホン（またはUSB）、マイクはUSBのピンマイク」。Bluetoothヘッドセットのマイクを使うにはUSBのBluetoothアダプターが要る（未購入）
- **今のUNO Qは基板が傷んでいる**（裏面の部品脱落）。内蔵Bluetoothが一度固まり、電源の抜き差しでしか戻らなかった。原因不明の固まりは、まず基板を疑う
- Discord Botは**1つのDiscordサーバーで同時に1つのボイスチャンネルにしか入れない**。チャンネル呼び出しのコマンド（`/ecologger join`等、先輩のBotの`/join`・`/leave`と被らない名前）は**未実装**
- 中継サーバーの修正（声を捨てない）は**自宅サーバーだけ**。先輩のサーバーには入っていない

## 2. 試験の前に確かめること

1. **自宅サーバー**（`ssh ecorun-home`）：`ecorun-logger-server`と`ecorun-discord-bridge`が動いていること。Botの部屋は`voice-test`、Discordはユーザーの個人テストサーバーのボイスチャンネル（IDは`/etc/ecorun-discord-bot.env`）
2. **UNO Qの機材のつなぎ方**：UNO QのUSB-C ← ドック（PD給電パススルー）。ドックのUSB-AにUSBのピンマイク（`USB Lavalier Mic Pro`）を挿す。耳はUSBの再生か、Bluetoothイヤホン（Sudio N2 Pro、ペアリング済み・自動接続）
   - **ドックを使うとUSBのadbが使えない**ので、作業はWi-Fiの`ssh unoq`（`uno-q.local`）で行う。学校のWi-Fiでは名前が引けないことがある
3. **UNO Qの送信設定**：今は机の上で使うためにWi-Fi・Podium直送になっている。試験では「中継サーバー経由」・部屋`voice-test`・「ピットの音声を受ける」ON・「ドライバーの声を送る」ON にする（中継のURLはメモリ`project_home_server_rock5b`にある。リポジトリには書かない）。設定は管理画面か`~/audio_check/podium_set.sh`
4. **音声エージェント**（`ecocapture-voice`）が動いていて、マイクと耳を認識していること（`/api/podium`の`voice_agent`）
5. 音を出す前に、何を何秒鳴らすかを先に言う。音量も先に確かめる

## 3. 試験の段取り（2人）

役割：**ドライバー役＝ユーザー**（UNO Qのイヤホン・ピンマイク）、**ピット役＝作業アシスタント**（Discordのボイスチャンネル。スマホかPC）。2人は声が直接届かないよう、別の部屋か十分離れた場所に。

| 番号 | 試験 | 見ること |
|---|---|---|
| T1 | Wi-Fi・室内。ピット→ドライバー（ピットがDiscordで話す） | ドライバーのイヤホンで聞き取れるか。遅れ（「せーの」で数える） |
| T2 | Wi-Fi・室内。ドライバー→ピット | ピットのDiscordで聞き取れるか。話し始め・語尾が切れないか（ノイキャンのゲート） |
| T3 | 交互に会話（無線のように） | 使い物になる遅れか。イヤホンの音をマイクが拾ってピットに返っていないか（エコー） |
| T4 | わざと同時に話す | `VoiceGuard`がいつ止めるか、止まった後どう戻るか |
| T5 | 騒音の中（車のエンジン音・走行音の録音を鳴らす、または実車） | 騒音だけでゲートが開かないか。騒音の中の声が通るか |
| T6 | LTEに切り替えて屋外でT1〜T3 | 遅れ、テレメトリの件数/秒（`tools/voice_gate/telemetry_rate.py`）、切断 |

記録：各試験で「聞こえ方（言葉が取れたか）・遅れの秒数・切れたか・エコー」と、UNO Qの`/api/podium`の`voice_*`カウンタ・`voice_pauses`。

## 4. この先の判断待ち・残り

- 10/20夜：大会でロガーの通話を使うか、スマホ＋Discordにするかの判定
- Discord Botのチャンネル呼び出しコマンドと、車3台の同時通話（Botを3体にする案）
- Lintarohさんへのメモ`lintaroh_share_20261020_boot.md`（未送）
- 中継サーバーの修正（`ecorun-logger-server`の`fix/logger-voice-burst`）を先輩のサーバーへPRで出すか
- 大会前にUNO Qの送信設定をLTE＋中継サーバーへ切り替える
- 当日の手順書に「電源ONからピットに出るまで約1分40秒」と書く
