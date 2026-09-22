# logger_v2 GNSS復帰・LTE／microSD追加準備

> 本書は当時の作業記録です。最新の設計方針は [実装方針.md](実装方針.md) を参照してください。LTEはUART直結、GNSSはI²Cへ変更する計画です。以下の部品数・参照番号・配置情報は、その後編集された現在の回路図を表すものではありません。

2026-09-19。今回の到達点は **GNSSの置き換えと追加部品の未配線配置**。LTE・SDの配線、ファームウェア、基板への反映は行っていない。

## 変更した内容

- U2をNEO-M9N-00Bから **MAX-M10M-00B** に復帰。v1のシンボル・18ピンフットプリント・実体のあるSTEPを再利用した。EXTINTの配置もv1同様。電源ピンは中央に2.54mm間隔。
- UART、PPS、RESET、RFの外部接続を機能名で維持。VCC／V_IO／V_BCKPは3.3V、VIO_SELは開放。未使用SDA／SCL／EXTINT／SAFEBOOT_NはNC。
- MAX-M10MのVCC_RFは最大50mA。既存27Ωではアンテナ短絡時に約120mAが流れるため、R7の給電元を外部+3V3に変更しVCC_RFはNCとした。R7=27Ω/1W、L1、C1の値・位置は保持。LNA_ENに接続するR10=10kΩは従来どおりDNP。この構成でアンテナの常時給電はLNA_ENから行わない。アンテナの必要電圧・消費電流とRFコイルの短絡電流耐量は実装時に照合する。
- 既存A4シート右側の空き領域に追加シートへの入口を配置。`logger_v2_lte_sd.kicad_sch` に44部品を未配線で配置した。追加シート内はワイヤ・ローカルラベル・電源シンボル・NCマーカーを追加していない。
- GNSS以外の既存58部品は、位置・値・フットプリント・DNP属性を含め変更なし。IMUプルアップR15/R16は実装のまま。既存のGNSS以外のネット接続も同一。
- `logger_v2.kicad_pcb` と `.kicad_pro` はバイト単位で変更なし。**現行PCBはNEO-M9Nのままで、今回の回路図とは未同期**。既存製造用データも更新していない。

## 配置した主要部品

|参照|部品|用途|
|---|---|---|
|U6|SIMCom SIM7070G|LCC68、24×24×2.3mm。HP等の別パッケージではない|
|J8|Same Sky NSIM-2-C|nanoSIM、ヒンジ式、挿入検出付き。検出接点の相手はC5/GND|
|J9|Hirose DM3AT-SF-PEJM5|microSD、プッシュプッシュ、挿入検出付き|
|J10|Hirose U.FL-R-SMT-1(10)|LTEアンテナ端子|
|U7|NXP SC16IS750IPW|SPI–UART変換、64バイトFIFO、補助GPIO×8|
|U8/U10|TI TXU0204PWR|UARTと補助信号の3.3V／1.8V変換|
|U9|TI TPS62130RGTR|5V→約3.8V、3A降圧電源候補|
|L2|Bourns SRN6045TA-2R2Y|2.2µH。典型Irms 6A、Isat 9.5A|
|C15|330µF/6.3Vポリマー、7343-D|VBATのバルク容量候補。低ESR品を選定する|
|Q1|2N7002|PWRKEYをオープンドレインで制御|
|Y2|14.7456MHz、CL12pF、3225-4pin|UART変換ICのクロック候補|
|U11/U12|ST USBLC6-4SC6|SIM／microSDのESD保護|
|J11|2.54mm 1×6ヘッダ|USB更新信号、BOOT_CFG、VDD_EXTの保守接続候補|

このほか電源・信号周辺の抵抗とコンデンサを配置。値は次の配線設計用の候補であり、完成回路のBOMではない。例えばU9の374kΩ/100kΩは基準0.8Vに対して3.792V、結晶負荷容量は採用する実部品と基板寄生容量に合わせて調整する。RF整合、SIM電源のESD配線、SD未使用データ端子の処理等は配線設計時に確定する。

SIM7070GのUARTは1.8V、SIMも1.8V対応。UNO Qの3.3V GPIOと直結しない。VBATの標準電圧は3.8Vで、5V直結は不可。2G時は2A級の電流ピークと300µF以上の負荷容量が示されているため、その条件を含めた部品候補を用意した。5V側に必要な追加電流は3.8V×2A÷(5V×0.9)≒1.69Aであり、UNO Q本体等の消費を加えた供給能力・熱設計は別途必要。3Aの降圧ICを置いただけでは5V供給能力の確認にはならない。

## GPIO見積もり

**既存接続を保ったまま、SPI–UART変換を使えば足りる。** 直接接続するための独立したハードウェアUARTが不足するので、本数だけの判断はできない。

現在のシールド信号端子はD0～D13、A0～A5、独立SDA/SCLの22本。D4とA0～A5の **7本が空き**。D0/D1のUSART1はGNSSに使用済み。A4/PC1とA5/PC0へLPUART1を割り当てる案は、UNO Q内部のRouterBridgeが同じLPUART1を使うため採用しない。内部通信を維持する構成を前提とした。[UNO Qピン配置](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)、[Arduino公式coreのRouterBridge割り当て](https://github.com/arduino/ArduinoCore-zephyr/blob/main/variants/arduino_uno_q_stm32u585xx/arduino_uno_q_stm32u585xx.overlay)。

|空き端子|MCU端子|将来の割り当て案|必要本数|
|---|---|---|---:|
|A0|PA4|SD_CS_N|1|
|A1|PA5|SDカード検出|1|
|A2|PA6|LTE_PWRKEY（Q1経由）|1|
|A3|PA7|LTE電源EN（U9）|1|
|A4|PC1|SPI–UART変換ICのCS_N|1|
|A5|PC0|SPI–UART変換ICのIRQ_N|1|
|D4|PA12|空き。将来CAN1_TXDにも使用可能|0|
|**合計**|||**6本使用／1本残り**|

この表は見積もりであり、ヘッダの現状のNCや配線には反映していない。SD検出を省略する構成なら2本残る。D4をCAN1送信用に使う場合は表の余りを消費する。

SPIのSCK/MOSI/MISOは既存のD13/D11/D12（SPI2）を共用するため、新たなGPIO消費は0本。既存CAN2のCSはD10のまま。U7はSPIモードを使用し、SIM7070のUART1へU8を介して接続する。**SIM7070自体のSPIピンをATコマンドポートとして使う案ではない。**

U7のGPIO5をDTR、GPIO7をRI、GPIO6をSTATUS、GPIO3をSIMカード検出に使えば、補助信号のためにMCU端子を増やさずに済む。DTR／RI／STATUSはU10でレベル変換、SIM検出はスイッチ入力として扱う。UARTのTX/RX/RTS/CTSはU7の専用端子で扱う。PWRKEYや電源ENはU7の状態に依存せず直接MCUから操作できる案とした。

SC16IS750のSPI上限は4Mbit/s。14.7456MHzの結晶ではUART 921600baudを作れ、8N1なら理論ペイロード上限約92kB/s。実際はSPI処理、ATプロトコル、無線回線、SD書き込みで低下する。SDの長い書き込み待ち中に64バイトFIFOをあふれさせないよう、**RTS/CTS自動フロー制御とSPIバスの排他制御が必要**。既存74HC595もSPIクロックでシフトするので、LED更新時に全ビットを書いてからラッチする制御を維持する。性能・同時動作はまだ実機検証していない。[NXPデータシート](https://www.nxp.com/docs/en/data-sheet/SC16IS740_750_760.pdf)。

## フットプリント／3D

- 新規ライブラリは `logger_v2_expansion.kicad_sym` と `logger_v2_expansion.pretty`。既存のライブラリ登録を残して追記した。
- SIM7070Gはメーカー資料の68ピン配置と推奨ランドから作成。4辺17パッド、1mmピッチ、2.0×0.6mmの長円ランド。図示された2か所の2.4mm角キープアウトを設定。
- 新規44部品すべてにフットプリントとローカルSTEPを割り当て。新規16種類＋MAX-M10Mの計17種類を表示・STEP読み込み検証した。モデル参照は`${KIPRJMOD}/3dmodels/`。
- SIM7070GとTPS62130はメーカー公称寸法から作成した簡略機械モデル。内部形状・シールドの細部・製造公差を再現したメーカー配布モデルではない。
- ソケットその他はKiCadの対応パッケージモデル。MAX-M10Mはv1で使用しているSTEP本体をローカルLFSオブジェクトから復元した。v1のファイルは変更していない。
- `output/lte_sd_model_catalog.kicad_pcb` は3D確認用の独立した部品一覧であり、実基板レイアウトではない。

## 検証結果

- 既存非GNSS58部品と関連ネットの保持を自動比較。GNSSの信号名とMAX-M10Mの端子番号をネットリストで照合。
- 新規44部品の全ピン番号とフットプリントのパッド番号を照合。SIM7070Gは68ピン漏れなし、端子1/17/18/34/35/51/52/68の位置と向きを確認。
- 全17モデルをSTEPソリッドとして読み込み、3D部品一覧と2ページの回路図をレンダリングして確認。
- ERC：既存シートは変更前と同じSTATUS_LATCHの未接続ラベル1件。今回の範囲外なので修正していない。追加シートは意図した未配線による291件（未接続221、信号入力未駆動40、電源未駆動30）。追加のライブラリ不一致は0件。**ERC全体がゼロという結果ではない。**
- バックアップ：`logger_v2-backups/before_lte_sd_20260919/`。比較結果：`output/lte_sd_verification_20260919.json`。

## 参照資料

- [u-blox MAX-M10M-00Bデータシート](https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_DataSheet_UBX-22028884.pdf)、既存の`refs/MAX-M10M_IntegrationManual.pdf`。
- [SIMCom SIM7070G公式製品ページ](https://en.simcom.com/product/SIM7070G.html)。メーカー作成のHardware Design V1.03は[公開ミラー](https://cdn.promelec.ru/upload/items/2021/04/15/sim7070_hardware_design_.pdf)から取得し`refs/SIM7070_hardware.pdf`に保存。ピン表pp12–17、外形p18、推奨ランドp19、電源pp20–22、UARTpp25–28、SIMp31を照合。
- [SIMCom Compatible Design V1.01](https://www.rbtronic.com.ua/simcom/LTE-LPWA/SIM7070_SIM7080_SIM7090/Application%20Note/SIM7070_SIM7000_Compatible_Design_V1.01.pdf)：p12のランド寸法を相互確認。
- [NSIM-2-C](https://www.sameskydevices.com/product/resource/nsim-2-c.pdf)、[Hirose DM3AT-SF-PEJM5](https://www.hirose.com/product/p/CL0609-0031-0-00)。
- [TI TXU0204](https://www.ti.com/lit/ds/symlink/txu0204.pdf)、[TPS62130](https://www.ti.com/lit/gpn/TPS62130)、[Bourns SRN6045TA](https://www.bourns.com/docs/Product-Datasheets/SRN6045TA.pdf)。
