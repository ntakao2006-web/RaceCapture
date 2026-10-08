# UNO Q 映像パイプライン確認手順（自前で実施する版）

> **なぜこの手順書があるか**
>
> `hardware_share_20260921.md`3章で回路担当へ依頼していたD-1〜D-4は、
> **「実機の検証記録が無いので確認済みとは回答できない」**という回答だった
> （`hardware_ans_20260921.md`1章）。**したがってこの確認はこちらで行う**（同6章の4）。
>
> あわせて、**元のD-3の判定基準は誤りだと指摘された**（同6章の5）。
> この文書は、その指摘を反映して**判定方法を差し替えたもの**である。
> 以後、UNO Qの映像確認はこの手順を正とし、`hardware_share_20260921.md`3章の手順は使わない。
>
> ~~⚠️ UNO Qは未調達。入手後に実施する。~~ → 2026-10-06時点で調達済み・実機稼働中。**V-4（GPU描画）は2026-10-02に確認済み**（ARCHITECTURE.md 4章）。
>
> **V-1〜V-3は`unoq_video_check.sh`で無人実行できる**（2026-10-08作成。3〜5章の手順と判定をそのまま自動化したもの）。
> UNO Qの電源を入れ、PCと同じネットワークにつないだうえで、PCから次の1行を流す。
> ```bash
> ssh unoq 'bash -s' < unoq_video_check.sh
> ```
> 結果はUNO Qの`~/enc_test/result_<日時>/summary.txt`に残る。常駐サービスは止めずに測るので、稼働状況と温度も一緒に記録する。
> カメラは不要（入力は事前生成した生映像ファイル）。カメラの接続方式（MIPI CSI＋キャリア基板／USB UVC）はV-3が通ってから回路担当と決める。

---

## 0. この確認が最優先である理由

**ハードウェアエンコードが使えなければ、UNO Qという選択自体が破綻する。**

A53×4コアのCPUエンコードでは1080p30は回らない。そうなるとVer.2のダッシュカム構想
（E-3：保存のみ・1080p30・1カメラ）が成立せず、GNSS・LTEを含む周辺の議論も前提から崩れる。
**他のどの検討よりも先に潰す。**

Ver.1でROCK 5Bを使った際、公式`video-streamer`がIntel/AMDのVAAPI専用だったため
Rockchip独自のRKMPPで同等機能を自作する羽目になった経緯がある
（`DASHCAM_ROCK5B_REPORT.md`3章）。UNO Q（Qualcomm）は`venus`というV4L2 M2Mドライバを使い、
APIがRaspberry Piと同じv4l2m2m系なので移植性は高いはずだが、
**Arduino配布のDebianイメージでvenusが有効化されて出荷されているかは不明**のままである。

---

## 1. 🔴 旧手順のどこが間違っていたか（差し替えの理由）

`hardware_share_20260921.md`3章のD-3では、こう書いていた。

> **判定基準**：30秒の素材が実時間（30秒前後）で完走し、その間の**CPU使用率が低い**なら
> ハードウェアエンコードが効いている。CPUが張り付いて30秒より大幅に遅い場合は
> **ソフトエンコードに落ちている**＝赤信号

**これは2か所とも誤っている。**

| # | 誤り | 正しい理解 |
|---|---|---|
| 1 | 「使えなければ黙ってソフトエンコードへ落ちる」前提だった | `-c:v h264_v4l2m2m`と**明示した場合、利用できなければエラーで落ちる**ことがある。**黙ってCPUへ切り替わるとは限らない**ので、「完走したかどうか」はハード/ソフトの判別にならない |
| 2 | CPU使用率でハード/ソフトを判別しようとしていた | 旧手順は入力に`testsrc`を使っていた。**入力画像の生成と色変換自体がCPUを食う**ため、**CPU使用率が高い＝CPUエンコード、とは言えない** |

**→ 判定は「所要時間とCPU負荷」ではなく、
①実際に使用されたデバイス ②フレーム欠落 ③保存結果 で行う。**
CPU負荷は**補助指標**として記録するだけに留める。

---

## 2. 準備

```bash
sudo apt-get update && sudo apt-get install -y v4l-utils ffmpeg mesa-utils sysstat
```

作業ディレクトリは**`/tmp`を使わない**。`/tmp`がtmpfs（RAM上）だと生映像でメモリを食い潰す。

```bash
mkdir -p ~/enc_test && cd ~/enc_test && df -h .
```

**空き容量は2GB以上あること**を確認する（生YUVの中間ファイルを置くため）。

---

## 3. V-1：エンコーダデバイスが見えているか

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

各デバイスが**何のデバイスか**まで見る。エンコーダは
「**OUTPUT側が生画（NV12等）／CAPTURE側がH.264**」というM2Mデバイスとして現れる。

```bash
for d in /dev/video*; do
  echo "===== $d"
  echo "-- OUTPUT(入力) 側:"; v4l2-ctl -d "$d" --list-formats-out 2>/dev/null | grep -Ei "nv12|yuv|nv21"
  echo "-- CAPTURE(出力) 側:"; v4l2-ctl -d "$d" --list-formats    2>/dev/null | grep -Ei "h264|hevc|h265"
done
```

**記録**：エンコーダらしきデバイス番号（例：`/dev/video1`）。以降この番号を使う。

- [ ] 未実施　／　[ ] 実施済み → エンコーダ：`/dev/video____`　／　デコーダ：`/dev/video____`

---

## 4. V-2：ffmpegがエンコーダを持っているか

```bash
ffmpeg -hide_banner -encoders | grep -i v4l2
```

`h264_v4l2m2m`が出てくるかを見る。

> ⚠️ **これは「ffmpegのビルドに含まれているか」を見ているだけで、
> 実際にハードウェアで回るかどうかとは別の話。** ここが通っても安心しないこと。

- [ ] 未実施　／　[ ] 実施済み → 結果：

---

## 5. V-3：★本命。1080p30のハードウェアエンコードが実時間で回るか

### 5-1. 入力をCPUで生成しない素材を先に作る

**旧手順の誤り②を避けるため、`testsrc`をその場で生成しながら測らない。**
生のNV12を一度ファイルへ書き出し、**エンコード時はファイルから読むだけ**にする。

```bash
cd ~/enc_test
ffmpeg -hide_banner -f lavfi -i testsrc2=size=1920x1080:rate=30 -t 2 \
       -pix_fmt nv12 -f rawvideo -y src_2s.nv12
ls -lh src_2s.nv12     # 約186MB（1920*1080*1.5*60frame）
```

この2秒素材を**15回ループ＝30秒ぶん**として流す。

### 5-2. 計測する

```bash
cd ~/enc_test
/usr/bin/time -v ffmpeg -hide_banner -loglevel verbose \
  -stream_loop 14 -f rawvideo -pix_fmt nv12 -s 1920x1080 -r 30 -i src_2s.nv12 \
  -c:v h264_v4l2m2m -b:v 12M -vsync 0 \
  -y out_hw.mp4 2> enc_hw.log
```

**入力は900フレーム（30fps × 30秒）ちょうどになる。**

### 5-3. 判定（ここが差し替えた部分）

**① 実際に使用されたデバイスを確認する**

```bash
grep -Ei "v4l2|/dev/video|Using device|output driver|capture driver" enc_hw.log | head -20
```

- ✅ **ログに`/dev/videoN`のオープンとv4l2m2mの初期化が出ている**なら、そのデバイスで回っている
- ❌ エラーで落ちている場合は、**ハードウェアエンコーダが使えないということ**
  （黙ってCPUへ落ちることを期待しない。エラーはエラーとして扱う）

**② フレーム欠落を確認する**

```bash
tail -3 enc_hw.log          # ffmpegの最終行 frame= が 900 か
ffprobe -v error -count_frames -select_streams v:0 \
        -show_entries stream=nb_read_frames,codec_name,width,height,avg_frame_rate \
        -of default=noprint_wrappers=1 out_hw.mp4
```

- ✅ `nb_read_frames=900`、`codec_name=h264`、`1920x1080`、`avg_frame_rate=30/1`
- ❌ フレーム数が足りない＝**取りこぼしている**。ビットレートやバッファ設定の見直しが要る

**③ 保存結果が壊れていないか確認する**

```bash
ffmpeg -v error -i out_hw.mp4 -f null - 2>&1 | head    # 何も出なければ健全
ls -lh out_hw.mp4
```

実際に再生して、ブロックノイズ・コマ飛び・色化けが無いかも目で見る。

**④ 速度とCPU負荷を「記録する」（判定には使わない）**

```bash
grep -E "speed=" enc_hw.log | tail -1
grep -E "Percent of CPU|Elapsed .wall clock" enc_hw.log
```

- 参考値として残すだけ。**単独ではハード/ソフトの判別根拠にならない。**

**⑤ 🔴 対照実験：同じ入力をCPUエンコードで回して比べる**

**これがいちばん確実な裏取り。** 同じ素材・同じ条件でlibx264を回す。

```bash
cd ~/enc_test
/usr/bin/time -v ffmpeg -hide_banner \
  -stream_loop 14 -f rawvideo -pix_fmt nv12 -s 1920x1080 -r 30 -i src_2s.nv12 \
  -c:v libx264 -preset ultrafast -b:v 12M -vsync 0 \
  -y out_sw.mp4 2> enc_sw.log
grep -E "speed=" enc_sw.log | tail -1
grep -E "Percent of CPU|Elapsed .wall clock" enc_sw.log
```

**A53×4コアなら、CPUエンコードは1080p30の実時間に届かないはず**（`speed`が1.0xを大きく下回る）。
**HW版とSW版で所要時間・CPU%がはっきり分かれれば、HWが効いていることの裏が取れる。**
**両者が似た値なら、HW指定が実質効いていないことを疑う。**

### 5-4. 記入欄

| 項目 | 結果 |
|---|---|
| 使用デバイス（ログから） | |
| 出力フレーム数 / 期待値900 | |
| 所要時間（wall clock） | |
| `speed=` | |
| CPU% | |
| 出力ファイルの健全性 | |
| **対照：libx264の所要時間 / speed / CPU%** | |
| **判定** | ✅ HWで回る ／ ❌ 回らない ／ △ 要再試験 |

---

## 6. V-4：GPUのOpenGL ESが有効か（ダッシュGUI描画用）

```bash
glxinfo -B 2>/dev/null | grep -Ei "renderer|opengl es"
```

`freedreno`および`Adreno 702`相当が出るかを見る。

> ⚠️ **Xが動いていない構成では`glxinfo`が使えない。** その場合は次で確認する。

```bash
sudo apt-get install -y mesa-utils-extra kmscube
eglinfo 2>/dev/null | grep -Ei "renderer|vendor|opengl es" | head
kmscube                # 画面に回転する立方体が出れば GBM/EGL 経路が生きている
```

- [ ] 未実施　／　[ ] 実施済み → 結果：

---

## 7. V-5：最終確認（回路担当の指定）

**単体で通っても、それだけでは成立を意味しない。**
最終的には**カメラ・表示・LTE・ロギングの同時動作**で評価する、と申し送られている
（`hardware_ans_20260921.md`1章）。

V-1〜V-4が通ったあとに、以下を同時に走らせて成立するかを見る。

- [ ] カメラ入力（MIPI CSI または USB UVC）→ ダッシュ合成 → 1080p30でSD保存
- [ ] ダッシュGUIの描画（Adreno 702）
- [ ] LTEでのテレメトリー送信
- [ ] ロギング（100Hz CSV＋生CAN）

このとき見るのは**温度・メモリ・録画セグメントの連続性**
（ダッシュカム側のDC-9-8-4と同じ観点）。

---

## 8. 関連資料

| 資料 | 内容 |
|---|---|
| `hardware_ans_20260921.md` | **この手順書が生まれた経緯。**1章＝回答原文、6章の4・5＝こちらの宿題 |
| `hardware_share_20260921.md` | 3章に旧手順（D-1〜D-4）。**判定基準が誤っているので使わない** |
| `LOGGER_V2_UNOQ_REPORT.md` | 4章＝UNO QとROCK 5Bの比較、7.2章＝E-3（保存のみ・1080p30・1カメラ）の決定 |
| `DASHCAM_ROCK5B_REPORT.md` | Ver.1でVAAPI専用問題に当たった経緯（3章） |
| `task_dashcam_breakdown.md` | ダッシュカム側のサブタスク（DC-9-8-4＝連続稼働試験） |
