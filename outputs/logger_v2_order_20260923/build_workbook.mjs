import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
const d=JSON.parse(await fs.readFile(path.join(dir,'bom_data.json'),'utf8'));
const ready=d.rows.filter(r=>r.supplier==='DigiKey'),hold=d.rows.filter(r=>r.supplier!=='DigiKey');
const wb=Workbook.create(),s=wb.worksheets.add('発注BOM'),h=wb.worksheets.add('代替・手持ち・DNP'),n=wb.worksheets.add('選定根拠');
function base(sh,cols,last){sh.showGridLines=false;sh.getRange(`A1:${cols.at(-1)[0]}${last}`).format.font={name:'Yu Gothic',size:10,color:'#182C3D'};sh.getRange(`A1:${cols.at(-1)[0]}${last}`).format.verticalAlignment='center';sh.getRange(`A1:${cols.at(-1)[0]}${last}`).format.wrapText=true;for(const [col,w] of cols)sh.getRange(`${col}1:${col}${last}`).format.columnWidthPx=w;sh.freezePanes.freezeRows(6);}
function band(sh,range,text){sh.mergeCells(range);const r=sh.getRange(range);r.values=[[text]];r.format.fill='#173B50';r.format.font={name:'Yu Gothic',size:17,bold:true,color:'#FFFFFF'};r.format.rowHeightPx=42;}
function note(sh,range,text,color='#EAF3F5'){sh.mergeCells(range);sh.getRange(range).values=[[text]];sh.getRange(range).format.fill=color;sh.getRange(range).format.rowHeightPx=35;}
function head(sh,range,values){sh.getRange(range).values=[values];sh.getRange(range).format.fill='#24566C';sh.getRange(range).format.font={name:'Yu Gothic',bold:true,color:'#FFFFFF',size:10};sh.getRange(range).format.rowHeightPx=32;}
const last=6+ready.length;
base(s,[['A',200],['B',215],['C',150],['D',235],['E',265],['F',60],['G',60],['H',65]],last+4);
band(s,'A1:H1','logger_v2  |  DigiKey 発注BOM  |  基板1台分');
note(s,'A2:H2','2026-09-23調査 ／ 31品目・実装79個＋予備110個＝189個。D2・D3も同じ基板に実装可能な機能代替品を割り当て、全品DigiKeyに統一。');
note(s,'A3:H3','手持ち：SD、IMU、GNSS、SMA、ピンヘッダ、4.7kΩ・10kΩ抵抗。Molexは基板側を合計2個だけ。');
note(s,'A4:H4','DigiKey直販の少量梱包を選択。在庫は取得ページの表示であり、確保済みではありません。注文時に在庫・単価を確認。');
head(s,'A6:H6',['実装位置','品目・定格','サイズ','メーカー品番','DigiKey品番','実装数','予備数','発注数']);
s.getRange(`D7:E${last}`).setNumberFormat('@');
s.getRange(`A7:H${last}`).values=ready.map(r=>[r.refs.join(', '),r.description,r.package,r.mpn.startsWith('0')?"'"+r.mpn:r.mpn,r.dk,r.needed,r.spare,null]);
s.getRange(`H7:H${last}`).formulas=ready.map((r,i)=>[`=F${7+i}+G${7+i}`]);
s.getRange(`A7:H${last}`).format.rowHeightPx=61;
s.getRange(`F7:H${last}`).format.horizontalAlignment='right';s.getRange(`F7:H${last}`).setNumberFormat('0');s.getRange(`G7:G${last}`).format.font.color='#2166A5';
for(let i=7;i<=last;i++)if(i%2)s.getRange(`A${i}:H${i}`).format.fill='#F1F6F8';
s.tables.add(`A6:H${last}`,true,'DigiKeyOrder');
s.getRange(`A${last+1}:E${last+1}`).merge();s.getRange(`A${last+1}`).values=[['合計（保留品を除く）']];
s.getRange(`F${last+1}:H${last+1}`).formulas=[[`=SUM(F7:F${last})`,`=SUM(G7:G${last})`,`=SUM(H7:H${last})`]];
s.getRange(`A${last+1}:H${last+1}`).format.fill='#D7E9EC';s.getRange(`A${last+1}:H${last+1}`).format.font.bold=true;
note(s,`A${last+3}:H${last+3}`,'予備数は変更可能です。CSVは作成時点の固定値なので、Excelで数量を変えた場合はCSV側も変更してください。');
base(h,[['A',100],['B',230],['C',60],['D',280],['E',520]],35);
band(h,'A1:E1','保護ダイオードの代替と購入対象外');
note(h,'A2:E2','98部品 ＝ DigiKey79個 ＋ 手持ち16個 ＋ 未実装3個。全リファレンスを重複なく照合。別調達・発注保留はありません。');
note(h,'A3:E3','D2・D3は機能代替として採用。全定格が同一の品ではありません。下記の差分を明記し、発注BOMに各3個を含めています。','#FFF0D7');
head(h,'A6:E6',['位置','必要部品','実装数','購入先・品番','適合根拠・仕様差分']);
h.getRange('A7:E8').values=d.rows.filter(r=>['D2','D3'].includes(r.refs[0])).map(r=>[r.refs.join(', '),r.description,r.needed,r.supplier+' / '+r.mpn+'\n'+r.dk,r.note]);h.getRange('A7:E8').format.rowHeightPx=175;h.getRange('A7:E8').format.fill='#FFF0D7';
note(h,'A10:E10','購入不要 ／ 手持ち品は基板上の対応部品を示しています。実物の型番・サイズは未確認です。');
head(h,'A12:E12',['位置','値・部品','数量','扱い','サイズ・注意']);
h.getRange(`A13:E${12+d.excluded.length}`).values=d.excluded.map(r=>[r.ref,r.value,1,r.reason,r.footprint+(r.note?'\n'+r.note:'')]);
h.getRange(`A13:E${12+d.excluded.length}`).format.rowHeightPx=43;
for(let i=13;i<=12+d.excluded.length;i++)if(i%2)h.getRange(`A${i}:E${i}`).format.fill='#F1F6F8';
base(n,[['A',165],['B',255],['C',360],['D',550],['E',410]],d.rows.length+9);
band(n,'A1:E1','選定根拠・購入リンク');
note(n,'A2:E2','基板に載るサイズとピン配置を優先。現行回路図とPCBの98部品について、値・フットプリントの一致を照合。');
note(n,'A3:E3','旧BOMは集計に使用せず、現行ValueとDNPを採用。抵抗やC20などで古いMPN/Specificationと不一致があるため、元品番も併記。');
note(n,'A4:E4','在庫表示にはキャッシュや地域ページ差があります。価格・納期の確約は含みません。実機動作・製造適合試験は未実施。');
head(n,'A6:E6',['位置','選定メーカー品番','基板フットプリント／元MPN','選定理由・注意','販売店製品ページ']);
n.getRange(`B7:B${6+d.rows.length}`).setNumberFormat('@');
n.getRange(`A7:E${6+d.rows.length}`).values=d.rows.map(r=>[r.refs.join(', '),r.mpn.startsWith('0')?"'"+r.mpn:r.mpn,r.footprint+'\n元MPN: '+r.original,r.note,r.url]);
n.getRange(`A7:E${6+d.rows.length}`).format.rowHeightPx=110;
for(let i=7;i<=6+d.rows.length;i++)if(i%2)n.getRange(`A${i}:E${i}`).format.fill='#F1F6F8';
n.getRange(`A${5+d.rows.length}:E${6+d.rows.length}`).format.fill='#FFF0D7';
n.getRange(`A${5+d.rows.length}:E${6+d.rows.length}`).format.rowHeightPx=190;
const docs=[['D1/D4','https://www.st.com/resource/en/datasheet/esdcan24-2bly.pdf'],['U9/U10','https://www.st.com/resource/en/datasheet/usblc6-4sc6y.pdf'],['Y1','https://abracon.com/Support/PackageDrawing/Resonators/ABM8.PDF'],['Q1','https://www.onsemi.com/pdf/datasheet/2n7002e-d.pdf'],['LED','https://optoelectronics.liteon.com/upload/download/DS22-2000-073/LTST-C170KGKT.PDF']];
docs.push(['D2','https://www.littelfuse.com/assetdocs/littelfuse_tvs_diode_array_aq3045_datasheet.pdf?assetguid=42516203-4330-4a77-a157-9b013cf634c9'],['D3','https://www.mccsemi.com/pdf/Products/CSPSBHC4V5LB(CSP1006-2).pdf']);
const csv=matrix=>'\uFEFF'+matrix.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
await fs.writeFile(path.join(dir,'DigiKey_upload.csv'),csv([['DigiKey Part Number','Quantity','Customer Reference'],...ready.map(r=>[r.dk,r.quantity,r.refs.join(' ')])]),'utf8');
await fs.writeFile(path.join(dir,'BOM_full.csv'),csv([['状態','実装位置','品目','サイズ','メーカー品番','販売店','販売店品番','必要数','予備候補数','購入推奨数','選定根拠','製品URL'],...d.rows.map(r=>[r.status,r.refs.join(' '),r.description,r.package,r.mpn,r.supplier,r.dk,r.needed,r.spare,r.status.startsWith('保留')?0:r.quantity,r.note,r.url])]),'utf8');
wb.recalculate();
const totals=s.getRange(`F${last+1}:H${last+1}`).values[0];
if(totals[0]!==79 || totals[2]!==ready.reduce((a,r)=>a+r.quantity,0))throw new Error('Quantity reconciliation failed '+JSON.stringify(totals));
for(const sh of [s,h,n])for(const row of sh.getUsedRange().values)for(const v of row)if(typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|N\/A|NAME\?|NUM!)/.test(v))throw new Error(v);
await fs.writeFile(path.join(dir,'verification.json'),JSON.stringify({counts:d.counts,totals,readyLines:ready.length,holdLines:hold.length,sourceHashes:d.hashes,manufacturerSources:docs},null,2));
for(const [sh,range,name] of [[s,'A1:H19','order_top'],[s,`A20:H${last+3}`,'order_bottom'],[h,'A1:E20','excluded_top'],[h,`A21:E${12+d.excluded.length}`,'excluded_bottom'],[n,'A1:E16','basis_top'],[n,'A17:E27','basis_middle'],[n,`A28:E${6+d.rows.length}`,'basis_bottom']]){
 const pic=await wb.render({sheetName:sh.name,range,scale:1,format:'png'});await fs.writeFile(path.join(dir,name+'.png'),new Uint8Array(await pic.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(dir,'logger_v2_DigiKey_BOM.xlsx'));
console.log(JSON.stringify({readyLines:ready.length,holdLines:hold.length,totals}));
