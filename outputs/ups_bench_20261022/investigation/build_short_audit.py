from pathlib import Path
import xml.etree.ElementTree as ET
import json,html,itertools

out=Path(__file__).parent
t=ET.parse(out/'inductor_current.xml')
components={c.attrib['ref']:c.findtext('value') for c in t.findall('./components/comp')}
pin_net={f"{n.attrib['ref']}.{n.attrib['pin']}":net.attrib['name'] for net in t.findall('./nets/net') for n in net.findall('node')}
aliases={'+5V':'SYS/USB 5V','+CAP':'CAP全体','CAP-MID':'中点','/LX':'LX',
 'Net-(U1-FBCH)':'FBCH','Net-(U1-FBCR)':'FBCR','Net-(U1-FBS)':'FBS','Net-(U1-ISET)':'ISET',
 'Net-(Q2-D)':'ENC','Net-(Q1-G)':'U2 OUT/Q1,Q2ゲート','Net-(Q1-D)':'Q1 D',
 'Net-(U2-IN+)':'REF/IN+','Net-(U2-IN-)':'IN−','Net-(U2-HYST)':'HYST'}
name=lambda n:aliases.get(n,n)
cases=[]
def add(refs,level,result,phase,energy,limit,note=''):
 for ref in refs.split():
  cases.append(dict(id=f'C-{ref}',location=f'{ref} 両端短絡',refs=[ref],level=level,result=result,phase=phase,energy=energy,limit=limit,note=note))
add('C6 C7 C8 R4','高','上段が短絡。下段C12〜C14にCAP全体の電圧がかかり、2.7V超過のおそれ。充電停止は全体3.95Vしか見ない。','接続・充電時／充電済み時','上段の既存電荷＋USBからの再充電','セル電圧は制限されない','下段は必ず3.95Vに達するとは限らず、短絡・漏れ・電源保護で変わる。短絡発生時には上段自身にも放電電流が流れる。')
add('C12 C13 C14 R6','高','下段が短絡。上段C6〜C8にCAP全体の電圧がかかり、2.7V超過のおそれ。','接続・充電時／充電済み時','下段の既存電荷＋USBからの再充電','セル電圧は制限されない','短絡発生時には下段自身にも放電電流が流れる。')
add('C9','高','CAP全体がGNDへ直結。蓄電エネルギーが短絡部・キャパ内部抵抗・配線へ放出される。L1は直接放電経路に含まれない。','充電済みならUSBの有無を問わない','CAPバンク（満充電計算約82J）','キャパから短絡への直接放電はU1制限外','空のキャパ＋USB接続だけなら、充電電流は正常なU1に制限される。')
add('C1 C2 C3 C4 C5 C15','高','SYS/USB 5VをGNDへ直結。短絡部・USB電源経路・接点・配線が発熱候補。','USB接続時が特に該当','USB＋SYSコンデンサ。バックアップ時はU1経由','USBからの電流はU1では制限されず、USB電源の保護に依存','キャパの大きな蓄電エネルギーが直接ここへ流れる構成ではない。')
add('C10 R7','高','FBCHがGNDに固定され、設定3.95Vでの充電停止判定を失う。キャパ全体の過充電・段間不均衡を疑う。','USB接続・充電時','USBからU1経由の充電','正常なISET電流制限は残るが、充電終止電圧の制御を失う','充電は降圧動作なので無限に電圧が上がるという意味ではない。USB電圧付近まで上昇する可能性があり、均等なら直ちに各段2.7V超過とは限らない。')
add('C11','高','FBCRがGNDへ落ち、R5経由でFBCHもほぼ0Vになる。RDYだけでなく充電停止も失う。','USB接続・充電時','USBからU1経由の充電','正常なISET電流制限は残る','C11は単なる状態表示用コンデンサではなく、FBCHと抵抗列を共有している。')
add('R2','高','FBSがGND固定となり、SYS電圧が正常でも不足と誤認する。バックアップ昇圧の制御を失い、SYS過電圧・U1/UNO Q/USB側への影響のおそれ。','充電済みでUSBを再接続する場合も対象','CAPバンクからU1経由','ISET電流制限が正常でも出力電圧制御は失われる','正常な電源同士の切替とは異なる故障。故障時電圧やICの停止挙動は未確認。')
add('R10','高','ISETがGNDに直結。指定20〜100kΩの電流設定範囲を外れ、正常なピーク電流を保証できない。','USB接続・充電・バックアップ','USB／CAP','電流設定が仕様外','0Ωなら必ず何A流れる、とデータシートからは断定できない。')
add('R8','条件付き','Q1がONのときISETがGNDへ直結し、電流設定が仕様外になる。Q1がOFFならR10=100kΩが残る。','主にバックアップ／切替過渡','USB／CAP','Q1の状態に依存','R8単独短絡だけで、通常USB充電中に必ず大電流となるわけではない。')
add('R13','高','ENCがSYSへ直結するため、Q2がONするとSYS→Q2 D-S→GNDの短絡が成立。Q2自体の発熱・発煙候補。','低電圧判定時・切替時。高いUSB電圧でQ2がOFFなら成立しない','USB／U1出力','USB側の電流はU1制限外','通常R13=100kΩがQ2の電流を制限している。')
add('R1','低','FBS=SYSとなりバックアップ設定が約1.2V相当へ変化し、正常な保持ができない。充電側のCAP電圧制御は残る。','バックアップ／切替','制御信号','他の故障がなければ大電流の直接経路ではない')
add('R3','低','CAP充電停止設定が約0.624Vへ低下。保持不足になるが、この短絡単独で過充電にはならない。','充電時','制御信号','電流制限・低い充電停止電圧が残る')
add('R5','低','FBCRとFBCHが接続され、CAP停止設定は約3.83V。単独短絡で充電上限が高くなる故障ではない。','充電時','制御信号','電圧制御が低い値で残る')
add('R9','条件付き','U2 IN−にSYSが直結し入力の正常な共通モード範囲を外れる。充電許可・電流切替の判定が不定になり得る。','接続・切替時','制御信号','CAP充電停止・U1のISET抵抗は残る','単独でL1へ無制限の大電流を流す経路ではない。')
add('R12','低','U2 IN−=0VとなりOUTはHigh、Q2が充電を禁止する。Q1はバックアップ用の約5Aピーク設定へ。','接続・充電時','制御信号','正常なR8/R10なら約5Aピーク範囲','充電しない症状に合うが、この故障単独で30A定格L1の焼損は説明しにくい。')
add('R11','条件付き','U2 OUTをGNDへ短絡。U2出力段の負荷・発熱候補。Q1/Q2ゲートはLowとなり低電圧時の充電禁止が働かない。','U2がHighを出そうとする状態','U2の出力段','U2の出力能力・短絡仕様に依存','U1のFBCH充電停止と100kΩの電流設定は残る。U2の出力短絡は直ちに発煙することを意味しない。')
add('R14','低','HYST=REFとなりヒステリシスがなくなる。境界付近の充電ON/OFF反復はあり得るが大電流の直接経路ではない。','電源電圧が判定境界付近','制御信号','U1電流制限は残る')
add('R15','条件付き','HYSTがGNDに落ち、推奨設定範囲を外れる。基準電圧の負荷や切替判定の異常が候補。','接続・切替時','制御信号','R14がREFからの電流を制限','L1への大電流の直接経路ではない。')
add('C16','条件付き','REF/IN+をGNDへ短絡。U2基準出力の負荷・判定異常。通常はOUTがLowになり充電許可側へ。','接続・充電時','U2基準出力','U1のFBCH充電停止・ISET電流設定は残る','基準出力短絡だけでL1が発煙するとは言えない。')
add('L1','高','LXとCAPが直結し、U1の下側スイッチON時にCAPをGNDへ直接放電し得る。上側ON時にはUSBとCAPが低インピーダンスで接続される。','接続・充電・バックアップ','USB／CAP','インダクタがないため正常なスイッチ電流の立上り制御が成立しない','外部ブリッジでL1を迂回する場合、主にU1・短絡部・キャパが発熱候補で、L1巻線に全電流が流れるとは限らない。')

def pair_case(a,b):
 na,nb=pin_net.get(a,''),pin_net.get(b,''); s=frozenset((na,nb))
 if na==nb:return ('同一ネット','もともと同じ電位で、電気的な新しい短絡ではない。','全状態','なし','なし')
 rules=[
 ({'+CAP','CAP-MID'},'高','上段の短絡・放電と、下段への全体電圧印加。','接続・充電済み','CAP／USB','段ごとの過電圧保護なし'),
 ({'CAP-MID','GND'},'高','下段の短絡・放電と、上段への全体電圧印加。','接続・充電済み','CAP／USB','段ごとの過電圧保護なし'),
 ({'+CAP','GND'},'高','CAP全体を直接放電。短絡部・キャパ・配線が発熱候補。','充電済みならUSBなしでも成立','CAP','U1電流制限外'),
 ({'+5V','GND'},'高','USB電源を直接短絡。短絡部・配線・接続端子が発熱候補。','USB接続時','USB','USB電源側の保護に依存'),
 ({'+5V','/LX'},'高','SYS→LX→L1→CAPへ、U1上側スイッチを迂回する充電経路。','USB接続時','USB／CAP','U1の正常なスイッチ電流制限を迂回'),
 ({'/LX','GND'},'高','充電済みCAP→L1→短絡→GND。USBから短絡への直接電流はL1を迂回する。','充電済み時。接続時だけの発煙には追加条件が必要','CAP。USBはU1上側スイッチ経由','外部短絡によるCAP放電は制限外'),
 ({'/LX','+CAP'},'高','L1両端短絡と同等。U1スイッチ動作でCAP直結放電・無制御充電のおそれ。','スイッチ動作中','USB／CAP','正常なLによる電流立上り制御を失う'),
 ({'+5V','+CAP'},'高','USBとキャパを直結。充電電流制御と3.95Vの充電停止を迂回。','USB接続時','USB／CAP','U1制限外。USB電圧・各段バランスに依存'),
 ({'+5V','CAP-MID'},'高','下段へUSB電圧が直接印加される。上段にも逆電圧などの異常が生じ得る。','USB接続時','USB／CAP','U1制限外'),
 ({'Net-(U1-FBCH)','GND'},'高','FBCH=0Vで3.95V充電停止を失う。','USB接続・充電時','USBからU1経由','ISET電流制限は残る'),
 ({'Net-(U1-FBCR)','GND'},'高','FBCRを接地するとR5経由でFBCHも低下し、充電停止を失う。','USB接続・充電時','USBからU1経由','ISET電流制限は残る'),
 ({'Net-(U1-FBS)','GND'},'高','SYS不足を誤検出し昇圧制御を失う。SYS過電圧のおそれ。','充電済み・切替時','CAP','ISET電流制限が残っても電圧制御を失う'),
 ({'Net-(U1-ISET)','GND'},'高','電流設定0Ωは指定20〜100kΩ範囲外。正常な電流制限値を保証できない。','スイッチ動作中','USB／CAP','仕様外。具体的な故障時電流は不明'),
 ({'Net-(Q2-D)','+5V'},'高','ENC=SYS。Q2 ON時にSYSをQ2経由でGNDへ短絡し、Q2が発熱候補。','Q2 ON時','USB／U1出力','R13を迂回'),
 ({'Net-(U1-ISET)','+5V'},'条件付き','ISETがSYS電圧へ固定され電流設定が仕様外。U1内部・電流制御への影響を要確認。','接続・動作中','制御端子へSYS印加','指定抵抗条件を外れる'),
 ({'+5V','unconnected-(U1-RDY-Pad3)'},'高','RDYがLowを出すとSYS→RDY内部出力段→GNDの短絡。U1が発熱候補。','特に未充電でUSB接続した直後','USB','状態出力はパワー端子ではなく通常はプルアップ抵抗が必要'),
 ({'+CAP','unconnected-(U1-BKB-Pad4)'},'高','BKBがLowになるバックアップ時、CAPがBKB出力段へ流入。U1が発熱候補。','バックアップ時が特に該当','CAP','状態出力段は大電流放電用ではない'),
 ({'+5V','Net-(Q1-G)'},'高','U2 OUTをSYSへ固定。U2がLowを出すとSYS→U2出力段→GNDの短絡。','正常なUSB電圧でU2 OUTがLowとなる状態','USB','外付け制限抵抗なし'),
 ({'+5V','Net-(U2-IN+)'},'条件付き','U2 REF/IN+へSYSが直接印加。基準回路への逆注入・判定異常・U2損傷のおそれ。','USB接続時','USB','REF出力への外部強制電圧は通常動作ではない'),
 ({'+5V','+3V3'},'高','UNO Qの3.3V系へ5Vを印加するおそれ。主にUNO Q側が損傷・発熱候補。','USB接続時','USB','UPS ICはこの短絡を遮断しない'),
 ({'Net-(Q2-D)','GND'},'低','ENC=0Vで充電禁止。単独では大電流の直接経路ではない。','充電時','制御信号','充電停止側'),
 ({'Net-(Q1-G)','GND'},'条件付き','U2 OUTの短絡負荷。Q1/Q2はOFF側になり、U1の電流設定と充電終止は残る。','U2がHighを出そうとする状態','U2出力段','出力短絡の発熱はあり得るがL1大電流へ直結しない'),
 ({'Net-(U2-IN+)','GND'},'条件付き','U2 REF/IN+短絡。判定異常・基準出力の負荷。','接続時','U2基準回路','U1の充電終止・電流設定は残る'),
 ({'Net-(U1-FBCR)','Net-(U1-FBCH)'},'低','R5短絡と同等。充電停止設定は約3.83Vへ低下。','充電時','制御信号','充電終止は残る'),
 ({'Net-(U2-HYST)','Net-(U2-IN+)'},'低','HYST=REFでヒステリシスがなくなる。','切替境界付近','制御信号','大電流の直接経路ではない')]
 for nets,level,result,phase,energy,limit in rules:
  if s==frozenset(nets):return level,result,phase,energy,limit
 if '/LX' in s and 'CAP-MID' in s:return ('高','中点をスイッチノードへ接続。下側スイッチONで下段が短絡し、上側ONで中点へSYSを印加する異常経路。','スイッチ動作中','USB／CAP','各段の過電圧・逆電圧やU1損傷のおそれ')
 if '+5V' in s and s & {'Net-(U1-FBCH)','Net-(U1-FBCR)'}:return ('高','CAPが未充電のときFBCH/FBCRへSYSが直接印加され、CAP+0.3Vの絶対最大定格を超える。入力保護経由の電流・U1損傷のおそれ。','特に未充電でUSB接続時','USB','通常の充電電流制限の対象でない入力注入')
 if s & {'+CAP','CAP-MID'} and 'Net-(Q1-G)' in s:return ('高','蓄電ノードをU2 OUTへ接続。OUTがLowを出すとU2出力段へ直接放電する経路となる。','CAP充電済みでU2 OUTがLowのとき','CAP','U2出力段は蓄電バンク放電用ではない')
 if '/LX' in s:return ('条件付き','LXのスイッチング波形が信号端子へ侵入。入力保護経由の電流・IC損傷・誤制御のおそれ。','スイッチ動作中','LXのパルス','正常動作の範囲外。結果の定量予測はしない')
 if 'Net-(U1-ISET)' in s or 'Net-(U1-FBS)' in s:return ('条件付き','電流設定またはSYS電圧帰還を他信号と接続し、制御条件が崩れる。過電流・過電圧の有無は追加解析が必要。','切替・動作中','制御異常を介したUSB／CAP','正常な保護を保証できない')
 if '+CAP' in s or 'CAP-MID' in s:return ('条件付き','蓄電ノードを別信号へ接続。IC入力保護や出力段へ電流が流れる場合は局所発熱のおそれ。','充電済み時／充電中','CAP／USB','接続された信号の内部構造に依存')
 return ('低／条件付き','直接の大電流経路は確認できない。信号混入・出力同士の競合・再起動・充電許可の異常などを確認する。','信号の状態に依存','主に信号回路','この短絡単独でL1やキャパの発煙と断定しない')

# Every transistor terminal pair, adjacent IC pin pair including corners,
# each U1 signal/power pin to its exposed ground pad, and adjacent header pins.
for ref in ['Q1','Q2']:
 for a,b in itertools.combinations(range(1,4),2):
  aa,bb=f'{ref}.{a}',f'{ref}.{b}';desc=pair_case(aa,bb)
  if a==2 and b==3:
   desc=('条件付き','Q1 D-S短絡ではR8が常時有効になり充電が平均約2.46A・ピーク約4.92Aとなる。これは30A定格L1の焼損を単独では説明しない。','USB接続・充電時','USB','正常なISET約20.3kΩの範囲') if ref=='Q1' else ('低','Q2 D-S短絡でENCがGNDへ固定され充電できない。','充電時','制御信号','充電停止側')
  cases.append(dict(id=f'{ref}-{a}-{b}',location=f'{aa} ↔ {bb}',refs=[ref],level=desc[0],result=desc[1],phase=desc[2],energy=desc[3],limit=desc[4],note='三端子部品の端子間故障。ゲートを含む短絡は他の端子にも結合し得る。'))
for ref,count in [('U1',16),('U2',8),('J1',10),('J2',8),('J3',6),('J4',8)]:
 pairs=[(n,n+1) for n in range(1,count)]
 if ref.startswith('U'):pairs.append((count,1))
 if ref=='U1':pairs.extend((n,17) for n in range(1,17))
 for a,b in pairs:
  aa,bb=f'{ref}.{a}',f'{ref}.{b}';desc=pair_case(aa,bb)
  cases.append(dict(id=f'{ref}-{a}-{b}',location=f'{aa} ↔ {bb}',refs=[ref],level=desc[0],result=desc[1],phase=desc[2],energy=desc[3],limit=desc[4],note=f'{name(pin_net.get(aa,""))} ↔ {name(pin_net.get(bb,""))}'))
geo=json.loads((out/'short_geometry.json').read_text(encoding='utf-8'))
critical=['+5V','+CAP','CAP-MID','/LX','GND','Net-(U1-FBCH)','Net-(U1-FBCR)','Net-(U1-FBS)','Net-(U1-ISET)','Net-(Q1-G)','Net-(Q2-D)']
network=[]
representative={net:next(pin for pin,n in pin_net.items() if n==net) for net in critical}
for i,(a,b) in enumerate(itertools.combinations(critical,2),1):
 d=pair_case(representative[a],representative[b])
 network.append(dict(id=f'N{i:02}',location=name(a)+' ↔ '+name(b),level=d[0],result=d[1],phase=d[2],energy=d[3],limit=d[4]))
near=[]
for i,p in enumerate(geo['near_pad_pairs'],1):
 d=pair_case(p['a'],p['b'])
 near.append({**p,'id':f'P{i:02}','level':d[0],'result':d[1]})
data={'scope':'40部品の全二端子部品短絡32件、Q1/Q2各3組、U1/U2隣接ピンとU1露出GND、全ヘッダ隣接ピン。加えて同一銅層の異ネットパッド近接44組を確認。非隣接端子の任意の組合せ・全配線とゾーン間距離・曲げたリードや金属ケースの接触は網羅を保証しない。',
 'assumptions':'既存の短絡があるとは断定しない。単一短絡故障を基本に、他条件が必要な場合を明記。IC自体が正常、指定部品が実装されていることは未確認。',
 'saved_pcb_drc':{'violations':0,'unconnected':0,'does_not_prove':'実装した基板にブリッジ・異物・部品破損がないこと'},
 'bank_energy_J_at_3_95V':81.95,'cases':cases,'critical_net_pairs':network,'near_pad_pairs':near,
 'measurement_limit':'大容量キャパ接続中は、正常でも抵抗レンジや導通で長時間低く見える。ブザーや低抵抗だけで短絡判定しない。放電確認前に抵抗測定・取り外し・短絡放電を行わない。',
 'sources':['https://www.analog.com/media/en/technical-documentation/data-sheets/max38890.pdf','https://www.analog.com/media/en/technical-documentation/data-sheets/144012fd.pdf','https://www.eaton.com/us/en-us/products/electronic-components/topics/supercapacitor-applications-guide.html']}
(out/'short_fault_audit.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
e=lambda x:html.escape(str(x))
def table(rows,cols):
 return '<table><thead><tr>'+''.join('<th>'+e(title)+'</th>' for key,title in cols)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(r.get(key,''))+'</td>' for key,title in cols)+'</tr>' for r in rows)+'</tbody></table>'
body='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UPS 短絡故障の洗い出し</title><style>body{font:15px/1.7 system-ui,sans-serif;color:#172838;background:#f5f7f9;margin:0}main{max-width:1500px;margin:auto;padding:28px}h1{font-size:28px}h2{margin-top:38px}p.note{background:#fff4dc;padding:16px;border-left:5px solid #b76c00}table{border-collapse:collapse;width:100%;background:white;font-size:13px}td,th{padding:10px;vertical-align:top;border:1px solid #d5dde4}th{background:#e7edf2;text-align:left;position:sticky;top:0}input{padding:10px;width:95%;max-width:650px;margin:12px 0}a{color:#07598c}small{color:#526473}</style><main>'''
body+='<h1>UPS：短絡した場合の発熱・発煙経路</h1><p>2026-10-22／実機への通電なし。回路・配線の変更なし。</p>'
body+='<p class="note">これは原因の確定結果ではなく、短絡箇所ごとの故障経路の一覧です。煙の位置と焼損部品は未確認です。「高」は故障が実在した場合の影響を表し、発生確率ではありません。</p>'
body+='<p>'+e(data['scope'])+'</p><p>'+e(data['assumptions'])+'</p>'
body+='<p><b>最優先：</b>中点−GND／中点−CAP、C9のCAP−GND、C10/C11/R7、R2、R10、R13、U1の2−3・14−15、U2の7−8。USB接続時だけの現象か、充電済み時にも成立するかを各行に記載しています。</p>'
body+='<p>指定L1は30A定格、正常なU1の電流設定はピーク約1〜4.92Aです。正常な電流切替やQ1 D-S短絡だけでは、L1巻線の発煙は説明しにくいです。フラックスや隣接部品の煙も候補です。</p>'
body+='<p class="note">'+e(data['measurement_limit'])+'</p>'
body+=f'<h2>部品・端子ごとの故障一覧：{len(cases)}件</h2><input id="filter" placeholder="部品名・ピン番号・現象で絞り込み（例：C11、Q2、過電圧）">'
body+=table(cases,[('id','ID'),('location','短絡箇所'),('level','影響'),('result','何が起こるか／発熱候補'),('phase','成立する時点'),('energy','電流・エネルギー源'),('limit','電流制限・保護との関係'),('note','条件・注意')])
body+='<h2>主要11ネットの全55組合せ</h2><p>電源・キャパ・中点・スイッチ・帰還・電流設定・ゲート制御の間を、異物やリード接触などで接続した場合。実際に基板上で近いとは限らず、故障があるという意味ではありません。</p>'
body+=table(network,[('id','ID'),('location','ネット間短絡'),('level','影響'),('result','結果'),('phase','成立条件'),('energy','エネルギー源'),('limit','保護との関係')])
body+='<h2>基板の近接パッド：異ネット44組</h2><p>同一銅層のパッド外接矩形の隙間が0.65mm以下の組。角丸・円形パッドでは実際の間隔より小さく表示され得ます。実際の短絡検出結果ではありません。裏面と表面のパッド同士は、重なって見えても短絡候補として数えていません。</p>'
body+=table(near,[('id','ID'),('a','端子A'),('a_net','ネットA'),('b','端子B'),('b_net','ネットB'),('bbox_gap_mm','外接矩形の隙間mm'),('layers','銅層'),('level','影響'),('result','短絡した場合')])
body+='<h2>資料・検証範囲</h2><p>保存済みPCBのDRC：違反0、未配線0。製造済み基板やはんだの状態を保証する結果ではありません。抵抗短絡と断線は別の故障であり、この表は短絡を中心にしています。</p><ul>'+''.join('<li><a href="'+e(url)+'">'+e(url)+'</a></li>' for url in data['sources'])+'</ul>'
body+='''<script>document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script></main></html>'''
(out/'short_fault_audit.html').write_text(body,encoding='utf-8')
assert sum(r['id'].startswith('C-') for r in cases)==32
print(json.dumps({'component_and_pin_cases':len(cases),'critical_net_pairs':len(network),'near_pad_pairs':len(near),'high_impact_cases':sum(r['level']=='高' for r in cases),'outputs':['short_fault_audit.html','short_fault_audit.json']},ensure_ascii=False))
