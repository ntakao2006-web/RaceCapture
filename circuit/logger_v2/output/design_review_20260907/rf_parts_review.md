# Logger v2 RF・部品調達 最終レビュー

確認日: 2026-09-07 JST。対象: circuit/logger_v2。

回路レビューで決定した修正と基板設計への反映は完了した。final_drc.json（07:47:54 JST）で DRC 違反・警告 0、未配線 0、回路図との不一致 0 を確認した。設計担当の最終照合でも全224端子、コネクタの位置・向き、全表面搭載の不一致は0。部品の注文、JLCでの在庫引当・製造審査、試作および実測は行っていない。最終のシルク文字はJLC公開条件（文字高1.0mm、文字線幅0.15mm）に合わせる追加仕上げを実施中で、その結果は別の最終DRCで確認する。

## 最終の実装区分

- JLCPCB Standard PCBA: 表面SMD 48個。NEO-M9Nの登録がStandard OnlyなのでStandard PCBAを使う。
- 後付け: J1–J7とU3 AE-BNO055-BOの計8部品。コネクタの位置と向き、既存IMUモジュールを維持する。完全な一括PCBAにはしていない。
- DNP: R10、R13、R14。R13/R14のCAN終端は実バスの両端条件に合わせて実装する。
- MH1–MH4は機構穴で実装部品数に含めない。

全ての部品本体は表面側に搭載する。THTコネクタの半田端子は裏面へ出るので、UNO Qとの干渉、脚長、スペーサ高さは実物で確認する。AEモジュールとコネクタをJLCに支給する手配・受入確認は行っていない。

## 採用した主要部品

| Ref | 採用品 | LCSC | 区分 |
|---|---|---|---|
| U1 | Nexperia 74HC595D,118 / SOIC16幅3.9mm | C5947 | Basic |
| U2 | u-blox NEO-M9N-00B | C5119087 | Extended / Standard Only |
| U3 | 秋月 AE-BNO055-BO | ― | 後付け |
| U4 | Microchip ATA6561-GAQW / SOIC8 | C2929602 | Extended |
| U5 | Microchip MCP25625-E/SS / SSOP28 | C184944 | Extended |
| D1–D8 | KT-0805G / green0805、直列抵抗680Ω | C2297 | Basic |
| D9/D10 | onsemi NUP2105LT1G / SOT23 | C14486 | Extended |
| D11 | Nexperia PESD5V0F1BL,315 / SOD882 | C45961 | Extended |
| L1 | Murata LQG15HS27NJ02D / 27nH350mA0402 | C12669 | Extended |
| R7 | UNI-ROYAL 25121WJ0270T4E / 27Ω±5%1W2512 | C25478 | Extended |
| Y1 | YXC XC2EL89COO-114YLC-20M / 20MHz CL12pF3225-4 | C18213008 | Extended |

JLC登録ページと在庫の証拠・取得時点はparts_sourcing.csvにまとめた。未採用の比較部品も含むため、この調査CSV全行を製造BOMとして発注へ取り込まない。

## GNSSとアンテナ給電

NEO-M9NのRF_INは内部DC blockと50Ω整合を備えるので、不要な直列コンデンサや汎用π整合回路は追加していない。RF ESDはIntegration Manual R10 §4.9.4の必須条件としてD11を追加した。未使用のV_USBはGND、VCC直近には1µFを追加。V_BCKPは+3V3であり、電源断後の保持用バックアップ電源ではない。[u-blox Integration Manual R10](https://content.u-blox.com/sites/default/files/NEO-M9N_Integrationmanual_UBX-19014286.pdf)

最終回路は VCC_RF → R7 27Ω/1W → bias node、bias node → L1 27nH → RF_IN/SMA center、bias node → C1 100nF X7R → GND。

元の22Ω公称では3.3/22=150mAで、公差を考える余裕がない。メーカーの19Ωという例も、外部LのDCR1–2Ωと内部LのDCR1.2Ωを仮定しており、今回のL1のDCR0.46Ωと一致しない。このため27Ω/1Wを採用した。抵抗の-5%下限25.65Ω、電源3.6Vで、他の抵抗を無視しても短絡電流は約140.4mA、抵抗損失は約0.505W。温度ディレーティングと実装後の短絡温度は未実測。[NEO-M9N Data sheet R08](https://content.u-blox.com/sites/default/files/NEO-M9N-00B_DataSheet_UBX-19014285.pdf)

正常時20mAではR7に0.54V落ちる。VCC_RFの典型値VCC-0.1VとL1のDCRを含めると、3.3V給電のアンテナ端は概算2.65V。この電圧で動くアクティブアンテナを使用する。アンテナ型番・最低動作電圧・実際の消費電流との照合と受信試験は未実施。より高いアンテナ給電電圧が必要なら低損失の能動電流制限付き給電回路へ変更する。

CAN保護NUP2105は24V standoff、30pF max、44V max@8A（8/20µs）。pin1/2がCAN lines、pin3がGND。通常NUP型番はSZ接頭の車載認定品とは区別する。[onsemi NUP2105L Rev.12](https://www.onsemi.com/pdf/datasheet/nup2105l-d.pdf)。RF ESDは0.4pF typの低容量品を使用した。[Nexperia PESD5V0F1BL](https://assets.nexperia.com/documents/data-sheet/PESD5V0F1BL.pdf)

## 最終RF配線と製造条件

2層・1.6mm FR-4、GCPW主配線幅1.5mm、左右gap0.3mmを採用。SMAからGNSSのRF_INまで表面の直線とし、pad部に短いテーパー、裏面直下に連続GND、両側にGND stitching viaを設けた。

独立計算は導体間誘電体1.51mm、Er4.5、銅厚35µm、1.57542GHz、マスクを含めないモデルを使用した。W1.0/gap0.3mmは58.06Ω、W1.4mmは51.36Ω、W1.502mmは50.00Ω。採用したW1.5mmはこのモデルで約50Ω。計算式は[KiCad9.0 coplanar.cpp](https://github.com/KiCad/kicad-source-mirror/blob/9.0/pcb_calculator/transline/coplanar.cpp)、数値はrf_impedance_estimate.jsonに保存した。pad transition、マスク、エッチング・基板厚公差を含む製造保証値ではない。

JLCPCBの標準FR-4 Controlled Impedanceは4層以上が対象で、今回の標準2層板は対象外。公式能力表は2層FR-4のErを4.5、Controlled Impedance対応を4/6/8/.../32層と記載する。したがって「JLC保証付き50Ω」として表示・注文しない。保証付きインピーダンス管理が必要な場合は、4層以上または別の対応製造条件でstackupと配線幅を再設計する。[JLCPCB PCB Capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

## IMU・水晶・デカップリング

AE-BNO055-BOは内部レギュレータとI2Cレベル変換を持つ18×11mmモジュールとして保持。裸BNO055/C93216は未採用で、この番号をモジュールfootprintのBOMへ流用しない。[秋月 AE-BNO055-BO](https://akizukidenshi.com/goodsaffix/AE-BNO055-BO_20220413.pdf)

Y1は20MHz/CL12pF、C2/C3はC0G18pFを採用した。概算CL=C2×C3/(C2+C3)+Cstrayで寄生3pFを見込む。端子1/3が水晶、2/4がケースGND。メーカー図面とランドを確認済みだが、起動余裕と周波数の実測は未実施。[YXC採用品と添付資料](https://jlcpcb.com/partdetail/19387115-XC2EL89COO_114YLC20M/C18213008)

パスコン、bulk、pull抵抗を回路図・PCBへ反映した。100nF=C14663（X7R50V0603）、1µF=C15849（X5R50V0603）、10µF=C15850（X5R25V0805）、18pF=C1647（C0G50V0603）はBasic。X5Rは85°C上限で、10µFの実効容量はDC biasにより減る。85°C超または最低実効容量を別途仕様にする場合は再選定する。

## 調達確認の境界

2026-09-07に公式JLCの部品登録、Basic/Extended区分、実装種別を照合した。parts_sourcing.csvは次の証拠を区別している。

- JLCの数量表示: 例C14663=65,537,578、C15849=9,147,549、C15850=7,852,178。索引経由の値はsnapshotであり注文時の引当を保証しない。
- InStockのみ: C12669、C25478、C1647、C23228、C25819などは公式HTMLの状態を確認したが数量は非表示。
- LCSC在庫のみ: U4 C2929602はLCSC側1,117を取得したが、JLC実装用在庫としては扱わない。
- 古い索引値: U5 C184944の86個は古い索引で、現在庫の根拠にしない。注文時に優先して在庫・納期を更新する。
- 後付け品: J1–J7、U3はJLC SMT発注対象から除外。exact型番のJLC受入を確認した扱いにはしない。

在庫予約、購入、JLC BOMマッチング、工場での実装方向確認、支給部品手配は未実施。試作ではGNSS受信、アンテナ給電と短絡温度、20MHz起動、IMU校正、CAN受信を確認する。

J6の+5Vはアクセサリへの出力で、外部受電入力ではない。分岐の個別過電流保護は追加していないのでアクセサリ電流とUNO Qの電源余裕を守る。独立短絡保護が必要な使用条件では、負荷仕様を決めて保護回路を追加する。