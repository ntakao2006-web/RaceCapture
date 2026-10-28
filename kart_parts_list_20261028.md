# カート用ロガー 試作0号 部品リスト（KT-2-1、2026-10-28）

> `kart_logger_study_20261027.md`8章の構成を、実際に買える部品に落としたもの。発注はユーザー（KT-2-2、11/5まで）。
> 価格と在庫は**2026-10-28に各店のページで見た値（税込）**。注文の前にもう一度確かめる。
> ステアリング角の部品も入れてある（2026-10-28 ユーザー決定）。
> 2026-10-28夕に改訂：
> - u-bloxのM10はGPSだけなら25Hzが出る（最初の版の「18Hzが上限」は古いデータシートの値で誤り。2章）
> - **基板（電子部品が載った板）は、DigiKey・Mouser・RSコンポーネンツなどの正規の店だけで買う**（ユーザー判断。Amazonの安い基板は偽物のチップが付いてくることが多いため）。
>   これに合わせ、GNSSをu-blox NEO-M9N（SparkFun）、ステアリング角のAS5600をAdafruitの基板に替えた。
>   Amazonで買うのは、電池・CHTセンサー・ボタン・コネクタ・ベルト・プーリーなど、基板ではないものだけ

## 0. 先に結論

- 店は**DigiKey・秋月・Amazon**の3つと、近所のホームセンター。合計は**約5.8万円**＋秋月の送料（うちステアリング角が約7,500円）。
  調査資料の見込み（2〜4.5万円＋ステアリング角3,000〜5,000円）を超えた。いちばん大きいのはGNSS（基板とアンテナで約1.7万円）
- **センサーを付けない最小の構成（GPSのラップと画面だけ）なら約3.6万円**（5章）
- **画面（Adafruit 4694）だけは今週中に頼む。** 国内の在庫がほぼ無い（DigiKeyとマルツは在庫0、DigiKeyは11/11に1個入荷予定）。
  11/5まで待つと手に入らないおそれがある（1章）
- 構成を2つ変えた（2章）
  - マイコン：手持ちのDevKitC-1ではなく、**電池の充電回路が入ったAdafruit ESP32-S3 Feather**（約3,200円）。
    DevKitC-1だと充電回路と5Vへの昇圧回路を別に買うことになり、値段はほぼ同じで配線が増える。DevKitC-1は部品が届くまでのファーム作りに使う
  - GNSS：**u-blox NEO-M9N（SparkFunの基板）＋25mm角の小さいアンテナ**。4種類の衛星を全部使ったまま25Hzが出る。
    安くするなら、アンテナ内蔵のSparkFun SAM-M10Q（約9,300円。GPSだけで25Hz）もある（2章の比較）
- 11/3の採寸のあとで決めるもの：ハンドルへの取付ボルト、ステアリング角のベルトの長さ（候補は5本セットで買っておく）、車体のパイプに巻くバンドの太さ
- 回転の入力回路の部品は、回路案（KT-3、11/9以降）が決まってから秋月で買う。1〜2日で届くので11/5の注文に入れなくてよい

## 1. 画面（急ぎ）

| 店 | 価格（税込） | 在庫（10/28） |
|---|---|---|
| [DigiKey](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/4694/13157994)（品番1528-4694-ND） | 8,150円 | **0個**。11/11に1個入荷予定 |
| マルツ（DigiKeyの在庫を売っている） | 9,302円 | 0個 |
| [Mouser](https://www.mouser.jp/ProductDetail/Adafruit/4694)（品番485-4694） | 未確認 | 未確認（自動では開けなかった。ブラウザで開いて確かめる） |
| 海外：[The Pi Hut](https://thepihut.com/products/adafruit-sharp-memory-display-breakout-2-7-400x240-monochrome)（英国）、[Adafruit](https://www.adafruit.com/product/4694)（米国） | £43.20／$44.95＋送料 | 検索結果では在庫あり（日付不明） |

品名はどこも「Adafruit SHARP Memory Display Breakout - 2.7" 400x240 Monochrome」（Adafruit 4694）。

頼み方の案：

1. Mouserを開いて、在庫があればそこで頼む（国内に数日で届く）
2. 無ければDigiKeyで取り寄せる（11/11入荷の1個を押さえる）
3. どちらもだめなら海外から（1〜2週間）

- パネル単体（シャープ LS027B7DH01A）はDigiKeyに2,000個以上の在庫があり5,311円。ただし5Vの電源、信号の電圧の変換、0.5mmピッチのフィルム配線のコネクタの実装が要る。
  Adafruitの基板にはそれが全部載っている。パネル単体は、Lintarohさんに頼める状況になってから（11/9以降）の選択肢
- 画面が遅れても、ファームは画面なし（PCへの文字出力）で先に作れる。画面の表示（KT-4-2）だけを後ろへずらす

## 2. 構成を変えたところ（調査資料8章から）

| 部分 | 調査資料の案 | この部品リスト | 理由 |
|---|---|---|---|
| マイコン | ESP32-S3（手持ちのDevKitC-1） | Adafruit ESP32-S3 Feather（フラッシュ4MB・PSRAM 2MB） | リチウム電池の充電回路・残量計・USB-Cが載っている。DevKitC-1は5Vで動かす基板なので、充電回路と昇圧回路を別に買う必要があり（約3,500円）、値段は変わらず配線が増える。電池から直接3.3Vを作るので、電池も長くもつ |
| GNSS | u-blox M10系、18〜25Hz | **u-blox NEO-M9N**（SparkFunの基板、アンテナ端子付き）＋Taoglasの25mm角アクティブアンテナ | 4種類の衛星を全部使ったまま25Hzが出る（M10は衛星を増やすと遅くなる）。下の比較 |
| SD | （記載なし） | Adafruit microSD基板（SPI・SDIO両用） | ピンが足りるように、SDは画面と同じSPIの線につなぐ予定 |
| CHTセンサー | プラグの座金型（K型） | **非接地**の座金型 | 熱電対IC（MAX31855）は、測る先の金属に電気的につながった（接地型の）熱電対を読めない。座金に溶接した接地型だとエラーになる |
| ステアリング角のAS5600 | （調査資料7章） | Adafruitの基板＋直径方向に磁化した磁石（どちらもDigiKey） | Amazonの4個入りの基板をやめた（正規の店で買うため） |

### GNSSの比較（どれもDigiKeyで買える正規品。税込）

| 案 | 基板 | アンテナ | 合計 | 1秒に何回 | 向き・不向き |
|---|---|---|---|---|---|
| **A（推奨）** | SparkFun NEO-M9N、U.FL端子（[15712](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/15712/11481331)）12,865円、在庫624 | Taoglas 25mm角アクティブ（[AGGBP.25A.07.0060A](https://www.digikey.jp/ja/products/detail/taoglas-limited/AGGBP-25A-07-0060A/5287273)、線6cm）4,267円、在庫1,078 | **約17,100円** | 4種類の衛星で25Hz | アンテナを箱の天井の裏に上向きで置ける。受信がいちばん強い。U.FL端子は小さいので接着剤で固定する |
| B | SparkFun NEO-M9N、チップアンテナ付き（[15733](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/15733/11481329)） | 基板に内蔵（小さいチップ型） | 13,871円（在庫28） | 4種類の衛星で25Hz | 1枚で済むが、チップ型のアンテナはパッチ型より受信が弱い |
| C | SparkFun SAM-M10Q（[GPS-21834](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/21834/18735208)） | 基板に内蔵（15mm角のパッチ型） | 9,338円（在庫264） | GPSだけで25Hz、GPS＋Galileoで20Hz | いちばん安く1枚で済む。衛星の数を取るか速さを取るかの選択になる |

- 速さの根拠：NEO-M9Nは「4種類の衛星を同時に使って最大25Hz」（u-bloxの製品概要）。M10は、u-bloxの資料（UBX-23006557、2023-07）でGPSだけ25Hz・GPS＋Galileo 20Hz・3種類16Hz・4種類10Hz
  （古いデータシートではGPSだけ18Hz。最初の版はこの古い値を使っていた）
- 衛星の種類が多いほど、その時に見えている衛星の数が増えて位置が安定する（スタンドや木の近くで効く）。カートでは1周が短く、1点ずつの質が効くのでAを推奨
- Aのアンテナ：SparkFunの基板はU.FL端子に3.3Vを出していてアクティブアンテナが使える（SparkFunの掲示板での回答）。Taoglasのこの系統は1.8〜5Vで動く（販売店の表示。注文前にデータシートで確かめる）
- MikroeのGNSS 7 Click（NEO-M9N、8,522円）も候補だったが、端子がSMAで、DigiKeyで在庫のある短いアンテナが見つからなかった（磁石付き3mのものはGPSの帯域だけ）
- 使わないもの：Amazonのドローン用の基板（Beitian BE-250など）。ユーザー判断で、偽物のチップのおそれがあるため

ファームへの影響（KT-4-1で直す）：今の`firmware/logger_v1`はDevKitC-1（フラッシュ16MB・PSRAM 8MB）向けの設定。
Featherは4MB・2MBなので、区画の表とPSRAMの設定を合わせる。今のファームは約0.6MBなので収まる。
GNSSは25Hzの設定を入れ、通信の速さ（初期値38400bps）を115200bps以上に上げる。GNSSの電源はFeatherの3.3Vから取れる。

## 3. 注文リスト

### DigiKey（6,000円以上で送料無料。3〜4日で届く）

| 品名 | 品番 | 数 | 価格（税込） | 用途・注意 |
|---|---|---|---|---|
| Adafruit ESP32-S3 Feather with 4MB Flash 2MB PSRAM | [5477](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/5477/16583982) | 1 | 3,174円 | マイコン。在庫61 |
| Adafruit Micro SD SPI or SDIO Card Breakout Board（3V専用） | [4682](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/4682/12822319) | 1 | 635円 | SD。在庫2,585 |
| SparkFun GPS Breakout - NEO-M9N, U.FL (Qwiic) | [15712](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/15712/11481331) | 1 | 12,865円 | GNSS（2章のA）。3.3V。予備電池付きで、2回目からは数秒で位置が出る。在庫624 |
| Taoglas GNSSアクティブパッチアンテナ 25mm角 U.FL 線60mm | [AGGBP.25A.07.0060A](https://www.digikey.jp/ja/products/detail/taoglas-limited/AGGBP-25A-07-0060A/5287273) | 1 | 4,267円 | GNSSのアンテナ。GPS・GLONASS・Galileo・BeiDou。在庫1,078 |
| Adafruit AS5600 Magnetic Angle Sensor（STEMMA QT） | [6357](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/6357/26832926) | 1 | 1,079円 | ステアリング角。アナログ出力（OUT）の端子あり。磁石は付いていない。在庫496 |
| Radial Magnets ネオジム磁石 直径6×厚さ2.5mm（直径方向に磁化） | [9042](https://www.digikey.jp/ja/products/detail/radial-magnets-inc/9042/5640338) | 2 | 229円 | AS5600用。1個は予備。在庫24,214 |
| （画面をDigiKeyで頼む場合）Adafruit 4694 | 1章 | 1 | 8,150円 | 取り寄せ |
| **小計** | | | **22,249円**（画面込み30,399円） | |

- 安くするならGNSSを2章のCに替える（基板とアンテナの2行の代わりにSAM-M10Q 9,338円。約7,800円減）

### 秋月電子

| 品名 | 品番（販売コード） | 数 | 価格（税込） | 用途・注意 |
|---|---|---|---|---|
| BNO055使用 9軸センサーフュージョンモジュールキット | [AE-BNO055-BO（116996）](https://akizukidenshi.com/catalog/g/g116996/) | 1 | 2,780円 | IMU。Ver.1と同じもので、ファームの実績がある。試作0号は生データの記録だけ（調査資料1章）。単体の手持ちがあれば不要（Ver.1の基板に付いているものは現状保存のため外さない） |
| MAX31855使用 K型熱電対アンプモジュール（Adafruit 269） | [108218](https://akizukidenshi.com/catalog/g/g108218/) | 1 | 3,450円 | CHTを読む |
| 熱電対用ミニチュアコネクター パネル用 メス K型用 | [MPJ-K-F-ROHS（114971）](https://akizukidenshi.com/catalog/g/g114971/) | 1 | 680円 | ロガーの箱側。CHTセンサーを外せるようにする |
| 熱電対用ミニチュアコネクター K型用 オス | [SMPW-K-M-ROHS（114969）](https://akizukidenshi.com/catalog/g/g114969/) | 1 | 1,360円 | CHTセンサーの線の先に付ける |
| **小計** | | | **8,270円**＋送料 | |

### Amazon（本体。基板ではないものだけ）

| 品名 | ASIN | 数 | 価格（税込） | 用途・注意 |
|---|---|---|---|---|
| リチウムポリマー電池 3.7V 2000mAh 103450（保護回路付き、PH2.0） | [B0GFCZZB3D](https://www.amazon.co.jp/dp/B0GFCZZB3D) | 1 | 2,199円 | 10×34×50mm、35g。**差す前に極性を確かめる**（4章） |
| Annadue CHTセンサー K型 内径14mmワッシャー 非接地絶縁 | [B0H998JP1B](https://www.amazon.co.jp/dp/B0H998JP1B) | 1 | 1,807〜2,204円 | 種類（#1〜#3）の違いが商品ページに書いていない（線の長さの違いと思われる）。エンジンからハンドルまで届く**1.5m以上**のものを選ぶ。座金の厚さ1.5mm。届くのは11/11〜15 |
| 防水押しボタン 16mm モーメンタリ（5個） | [B086JKLWTV](https://www.amazon.co.jp/dp/B086JKLWTV) | 1 | 899円 | ボタン2つ（ラップの操作・ステアリングの0点など）。手袋で押せる大きさ |
| GX12 丸形コネクタ 4ピン（10組） | [B0C1CZ38MK](https://www.amazon.co.jp/dp/B0C1CZ38MK) | 1 | 1,414円 | ステアリング角のセンサー用。ねじ込みで振動でも外れない |
| GX12 丸形コネクタ 3ピン（3組） | [B09DPLJ22L](https://www.amazon.co.jp/dp/B09DPLJ22L) | 1 | 979円 | B入力（磁気・赤外線の受信機。今回は端子だけ） |
| GX12 丸形コネクタ 2ピン | [B0C5917BHP](https://www.amazon.co.jp/dp/B0C5917BHP) | 1 | 976円 | 回転（プラグコードに巻く線） |
| **小計** | | | **約8,300〜8,700円** | |

コネクタはピンの数を変えて、差し間違えられないようにしてある。

### Amazon（ステアリング角。基板ではないものだけ）

| 品名 | ASIN・探し方 | 数 | 価格（税込） | 用途・注意 |
|---|---|---|---|---|
| GT2 ベルト 幅6mm 閉ループ 110/200/300/400/610mm（5本） | [B0G6SFFP1Q](https://www.amazon.co.jp/dp/B0G6SFFP1Q) | 1 | 1,432円 | 長さは11/3の採寸後に選ぶ。合わない分は、柱側のプーリー（3Dプリント）の歯数と、センサーの箱の取付の長穴で調整する |
| GT2 プーリー 40歯 穴径5mm アルミ（4個） | [B0G3XXKJR2](https://www.amazon.co.jp/dp/B0G3XXKJR2) | 1 | 1,669円 | センサー側。柱側は3Dプリントの2つ割り（60歯にすると1.5倍） |
| ベアリング 625ZZ（内径5・外径16・幅5mm） | 「625ZZ ベアリング」で探す | 2個〜 | 500〜900円（未確認） | センサーの軸受け。鉄なので、磁石から10mm以上離して置く |
| アルミ丸棒 直径5mm | 「アルミ丸棒 5mm」・ホームセンター | 100mmほど | 300〜600円（未確認） | センサーの軸。磁石の近くに鉄の軸は使わない（調査資料7章） |
| **小計** | | | **約4,250円** | |

AS5600の基板と磁石はDigiKeyで買う（上の表）。

### 11/3の採寸のあとで決めるもの・近所で買えるもの（価格は目安）

| もの | 目安 | いつ・注意 |
|---|---|---|
| ハンドル中央への取付ボルト・ナット | 数百円 | 11/3にハンドル中央の取付部を見てから |
| ステンレスのホースバンド×2 | 400円 | ステアリング角のセンサーの台を車体のパイプに留める。11/3にパイプの太さを測ってから |
| M3のボルト・ナット | 300〜500円 | 2つ割りのプーリーと箱用。手持ちがあれば不要 |
| 4芯シールド線 2m | 800〜1,500円 | ステアリング角のセンサーからロガーまで。秋月・ホームセンター |
| 回転の入力回路の部品（抵抗・コンデンサー・ダイオード・シュミットトリガーのICなど） | 1,000円前後 | KT-3の回路案が決まってから（11/9以降） |
| ユニバーサル基板・ピンヘッダー・線・熱収縮チューブ | 1,000円前後 | 手持ちがあれば不要 |
| 電源スイッチ（小型のトグル） | 300〜500円 | FeatherのENとGNDの間に入れる。切ると3.3Vが止まる（切っていても充電はできる） |
| クランプ式のノイズフィルター（フェライト）×2〜3 | 300〜600円 | 回転とステアリング角の線に付ける。点火のノイズ対策 |
| 画面の前の透明板（ポリカーボネート1mm） | 500〜1,000円 | 画面のガラスを守る |
| microSDカード（高耐久、16〜32GB） | 1,000〜1,500円 | 手持ちが無ければ |

## 4. 届いたら最初に確かめること

- **電池の極性**：PHコネクタの赤・黒の並びは、メーカーによって逆のことがある。Featherの電池端子の＋−（基板に印字）と電池のコネクタの赤線の位置を見比べ、
  逆なら差さない（コネクタのピンを入れ替える）。逆に差すとFeatherの充電回路が壊れる
- **CHTセンサーが非接地か**：テスターで、熱電対の線と座金の間が導通しないことを確かめる
- **AS5600の基板**：回る向きを決めるDIRの端子がGNDにつながっているかを、基板の印刷か回路図で確かめる（浮いていると角度が安定しない）。
  出力はアナログ（OUT）を使う予定。線が1.5mほどになるので、I²Cで読むより強い（KT-4-7で決める）。
  磁石は、センサーの上で回して角度が0〜360°まで滑らかに変われば向きが正しい
- **NEO-M9N＋アンテナ**（KT-4-1の最初に、手持ちのDevKitC-1につないで見る）
  - アンテナのU.FL端子は小さく、振動で抜けやすい。差したら接着剤かカプトンテープで固定する
  - 屋外で衛星をつかむか、4種類の衛星（＋みちびき）で25回／秒出るかを見る
  - アンテナは上向きにし、上に金属を置かない（3Dプリントの箱の天井越しなら問題ない）
- Featherの充電は電流が小さめなので、空からの充電は数時間〜一晩かかる見込み（未確認）。前の日の夜に充電する

## 5. 合計

| 店 | 小計（税込） | うちステアリング角 |
|---|---|---|
| DigiKey（マイコン・SD・GNSS・AS5600） | 22,249円 | 1,308円（AS5600と磁石） |
| 画面 | 約8,150円 | ― |
| 秋月 | 8,270円＋送料 | ― |
| Amazon | 約12,750円 | 約4,250円 |
| 近所・後で | 約7,100円 | 約1,950円（シールド線・ホースバンド・M3） |
| **合計** | **約5.8万円**＋秋月の送料 | **約7,500円** |

### センサーを付けない最小の構成

GPSのラップ・セクター・走行ライン・G（GNSSから計算）・画面だけ。回転・CHT・BNO055・ステアリング角を外す。

| 店 | 買うもの | 金額 |
|---|---|---|
| DigiKey | マイコン 3,174円、SD基板 635円、画面 8,150円、GNSS 12,865円、アンテナ 4,267円 | 29,091円（送料無料） |
| Amazon | 電池 2,199円、押しボタン 899円 | 3,098円 |
| 近所 | 電源スイッチ・取付ボルト・画面の前の透明板・microSDカード・ユニバーサル基板 | 約3,000〜4,500円 |
| **合計** | | **約3.6万円**（手持ちを使えば約3.3万円。GNSSを2章のCにすれば約2.8万円） |

あとから足すときの目安：回転 約2,300円（入力回路の部品・2ピンのコネクタ・ノイズフィルター）、CHT 約7,500円、BNO055 2,780円、ステアリング角 約8,900円（4ピンのコネクタ込み）。
秋月で買うものが無くなるので秋月の送料もかからない。

減らせるところ：

- GNSSを2章のC（SAM-M10Q）にすれば約7,800円減（GPSだけで25Hz、またはGPS＋Galileoで20Hz）
- 手持ちがあるもの（microSD・ユニバーサル基板・M3・線）を使えば、約3,000円減
- コネクタを4ピンだけにすれば約1,900円減（差し間違いは色のテープで防ぐ）
- ステアリング角を試作1号へ回せば約7,500円減

## 6. 使わないもの

- 手持ちのESP32-S3-DevKitC-1：本体には使わない。部品が届くまでのファーム作りと、PCで録った走行データを流す確認（KT-4-6）に使う
- Ver.1基板（`ecologger_v1`）：調査資料8章のとおり使わない（エコラン大会後の現状保存の対象でもある）
- Amazonなどの安い基板（GNSSのBeitian BE-250、AS5600の4個入りなど）：ユーザー判断で使わない（偽物のチップのおそれ）
- 試作1号で専用基板を作るときは、GNSSのモジュール単体を別に買う（NEO-M9N-00BはDigiKeyで約2,800円）。
  試作0号の基板からモジュールを外して使い回すことはしない（外すのはまず無理）。試作0号の基板は予備・確認用に残す

## 出典（2026-10-28に見たページ）

- DigiKey：[Adafruit 4694](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/4694/13157994)、[LS027B7DH01A](https://www.digikey.jp/ja/products/detail/sharp-microelectronics/LS027B7DH01A/5054067)、[Adafruit 5477](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/5477/16583982)、[Adafruit 4682](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/4682/12822319)、
  [SparkFun 15712](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/15712/11481331)、[SparkFun 15733](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/15733/11481329)、[SparkFun 21834](https://www.digikey.jp/ja/products/detail/sparkfun-electronics/21834/18735208)、
  [Taoglas AGGBP.25A.07.0060A](https://www.digikey.jp/ja/products/detail/taoglas-limited/AGGBP-25A-07-0060A/5287273)、[MIKROE-3922](https://www.digikey.jp/ja/products/detail/mikroelektronika/MIKROE-3922/11507397)、[Adafruit 6357](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/6357/26832926)、[Radial Magnets 9042](https://www.digikey.jp/ja/products/detail/radial-magnets-inc/9042/5640338)
- 秋月電子：[AE-BNO055-BO](https://akizukidenshi.com/catalog/g/g116996/)、[MAX31855モジュール](https://akizukidenshi.com/catalog/g/g108218/)、[MPJ-K-F](https://akizukidenshi.com/catalog/g/g114971/)、[SMPW-K-M](https://akizukidenshi.com/catalog/g/g114969/)
- NEO-M9Nの速さ（4種類の衛星で25Hz）：[u-blox NEO-M9N Product summary](https://content.u-blox.com/sites/default/files/NEO-M9N_ProductSummary_UBX-19027207.pdf)
- M10の速さ（GPSだけ25Hz）：[u-blox Information note UBX-23006557](https://content.u-blox.com/sites/default/files/documents/u-bloxM10-with-25Hz-Navigation-UpdateRate_IN_UBX-23006557.pdf)（2023-07-10）。
  古い値（18Hz）は[SparkFun Hardware Overview](https://docs.sparkfun.com/SparkFun_u-blox_SAM-M10Q/hardware_overview/)
- SparkFun NEO-M9Nのアンテナ端子の3.3V：[SparkFunの掲示板](https://community.sparkfun.com/t/neo-m9n-antenna-bias-voltage/42376)
- Taoglas AGGBP系の電圧（1.8〜5V）：[RS（同系統のAGGBP.SLS.25A）](https://se.rs-online.com/web/p/gps-antennas/2857161)
- Radial Magnets 9042が直径方向の磁化であること：[Radial Magnets](https://radialmagnet.com/?p=153)
- Adafruit 6357の端子（VIN・3V・GND・SCL・SDA・OUT、磁石は別売り）：[Adafruit](https://www.adafruit.com/product/6357)
- GNSS 7 Clickの仕様（SMA・3.3V・予備電池）：[DigiKeyのデータシート](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/57/MIKROE-3922_Web.pdf)
- DigiKeyの送料（6,000円未満は2,000円）：DigiKey Japanの各ページの表示
- Adafruit 4694の仕様（3V/5V両用、フレームバッファ13.5KB）：[Adafruit](https://www.adafruit.com/product/4694)
- Amazonの各商品：表のリンク先
