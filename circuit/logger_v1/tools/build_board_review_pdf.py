#!/usr/bin/env python3
"""Create the verified, image-led logger_v1 PCB review PDF."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
VIS = ROOT / "tmp" / "order_review_visuals"
DATA = json.loads((ROOT / "tmp" / "order_review_data.json").read_text(encoding="utf-8"))
OUT = ROOT / "output" / "pdf" / "logger_v1_board_review_20260819.pdf"
GERBER_ZIP = ROOT / "output" / "manufacturing" / "logger_v1_JLCPCB_20260819_current.zip"
PCB = ROOT / "logger_v1.kicad_pcb"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def register_fonts():
    pdfmetrics.registerFont(TTFont("JP", r"C:\Windows\Fonts\BIZ-UDGothicR.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("JP-Bold", r"C:\Windows\Fonts\BIZ-UDGothicB.ttc", subfontIndex=0))


register_fonts()

BASE = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
BLUE = colors.HexColor("#2563eb")
GREEN = colors.HexColor("#15803d")
AMBER = colors.HexColor("#b45309")
RED = colors.HexColor("#b91c1c")
LIGHT = colors.HexColor("#f8fafc")
LINE = colors.HexColor("#cbd5e1")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="JPBody", fontName="JP", fontSize=8.7, leading=13, textColor=BASE, wordWrap="CJK", spaceAfter=2.5 * mm))
styles.add(ParagraphStyle(name="JPSmall", fontName="JP", fontSize=7.2, leading=10.5, textColor=MUTED, wordWrap="CJK"))
styles.add(ParagraphStyle(name="JPTitle", fontName="JP-Bold", fontSize=22, leading=29, textColor=BASE, wordWrap="CJK", spaceAfter=3 * mm))
styles.add(ParagraphStyle(name="JPH1", fontName="JP-Bold", fontSize=15, leading=20, textColor=BASE, wordWrap="CJK", spaceAfter=3 * mm))
styles.add(ParagraphStyle(name="JPH2", fontName="JP-Bold", fontSize=10.5, leading=15, textColor=BASE, wordWrap="CJK", spaceBefore=1 * mm, spaceAfter=2 * mm))
styles.add(ParagraphStyle(name="JPCenter", fontName="JP", fontSize=8, leading=12, textColor=BASE, alignment=TA_CENTER, wordWrap="CJK"))
styles.add(ParagraphStyle(name="Status", fontName="JP-Bold", fontSize=15, leading=22, textColor=AMBER, alignment=TA_CENTER, wordWrap="CJK"))


def P(text, style="JPBody"):
    return Paragraph(text, styles[style])


def img(path, max_w, max_h):
    path = Path(path)
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return Image(str(path), width=w * scale, height=h * scale)


def styled_table(rows, widths, header=True, font_size=7.2, row_bgs=None):
    cooked = []
    for row in rows:
        cooked.append([cell if hasattr(cell, "wrap") else P(str(cell), "JPSmall") for cell in row])
    table = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (-1, -1), "JP"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "JP-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), BASE),
        ])
    if row_bgs:
        for row, color in row_bgs.items():
            commands.append(("BACKGROUND", (0, row), (-1, row), color))
    table.setStyle(TableStyle(commands))
    return table


def status_box(title, body, color=AMBER):
    table = Table([[P(title, "Status")], [P(body, "JPCenter")]], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, color),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed") if color == AMBER else colors.HexColor("#f0fdf4")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    canvas.setFont("JP", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10.5 * mm, "logger_v1 基板レビュー / 2026-08-19 / 現行PCB基準")
    canvas.drawRightString(192 * mm, 10.5 * mm, f"{doc.page}")
    canvas.restoreState()


def make_story():
    story = []
    story += [
        P("logger_v1 基板レビュー・発注判定", "JPTitle"),
        P("対象: logger_v1.kicad_pcb（2026-08-19 23:24保存後の現行版） / JLCPCB 2層・1 oz・1.6 mm想定", "JPBody"),
        status_box(
            "判定: 条件付きHOLD",
            "KiCad DRCは製造違反0・未配線0。機構、配線、Gerber整合は合格。<br/>ただしU10の0.20 mmランドはJLCPCB一般値0.25 mm未満のため、JLCDFM受理または工場確認前には発注確定しない。",
        ),
        Spacer(1, 5 * mm),
    ]

    summary_rows = [
        ["確認項目", "結果", "発注判断"],
        ["KiCad PCB DRC", "0違反 / 0未配線", "合格"],
        ["回路図等価性", "6件。すべて意図したカスタム形状またはC33記号属性", "基板製造に影響なし"],
        ["ERC", "3エラー / 8警告。電源ピン型・ライブラリキャッシュ由来", "実接続を照合済み"],
        ["JLC寸法監査", "187件を全件分類", "U10のみ工場確認待ち"],
        ["外形 / 構成", "70.635 × 100.000 mm（中心線） / 2層 / 1.6 mm", "合格"],
        ["最小穴-外形余白", "約1.605 mm", "十分"],
        ["現行Gerber", "PCB最終保存後に再生成", "古いZIPは使用禁止"],
    ]
    story += [styled_table(summary_rows, [38 * mm, 86 * mm, 50 * mm]), Spacer(1, 4 * mm)]

    findings = [
        ["優先度", "レビュー所見", "対応"],
        ["発注前", "U10 TUSB320の12ランドは幅0.20 mm。TI RWB0012A推奨ランドどおりだが、JLCPCB一般最小0.25 mmを下回る。", "ENIGを選択し、JLCDFMまたはCAM確認で受理を確認。"],
        ["発注前", "LED列のシルクが左端PWR・右端PWRで重複。既定のQA〜QH用途が SYS … CAN なら誤表示。", "意図がSYS/CANなら左をSYS、右をCANへ修正。"],
        ["実装計画", "裏面SMDが10点ある。上面ステンシルだけでは裏面をリフローできない。", "裏面は手はんだ、または両面ステンシル/二次実装を選択。"],
        ["資料修正", "C33は0.1 µF 0603で+3V3-GND接続だが、回路図記号だけ極性コンデンサ。", "基板は正しい。次回回路図更新でC_Smallへ変更。"],
    ]
    story += [styled_table(findings, [24 * mm, 102 * mm, 48 * mm], row_bgs={1: colors.HexColor("#fff7ed"), 2: colors.HexColor("#fef2f2")}), PageBreak()]

    story += [P("1. 完成イメージと機械配置", "JPH1")]
    story += [img(VIS / "board_iso.png", 174 * mm, 220 * mm), Spacer(1, 2 * mm)]
    story += [P("コネクタは左辺へ揃い、USB-C J2/J6、Micro-Fit J4/J5、SMA J7はいずれも筐体外側へ正しく突出する。ESP32アンテナ部は基板端側に置かれ、銅箔禁止領域を確保。部品コートヤード重複は0件。", "JPBody"), PageBreak()]

    story += [P("2. 表面: 3Dと製造レイヤ", "JPH1")]
    two = Table([
        [img(VIS / "board_top.png", 84 * mm, 110 * mm), img(VIS / "front_layers.png", 84 * mm, 110 * mm)],
        [P("3D上面", "JPCenter"), P("F.Cu + F.Mask + F.SilkS + Edge.Cuts", "JPCenter")],
    ], colWidths=[87 * mm, 87 * mm], hAlign="CENTER")
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.35, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [two, Spacer(1, 3 * mm), P("機能シルクは十分な大きさ。0.7 mmの部品番号115件はJLCPCB推奨文字高さ1.0 mm未満で、欠け・省略の可能性があるが、電気・組立位置・実装データには影響しない。Gerber生成時はsoldermask subtractionを有効にし、パッド上シルクをクリップ済み。", "JPBody"), PageBreak()]

    story += [P("3. 裏面と上面ステンシル注文時の注意", "JPH1")]
    two2 = Table([
        [img(VIS / "board_bottom.png", 84 * mm, 105 * mm), img(VIS / "back_layers.png", 84 * mm, 105 * mm)],
        [P("3D裏面", "JPCenter"), P("B.Cu + B.Mask + B.SilkS + Edge.Cuts（ミラー表示）", "JPCenter")],
    ], colWidths=[87 * mm, 87 * mm], hAlign="CENTER")
    two2.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.35, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [two2, Spacer(1, 3 * mm)]
    backside = DATA["backside_smd_footprints"]
    back_rows = [["Ref", "Value", "用途上の実装面"]] + [[x["reference"], x["value"], "B.Cu"] for x in backside]
    story += [P(f"裏面SMD: {len(backside)}点。上面のみのステンシル注文では以下を手実装する必要がある。", "JPBody"), styled_table(back_rows, [24 * mm, 45 * mm, 45 * mm]), PageBreak()]

    story += [P("4. USB-C位置決め穴とU10微細ランド", "JPH1")]
    pair = Table([
        [img(VIS / "usb_u10_detail.png", 92 * mm, 108 * mm), img(VIS / "tusb320_land-34.png", 76 * mm, 108 * mm)],
        [P("現行基板: J2/J6・U10", "JPCenter"), P("TI TUSB320 datasheet: RWB0012A推奨ランド", "JPCenter")],
    ], colWidths=[96 * mm, 78 * mm], hAlign="CENTER")
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.35, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [pair, Spacer(1, 3 * mm)]
    critical_rows = [
        ["箇所", "設計値", "根拠", "判定"],
        ["J2/J6 NPTH-銅箔", "0.2041 mm", "JLCPCB NPTH-to-copper下限0.20 mm", "下限+0.0041 mm。KiCad規則を0.20 mmに設定しDRC合格。"],
        ["U10 12パッド", "最小幅0.20 mm", "TI推奨RWB0012A: 12×0.20 mm", "部品には正しい。JLC一般最小0.25 mm未満のため工場確認待ち。"],
        ["表面処理", "ENIG推奨", "JLCPCBは微細QFN/BGA・0.5 mm以下ピッチでENIGを推奨", "HASLは選ばない。"],
    ]
    story += [styled_table(critical_rows, [31 * mm, 34 * mm, 60 * mm, 49 * mm]), Spacer(1, 3 * mm), P("参照: https://www.ti.com/lit/ds/symlink/tusb320.pdf / https://jlcpcb.com/capabilities/pcb-capabilities/ / https://jlcpcb.com/blog/npth-design-guide", "JPSmall"), PageBreak()]

    story += [P("5. DRC / ERC / 独自監査の全件分類", "JPH1")]
    all_rows = [
        ["検査群", "件数", "内容", "最終分類"],
        ["KiCad DRC", "0", "銅箔、穴、マスク、シルク、外形", "合格"],
        ["未配線", "0", "パッド未接続", "合格"],
        ["Footprint filter", "6", "C33 / J2 / J3 / J4 / J5 / J6", "名称・記号属性。実パッド/ネット照合済み"],
        ["ERC error", "3", "U1 IN / U2 VDD / U6 VIN", "外部電源、ダイオード、受動型eFuse出力により未駆動判定。実配線は成立"],
        ["ERC warning", "8", "ライブラリコピー不一致", "埋込シンボルのピン番号と現行ネットリストを使用。製造影響なし"],
        ["小シルク文字", "115", "高さ0.7 mmの部品番号", "可読性のみ。機能ラベルは別"],
        ["U10小パッド", "12", "幅0.20 mm", "TI推奨どおり / JLCDFM確認待ち"],
        ["同一ネット間隔", "60", "0.25 mm未満の幾何候補", "57屈曲、3パッド接続。独立スリット0"],
    ]
    story += [styled_table(all_rows, [34 * mm, 18 * mm, 65 * mm, 57 * mm]), Spacer(1, 4 * mm), img(VIS / "same_net_spacing_map.png", 174 * mm, 122 * mm), PageBreak()]

    story += [P("6. 前回Gerber以降の銅箔差分", "JPH1")]
    delta = Table([
        [img(VIS / "copper_changes.png", 78 * mm, 180 * mm), P(
            "<b>現行差分</b><br/>"
            "・+3V3: 2本削除、3本追加<br/>"
            "・/OTG_OC: 3本削除、3本追加<br/>"
            "・GND: 0.6/0.3 mmビアを8本追加<br/>"
            "・重複GNDビア1本を削除<br/><br/>"
            "現行統計: 823 tracks / 553 vias / 10 zones。差分後のDRCは0違反・0未配線。変更された+3V3はC29パッドを介して接続し、/OTG_OCも連続性を保持。前回23:07生成ZIPはこの差分を含まないため、発注に使用しない。",
            "JPBody",
        )],
    ], colWidths=[84 * mm, 90 * mm], hAlign="CENTER")
    delta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.35, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [delta, PageBreak()]

    story += [P("7. LED列とSMAコネクタ", "JPH1")]
    story += [img(VIS / "led_silk_detail.png", 174 * mm, 62 * mm), Spacer(1, 2 * mm)]
    led_rows = [
        ["対象", "確認結果"],
        ["LED D4-D11", "3 mm・2端子・2.54 mmピッチ。1番ピン=カソード、全D4-D11 pad 1はGND。"],
        ["LEDシルク", "KiCad標準LED_D3.0mmを基に、線幅0.15 mm・パッド回避形状へ調整。DRCシルク重なり0。"],
        ["機能ラベル", "現行は PWR / ERR / LOG / GPS / TLM / WiFi / BT / PWR。両端PWR重複は要意図確認。"],
    ]
    story += [styled_table(led_rows, [35 * mm, 139 * mm]), Spacer(1, 4 * mm)]
    sma_pair = Table([
        [img(VIS / "sma_mechanical_detail.png", 92 * mm, 78 * mm), P(
            "<b>J7 S-037-TGG</b><br/>"
            "・5穴: 信号1 + GND 4<br/>"
            "・穴径1.5 mm / 5.08 mm角配置<br/>"
            "・シルクは脚周囲の短線4本のみ<br/>"
            "・基板左辺からコネクタ本体を外向きに配置<br/>"
            "・3DはS-037-TGG公式モデルではなく、外形を合わせたWürth機械プロキシ。フットプリント寸法は秋月/COSMTEC図面を基準。",
            "JPBody",
        )],
    ], colWidths=[98 * mm, 76 * mm])
    sma_pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.35, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [sma_pair, PageBreak()]

    story += [P("8. 発注パッケージと最終チェックリスト", "JPH1")]
    hashes = [
        ["ファイル", "SHA-256"],
        [PCB.name, sha256(PCB)],
        [GERBER_ZIP.name, sha256(GERBER_ZIP)],
    ]
    checklist = [
        ["項目", "設定 / 状態"],
        ["Gerber", "現行PCBから再生成。F/B Cu, Mask, Silk, Paste, Edge.Cuts + PTH/NPTH drill"],
        ["シルク処理", "Subtract soldermask有効"],
        ["推奨表面処理", "ENIG"],
        ["基板色", "緑/赤/黄/青/紫なら0.10 mmソルダーマスクブリッジ条件"],
        ["オンラインDFM", "未実行（Gerber外部送信の許可待ち）"],
        ["生産ファイル確認", "U10があるため Yes を推奨。CAM変更の有無を確認"],
        ["発注対象", "このZIPのみ。旧 logger_v1/JLCPCB_20260819_Gerber.zip は使用しない"],
        ["ステンシル", "上面のみなら裏面SMD 10点は手実装"],
    ]
    story += [styled_table(checklist, [45 * mm, 129 * mm]), Spacer(1, 5 * mm), P("ファイル同一性", "JPH2"), styled_table(hashes, [58 * mm, 116 * mm]), Spacer(1, 5 * mm)]
    story += [status_box("最終ゲート", "1) U10をJLCDFM/CAMで受理確認　2) LED両端ラベルの意図確定　3) 裏面実装方法を確定。これらを満たせば、現行Gerberは発注に進める。"), Spacer(1, 4 * mm)]
    story += [P("公式参照: JLCPCB capabilities / NPTH design guide / DRC & DFM guidance / TI TUSB320 datasheet。数値は2026-08-19確認時点。", "JPSmall")]
    return story


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=19 * mm, title="logger_v1 board review 2026-08-19", author="OpenAI Codex")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="review", frames=[frame], onPage=header_footer)])
    doc.build(make_story())
    print(OUT)


if __name__ == "__main__":
    main()
