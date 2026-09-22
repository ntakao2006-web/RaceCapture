# Logger v2 回路レビュー（独立確認）

確認日: 2026-09-07。対象は現行 `logger_v2.kicad_sch` から新規出力した `circuit_review_source.xml`。保存済み `logger_v2.net` と `refs/implementation_policy_received.md` には現行回路図と異なる情報があるため、接続判断は新規出力を優先した。

確認時の回路図 SHA-256: `E993465DA1802582EDE7D792C22F453D7770EB46545869E41D32F433FA2778D7`。

本レビュー担当は回路図・PCBを編集していない。GNSS/RFとIMUモジュールの詳細は別レビューに統合する。

## 結論

現行のUNO Q割り当て、CAN電源、UART方向、SPI共有、CAN1のハードウェア受信専用接続に電気的な接続誤りは見つからなかった。パスコン未実装の状態なので、以下の追加を回路図とBOMに反映してから配線する。表面PCBA向けにはY1と調達困難な部品の品種・フットプリント変更も必要。

ERCは **error 0、warning 1**。warningはU1の `lib_symbol_mismatch`（標準74HC595とのキャッシュ差分）で、配線断線ではない。U1を採用品の正規シンボルへ更新し、ピン番号の不変を確認して解消する。

## 1. 優先する変更

### P1: 電源バイパスを追加

下記の名前は機能名であり、実装担当が空いているC番号を割り当てる。すべて表面配置。100 nFは1608、X7R、16 V以上を基本とする。

| 対象 | 追加接続 | 数 | 配置 |
|---|---|---:|---|
| U1 pin 16 VCC | +3V3 → 100 nF → GND | 1 | U1.16直近。GNDは短いviaで裏面連続GNDへ |
| U4 pin 3 VCC | +5V → 100 nF → GND | 1 | U4.3とU4.2の最短電流ループ |
| U4 pin 5 VIO | +3V3 → 100 nF → GND | 1 | U4.5直近 |
| U5 pin 1 VIO | +3V3 → 100 nF → GND | 1 | U5.1直近 |
| U5 pin 19 VDD | +3V3 → 100 nF → GND | 1 | U5.19直近 |
| U5 pin 27 VDDA | +5V → 100 nF → GND | 1 | U5.27とU5.26の最短電流ループ |
| シールド3.3 V受電点 | +3V3 → 10 µF → GND | 1 | J3.4付近、10 V以上、X7R推奨 |
| CAN用5 V分岐 | +5V → 10 µF → GND | 1 | U4/U5電源分岐付近、10 V以上、X7R推奨 |

GNSS/U3向けは別途追加。6個のIC用100 nFと2個のbulkを、GNSS用やモジュール内コンデンサで共用しない。bulk値はシールドの局所蓄電を目的とする設計判断で、最終容量はDCバイアス後の実効値を確認する。

根拠: [MCP25625 datasheet, Figure 1-2](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf)、[ATA6561評価基板の回路・BOM](https://www.microchip.com/content/dam/mchp/documents/OTH/ApplicationNotes/ApplicationNotes/Atmel-9310-ATA6560-EK-ATA6561-EK_Application-Note.pdf)、[TI HC595 datasheet](https://www.ti.com/lit/ds/symlink/sn74hc595.pdf)。

### P1: Y1をSMD水晶に変更、負荷容量を採用品へ合わせる

現状 `Y1=HUSG-20.000-20` はHC49 THT。20 MHzの周波数は維持してSMDへ変更する。新しい水晶の端子が1/3なら、旧Y1.1/.2と新1/3の電気的対応を明示し、ケース端子2/4は採用品の指定に従う。

`C2/C3=33 pF` は新しい水晶にも自動的に適合する値ではない。初期値は `CL ≈ C2*C3/(C2+C3) + Cstray` で選ぶ。例えばCL 12 pF、寄生3 pF見込みなら18 pF×2、CL 18 pF、寄生4.5 pF見込みなら27 pF×2。C0G/NP0を選ぶ。これは推定値なので量産前に発振開始と周波数を確認する。

OSC1=U5.9、OSC2=U5.8。Y1とC2/C3はこの2ピン直近にまとめ、デジタル配線を水晶の下へ通さない。水晶最大drive levelによってはOSC2側直列抵抗が必要なので、採用品の規定を確認する。[MCP25625 datasheet, §3.13 / Table 3-6](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf)

### P1: 旧方針文書のUNO Q表を訂正

`implementation_policy_received.md` の「D3=FDCAN TX / D4=RX」は誤り。**D4=PA12/FDCAN1_TX、D5=PA11/FDCAN1_RX** が正しい。現行回路図はすでに正しいため、旧文書へ合わせた変更をしない。GNSS resetは現行のD3で正しい。

根拠: [UNO Q公式pinout（2026-02-17）](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)、[UNO Q公式datasheet（2026-09-03）§9.6](https://docs.arduino.cc/resources/datasheets/ABX00162-ABX00173-datasheet.pdf)。最新datasheetではD3/PB0も5 V非許容である点が追記されているが、現行3.3 V GNSS reset接続は問題ない。

### P2: 起動中の74HC595入力状態

現行U1.13 /OEはGND、U1.10 /SRCLRは+3V3で正常動作する。ただしMCU起動中はSER/SRCLK/RCLKが高インピーダンスになり、LEDの初期表示も不定。SER=U1.14、SRCLK=U1.11、RCLK=U1.12それぞれに47〜100 kΩのGNDプルダウンを追加することを推奨する。起動時にLED消灯を保証する要件があれば/OE制御も必要で、プルダウンだけではレジスタ初期値を保証しない。[Toshiba TC74HC595AF datasheet](https://toshiba.semicon-storage.com/info/docget.jsp?did=16512&prodName=TC74HC595AF)

### P2: 外部センサ5 V給電の保護

J6.1はUNO Qの+5Vへ直結。負荷が短絡するとUNO Qとシールド全体へ影響する。CAN2センサ給電を使用するなら `+5V → 電流制限/保護 → +5V_CAN2 → J6.1` とし、給電電流をコネクタ近傍へ表記することを推奨する。現在の資料にはセンサ最大電流がなく、保護定格は未確定。これはCAN信号配線の誤りではなく外部給電の堅牢性に関する項目。

## 2. 現行ヘッダ割り当ての確認結果

| シールド端子 | UNO Q | 現行接続 | 判定 |
|---|---|---|---|
| J5.8 | D0 / PB7 / USART1_RX | U2.20 GNSS TXD | OK |
| J5.7 | D1 / PB6 / USART1_TX | U2.21 GNSS RXD | OK |
| J5.6 | D2 / PB3 | U3.5 IMU RESET_N | OK |
| J5.5 | D3 / PB0 | U2.8 GNSS RESET_N | OK |
| J5.4 | D4 / PA12 / FDCAN1_TX | NC | OK、車載CANは送信不能 |
| J5.3 | D5 / PA11 / FDCAN1_RX | U4.4 CAN1_RXD | OK |
| J5.2 | D6 / PB1 | U2.3 GNSS_PPS | OK |
| J5.1 | D7 / PB2 | U1.12 STATUS_LATCH | OK |
| J2.10 | D8 / PB4 | U5.18 CAN2_RESET_N | OK |
| J2.9 | D9 / PB8 | U5.13 CAN2_INT_N | OK |
| J2.8 | D10 / PB9 | U5.17 CAN2_CS_N | OK |
| J2.7 | D11 / PB15 / SPI2_MOSI | U5.15 SI、U1.14 SER | OK |
| J2.6 | D12 / PB14 / SPI2_MISO | U5.16 SO | OK |
| J2.5 | D13 / PB13 / SPI2_SCK | U5.14 SCK、U1.11 SRCLK | OK |
| J2.2 | D20 / PB11 / I2C2_SDA | IMU_SDA | OK |
| J2.1 | D21 / PB10 / I2C2_SCL | IMU_SCL | OK |

J4 A0〜A5は全てNCであり、A4/A5(I2C3)とD20/D21(I2C2)の短絡はない。J3.4=+3V3、J3.5=+5V、J3.6/.7=GND、J3.8 VIN=NC。接続表のUNO Q根拠は上記公式pinout。

## 3. CAN、STATUSの確認結果と実装条件

- U4 ATA6561: pin3 VCC=+5V、pin5 VIO=+3V3、pin2 GND、pin8 STBY=GND、pin1 TXD=+3V3。受信専用接続として成立。CANH=pin7→J7.2、CANL=pin6→J7.3。J7.1はNC、R14はDNPで既存車載バスの終端へ追加負荷を作らない。[ATA6561 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/20005991B.pdf)
- U5 MCP25625: VIO pin1/VDD pin19=+3V3、VDDA pin27=+5V、GND pin10/VSS pin26=GND、STBY pin5=GND。TxCAN pin20↔TXD pin24、RxCAN pin21↔RXD pin28の外部ループは正しい。CANH pin4→J6.2、CANL pin3→J6.3。[MCP25625 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf)
- R12(10 kΩ)はCS_N、R17(10 kΩ)はRESET_Nの3.3 V pull-up。INT_Nは専用出力で、今回の接続で追加pull-up必須とは判断しない。CAN2はClassic CAN最大1 Mbpsであり、CAN FD対応とは表記しない。R13はCAN2端点時だけ実装する現行DNP方針でよい。
- 74HC595のVCC=3.3 V、LED抵抗1 kΩ×8で電流は低く、5 Vレベル変換は不要。QA〜QHにR1/R2/R3/R4/R6/R8/R9/R11とD1〜D8が順番に接続。シリアル入力とクロックはCAN2と共有できるが、STATUS_LATCHはSTATUS用8 bitを書き終えた時だけ立ち上げる。
- D9/D10はCAN線→TVS→コネクタの長いstubにせず、コネクタからICへの通り道で短いGND帰路を作る。代替品へ変更するときは双方向2回路・pad3=GND・バス過渡電圧許容を再確認。[現行PEC3824C2A-AUメーカー資料](https://akizukidenshi.com/goodsaffix/PEC3808C2A-AU_SERIES.pdf)

## 4. 電源・SDの範囲

この現行回路にはmicroSDスロット、SD配線、車載12 VからのDC/DC、入力サージ対策はない。電源はUNO Qのヘッダから受ける構成。したがって今回のシールドを「単体でSDへ記録できるロガー」「車載電源へ直接接続できる基板」とは表記しない。既存のPhase 1センサ/CANシールドとしては設計を進められる。

UNO Qの3.3 Vは本体と共用であり、公開datasheetにシールド向けの独立した電流保証値は見つからなかった。GNSSのアンテナ電流、IMU、全LED点灯、CAN2負荷を含めた実機電圧降下を確認する。5 Vヘッダは入力方法によって供給経路が変わるため、使用するUSB-C/外部5 V/VIN構成でU4 VCCとU5 VDDAが4.5 V以上を保つことを確認する。[UNO Q datasheet §3、§9.7](https://docs.arduino.cc/resources/datasheets/ABX00162-ABX00173-datasheet.pdf)

## 5. 基板完成後に残る実機確認

1. 受電点、U2電源、U4 VCC/VIO、U5 VDD/VIO/VDDAを負荷最大時に測定する。
2. CAN2起動時にハードウェアRESETかSPI RESETを必ず実行する。初期SPIは低速で始め、上限10 MHz内で検証する。
3. 20 MHz発振の起動・周波数を電源/温度範囲で検証する。
4. CAN1はFDCAN Bus Monitoringで実バス受信と送信不能を確認し、CAN2は終端2箇所のベンチバスで送受信する。
5. SPI通信中にSTATUS表示が変化せず、LATCHでのみ更新されることを確認する。

新規出力したERCとnetlistはこのフォルダ内の `circuit_review_erc.json`、`circuit_review_source.xml` に保存した。
