# 回路レビュー反映結果

2026-09-07。原本バックアップは `logger_v2-backups/pcb_design_20260907/`。回路図は59部品となった。基板・プロジェクト設計ルールは本担当では編集していない。

## 反映済み

- C4–C14: U1/U4/U5/GNSSの電源バイパスと3.3 V/5 Vのbulkを追加。機能ごとの配置先は `reviewed_parts_metadata.json` のFunctionに記載。
- R18–R20: SER/SRCLK/RCLKへ47 kΩ pull-downを追加。
- D11: PESD5V0F1BL,315 / C45961をRFラインに追加。pad2=RF、pad1=GND。双方向品。
- U1: Nexperia 74HC595D,118 / C5947へ変更し、3.9 mm幅SOIC16へ変更。標準ライブラリとの差分warningも解消。
- D1–D8: KT-0805G / C2297へ変更。各直列抵抗は680 Ω / C23228。
- Y1: XC2EL89COO-114YLC-20M / C18213008、20 MHz、CL=12 pF、3225-4端子へ変更。C2/C3は18 pF C0G / C1647。旧Y1.2信号を新Y1.3へ対応し、ケース端子2/4はGND。
- L1: LQG15HS27NJ02D / C12669、0402へ変更。
- R7: 27 Ω、1 W、2512 / C25478へ変更。電源最大3.6 Vと抵抗−5%を仮定した短絡電流上限は約140 mA。22 Ω時よりアンテナ電圧が0.10 V低くなる（20 mA時）ため、実アンテナ接続で動作電圧を確認する。
- U4: ATA6561-GAQW / C2929602、U5: MCP25625-E/SS / C184944へ発注名を統一。
- D9/D10: NUP2105LT1G / C14486へ変更。既存SOT23 pin1/2=line、pin3=GNDを維持。
- 全実装SMDのManufacturer/MPN/LCSCを回路図に記載。J1–J7/U3は手実装扱い。DNPはR10/R13/R14。
- U3 AE-BNO055系モジュールを保持。UNO Qヘッダ割り当ては元の正しい現行接続を保持。
- 新規標準フットプリント6種をプロジェクトへコピーし、STEPの参照を `${KIPRJMOD}/3dmodels/` に統一。

## 検証

- `reviewed_erc.json`: ERC error 0 / warning 0。
- `schematic_connectivity_validation.json`: 元44部品の全接続群を保全（Y1の番号変更を正規化した比較）。追加11コンデンサ、3 pull-down、RF ESD、Y1ケースGNDを確認。
- 全シンボルのpin番号集合とフットプリントpad番号集合が一致。
- 保存済みPCBと回路図の全59部品のFootprint名、および全224端子のネット名が一致。
- 19種類の使用STEPをローカル参照として検証。
- PDF/PNGで回路図を表示確認。

最終回路図SHA-256: `0d30c36a3051426f8e3f44066d25a1b0942beeb9ab918904210d392fc24e6720`。

最終PCBシルクとの一致のため、D1–D8、U3、J5のFootprintフィールドを専用の `_ShieldSilk` ライブラリ名へ同期した。回路図の位置、UUID、その他のフィールド、電気接続は不変。

## 最終実装集計

| 区分 | 実装数 | LCSC品種数 |
|---|---:|---:|
| JLCPCB Basic SMD | 39 | 10 |
| JLCPCB Extended SMD | 9 | 8 |
| SMD合計 | 48 | 18 |

回路図全59部品のうち、上記48部品をPCBA対象とし、J1–J7とU3の8部品は手実装、R10/R13/R14の3部品はDNP。PCB上の取付穴MH1–MH4は電気部品の集計外。NEO-M9NのためJLCPCB Standard PCBAを選ぶ。詳細は `final_assembly_counts.json`。

基板作業用の最新入力は `reviewed_netlist.xml`、部品情報は `reviewed_parts_metadata.json`。プロジェクト直下の `logger_v2.net` も最新化した。`apply_pcb_review.py` は初期バックアップから作り直す単発処理なので、後続の手編集後に再実行しない。

## 継続条件

J6.1の5 V出力に個別電流保護はない。推定電流で保護部品を確定せず、仕様・シルクに未保護出力と記載する。SD回路・車載12 V入力DC/DCはこのPhase 1シールドに含まれない。水晶CLの寄生見込み、GNSSアンテナ動作電圧、電源レール低下、実CAN受信/送信は実機で確認する。

現行Basic確認を追加した抵抗: [10 kΩ C25804](https://jlcpcb.com/partdetail/C25804)、[4.7 kΩ C23162](https://jlcpcb.com/partdetail/C23162)、[120 Ω C22787](https://jlcpcb.com/partdetail/0603WAF1200T5E/C22787)。在庫数は注文時に再確認する。
