# MAZDA2（タイムズレンタカー）実車CAN/OBD2 現地手順書

> **目的**：自作CANトランシーバ回路（XIAO ESP32C3 + MCP2562FD）が実車で動くことを確認する。
> 「生CANが取れるか」→「OBD2応答が返るか」の順で、受動（送信なし）から段階的に上げていく。
>
> **対象車両**：MAZDA2（タイムズレンタカー、借用車）。
> **重要**：この調査結果は**MAZDA2専用のファイル**に記録する。NCロードスターの既存ファイル
> （`obd2_survey_nc_roadster*.json` / `OBD2_SURVEY.md`の該当節など）は**一切上書きしない**。
> 新規ファイルは `mazda2_` プレフィックスで作る。

---

## 手順の改訂（実車1回目の結果を受けて。こちらを優先する）

初回は `can_logger`（受動）から始めて `frames=0` / `buserr=0` の完全な無音となった。
その後の切り分けで **自作側は全て白** と確定している。

| 対象 | 検証方法 | 結果 |
|---|---|---|
| 回路（GPIO・トランシーバ・給電・STBY・500k） | `can_selftest` 自己受信 | **PASS 20/20**、TEC=REC=0 |
| ハーネス3本（6=CANH / 14=CANL / 5=GND） | ICを抜いて配線のみをΩ測定 | **全て 0Ω** |
| イグニッション | エンジン始動済み | 問題なし |
| コネクタ勘合 | 形状的に奥まで挿入済み | 問題なし |

**残っている未実施の操作は「送信」だけ。** 初回は LISTEN_ONLY しか試していないため、
「静かなだけの生きたバス」と「死んだバス」を区別できていない。DLCがブロードキャストを
出さない構成の車では、受動キャプチャは必ずゼロになる。

### 明日の順序

1. **ELM327 を 6番/14番へ挿して送信する**（本命。独立した既知良品での確認）
   - IG ON を声に出して確認してから
   - ELM327のLED点灯 = pin16の12Vが来ている証拠
   - `elm327_probe.py` で `ATZ` → `ATSP0` → `ATDPN`
   - `A6` が返れば **ISO 15765-4 CAN(11bit, 500kbps)** で6/14は生きている
2. 応答あり → DLCはブロードキャストを出さない構成。**OBD2ポーリングをデータ源にする方針へ切替**
   （`can_obd_logger` を使う。生CAN逆解析はDLCからは不可と判断する）
3. 応答なし → OBD端子を **3番/11番へ移設** し、`-125k` ビルドで受動キャプチャ（MS-CAN狙い）

### ⚠️ 3番/11番を試す場合の絶対禁止事項

**3番と6番、11番と14番を導通させてはいけない。** MS-CAN(125k)とHS-CAN(500k)を電気的に
直結することになり、双方のバスでエラーフレームが連続発生してノードがバスオフに陥る。
車両の通信が両系統とも停止し、警告灯・DTC・フェイルセーフ動作を引き起こす。

正しい方法は**OBDコネクタ内の圧着端子の移設**。細いピックでランスを押して端子を抜き、
CANHを6番の穴→3番の穴へ、CANLを14番の穴→11番の穴へ挿し替える。配線を増やさずに済み、
2系統が同時に繋がることが原理的に起きない。GND(5番)はそのまま。

### 背景メモ

- 日本のMAZDA2はDJ型デミオの改名（2019年）。プラットフォームは2014年世代で、
  セキュリティゲートウェイ普及前の設計。**ゲートウェイでDLCが隔離されている可能性は低い。**
- RaceChronoのDIY CANリーダーは NC/ND世代ロードスターについて「OBD 6番・14番から直接
  CANバスにアクセス可能」と明記。隔離側に挙がるのは 2022 BRZ/GR86、2018+ WRX、多くのPorsche。
  **マツダは隔離側に一台も挙がっていない。**
- フォード／マツダは2003〜2004年頃**以降**、HS-CAN(6/14, 500k)に加えて
  MS-CAN(3/11, 125k・ボディ系)を持つ車種が多い。**ノーマルのELM327はMS-CANにアクセスできない**
  （OBD2規格外ピンのため）。よって「ELM327で読めた」はMS-CAN非搭載の証明にはならない。
- GNDは **5番(Signal Ground)単独で正しい**。4番はChassis Ground。

---

## 0. 出発前チェック（家で・PCの前で）

- [ ] **卓上の120Ω終端抵抗をブレッドボードから外す**
      （`can_selftest`用に付けていたもの。車両バスは両端で終端済みのため、
      これを付けたまま繋ぐとバスの終端インピーダンスを狂わせる）
- [ ] ハーネスの導通を再確認（テスタ）：OBD **6番↔CANH** / **14番↔CANL** / **4・5番↔GND**、
      かつ **6番↔14番が非導通**
- [ ] MCP2562FD の給電を再確認：**VDD(pin3)=5V / VIO(pin5)=3.3V**
      （VIOを5Vにすると3.3V非トレラントのC3が壊れる）
- [ ] 3つのファームを**事前にビルドしておく**（現地でネットが無くてもuploadできるように）
      ```bash
      cd firmware/can_logger && python -m platformio run
      ```
      ```bash
      cd firmware/can_obd_logger && python -m platformio run -e esp32-c3-can-obd-logger
      ```
- [ ] **`can_obd_logger` の bench ビルド（`-e esp32-c3-can-obd-logger-bench`）は実車で使わない**。
      あれは `TWAI_MODE_NO_ACK` の卓上ループバック専用。

### 持ち物
PC（充電済み）／USB-Cケーブル（XIAO用）／ブレッドボード一式／OBDハーネス／
テスタ／養生テープ（配線をダッシュ下に仮固定する用）／モバイルバッテリー（保険）

---

## 1. 車内セットアップ

1. **エンジン・IGは OFF の状態で**OBDコネクタを挿す（通電中の抜き差しは避ける）。
   - MAZDA2 の16pin DLCは運転席足元・右奥（ボンネットオープナーの近く）にある想定。
     現物で位置を確認してから作業する。
2. ブレッドボードとPCをUSBで接続。基板の電源はPCのUSBから取る（車両12Vからは取らない）。
3. 配線が**ペダル周りに垂れていないこと**を必ず確認してから、IGをONにする。
4. COMポート番号を確認する。
   ```bash
   python -c "import serial.tools.list_ports as p;[print(x.device,x.description) for x in p.comports()]"
   ```

> **借用車なので**：ステップA/Bは停車・IG ON（またはエンジンON）で行う。
> 走行中のPC操作はしない（走行キャプチャはコマンドを流してから走り出す）。
> 返却前にOBDコネクタを必ず抜き、内装の養生も剥がす。

---

## 2. ステップA：生CAN受信確認（`can_logger` / 完全受動）★ここが回路の合否判定

**なぜ最初にこれか**：`can_logger` は `TWAI_MODE_LISTEN_ONLY` ＋ TWAI-TXをダミーGPIOへ退避
＋ トランシーバTXDをHIGH固定、の3重で**物理的にバスへ何も出せない**。借用車に最初に繋ぐ
ファームとして最も安全で、しかも「回路が動くか」の判定はこれだけで付く。

```bash
cd firmware/can_logger && python -m platformio run -e esp32-c3-can-logger -t upload
```

IG ON の状態で、まず60秒だけ素通しで様子を見る：

```bash
python can_capture_logger.py --port COM5 --out mazda2_a1_idle --limit-seconds 60 --echo
```

### ⚠️ 前提の訂正（2026-09-01 の実車1回目を受けて）

初回の実車トライで **frames=0 / buserr=0**（完全な無音）となった。切り分けの結果:

- 回路は健全（`can_selftest` で PASS 20/20、TEC=REC=0）
- ハーネスも健全（OBDコネクタ端↔ブレッドボード間の導通確認OK、6=CANH/14=CANL/5=GND）
- イグニッションON・エンジン始動済み、コネクタも奥まで勘合済み

したがって **こちら側は端から端まで検証済み**で、残る説明は車両側にある。最有力は
**診断ゲートウェイ**。近年の車はDLCと車内CANバスの間にゲートウェイECUを挟むため、
車内のブロードキャストはDLCまで出てこず、DLC側は「リクエストが来るまで誰も喋らない
静かなスタブ」になる。この場合、受動キャプチャがゼロでもエラーも出ないのが**正常**。

NCロードスター（2005年式）はゲートウェイが無く 2-0-8 の `ATMA` で生CANが素通しで
見えていた。その前提を新しい車にそのまま持ち込めない。

**→ ステップAの `total=0` は、この車では「失敗」を意味しない。**
送信して初めて分かるので、Aで無音でも落胆せずステップB（送信あり）へ進むこと。
GNDは **5番(Signal Ground)単独で正しい**（4番はChassis Ground。スキャンツールも5番を使う）。

### 判定
| 観測 | 意味 | 次にやること |
|---|---|---|
| 大量のフレームが `t_us,id,...` 形式で流れる | **回路OK・配線OK・500kbps一致** | ステップBへ |
| `#`ステータス行だけで `total=0`、`buserr=0` | バスに繋がっていない／H-L逆／ピン違い | 下の切り分け1へ |
| `total=0` だが `buserr` が増え続ける | 電気的には繋がっているが**ビットレート違い**の疑い | 下の切り分け2へ |
| `state` が `RUNNING` 以外 | ドライバ初期化かバス状態の異常 | ステータス行を全部残して報告 |

**切り分け1（総無反応）**：USBを抜き差しして再起動 → `# bitrate=500k, RX=GPIO20` の起動バナーが
出るか確認（出なければファーム/USB側の問題で車両とは無関係）。出るならOBDコネクタの
勘合・6/14番の結線・GNDを疑う。テスタでOBD 6番-14番間の抵抗を測って **約60Ω** なら
車両バスは生きている（120Ωが2本並列＝正常な終端）。

**切り分け2（ビットレート疑い）**：250k版を焼いて同じことをやる。
```bash
cd firmware/can_logger && python -m platformio run -e esp32-c3-can-logger-250k -t upload
```

### Aが通ったら、そのまま取っておくログ
- [ ] `mazda2_a1_idle`（IG ON・エンジン停止・無操作、60秒）
- [ ] `mazda2_a2_engine_idle`（エンジンON・アイドリング、60秒）

---

## 3. ステップB：OBD2応答確認（`can_obd_logger` / 送信あり）

ここから**バスへリクエストを送る**。送るのは OBD2 mode 01（現在値の読み取り）の標準PIDのみで、
車両側の設定を書き換えるコマンドは一切含まない。

```bash
cd firmware/can_obd_logger && python -m platformio run -e esp32-c3-can-obd-logger -t upload
```
```bash
python can_capture_logger.py --port COM5 --out mazda2_b1_obd_idle --limit-seconds 60 --echo
```

### 確認したいこと（2-2-1の保留事項がここで解ける）
- [ ] `0x7E8`〜`0x7EF` からの肯定応答（`41 <PID> ...`）が返るか
- [ ] `0x7E0`（物理アドレス）で応答するか、`0x7DF`（機能アドレス）へ自動切替が必要か
      → ステータス行と、送信IDが途中で変わっていないかで判る
- [ ] パディング `0x55` が受け付けられるか（否定応答 `0x7F` が出ないか）

抽出：
```bash
python can_obd_extract.py mazda2_b1_obd_idle.csv --list
```

---

## 4. ステップC：走行キャプチャ（`can_obd_logger` のまま）

生CANとOBD2応答が**同じ基板の同じ時計**で記録されるので、あとで `can_correlate.py` に
かけるときに時刻合わせが要らない（2-2-1でE2E検証済み）。

```bash
python can_capture_logger.py --port COM5 --out mazda2_c1_drive --limit-seconds 900
```
コマンドを流してPCを助手席側に置いてから走り出す。発進・加速・停止・据え切りを一通り含める。

解析（帰宅後でよい）：
```bash
python can_obd_extract.py mazda2_c1_drive.csv --pid 0D --out mazda2_c1_ref_speed.csv
```
```bash
python can_correlate.py --can mazda2_c1_drive.csv --ref mazda2_c1_ref_speed.csv --ref-time-unit us
```

---

## 5. ステップD：停車操作の差分（`can_logger` に戻す / 2-4-3）

**必ず `can_logger`（受動）へ焼き直してから**行う。`can_obd_logger` のままだと自分の `0x7E0` と
ECUの `0x7E8` が混入して `can_diff.py` が誤検出する。

停車・パーキング（AT）または N＋サイドブレーキで、1操作ごとに10〜20秒。
```bash
python can_capture_logger.py --port COM5 --out mazda2_d0_base --limit-seconds 20
```
- [ ] `mazda2_d0_base`（無操作の基準）
- [ ] `mazda2_d1_winker_l` / `d2_winker_r` / `d3_hazard`
- [ ] `mazda2_d4_headlight` / `d5_brake`（ブレーキ踏み込み保持）
- [ ] `mazda2_d6_door`（ドア開閉）/ `d7_window`

```bash
python can_diff.py --base mazda2_d0_base.csv --test mazda2_d1_winker_l.csv
```

> NCロードスターでは「OBDポートはHS-CANのみでボディ系はMS-CAN側」という示唆が出ている（2-0-9）。
> MAZDA2でも同じ結果になる可能性があるが、**それ自体が有益な確認**なので手順は変えない。

---

## 6. 記録ファイルの命名規則（既存データを壊さないため）

- 車両プレフィックスを必ず付ける：`mazda2_<step>_<内容>`
- NCロードスターの既存ファイル（`obd2_survey_nc_roadster*`, `can_baseline.json`,
  `can_window_*.json`, `can_deepdive_round*.json` 等）は**読み取り専用扱い**。
- 車両を識別しうる情報（VIN、ナンバー、レンタル契約番号）は記録・コミットしない。
