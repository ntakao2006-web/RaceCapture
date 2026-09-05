# レクサスUX 実車CAN解析 現地手順書（1時間・無人運用）

> **目的**：自作CANトランシーバ回路（XIAO ESP32C3 + MCP2562FD）をレクサスUXのOBD2ポートへ
> 直結し、**生CANフレームとOBD2応答を同一タイムスタンプで1時間ぶん取り切る**。
> 帰宅後に `can_correlate.py` へかけて「どのCAN IDのどのバイトが車速・回転数か」を特定する。
>
> **対象車両**：レクサスUX（2022年式、マイナーチェンジ後・タッチパネル仕様）。
> **運用方針**：ユーザーは運転に専念する。走行中はPCに一切触らない。
> 計測メニューの進行は `can_capture_logger.py --phase-plan` がホスト側のタイマーで自動実行する。
>
> **記録先**：`lexus_ux_` プレフィックスの新規ファイルに限定する。
> NCロードスター（`obd2_survey_nc_roadster*`・`OBD2_SURVEY.md`本体）と
> MAZDA2（`mazda2_*`）の既存ファイルは**一切上書きしない**。

---

## 0. この調査が「1時間で終わる」と言い切れる根拠

前回のMAZDA2実車2回目（2026-09-02）で、**自作側の未検証項目は全て潰れている**。

| 項目 | 結果 | 根拠ファイル |
|---|---|---|
| 回路・ハーネス・ファーム | **実車で完動** | `mazda2_b1_obd_idle.status.log`（`sent=resp`、`buserr=0`、`tec=rec=0`、74秒連続） |
| OBD2ポーリング | **rpm/speed/coolant/throttleを実測** | 同上（`rpm=751 coolant=88 throttle=13`） |
| 生CANの受動キャプチャ | MAZDA2のDLCは**スタブ構成**（診断応答以外を出さない） | `mazda2_b1_obd_idle.csv` の全5794行が `0x7E0`/`0x7E8` のみ |

つまり今回は**接続して回すだけ**であり、切り分け作業は残っていない。
また、レクサスUXについては 2-0-6 のELM327調査（`OBD2_SURVEY.md`）で

- OBD2は **ISO 15765-4 CAN (11bit, 500kbps)**、標準PIDに31項目対応（`5C` 油温を含む）
- `ATMA` で **`4E0`（34620回）・`45A`・`623`・`70C`** を観測

が分かっている。**MAZDA2と違い、UXのDLCには自発フレームが確かに流れている**。
ELM327ではUART律速で4種しか拾えなかったものを、今回ハードウェアCANコントローラで取り切る。

---

## 1. 家でやっておくこと（前日〜出発前、15分）

> **2026-09-05に 1-1・1-2 は実施済み**（COM5のESP32-C3へ書き込み、卓上リハーサル合格）。
> 次に車へ持ち出すときは **1-3 のチェックリストだけ**を確認すればよい。
> ただし基板を別のPCへ繋ぎ替えた・ファームを焼き直した場合は 1-2 をもう一度やること。

### 1-1. ファームウェアの書き込み

```bash
cd firmware/can_obd_logger && python -m platformio run -e esp32-c3-can-obd-logger -t upload
```

> `can_obd_logger` は `TWAI_MODE_NORMAL`（送信あり）。送るのは **OBD2 mode 01（読み取り専用）**と
> 受信フレームへのACKだけで、車両設定を書き換えるコマンドは一切含まない。
>
> **PIDテーブルはUX向けに拡張済み**（2026-09-05）。既存の14項目に加え、UXで応答を確認済みの
> `5C`（油温）・`47`・`4C`・`43`・`44`・`34`・`1F` を追加した。未対応PIDは自動バックオフで
> 間隔が最大64倍まで伸びるため、他車種で使っても既存PIDのレートは食わない。

### 1-2. 卓上リハーサル（CAN未接続のままでよい・所要2分）

**フェーズ自動切替が効くことを、車に乗る前に必ず確認する。**

```bash
python can_capture_logger.py --port COM5 --out rehearsal --limit-seconds 25 --phase-plan "0:poll:t_poll,10:passive:t_passive,20:poll:t_resume"
```

確認する点（`rehearsal.status.log` を開く）：

- `# host: phase ... action=passive key=p label=t_passive` が書かれている
- その直後に ESP32 側の応答 `# obd polling PAUSED (passive; ACK is still sent)` がある
- 20秒後に `# obd polling RESUMED` がある

ここが通れば、走行中の自動進行は確実に動く。**通らなければCOMポート番号を疑う**
（`--port` を間違えていても「接続待ち」で静かに待つだけなので気づきにくい）。

**2026-09-05の実測（合格例）**：`p` 送出から `# obd polling PAUSED` まで約210ms、
`r` で `RESUMED`。ポーリング停止中は `txerr` の増加が止まり（665で固定）、再開で再び増える
＝**キーがバス動作へ実際に反映されている**ことまで確認できた。

> **卓上では `txerr` と `buserr` が増え続けるが、これは正常**。CAN相手がいないためACKが
> 返らないだけで、実車では0になる（MAZDA2実車では74秒でbuserr=0・TEC=REC=0）。
> 逆に**卓上でこれが増えないほうが異常**（送信できていない）。
>
> **既知の落とし穴（対処済み）**：ESP32-C3のUSB Serial/JTAGは、ファーム側で
> `usb_serial_jtag_driver_install()` を呼んでいないとホストからの1バイトを受け取れず、
> **PC側の `write` が永久にブロックする**（＝キャプチャごと停止する）。2026-09-05に実機で
> 再現し、ファーム側は専用ドライバでの直接読み取りへ、PC側は `write_timeout` 必須＋
> `flush()` 廃止へ修正済み。**古いファームのまま走らせないこと。**

### 1-3. 持ち物と設定

- [ ] ESP32-C3基板 + OBD2ハーネス（6=CANH / 14=CANL / 5=GND）
- [ ] **卓上検証用の120Ω終端を外したこと**（車両バスは両端終端済み。付けたままだと三重終端になる）
      ※卓上リハーサルでは付けたままで構わない。**車に持ち込む直前に外す**のを忘れやすいので、ケーブルを車へ運ぶ前にここでもう一度見る
- [ ] ノートPC（残量50%以上）＋ USBケーブル（**走行中に抜けないよう養生テープ等で固定**）
- [ ] **PCのスリープを無効化**（Windowsの「電源とスリープ」を「なし」に。蓋を閉じる動作も「何もしない」）
- [ ] 空き容量：生CANが本気で流れると **1時間で200〜400MB** 程度。1GB以上空けておく
- [ ] 基板とケーブルを**ペダル周り・ステアリング下に垂らさない**（足に絡むと危険）

---

## 2. 現地タイムスケジュール（60分・完全放置）

キャプチャ開始を `t=0` とする。**運転者のアクションは「3分後にエンジン始動」「13分後に発進」の2回だけ**。

| 経過 | フェーズ | ロガー | 運転者の行動 | このフェーズで得るもの |
|---|---|---|---|---|
| 0:00 – 3:00 | `ig_on` | 受動（ポーリング停止） | **IG ON（エンジンはかけない）**、そのまま待つ | エンジン停止時の自発フレーム。ボディ系IDの基準 |
| 3:00 – 8:00 | `engine_idle` | 受動 | **エンジン始動**、停車のまま待つ | 始動で増えるID＝パワトレ系IDの絞り込み |
| 8:00 – 13:00 | `idle_obd` | OBDポーリング | 停車のまま待つ | OBD疎通確認と、静止時の基準値（rpm/水温/油温） |
| 13:00 – 50:00 | `drive` | OBDポーリング | **走行**（PCに触らない） | 本命。車速・回転数の変化と生CANの相関データ |
| 50:00 – 55:00 | `drive_passive` | 受動 | 走行を続ける | 自分の送信を止めた**純粋な生CANレート**と取りこぼし量の実測 |
| 55:00 – 60:00 | `stop_idle` | OBDポーリング | 停車・アイドル（またはEV走行/停車） | ハイブリッド挙動（エンジン停止時のPID応答）の確認 |

走行の中身は普段どおりでよいが、**発進・停止・高めの速度域が一度ずつ入る**と相関の精度が上がる。
渋滞だけ・信号待ちだけ、という1時間にならなければ十分。

### 2-1. 実行コマンド（プランA：完全放置・推奨）

出発前、IG ONにする直前にこの1行を実行して、**あとは画面を見ない**。

```bash
python can_capture_logger.py --port COM5 --out lexus_ux_run1 --limit-seconds 3660 --phase-plan "0:passive:ig_on,180:passive:engine_idle,480:poll:idle_obd,780:poll:drive,3000:passive:drive_passive,3300:poll:stop_idle"
```

起動直後に、フェーズ計画の一覧と `[*] COM5 @ 115200bps を受信中...` が出る。
`--limit-seconds 3660` により**61分で自動停止**する（最後の1分は余裕）。
途中でUSBが一瞬抜けても自動再接続し、受動フェーズ中なら `p` を送り直して状態を復旧する。

### 2-2. 実行コマンド（プランB：停車中の操作差分も採る場合）

出発前の停車中に、ウィンカー等の単一操作を45秒ずつ入れる版。**画面のフェーズ表示に合わせて操作する**
（`[*] 720s フェーズ poll ops_blinker_l` のように次の操作名が表示される）。
走行時間が33分に減るぶん、こちらは操作の手間がある。

```bash
python can_capture_logger.py --port COM5 --out lexus_ux_run1 --limit-seconds 3660 --phase-plan "0:passive:ig_on,180:passive:engine_idle,480:poll:idle_obd,660:poll:ops_base,720:poll:ops_blinker_l,765:poll:ops_blinker_r,810:poll:ops_hazard,855:poll:ops_headlight,900:poll:ops_wiper,945:poll:ops_brake,990:poll:drive,3000:passive:drive_passive,3300:poll:stop_idle"
```

| 経過 | 操作 |
|---|---|
| 11:00 | `ops_base`：**全て消灯・ブレーキも離した基準状態**でじっと待つ（60秒） |
| 12:00 | 左ウィンカーON（45秒） |
| 12:45 | 右ウィンカーON（45秒） |
| 13:30 | ハザードON（45秒） |
| 14:15 | ヘッドライトON（45秒） |
| 15:00 | ワイパー作動（45秒） |
| 15:45 | ブレーキペダルを踏み続ける（45秒） |
| 16:30 | 全て戻して発進 |

> 必ず **P または N で停車したまま**行う。操作は1つずつ、他は全てOFFに戻してから次へ。

---

## 3. 走行中（原則、何もしない）

見るのは**停車したときだけ**。異常の判断は次の3点で足りる。

| 画面の様子 | 意味 | 対応 |
|---|---|---|
| 行が猛烈に流れている／`# stat ... total=` が伸び続ける | 正常。生CANが取れている | そのまま |
| `# stat` は毎秒出るが `total=` がOBD往復ぶんしか増えない | UXのDLCもスタブ構成だった | そのまま最後まで回す（OBDログとして完結する） |
| `[!] シリアルが切断されました` が繰り返される | USBの接触不良 | **安全な場所に停車してから**挿し直す（キャプチャは自動再開する） |
| `drop_rb` / `rx_missed` が増え続けている | USB出力が受信レートに追いつかず取りこぼし中 | 対応不要。取りこぼし量はログに残るので後で定量評価する |

**やってはいけないこと**：走行中のキーボード操作、コネクタの抜き差し、Ctrl+Cでの停止。

---

## 4. 帰宅後の解析手順

### 4-1. まずフェーズごとに切り分ける

```bash
python can_split_phases.py --capture lexus_ux_run1
```

フェーズ別のフレーム数・ID数・レートが一覧で出て、`lexus_ux_run1_p1_ig_on.csv` のような
ファイルが書き出される。**この一覧が今回の一次成果**であり、ここで次の判定ができる。

| `p1_ig_on` / `p2_engine_idle` の frames | 意味 | 次にやること |
|---|---|---|
| 数千〜数万（多数のID） | **生CANが取れている（期待どおり）** | 4-2以降へ進む。本命の相関検証 |
| 数十〜数百 | 低頻度IDのみ流れている | 4-2へ進む。IDが少ないぶん解析は早い |
| 0 | UXのDLCもスタブ構成だった | 生CANの逆解析は断念し、OBD2ポーリングのログとして評価する（`p3_idle_obd` 以降は有効） |

### 4-2. OBD2応答を基準値の時系列へ変換する

```bash
python can_obd_extract.py --can lexus_ux_run1.csv --list          # 含まれるPIDの確認
python can_obd_extract.py --can lexus_ux_run1.csv --out lexus_ux_run1_ref
```

`lexus_ux_run1_ref_0D_speed.csv` / `..._0C_rpm.csv` / `..._5C_oil_temp.csv` などが出る。

### 4-3. 生CANと基準値の相関をとる（本命）

走行フェーズのCSV名は 4-1 の出力で確認すること（プランAなら `lexus_ux_run1_p4_drive.csv`）。

```bash
python can_correlate.py --can lexus_ux_run1_p4_drive.csv --ref lexus_ux_run1_ref_0D_speed.csv --ref-name speed_kmh --ref-time-unit us --top 20
python can_correlate.py --can lexus_ux_run1_p4_drive.csv --ref lexus_ux_run1_ref_0C_rpm.csv  --ref-name rpm       --ref-time-unit us --top 20
```

同一基板・同一 `esp_timer` のタイムスタンプなので、**`--time-offset` / `--auto-lag` は不要**。
R²が 0.95 を超える候補が出れば、そのCAN ID・バイト位置・スケールが特定できたことになる。

### 4-4. 操作差分（プランBで採った場合）

自分が出したOBD往復を落としてから `can_diff.py` にかける。

```bash
python can_split_phases.py --capture lexus_ux_run1 --exclude-ids 7E0,7E8 --suffix _nx
python can_diff.py --base lexus_ux_run1_p4_ops_base_nx.csv --test lexus_ux_run1_p5_ops_blinker_l_nx.csv --test lexus_ux_run1_p6_ops_blinker_r_nx.csv
```

### 4-5. 取りこぼしの評価

```bash
grep "drop_rb" lexus_ux_run1.status.log | tail -5
```

`drop_rb` / `rx_missed` が増えていたら、そのぶん生CANを取り逃している。
`p5_drive_passive`（自分の送信を止めた5分間）のレートが、`p4_drive` のレートより明確に高ければ、
**OBDポーリングがUSB帯域を圧迫していた**ということなので、次回は受動主体の構成に変える。

---

## 5. 安全・禁止事項

- **走行中にPCを操作しない。** 本手順書はそのために `--phase-plan` を用意している。
- **3番/11番ピンには触らない。** UXは日本のOBD2規格どおり 6/14 が HS-CAN。
  MAZDA2手順書にある「3番/11番へ移設」はマツダ固有のMS-CAN対策であり、UXでは不要かつ危険。
- **6番と3番、14番と11番を導通させない**（2系統直結はバスオフを招く）。
- 送信するのは **OBD2 mode 01（読み取り）とAT相当の設定なし**。DTCの消去やアクチュエータ制御は行わない。
- **VIN（PID `09 02`）は取得しない。** 本手順のPIDテーブルにも含めていない（個人特定情報のため）。
- 取得したログをコミットする前に、車台番号等が含まれていないことを確認する。

---

## 6. 記録するファイル

| ファイル | 内容 |
|---|---|
| `lexus_ux_run1.csv` | 生CAN＋OBD応答の全フレーム（`host_iso,t_us,can_id,ext,rtr,dlc,data_hex`） |
| `lexus_ux_run1.status.log` | ステータス行とフェーズ区切り（`# host: phase ...`） |
| `lexus_ux_run1_p*_*.csv` | フェーズ別に切り分けたもの（`can_split_phases.py` の出力） |
| `lexus_ux_run1_ref_*.csv` | OBD2応答から起こした基準値の時系列 |

> `.csv` は大きくなるため、**リポジトリへ入れるのは解析結果とサマリまで**とし、
> 生ログ本体を置くかは容量を見てから判断する（MAZDA2の生ログは現在リポジトリ直下に置いている）。
