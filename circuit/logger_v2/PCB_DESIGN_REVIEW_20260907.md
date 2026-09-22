# EcoLogger V2 — Arduino UNO Q シールド基板

2026-09-07 / Rev A / KiCad 9.0.6

回路レビュー、部品置換、パスコン追加、配置配線、GND形成を反映した設計。原本は `logger_v2.kicad_pro`、`logger_v2.kicad_sch`、`logger_v2.kicad_pcb`。今回の対象はUNO Qから給電するGNSS・IMU・2系統CANの上面シールドで、SDスロットと車載12 V入力電源は含まない。

## 形状と配置配線

- 2層、68.58 × 53.34 mm、厚さ1.6 mm。開始時のEdge.Cuts、4個の取付穴、J1–J7の位置・向き・全ランド中心を保持した。
- 全59部品を表面に配置。内訳はPCBA実装48点、表側へ後付けするコネクタ7点とIMUモジュール1点、DNP抵抗3点。取付穴4点は部品数に含めない。
- CAN1、CAN2、水晶、GNSS、表示回路を機能ごとにまとめた。LEDと抵抗を2.8 mm等ピッチに整列し、配線の主方向と45度の曲げ方を揃えた。
- 通常信号は主に幅0.25 mm、局所最小0.20 mm。通常クリアランス0.20 mm、狭ピッチ部の最小0.15 mm。GNDゾーンとRFの隙間は0.30 mm。ビアは外径0.60 mm／穴0.30 mm。
- 表裏GND、RF両側のGNDビア列、IC電源直近のGND接続を設けた。RF直下を信号配線が横断しないよう制限した。
- 裏面にJ6/J7の端子表と、J6の5 Vが未保護出力であることを印字した。コネクタを外さずに接続表を確認できる。

## 回路レビューで反映した変更

| 対象 | 最終変更 |
|---|---|
| C4–C14 | IC・GNSSの電源バイパス、GNSS用1 µF、3.3 V/5 V各10 µFを追加。回路図にも反映 |
| R18–R20 | 74HC595のデータ・クロック・ラッチへ47 kΩのプルダウンを追加 |
| U1 | Nexperia 74HC595D,118 / C5947、正しい3.9 mm幅SOIC-16へ変更 |
| D1–D8、LED抵抗 | KT-0805G / C2297のSMD LEDと680 Ωへ変更 |
| Y1、C2/C3 | 20 MHz・CL 12 pFの3225 SMD水晶 / C18213008、18 pF C0Gを2個。ケース端子2/4をGND接続 |
| D9/D10 | CAN保護をNUP2105LT1G / C14486へ変更 |
| D11 | SMA近傍へ低容量RF ESD保護PESD5V0F1BL,315 / C45961を追加 |
| L1 | RF用27 nH、Murata LQG15HS27NJ02D / C12669、0402へ変更 |
| R7 | アンテナ短絡時を考慮し27 Ω・1 W・2512 / C25478へ変更 |
| U4/U5 | ATA6561-GAQW / C2929602、MCP25625-E/SS / C184944へ発注情報を統一 |

UNO Qの公式端子表と照合し、D4=FDCAN TX（この基板では未接続）、D5=FDCAN RX、D3=GNSSリセットを確認した。CAN1のTXD固定による受信専用接続を維持した。CAN2はClassic CAN用で、CAN FD用ではない。74HC595とCAN2のSPI共有では、表示更新時だけSTATUS_LATCHを操作する。

根拠: [UNO Q pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)、[MCP25625](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf)、[NEO-M9N Integration Manual](https://content.u-blox.com/sites/default/files/NEO-M9N_Integrationmanual_UBX-19014286.pdf)。個別部品の根拠と確認日は `output/design_review_20260907/parts_sourcing.csv` と `rf_parts_review.md` に記録した。

## RF設計

J1の信号ランド(105,90)からU2 RF_IN(117.5,90)まで、中心線12.5 mmの表面直線を維持した。主区間は幅1.5 mm、GNDとの隙間0.3 mm。モジュール側の狭いランドへ幅0.8 mmの区間とテーパーで接続している。L1とD11は短い枝で接続した。GNSS内部のDCブロックを利用し、不要な直列コンデンサは追加していない。

総厚1.6 mm、誘電体高さ1.51 mm、Er=4.5、銅厚35 µm、1.57542 GHzを仮定したGCPW計算は、幅1.0 mmで約58.1 Ω、幅1.5 mmで約50.0 Ω。ソルダーマスク・ランド遷移・実材料公差を含まない公称設計値である。JLCPCBの公開インピーダンス制御は4層以上のため、この2層基板を「50 Ω保証品」として発注する前提にはしていない。[JLCPCB製造能力](https://jlcpcb.com/capabilities/pcb-capabilities)

裏面GNDの連続性はRF下の107.0–117.5 mm／89.3–90.7 mm範囲を0.1 mm刻みで照合した。1590点で欠落0。SMAの信号スルーホール自体は検査範囲外。最終的なRF特性、受信感度、使用アンテナとの動作は試作で確認する。

## 製造・実装データ

`manufacturing_20260907/` に次を収録する。

| ファイル | 用途 |
|---|---|
| `Gerber_JLCPCB.zip` | 銅箔2層、表裏マスク、表裏シルク、表面ペースト、外形、PTH/NPTHドリル |
| `JLCPCB_BOM.csv` / `JLCPCB_CPL.csv` | 表面PCBAの48点。LCSC品番を指定、位置単位mm、原点は基板外形左下 |
| `Complete_BOM.csv` | DNPと後付け品を含む全59点 |
| `Manual_Assembly.csv` | J1–J7とU3の8点 |
| `Schematic.pdf` | 最終回路図 |
| `PCB_top.png` / `PCB_bottom.png` | 最終の表裏表示 |
| `validation/` | ERC、DRC、回路接続・機構・製造出力の照合結果 |

NEO-M9NがStandard Onlyのため、**JLCPCB Standard PCBA・Top side**を前提とする。2層FR4、1.6 mm、外層1 oz、緑レジスト、表面処理はENIGを選ぶ。基板外形を変える工具穴・フィデューシャルは追加していない。実装工程用の捨て板と工具穴・基準マークはJLC側のパネル化で付加する。

R10（GNSS LNA_ENの任意リンク）、R13/R14（CAN終端）はDNP。R13はCAN2バス端点で必要な場合のみ別途実装する。CAN1車載バスへ不要な終端を追加しない。R15/R16のI2Cプルアップは実装する。

J2–J5にはUNO Qへ差し込める十分な下側ピン長のシールド用スタッキングヘッダを使う。通常の短足ソケットを発注しない。U3は既存AE-BNO055系モジュールを表面に浮かせて後付けする。3D表示のヘッダ・モジュール形状は配置確認用で、選定した脚長やUNO Qとの実物干渉を保証するものではない。

PCBAは18品種48点で、Basicが10品種39点、Extendedが8品種9点。JLC用BOMは同一部品のリファレンスをまとめた18行、CPLは個々の実装座標を記した48行としている。

部品在庫は確認時点の表示であり、注文時の引当ではない。JLCの部品マッチングと2D実装プレビューで、各ICの1番端子、LEDカソード、水晶1/3端子を確認する。CPLの数字だけから部品ライブラリのゼロ度基準一致を保証しない。`cpl_rotation_review.md` に確認表を収録する。

## 設計検証と実機確認の境界

設計検証はERC error/warning 0、DRC error/warning 0、未配線0、回路図との不一致0。全224端子のネット、部品値、フットプリント、DNPを再照合し不一致0。全コネクタと外形は元データと一致する。ドリルはPTH 224穴／NPTH 6穴を座標・径で照合した。Excellonの丸め誤差は最大0.0005 mm。

実基板の製造・通電・車両搭載は未実施。試作時は次を確認する。

1. UNO Qとの脚長・高さ・USBコネクタ周辺の干渉、IMU下の部品との間隔。
2. GNSS・IMU・全LED・CAN動作時の3.3 V/5 V電圧。U4とU5のアナログ5 Vが最低4.5 Vを維持すること。
3. R7で20 mA時に約0.54 V降下するため、アクティブアンテナの最低動作電圧。電源3.3 Vならアンテナ端は典型約2.66 Vとなる。短絡時の電源挙動とR7温度も確認する。
4. 20 MHz水晶の発振開始、CAN1受信専用動作、CAN2送受信、SPI共有時のLED保持、IMU軸方向と校正、GNSS受信。
5. J6.1の5 V出力は分岐保護なし。負荷電流仕様がないためヒューズ定格は確定していない。外部電源を入力しない。外部アクセサリへ常用給電する場合は最大電流を決めて分岐保護を追加する。

回路変更の詳細は `output/design_review_20260907/schematic_changes.md`。作業前の回路・基板は `logger_v2-backups/pcb_design_20260907/` に保持している。`tools/design_board.py` と `tools/apply_pcb_review.py` は初期構築用であり、完成基板へ再実行しない。
