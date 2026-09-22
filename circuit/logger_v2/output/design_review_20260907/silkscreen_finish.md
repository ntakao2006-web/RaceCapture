# Logger v2 シルク仕上げ

2026-09-07。原本 PCB / 回路図 / 現行 footprint library は、この担当では編集していない。

## 成果と確認

- `tools/finish_silkscreen.py`: 入力 PCB を読み、別の出力 PCB へシルクのみを仕上げる。入力と同一パスへの保存は禁止している。
- 最新配線済み原本を読み取りコピーした `silkscreen_work/latest_snapshot.kicad_pcb` に適用して確認した。LED と抵抗列は 2.8 mm pitch。座標は各 footprint の現在位置から求めるため、列の pitch に追従する。
- `latest_finished_drc.json`: silk_overlap / silk_over_copper / silk_edge_clearance / text_height は **0**、未配線 **0**。この時点ではシルクを変更した 10 個の footprint の library mismatch だけが残る。
- 下記のライブラリ同期を作業用フォルダだけで実施した `synced_finished_drc.json`: **違反 0、未配線 0**。
- `latest_finished.silk.json`: 仕上げ前後および保存再読込後の保護対象 SHA-256 が同一。pad、部品位置・角度、配線、via、zone、Edge.Cuts、ルール、FPID、F.Fab、F.CrtYd、3D model などは仕上げ処理で変わらない。
- 0.8 mm 未満の表示文字なし。参照名は全て F.Silkscreen、横向き。既存の非表示 mounting-hole reference はそのまま。

## 配置方針

LED D1–D8 とその抵抗は直線の annotation row にした。タイトルは LED 列の中心へ合わせ、短い `UNO Q SHIELD` を下段中央に置いた。部品名はパッドと外形を避け、U3 の下になる R20 の文字はモジュール下端より下の右側へ出した。J1–J7 の参照名も表示する。

F.Silkscreen 図形の変更は次の範囲だけ。

1. D1–D8 の `LED_0805_2012Metric`: 下側の横線を 0.2 mm の端部へ短縮。両側の縦線を残し、LED 番号と C14 の間に文字領域を確保する。
2. U3 の `AE_BNO055_BO`: 右側と下側の輪郭線を R17/R20 の pad 周囲で短くする。IMU 下への部品配置を妨げる印刷だけを切り、F.Fab の完全な外形は維持する。
3. J5 の 1×8 header: 既存 Edge.Cuts の右上 chamfer に合わせて、シルクの右上角だけを斜めにつなぐ。pad/穴/connector 角度は変えない。

## 適用

KiCad 9 の Python で次を実行する。出力はまず review 用の別ファイルにする。

```powershell
& 'C:\Users\lintaroh\AppData\Local\Programs\KiCad\9.0\bin\python.exe' `
  circuit/logger_v2/tools/finish_silkscreen.py `
  circuit/logger_v2/logger_v2.kicad_pcb `
  circuit/logger_v2/output/design_review_20260907/final_silk_candidate.kicad_pcb `
  --library-out circuit/logger_v2/output/design_review_20260907/final_silk_library.pretty
```

後から配線/viaを変えた場合は、同じ処理の出力に対して DRC を再実行する。シルク検査を無効化したり DRC exclusion を追加する処理はない。

## footprint library と埋込み形状の同期

`silkscreen_work/reviewed_silk.pretty` に、仕上げ済み board の footprint を正規化して書き出した 3 個の候補を置いた。作業用コピーでは次の同期手順を検証済み。

1. `LED_0805_2012Metric.kicad_mod` と `AE_BNO055_BO.kicad_mod` を、同名の `logger_v2_custom.pretty` のファイルへ反映する。既に仕上げ処理をかけた board の埋込みシルクと一致する。
2. `PinSocket_1x08_P2.54mm_Vertical_ShieldCorner.kicad_mod` を `logger_v2_custom.pretty` へ追加する。J3 も元の 1×8 footprint を共有しているため、元の `PinSocket_1x08_P2.54mm_Vertical` を上書きしない。
3. **J5 だけ** PCB FPID と回路図の Footprint property を `logger_v2_custom:PinSocket_1x08_P2.54mm_Vertical_ShieldCorner` にそろえる。シルク仕上げスクリプト自身はこの FPID / schematic の変更を行わない。
4. J5 の pad/位置/角度を変更する必要はない。更新後に PCB と schematic の一致を含む最終検査を行う。

`synced_finished.kicad_pcb` は上記 3 の FPID 変更を作業用コピーにだけ加えた検証基板。`synced_library.pretty` は元 library の作業用複製へ 3 個を反映したもの。作業用 `fp-lib-table` はこの複製を向くため、そのまま原本プロジェクトへ持ち込まない。

全ての資料は、この時点の配線済み snapshot に対する確認であり、以後の親担当による変更は最終基板で再確認する。
