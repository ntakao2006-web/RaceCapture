> **訂正（2026-09-07、公式資料・現行回路図で検証済み）**: UNO Qは **D4 = FDCAN1_TX、D5 = FDCAN1_RX**。現行シールドはCAN1_RXDをD5（J5.3）、GNSS_RESET_NをD3（J5.5）へ接続し、D4は未使用です。下の受領本文にある「D3=TX / D4=RX」とGNSS resetのD5割り当ては使用しないでください。受領本文は記録として保持しています。[Arduino UNO Q公式datasheet §9.6](https://docs.arduino.cc/resources/datasheets/ABX00162-ABX00173-datasheet.pdf)

---

# EcoLogger v2 Phase 1 実装方針

更新: 2026-09-07  
対象: `logger_v2(2).net`

## 0. 現在の判断

最新版では主要な部品ブロックは揃った。

- 74HC595 + STATUS LED
- NEO-M9N-00B
- AE-BNO055-BO
- CAN1: ATA6561
- CAN2: MCP25625
- MCP25625用20 MHz水晶
- CAN TVS ×2
- CAN終端抵抗 footprint ×2
- GNSS SMA + active antenna bias-T

したがって、**以下に挙げる少数の回路修正を済ませれば、残作業は基本的に「UNO Qヘッダとの配線」と「ネット名整理」でよい。**

パスコン、ローカルbulk capacitor等はPCB設計時にまとめて追加する方針でよい。  
ただし、PCB発注前には必ず回路図/BOMにも反映する。

---

# 1. 先に直す項目

配線作業へ入る前に、以下だけ修正する。

## 1.1 UNO QのFDCANピン

Arduino UNO Q公式pinoutでは

```text
D3 = FDCAN1_TX
D4 = FDCAN1_RX
```

である。

以前の実装方針にあった `D4=TX / D5=RX` は誤りなので使用しない。

CAN1を車載CANの受信専用とするため、今回は

```text
UNO Q D4 / FDCAN1_RX <- U4 ATA6561 RXD
U4 ATA6561 TXD        -> +3V3
```

とする。

つまり **D3/FDCAN1_TXはCAN1へ接続しない**。

ソフトウェア側でもFDCANをBus Monitoring / Listen-Only相当で使用する。

これにより、ソフトウェアの不具合があってもCAN1から車載CANへdominant bitを送信できない。

---

## 1.2 NEO-M9N V_USB

現在のネットリストでは

```text
U2 pin 7 V_USB -> +3V3
```

になっている。

Phase 1ではGNSSのUSBを使用しないので

```text
U2 pin 7 V_USB -> GND
```

へ変更する。

u-bloxのIntegration ManualでもUSB未使用時はV_USBをGNDへ接続する指定。

---

## 1.3 GNSS active antenna bias-T

現在:

```text
VCC_RF ---- L1 ---- RF line
   |
  R7
   |
  C1
   |
  GND
```

となっているが、R7がアンテナ給電の直列電流制限になっていない。

以下へ変更する。

```text
U2 VCC_RF
    |
   R7
    |
    +------ C1 ------ GND
    |
   L1
    |
RF line ---- U2 RF_IN ---- SMA
```

値:

```text
C1 = 100 nF X7R
L1 = 27 nH
R7 = 22 Ω
```

NEO-M9NのIntegration Manualでは一般例として10 Ωが示されているが、
VCC_RF=3.3 Vから直接給電する場合は短絡電流を150 mA未満とするため
19 Ω以上が必要とされている。

そのためPhase 1では **22 Ω** とする。

短絡時の発熱も考え、R7は現在の0603から変更し、
**0.5 W以上を確保できる抵抗/footprint**を使う。

L1は現在の27 nH品を使用してよい。

---

## 1.4 NEO-M9N LNA_EN

現在:

```text
U2 LNA_EN -- R10 10k -- GND
```

となっている。

LNA_ENはNEO-M9Nから出る制御**出力**であり、
今回の単純なVCC_RF bias-Tでは使用しない。

したがって

```text
R10 = DNP
```

とし、LNA_ENはNCでよい。

---

## 1.5 UNO QのI2Cヘッダ

UNO Qでは

```text
D20/D21 = I2C2
A4/A5   = I2C3
```

であり、Classic UNOのように同一信号ではない。

現在の

```text
/SDA/A4
/SCL/A5
```

でJ2側とJ4側を短絡しているネットを分離する。

```text
D20 -> D20_I2C2_SDA
D21 -> D21_I2C2_SCL

A4/D18 -> A4_D18_I2C3_SDA
A5/D19 -> A5_D19_I2C3_SCL
```

Phase 1のBNO055はD20/D21側を使う。

---

## 1.6 Power header

現在J3 pin 8のネット名が

```text
VCC
```

になっている。

UNO QではここはVINなので

```text
VCC -> VIN
```

へ改名する。

Phase 1ではVINは未使用でよい。

---

## 1.7 車載CANコネクタの+5 V

現在はCAN1側のJ7 pin 1にも+5 Vが出ている。

CAN1は車載CANへ接続する用途なので、車両ハーネス側で明確に必要と決まっていない限り

```text
J7 pin 1 = NC
```

とする。

車載側への不用意な+5 V逆流を防ぐ。

CAN2のJ6 pin 1はユーザー定義センサバス用なので、センサ給電を行う仕様なら+5 Vのままでよい。

---

# 2. ここまで直した後の残作業

上記を終えたら、**基本的には配線だけ**でよい。

推奨ピン割り当ては以下。

| UNO Q | Phase 1用途 |
|---|---|
| D0 / USART1_RX | GNSS TXD |
| D1 / USART1_TX | GNSS RXD |
| D2 | IMU_RESET_N |
| D3 / FDCAN1_TX | 未使用（CAN1はHW受信専用） |
| D4 / FDCAN1_RX | CAN1_RXD |
| D5 | GNSS_RESET_N |
| D6 | GNSS_TIMEPULSE |
| D7 | STATUS_LATCH |
| D8 | CAN2_RESET_N |
| D9 | CAN2_INT_N |
| D10 / SPI2_SS | CAN2_CS_N |
| D11 / SPI2_MOSI | SPI2_MOSI |
| D12 / SPI2_MISO | SPI2_MISO |
| D13 / SPI2_SCK | SPI2_SCK |
| D20 / I2C2_SDA | IMU_SDA |
| D21 / I2C2_SCL | IMU_SCL |

A0～A5はPhase 1では空ける。

---

# 3. CAN1: 車載CAN受信専用

部品:

```text
U4 = ATA6561-GAQW-N
J7 = 車載CAN
D10 = CAN TVS
R14 = 120 Ω termination
```

配線:

```text
U4 VCC  -> +5V
U4 VIO  -> +3V3
U4 GND  -> GND
U4 STBY -> GND

U4 RXD  -> UNO Q D4 / FDCAN1_RX
U4 TXD  -> +3V3

U4 CANH -> J7 CANH
U4 CANL -> J7 CANL
```

CAN1は既存車載CANへぶら下がるため

```text
R14 = DNP
```

を標準とする。

D10 TVSはJ7直近へ配置する。

---

# 4. CAN2: MCP25625

部品:

```text
U5 = MCP25625T-E/SS
Y1 = 20 MHz
J6 = ユーザー定義CAN
D9 = CAN TVS
R13 = 120 Ω termination
```

電源:

```text
U5 VIO  -> +3V3
U5 VDD  -> +3V3
U5 VDDA -> +5V
U5 GND  -> GND
U5 VSS  -> GND
U5 STBY -> GND
```

MCP25625内部接続:

```text
TxCAN -> TXD
RXD   -> RxCAN
```

これは最新版ですでに正しく接続されている。

SPI:

```text
UNO D13 -> CAN2_SCK   -> U5 SCK
UNO D11 -> CAN2_MOSI  -> U5 SI
UNO D12 <- CAN2_MISO  <- U5 SO
UNO D10 -> CAN2_CS_N  -> U5 CS_N
UNO D9  <- CAN2_INT_N <- U5 INT_N
UNO D8  -> CAN2_RESET_N -> U5 RESET_N
```

最新版の

```text
R12 = CS_N 10k pull-up
R17 = RESET_N 10k pull-up
```

はそのままでよい。

20 MHz水晶と33 pF ×2も現状のまま進めてよい。

R13 = 120 Ωは、ロガーがCAN2バス端に来る場合のみ実装する。

---

# 5. SPIとSTATUS LED

74HC595はMCP25625とSPI2のSCK/MOSIを共用する。

```text
UNO D11 / SPI2_MOSI
    +-> U5 MCP25625 SI
    +-> U1 74HC595 SER

UNO D13 / SPI2_SCK
    +-> U5 MCP25625 SCK
    +-> U1 74HC595 SRCLK

UNO D7
    -> U1 74HC595 RCLK
```

74HC595にはMISOがないため競合しない。

ネット名は

```text
CAN2_MOSI -> SPI2_MOSI
CAN2_SCK  -> SPI2_SCK
STATUS_OUT -> STATUS_LATCH
```

へ変更する。

---

# 6. GNSS: NEO-M9N-00B

UART:

```text
U2 TXD -> GNSS_TXD -> UNO D0 / USART1_RX
U2 RXD <- GNSS_RXD <- UNO D1 / USART1_TX
```

ネット名もモジュール基準に揃える。

現在の

```text
GNSS_RxD = U2 TXD
GNSS_TxD = U2 RXD
```

という名前は逆に見えるため改名する。

制御:

```text
U2 RESET_N   <- UNO D5
U2 TIMEPULSE -> UNO D6
```

電源/設定:

```text
VCC    -> +3V3
V_BCKP -> +3V3
V_USB  -> GND
D_SEL  -> NC
USB_DM -> NC
USB_DP -> NC
```

D_SEL openでUART/I2C側になる。

RF:

```text
SMA center ---- RF_IN
                  |
                 L1
                  |
             antenna bias node
                /   \
              R7     C1
              |       |
           VCC_RF    GND
```

PCBではSMA～RF_INを50 Ωで最短にする。

RF入力のESD保護はu-blox推奨。
必須機能ではないため今回の「配線完了」のblockerとはしないが、
車載・外部SMAなのでPCB設計時に低容量RF ESD footprint追加を推奨する。

---

# 7. IMU

U3 = AE-BNO055-BO

```text
VIN     -> +3V3
GND     -> GND
SDA     -> UNO D20 / I2C2_SDA
SCL     -> UNO D21 / I2C2_SCL
RESET_N -> UNO D2
INT     -> NC
VOUT    -> NC
```

R15/R16 = 4.7k I2C pull-upはfootprintを残す。

AE-BNO055-BO側にもpull-upがあるため

```text
R15 = DNP
R16 = DNP
```

を初期状態とし、必要なら後から実装する。

---

# 8. ネット名整理

配線と同時に以下へ統一する。

```text
/RX/0       -> D0_USART1_RX
/TX/1       -> D1_USART1_TX
/2          -> D2
/*3         -> D3_FDCAN1_TX
/4          -> D4_FDCAN1_RX
/*5         -> D5
/*6         -> D6
/7          -> D7
/8          -> D8
/*9         -> D9
/*10        -> D10_SPI2_SS
/*11        -> D11_SPI2_MOSI
/12         -> D12_SPI2_MISO
/13         -> D13_SPI2_SCK

CAN2_MOSI   -> SPI2_MOSI
CAN2_MISO   -> SPI2_MISO
CAN2_SCK    -> SPI2_SCK
CAN2_CS     -> CAN2_CS_N
CAN2_INT    -> CAN2_INT_N
CAN2_RESET  -> CAN2_RESET_N

GNSS_RxD    -> GNSS_TXD
GNSS_TxD    -> GNSS_RXD
GNSS_RESET  -> GNSS_RESET_N
GNSS_PPS    -> GNSS_TIMEPULSE

IMU_RESET   -> IMU_RESET_N
STATUS_OUT  -> STATUS_LATCH

VCC         -> VIN
```

---

# 9. パスコンはPCB設計時に行う

今回の回路図配線作業ではパスコンをいったん保留してよい。

PCBレイアウトに入った時点で、各ICの電源pinの直近に追加する。

最低限対象:

```text
U1 74HC595
U2 NEO-M9N
U4 ATA6561 VCC/VIO
U5 MCP25625 VDD/VIO/VDDA
```

BNO055はモジュールなのでモジュール内の実装を基本とする。

さらにシールド側へ

```text
+3V3 local bulk
+5V local bulk
```

を置く。

「パスコンを基板設計時に考える」は問題ないが、
**PCB発注時点では回路図・BOMへ追加済みにすること。**

---

# 10. 配線完了判定

以下を満たせば回路図としてPhase 1はほぼ完成。

- [ ] NEO-M9N V_USBをGNDへ変更
- [ ] GNSS bias-Tを正しいトポロジへ変更
- [ ] C1を100 nFへ変更
- [ ] R7を22 Ω / 0.5 W以上へ変更
- [ ] R10 LNA_EN pull-downをDNP
- [ ] D20/D21とA4/A5を分離
- [ ] J3 `VCC` を `VIN`へ改名
- [ ] J7 pin1 +5VをNC化（車載側で不要なら）
- [ ] CAN1 RXDをD4へ接続
- [ ] CAN1 TXDを+3V3へ固定
- [ ] CAN2 SPI/INT/RESETをD8～D13へ配線
- [ ] GNSS UART/RESET/TIMEPULSEを配線
- [ ] IMU I2C/RESETを配線
- [ ] 74HC595 SPI/LATCHを配線
- [ ] ネット名を整理
- [ ] R14をDNP指定
- [ ] R13の実装条件を指定
- [ ] R15/R16をDNP指定

ここまで終われば、次は

1. ERC
2. footprint照合
3. PCB配置
4. パスコン/bulk追加
5. RF/CANレイアウト

へ進んでよい。

---

# 11. 一文での方針

**`logger_v2(2).net` は主要部品が揃っており、GNSS電源/RF周辺とUNO Qヘッダ定義を少し直した後は、基本的に配線だけでPhase 1回路図を完成させられる。パスコンはPCB設計時に追加する。**

---

## 参考

- Arduino UNO Q datasheet / pinout  
  https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf

- u-blox NEO-M9N Integration Manual  
  https://content.u-blox.com/sites/default/files/NEO-M9N_Integrationmanual_UBX-19014286.pdf

- Microchip MCP25625 Data Sheet  
  https://ww1.microchip.com/downloads/en/DeviceDoc/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf
