# JLCPCB 穴・配線間隔の独立検証

2026-09-07、主基板 `logger_v2.kicad_pcb` を読み取り専用で検証した。対象は 2 層、直線配線 420 本、スルービア 171 個、部品 PTH 53 穴。

| 項目 | 実最小 | JLCPCB 絶対最小 | 判定 |
|---|---:|---:|---|
| PTH 穴縁から異ネット配線の銅箔縁 | 0.490 mm | 0.28 mm | 適合 |
| ビア穴縁から異ネット配線の銅箔縁 | 0.351638 mm | 0.20 mm | 適合 |
| PTH 環状リング、2 層・1 oz | 0.240 mm | 0.18 mm | 適合 |

基準は [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities) の PTH to Track、Via hole to Track、PTH Annular Ring（2-layer board, 1 oz）の値を使用した。PTH to Track は推奨 0.35 mm も満たす。PTH 環状リングの推奨値は 0.25 mm で、J6/J7 はこの推奨値に対して 0.01 mm 小さい。絶対最小値に対する違反はない。

PTH と配線の最接近箇所は J6.4（GND、穴径 1.02 mm）と裏面の CAN2_H 配線。ビアと配線の最接近箇所は U5 RXD のビア（132.336, 63.9465 mm、穴径 0.30 mm）と表面の CAN2_INT_N 配線。最小環状リングは J6/J7 の 8 パッドで、ランド径 1.50 mm、穴径 1.02 mm から `(1.50 − 1.02) / 2 = 0.24 mm` となる。

距離は穴中心から線分中心線への最短距離より穴半径と配線幅の半分を差し引いて算出した。両銅箔層について異ネットを比較し、同一ネット、ゾーン、パッド間隔、製造公差はこの検証の対象外とした。全穴が同心円形、全配線が直線であることを確認した。部品 PTH の環状リングはビアの環状リングと別に集計した。

基板 SHA-256: `30ca8371a71b22a3fb1c98f0d95ea5627f4f6028b7b93308668d068b1eef85a7`

詳細結果は `jlc_hole_clearance_audit.json`。最終保存で基板のハッシュが変わった場合は `tools/audit_jlc_hole_clearance.py` を KiCad Python で再実行する。
