from pathlib import Path
import json,csv,hashlib,runpy,contextlib,io,urllib.request
P=Path(__file__).resolve().parent
root=P.parents[1]/'circuit/logger_v2'
src=json.loads((root/'output/order_source_20260923.json').read_text(encoding='utf8'))
by={r['Reference']:r for r in src}
rows=[]
def add(refs,desc,package,mpn,dk,qty,url,note,status='在庫表示あり'):
 refs=refs.split(); rows.append(dict(refs=refs,description=desc,package=package,mpn=mpn,dk=dk,needed=len(refs),spare=qty-len(refs),quantity=qty,url=url,note=note,status=status,footprint='; '.join(sorted({by[r]['Footprint'] for r in refs})),original='; '.join(sorted({by[r].get('MPN','') or '(空欄)' for r in refs}))))
def url(m,part,id):return f'https://www.digikey.jp/en/products/detail/{m}/{part}/{id}'
add('C1 C2 C8 C12 C13 C20 C28','10µF ±10% X7R 10V','0805 / 2012','CL21B106KPQNFNE','1276-2934-1-ND',10,url('samsung-electro-mechanics','CL21B106KPQNFNE',3891020),'旧445-6857-1-NDが注文画面で入荷待ちのため差替え。Samsung製10µF±10%・10V・X7R、2.00×1.25mm、高さ最大1.40mm。同じ0805ランドに実装可能。DigiKey製品ページの直販在庫65,218個、CT10個284円（税別）表示を2026-09-23確認。実装7＋予備3。C20は現行Value=10u。')
add('C3 C4 C5 C6 C14 C17 C19 C21 C22 C23 C24 C25 C26 C27','100nF ±10% X7R 100V','0603 / 1608','GRM188R72A104KA35D','490-3285-1-ND',25,url('murata-electronics','GRM188R72A104KA35D',702826),'現行MPNを維持。C21～C27も現行Value=0.1u。')
add('C7','330µF 6.3V ポリマー','φ6.3 × H5.9mm','6SVPC330M','P16611CT-ND',2,url('panasonic-industry','6SVPC330M',4204943),'指定品維持。ESR17mΩ、極性あり。')
add('C9 C10','15pF ±5% C0G 50V','0603 / 1608','CC0603JRNPO9BN150','311-1060-1-ND',5,url('yageo','CC0603JRNPO9BN150',302794),'Value=15pを採用。古いSpecificationの18pF/CL12pFは不採用。')
add('C11','10nF ±10% X7R 100V','0603 / 1608','GRM188R72A103KA01D','490-GRM188R72A103KA01DCT-ND',5,url('murata-electronics','GRM188R72A103KA01D',3845635),'現行Value=0.01u。耐圧は元の50V以上。')
add('C15','1µF ±10% X7R 50V','0805 / 2012','C2012X7R1H105K085AC','445-14539-1-ND',3,url('tdk-corporation','C2012X7R1H105K085AC',3951775),'同サイズ・同容量・同耐圧。高さ最大1.0mm。新規設計非推奨品だが在庫表示あり。')
add('D1 D4','CAN用 双方向2線 TVS 24V','SOT-23-3','ESDCAN24-2BLY','497-13262-1-ND',4,url('stmicroelectronics','ESDCAN24-2BLY',3661760),'PEC3824C2A-AUの代替。1/2=CAN、3=GND。24V、Vbr最低27V、容量最大30pF。クランプ特性は元品と完全同一ではない。')
add('D5 D6 D7 D8 D9 D10 D11 D12','緑LED 571nm / Vf約2V','0805 / 2012','LTST-C170KGKT','160-1414-1-ND',12,url('liteon','LTST-C170KGKT',386776),'同0805、1=カソード、2=アノード。元品と発光色・明るさに差あり。')
add('J6 J9','Micro-Fit 3.0 基板側4極','2×2 / 3.0mm 横向きTHT','43045-0400','WM1814-ND',2,url('molex','0430450400',252527),'43045-0400と同じ品番の表記違い。指定どおり2個だけ。ケーブル側・圧着端子は含めない。')
add('J11','nanoSIM ヒンジ式ソケット','TE専用フットプリント','2452796-1','343-2452796-1CT-ND',2,url('te-connectivity-linx','2452796-1',21284797),'SDとは別部品。現行指定品維持。マーケットプレイス品ではなくDigiKey直販CTを指定。')
add('L1','2.2µH ±20% 電源インダクタ','2.5×2.0×1.2mm','DFE252012F-2R2M=P2','490-13055-1-ND',3,url('murata-electronics','DFE252012F-2R2M-P2',5812591),'旧490-10649-1-NDがユーザーのカートで規制表示のためFシリーズへ差替え。2.2µH±20%、外形・高さ・推奨ランド（内側1.2/外側2.8/幅2.0mm）は元品と一致。Irms2.3A / Isat3.3A / DCR82mΩ最大（元2.2A/3.0A/84mΩ）。DigiKey直販190,191個、1個税別42円の表示を2026-09-23確認。3個＝実装1＋予備2。ユーザーカートでの規制解除は未確認。')
add('L2','27nH RF巻線インダクタ','0603 / 1608','LQW18AN27NJ00D','490-1174-1-ND',3,url('murata-electronics','LQW18AN27NJ00D',584382),'指定品維持。440mA、SRF3.7GHz以上。一般電源用インダクタには置換しない。')
add('Q1','Nch MOSFET 60V','SOT-23','2N7002ET1G','2N7002ET1GOSCT-ND',3,url('onsemi','2N7002ET1G',1792136),'2N7002相当。1=G、2=S、3=Dで基板と一致。')
for refs,value,mpn,dk,qty,id,note in [
 ('R1 R5 R11','100kΩ ±0.1%','RT0603BRD07100KL','YAG1235CT-ND',10,1072187,'R11の帰還抵抗精度を優先し3個とも0.1%に統一。'),
 ('R4 R23 R24 R25 R26 R27 R28 R29 R30','1kΩ ±1%','RC0603FR-071KL','311-1.00KHRCT-ND',15,729790,'Value基準。古いMPNに10kΩ表記が残る箇所あり。'),
 ('R6 R8 R22 R31 R32','47kΩ ±1%','RC0603FR-0747KL','311-47.0KHRCT-ND',10,727253,'同サイズの1%品。'),
 ('R10','374kΩ ±1%','RC0603FR-07374KL','311-374KHRCT-ND',5,730136,'電源帰還上側。Value=374kを採用。'),
 ('R14 R16','120Ω ±1%','RC0603FR-07120RL','311-120HRCT-ND',5,726920,'現行DNP=noのため含む。接続するCANバスの終端配置に従って実装する。'),
 ('R17 R18 R19','22Ω ±1%','RC0603FR-0722RL','311-22.0HRCT-ND',10,727055,'現行Value=22Ω。'),
 ('R20 R21','0Ω ジャンパ','RC0603JR-070RL','311-0.0GRCT-ND',5,726675,'現行Value=0Ω。')]:
 add(refs,value+' 0.1W','0603 / 1608',mpn,dk,qty,url('yageo',mpn,id),note)
add('R15','27Ω ±5% 1W','2512 / 6332','CRCW251227R0JNEG','541-27XCT-ND',3,url('vishay-dale','CRCW251227R0JNEG',1178543),'指定品維持。ここは0603ではなく2512・1Wが必要。')
for refs,desc,pkg,mpn,dk,qty,m,id,note in [
 ('U2','3A 降圧DC/DC','TSOT26','AP63301WU-7','31-AP63301WU-7CT-ND',2,'diodes-incorporated',10491607,'指定品維持。AP63300/固定電圧版と混同しない。'),
 ('U3','4bit レベル変換','TSSOP-14 / P0.65','TXU0204PWR','296-TXU0204PWRCT-ND',2,'texas-instruments',14641512,'指定品維持。PWパッケージ。'),
 ('U4','CANコントローラ＋トランシーバ','SSOP-28 / 幅5.3mm','MCP25625T-E/SS','MCP25625T-E/SSCT-ND',1,'microchip-technology',4860100,'指定品維持。/SSパッケージ。高価なため予備なし。'),
 ('U6','LTE Cat-M/NB-IoTモジュール','LCC-68 / 24×24mm','SIM7070G','3781-SIM7070G-ND',1,'simcom-wireless-solutions-limited',15841451,'指定の裸モジュール。開発ボードではない。高価なため予備なし。'),
 ('U7','CANトランシーバ','SOIC-8 / 幅3.9mm','ATA6561-GAQW-N','ATA6561-GAQW-NCT-ND',2,'microchip-technology',9453105,'指定品維持。VDFN版を選ばない。'),
 ('U8','8bit シフトレジスタ','SOP-16 / 幅5.3mm','TC74HC595AF(EL,F)','264-TC74HC595AF(EL,F)CT-ND',2,'toshiba-semiconductor-and-storage',6679568,'指定AFのSOP16を維持。一般的な幅3.9mm SOICの74HC595は合わない。'),
 ('U9 U10','4線ESD保護','SOT-23-6','USBLC6-4SC6','497-4492-1-ND',4,'stmicroelectronics',725216,'指定品維持。2線品USBLC6-2SC6とは別品。')]:
 add(refs,desc,pkg,mpn,dk,qty,url(m,mpn.replace('/','-').replace('(','-').replace(',','-').replace(')',''),id),note)
add('Y1','水晶 20MHz / CL10pF','3225 / 4端子','ABM8-20.000MHZ-10-B1U-T','535-14973-1-ND',2,url('abracon-llc','ABM8-20-000MHZ-10-B1U-T',9997881),'同寸法3.2×2.5mm、CL10pF。1/3=水晶、2/4=GND。発振余裕は実機で確認。')
add('D2','RF用 双方向TVS 5.5V / 0.4pF','DFN1006D-2 / SOD882D','PESD5V0F1BRLDYL','1727-PESD5V0F1BRLDYLCT-ND',3,url('nexperia-usa-inc','PESD5V0F1BRLDYL',4843313),'候補のみ。直販在庫0。掲載入荷予定2027-06-29。SOD882Dのパッド適合を最終確認するまで発注保留。マーケットプレイス在庫はMOQ・送料が別のため不採用。','保留：在庫・実装確認')
add('D3','LTE電源 双方向TVS 4.5V','DFN1006-2 / SOD882','PTVS4V5D1BLYL','1727-PTVS4V5D1BLYLCT-ND',3,url('nexperia-usa-inc','PTVS4V5D1BLYL',7669954),'PESDHC2FD4V5Bの候補のみ。直販在庫0。Vwm4.5V/Vbr4.7Vは一致、クランプ13.2V@34A（元12V@25A）で完全同等ではない。実装寸法・保護特性の最終確認まで発注保留。','保留：在庫・代替確認')
changes={
 'R1':('CRT0603-BY-1003ELF','CRT0603-BY-1003ELFCT-ND',url('bourns-inc','CRT0603-BY-1003ELF',1775045),'0603・100kΩ・0.1%・0.1W。R11の帰還精度を優先し同一品へ統一。'),
 'R17':('CRCW060322R0FKEA','541-22.0HCT-ND',url('vishay-dale','CRCW060322R0FKEA',1179617),'0603・22Ω・1%・0.1Wを維持。在庫表示のあるVishay品。'),
 'R15':('RMCF2512JT27R0','RMCF2512JT27R0CT-ND',url('stackpole-electronics-inc','RMCF2512JT27R0',4425469),'2512・27Ω・5%・1Wを維持。同サイズのStackpole品へ置換。'),
 'U9':('USBLC6-4SC6Y','497-11883-1-ND',url('stmicroelectronics','USBLC6-4SC6Y',2756524),'USBLC6-4SC6の車載グレード品。同じ4線・SOT23-6・ピン配置。2=GND、5=VBUS、1/3/4/6=I/O。')}
for r in rows:
 if r['refs'][0] in changes:
  r['mpn'],r['dk'],r['url'],r['note']=changes[r['refs'][0]]
 if r['refs'][0]=='R10':r['url']=url('yageo',r['mpn'],727189)
 if r['refs'][0] in ['R10','R14','R20','C9','C11']:
  r['quantity']=10;r['spare']=10-r['needed'];r['note']+=' 少量価格の段差も考慮して10個。'
for r in rows:
 r['supplier']='DigiKey'
 if r['refs']==['D2']:
  r.update(mpn='PESD5V0F1BL-QYL',dk='C7508780',supplier='LCSC',package='DFN1006-2 / SOD882',quantity=5,spare=4,status='別調達：LCSC指定品',url='https://www.lcsc.com/product-detail/C7508780.html',note='現在指定のPESD5V0F1BL-Qの梱包品番。代替ではなく指定品を採用。LCSC在庫38,210個表示、最小5個・5個単位。5個購入（実装1＋予備4）。秋月・千石では適合品の販売を確認できず。2026-09-23調査。')
 if r['refs']==['D3']:
  r.update(dk='C478159',supplier='LCSC（候補）',url='https://www.lcsc.com/product-detail/C478159.html',status='保留：代替特性確認',quantity=20,spare=19,note='LCSCにPTVS4V5D1BLYLの在庫347,140個表示、最小20個。指定品PESDHC2FD4V5B（C110686）は在庫なし。候補はDFN1006-2・4.5V双方向だが、クランプ保証値が異なるため未確定。秋月のDF2S23P2CTCは21V・1.6×0.8mmで不適合。2026-09-23調査。')
owned=set('U1 U5 J1 J2 J3 J4 J5 J8 J7 J10 J12 R2 R3 R7 R9 R12'.split())
for r in rows:
 if r['refs']==['D2']:
  r.update(mpn='AQ3045-01ETG',dk='F9321CT-ND',supplier='DigiKey',description='RF用 双方向TVS 5.3V / 0.35pF',package='SOD882 / 1.0×0.6mm',quantity=3,spare=2,status='在庫表示あり：機能代替',url=url('littelfuse-inc','AQ3045-01ETG',6347831),note='GNSSアンテナESD用の機能代替。SOD882・端子ピッチ0.65mm、現PCBの0.4×0.7mmパッドに端子が重なる。容量typ0.35/max0.5pF（元0.4/0.55）、双方向。VRWM5.3V（元5.5）、Vc最大12V@1A（元11V@1A）で全特性同一ではない。3A・ESD±30kV。DigiKey直販82,168個表示。RF/ESD実機試験未実施。')
 if r['refs']==['D3']:
  r.update(mpn='CSPSBHC4V5LB-TP',dk='353-CSPSBHC4V5LB-TPCT-ND',supplier='DigiKey',description='LTE電源 双方向TVS 4.5V',package='CSP1006-2 / 1.0×0.6mm',quantity=3,spare=2,status='在庫表示あり：機能代替',url=url('mcc-micro-commercial-components','CSPSBHC4V5LB-TP',22557216),note='3.8V電源ESD用の機能代替。4.5V双方向、端子ピッチ0.65mm・長さ0.20～0.30/幅0.45～0.55mmで現PCBの0.4×0.6mmパッドに実装可能。Vc最大8.5V@50A/10.5V@100A（元12V@25A）、100A/900W。容量最大300pF、Tj上限125℃。元品のVhold最低4.6Vに対し本品は保証値記載なし、1Aクランプも保証値なし。全特性同一ではなく、実機サージ後復帰は未検証。DigiKey地域ページに10,002個表示。')
dnp={r['Reference'] for r in src if r['DNP']=='yes'}
used=[r for a in rows for r in a['refs']]
assert len(used)==len(set(used))==79
assert set(used)|owned|dnp==set(by) and not (set(used)&(owned|dnp))
assert sum(r['needed'] for r in rows if r['supplier']=='DigiKey')==79
excluded=[dict(ref=r['Reference'],value=r['Value'],footprint=r['Footprint'],reason='未実装（DNP）' if r['Reference'] in dnp else '手持ち品',note='0603（1608）・0.1W以上。抵抗値だけでなく実物サイズを確認。' if r['Reference'].startswith('R') and r['Reference'] not in dnp else '') for r in src if r['Reference'] in owned|dnp]
data=dict(date='2026-09-23',rows=rows,excluded=excluded,counts=dict(source=98,owned=16,dnp=3,purchase=79,ready=79,external=0,hold=0),hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [root/'logger_v2.kicad_sch',root/'logger_v2.kicad_pcb']})
(P/'bom_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(data['counts']), 'lines',len(rows),'order qty ready',sum(r['quantity'] for r in rows if not r['status'].startswith('保留')))
