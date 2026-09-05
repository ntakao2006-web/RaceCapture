# NCロードスター（NCEC）実車CAN/OBD解析 現地手順書（1時間）

> **目的**：自作CANトランシーバ回路（XIAO ESP32C3 + MCP2562FD）をNCECのOBD2ポートへ直結し、
> **①停車中の操作差分（2-4-3／2-4-4）** と **②走行中の相関検証（2-4-5）** を
> **1本のキャプチャ・1つの時間軸**で取り切る。
>
> **対象車両**：NCロードスター（NCEC、2005年式初期型、MT、DSC非搭載）＝**本プロジェクトの本番投入車両**。
>
> **なぜこの車が本命か**：MAZDA2はDLCがスタブ構成（診断応答のみ）、レクサスUXはゲートウェイ隔離で
> 非診断IDが固定値2種のみ。**3車両のうち生CANが実際に流れているのはNCECだけ**であることが
> 実測で確定している（`vehicle_can_survey_summary.md`）。生CAN逆解析ができる唯一の車両。
>
> **記録先**：`ncec_run1` プレフィックスの新規ファイルに限定する。既存の
> `obd2_survey_nc_roadster*`・`mazda2_*`・`lexus_ux_*` は**一切上書きしない**。

---

## 0. この1時間で何を取りに行くのか

2026-08-01のELM327調査（`OBD2_SURVEY.md`）で、NCECには次の状態まで来ている。

| 区分 | CAN ID | 状況 |
|---|---|---|
| デコード式まで判明・実測検証済み | `200` `201` `215` `231` `240` `4B0` | 今回は**フルスピード＋µsタイムスタンプで裏取り**する |
| 警告灯関連らしいが割当不明 | `211` `212` | 今回の**操作差分で当てに行く** |
| 完全に未解明 | `21A` `39A` `420` `4EC` `4FF` | 同上。特に`21A`/`39A`は**全27サンプル常時ゼロ**で、「低頻度イベント系フラグ（パーキングブレーキ・ドア・シートベルト等）」という仮説がある。**今回はその仮説を直接叩きに行く**（ドア／シートベルト／サイドブレーキを操作リストに入れた理由） |

ELM327では **UART 38400bps が CAN 500kbps に追いつかず `BUFFER FULL` 頻発・タイムスタンプ無し**
だったため、これ以上は進めなかった。今回はハードウェアCANコントローラで取り切る。

**自作側の未検証項目はもう無い**。MAZDA2（74秒、欠落0）とレクサスUX（61分、drop=0・buserr=0）で
回路・ハーネス・ファーム・USB経路・`--phase-plan`の自動進行はすべて実車実証済み。
今回は**繋いで回すだけ**であり、切り分け作業は残っていない。

---

## 1. 家でやっておくこと（15分）

### 1-1. ファームウェアの確認（多くの場合、書き込み不要）

基板には **2026-09-05のレクサスUX調査時点で `can_obd_logger` が書き込まれている**。
その後ファーム側の変更はないので、**基板を触っていなければ再書き込みは不要**。
別PCへ繋ぎ替えた・別ファーム（`can_logger` / `can_selftest`）を焼いた覚えがある場合だけ、次を実行する。

```bash
cd firmware/can_obd_logger && python -m platformio run -e esp32-c3-can-obd-logger -t upload
```

> **`-e esp32-c3-can-obd-logger-bench` を焼かないこと**（`TWAI_MODE_NO_ACK`の卓上専用ビルド。実車禁止）。
> 送信するのは **OBD2 mode 01（読み取り）とACKだけ**。DTC消去・アクチュエータ制御は含まない。
>
> PIDテーブルはUX調査時に拡張済みで、NCECが対応しない `5C`（油温）等は
> 自動バックオフで間隔が最大64倍まで伸びるため、対応PIDのレートを食わない。**NCEC向けの改造は不要**。

### 1-2. 卓上リハーサル（CAN未接続でよい・2分）

```bash
python can_capture_logger.py --port COM5 --out rehearsal --limit-seconds 25 --phase-plan "0:poll:t_poll,10:passive:t_passive,20:poll:t_resume"
```

`rehearsal.status.log` に次の3つが並んでいれば合格。

- `# host: phase ... action=passive key=p label=t_passive`
- その直後の `# obd polling PAUSED (passive; ACK is still sent)`
- 20秒後の `# obd polling RESUMED`

通らない場合はまず `--port` を疑う（ポート番号違いでも「接続待ち」で静かに待つだけなので気づきにくい）。

> 卓上では `txerr`・`buserr` が増え続けるが**これは正常**（ACKを返す相手がいないだけ）。実車では0になる。

### 1-3. 持ち物・設定チェックリスト

- [ ] ESP32-C3基板 + OBD2ハーネス（6=CANH / 14=CANL / 5=GND）
- [ ] **卓上検証用の120Ω終端を外したこと**（車両バスは両端終端済み。付けたままだと三重終端）
- [ ] ノートPC（残量50%以上）＋ USBケーブル（**運転中に抜けないよう養生テープで固定**）
- [ ] **PCのスリープ無効化**（「電源とスリープ」を「なし」、蓋を閉じる動作も「何もしない」）
- [ ] **空き容量2GB以上**。NCECは生CANが本当に流れるため、レクサスUX（61分で37MB）より**大きくなる**。
      300〜600 frame/s なら1時間で**100〜200MB**程度の見込み
- [ ] **PCの画面が運転席から見える置き方**（停車中の操作ブロックでラベル表示を見ながら操作するため）
- [ ] 基板・ケーブルを**ペダル周り／ステアリング下に垂らさない**
- [ ] この手順書の「2-2. 停車ブロック」の表を印刷するかスマホに表示しておく

---

## 2. 現地タイムスケジュール（60分）

キャプチャ開始を `t=0` とする。**前半13分は停車したまま画面を見て操作、後半は完全放置**。

### 2-1. 実行コマンド（プランA：60分・推奨）

**IG ONにする直前**にこの1行を実行する。

```bash
python can_capture_logger.py --port COM5 --out ncec_run1 --limit-seconds 3660 --phase-plan "0:passive:ig_on,60:passive:engine_idle,150:passive:ops_base,240:passive:ops_blinker_l,280:passive:ops_blinker_r,320:passive:ops_hazard,360:passive:ops_headlight,400:passive:ops_wiper,440:passive:ops_brake,480:passive:ops_clutch,520:passive:ops_door,560:passive:ops_seatbelt,600:passive:ops_defog,640:passive:ops_ac,680:passive:ops_pbrake,720:passive:ops_base2,780:poll:idle_obd,900:poll:rev_obd,1020:poll:drive,3120:passive:drive_passive,3420:poll:stop_idle"
```

### 2-2. 前半（0:00〜13:00）＝停車ブロック。画面を見ながら操作する

**平坦な場所に停車し、サイドブレーキを引き、ニュートラルにしてから始める。**

| 経過 | ラベル | 運転者の操作 | 狙い |
|---|---|---|---|
| 0:00 | `ig_on` | **IG ON（エンジンはかけない）**、何も触らず待つ | エンジン停止時の自発フレーム |
| 1:00 | `engine_idle` | **エンジン始動**、何も触らず待つ | 始動で増えるID＝パワトレ系の絞り込み |
| 2:30 | `ops_base` | **全OFFの基準状態**でじっと待つ（90秒） | 操作差分のベースライン |
| 4:00 | `ops_blinker_l` | 左ウィンカーON | `211`/`212`候補 |
| 4:40 | `ops_blinker_r` | 右ウィンカーON | 同上（左右でビットが分かれるか） |
| 5:20 | `ops_hazard` | ハザードON | 同上 |
| 6:00 | `ops_headlight` | ライトON（スモール→ロービーム） | 同上 |
| 6:40 | `ops_wiper` | ワイパー作動 | 同上 |
| 7:20 | `ops_brake` | ブレーキペダルを踏み続ける | ブレーキランプ／`212`候補 |
| 8:00 | `ops_clutch` | **クラッチペダルを踏み続ける** | **`231`＝クラッチSWの答え合わせ（陽性対照）** |
| 8:40 | `ops_door` | 運転席ドアを開けて保持 | **`21A`/`39A`の仮説検証** |
| 9:20 | `ops_seatbelt` | ドアを閉め、シートベルトを外して保持 | 同上 |
| 10:00 | `ops_defog` | ベルトを戻し、リアデフォッガON | 同上 |
| 10:40 | `ops_ac` | デフォッガOFF、エアコン（A/C＋ブロワ）ON | 同上 |
| 11:20 | `ops_pbrake` | **ブレーキペダルを踏んだまま**サイドブレーキを下ろす | 同上 |
| 12:00 | `ops_base2` | **サイドを引き直し、全てOFFへ戻す**（60秒） | 基準の再現性確認 |

**操作のルール（これだけ守れば解析が通る）**

1. **画面に次のラベルが出た瞬間に、前の操作をOFF・次の操作をONにする**。
2. **同時に2つ操作しない**。指定されたもの以外は全てOFFに戻してから次へ。
3. 40秒ぶんまるまる保持する。早く戻さない。
4. 数秒ずれても問題ない（解析側で `--skip-head` により境界を捨てる）。**操作を飛ばした・順番を間違えた場合は、
   その場でメモを取る**（後で該当フェーズを解析から外せば済む）。

> **`ops_clutch` を入れてある理由**：`0x231`＝クラッチスイッチはコミュニティ資料で既知。
> ここが差分に出れば「この手法はこの車で機能している」と言い切れ、出なければ他の所見も疑ってよい、
> という**陽性対照**になる。最初に見るのはこれ。

> **`ops_pbrake` の安全条件**：必ず**平坦な場所・ニュートラル・ブレーキペダルを踏んだまま**行う。
> 少しでも傾斜があると感じたら**このフェーズは飛ばしてよい**（画面のラベルが進むのを待つだけ）。

### 2-3. 後半（13:00〜60:00）＝放置。運転に専念する

| 経過 | ラベル | ロガー | 運転者の行動 | 得るもの |
|---|---|---|---|---|
| 13:00 | `idle_obd` | OBDポーリング | 停車のまま待つ（120秒） | **OBD疎通確認**と静止時の基準値 |
| 15:00 | `rev_obd` | OBDポーリング | **ニュートラルのまま空ぶかし**を数回（2,000〜4,000rpmを2〜3秒ずつ、120秒） | **走らなくても回転数の相関が取れる**保険 |
| 17:00 | `drive` | OBDポーリング | **走行**（PCに一切触らない） | 本命。車速・回転数と生CANの相関 |
| 52:00 | `drive_passive` | 受動 | 走行を続ける | 自分の送信を止めた**純粋な生CANレート**と取りこぼし量 |
| 57:00 | `stop_idle` | OBDポーリング | 停車・アイドル | 終端の基準値 |
| 60:00 | 自動停止 | — | Ctrl+Cは押さなくてよい | — |

走行の中身は普段どおりでよいが、**発進・停止・高めの速度域が一度ずつ入る**と相関の精度が上がる。

### 2-4. 13:00時点の1回だけのチェック（`idle_obd` へ移ったとき）

停車中なので、ここで画面を1度だけ確認する。以後は見ない。

| 画面の様子 | 意味 | 対応 |
|---|---|---|
| 行が猛烈に流れ、`# stat ... total=` が伸び続ける | **正常。生CANが取れている** | そのまま |
| `total=` がOBD往復ぶんしか増えない | 生CANが来ていない（前半の操作差分は空振り） | そのまま最後まで回す。OBDログとして完結させる |
| `drop_rb` / `rx_missed` が増え続ける | USB出力が受信レートに追いつかず取りこぼし中 | **対応不要**。取りこぼし量はログに残るので後で定量評価する |
| `[!] シリアルが切断されました` の繰り返し | USBの接触不良 | **安全な場所に停車してから**挿し直す（自動再開する） |

**走行中にやってはいけないこと**：キーボード操作、コネクタの抜き差し、Ctrl+Cでの停止。

---

## 3. プランB（走行時間が取れない場合・31分）

停車ブロックと空ぶかしはそのまま、走行を10分に縮めた版。**前半13分の成果は同じ**。

```bash
python can_capture_logger.py --port COM5 --out ncec_run1 --limit-seconds 1860 --phase-plan "0:passive:ig_on,60:passive:engine_idle,150:passive:ops_base,240:passive:ops_blinker_l,280:passive:ops_blinker_r,320:passive:ops_hazard,360:passive:ops_headlight,400:passive:ops_wiper,440:passive:ops_brake,480:passive:ops_clutch,520:passive:ops_door,560:passive:ops_seatbelt,600:passive:ops_defog,640:passive:ops_ac,680:passive:ops_pbrake,720:passive:ops_base2,780:poll:idle_obd,900:poll:rev_obd,1020:poll:drive,1620:passive:drive_passive,1740:poll:stop_idle"
```

フェーズ番号（`p1`〜`p21`）とラベルはプランAと完全に同じなので、**4章の解析コマンドはそのまま使える**。

---

## 4. 帰宅後の解析手順

### 4-1. フェーズごとに切り分ける（まずこれ）

```bash
python can_split_phases.py --capture ncec_run1
```

フェーズ別のフレーム数・ID数・レートが一覧で出る。**この一覧が今回の一次成果**。
`p1_ig_on`〜`p16_ops_base2` に多数のIDが並んでいれば、生CANが取れている＝以降の解析が全部成立する。

### 4-2. 操作差分（2-4-3／2-4-4の本体）

自分が出したOBD往復（`7E0`/`7E8`）を落とし、フェーズ境界の前後も捨ててから分割する。

```bash
python can_split_phases.py --capture ncec_run1 --exclude-ids 7E0,7E8 --skip-head 5 --skip-tail 2 --suffix _nx
```

> `--skip-head 5` は「画面のラベルを見てから手を動かすまでの遅れ」で区間の頭に混ざる
> 前の操作のフレームを捨てるため。これが混ざると、本来 STRONG（固定値A→固定値B）で出る所見が
> MEDIUM（複数値化）へ落ちて見落としやすくなる。

続けて、ベースライン1本と操作12本をまとめて1回で比較する。

```bash
python can_diff.py --base ncec_run1_p3_ops_base_nx.csv --test ncec_run1_p4_ops_blinker_l_nx.csv --test ncec_run1_p5_ops_blinker_r_nx.csv --test ncec_run1_p6_ops_hazard_nx.csv --test ncec_run1_p7_ops_headlight_nx.csv --test ncec_run1_p8_ops_wiper_nx.csv --test ncec_run1_p9_ops_brake_nx.csv --test ncec_run1_p10_ops_clutch_nx.csv --test ncec_run1_p11_ops_door_nx.csv --test ncec_run1_p12_ops_seatbelt_nx.csv --test ncec_run1_p13_ops_defog_nx.csv --test ncec_run1_p14_ops_ac_nx.csv --test ncec_run1_p15_ops_pbrake_nx.csv
```

**読み方**

1. **まず `p10_ops_clutch` の結果に `0x231` が出ているかを見る**（陽性対照）。出ていれば手法が機能している。
2. `STRONG` = ベースで固定値A→操作中に固定値B。**これが本命**。
3. `MEDIUM` = 固定だったバイトが複数値化。操作タイミングのずれで STRONG から落ちたものが混じる。
4. `counter` = 両方で値種類が多いローリングカウンタ疑い（`0x211`末尾・`0x420`byte0が該当するはず）。**無視してよい**。
5. 全操作で同じIDのバイトが動いていたら、それは操作と無関係の時間変動。**`p16_ops_base2` をtestにした差分**
   （＝何も操作していない区間同士）を取り、そこにも出るなら偽陽性と判定する。

```bash
python can_diff.py --base ncec_run1_p3_ops_base_nx.csv --test ncec_run1_p16_ops_base2_nx.csv
```

エンジン始動で現れるIDも見ておく。

```bash
python can_diff.py --base ncec_run1_p1_ig_on_nx.csv --test ncec_run1_p2_engine_idle_nx.csv
```

### 4-3. OBD2応答を基準値の時系列へ変換する

```bash
python can_obd_extract.py --can ncec_run1.csv --list
```

```bash
python can_obd_extract.py --can ncec_run1.csv --out ncec_run1_ref
```

`ncec_run1_ref_0D_speed.csv` / `..._0C_rpm.csv` / `..._11_throttle.csv` / `..._05_coolant.csv` などが出る。
NCECは油温PID `5C` 非対応なので、`5C` のファイルは出ない（想定どおり）。

### 4-4. 生CANと基準値の相関（2-4-5の本体）

同一基板・同一 `esp_timer` のタイムスタンプなので **`--time-offset` / `--auto-lag` は不要**。

```bash
python can_correlate.py --can ncec_run1_p19_drive.csv --ref ncec_run1_ref_0D_speed.csv --ref-name speed_kmh --ref-time-unit us --top 20
```

```bash
python can_correlate.py --can ncec_run1_p19_drive.csv --ref ncec_run1_ref_0C_rpm.csv --ref-name rpm --ref-time-unit us --top 20
```

```bash
python can_correlate.py --can ncec_run1_p19_drive.csv --ref ncec_run1_ref_11_throttle.csv --ref-name throttle --ref-time-unit us --top 20
```

```bash
python can_correlate.py --can ncec_run1_p18_rev_obd.csv --ref ncec_run1_ref_0C_rpm.csv --ref-name rpm --ref-time-unit us --top 20
```

**期待する答え**（ここまでは既知。合っていれば手法とデータの妥当性が確認できる）

| 基準値 | 出るはずの候補 | 期待する式 |
|---|---|---|
| 車速 | `0x201` offset4/width2/big、`0x4B0` の4つの2バイト | `slope≈0.01, intercept≈-100`（100km/hオフセット） |
| 回転数 | `0x201` offset0/width2/big | `slope≈0.25`（`raw/4`） |
| スロットル | `0x200` offset7 / `0x215` offset6 / `0x240` offset3 | `slope≈100/255≈0.392` |
| 水温 | `0x240` offset1 | `slope≈1, intercept≈-40` |

R²が0.95を超えれば特定できたと見てよい。**既知の6IDが期待どおり出たあと、
上位に残った未知IDのバイト**（`21A`/`39A`/`420`/`4EC`/`4FF`）が今回の新規成果になる。

`0x7E8` 自身も上位に並ぶが基準値の出所なので自明な自己一致。無視するか `--candidate-id` で絞る。

### 4-5. 取りこぼしと生CANレートの評価

```bash
grep "drop_rb" ncec_run1.status.log | tail -5
```

`p20_drive_passive`（自分の送信を止めた5分間）のレートが `p19_drive` より明確に高ければ、
**OBDポーリングがUSB帯域を圧迫していた**ということ。次回は受動主体の構成に変える判断材料になる。

---

## 5. 安全・禁止事項

- **走行中にPCを操作しない。** そのために `--phase-plan` を使っている。
- **停車中の操作は、平坦な場所・ニュートラル・サイドブレーキで行う**（`ops_pbrake` のみ足でブレーキ保持）。
- **OBDの3番・11番ピンには触らない。** NCECはHS-CANが6/14。
  **6番と3番、14番と11番を導通させない**（MS-CANとの2系統直結はバスオフを招き、車両側の警告灯・DTC・
  フェイルセーフを引き起こす）。
- **卓上の120Ω終端を外したことを、繋ぐ前にもう一度確認する。**
- `can_selftest`（NO_ACKモード）と `-bench` ビルドを実車バスへ繋がない。
- OBD2は **mode 01（読み取り）のみ**。DTC消去・アクチュエータ制御は行わない。
- **VIN（mode 09 PID 02）は取得しない**（PIDテーブルにも入れていない）。
- ログをコミットする前に、車台番号等の個人特定情報が含まれていないことを確認する。

### 補足：受動フェーズでもACKは返る

2-4-3では「操作差分は完全受動の `can_logger` で採ること」としていたが、その理由は
**自分が投げた `7E0` とECUの `7E8` 応答が `can_diff.py` にID出現／消滅として拾われるため**だった。
今回は `can_obd_logger` の `passive` フェーズ（`p`キーでポーリング停止）を使うので、
**操作ブロックの間 `7E0`/`7E8` は1本も出ない**＝同じ目的を満たす。
`4-2` の `--exclude-ids 7E0,7E8` は保険。

こうすることで**現地でのファーム焼き直しが不要**になり、操作差分と走行相関が
**同一ファイル・同一時間軸**に載る（別ファームで2本撮ると時間軸が分かれる）。
ただしACKは返るので「バスに一切影響しない」ではない点は明記しておく（MAZDA2・UXで実車実証済みの構成）。

---

## 6. 記録するファイル

| ファイル | 内容 |
|---|---|
| `ncec_run1.csv` | 生CAN＋OBD応答の全フレーム（`host_iso,t_us,can_id,ext,rtr,dlc,data_hex`） |
| `ncec_run1.status.log` | ステータス行とフェーズ区切り（`# host: phase ...`） |
| `ncec_run1_p*_*.csv` | フェーズ別に切り分けたもの |
| `ncec_run1_p*_*_nx.csv` | 操作差分用（`7E0`/`7E8`除外・境界カット済み） |
| `ncec_run1_ref_*.csv` | OBD2応答から起こした基準値の時系列 |

> 生ログ本体（`.csv`／`.jsonl`）は**リポジトリに含めない**方針（`.gitignore`済み）。
> リポジトリへ入れるのは解析結果とサマリ、および `status.log` まで。
