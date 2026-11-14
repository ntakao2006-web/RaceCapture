# 解析ソフトへの書き出し：形式の先行調査（SP-5-5）

2026-11-13 調査。`task_spec_rebuild_breakdown.md` の SP-5-5（`SPEC.md` A-5）のための下調べ。
**この資料は調べた結果だけで、まだ何も作っていない。** 形式を決めるのはユーザー（8章）。

- 調べ方：公式の資料と、有志の実装のREADME・ソースをWebで読んだ。**実際にソフトへ読み込ませる確かめはしていない**
- 「未確認」と書いた所は、一次情報に当たれなかった・ページが開けなかった所
- 「検索の要約のみ」と書いた所は、ページ本体が開けず、検索結果に出た要約だけで書いた所（MoTeCの公式サイトとフォーラムは自動の読み取りを受け付けなかった）

---

## 1. 先に結論

1. **MoTeCの`.ld`は自前で書けそう。** 公式の仕様は公開されていないが、有志が解析した読み書きの実装が複数あり、
   レースゲームの記録を`.ld`に変える道具が実際に使われている。ラップの区切りは隣に置く`.ldx`（中身はXML）に書く。
2. **i2の版の制約は「Pro用の印が付いたファイルなら、i2 Standard でも i2 Pro でも追加のライセンスなしで開ける」**という説明が複数ある
   （有志の実装のREADME、MoTeCフォーラムの回答の要約）。有志の書き出しはこの印を付けて書く。
   ただし**MoTeCの使用条件として、MoTeC製でない機器のデータをi2 Proで使ってよいか**は別の話で、古いフォーラムの回答では「MoTeCが認めた製品に限る」とされている。
   ここは現行の使用許諾を読んで判断する必要がある（3-4）。
3. **`.vbo`（RaceLogic）は仕様が公式に公開されているテキスト形式**で、作るのがいちばん易しく、開けるソフトも多い
   （Circuit Tools・RaceChrono・RaceRender・Telemetry Overlay・Track Attack ほか）。
4. **おすすめの順**：(1) `.vbo` → (2) `.ld`＋`.ldx` → (3) 必要になったら RaceRender向けCSV・MDF4。理由は6章。

---

## 2. こちらの記録に何が入っているか（書き出せる項目）

リポジトリの中を軽く見た範囲（`tools/race_analysis/race_analysis.py`・`sd_gnss.py` の冒頭。`drive_logs/` は開いていない）。

| 種類 | 本体のCSVの列（`race_analysis.py` が読む列） | 書き出し先での扱い |
|---|---|---|
| 時刻 | `mcu_ms`・`host_utc`・`gnss_utc`・`gnss_itow_ms` | どの形式も時刻が要る。`.vbo`はUTCの時分秒、`.ld`は開始からの一定間隔 |
| 位置（GNSS） | `Lat`・`Lon`・`Altitude`・`Yaw`（向き）・`GPSFix`・`GPSSats`・`gnss_hacc_m` | 地図とラップの元。10 Hz（SDの`EL*.BIN`に全部残る。`sd_gnss.py`） |
| 速度 | `GPSSpeed`・`Speed`（車両CAN）・`WheelFrontA/B`・`WheelRearA/B` | そのまま |
| エンジン | `RPM`・`Throttle`・`WaterTemp`・`WaterTempDefi`・`OilTemp`・`IntakeTemp`・`ClutchDisengaged`・`FuelLevelRaw` | そのまま（追加のチャンネル） |
| 動き | `AccelX/Y/Z`・`LongAccel`・`LatAccel`・`GyroZ` | そのまま |
| 油圧など | `PressVolt`・`Temp1Volt`・`Temp2Volt`（電圧のまま） | 物理量へ直してから出すかを決める |
| ラップ | `LapCount`・`CurrentLap`・`LapTime`・`BestLap`・`Sector`・`SectorTime` | ラップの区切りの時刻へ直して出す。コントロールラインは解析の設定（`line`）にある |
| 距離 | `Distance` | そのまま |

- 本体のCSVの1行の間隔（何Hzか）は、この調査では確かめていない（**未確認**。作るときに実物で見る）
- どの形式でも「全部の列を同じ間隔に並べ直す」作業が要る（`.vbo`は1ファイル1つの間隔、`.ld`はチャンネルごとに一定の間隔）

---

## 3. MoTeC i2（`.ld` と `.ldx`）

### 3-1. 公式の仕様は公開されているか

- **公開されていない。** MoTeCのフォーラムの「Log file format」で、形式は出していないという回答がある（**検索の要約のみ**。本体は開けず）
  https://forum.motec.com.au/viewtopic.php?p=2241
- 有志の実装はどれも「実物のファイルを調べて分かった範囲」で作られている。中身に意味の分からない固定の数字が残っている
  （`ldparser.py` のコメントに「unknown」「some magic number?」とある）
  https://github.com/gotzl/ldparser

### 3-2. 有志の実装

| 名前 | 言語 | ライセンス | 読む／書く | 分かったこと | 出どころ |
|---|---|---|---|---|---|
| gotzl/ldparser | Python | GPL-3.0 | 読む＋**書く** | READMEは「読む道具」とだけ書くが、ソースに`write()`がある。ヘッダー（ドライバー・車両・会場・短いコメント・日時）、イベント・会場・車両の欄、チャンネル（名前32字・短い名前8字・単位12字・周波数・型）を書ける。書ける型は16/32ビットの整数と小数。**64ビットの小数は読めるが書けない**。`.ldx`は扱わない | https://github.com/gotzl/ldparser ／ https://raw.githubusercontent.com/gotzl/ldparser/master/ldparser.py |
| stevendaniluk/MotecLogGenerator | Python | READMEに明記なし（検索の要約ではWTFPL。**未確認**） | 書く | CSV・CANの記録（DBCつき）から`.ld`を作る。上のldparserを部品に使う。全チャンネルを一定の周波数へ並べ直す。ドライバー・車両・会場・イベント・コメントを入れられる。**`.ldx`・ラップ・GPSの説明はない**。「Pro Enabled なので i2 Standard でも i2 Pro でも開ける」と書いてある。「研究用で、MoTeCのライセンスの決まりを避けるために使わないこと」という断り書きあり | https://github.com/stevendaniluk/MotecLogGenerator |
| GeekyDeaks/sim-to-motec | Python | **未確認**（READMEに記載なし） | 書く | Gran Turismo 7・Automobilista 2 の記録を`.ld`と`.ldx`に変える。**`.ldx`にラップの区切り（ビーコン）・総周回・ベストの周とタイムを書く**。GT7ではコース図を出すために「にせのGPS」を書いている（＝GPSのチャンネルを書けばi2でコース図が出せる）。会場名も入れる | https://github.com/GeekyDeaks/sim-to-motec ／ https://raw.githubusercontent.com/GeekyDeaks/sim-to-motec/main/stm/motec/ldx.py |
| afonso360/motec-i2 | Rust | MIT | 読む＋書く | `LDReader`と`LDWriter`がある。ヘッダー・イベント・会場・車両・チャンネルの型を持つ。説明の文書は少ない（全体の13%） | https://docs.rs/motec-i2/latest/motec_i2/ |
| BenergyRacing/racing-data-converter | TypeScript | GPL-2.0 | 書く | `.ld`ではなく**MoTeCのCSV**（3-5のCSV取り込み用）を書く。ほかにMegaLogViewer・Pi Toolbox・WinDarab向けのテキストも | https://github.com/BenergyRacing/racing-data-converter |

ライセンスの注意：このリポジトリは公開なので、**GPLの実装（ldparser）をそのまま取り込むと、取り込んだ部分にGPLがかかる**。
形式の知識だけを借りて自前で書くか、MITの実装を手本にするか、別の小さな道具として分けるかを、作る前に決める。

### 3-3. どこまで書けるか

| 項目 | 書けるか | 根拠・注意 |
|---|---|---|
| チャンネル（名前・単位・周波数・値） | 書ける | ldparserの`ldChan`。周波数はチャンネルごとに一定でなければならない（MotecLogGeneratorが全部を並べ直しているのはこのため） |
| ドライバー・車両・会場・イベント・コメント・日時 | 書ける | ldparserの`ldHead`・`ldEvent`・`ldVenue`・`ldVehicle` |
| ラップの区切り（ビーコン） | 書ける（`.ldx`に） | sim-to-motecの`ldx.py`。`<MarkerGroup Name="Beacons">`の中に、周の終わりの時刻（記録の頭からのマイクロ秒）を並べる。`.ldx`は`.ld`と同じ名前で隣に置く |
| ベストの周・総周回 | 書ける（`.ldx`に） | 同上（`Total Laps`・`Fastest Time`・`Fastest Lap`） |
| GPS（緯度・経度） | 書けるが**精度に注意** | 本物のMoTeCの記録では`GPS.Latitude`・`GPS.Longitude`が**64ビットの小数**だった（ldparserのissue #19）。ldparserの書く側は64ビットに対応していない。32ビットの小数だと、日本の経度（約140度）では1目盛りが1 m強になる（こちらの計算）。**64ビットで書く部分を自前で足す必要がありそう**。sim-to-motecがどの型で書いているかは**未確認** https://github.com/gotzl/ldparser/issues/19 |
| コース図 | i2の中で作る | i2の「Tools → Track Editor → Generate Track」でGPSから作る。要るチャンネルは `GPS Latitude`・`GPS Longitude`・`GPS Speed`（MoTeCのGPSの説明書。**検索の要約のみ**）。きれいな1周を選んで作る https://forum.motec.com.au/viewtopic.php?p=22365 |
| セクター | **未確認** | i2の側でコース図に区間を切るのが普通。ファイルに書けるかは調べきれていない |

### 3-4. i2 Standard と i2 Pro のどちらで開けるか

分かったこと（出どころの強さの順）：

1. MoTeCのM1 Tuneの公式ヘルプ：機器側で「Pro Analysis」が有効なら、書き出される`.ld`は**i2 Proのログ**になる。
   そうでない**Standardのログをi2 Proで開くには有効化（ライセンス）が要る**
   https://help.motec.com.au/m1/tune/1.5/Topics/Logged_Data_Importing_Exporting_1.5.html
2. つまり`.ld`の中に「Pro用かどうか」の印がある。ldparserは書くときにこの欄へ固定の数字を入れている（コメントは「pro logging (some magic number?)」）。
   MotecLogGeneratorのREADMEは、この書き方で作ったファイルは**i2 Standard でも i2 Pro でも開ける**としている
   https://github.com/stevendaniluk/MotecLogGenerator
3. MoTeCフォーラムのCSV取り込みの話でも「できた`.ld`はi2 Proのファイルなので、**i2 Standardでもi2 Proでも追加のライセンスなしで開ける**」という回答がある（**検索の要約のみ**）
   https://forum.motec.com.au/viewtopic.php?p=19680
4. i2 Standard と i2 Pro はどちらもMoTeCのサイトのダウンロードに並んでいる（64ビット版 1.1.6、2024年7月。**検索の要約のみ**。無料と明記されているかは**未確認**）
   https://www.motec.com.au/i2/i2downloads/
5. 「どんなMoTeCのログでもi2 Proで開けるようにする」1年・PC1台のライセンス（#22011）が別に売られている（**検索の要約のみ**）
   https://www.motec.com.au/i2/i2licences/

まとめると：

- **技術の面**：Pro用の印を付けて書けば、i2 Pro でそのまま開ける見込みが高い（レースゲームの変換の道具がこの形で使われている）。i2 Standard でも開けるという説明があるが、**こちらで確かめてはいない**
- **使用条件の面**：古いフォーラムの回答に「i2 Proは、MoTeCの機器か、MoTeCが認めた他社のソフトのデータに限る」という趣旨がある（**検索の要約のみ**・18年ほど前）。
  自作ロガーのデータをi2で見ることが今の使用許諾で認められているかは**未確認**。
  **個人で見る分には道具として作れるが、チームへ配る・公開のリポジトリに「i2で開けます」と載せる前に、i2を入れたときに出る使用許諾を読むか、MoTeCの代理店に聞くのが安全**
  https://forum.motec.com.au/viewtopic.php?p=2241 ／ https://forum.motec.com.au/viewtopic.php?p=3219

### 3-5. i2 はCSVを取り込めるか

- **取り込めるが、有料。** i2 Pro の「File → Import Data」で種類を「MoTeC CSV Dataset」にして読む。
  それには「Import MoTeC CSV Dataset」という**1年ごとのライセンス**が要る（MoTeCフォーラム・販売店の商品名 #22085。**検索の要約のみ**）
  https://forum.motec.com.au/viewtopic.php?p=19680 ／ https://www.cj-motor.com/motec-i2-imp-motec-csv-dataset-1yr-lic-rnw
- CSVの書式はMoTeC独自。手本は「i2で何かのログをCSVに書き出したもの」。Excelで開いて保存すると読めなくなる。
  取り込むと日時が取り込んだ時刻になる、イベント名が入らない、という報告がある（同上）
- → **ライセンスを買わないなら、CSVの道は使えない。`.ld`を直接書くほうが筋がよい**

---

## 4. ほかの形式

### 4-1. RaceLogic `.vbo`（Circuit Tools）

- **仕様は公式に公開。** RaceLogicの開発者向けページに構造の説明がある
  https://developers.racelogic.co.uk/Portal/Tutorials/tutorialVBOfilestructure.html
- 中身はテキスト。`[header]`（チャンネルの名前）→`[channel units]`（追加のチャンネルの単位）→`[comments]`→`[laptiming]`（コントロールラインと区間の線）→`[column names]`→`[data]`（1行1サンプル）
- 決まった形の列：時刻は`hhmmss.sss`（UTC）、緯度は「分×100000」、経度は「分×-100000」（**東経が負になる向き**。間違えやすい）、速度はkm/h、向きは度、高さはm
- **追加のチャンネルは自由に足せる**（回転数・スロットル・油温・水温など。名前に空白は使えない）
- **ラップ**：`[laptiming]`に `Start <緯度1> <経度1> <緯度2> <経度2> ¬ 名前` の形で線を書ける。区間は`Split`
- **1ファイルの間隔は1つだけ**（複数の間隔を混ぜられるのはバイナリの`.vbb`のほう）
  https://en.racelogic.support/Knowledge_Base/File_Formats
- **Circuit Tools は無料**（サブスクなし。Windows・macOS・iOS）。`.vbo`を読む（**検索の要約のみ**。公式ページは開けず）
  https://vboxmotorsport.co.uk/en/circuit-tools
- 他社の機器の`.vbo`がCircuit Toolsで全部の機能つきで開けるかは**未確認**。コースはRaceLogicのコースの一覧から自動で当てる作りで、
  一覧に無いコースでも落ちないようにした、という更新の記録がある（＝開けるが、自動のコース判定は効かないことがある）
- 注意：`[column names]`の短い名前と`[header]`の名前が違うとCircuit Toolsが困ることがある、というRaceChronoのフォーラムの話（**検索の要約のみ**）。同じ名前にしておく
  https://racechrono.com/forum/discussion/comment/12992/
- **2026-11-14 実測（Circuit Tools 3 v3.2.120）**：自作の`.vbo`は開けて、周の比べもできる。ただし**衛星数の列は31までに抑える**（32の行は使われず、Delta-T・セクター・コース図が崩れる）。
  「not a genuine Racelogic VBOX file」で閉じるのは2周目以降の動画を開くときだけ。距離は速度の列から出す。行は10Hzにする（20Hzだと距離を約1.5倍に数える）。
  RaceChrono Pro の書き出しは`[laptiming]`の線を「経度 緯度 経度 緯度」の順で書いていた（上の説明と順が逆。Circuit Tools 3はそれで読めている）

### 4-2. AiM（Race Studio 3）

- Race Studio 3 Analysis が読むのはAiMの`.xrk`など自社の形式。ゲームのデータを取り込む口はある（販売店の説明）
  https://www.aimshop.com/pages/race-studio-analysis-3-export-import-data-files
- **他社のロガーのCSVを取り込む公式の口は見つからなかった**（公式の説明書のページは開けず。**未確認**）
- `.xrk`を自前で書く実装も見つからなかった → **候補から外す**

### 4-3. RaceChrono

- 取り込みは**`.vbo`がおすすめ**と開発者側が答えている（CSVは決まった形が無いので取り込みを作りにくい、という理由）。
  `.vbo`の取り込みには、向き・速度・緯度・経度が最低限要る。加速度の列は無視され、GPSから計算し直される（フォーラム。**検索の要約のみ**）
  https://racechrono.com/forum/discussion/2408/custom-data-import
- `.vbo`の追加のチャンネルは、iOS版で取り込めるようになったという更新の記録がある（Android版は**未確認**）
  https://racechrono.com/?p=2025
- 取り込みに有料版（Pro）が要るかは**未確認**
- → **`.vbo`を作れば、スマホでも見られる**

### 4-4. RaceRender（動画に計器を重ねる）

- **CSVの書式を公式に公開**している。列の名前の決まりがある：`Time`（必須）、`Longitude`・`Latitude`（度の小数）、`Altitude`、`KPH`、`Heading`、`Lap`（周の番号）、`RPM`、`Throttle`、`X`・`Y`（前後・横のG）、`GPS_Update` など。ほかの列は自由に足せる
  https://racerender.com/Developer/DataFormat.html
- `.vbo`も読む（「ふつうの書き方の`.vbo`ならたいてい読める」）
  https://racerender.com/RR3/docs/TechInfo.html
- 無料版の制限は**未確認**。解析というより、動画づくりの道具

### 4-5. Telemetry Overlay（動画に計器を重ねる）

- 有料（買い切り。公式ページの表示は199ドル。試用版あり・制限は**未確認**）
- 読めるもの：GPX・NMEA・VBOX・AiMのCSV・RaceChronoのCSV など。地図とラップに対応。自前のCSVも読めるとされるが、列の決まりは**未確認**（説明書のPDFを読めなかった）
  https://goprotelemetryextractor.com/telemetry-overlay-gps-video-sensors

### 4-6. Track Attack

- 公式の対応形式の一覧は見つからなかった（**未確認**）
- 利用者の話では、`.vbo`の取り込みに対応（2019年〜）、RaceCaptureのログも取り込んでコースを当ててラップを切る。無料版は1回25分・10回まで
  https://rennlist.com/forums/gt4-spyder/1133718-track-attack-supports-track-precision-app.html ／ https://www.hpacademy.com/forum/data-analysis-fundamentals/show/racecapture/

### 4-7. Podium（Autosport Labs）

- こちらはすでにRaceCapture互換で、Podiumへはライブで送っている（`EcoCapture-Web/podium.py`）。ただし公式のPodiumへ直接送る道は外すと決まっている（SP-9-4）
- あとからログのファイルを上げる口もある（RaceCaptureのログの形。上限100 MBという利用者の話、ラップが入っていないログは出てこないというスタッフの回答）。
  ファイルの形の公式の説明は見つからなかった（**未確認**）
  https://direct.forum.autosportlabs.com/viewtopic.php?p=23088 ／ https://direct.forum.autosportlabs.com/viewtopic.php?p=26634
- → 新しく作る必要は薄い

### 4-8. ASAM MDF4（`.mf4`、asammdf）

- 自動車の計測の標準の形。Pythonの`asammdf`（LGPL）で書ける。同じ`asammdf`の画面（無料）でグラフとGPSの地図が出る
  https://asammdf.readthedocs.io/en/master/gui.html ／ https://www.csselectronics.com/pages/asammdf-gui-api-mdf4-mf4
- **ラップの考え方が無い**（周ごとの重ね合わせ・タイムの差は出ない）。レースの解析には向かない
- → CANの生の記録を残す・量産車の計測の道具で開く、という用事が出たとき用

### 4-9. 汎用CSV

- どのソフトでも「そのまま」は開けない（列の名前・時刻の形・緯度経度の形がソフトごとに違う）。Excel・Pythonで見る用
- すでに本体のCSVと`race_analysis.py`の表があるので、新しく作るものはない

### 4-10. 参考：無料で開ける解析ソフト（TrackDataAnalysis）

- 有志の解析ソフト（MIT・無料、Windows・Mac・Linux）。**MoTeCの`.ld`、RaceLogicのVBOX、Autosport Labs（RaceCapture）の`.LOG`、AiMの`.xrk`**などを直接読む。
  周の重ね合わせ・タイムの差・GPSの地図・動画の同期がある
  https://github.com/racer-coder/TrackDataAnalysis
- i2の使用条件が気になる場合の逃げ道にもなる（`.ld`を書いてもi2以外で開ける）

---

## 5. 比べた表

| 形式 | 開くソフト | 仕様は公開か | 自前で書けるか | 無料で開けるか | ラップ | 地図 | 作る手間 |
|---|---|---|---|---|---|---|---|
| **`.vbo`** | Circuit Tools、RaceChrono、RaceRender、Telemetry Overlay、Track Attack、TrackDataAnalysis | **公開**（公式） | 書ける（テキスト） | Circuit Toolsは無料 | ○（線をファイルに書ける） | ○ | 小 |
| **`.ld`＋`.ldx`** | MoTeC i2、TrackDataAnalysis | 非公開（有志の解析） | 書けそう（有志の実装あり。GPSの64ビットは自前で足す） | i2はダウンロードできる。Pro用の印つきなら追加ライセンスなしという説明（こちらでは未確認）。使用条件は要確認 | ○（`.ldx`のビーコン） | ○（i2の中でGPSから作る） | 中 |
| MoTeCのCSV | MoTeC i2 Pro | 非公開（i2の書き出しが手本） | 書ける | **×（取り込みに1年ごとの有料ライセンス）** | ○ | ○ | 小〜中 |
| AiM `.xrk` | Race Studio 3 | 非公開 | 実装が見つからない | ソフトは無料 | — | — | 対象外 |
| RaceRender向けCSV | RaceRender | **公開**（公式） | 書ける | 無料版の制限は未確認 | ○（`Lap`の列） | ○ | 小 |
| MDF4 `.mf4` | asammdf、Vector・ETASなどの計測の道具 | 標準（ASAM） | 書ける（asammdf） | asammdfは無料 | ×（ラップの考え方なし） | △（位置を出すだけ） | 小 |
| 汎用CSV | Excel・Python | — | 済み | ○ | × | × | なし |

---

## 6. おすすめの順と理由

### まず作るもの：`.vbo`

- 仕様が公式に公開されていて、**当てずっぽうの部分が無い**（確かめがしやすい）
- テキストなので、うまく開けないときに中を目で見て直せる
- 1つ作れば、**無料のCircuit Tools・スマホのRaceChrono・動画のRaceRender／Telemetry Overlay** と、開けるソフトがいちばん多い
- ラップの線（コントロールライン）をファイルに入れられるので、「ラインを変えたらどの画面も同じに変わる」（`SPEC.md` T-5）と合わせやすい
- `.ld`を作るときに要る下ごしらえ（一定の間隔へ並べ直す・単位をそろえる・ラップの区切りの時刻を出す）が、そのまま使い回せる

### 次に作るもの：`.ld`＋`.ldx`（ユーザーの第一希望）

- 書けそうだが、**形式が非公開で、実物で試して直す回数が読めない**。先に`.vbo`で下ごしらえを固めてから着手するほうが早い
- 作る順：(a) 少ないチャンネル（時刻・速度・回転数）だけの`.ld`を作ってi2で開くか見る → (b) `.ldx`でラップが切れるか見る →
  (c) GPSを64ビットで書いてコース図が作れるか見る → (d) 全チャンネル
- (a)の時点で i2 Standard・i2 Pro のどちらで開くかが分かる。**開かなければここでやめて、`.vbo`だけにする**という逃げ道がある

### 作らなくてよさそうなもの

- MoTeCのCSV（有料ライセンスが要る）、AiM（口が無い）、汎用CSV（もうある）
- MDF4・RaceRender向けCSVは、要る場面が出たら（手間は小さい）

---

## 7. 残っている「未確認」

| 何が | どう確かめるか |
|---|---|
| Pro用の印つきの自作`.ld`が i2 Standard／i2 Pro（現行の1.1.6）で本当に開くか | 6章の(a)。小さい`.ld`を1つ作って開く |
| 自作ロガーのデータをi2で使うことが、今の使用許諾で認められるか | i2を入れるときの使用許諾を読む。はっきりしなければ代理店に聞く |
| i2 Standard／Pro のダウンロードが無料か・登録が要るか | MoTeCのダウンロードのページを人が開いて見る |
| GPSを32ビットで書いたときにi2のコース図がどのくらい粗くなるか、64ビットで書けるか | 6章の(c) |
| セクターを`.ldx`に書けるか | i2で区間を切った`.ldx`を見て比べる |
| 他社の`.vbo`がCircuit Toolsで全機能つきで開くか（コースが一覧に無いときの動き） | `.vbo`を1つ作って開く |
| RaceChrono（Android）で`.vbo`の追加のチャンネルが出るか、有料版が要るか | 同上 |
| Telemetry Overlay・Track Attack の対応形式の正式な一覧 | 使うと決まったら公式の説明書を読む |
| sim-to-motec・MotecLogGenerator のライセンス | リポジトリのLICENSEを見る（手本にするなら） |
| 本体のCSVの間隔（Hz） | 作るときに実物で見る |

---

## 8. ユーザーが決めること

1. **どのソフトを持っているか・入れられるか**：MoTeC i2 は Standard か Pro か（もう入っているか、これから入れるか）。
   Circuit Tools（無料）を入れて使う気があるか
2. **誰が見るか**：自分だけか、チームにも配るか。配るなら、相手が無料で開けるソフト（Circuit Tools・RaceChrono・TrackDataAnalysis）に合わせるほうが楽
3. **i2の使用条件をどう扱うか**：個人で見るだけにするか、代理店に聞くか。公開のリポジトリに`.ld`の書き出しを載せるか
4. **GPLの実装を手本にしてよいか**：ldparser（GPL-3.0）を取り込むか、形式の知識だけ借りて自前で書くか
5. **動画に計器を重ねる用事があるか**：あるなら RaceRender／Telemetry Overlay も視野に入る（`.vbo`で足りる見込み）。焼き込み録画がすでにあるので優先は低そう
6. **書き出す単位**：走行1回を1ファイルにするか、スティントごと・周ごとに分けるか
7. **電圧のままの列（油圧など）**：物理量へ直して出すか、電圧のまま出すか
8. **おすすめの順（`.vbo` → `.ld`）でよいか**、第一希望の`.ld`を先にするか
