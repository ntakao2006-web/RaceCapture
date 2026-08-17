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
  - ⏳ **AMD機での検証(DC-1〜DC-5進行中、詳細は`task_dashcam_breakdown.md`参照)**：手元のAMD A4 PRO-7300B機(Ubuntu Server 24.04)で公式インストールスクリプトをAMD向けに調整（Intel専用VAAPIドライバをMesa版へ読み替え、Ubuntu 24.04でのパッケージ名変更に追随、GStreamerのVAAPIプラグインを追加導入)した結果、`racecapture`・`video-streamer`ともインストール成功、VAAPI H264エンコーダー(`vaapih264enc`)の登録まで確認できた。Intel/N100系実機についてはこのAMD機での知見は直接は適用できないため、引き続き実機確認が必要
  - ✅ **DC-5でvideo-streamerのVAAPI初期化失敗を解消**：原因はUSBカメラ未接続ではなく、`video-streamer`にバンドルされた2022年当時の古い`libstdc++.so.6`/`libva*.so.2`がUbuntu 24.04のMesa VAAPIドライバと非互換だったこと。システム側の新しいライブラリを`LD_PRELOAD`で優先させることで解消し、動画エンコードパイプラインの起動自体には成功した。同種のPyInstallerバンドル起因のライブラリ非互換は、今後の他コンポーネントの検証でも再発しうる典型パターンとして記録
  - ⚠️ **新たな構造的発見**：video-streamerの「データ焼き込み」はUSBカメラ映像を直接GStreamerで合成するのではなく、race_captureアプリのダッシュ画面をX11の`ximagesrc`で画面キャプチャする方式。そのため**race_captureアプリのGUIが実際にX11セッション上で描画されていることが構造的な前提条件**であり、ヘッドレス環境では原理的に成立しない
  - ⚠️ **race_capture(Kivy)が`No matching FB config found`でクラッシュする問題を、実GPU(Radeon HD 8470D、Mesa `radeon`クラシックドライバ)を使った本物のXorgセッション(物理モニター非接続、EDID偽装のみ)でも再現**。当初「Xvfbのソフトウェアレンダラ限定の問題」と推測していたが、この推測は否定された。GLX自体は`direct rendering: Yes`・528件のGLXFBConfigs（標準的なdepth24/stencil8/RGBA8888構成含む）と正常に機能しているにもかかわらず発生する。**DC-2（物理モニター接続問題）とは別個の問題であり、DC-2を解決してもこのクラッシュ自体は残る**点に注意
  - ✅ **原因をさらに深掘りし、Kivy固有ではなくSDL2自体の問題と判明**：Kivyのログの`Provider: x11(['window_sdl2'] ignored)`は、実はKivy独自のネイティブX11実装(フォールバックなしで即fatalErrorする、脆い経路)が選ばれていたことを示すログだった（GitHub上のソース確認）。`KIVY_WINDOW=sdl2`でSDL2を強制したところ、SDL2自体も`RuntimeError: Couldn't find matching GLX visual`で同様に失敗した
  - ✅ **さらに切り分けを進め、システムのGLXスタック自体は無罪と確定**：Python/ctypesで`glXChooseFBConfig`をKivyと全く同じ属性で直接呼び出したところ18件マッチし、Visual取得にも成功。`xdpyinfo`/`glxinfo`でも要求を満たすdepth 32 ARGB visual・FBConfigの実在を確認した。つまり原因はシステム側ではなく**race_capture(PyInstallerバンドル)固有の何か**。バンドルされた古い`libX11.so.6`/`libXrender.so.1`を`LD_PRELOAD`でシステム版に差し替える対策（video-streamerのVAAPI問題で有効だった手法）を試したが、race_captureでは効果がなかった。PyInstallerが`$ORIGIN`相対RPATHや絶対パスdlopenでバンドル版を直接読み込んでいるためと推測され、**外部からの環境変数介入では回避できない**。これ以上の追い込みにはgdb等のソースレベルデバッグ、またはrace_capture自体のソースからの再ビルドが必要と判断し、調査を一旦打ち切った。**より新しいGPU/ドライバでの比較検証**（この検証機固有の問題なのか、race_capture配布バイナリ自体の一般的な非互換なのかの切り分けも兼ねて）が次の有力な選択肢
- 完全ファンレスな小型ミニPCの具体的な実測重量は未確認(今回確認できたBeelink Mini
  S12 Proは小型ファン搭載)
- ODROID-H4/H5シリーズの今後の供給状況
- 車載での振動・高温環境下での長期動作実績(特に裸基板構成の場合)
- エコマイレッジチャレンジ車両特有の電源容量・搭載スペース制約との整合性

---

## 7. 次のステップ(推奨)

> 実作業ログ・進捗は`task_dashcam_breakdown.md`（タスクID: `DC-N`）を参照。

- 🔄 **【2026-08-10追記】ROCK 5B（Radxa、Rockchip RK3588、ARM）への移行を検討・決定**：
  DC-6/DC-7で確立したEliteDesk(Intel, x86)ルートは約1.2kgと車載搭載には重量面で不利。
  軽量なx86 SBCの代替候補として調査した「LattePanda 3 Delta 864」も、実際の国内価格
  （秋月電子で¥65,400、Windows 10ライセンス込み）・直輸入価格（DFRobot Linux版で
  $279、送料・関税込み概算¥48,000〜53,000）とも高価と判明。一方、国内代理店
  （IoT本舗）で約¥23,000で入手できるRadxa ROCK 5B（RK3588、ARM）はコスト面で
  明確に有利なため、こちらへの切り替えを決定した。ただし公式の`video-streamer`は
  VAAPI専用のクローズドバイナリ（ソース非公開）でARM非対応のため、ハードウェア
  エンコード機能はRKMPP（`ffmpeg-rockchip`）ベースでの自作が必須になる見込み。
  詳細な比較・トレードオフ・電源仕様は`DASHCAM_ROCK5B_REPORT.md`
  （友人向け共有レポートと兼用）、進め方は`task_dashcam_breakdown.md`のDC-9参照
- 🔴 **DC-6で結論確定**：手元にあったHP EliteDesk 800 G3系(Intel Core i5、Mesa `iris`系ドライバ、
  AMD機とは全く異なるGPUベンダー)でAMD機(DC-1〜DC-5)と同じ検証を行った結果、race_captureの
  `No matching FB config found`(exit 102)が**同一のまま再現した**。depth32 Visual・
  GLXFBConfigs(992件)ともシステム側には十分存在するにもかかわらず失敗することも同一。これにより
  **AMD機固有の環境問題ではなく、race_capture配布バイナリ(Kivy 2.3.1/SDL2)自体がUbuntu 24.04世代
  のMesa/Xorg/XRenderスタックと一般的に非互換であることが確定**した。また`video-streamer`の
  VAAPI初期化失敗（バンドルされた古い`libstdc++.so.6`が原因、`LD_PRELOAD`で解消）もAMD/Intel
  両方で再現し、これもベンダー非依存の汎用的な非互換と判明した。詳細は`task_dashcam_breakdown.md`
  のDC-6-4/DC-6-5参照
- 🎉 **DC-6-6で最終解決**：ユーザー判断で選んだ方針(c)「EliteDeskをUbuntu 22.04 LTSへ
  ダウングレードする」を実行した結果、race_captureの`No matching FB config found`は
  **Ubuntu 22.04世代のMesa/Xorgでは再発せず解消した**（DC-6-6-6）。続けて`race_capture`＋
  `video-streamer`を同時起動し、`race_capture`のダッシュ画面が`ximagesrc`経由で実際に
  mp4動画として録画されることを画像で目視確認し、**「ダッシュ表示＋映像データ焼き込み」という
  当初の目的が達成された**（DC-6-6-7）。副次的に見つかった`video-streamer`の音声キャプチャ
  失敗（`adduser $USER audio`漏れ）も`racecapture_streaming_install_intel.sh`側の恒久修正で
  解消済み。詳細は`task_dashcam_breakdown.md`のDC-6-6-6/DC-6-6-7参照
- 🎉 **DC-7-1でキオスク自動起動も実証完了**：ratpoisonによるキオスク自動起動（電源投入だけで
  `race_capture`+`video-streamer`が無人起動するか）を検証した結果、GDM3自動ログイン設定と
  AccountsServiceのユーザー設定ファイル生成（公式スクリプトに元々欠けていた2点、
  `racecapture_streaming_install_intel.sh`へ反映済み）を追加することで、**2回のリブートで
  完全に無人でのキオスク自動起動を確認**した。初回起動時のみ発生するGNOME keyring初期化
  ダイアログも解消済み。詳細は`task_dashcam_breakdown.md`のDC-7-1参照
- 🎉 **DC-7-2でRTMP出力パイプライン自体の動作も実証**：ローカルに一時的なRTMPサーバー
  (nginx+libnginx-mod-rtmp)を立てて`video-streamer`の配信先をそちらに向けたところ、
  `Could not connect to RTMP stream`エラーは発生せず、実際にRTMPストリームが継続送信される
  ことを確認した。**これまでの失敗は単に配信先URLがダミー値だったことが原因で、
  video-streamer側のRTMP実装自体には問題がない**ことが判明。実際のYouTube Live等への
  本番配信（配信キーでの疎通確認）自体は未実施のまま
  - 🔴🎉 **副次的に重大なディスクフルバグを発見・解消**：`streaming_url`がダミー値のまま
    長時間(約2時間)放置すると、`video-streamer`のRTMP接続失敗リトライでログファイルが
    45GBまで肥大化しディスクを100%使い果たすことが判明。logrotate＋1分間隔cronによる
    ローテーションを恒久対策として導入し、`racecapture_streaming_install_intel.sh`にも
    反映済み。詳細は`task_dashcam_breakdown.md`のDC-7-2参照
- **今後の検討事項**：EliteDesk自体は約1.2kgと車載搭載には重量面で不利なため、今回確立した
  「Ubuntu 22.04 LTS＋本ダウングレード方針」が軽量な機材(市販小型N100ミニPC/SBC/Mini-ITX
  裸基板等)でも同様に通用するか、それらの機材でUbuntu 22.04が使えるか（Ubuntu 24.04専用の
  機材でないか）の確認が必要（DC-7-3）。また実際のYouTube等への本番RTMPライブ配信（配信キー
  未検証）・車載電源の保護回路との統合（DC-7-4）が、車載本番導入に向けた残タスク
1. （DC-6で）Intel実機でRaceCaptureのインストールスクリプトを流して動作検証する
2. SSH経由でClaude Codeから当該マシンを直接操作し、セットアップ・トラブル
   シューティングを行う(Ubuntu + OpenSSHサーバーを有効化すればよい)
3. 検証がうまくいけば、その結果を踏まえて軽量化(SBC/裸基板ルート)を再検討する
4. 車載電源の保護回路(ARCHITECTURE.md Phase 4で既に計画済み)との統合を検討する

---

## 8. 配信用ダッシュと運転中表示用ダッシュの分離（2026-08-15追記）

### 8.1 発端

当初の構想では「YouTube配信・録画される映像＝ダッシュ表示画面そのもの」を前提にしていたが、
ユーザーから「配信用に自分で設定したゲージを重ねた画面と、走行中に実際に見る通常のダッシュ
表示を分けたい。ROCK 5Bで、HDMIダミープラグ等を使って複数画面に別々のダッシュを表示する
ことはできるのか」という疑問が出た。これができないと構想の前提が崩れるため、緊急度の
高い技術調査として着手した。

### 8.2 結論：ハードウェア的には実現可能。むしろ「分離には必須」の構造だった

**ROCK 5Bは公式に3系統の独立ディスプレイを同時出力できる**（HDMI 2.1×2ポート＋USB-C経由の
DisplayPort、最大8K対応。[Radxa公式ドキュメント](https://docs.radxa.com/en/rock5/rock5b/getting-started/introduction)）。
Linuxの標準的な「拡張デスクトップ」機能で各出力に別々の内容を描画でき、特殊な裏技は不要。

さらに、既存の調査記録（6章）で判明済みの通り、`video-streamer`の「データ焼き込み」は
**race_captureアプリが今まさに画面に描画しているダッシュ画面そのものを、X11の`ximagesrc`で
そのままキャプチャする方式**であり、裏で別レイアウトを合成する仕組みではない。つまり
配信用と表示用を分けるには、「別々の出力に、別々のレイアウトのrace_captureをそれぞれ
全画面表示し、配信用の出力だけをキャプチャする」という構成が唯一の実現方法であり、
**ユーザーの想定していた「マルチディスプレイ操作」が構造的に必須**だったことが分かった。

配信用の出力に物理モニターを車内にもう1台置きたくなければ、想定通り**ダミーHDMIプラグ
（EDIDエミュレータ）**でOSに「モニターが繋がっている」と錯覚させれば、実際に運転者が見る
モニターは1台のままで完結する。

### 8.3 最重要確認事項：race_captureアプリを2インスタンス同時起動できるか

上記の構成を実現するには、**race_captureアプリを2つのプロセスとして同時起動し、それぞれ
別出力・別レイアウトで動作させられるか**が技術的な生命線になる。この確認が取れなければ
分離構想自体が成立しないため、GPU描画確認（DC-9-3）以上に優先度の高い最重要事項と位置づける。

机上調査（Web調査ベース、ROCK 5B実機未着手）で分かったこと・懸念点は以下の通り。

#### (a) Kivyのマルチウィンドウ制約とワークアラウンド

Kivyフレームワーク自体は**1プロセス＝1ウィンドウという設計で、ネイティブなマルチウィンドウ
機能を持たない**。ただし、Kivyコミュニティでは「別々のプロセスとして複数のKivyアプリを
起動し、それぞれ異なる`DISPLAY`環境変数や`Config`のウィンドウ位置設定(`graphics`の`top`/
`left`)で別モニタに配置する」というワークアラウンドが確立されている。**「2インスタンス
同時起動」というアプローチ自体はKivyアプリとして正攻法**であり、目新しい裏技ではない。

#### (b) 設定ファイル（ゲージレイアウト）の分離

Kivy標準の設定ファイルは`~/.kivy/config.ini`だが、`KIVY_HOME`環境変数で保存先ディレクトリを
変更できる（Kivy標準機能）。2インスタンスをそれぞれ別の`KIVY_HOME`で起動すれば、Kivy自体の
設定競合は回避できる見込み。ただし、`race_capture`アプリ固有の設定・ゲージレイアウトの
保存先が`~/.kivy/`配下なのか、独自パス（`task_dashcam_breakdown.md`のDC-6-6-6で実際に
使われている`~/.config/racecapture`という独自ディレクトリの可能性が高い）なのかは未確認。
独自パスの場合、`KIVY_HOME`だけでは解決せず、race_capture独自の設定パス指定手段
（環境変数・コマンドライン引数）が必要になる。**実機での確認が必須**。

#### (c) 🔵【訂正】race_captureアプリのソースコードはこのリポジトリに既にクローン済みだった

初稿では「GitHub API上で`autosportlabs/RaceCapture_App`が404だったため、ソースは
非公開になった」と誤って結論づけていたが、**このリポジトリ自体に`reference/RaceCapture_App`
というgit submoduleとして既にクローンされていた**ことをユーザーの指摘で判明・訂正した
（`.gitmodules`参照。実体は`https://github.com/ryandoherty/RaceCapture_App.git`という
個人のフォークで、公式`autosportlabs/RaceCapture_App`が非公開化される前の状態を保持して
いると見られる）。GitHub API調査は`autosportlabs`組織内だけを見ており、フォークの存在と
ローカルの`reference/`ディレクトリの存在を見落としていた。**「ソースを読んで確認する」
という選択肢は現役で使える**。

実際にソースを読んで以下が確認できた（`reference/RaceCapture_App/main.py`他）：

- `main.py`の`processArgs()`に`-p`/`--port`引数があり、`init_rc_comms()`で
  `comms_factory(port)`に渡される。**シリアルポートはコマンドライン引数で明示指定できる**
- `self.settings = SystemSettings(self.user_data_dir, ...)`。`user_data_dir`はKivy標準の
  `App.user_data_dir`プロパティで、設定・トラックDB等の保存先はここに紐づく。Kivy標準の
  `KIVY_HOME`環境変数で分離できる見込みが実装からも裏付けられた
- マルチウィンドウ関連のコードは存在せず、Kivyの制約（1プロセス1ウィンドウ）通りの
  素朴な単一`App`/単一`Window`構成。8.3(a)の「複数プロセス起動が正攻法」という理解と一致

#### (d) 🔴 実装で裏付けられた最大の懸念：ESP32/RaceCapture実機とのシリアル接続競合

`autosportlabs/comms/serial/serialconnection.py`の`SerialConnection.open()`は
`serial.Serial(device, timeout=..., write_timeout=...)`という`pyserial`の素朴な呼び出しの
みで、**`TIOCEXCL`等のOSレベル排他ロックは一切実装されていない**。さらに
`autosportlabs/comms/comms.py`を見ると、接続確立後は専用のサブプロセス
（`connection_message_process`）が常時`read_line()`ループを回し続けて改行区切りの
メッセージをストリーム的に読み取る設計になっている。

これにより、**2つのrace_captureインスタンスが同じシリアルポートに同時接続した場合、
カーネルの入力バッファから来るバイト列を2つの独立した読み取りループが競合的に消費し、
メッセージが分断・破損する可能性が高い**ことが、推測ではなく実装の構造から論理的に
裏付けられた。これは今回の分離構想における最大のリスクのまま変わらない。

公式のRaceCapture Pro/Track/Apex/MK2は「WiFi/Bluetoothで最大2〜4台の受信側に同時配信」
という設計を持つが（[EvolutionMフォーラムでの実演事例](https://www.evolutionm.net/forums/motor-sports/740681-racecapture-pro-multi-display-demo.html)）、これは公式ハードウェア側の機能であり、
**今回自作しているESP32-C3代替ファームウェア（[firmware/src/main.cpp](firmware/src/main.cpp:1444)）はUSB接続のみの設計でWiFi/
Bluetoothを持たない**ため、公式機のような複数配信機構には頼れない。

回避策の候補（優先度順）：

1. 🔴 **【訂正】単純な`socat`によるポート複製では解決しない**：当初「`socat`でシリアル
   ポートを仮想的に複製すれば読み取り専用の複製で足りる」と考えていたが、追加調査の結果、
   **`socat`の標準的な複製構成（`TCP-LISTEN,fork`や単純な`PTY`作成）は「1つのソースの
   データを複数の購読者で奪い合う」形になり、シリアル直結と同じ分断問題が起きる**ことが
   判明した。「1つのソースから複数の購読者へ“同じ”データを配信する」ブロードキャストは
   単純な複製コマンドでは実現できない
2. ✅ **正しい設計方針：gpsd型のfan-outブリッジデーモンを自作する**。GPSデバイス用の
   定番デーモン`gpsd`は「1つのデーモンプロセスだけがシリアル/USBデバイスを排他的に読み、
   読み取った内容を複数のクライアントに配信する」という構成（fan-out architecture）を
   取っており、これが本件の正解パターンと判断できる。具体的には、①専用のブリッジ
   プロセス（Pythonで数十行程度の自作で足りる規模）がESP32実機のシリアルポートを
   唯一読み取り、②受信した行を複数の仮想シリアルポート（`socat PTY,link=/dev/ttyV0`等で
   作成）へ複製して書き込み、③各race_captureインスタンスは`--port /dev/ttyV0`
   `--port /dev/ttyV1`のように別々の仮想ポートを読む、という構成。双方向の書き込み
   （race_capture側からのコマンド送信）は今回の用途（表示のみ、設定変更なし）では
   基本的に発生しない想定のため、まずは読み取り方向（実機→race_capture）のfan-outだけ
   自作すれば足りる可能性が高い
3. 将来的にファームウェア側でWiFi配信機能を追加する（当面の対象外、大きな設計変更）
4. `reference/RaceCapture_App`のソースが読めるため、`SerialConnection`/`Comms`クラス
   自体に「1つの接続から複数の購読者にメッセージをブロードキャストする」機能を
   自分たちで追加改造するという選択肢も、(c)の訂正により現実的な選択肢に浮上した
   （フォーク元のライセンス確認は必要。ただし②のブリッジデーモン方式の方がrace_capture
   本体の改造が不要で影響範囲が小さく、優先度は②の方が高い）

#### (e) video-streamer側のキャプチャ範囲

`video-streamer`が使うGStreamerの`ximagesrc`要素自体には特定ウィンドウ（XID）だけを
キャプチャする機能があるが、`video-streamer`の設定ファイル（`video-config.ini`）で
これが指定可能かは、クローズドバイナリのため不明（[配布リポジトリ](https://github.com/autosportlabs/racecapture_video_data_livestreaming)には
インストールスクリプトのみでREADME以外の設定サンプルなし）。ただし、**配信用インスタンスの
出力先を専用の出力（ディスプレイ）に固定する設計であれば、ximagesrcはデフォルトの
ルートウィンドウキャプチャのままでよく**、xidプロパティに頼る必要はない見込み
（＝出力を分ければこの懸念は実質解消する）。

#### (f) 検証はROCK 5B到着済みだが、Raspberry Piでも先行して着手できる可能性

DC-9-1（手元のRaspberry Pi単体での先行検証）は、実はこのマルチインスタンス・
マルチディスプレイ検証にも使える可能性が高い。**Raspberry Pi 4/5はマイクロHDMI×2ポートで
2系統の独立ディスプレイ出力に対応**しており、ROCK 5B同様の検証環境として使える。
ただし、Raspberry Pi版とROCK 5B版のrace_captureバイナリ・OS（Raspbian vs Radxa OS/Debian）は
別物であり、x86→ARMほどの隔たりはないにせよ、**Raspberry Piでの検証結果がそのまま
ROCK 5Bに転用できる保証はない**点は既存の注意点（DASHCAM_ROCK5B_REPORT.md等）と同様。

#### (g) 🔴 新論点：ROCK 5Bのスペックで2インスタンス同時稼働の余力があるか（2026-08-15追記）

`DASHCAM_ROCK5B_SOFTWARE_HURDLES.md`4章のCPU/メモリ検討は「race_capture 1インスタンス＋
エンコード」を前提にしたものであり、2インスタンス化での追加負荷は未検討だった。整理すると：

- **メモリ**：1インスタンスで2GB未満の実績があるため、2インスタンスでも4GB未満で収まる
  見込み。8GBモデルなら比較的楽観視できる
- **エンコード（VPU）**：8K30対応でオーバースペックのまま変わらず、CPUを圧迫しない
- **CPU（シングルコア、既存最大の懸念）**：ROCK 5B（Geekbench6シングルコア約849）は
  公式最小要件Core i5-6500（約2,200前後）よりかなり弱く、1インスタンスの時点で
  「race_captureのGUI描画ループがボトルネックになるリスク」が指摘されていた。Kivy
  プロセスが2つに増えると単純には負荷が倍増するが、ROCK 5Bは**4×Cortex-A76（高性能）＋
  4×Cortex-A55（高効率）のbig.LITTLE構成**のため、`taskset`/cgroupsで2インスタンスを
  それぞれ別のA76コアに固定すれば「1コアの奪い合い」は回避できる見込み
- 🔴 **未知数：Mali G610（Panfrost/Panthorドライバ）での複数プロセス同時描画の実効性能**。
  Web調査では、PanthorカーネルドライバがMali-G610でOpenGL ES 3.1公式適合を達成したという
  情報（2024年、[Collabora記事](https://www.collabora.com/news-and-blog/news-and-events/taming-the-panthor-opengl-es-31-conformance-achived-mali-g610.html)、テスト環境はまさにROCK 5B）は見つかったが、
  **複数プロセス・複数EGLコンテキストを同時実行した際のパフォーマンス特性についての
  公開情報は見つからなかった**。そもそも1インスタンスでの描画自体が未検証（ハードル①）
  なので、この点は実測以外に確認する方法がない
- 画面キャプチャ（`ximagesrc`または自作RKMPPパイプラインでのキャプチャ）は配信用の
  1画面のみが対象のため、2画面分キャプチャする必要はなく、負荷は増えない見込み

対応策の候補（既存4章の対応策の延長）：`taskset`/cgroupsでのコア固定・CPUガバナー
`performance`固定、解像度/フレームレート低減、表示用ダッシュのレイアウトを配信用より
軽量にする（重いグラフ/マップ描画は配信用のみに限定する等）。

**結論として、絶望的に足りないと判断する材料はないが、「余裕」とも言い切れず、実測でしか
判断できない**。DC-9-1に「2インスタンス＋エンコード＋配信を同時実行した際のCPU/GPU負荷
実測（`mpstat -P ALL`、体感フレームレート等）」を検証項目として追加する。

#### (h) EliteDeskでの先行検証の実現性とDC-2の既知の注意点

DC-9-1-b（2インスタンス同時起動＋別出力＋別レイアウト）・(g)のCPU負荷検証の一部は、
Kivy/pyserierの挙動に依存するためROCK 5B（ARM）を待たずに**EliteDesk（x86、既に
race_capture動作実績あり、DC-6-6-7）で先行して着手できる**。

- **マルチディスプレイ出力**：EliteDesk 800 G3（Mini型ではなく通常サイズ＝SFF/Tower系）は
  背面に**DisplayPort×2ポートを標準搭載**しており（DC-6-1で判明済み）、2系統独立出力の
  検証環境として使える
- ⚠️ **既知の注意点（DC-2で未解決のまま保留中）**：過去にDP→D-Sub変換アダプター経由・
  VGA直結経由いずれでも、BIOS/HPロゴまでは表示されるが**Ubuntu起動直後に信号が消える**
  症状が発生し、原因未特定のまま「SSH中心の運用に切り替え、車載本番接続時に再検討」と
  して保留していた。マルチディスプレイ検証で物理モニターへの表示確認まで行う場合は、
  この既知の問題を踏まえ、DPケーブル直結（D-Sub変換アダプターを介さない）で改めて
  試す・`video=`強制モード指定を再検討する等の対応が必要になる可能性がある。ただし
  DC-6-6-6/DC-6-6-7では「物理モニター非接続のままEDID偽装でXサーバーを起動し、
  race_captureの動作自体は確認できた」という実績があるため、**物理モニター表示に
  こだわらなければ（EDID偽装のみで）2出力分のXサーバー起動・race_capture動作確認自体は
  可能**と見込まれる
- CPU/GPU負荷実測（(g)参照）はIntel UHD Graphics 630（EliteDesk搭載）とMali G610
  （ROCK 5B）で特性が全く異なるため、**EliteDeskでの負荷実測結果はROCK 5Bにそのまま
  転用できない**点に注意。あくまで「Kivyマルチプロセス化・シリアル競合・ブリッジ
  デーモンの設計・動作ロジック」の先行検証と割り切る

### 8.3.5 EliteDeskでの実測結果(2026-08-17)

DC-9-1-a〜cをEliteDesk（`dashcam-test`、SSH経由でClaude Codeから直接操作）で実際に検証した。
結論から言うと、**(b)(c)とも単純な実装では機能せず、いずれも設計の見直しが必要**と判明した。

**(a) マルチディスプレイのハードウェア/OS動作は問題なし**：`xrandr`で確認したところ、
DP-1（primary、1920x1080+0+0）・DP-3（1920x1080+1920+0）が正しく拡張デスクトップとして
認識されていた。DC-2で懸念されていた「起動直後に信号が消える」問題は、この機体・
この接続では再現しなかった（今回はDP直結×2、DP→D-Sub変換アダプターは使用していない）。

**(b) ウィンドウの別出力配置は失敗**：2インスタンス目を別`KIVY_HOME`（`~/.kivy2`）で用意し、
`config.ini`の`[graphics]`セクションを`position=custom, left=1920, top=0`に設定して起動したが、
実際には**2つ目のウィンドウも1つ目と全く同じ座標`(0,0)`に重なって表示された**
（`xwininfo`で確認）。タイル型WM`ratpoison`がフローティング位置指定を無視し、単一フレーム
（画面全体をカバー）の原点に新規ウィンドウを配置する挙動によるものと推測される。
`ratpoisonrc`にフレーム分割の設定はなく、デフォルトの単一フレーム構成だった。
🔵 **対応方針（ユーザー確認済み・採用）**：`video-streamer`はrace_captureの描画結果を
X11の`ximagesrc`で画面キャプチャするだけなので、配信用インスタンスは物理モニターに
出す必要がない。ratpoisonと戦うのではなく、**配信用インスタンスはXvfb等のヘッドレス
仮想ディスプレイ（`DISPLAY=:1`等）上で起動し、走行中表示用インスタンスのみ物理モニター
（`DISPLAY=:0`、ratpoison管理）に出す**設計に変更する。本番でも仮想/ダミーディスプレイを
使う方針のため、この方式で違和感はない。ratpoisonのフレーム分割による解決は不採用。

**(c) fan-outブリッジのプロトタイプ実装・実機検証で新たな壁を発見**：
`serial_fanout_bridge.py`（リポジトリ直下に追加）を実装し、`pty.openpty()`で仮想ポートを
2つ作成、実ポート（`/dev/ttyACM0`）から読んだバイト列を両方へブロードキャストする方式で
実機検証した。

1. **シリアル競合の実害を実証**：ブリッジなしで2インスタンスを同時に直結させる比較実験
   （本来の目的とは別に、競合の実害を確認する目的で先に実施）では、2インスタンス目だけ
   でなく**本番側（1インスタンス目）にもデータ破損が波及**した
   （`SampleMetaException`多発、`sqlite3.IntegrityError: NOT NULL constraint failed:
   datapoint.sample_id`でセッション記録DBへの書き込み失敗）。fan-outブリッジが
   必須であることが実機で裏付けられた。
2. 🔴 **読み取り専用のfan-out設計そのものが機能しないことが判明**：`HANDOFF.md`によると
   RCPプロトコルは**race_capture側が約1Hzで`getStatus`等をポーリング送信し、ESP32が
   応答するpull型**。ブリッジが実ポートを読み取り専用で掴んでいても、誰もコマンドを
   送らなければESP32は何も応答しない。実機検証でも仮想ポート経由の受信は**0バイト**
   だった。当初「書き込み方向（コマンド送信）は表示専用用途では不要」としていた前提が
   誤りだった。
3. **次回への対応方針**：ブリッジ自体が唯一のRCPクライアントとして振る舞う設計に変更する。
   ブリッジが定期的にポーリングコマンドをESP32へ送信し、応答を全consumerへブロードキャスト。
   race_capture各インスタンスが仮想ポートへ書き込んでくる（自分自身のつもりの）ポーリング
   コマンドは実ポートへは転送せず握りつぶす（実ポートへの書き込みは常にブリッジの1箇所に
   一元化し、書き込み競合も回避する）。
4. 🔵 副次的な有用情報：`rcpapi.py`のソースで、自動検出時に`last_known_device`
   （ユーザー設定に保存）が`get_available_devices()`の一覧に存在しなくても候補の先頭に
   追加されることを確認済み（[rcpapi.py:672-682](reference/RaceCapture_App/autosportlabs/racecapture/api/rcpapi.py)）。
   仮想ポート（`/dev/pts/N`、udev経由の一覧には出てこない可能性が高い）を各インスタンスに
   認識させる手段として、この仕組みが使える見込み。

**動画のローカル保存について**：`~/Desktop/video-config.ini`に`[local_recording]`
（`video_dir`・`segment_length_sec`）と`[streaming]`が独立したセクションとして
存在しており、ローカル録画自体はDC-6-6-7で動作実績済み。ユーザーはセルラー回線の
帯域を考慮しYouTube Live配信をやめてローカル保存中心にする方針を検討中だが、
「録画映像にもゲージを重ねて焼き込みたい」という要望は残るため、
**配信の有無にかかわらず2インスタンス分離（(b)(c)）自体は引き続き必要**と確認した。

### 8.4 まとめ・優先度

この「2インスタンス同時起動＋別出力＋別レイアウト」の検証は、**GPU描画確認（DC-9-3）と
並ぶ、あるいはそれ以上に構想全体の前提を左右する最優先確認事項**と位置づける。特に
(d)のシリアル接続競合は、GPU描画問題（回避策が複数あり詰まっても対応可能）とは異なり、
**実装（`pyserial`の素朴な呼び出し・排他ロックなし）から見て高確度で問題が起きると
見込まれる**という点でリスクの質が異なる。幸い(c)の訂正により、`reference/RaceCapture_App`
のソースが読める状態にあるため、回避策（`socat`複製、または`Comms`クラス自体の改造）の
検討は「ソースが読めない中での試行錯誤」よりずっと見通しが立てやすい。
`task_dashcam_breakdown.md`のDC-9-1にこの検証を明記し、ROCK 5B/Raspberry Pi問わず
何か具体的な作業に着手する前に最優先で確認する方針とする。

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
- [Product Introduction | Radxa Docs (ROCK 5B、3系統独立ディスプレイ出力の記載)](https://docs.radxa.com/en/rock5/rock5b/getting-started/introduction)
- [RaceCapture/Pro Multi-Display Demo - EvolutionM（公式ハードウェアのWiFi/Bluetooth複数配信について）](https://www.evolutionm.net/forums/motor-sports/740681-racecapture-pro-multi-display-demo.html)
- [autosportlabs/RaceCapture_App - Wayback Machine 2018年6月時点のアーカイブ（現在はGitHub上で404）](http://web.archive.org/web/20180611003737/https://github.com/autosportlabs/RaceCapture_App)
- [Multiple monitor problems - Kivy Users Google Group](https://groups.google.com/g/kivy-users/c/hav2pvRoIa4)
- [Taming the Panthor: OpenGL ES 3.1 conformance achieved on Mali-G610 - Collabora（ROCK 5B実機でのPanthorドライバ検証）](https://www.collabora.com/news-and-blog/news-and-events/taming-the-panthor-opengl-es-31-conformance-achived-mali-g610.html)
- [The Architecture of Open Source Applications: GPSD（fan-out型ブリッジデーモンの設計参考）](https://aosabook.org/en/v2/gpsd.html)
