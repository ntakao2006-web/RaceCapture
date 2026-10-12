# レーシングカート用ロガーのディスプレイ調査（2026-10-12）

ハンドルに付けるカート用ロガー（MyChron等）の画面がどういう方式か、夜に読めるか、
同じような表示器を買えるかを調べたメモ。Phase 6の「走行中でも見える高輝度サブディスプレイ」
（ARCHITECTURE.md 5章 Phase 6）の部品選定の判断材料にする。

## 1. 市販カートロガーの画面の方式

| 製品 | 画面 | 解像度 | バックライト | 明るさ自動調整 |
|---|---|---|---|---|
| AiM MyChron6 | グラフィック（白黒、販売店の資料では16階調グレー） | 320×136 | RGB 8色から選べる | 照度センサーあり（販売店の説明） |
| AiM MyChron5 / 5S | グラフィック（白黒） | 268×128 | RGB 8色（660は7色） | 照度センサーで自動調整（公式仕様） |
| Alfano 7 | 4インチ RGBバックライト、アクリル窓 | 128×268 | 色と強さを変更できる | 照度センサーで自動調整 |
| Unipro UniGo One | FSTN液晶（白黒） | 非公開 | 白 | 照度センサーで自動調整 |

画面方式の要点：
- **主流は「白黒のグラフィック液晶（STN/FSTN系）＋LEDバックライト」**。フルカラーTFTではない。
  白地（または色付きの地）に黒い文字のポジ表示で、地の色はバックライトのLEDの色で決まる。
  MyChronの「RGB 8色」は画面がカラーなのではなく、バックライトの色を選べるという意味。
- この方式を選ぶ理由は、**直射日光の下でも外の光を反射して読める**こと（反射・半透過型の偏光板）。
  カラーTFTを日向で読ませるには1000cd/m²級の強いバックライトが必要で、電池がもたない。
  MyChron6は内蔵電池で約20時間動く。
- 窓は傷に強く反射しにくいポリカーボネート（MyChron5の公式仕様）、本体はIP67防水（MyChron6）。
- 補足：AiMの公式仕様書は「Graphical」としか書いておらず、液晶の種類（FSTN等）や輝度(cd/m²)は
  公表していない。MyChronの液晶の種類は販売店の説明からの推定で、実物では確認していない。

## 2. 夜に読めるか

- **読める**。上の製品はどれもバックライトがあり、照度センサーで周りが暗いと自動で明るさを変える。
  カートの販売店も、夜のレース向けにバックライト付きの表示を勧めている。
- 注意点：白地に黒文字の表示は、夜だとバックライトが光る面が広くまぶしい。そのため目が慣れるまで
  読むのに時間がかかる（車両用表示の特許文献の指摘）。夜向きなのは黒地に光る文字（ネガ表示）だが、
  こちらは昼の日向で見づらくなる。昼も夜も読ませたいなら、ポジ表示＋照度センサーで減光するのが
  市販品と同じやり方。
- 夜の見やすさを数値で確かめた資料（輝度の測定値など）は見つからなかった。夜間耐久レースで
  使ったことがある人に聞くのがいちばん確か。

## 3. 同じような表示器は買えるか

### 3-1. 完成品のロガーごと買う
- MyChron6：海外の販売店で€713（フランス）、£470（英国、1T版・売り切れ表示）。
  日本円の価格は見つからなかったので、国内のカート用品店か代理店に聞く必要がある。
  他の機器から表示用に任意のデータを送るような使い方は想定されておらず、
  **こちらのロガー用の表示器としては使えない**と考えたほうがよい。

### 3-2. CANで受けて表示する汎用ダッシュ（四輪用）
- AiM MXS 1.3 Strada（5インチ カラーTFT、記録機能なし）：£1,236〜、$1,499前後。
  CAN入力の設定ができるかは公式資料で確認が必要。高価で、カートのハンドルに付けるには大きい。

### 3-3. 表示パネルだけを買って自作する（Phase 6のサブディスプレイ向け）
| 種類 | 例 | 昼 | 夜 | 備考 |
|---|---|---|---|---|
| 半透過型の白黒グラフィック液晶（FSTN）＋LEDバックライト | Newhaven、Display Visions等の128×64〜240×128の液晶 | ◎ | ○（バックライト） | **市販カートロガーと同じ方式**。動作温度 −20〜70℃ 程度の品が多い |
| 半透過型のカラーTFT | 2〜3.5インチ、SPI接続（AliExpressで約$15〜） | ○ | ○ | 安い品は「日向で読める」の根拠があいまいなので実物で試す |
| 高輝度IPS（1000cd/m²） | Orient Display AFY320240A1-3.5INTH（3.5インチ 320×240、約$21） | ○ | ○（減光が必須） | 消費電力が大きい。車両の5V給電なら問題になりにくい |
| メモリ液晶（Sharp） | Adafruitの1.3インチ 168×144など | ◎ | ×（バックライトなし） | 夜はLEDで外から照らす工夫が要る。書き換えが遅くタコメーター向きではない |

自作で市販品に近づけるには：
- 白黒FSTN（ポジ・半透過）＋白かRGBのLEDバックライト＋照度センサーでPWM減光、の組み合わせ。
- 窓に反射を抑えたポリカーボネート板を付ける。
- 車両から給電できるので、電池がもつかどうかを気にしなくてよい。高輝度IPSも選べる。

## 4. 未確認のこと
- MyChron6の液晶の種類と16階調グレー：公式仕様書には書かれておらず、販売店の説明だけが根拠。
- 各製品の輝度(cd/m²)と、夜に一番暗くしたときの明るさ：公表値が見つからない。
- 日本国内での価格と入手先。

## 5. サブディスプレイの部品候補（白黒液晶、2026-10-12追記）

### 5-1. 選ぶときの条件
- 表示するのは予測タイム・デルタタイム（5〜10 Hz、`logger_v2_channel_and_sensor_spec.md` 3-3章）。
  走行中にちらっと見て読めるよう、**数字の高さ15mm以上**を目安にする（目からの距離50〜70cm）。
- 昼の日向で読めること：**FSTN・ポジ（白地に黒文字）・半透過型**。黒地や「transmissive（透過型）」は日向に弱いので外す。
- 夜：LEDバックライト付きで、マイコンからPWMで明るさを変えられること。
- 外部CANから5Vをもらい、アクセサリー側マイコン（未定）からSPIで描く。液晶は3.3V。
- 少数買い（1枚〜）ができ、日本へ送ってくれる店（DigiKey・Mouser・RS）で買えること。

### 5-2. 候補
| | ① 本命 | ② 小さく安く | ③ 小さく色つき |
|---|---|---|---|
| 品番 | **EA DOGXL240W-7** ＋ バックライト **EA LED94X67-GR** | **NHD-C12864LZ-FSW-FBW-3V3** | **NHD-C12864DA-FSRGB-FBW-3V3** |
| メーカー | Display Visions（ドイツ、ELECTRONIC ASSEMBLY） | Newhaven Display（米国） | Newhaven Display（米国） |
| 画素 | 240×128 | 128×64 | 128×64 |
| 表示方式 | FSTN・ポジ・半透過（白地） | FSTN・ポジ・半透過、白バックライト | FSTN・ポジ・半透過、RGBバックライト |
| 外形／表示部 | 94×67 mm／約90×47 mm（TME表記） | 表示部 70×40 mm | 表示部は未確認（図面が画像のため読めず） |
| バックライト | 緑・赤の2色（混ぜて黄色）。1色最大120 mA、5Vなら抵抗25Ω | 白 | 赤・緑・青 各60 mA（共通アノード） |
| 接続 | SPI（書き込みのみ、最大8 MHz）／I2C、ST互換ではなくUC1611s | SPI／パラレル、ST7565R | 4線SPI／パラレル、ST7565R |
| 電源 | 2.7〜3.3 V（約0.9 mA） | 3.0 V | 2.7〜3.3 V |
| 動作温度 | −20〜+70℃ | （データシートで要確認） | −20〜+70℃ |
| 価格（1個） | 液晶本体 約£41（同系のDOGXL240S-7、RS英国）。バックライトは別売で価格未確認 | 約$17.6（DigiKey、在庫約4,000） | 約$18.6（DigiKey、在庫392） |
| 数字の大きさ | 縦48ドットの数字で約17 mm、横に5〜6文字 | 縦32ドットで約20 mm、2行まで | 表示部が分かれば計算する |

### 5-3. おすすめと理由
- **①EA DOGXL240W-7＋EA LED94X67-GRを本命にする**。
  - 表示部が約90×47 mmと大きく、デルタタイムを大きな数字で出しつつ、下にラップタイム・油温などを小さく並べられる。
  - バックライトが緑と赤の2色なので、**速いとき緑・遅いとき赤**のように、色で良し悪しがわかる（MyChronのRGBバックライトと同じ使い方）。
  - 1個から買え、基板にそのままはんだ付けできるピン付き。
  - 240×128の画面1枚分は3,840バイト、8 MHzのSPIで約4 msで送れるので、10 Hzの更新は余裕。
- **②は、①が大きすぎて付けられない場合の代わり**。安くて在庫も多いが、デルタタイムしか置けない。
- **③は、小さい画面で色も変えたい場合**。表示部の大きさをデータシートの図面で確認してから決める。
- 寒さ対策のヒーター付き（NHD-C12864A1Z-FSW-FBW-HTT、−40℃まで）は、日本でのレース・エコランでは不要と判断。

### 5-4. 組むときの注意
- **バックライトを5Vに直接つながない**（メーカーが、すぐ壊れると注意している）。①のGRは1色あたり抵抗25Ω（5V時）。
  マイコンのPWMからMOSFETで駆動し、照度センサー（例：照度センサーIC、フォトトランジスタ）の値で明るさを変える。
- 液晶本体は3.3V。外部CANの5Vから3.3Vのレギュレーターで作る。
- コントラストは最初に一度コマンドで合わせる必要がある（①は温度補償が内蔵されているので、合わせた後は−20〜70℃で一定）。
- STN液晶は寒いと反応が遅くなる。5〜10 Hzの数字の書き換えは常温なら問題ないが、真冬の早朝は数字がにじむことがある。
- 窓には反射を抑えたポリカーボネート板を付け、液晶に直射日光の熱がこもらないようにする（上限70℃）。

### 5-5. 未確認のこと
- ①のバックライトEA LED94X67-GRの価格と、日本から買える店（DigiKey・RSに液晶本体の掲載はある）。
- ①の表示部の正確な寸法（データシートは外形94×67 mmのみ、TMEは表示部90×46.7 mmと表記）。
- ③の表示部の寸法。
- アクセサリー側マイコンが未定（task_phase6_breakdown.mdで保留中）。①はUC1611s、②③はST7565Rで、どちらもマイコン用ライブラリ（u8g2等）が対応しているかは選定時に確認する。

## 出典
- AiM MyChron6 技術仕様書（Ver.1.19）：https://dwls.aim-sportline.com/technical-sheets/aim_mychron6.pdf
- AiM MyChron5 技術仕様：https://aim-sportline.com/en/out-of-production/mychron5/technical-specifications.htm
- AiM MyChron5S 技術仕様書：https://aimsports.com/download/technical-sheets/aim_mychron5S_101.pdf
- MyChron5とMyChron6の比較（Harris Race Radios）：https://harrisraceradios.com/pages/mychron-5-vs-mychron-6-comparison
- MyChron6 販売ページ（16階調・照度センサーの記載）：https://pmbperformance.com/products/aim-sports-mychron6-karting-dash-and-data-logger 、https://www.itakashop.com/it/aim-displays-kart/13289-mychron-6.html
- 夜のレースでのバックライト（Impel Motorsports）：https://impelmotorsports.com/blogs/news/smarter-racing-starts-here-unlock-your-setup-with-aim-dash-mychron-6
- Alfano 7 レビュー（TKART）：https://tkart.it/en/magazine/first-analysis/alfano-dashboard-telemetry-laptimer-kart-customizable-gps-glonass-navstar-galileo-beidou-ada-wireless
- Unipro UniGo One レビュー（TKART）：https://tkart.it/en/magazine/first-analysis/unipro-unigo-one-kart-data-logger-laptimer
- MyChron6 価格：https://www.gt2i.com/en/instrumentation/200160-mychron-6-aim-gps-stopwatch-temperature-sensor-with-1-thermocouple-connection.html 、https://zipnorth.com/products/aim-mychron-6-1t-complete-with-m10-water-temperature-sensor
- AiM MXS 1.3 Strada：https://compare.parts/product/22186749161--aim-mxs-1-3-strada-dash-5-colour-tft-display-street-icons-with-can-connection/ 、https://product41.com/products/aim-mxs-1-3-strada
- 日向で読める表示の方式と1000cd/m²の目安（Display Visions）：https://www.lcd-module.com/displays/sunlight-readable-modules.html
- ポジ表示とネガ表示：https://support.newhavendisplay.com/hc/en-us/articles/4415451319063-LCD-Types-and-Modes 、https://orientdisplay.com/?p=355745
- 車両用表示の夜の見やすさ（特許 US5347293）：https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5347293
- FSTN液晶：https://www.orientdisplay.com/?p=23053
- 高輝度IPS 3.5インチ（Orient Display）：https://orientdisplay.com/products/3-5-sunlight-readable-ips-320x240-1000-nits/
- 半透過型の液晶モジュール（AliExpress）：https://www.aliexpress.com/af/Transflective-Display-Module.html
- Sharpメモリ液晶（Adafruit）：https://learn.adafruit.com/adafruit-sharp-memory-display-breakout
- EA DOGXL240-7 データシート（2022年3月版）：https://www.lcd-module.com/fileadmin/pdf/grafik/dogxl240-7.pdf
- EA DOGXL240 の表示部寸法（TME）：https://www.tme.eu/en/details/eadogxl240s-7/lcd-graphic-displays/display-visions/ea-dogxl240s-7/
- EA DOGXL240S-7 価格（RS英国）：https://uk.rs-online.com/web/p/lcd-monochrome-displays/1971299
- EA DOGXL240W-7（DigiKey）：https://punchouttest.digikey.com.mx/en/products/detail/display-visions/EA-DOGXL240W-7/4896742
- NHD-C12864LZ-FSW-FBW-3V3（価格・在庫）：https://www.flux.ai/vasyl/nhd-c12864lz-fsw-fbw-3v3~ny0.md 、https://uk.rs-online.com/web/p/lcd-monochrome-displays/2644053
- NHD-C12864DA-FSRGB-FBW-3V3 データシート：https://newhavendisplay.com/content/specs/NHD-C12864DA-FSRGB-FBW-3V3.pdf （価格・在庫はDigiKeyの64128K-FC-BW-RGBのページの代替品欄：https://www.digikey.com/en/products/detail/displaytech/64128K-FC-BW-RGB/6650332 ）
- NHD-C12864A1Z-FSW-FBW-HTT（ヒーター付き）：https://newhavendisplay.com/es/128x64-graphic-cog-lcd-display-with-white-backlight-heater/
