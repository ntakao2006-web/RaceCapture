# 「skipping Podium sample…」の警告の原因と、5B側のログの照合結果（2026-10-25 朝）

佐藤先輩

ログとパッチ（PR#13）ありがとうございます。いただいた先輩のサーバーのログ（10/24 08:31〜10/25 02:29 UTC）と、5B側のログ・保存ファイルを突き合わせました。

## 先に結論

1. **警告の原因は、再接続やメタの送り直しではありません。** 行の形式の食い違いです
   - ロガー（Ver.2・Androidとも）は、Podium本来の形式で送っています：**値が入っているチャンネルの値だけ**をmetaの順に詰めて並べ、最後にビットマスク（Podium公式のRaceCaptureファームと同じ。`loggerApi.c`の`api_send_sample_record`）
   - サーバーの`telemetry_bridge.rs`の`PodiumChannels::decode`は、行の長さが常に`N + ceil(N/32)`（無効なチャンネルにも値を置く固定長）であることを前提にしているため、**1チャンネルでも無効な値がある行は全部捨てられます**
   - Ver.2（majesta）は、CANのない車なのでRPM・Throttle・WaterTempが常に無効で、周回のラインを通るまでは周回系も無効なため、**ほぼ全部の行が捨てられています**（先輩のサーバーの警告9,735件はすべてmajesta、セッション27の2,890件は、Ver.2側で送ったと記録している2,895フレームとほぼ同じ数）
   - 5Bでも同じ警告が出ています（10/24以降で android-test 約18.3万件、majesta 約7.4万件、aubergine 約2.6万件、super-cub 約1万件）
2. **ピットのGrafanaへの影響はありません。** 捨てられているのは、サーバーがデコードして配る`podium`イベント（Socket.IOの`telemetry`・Webの地図など）だけです。生の行（`podium.raw`）とJSON Linesファイルは保存・複製されていて、5Bのブリッジ（`live_bridge.py`）はPodium形式（詰めた形）でデコードしているので、Grafana・地図には出ています
3. **今朝は、先輩のサーバー → 5Bの複製が動いています。** majestaのデータが7:58から5Bに届いていて（5Bへの直接の接続は無いので、先輩のサーバーからの複製です）、8:25の時点で最新の行が届いていました

## ロガー側を固定長に変えない理由

ご依頼の「無効なチャンネルにも数値の仮置きを入れて固定長にする」は、今日は入れないでおきたいです。

- Podium本体はこの詰めた形を前提にしていて、サーバーの中継は「ロガーの行をそのままPodiumへ渡す」作りなので、ロガーを固定長にするとPodiumへ送ったときに値がずれます
- 5Bのブリッジ（ピットのGrafana）も詰めた形でデコードしているので、ロガーだけ変えると**ピットの表示の値が全部ずれます**。大会当日にVer.2・スマホ2台・ブリッジを同時に変えるのは危ないと考えています

その代わり、ご依頼にあった確認項目は、コードを追って次のとおりでした。

| 確認項目 | 結果 |
|---|---|
| 接続・再接続・送り先の切り替えのたびに`podium.meta`を送るか | 送っています。Ver.2は接続ごとに`hello`→`podium.meta`→サンプルの順（`podium.py`の`relay_session`）。送り先を切り替えるときも接続を作り直すので同じです |
| `podium.meta`より前に`podium.samples`が出ることはあるか | ありません。行のバッファは接続ごとに新しく作るので、前の接続の行が次の接続に混ざることもありません |
| チャンネルの順番が送信中に変わるか | 変わりません。設定が変わったときは、溜めていた行を捨て、新しい`podium.meta`を先に送ってから新しい並びの行を送ります |
| `null`・`NaN`を送るか | 送りません。有限の数値だけを入れ、それ以外はビットを落として行から抜きます |
| ビットマスクの形式 | 32チャンネルごとに1語、値の後ろ。0〜2^32−1の正の整数です（majestaは35チャンネルなので2語） |

## 行の具体例（majesta、35チャンネル。位置の値は伏せてあります）

metaの並び：
`Interval, Utc, Latitude, Longitude, Altitude, GPSSpeed, Yaw, GPSFix, GPSSats, AccelX, AccelY, AccelZ, GyroX, GyroY, GyroZ, Roll, Pitch, Speed, RPM, Throttle, WaterTemp, LongAccel, LatAccel, GPSAcc, OilTemp, OilTempState, LapCount, CurrentLap, LapTime, BestLap, ElapsedTime, RaceTime, LapsLeft, TimeLimit, Margin`

実際に送っている行（28要素＝値26個＋マスク2語）：

```json
[19735,1792882681000,35.0,139.0,167.63,0.05,0.0,3,24,0.41,-0.16,9.5,0.12,-0.12,0.0,2.44,-0.94,0.05,0.0,0.0,0.3,16.92,0,0,0,7,266600447,1]
```

- 1語目のマスク`266600447`＝`0x0FE3FFFF`：bit18〜20（RPM・Throttle・WaterTemp）と bit28〜31（LapTime・BestLap・ElapsedTime・RaceTime）が0
- 2語目の`1`：bit32（LapsLeft）だけ1。TimeLimit・Margin（bit33・34）は10秒に1回だけ値を入れ、それ以外は0
- サーバーは長さ37（35＋2）を期待しているので、この行は捨てられます。10秒に1回の行（30要素）も同じです

## サーバー側の直し方の案（大会後で構いません）

`PodiumChannels::decode`を、ビットが立っているチャンネルだけ値を順に読む形にすれば、今のロガーの行がそのまま読めます。

```rust
pub fn decode(&self, row: &[Value]) -> Option<Value> {
    let count = self.names.len();
    let words = count.div_ceil(32);
    if count == 0 || row.len() < words {
        return None;
    }
    let (values, mask_values) = row.split_at(row.len() - words);
    let masks: Vec<u32> = mask_values.iter().map(decode_mask).collect::<Option<_>>()?;
    let present = masks.iter().map(|m| m.count_ones() as usize).sum::<usize>();
    // ビットの数と値の数が合わない行（metaとずれた行）は捨てる
    if present != values.len() || masks.last().map_or(false, |m| count % 32 != 0 && m >> (count % 32) != 0) {
        return None;
    }
    let mut values = values.iter();
    let mut data = Map::new();
    for (index, name) in self.names.iter().enumerate() {
        if masks[index / 32] & (1u32 << (index % 32)) == 0 {
            continue;
        }
        let value = values.next()?;
        if !value.is_number() {
            return None;
        }
        data.insert(name.clone(), value.clone());
        // （Latitude/Longitudeの小文字キーの追加は今のまま）
    }
    (!data.is_empty()).then_some(Value::Object(data))
}
```

- 今の固定長の行（全部有効な行）もこの形で同じように読めます
- 今のテストの`converts_podium_position_into_map_keys_and_respects_mask`の`no_gps`の行は、詰めた形だと`[2000, 42, 9]`になります

## 5B側のログの照合（ご依頼の件、時刻は日本時間）

| 時刻 | 5B側 |
|---|---|
| 10/25 1:52 | Androidの試験機（pixel-test、room android-test）が5Bへ直接接続 |
| 1:57〜2:29 | 先輩のサーバー → 5Bへの接続が`No route to host`／`open Socket.IO websocket`で失敗し続けていた時間。**5B側には何も記録がありません**（5Bのtailscaledにも、Funnelが止まった記録はありません）。今は外から`https://rock-5b.tail5a9705.ts.net/`が200で返ります |
| 〜2:19:27 | 5B → 先輩のサーバーの接続について、切断・エラーの記録は無し（5Bは切れたと気づいていなかった） |
| 2:19:27 | こちらで5Bのコンテナを再起動（ログの`shutdown requested by SIGTERM`） |
| 2:19:28〜2:21:26 | 5B → 先輩のサーバーの接続が、つながっては0.3〜30秒で切れるのを繰り返す。5B側の理由は`peer websocket closed`か`cluster peer websocket disconnected`だけで、それ以上の理由は出ていません |
| 2:20:14〜 | 5B側でも`cluster messages dropped`（02:35までに593行） |
| 2:19:57 | Ver.2が5Bへ直接接続（`ecologger-v2`、room majesta） |
| 2:21:26〜今 | 5B → 先輩のサーバーの接続は切れていません（クラスタ関係の警告もなし） |
| 7:58〜 | majestaのデータが先輩のサーバーから5Bへ複製されて届いている（8:25時点で最新） |

- 履歴の同期が始まったかは、5Bのログには同期についての行が無いので分かりません（つながった直後の約88MB／35MBが流れた、という通信量の記録だけです）
- 2:19:57以降にVer.2が5Bへ直接送った分が先輩のサーバーへ複製されたかは、5B側からは見えません。先輩のサーバーの`/data/telemetry/majesta/`に、10/24 17:20 UTC以降のファイルがあるかで確認できると思います

## PR#13について

無通信の検出は、まさに10/24〜25に起きたことへの対策なのでありがたいです。今日は今の構成のまま（今朝は複製が動いているので）で行き、PR#13は大会後に試させてください。
