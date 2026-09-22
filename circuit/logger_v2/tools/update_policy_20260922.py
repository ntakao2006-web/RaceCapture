"""Document-only snapshot and explicit target connectivity. Does not edit CAD files."""
from pathlib import Path
import sexpdata as sx, csv, json, hashlib, re, collections, shutil
P=Path(__file__).resolve().parents[1]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def props(a):return {x[1]:x[2] for x in ch(a,'property')}
def read(p):return sx.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def esc(v):return str(v).replace('|','\\|').replace('\n',' ')
def table(headers,rows):return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(esc(v) for v in row)+'|' for row in rows])+'\n'
def key(ref):
 m=re.match(r'([A-Z]+)(\d+)$',ref);return (m[1],int(m[2])) if m else (ref,0)
files=[P/'logger_v2.kicad_sch',P/'logger_v2_lte_sd.kicad_sch',P/'logger_v2.kicad_pcb',P/'logger_v2_expansion.kicad_sym']
hashes={f.name:sha(f) for f in files}
root=read(files[0]);child=read(files[1]);lib=read(files[3]);defs={z[1]:z for z in ch(lib,'symbol')}
cache={z[1]:z for z in ch(one(root,'lib_symbols'),'symbol')}
parts={};locations=[];alias=[]
def aliasref(d):
 value=d['Value'];role=d.get('Role','')
 if value=='SIM7070G':return 'U6'
 if value=='TXU0204PWR':return 'U7'
 if value=='AP63301WU-7':return 'U8'
 if value=='USBLC6-4SC6':return 'U9' if role.startswith('SIM ') else 'U10'
 return {'2N7002':'Q1','2452796-1':'J8','47219-2001':'J9','LTE service 1x06':'J10','U.FL-R-SMT-1(10)':'J11'}[value]
for e in ch(root,'symbol'):
 d=props(e);ref=d.get('Reference','')
 if ref.startswith('#'):continue
 r=aliasref(d) if '?' in ref else ref
 assert r not in parts
 sy=cache[one(e,'lib_id')[1]]
 pins={one(q,'number')[1]:one(q,'name')[1] for u in ch(sy,'symbol') for q in ch(u,'pin')}
 parts[r]={'d':d,'symbol':one(e,'lib_id')[1],'pins':pins,'dnp':str(one(e,'dnp')[1]),'status':'配置済み','at':one(e,'at')[1:],'uuid':one(e,'uuid')[1]}
 locations.append([ref,r,d['Value'],', '.join(map(str,one(e,'at')[1:])),one(e,'uuid')[1]])
 if '?' in ref:alias.append([r,ref,d['Value'],d.get('Role',''),', '.join(map(str,one(e,'at')[1:]))])
missing=list(csv.DictReader((P/'output/追加部品_20260921.csv').open(encoding='utf-8-sig')))
for row in missing:
 r=row['Reference'];assert r not in parts
 d={'Reference':r,'Value':row['Value'],'MPN':row['MPN'],'Footprint':row['Footprint'],'Supplier':'秋月電子通商' if row['SupplierCode'] else '他社調達','SupplierCode':row['SupplierCode'],'SupplierURL':row['URL'],'Datasheet':row['URL']}
 if r=='C29':d.update(Value='100nF',MPN='GRM188R72A104KA35D',SupplierCode='114559',SupplierURL='https://akizukidenshi.com/catalog/g/g114559/',Datasheet='https://akizukidenshi.com/catalog/g/g114559/')
 sy=defs[d['MPN']]
 pins={one(q,'number')[1]:one(q,'name')[1] for u in ch(sy,'symbol') for q in ch(u,'pin')}
 parts[r]={'d':d,'symbol':'logger_v2_expansion:'+d['MPN'],'pins':pins,'dnp':'no','status':'要追加','at':None}
assert len(parts)==97
# Start with observed, annotated root nets. Do not trust netlist output for U?/J?.
netlist=read(P/'output/doc_current_root.net');current={};target={}
renames={'Net-(C1-Pad1)':'GNSS_ANT_BIAS','Net-(D11-A2)':'GNSS_RF','Net-(D9-LINE1)':'CAN2_H','Net-(D9-LINE2)':'CAN2_L','Net-(D10-LINE1)':'CAN1_H','Net-(D10-LINE2)':'CAN1_L','Net-(U1-RCLK)':'STATUS_LATCH','Net-(U2-LNA_EN)':'GNSS_LNA_EN','Net-(U5-OSC1)':'CAN2_OSC1','Net-(U5-OSC2)':'CAN2_OSC2','Net-(U5-R_{XD})':'CAN2_RX_LOOP','Net-(U5-T_{XD})':'CAN2_TX_LOOP','IMU_SCL':'I2C_SCL','IMU_SDA':'I2C_SDA'}
for net in ch(one(netlist,'nets'),'net'):
 name=one(net,'name')[1];items=[]
 for node in ch(net,'node'):
  r=one(node,'ref')[1];pin=one(node,'pin')[1]
  if '?' in r:continue
  items.append(r+'.'+pin)
  nm=name.lstrip('/')
  if nm.startswith('unconnected-'):nm='NC'
  nm=renames.get(nm,nm)
  current[(r,pin)]=name;target[(r,pin)]=nm
def setnet(net,*nodes):
 for nd in nodes:
  r,pin=nd.split('.');assert r in parts and pin in parts[r]['pins'],nd
  target[(r,pin)]=net
for r,v in parts.items():
 for pin in v['pins']:target.setdefault((r,pin),'NC')
# Explicit header migration and completion of existing logical circuits.
for net,nodes in {
 'LTE_RX_3V3':['J5.8','U7.4'],'LTE_TX_3V3':['J5.7','U7.2'],'LTE_RTS_3V3':['J5.6','U7.3'],'LTE_CTS_3V3':['J2.10','U7.5'],
 'CAN1_TXD':['J5.4','U4.1'],'CAN2_RESET_N':['J4.1','U5.18','R17.2'],'IMU_RESET_N':['J4.2','U3.5'],
 'I2C_SDA':['J2.2','R16.1','U3.3','U2.16'],'I2C_SCL':['J2.1','R15.1','U3.4','U2.17'],
 'STATUS_LATCH':['J5.1','U1.12','R20.1'],'NC':['U2.2','U2.3','J4.6'],
 'LTE_PWRKEY_CTL':['J4.3','R25.1'],'LTE_PWR_EN':['J4.4','U8.2','R23.1'],
 'SD_CS_N':['J4.5','J9.2','R26.1','U10.3'],
 '+3V3':['U7.1','C27.1','J9.4','C25.1','C26.1','R26.2','R27.2','U10.5'],
 '+5V':['U8.3','C16.1','C17.1','C21.1'],
 'GND':['U7.7','U8.4','U9.2','U10.2','Q1.2','J8.4','J8.8','J8.9','J8.10','J9.6','J9.9','J10.4','J11.2','D12.2','C15.2','R22.2','R23.2','R24.2']+[f'C{i}.2' for i in range(16,29)],
 'LTE_VBAT':['U6.55','U6.56','U6.57','L2.2','C15.1','C18.1','C19.1','C20.1','C22.1','C23.1','D12.1','R21.1'],
 'LTE_SW':['U8.5','L2.1','C29.2'],'LTE_BST':['U8.6','C29.1'],'LTE_FB':['U8.1','R21.2','R22.1'],
 'LTE_VDD_EXT':['U6.15','U7.14','U7.8','C28.1','J10.6'],
 'LTE_RX_1V8':['U7.13','U6.10'],'LTE_RTS_1V8':['U7.12','U6.8'],'LTE_TX_1V8':['U6.9','U7.11'],'LTE_CTS_1V8':['U6.7','U7.10'],
 'LTE_PWRKEY_GATE':['R25.2','R24.1','Q1.1'],'LTE_PWRKEY_N':['Q1.3','U6.1'],
 'SIM_VDD':['U6.30','J8.1','C24.1','U9.1','U9.5'],
 'SIM_CLK_MODEM':['U6.32','R28.1'],'SIM_CLK':['R28.2','J8.3','U9.3'],
 'SIM_RST_MODEM':['U6.33','R29.1'],'SIM_RST':['R29.2','J8.2','U9.4'],
 'SIM_DATA_MODEM':['U6.31','R30.1'],'SIM_DATA':['R30.2','J8.6','U9.6'],
 'SPI2_SCK':['J9.5','U10.1'],'SPI2_MOSI':['J9.3','U10.4'],'SPI2_MISO':['J9.7','R27.1','U10.6'],
 'LTE_RF_MODEM':['U6.60','R31.1'],'LTE_RF':['R31.2','J11.1'],
 'LTE_USB_VBUS':['J10.1','U6.24'],'LTE_USB_DP':['J10.2','U6.27'],'LTE_USB_DM':['J10.3','U6.28'],'LTE_BOOT_CFG':['J10.5','U6.6']
}.items():setnet(net,*nodes)
for pin in ['2','17','18','29','39','45','46','54','58','59','61','62','63','64','65']:setnet('GND','U6.'+pin)
allpins={(r,p) for r,v in parts.items() for p in v['pins']};assert set(target)==allpins
groups=collections.defaultdict(list)
for (r,pin),net in target.items():groups[net].append(r+'.'+pin)
assert len(groups['LTE_FB'])==3
assert all(target[('U7',str(p))]=='NC' for p in [6,9])
assert target[('U4','1')]=='CAN1_TXD' and target[('U2','15')]=='NC'
assert all(parts[r]['dnp']=='no' for r in ['R15','R16'])
policy=P/'実装方針.md';original=policy.read_text(encoding='utf8');backup=P/'output/実装方針_詳細化前_20260922.md'
assert not backup.exists();backup.write_text(original,encoding='utf8')
t=original.replace('更新日：2026-09-21','更新日：2026-09-22（現行ファイル照合・端子接続仕様を追記）')
start=t.index('この文書は今後の配線');end=t.index('## 2.')
t=t[:start]+'''本書の目的は、採用品・端子番号・定数・接続ネット・未使用端子処理を固定し、データシートと合わせて同じ電気的回路を再作成できるようにすること。**完成形は第10～15節を規範とする。現在の画面そのものを再現する場合は第16節の現状記録を使う。** 配線の折れ曲がりや文字位置まで一致させるための原図は `.kicad_sch` であり、本書はピン単位の電気的同一性を規定する。

2026-09-22の実ファイルは、メイン回路図69部品（従来59部品＋LTE/SD主要10部品）、別ファイル `logger_v2_lte_sd.kicad_sch` に主要10部品の別配置が残る。メインから別ファイルへの階層シート接続はない。**完成形ではメイン側の10部品を使用し、別ファイルの10部品を二重実装しない。** C15～C29・R21～R31・L2・D12の28部品は現在配置されておらず、第12節に従い追加する。完成形の物理部品数は97（うちDNP 3個）、実装数94。

主要10部品は未採番・未配線である。第10節の番号は今後の採番指定で、現在のファイルに付与した番号ではない。本更新では文書のみ変更し、回路図・配置・配線・PCBには変更を加えない。完成形への変更点を第11節に限定して示す。

過去の部品選定・部品配置更新・AP63301置換記録と20260921/22の旧CSVは、その時点の作業記録。現在配置されているかどうかは本書第16節と現物を優先する。ユーザー指定はUNO Qシールド、秋月優先、裸SMD優先（IMU例外）、MAX-M10M、JCA002、TE 2452796-1、V1同一SDスロット。具体的な追加採番・ネット名・OE固定接続・サービス端子順序は本書で定める設計上の選択であり、メーカーの唯一の指定回路という意味ではない。

'''+t[end:]
t=t.replace('- OEは両側電源の立ち上がりを考慮して制御・固定する。電源断時の逆給電を防ぎ、VDD_EXTを外部から駆動しない。','- OE（U7.8）はVCCBと同じLTE_VDD_EXTへ接続する。VDD_EXTはU6.15からの出力で、外部電源を接続しない。TXU0204の電源断時出力遮断機能を使用する。')
t=t.replace('SIM7070GのSIMインターフェースは1.8V系で使用する。SIM_VDDはモジュールから供給し、3.3Vへ接続しない。','SIM7070GのUART/VDD_EXT、SIMインターフェースはいずれも1.8V系。SIM_VDDはモジュールの専用出力で、VDD_EXTとは別ネットにする。Hardware Design V1.03 §3.6に従い1.8V対応SIMを使用し、3V専用SIMと活線挿抜は対象外。SIM_VDDを外部の3.3VやVDD_EXTへ接続しない。')
t=t.replace('`logger_v2_lte_sd.kicad_sch` に配置済み、現在は未採番・未配線','メイン `logger_v2.kicad_sch` に配置済み、未採番・未配線。別ファイルにも複製あり')
old=next(x for x in t.splitlines() if x.startswith('- 現在配置されている97個'))
t=t.replace(old,'- 完成形97部品の型番・フットプリント・3D参照は第14節に固定する。現在のメインには69部品がある。3Dにはメーカー品のほか、公称形状モデル・汎用モデルを含み、厳密なメーカー形状や実装実績を意味しない。')
t += '\n'+(P/'tools/policy_detail_20260922.md').read_text(encoding='utf8')
t=t.replace('<!-- ALIASES -->',table(['完成形番号','現状番号','部品','識別用途','メイン座標x,y,角度(mm,°)'],alias))
connrows=[]
for net in sorted(groups):
 if net=='NC':continue
 connrows.append([net,', '.join(sorted(groups[net],key=lambda x:(key(x.split('.')[0]),int(x.split('.')[1]))))])
t=t.replace('<!-- NETS -->',table(['ネット名','同一ネットに接続する全端子（部品番号.物理ピン番号）'],connrows))
ncrows=[]
for r in sorted(parts,key=key):
 nc=[p+' ('+parts[r]['pins'][p]+')' for p in sorted(parts[r]['pins'],key=int) if target[(r,p)]=='NC']
 if nc:ncrows.append([r,', '.join(nc)])
t=t.replace('<!-- NC -->',table(['部品','配線しない端子（番号と名称）'],ncrows))
rows=[];modelrows=[];pinrows=[]
for r in sorted(parts,key=key):
 v=parts[r];d=v['d'];fp=d['Footprint'];libname,fpname=fp.split(':');f=read(P/(libname+'.pretty')/(fpname+'.kicad_mod'))
 models=[one(m,'xyz') if False else m[1] for m in ch(f,'model')]
 assert {q[1] for q in ch(f,'pad') if q[1]}==set(v['pins']),r
 for model in models:assert Path(model.replace('${KIPRJMOD}',str(P))).is_file(),model
 rows.append([r,d['Value'],d.get('MPN',''),v['status'],'DNP' if v['dnp']=='yes' else '実装',d.get('Supplier','')+' '+d.get('SupplierCode',''),('[資料/購入先]('+d.get('SupplierURL',d.get('Datasheet',''))+')') if d.get('SupplierURL',d.get('Datasheet','')) else '—'])
 modelrows.append([r,v['symbol'],fp,'<br>'.join(models)])
 for pin in sorted(v['pins'],key=int):pinrows.append([r,pin,v['pins'][pin],target[(r,pin)]])
t=t.replace('<!-- BOM -->',table(['番号','値','MPN','現在の状態','実装区分','調達先・商品番号','資料'],rows))
t=t.replace('<!-- LIBS -->',table(['番号','シンボルID','フットプリントID','3Dモデル'],modelrows))
currentrows=[]
for net in ch(one(netlist,'nets'),'net'):
 name=one(net,'name')[1]
 nodes=[one(n,'ref')[1]+'.'+one(n,'pin')[1] for n in ch(net,'node') if '?' not in one(n,'ref')[1]]
 if nodes:currentrows.append([name,', '.join(nodes)])
t=t.replace('<!-- CURRENT_NETS -->',table(['現在のネット名（未接続も含む）','現在の端子'],currentrows))
t=t.replace('<!-- CURRENT_LOCATIONS -->',table(['現状番号','完成形番号','値','現在座標x,y,角度','UUID'],locations))
childrows=[]
for e in ch(child,'symbol'):
 d=props(e)
 if d.get('Reference','').startswith('#'):continue
 childrows.append([d['Reference'],d['Value'],d.get('Role',''),', '.join(map(str,one(e,'at')[1:])),one(e,'uuid')[1]])
t=t.replace('<!-- CHILD -->',table(['現状番号','値','用途','座標x,y,角度','UUID'],childrows))
assert '<!--' not in t
policy.write_text(t,encoding='utf8')
with (P/'output/完成形ピン接続仕様_20260922.csv').open('w',encoding='utf-8-sig',newline='') as out:
 w=csv.writer(out);w.writerow(['Reference','Pin','Name','Net']);w.writerows(pinrows)
assert hashes=={f.name:sha(f) for f in files},'CAD file changed during documentation update'
report={'cad_hashes':hashes,'target_parts':len(parts),'target_pins':len(allpins),'dnp':[r for r,v in parts.items() if v['dnp']=='yes'],'current_main_parts':len(locations),'duplicate_child_parts':len(childrows),'parts_to_add':len(missing),'every_pin_assigned_once':True,'all_pin_sets_match_footprints':True,'all_models_exist':True,'cad_unchanged':True}
(P/'output/実装方針_検証_20260922.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
