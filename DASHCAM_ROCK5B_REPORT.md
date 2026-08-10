# ダッシュカムサブプロジェクト：ROCK 5B（Rockchip RK3588）移行方針レポート

> 電源回路設計を担当する友人への共有用レポート。「なぜx86ミニPCではなくRadxa ROCK 5B
> （ARM/Rockchipボード）を使うのか」という背景と、電源回路設計に関わる仕様をまとめている。
> 検証の詳細な作業ログは`task_dashcam_breakdown.md`、意思決定の調査記録は
> `DASHCAM_STREAMING_RESEARCH.md`を参照（いずれも本リポジトリ内）。

作成日：2026-08-10

---

## 1. これまでの経緯（要約）

ダッシュカムサブプロジェクトは、「走行終了と同時にセンサーデータが焼き込まれた動画が
完成している」ダッシュカムの自作を目標に、AutosportLabs公式の「Video plus data
streaming with racecapture」システム（`race_capture`アプリ + `video-streamer`）を
使う方式で進めてきた。

このシステムの`video-streamer`（画面キャプチャ→ハードウェアエンコード→ローカル保存/
RTMP配信を担うプロセス）が**Intel/AMDのVAAPI（ハードウェアエンコードAPI）専用**に
作られているため、当初はx86 CPU搭載機が必須という前提で検証を進めた。

- 手元のAMD PC（AMD A4 PRO-7300B）で検証開始 → VAAPI経由のハードウェアエンコード自体は
  成功したが、`race_capture`アプリ（ダッシュ表示GUI）がUbuntu 24.04世代のMesa/Xorg
  スタックと非互換で起動クラッシュする問題が発生
- Intel機（HP EliteDesk 800 G3、Core i5第7世代）でも同一の問題が再現し、**GPUベンダーに
  依存しない、race_capture配布バイナリ自体の非互換**と判明
- Ubuntu 22.04 LTSへダウングレードすることで解消し、「ダッシュ表示＋映像データ焼き込み」
  ＋「キオスク自動起動（電源投入だけで無人起動）」まで実証完了

ただし、この検証で使ったEliteDeskは**約6.1kg**あり、車載搭載には重量面で不利という
課題が残った。

---

## 2. なぜROCK 5Bを検討するに至ったか（軽量・低コストなx86機との比較）

軽量なx86 SBCとして「LattePanda」シリーズを検討したが、実際の価格を調べたところ
以下の通りだった。

| 選択肢 | 価格 | 備考 |
|---|---|---|
| LattePanda 3 Delta 864（秋月電子、Windows込み） | ¥65,400 | Windows 10 IoT Enterpriseライセンス込み（不要な費用） |
| LattePanda 3 Delta 864（DFRobot直輸入、Linux版） | $279（概算¥48,000〜53,000、送料・関税込み） | 通関・保証・日本語サポートなしのリスクを負ってこの価格 |
| LattePanda Sigma（参考、上位モデル） | 重量438g | Core i5-1340P搭載、大型ヒートシンク込みで軽量とは言い難い |

一方、**Radxa ROCK 5B（Rockchip RK3588、ARMアーキテクチャ、8コア）は国内代理店
（IoT本舗）で約¥23,000**で購入できることを確認した。x86の選択肢と比べて明確に
安価である。

---

## 3. ROCK 5Bを使う上でのトレードオフ（重要）

ROCK 5BはARMアーキテクチャのため、これまでx86で確立してきた仕組みをそのまま
使うことはできない。具体的には以下の2点を作り直す必要がある。

1. **GPU描画（`race_capture`アプリのダッシュ表示）**：ROCK 5Bの内蔵GPU（Mali G610）は、
   これまで検証したIntel/AMDとは全くの別物。`race_capture`はオープンソース
   （[github.com/autosportlabs/RaceCapture_App](https://github.com/autosportlabs/RaceCapture_App)）
   で、Raspberry Pi向けの公式ARM対応実績もあるが、Mali GPUでの動作は未検証。
   x86環境では公式配布バイナリがGPUベンダーを問わず起動クラッシュした実績があるため、
   Mali環境でも同種の問題に当たるリスクがある（ただしオープンソースなので、詰まっても
   ソースからビルドし直すという対応策は残っている）
2. **ハードウェアエンコード（`video-streamer`相当の機能）**：公式の`video-streamer`は
   VAAPI専用かつ**ソースコード非公開のクローズドバイナリ**（配布リポジトリの中身は
   インストールスクリプトのみ）のため、ROCK 5B向けに改造することができない。
   Rockchip独自のエンコードAPI「RKMPP」を使い、**同等機能を自作する**方針で進めている

つまり今回の移行は「既存ツールの移植」ではなく、コスト・重量メリットと引き換えに
「一部機能を自作する」という判断である、という点は認識しておいてほしい。

---

## 4. 友人（電源回路設計）へ：ROCK 5Bの仕様

### 4.1 電源入力仕様（Radxa公式ドキュメントより）

- **USB PD2.0対応**：5V/5A、または9V〜20V/2Aでの給電に対応
- 9V〜20V DCの固定電圧アダプタ（USB-Cプラグ形状）でも可
- GPIOピン経由の5V PoE給電にも対応（今回は未使用の想定）
- ⚠️ 公式ドキュメントに**「5Vでは3A程度までしか給電できない電源アダプタが多い」**という
  注意書きあり。電圧が低いまま高出力を狙うと不安定になりうるため、**9V〜12V系で
  2A以上供給できる設計を推奨**

車載12V電源からの給電を想定すると、単純な12V→5Vの降圧だけでなく、**USB PD
ネゴシエーションに対応したトリガー基板、またはUSB PD対応のDC-DCコンバータを
経由する設計**が必要になる見込み。

### 4.2 冷却（電源設計にも関係）

RK3588は連続的な高負荷（今回の用途である動画エンコードはまさにこれに該当）では、
**アクティブファンによる冷却がほぼ必須**（パッシブのみだと熱で性能が落ちる領域に
入りやすいという情報あり）。小型の冷却ファン（5V駆動、数百mA程度）の電源も
設計に含めておく必要がある。

### 4.3 物理仕様

- 基板サイズ：**100mm × 75mm**（Pico-ITXフォームファクタ）
- 重量：公式資料に記載なし。**実機到着後に実測して追って共有する**
- ストレージ：microSDカードで起動する想定（eMMC/M.2 NVMeも選択可）

### 4.4 セルラー通信（ライブ配信・テレメトリー用）

ROCK 5B本体にはセルラー通信用の専用スロットがないため、**USBポートに接続する
ドングル型LTEモデム＋データ専用SIM契約**で対応する方針。ROCK 5B本体の電源設計に
追加の考慮は基本的に不要（USBポートからの給電で足りる想定）。

### 4.5 電源のON/OFF運用方針（制御方式の設計に関わる）

想定している運用は以下の通り。

- **駐車中は基本的に電源オフ**：車両バッテリーへの負荷を避けるため
- **走行直前に電源を入れることがある**：GPSの測位（コールドスタート）には数十秒〜
  数分かかることがあるため、走行開始前に事前に電源を入れて温めておきたい

つまり、**「イグニッションONと同時に電源が入る」という単純な連動方式では不十分**で、
イグニッションONより前に（手動、またはそれに類する何らかの方式で）電源を入れられる
必要がある。逆に、イグニッションOFFと同時に即座に電源を切る方式でも運用上は問題ない
（駐車後すぐ電源が落ちて構わない）。この非対称性（ON側は事前操作、OFF側は連動でも可）
を電源制御方式の設計に反映してほしい。

---

## 5. 今後の進め方（参考）

1. 手元のRaspberry Piで、自作ESP32ファームウェア＋`race_capture`アプリの
   ライブテレメトリー機能（podium.live経由）の動作を確認（外部モニター使用、
   追加購入なしで着手可能）
   - ※スマートフォン版RaceCaptureアプリでのpodium.live中継＋PC版PodiumLiveでの
     モニタリングは、本サブプロジェクトの検証とは別に、ユーザー自身がすでに動作確認済み
2. ROCK 5B購入（USB PD対応電源・冷却ファン付きヒートシンク・microSDを同時手配）
3. ROCK 5B上での`race_capture`アプリのGPU描画確認（最大の技術的未知数）
4. RKMPPを使ったハードウェアエンコード機能の自作・動作確認（ローカル保存優先、
   配信は後回し）
5. ある程度動作確認できた段階で、USBドングル型LTEモデム（データ専用SIM）を購入し、
   YouTube配信・セルラー通信を検証
6. 動作確認が取れた段階で、車載用モニター等の周辺機器を購入
7. **友人によるロガー本体（電源保護回路含む）の完成（2026年9月中旬予定）を待たず**、
   検証用のESP32-C3代替機のまま実車に持ち込み、2週間程度の実運用テストを実施
   （真夏〜初秋の高温環境は、連続エンコード時の熱設計を検証する上で好条件と判断）

---

## 出典

- [Radxa ROCK 5B Product Introduction](https://docs.radxa.com/en/rock5/rock5b/getting-started/introduction)
- [Rock5/hardware/5b - Radxa Wiki](https://wiki.radxa.com/Rock5/hardware/5b)
- [ROCK 5 Model B - IoT本舗 オンラインストア](https://shop.iothonpo.com/product/rock-5b/)
- [Lattepanda 3 Delta 864（秋月電子）](https://akizukidenshi.com/catalog/g/g117563/)
- [LattePanda 3 Delta 864（DFRobot, Linux版）](https://www.dfrobot.com/product-2594.html)
- [autosportlabs/RaceCapture_App（race_captureソース）](https://github.com/autosportlabs/RaceCapture_App)
- [autosportlabs/racecapture_video_data_livestreaming（video-streamerインストールスクリプト配布元）](https://github.com/autosportlabs/racecapture_video_data_livestreaming)
