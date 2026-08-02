# ダッシュカム型リアルタイム映像合成・配信システム 調査レポート

## 0. 位置づけ

本ドキュメントは、RaceCaptureロガー本体(ARCHITECTURE.md)とは別軸の派生アイデア――
「AiM SmartyCamのように、走行終了と同時にセンサーデータが焼き込まれた動画が完成している
ダッシュカムを自作する」というアイデア――についての調査記録・意思決定メモである。
ARCHITECTURE.mdの「試行錯誤ログを書かない」というルールに従い、このテーマの調査過程は
本ファイルに独立して記録する。ARCHITECTURE.md本体への統合は、実装着手が決まった段階で
別途検討する。

---

## 1. 発端となったアイデア

AiMのSoloシリーズに接続する純正ダッシュカムは、走行中にCAN/GPS由来のデータ(RPM・
スロットル開度・速度・加速度等)をリアルタイムに動画へ焼き込み、**走行終了と同時に
合成済みの動画が完成している**。GoProで撮影してから後日DashWare等で合成する方式と違い、
後処理の手間が一切ない。この「その場で完成している」という体験を、既存のRaceCapture
ハードウェアと組み合わせて自作したい、というのが出発点だった。

ユーザーからの要件は一貫して以下の通り:

- ソフトウェア開発はできない(ノーコード/ローコード + AIアシスト前提)
- 画面レイアウトはDashWareのような感覚で組みたい
- コストは最小限にしたいが、5〜10万円程度の投資は許容できる
- 手元の機材(予備Windows PC、Web会議用USBカメラ、Raspberry Pi 3B、互換Piカメラ)から
  スモールスタートしたい
- 車載12V電源の不安定さへの対策が必要
- 「その場で動画が完成している」体験が最重要。後処理方式は不採用

---

## 2. なぜRaspberry PiではなくIntel(x86)が必要なのか

結論:**「ダッシュ表示」だけならRaspberry Piで全く問題ないが、「映像へのリアルタイム
データ焼き込み・エンコード・(必要なら)配信」を伴う構成には、現状Intel系CPU(x86)が
実質必須**。理由は独立した3つある。

### 理由1: 当初検討したOBS Browser Source方式が、CEFのARM非対応で動かない

ノーコードでDashWare的なレイアウトを組む手段として、OBS Studio + Browser Source
(HTML/CSSで作った画面をブラウザエンジンでリアルタイム合成する仕組み)を検討した。
これはVS Code/Slack/Discord等でも使われる一般的な手法だが、OBSのBrowser Source機能は
CEF(Chromium Embedded Framework)に依存しており、**CEFはLinux ARM(Raspberry Pi等)
向けのビルドが提供されておらず、起動すらしない**。

→ この経路は、後に理由2の「公式ツール」が見つかったことで採用しないことになったが、
「ラズパイ+OBS」という組み合わせが原理的に成立しない、という発見自体は調査の重要な
分岐点だった。

### 理由2: 公式のRaceCapture video-streamerツールが、Intel専用のハードウェアエンコード(VAAPI)に依存している

AutosportLabs公式の「Video plus data streaming with racecapture」システムの
インストールスクリプト(`racecapture_streaming_install.sh`)を実際にダウンロードして
中身を確認した。依存パッケージに以下が含まれている。

```
sudo apt-get -y -qq install ... intel-media-va-driver-non-free ... gstreamer1.0-plugins-bad gstreamer1.0-libav ...
```

`intel-media-va-driver-non-free` は **Intel内蔵GPUのVAAPI(QuickSync)ハードウェア
エンコードドライバ**そのものである。つまりこのツールは、GStreamer経由でIntelの
ハードウェアエンコーダを使う前提で作られている。Raspberry PiにはIntel iGPUが存在しない
ため、この仕組みをそのまま使うことができない。

推奨ハードウェアがBeelink SER5(AMD)/Dell Optiplex 7050(Intel)/HP EliteDesk 800 G3
(Intel)とIntel機中心なのも、この依存関係と整合する。

### 理由3: Raspberry Pi 5はハードウェアエンコーダを持たず、ソフトウェアエンコードだけで既にCPUが手一杯になる

Raspberry Pi 5(BCM2712)は、Pi 4にあったハードウェアH.264/H.265エンコーダを廃止して
おり、エンコードは全てCPU任せのソフトウェア処理になる。実測ベンチマークでは、
**1080p30のライブ配信1本だけでCPU使用率が80%前後まで上昇する**という報告があった。

ここに「ダッシュのゲージ描画」「複数カメラの映像合成」「(配信する場合は)並行しての
アップロード」まで乗せることを考えると、たとえARM対応版のソフトウェアが存在しても、
Pi 5の現行シリコンでは性能的に余裕がない。

### まとめ

| 制約 | 内容 | 影響範囲 |
|---|---|---|
| CEF/ARM非互換 | OBS Browser SourceがARMで起動しない | 当初検討したOBSルートのみ(公式ツール採用で回避済み) |
| VAAPI依存 | 公式ツールがIntelのハードウェアエンコードドライバに依存 | 公式ツールを使う限り、現状はIntel機が前提 |
| ハードウェアエンコーダ不在 | Pi 5はソフトウェアエンコードのみ、既に高負荷 | ARM移植ができたとしても性能的に厳しい |

---

## 3. 調査の全体まとめ(時系列)

1. **AiM SmartyCamの動作原理の調査** — リアルタイムOSD合成方式であること、ただし
   内部実装は非公開であることを確認
2. **カメラの検討** — フルHD30〜60fps・グローバルシャッター・16:9を満たす候補として
   Arducam AR0234 Pivarietyを選定。ラズパイカメラの小ささとGoProの違いは、センサー
   サイズ・レンズ設計・対応解像度の違いによるものであり、「小さい=低性能」とは
   限らないことを確認
3. **ノーコードでの合成手段の探索** — OBS Studio + Browser Sourceに帰着。「Webページを
   オフラインの描画エンジンとして使う」こと自体は業界で広く使われる一般的な手法である
   ことを確認
4. **CEFのARM非互換を発見** — ラズパイ上でOBS Browser Sourceが動作しないことが判明
5. **後処理方式の検討と却下** — 「その場で完成」という価値提案に反するため不採用。
   Raspberry Pi 4での実測ベンチマーク(0.4〜0.8倍速)も却下の裏付けとした
6. **車載電源の課題** — カーPC専用のDC-DC電源ユニット(M4-ATX等)というジャンルの存在、
   コスト(6〜7万円程度)を確認
7. **スモールスタート手段の検討** — 手元のWindows PC、Raspberry Pi 3B/互換カメラでの
   検証可能性を検討
8. **Podium/RaceCaptureエコシステムの機能限界を発見** — Podium単体では動画への焼き込み
   エクスポートはできず、RaceRenderという別の後処理ソフトを組み合わせる公式ワーク
   フローが存在することが判明
9. **AutosportLabs公式のリアルタイム配信システムを発見** — 「Video plus data streaming
   with racecapture」。これがこの調査全体の転換点となった
10. **配信先・視聴方法を確認** — YouTube Live(RTMP)への配信、podium.live上でのAd Hoc
    イベント表示、YouTube映像とPodiumのライブテレメトリを同一画面に埋め込み可能である
    ことを確認。ただしYouTube Liveには約40秒の遅延がある
11. **RaceCaptureアプリとの関係を確認** — 当初「別マシンで別の専用ソフトが動いている」
    と誤解していたが、実際は**拡張されたRaceCaptureアプリ + 専用のvideo-streamerが
    同一マシン上で連携動作**していることが判明。訂正して報告
12. **インストールスクリプトを実際に取得・解析** — `ratpoison`による完全キオスク
    セッション化、`race_capture`と`video-streamer`の2プロセス自動起動、
    `video-config.ini`によるローカル録画/配信設定、Intel VAAPI依存、を実コードで確認
13. **自動起動・キオスク化を確認** — ログインセッションが`/var/lib/AccountsService`
    に永続化され、電源再投入のたびに自動的にダッシュ+配信モードで起動することを確認
14. **必要スペックを確認** — 公式最低要件はIntel Core i5-6500〜i5-7600 + 8GB RAM +
    SSD(必須、耐振動のため)
15. **小型化・軽量化の検討** — Raspberry Pi互換サイズのx86 SBC(UP 7000、ODROID-H4、
    LattePanda Mu/Sigma)を調査。UP 7000は納期4〜5週間、ODROID-H4はIntel側の供給問題で
    シリーズ全体が生産停止中であることが判明。現実的な代替として、Mini-ITXの裸基板
    (ASRock N100DC-ITX等)や、市販の小型N100ミニPCを検討

---

## 4. 実現する構成 vs 実現しない構成

### 4.1 本命構成:「動画配信+カメラ」を主軸とした構成(実現する)

```
[RaceCapture実機(PodiumConnect不要)] --(USB/Bluetooth/WiFi)--> [x86ミニPC]
                                                                    |
                              [USBカメラ] --(USB)--> RaceCaptureアプリ(拡張版)が全て担う:
                                                                    |
                                                     |-- ① ダッシュ表示(ゲージ)
                                                     |-- ② ライブテレメトリー配信
                                                     |     (アプリ自身の機能。ミニPCの
                                                     |      インターネット接続を使って
                                                     |      podium.liveへ中継。
                                                     |      PodiumConnect不要)
                                                     |-- ③ video-streamer(併走プロセス)
                                                     |     Intel VAAPIでハードウェア
                                                     |     エンコードし、映像に②のデータを
                                                     |     焼き込みながらローカル保存
                                                     |     + (任意)YouTube Live配信
                                                     |
                                               [車載ディスプレイ1台]
```

**特徴:**
- 電源投入→自動ログイン→自動的にダッシュ画面(全画面キオスク)が表示される
- **PodiumConnectは不要**。通常のRaceCapture実機だけで、①ダッシュ表示・②ライブ
  テレメトリー配信・③映像への焼き込み+配信、の3つすべてを1台のミニPC上の
  RaceCaptureアプリ(+併走するvideo-streamer)がまかなう
- ②のライブテレメトリーは、PodiumConnect機のような内蔵セルラー通信ではなく、
  **ミニPC自体が持つインターネット接続(WiFi/モバイルホットスポット等)を使って
  RaceCaptureアプリが中継する**、という昔からある仕組みを流用する(podium.live側の
  デバイスID登録+アプリの「Send Telemetry」設定で有効化)
- 走行終了と同時に、データが焼き込まれた動画がローカルに保存されている(本命の要望を満たす)
- YouTube配信・ライブテレメトリー配信はいずれも任意のオプション(インターネット接続が
  不要な構成にする場合は両方オフにできる)
- ダッシュのゲージレイアウトはRaceCaptureアプリのGUIから直接編集可能
- カメラは専用品でなく市販USBウェブカメラで可(手元のWeb会議用カメラで試作可能)
- 公式にサポートされたRaceCapture機器であれば追加のプロトコル開発が不要
  (自作すべきだったWebSocket中継やHTML/CSSダッシュボードが不要になった)

**必要なもの:**
- x86ミニPC(要件は5章参照)
- 車載用DC-DC電源ユニット、またはそれに準ずる保護回路
- USBカメラ1〜2台
- ダッシュ用ディスプレイ1台
- RaceCapture実機(PodiumConnectは不要)
- (ライブテレメトリー配信・YouTube配信をする場合のみ)車載モバイルホットスポット

### 4.2 実現しない・妥協が必要な構成

| 構成 | 実現可否 | 理由・トレードオフ |
|---|---|---|
| **Raspberry Piのみ+OBS Browser Source(当初案)** | 不可 | CEFがARM非対応で起動しない |
| **後処理方式(GoPro単体撮影+PCで編集)** | 可能だが本命の要望を満たさない | 「その場で完成」という体験が失われる。実測ベンチマークでも実用速度が出ないことを確認済み |
| **DashWareのレイアウトファイルを解析して自作移植** | 非推奨 | 車輪の再発明。公式ツールが既に同等以上の機能を提供するため不要と判断 |
| **Raspberry Pi + RaceCaptureアプリ(映像無し、ダッシュ表示のみ)** | 可能 | 本命の「映像への焼き込み」体験は得られないが、最軽量・最安・最速で組める代替案(5.2節で比較) |

---

## 5. ハードウェア比較(重量を中心に)

### 5.1 市販の小型ミニPCを使った場合の重さ

| 機種 | 重量 | CPU | 備考 |
|---|---|---|---|
| Beelink Mini S12 Pro | 約280〜335g | Intel N100 | 小型ファンあり(完全ファンレスではない)。アイドル時7〜10W |
| Dell OptiPlex 7050 Micro(公式推奨) | 約1.18kg | Intel Core i5(第6/7世代) | 公式最低要件を満たす検証済み構成 |
| HP EliteDesk 800 G3 Mini(公式推奨) | 約1.21kg | Intel Core i5(第6/7世代) | 同上 |

公式推奨機はいずれも1.2kg前後だが、**同じIntel N100系のQuickSyncを積んだ市販の小型
ミニPCなら、1/4程度の重さ(300g前後)まで軽量化できる**。完全ファンレスの製品も
市場に存在するが、今回具体的な実測重量を確認できたのはBeelink Mini S12 Pro
(小型ファン搭載)のみだった。完全ファンレス機を選ぶ場合は、購入前に個別の
スペックシートで重量を確認することを推奨する。

### 5.2 動画配信なし・Raspberry Piのみ構成にした場合の重さ

| 構成要素 | 重量 |
|---|---|
| Raspberry Pi 5 本体のみ | 約46〜50g |
| + ディスプレイ・ケース・電源周り(概算) | + 200〜400g程度(ディスプレイサイズ次第) |
| **合計目安** | **約300〜500g程度** |

Raspberry Piでの「ダッシュ表示専用」構成(RaceCaptureアプリのみ、映像合成なし)は
公式にサポートされており、電源投入で自動起動し、Piのゲージ描画をGPUで高速化する
最適化まで用意されている。ただし**この構成では動画へのデータ焼き込みは一切できず、
本命の「その場で動画が完成している」体験は得られない**。

### 5.3 総合比較表

| 構成 | 重量目安 | 動画合成 | 配信 | 入手性 |
|---|---|---|---|---|
| 公式推奨x86ミニPC(Optiplex/EliteDesk) | 約1.2kg | ○ | ○ | 中古で入手しやすい |
| 市販小型N100ミニPC(Beelink等) | 約300g | ○(要現地検証) | ○(要現地検証) | 即納性高い |
| x86 SBC(UP 7000) | 未計測・軽量級 | ○(要現地検証) | ○(要現地検証) | 納期4〜5週間 |
| x86 SBC(ODROID-H4) | 未計測・軽量級 | ○(要現地検証) | ○(要現地検証) | 現在シリーズ生産停止中 |
| Mini-ITX裸基板(ASRock N100DC-ITX等) | 組立後200〜700g程度 | ○(要現地検証) | ○(要現地検証) | 即納・要自作組立 |
| Raspberry Pi単体(映像なし) | 約300〜500g | × | × | 即納・最安 |

「○(要現地検証)」としたものは、AutosportLabsによる公式検証実績がなく、実機での
動作確認が必要なことを意味する。

---

## 6. 未検証・要確認事項

- 市販小型N100ミニPC / SBC / Mini-ITX裸基板いずれも、RaceCaptureのvideo-streamer
  インストールスクリプトが問題なく動作するかは**未検証**。Intel VAAPI対応チップで
  あれば動く可能性は高いが、実機確認が必須
- 完全ファンレスな小型ミニPCの具体的な実測重量は未確認(今回確認できたBeelink Mini
  S12 Proは小型ファン搭載)
- ODROID-H4/H5シリーズの今後の供給状況
- 車載での振動・高温環境下での長期動作実績(特に裸基板構成の場合)
- エコマイレッジチャレンジ車両特有の電源容量・搭載スペース制約との整合性

---

## 7. 次のステップ(推奨)

1. 市販の小型N100ミニPC(Beelink Mini S12 Pro等、即納性が高いもの)を1台調達し、
   実際にRaceCaptureのインストールスクリプトを流して動作検証する
2. SSH経由でClaude Codeから当該マシンを直接操作し、セットアップ・トラブル
   シューティングを行う(Ubuntu + OpenSSHサーバーを有効化すればよい)
3. 検証がうまくいけば、その結果を踏まえて軽量化(SBC/裸基板ルート)を再検討する
4. 車載電源の保護回路(ARCHITECTURE.md Phase 4で既に計画済み)との統合を検討する

---

## 出典

- [Video plus data streaming with racecapture - Autosport Labs](https://wiki.autosportlabs.com/Video_plus_data_streaming_with_racecapture)
- [racecapture_video_data_livestreaming - GitHub (autosportlabs)](https://github.com/autosportlabs/racecapture_video_data_livestreaming)
- [RaceCapture on Raspberry Pi - Autosport Labs](https://wiki.autosportlabs.com/RaceCapture_on_Raspberry_Pi)
- [Use a Raspberry Pi to create a dedicated dash for your RaceCapture for about $100 – Autosport Labs](https://www.autosportlabs.com/create-a-dedicated-dash-for-your-racecapture-for-about-100/)
- [RPi5 Codec confusion - Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=357870)
- [Raspberry Pi 5 has no hardware video encoding and only HEVC decoding | Hacker News](https://news.ycombinator.com/item?id=38068801)
- [UP 7000 Intel Processor N100 fanless SBC review – CNX Software](https://www.cnx-software.com/2023/11/25/up-7000-review-intel-processor-n100-fanless-sbc-unboxing-first-boot/)
- [ODROID-H4 – Hardkernel](https://www.hardkernel.com/shop/odroid-h4/)
- [LattePanda Mu Review – Tom's Hardware](https://www.tomshardware.com/raspberry-pi/lattepanda-mu-review)
- [OptiPlex 7050 Micro Owner's Manual - Dell](https://www.dell.com/support/manuals/en-us/optiplex-7050-desktop/optiplex-7050-desktop-micro-owners-manual/physical-dimension-specifications)
- [HP EliteDesk 800 G3 Mini - hardware-corner.net](https://www.hardware-corner.net/desktop-models/HP-EliteDesk-800-G3-Mini/)
- [Beelink Mini S12 Pro - Starry Hope](https://www.starryhope.com/minipcs/models/beelink-mini-s12-pro/)
- [Raspberry Pi 5 - Technical Specifications and Mechanical Drawings - element14 Community](https://community.element14.com/products/raspberry-pi/b/blog/posts/raspberry-pi-5-technical-specifications-and-mechanical-drawings)
