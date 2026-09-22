# 市販レーシングダッシュのUIを「実際に動かして」学ぶ方法 — 調査メモ（2026-09-22）

> 目的：自作ロガーの表示系UI（特に**物理ボタンで操作するダッシュ**）を設計するにあたり、
> RaceBox / AiM / MoTeC 等のUIを**実機を買わずに動かして確認する**手段を洗い出す。
> 位置づけ：ARCHITECTURE.md 8章の「サブファイル（詳細・作業用）」。結論が固まったら
> 該当PhaseのタスクとしてARCHITECTURE.mdへ転記する。
> ステータス：**調査のみ。まだ何も試していない**（各項目の「検証状況」参照）。

---

## 0. 結論（最短ルート）

| 順位 | 手段 | 何が分かるか | コスト |
|---|---|---|---|
| ① | **ECUMaster ADU の設定ソフト（ADU Client）** | 実機なしでPC上にダッシュ画面を描画し、**チャンネル値と物理ボタン押下をシミュレート**できる。＝「ボタンでページが切り替わる」挙動そのものを体験できる | 無料・Windows |
| ② | **MoTeC Display Creator** | 純正サンプルレイアウトが同梱。**DC Simulate / i2再生**でログを流し込み、走行中に画面がどう動くかを再生できる | 無料・Windows |
| ③ | **ESP32でRaceBox Miniをエミュレート** | 純正RaceBoxアプリを実機同様に動かせる。手持ちのESP32でできる（`rcp_mock_device.py`と同じ発想） | 無料（手持ち機材） |
| ④ | **各社の取扱説明書PDF** | ボタン操作の**一次資料**。ページ遷移・メニュー階層・長押しの定義が全部書いてある | 無料 |
| ⑤ | **中古実機を1台** | 視認性・押し心地・手袋での操作性は実物でしか分からない | 1〜3万円程度 |

**物理ボタン操作のUXを知るという目的に対しては①が本命**、画面デザインのカタログ収集は②③④が効く。

---

## 1. PC上で実機なしにダッシュUIを動かせるソフト

いずれもWindows専用。手元はLinux中心のため **Wine もしくは Windows VM** が前提になる（未検証）。

### 1-1. ECUMaster ADU Client（ADU5/ADU7用）★最重要
- ダッシュのページを作る設定ソフト。**アラームのプレビュー**と、**オフライン時にボタン入力をシミュレートして
  プレビュー画面上で機能の挙動を確認する**機能があるとされる。
- ADUは**本体3ボタン＋CANキーボード対応**という構成で、こちらが作ろうとしているものに一番近い。
- 入手：ECUMaster のソフトウェアダウンロードページ（無料）。
- 検証状況：**未検証**。①アカウント登録なしで落とせるか ②ボタンシミュレーションがどこまで再現するか
  （ページ送り／メニュー階層／長押し）を実際に触って確認すること。

### 1-2. MoTeC Display Creator（C125/C127/C1212用）
- **無料ダウンロード＋サンプルレイアウト同梱**。ゲージ・警告画面・レイアウトを自作できる。
- **DC Simulate**：i2で再生したログを流し込み、「その瞬間ダッシュに何が出ていたか」を映像と突き合わせて
  再現できる。＝**走行中の情報密度・警告の出方**を静止画ではなく動きとして観察できる。
- 注意：作ったレイアウトを**実機C125へ入れるには有償のenable code**が必要。ただし**PC側の設計・シミュレーション
  だけなら不要**（＝今回の目的には十分）。
- 入手：motec.com.au/downloads（Display Creator 64bit）。

### 1-3. AEM DashDesign（CD-5/CD-7用）
- 無料。ライト／ダーク、ハイコントラスト、アナログ風／デジタル風など**テンプレートが大量に同梱**されており、
  「同じ情報をどう見せ分けるか」のカタログとして優秀。サーキット・ドラッグ・オフロード等の用途別レイアウトもある。

### 1-4. AiM Race Studio 3（MX系用）
- 無料。MXm/MXG/MXS等の**カスタムページを設計し、プレビューできる**。
- 補助ツールとして、ブラウザで動くサードパーティのレイアウトエディタ `dasheditor.speedfreaks.no`（AiM dash用）もあり、
  RS3からエクスポート→編集→再インポートという運用が紹介されている。
- 併せて **Race Studio Analysis** にはデモデータが付属し、解析側UIも触れる。

### 1-5. SimHub（sim racing用・無料）
- **DashStudio**で自作ダッシュを作れるうえ、コミュニティ製の**実機レプリカ・ダッシュが大量に公開**されている
  （例：「MoTeC C127 SimHub Dash」＝実機を参照して作られたレプリカ）。
- ゲームのテレメトリで駆動するのが本来の使い方だが、**レプリカのレイアウトをXML/デザイナ上で解剖できる**のが価値。
  「実機のどのページに何が並んでいるか」を無料で分解して読める。

### 1-6. RealDash（無料・スキン多数）
- **RealDash CANプロトコル**という公開仕様があり、Arduino/ESP32からシリアル・BT・WiFiで値を流し込める。
- つまり **自作ロガーの値で市販品風スキンを動かす**ことが即座にできる。UIの「良し悪し」を自分のデータで
  評価できるので、模倣対象の選定に向く。ただし操作はタッチ前提。

---

## 2. RaceBox：ESP32でエミュレートして純正アプリを動かす

- 公開実装：`github.com/anchit92/ESP32-RaceBox-mini-Emulator`（ESP32＋u-blox GNSS＋MPU6050、部品代$40以下）。
- 仕組み：**BLEでRaceBox Miniとして名乗り**、88バイトのGNSS＋IMUパケットを25Hzで送る（Nordic UART Service
  `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`）。RaceBox社は**BLEプロトコル仕様書を公開**している（racebox.pro）。
- 対応アプリ：Solostorm / RaceChrono / RaceChrono Pro / NMEAconnect / AutoX DL / **RaceBox純正アプリ**。
- 既知の制約：**デバイスIDを4000000000以上にすると純正アプリが接続を拒否する**。`RaceBox Mini ` の接頭辞は変えない。
- このプロジェクトとの相性：**GNSSもIMUもエミュレータ側で捏造できるので、GPSモジュール未調達（Phase1-5未完）でも
  ラップタイム表示・デルタ表示のUXを体験できる**。`rcp_mock_device.py`でRaceCapture純正アプリを動かしたのと
  まったく同じ手口。
- 検証状況：**未検証**。手持ちのESP32-C3/S3で、GNSS実機なし（座標を合成コース上で動かす）でどこまで動くかを試す価値が高い。

---

## 3. 一次資料としての取扱説明書・動画

- **AiM MX 1.2 Strada シリーズ ユーザーガイド**（support.aimshop.com / aim-sportline.com に公開PDF）：
  「**システムボタンは4つ、5つ目はバックライト、6つ目は区間オドメータのリセット**」「Menuボタンを押すとこの画面が出る」
  といった記述があり、**ボタン割り当てとメニュー階層がそのまま書かれている**。模倣するならこれが最も確実な一次資料。
- **MoTeC C125 User Manual**（motec.com.au に公開PDF）：ボタン・オプションのロータリースイッチの扱い、
  アラームの確認（acknowledge）操作などが載っている。
- YouTubeの実機操作動画（例：ECUMaster ADUの設定ウォークスルー、Race Studio 3のダッシュ設定）で、
  **押す→何が起きるか**のリズムを確認できる。静止画のマニュアルでは分からない部分。

---

## 4. 物理ボタンUIの共通パターン（各社から抽出）

「かっこいいポチポチ操作」を実現するために、市販機がほぼ例外なく採っている構造：

1. **ソフトキー方式**：画面の端にラベルを出し、その真下（横）の物理ボタンに割り当てる。
   ボタンの意味が**画面ごとに変わる**ので、少ないボタン数で階層メニューが成立する（AiM MX系の4ボタンが典型）。
2. **ボタン数は3〜4個に絞る**。グローブ着用・振動下での誤操作を避けるため、1操作=1機能を守る。
   同時押しは使わない。長押しは「メニューに入る／リセット」程度に限定する。
3. **走行中モードとピットモードを分ける**。走行中に触れるのは「ページ送り」「ラップリセット」
   「アラーム確認」だけ。設定変更や消去は停車中しか入れない。
4. **アラーム確認（acknowledge）ボタンは必須**。警告が出っぱなしで画面を占有すると逆に危険。
5. **ロータリー（回転ノブ）の分離**（MoTeC C125のオプション）：選択＝回す、決定＝押す、に分けると
   メニューが深くても操作が破綻しない。ボタン3個で階層を深くするより快適。
6. **ページは環状（ラスト→先頭へ戻る）**。「戻る」ボタンを使わずに全ページへ到達できるようにする。

---

## 5. このプロジェクトへの当てはめ

現状の構成（ARCHITECTURE.md 2章・3章、task_phase4_breakdown.md 4-4-2、task_phase6_breakdown.md）：
- 表示ユニット＝Raspberry Pi＋**公式RaceCapture App（Kivy）**。タッチ前提のUIで、かつMesa VC4の描画問題に苦戦中。
- Phase 6で**高輝度サブディスプレイ（デルタタイム等）をCANノードとして増設**する構想があり、
  ロガー側のCANブロードキャスト（6-3）とチャンネルテーブル（6-1）は実装済み。

### 案A：公式アプリはそのまま、物理ボタンをキーボード入力にマップする（最小コスト・即効）
- 逆コンパイル調査で判明済みの内蔵ショートカット（`a`=Analysis / `d`=Dashboard / `s`=Setup /
  `p`=Preferences / `t`=Status / `Esc`=Home）を、**GPIOのタクトスイッチ→uinput経由のキーイベント**として
  そのまま叩けばよい。アプリを一切改造せずに「ポチポチ操作」が成立する。
- しかも task_phase4_breakdown.md 4-4-2 の残作業③「車載時（キーボードなし）のHomeへの戻り導線」が
  **同時に解決する**。費用対効果が突出して高い。
- Dashboard内のページ送り（Carousel）にショートカットがあるかは未確認。無ければ合成スワイプ、
  もしくはKivy側への最小パッチで対応する。
- **これは案Bの前段としても有効**（ボタン数・配置・長押しの要否を実車で先に確かめられる）。

### 案B：Phase 6のCANサブディスプレイを「自作ダッシュUI」の本命にする（本丸）
- ロガー本体は既に全チャンネルを外部CANへ流せる（6-3）ので、**表示側MCUは受信して描くだけ**。
  UIの実験場としては理想的に切り離されている。
- ここに4節のパターン（ソフトキー3〜4個、走行中/ピットモード、環状ページ）を適用する。
- 開発時の検証は実車不要：ロガー本体をモック値で走らせれば、CAN経由で表示側だけ延々と作り込める。

### 案C：公式アプリを置き換える自作フルダッシュ
- コストが大きく、公式エコシステム活用というプロジェクトの基本方針（1章）に逆行するため**現時点では非推奨**。
  案Bのサブディスプレイが育ってから改めて判断する。

---

## 6. 次の一手（推奨順）

1. ADU Client と Display Creator をWindows VM/Wineへ入れ、**ページ遷移とボタン挙動のスクリーンショットを収集**して
   「UI要素カタログ」（どの値を何桁で、どこに、どの優先度で置くか）を作る。
2. AiM MX 1.2 ユーザーガイドPDFから、**ボタン割り当て表とメニュー階層図**を書き起こす。
3. 手持ちESP32でRaceBoxエミュレータを動かし、純正アプリでラップ／デルタ表示のUXを体験する。
4. Raspberry Piで **GPIOボタン→キーイベント**のブリッジを作る（案A）。ここまでで「物理ボタンで操作できるダッシュ」が
   一度成立する。
5. 1〜4を踏まえ、Phase 6サブディスプレイのUIワイヤーフレーム（ページ構成・ボタン割り当て）を起こす。

---

## 7. 注意点

- **模倣の範囲**：情報設計・操作体系（何をどこに置くか、ボタンで何をするか）を学ぶのは問題ないが、
  **画面デザインそのもののコピー、ロゴ・アイコン画像の流用、商標的な見た目の再現は避ける**。
- 各社の設定ソフトは**実機を持たない人が使ってよいか**の条項を確認してから使う（無料配布＝無制限ではない）。
- RaceBoxエミュレータは**自分の端末で自分のアプリを動かす範囲**で使う。デバイスIDの制約に注意。
- Windows専用ソフトが多いため、**Wine/VMの構築コスト**を先に見積もること。

---

## 参考リンク

- MoTeC Display Creator: https://www.motec.com.au/displaycreator/ ／ ダウンロード: https://www.motec.com.au/downloads
- MoTeC C125 User Manual: https://www.motec.com.au/hessian/uploads/C125_User_Manual_1f4a1c6bf4.pdf
- ECUMaster ADU: https://www.ecumaster.com/products/adu/ ／ ソフト: https://ecumasterusa.com/pages/software-downloads
- ECUMaster コミュニティ（チャンネル・ボタンのシミュレーション）: https://community.ecumaster.com/t/channel-simulation/3377
- AiM Race Studio 3: https://community.aimshop.com/software/racestudio-3
- AiM MX 1.2 Strada ユーザーガイド: https://support.aimshop.com/product-documentation/pdf/MXS_1.2/1_USER_GUIDE.pdf
- AiM用 DashEditor（ブラウザ）: https://dasheditor.speedfreaks.no/
- AEM DashDesign（CD-7製品ページのInstructionsタブから無料DL）: https://www.aemelectronics.com/
- RaceBox BLEプロトコル仕様: https://www.racebox.pro/products/mini-micro-protocol-documentation
- ESP32 RaceBox Mini エミュレータ: https://github.com/anchit92/ESP32-RaceBox-mini-Emulator
- SimHub DashStudio: https://github.com/SHWotever/SimHub/wiki/Dash-Studio ／ MoTeC C127レプリカ: https://www.overtake.gg/downloads/motec-c127-simhub-dash.23641/
- RealDash CANプロトコル: https://realdash.net/manuals/realdash_can.php
