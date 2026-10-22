import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=fileURLToPath(new URL('.',import.meta.url));
const dk=JSON.parse(await fs.readFile(`${dir}/dk_priced.json`,'utf8'));
const base=JSON.parse(await fs.readFile(`${dir}/../ups_digikey_2sets_20261016/bom_data.json`,'utf8'));
const choices=[
 ['J1','103786','FH-1x10SG/RH','10P メスピンソケット',1,1,40,85,'1F 13番 下段引出','2.54mm・高さ8.5mm・接点3A。旧Samtecは4.7A。'],
 ['J2, J4','103785','FH-1x8SG/RH','8P メスピンソケット',1,2,30,35,'1F 13番 下段引出','2.54mm・高さ8.5mm・接点3A。旧Samtecは4.7A。'],
 ['J3','103784','FH-1x6SG/RH','6P メスピンソケット',1,1,25,53,'1F 13番 下段引出','2.54mm・高さ8.5mm・接点3A。旧Samtecは4.7A。'],
 ['Q1, Q2','104256','2N7002K','Nch MOSFET',40,1,200,3,'1F 36番 2段目','PANJIT製、60V/300mA、SOT-23、1=G/2=S/3=D。制御用の代替。'],
 ['C11','117142','GRM21BR71H474KA88L','0.47µF 50V X7R',20,1,170,3,'1F 35番 4段目','Murata製、0805 (2012)、±10%。元品と同じ容量・耐圧・温度特性。'],
 ['C15','114559','GRM188R72A104KA35D','0.1µF 100V X7R',20,1,150,5,'1F 35番 3段目','Murata製、0603 (1608)、±10%。元の50V品から耐圧を上げた代替。'],
 ['R4, R6','111796','RG2012N-102-B-T5','1kΩ 0.1% 1/8W',5,1,100,24,'1F 15番 下段引出','Susumu製、0805 (2012)。元の1%品より高精度、電力は同じ。']
];
const ak=choices.map(([refs,code,mpn,label,pack,order,price,stock,shelf,note])=>{
 const r=base.find(x=>x.References===refs); if(!r)throw Error(refs);
 const {Required_2sets,...old}=r;
 return {...old,Design_MPN:r.MPN,MPN:mpn,Supplier:'秋月店頭',Supplier_Part_Number:code,Label:label,Required:r.Quantity,Pack_Size:pack,Order_Units:order,Order_Quantity:pack*order,Spare:pack*order-r.Quantity,Unit_Price:price,Line_Total:order*price,Stock:stock,Stock_Unit:pack===1?'個':'袋',Shelf:shelf,Stock_Checked:'2026-10-17',Notes:note,URL:`https://akizukidenshi.com/catalog/g/g${code}/`};
});
ak.forEach(r=>{r.Manufacturer=r.References.startsWith('J')?'Chang Enn':r.References.startsWith('Q')?'PANJIT':r.References.startsWith('C')?'Murata Electronics':'Susumu';r.Stock_Source=r.URL;r.Rating=r.Notes;});
const sum=(rs,k)=>rs.reduce((s,r)=>s+r[k],0), total=sum(dk,'Line_Total'), akTotal=sum(ak,'Line_Total');
if(total!==6014||akTotal!==745)throw Error('Price');
const wb=Workbook.create(),s=wb.worksheets.add('DigiKey'),a=wb.worksheets.add('秋月店頭');
function init(sh,widths,last){sh.showGridLines=false;sh.getRange(`A1:Q${last}`).format.font={name:'Yu Gothic',size:10,color:'#263747'};widths.forEach((w,i)=>sh.getRangeByIndexes(0,i,last,1).format.columnWidth=w);sh.freezePanes.freezeRows(9);sh.freezePanes.freezeColumns(1);}
function title(sh,text,last){sh.getRange(`A2:${last}2`).merge();sh.getRange('A2').values=[[text]];sh.getRange('A2').format.font={name:'Yu Gothic',size:18,bold:true,color:'#163D52'};sh.getRange('A2').format.rowHeight=32;}
function merged(sh,row,end,text){sh.getRange(`A${row}:${end}${row}`).merge();sh.getRange(`A${row}`).values=[[text]];sh.getRange(`A${row}:${end}${row}`).format={wrapText:true,rowHeight:28,verticalAlignment:'center'};}
function hdr(sh,r){sh.getRange(r).format={fill:'#163D52',font:{name:'Yu Gothic',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:38,verticalAlignment:'center'};}
function body(sh,lastCol,end,height){sh.getRange(`A10:${lastCol}${end}`).format={wrapText:true,rowHeight:height,verticalAlignment:'center'};for(let n=10;n<=end;n++)if(n%2)sh.getRange(`A${n}:${lastCol}${n}`).format.fill='#F0F5F7';}
init(s,[24,15,31,9,9,9,12,13,36,5,35,49,67,75,15,15,85],40);
title(s,'UNO Q UPS｜1セット用 DigiKey BOM','I');
merged(s,3,'I','秋月は秋葉原店頭で購入。DigiKeyは送料無料ラインの税抜6,000円付近に調整。');
s.getRange('A4:B4').values=[['商品小計（税抜）',null]];s.getRange('B4').formulas=[['=SUM(H10:H29)']];
s.getRange('C4:D4').values=[['税込概算',null]];s.getRange('D4').formulas=[['=ROUND(B4*(1+$F$4),0)']];
s.getRange('E4:F4').values=[['消費税率',0.1]];s.getRange('F4').setNumberFormat('0%');
s.getRange('G4:H4').values=[['秋月込概算',null]];s.getRange('H4').formulas=[["=D4+'秋月店頭'!H4"]];
for(const c of ['B4','D4','H4']){s.getRange(c).setNumberFormat('¥#,##0');s.getRange(c).format.font.bold=true;s.getRange(c).format.fill='#DDF1E8';}
merged(s,5,'I','2026-10-17確認｜20品種・必要30個・注文115個。小さな抵抗・コンデンサは予備付き。');
merged(s,6,'I','注文数はE列。カットテープ（CT）を指定し、追加料金のあるDigi-Reelは選択しません。');
merged(s,7,'I','価格・在庫は確認時の表示。税込は10%の概算、注文画面の最終金額を優先してください。');
s.getRange('A9:Q29').values=[['部品番号','値','購入メーカー型番','必要数','注文数','予備','単価\n税抜円','小計\n税抜円','DigiKey注文番号','','現行設計MPN','フットプリント','仕様','購入代替・備考','確認在庫\n個','確認日','購入ページ / 価格出典'],...dk.map(r=>[r.References,r.Value.startsWith('MAX')?'電源IC':r.Value.startsWith('LTC')?'比較器':r.Value,r.MPN,r.Required,r.Order_Quantity,null,r.Unit_Price,null,r.Supplier_Part_Number,'',r.Design_MPN,r.Footprint,r.Rating,r.Notes,r.Stock,r.Stock_Checked,r.URL])];
hdr(s,'A9:Q9');body(s,'Q',29,66);
dk.forEach((r,i)=>{const n=i+10;s.getRange(`F${n}`).formulas=[[`=E${n}-D${n}`]];s.getRange(`H${n}`).formulas=[[`=E${n}*G${n}`]];});
s.getRange('E10:E29').format.fill='#DDF1E8';s.getRange('D10:F30').setNumberFormat('0');s.getRange('G10:H30').setNumberFormat('¥#,##0.##');s.getRange('D10:H30').format.horizontalAlignment='center';
s.getRange('A30').values=[['合計']];for(const c of ['D','E','F','H'])s.getRange(`${c}30`).formulas=[[`=SUM(${c}10:${c}29)`]];s.getRange('A30:I30').format.font.bold=true;
const notes=[
 '抵抗は原則10個。予算調整のためR1は2個、R14は3個。C5・C10・C16は各2個（各1個予備）。',
 'C5は秋月115331の秋葉原在庫0のため村田製を採用。C10は安価なTDK製。R10/R13は在庫のある包装違い。',
 '7Fスーパーキャパシタは6個。2直列×3並列で公称10.5F。保持時間・今回の代替品の実機動作は未確認。',
 '代替品は現行設計MPNと分けて記載。今回の購入リスト作成では回路図・PCBは変更していません。',
 '対象は基板1枚の実装部品40点。基板製造費、UNO Q本体、配線材、取付ねじ、工具は含みません。',
 '送料無料条件：DigiKey出荷の商品小計6,000円以上。価格変動で下回る場合は注文前に再調整してください。'
];notes.forEach((v,i)=>merged(s,32+i,'I',v));
s.getRange('K37:Q37').merge();s.getRange('K37').values=[['送料出典：https://www.digikey.jp/ja/help-support/delivery-information/delivery-time-and-cost']];
init(a,[20,27,12,12,11,10,12,13,10,14,30,5,33,35,51,68,85],29);
title(a,'UNO Q UPS｜秋葉原店頭 買い物リスト','K');
merged(a,3,'K','7種類・必要10個・購入89個。販売コードと購入単位をそのまま店頭で確認できます。');
a.getRange('A4:C4').merge();a.getRange('A4').values=[['秋月 合計（税込）']];a.getRange('H4').formulas=[['=SUM(H10:H16)']];a.getRange('H4').setNumberFormat('¥#,##0');a.getRange('H4').format={fill:'#DDF1E8',font:{bold:true,size:16}};
merged(a,5,'K','2026-10-17の秋葉原店表示在庫を確認。通販在庫ではなく、店頭在庫と売り場を記載。');
merged(a,6,'K','購入する数はD列。ソケットは計4個、残り4商品は各1袋です。');
merged(a,7,'K','在庫は変動します。2N7002Kと0.47µFは確認時に各3袋。');
a.getRange('A9:Q16').values=[['部品番号','商品','販売コード','買う数\n個 / 袋','入数\n個/単位','必要数','予備\n個','小計\n税込円','単価\n税込円','秋葉原在庫\n販売単位','売り場','','購入メーカー型番','現行設計MPN','フットプリント','仕様・代替内容','商品ページ / 価格・在庫出典'],...ak.map(r=>[r.References,r.Label,r.Supplier_Part_Number,`${r.Order_Units}${r.Stock_Unit}`,r.Pack_Size,r.Required,null,null,r.Unit_Price,`${r.Stock}${r.Stock_Unit}`,r.Shelf,'',r.MPN,r.Design_MPN,r.Footprint,r.Notes,r.URL])];
hdr(a,'A9:Q9');body(a,'Q',16,72);
ak.forEach((r,i)=>{const n=10+i;a.getRange(`G${n}`).formulas=[[`=E${n}*${r.Order_Units}-F${n}`]];a.getRange(`H${n}`).formulas=[[`=I${n}*${r.Order_Units}`]];});
a.getRange('D10:D16').format.fill='#DDF1E8';a.getRange('D10:J17').format.horizontalAlignment='center';a.getRange('H10:I17').setNumberFormat('¥#,##0');
a.getRange('A17').values=[['合計']];for(const c of ['F','G','H'])a.getRange(`${c}17`).formulas=[[`=SUM(${c}10:${c}16)`]];a.getRange('A17:K17').format.font.bold=true;
[
 'ピンソケットはメス・短足・2.54mm。10Pを1個、8Pを2個、6Pを1個。',
 'C11/C15は元と同じ実装サイズ・X7R。C15の耐圧は50Vから100V。R4/R6は同じ1kΩ・0805・1/8W。',
 '2N7002KはPANJIT製。SOT-23、1=G/2=S/3=Dが既存フットプリントと対応します。',
 'ソケット接点定格3A（元品4.7A）。推奨穴1.02±0.05mmに対し基板穴1.0mm、高さ8.5mm。',
 '店頭在庫のない1µF（秋月115331）はこのリストから除外し、DigiKeyのC5に含めました。',
 '袋単位のためMOSFET38個、C11/C15各19個、1kΩ抵抗3個が予備として残ります。'
].forEach((v,i)=>merged(a,19+i,'K',v));
s.getRange('A4:I4').format.rowHeight=32;
a.getRange('A4:K4').format.rowHeight=32;
wb.recalculate();
for(const [sh,cell,n] of [[s,'B4',6014],[s,'D4',6615],[s,'H4',7360],[s,'D30',30],[s,'E30',115],[s,'F30',85],[a,'H4',745],[a,'F17',10],[a,'G17',79]])if(sh.getRange(cell).values[0][0]!==n)throw Error(`Bad ${cell}`);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},summary:'Error scan'})).ndjson);
await(await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/UNO_Q_UPS_1set_6000yen.xlsx`);
for(const [sheet,range,name] of [['DigiKey','A1:I19','digikey_top'],['DigiKey','A20:I37','digikey_bottom'],['秋月店頭','A1:K24','akizuki'],['DigiKey','K9:N19','dk_substitutions'],['秋月店頭','M9:P16','ak_substitutions']]){const img=await wb.render({sheetName:sheet,range,scale:1,format:'png'});await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await img.arrayBuffer()));}
const csv=rs=>'\ufeff'+rs.map(r=>r.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
await fs.writeFile(`${dir}/DigiKey_upload_1set.csv`,csv([['DigiKey Part Number','Quantity','Customer Reference'],...dk.map(r=>[r.Supplier_Part_Number,r.Order_Quantity,r.References])]));
await fs.writeFile(`${dir}/Akizuki_Akihabara_1set.csv`,csv([['販売コード','商品','購入型番','購入数量','購入単位','入数','購入個数','1セット必要数','予備','税込単価円','税込小計円','部品番号','秋葉原在庫','売り場','確認日','URL','備考'],...ak.map(r=>[r.Supplier_Part_Number,r.Label,r.MPN,r.Order_Units,r.Stock_Unit,r.Pack_Size,r.Order_Quantity,r.Required,r.Spare,r.Unit_Price,r.Line_Total,r.References,r.Stock,r.Shelf,r.Stock_Checked,r.URL,r.Notes])]));
await fs.writeFile(`${dir}/selection.json`,JSON.stringify({date:'2026-10-17',DigiKey:dk,Akizuki:ak,totals:{required:40,order:204,spare:164,digikey_ex_tax:6014,digikey_incl_tax_estimate:6615,akizuki_incl_tax:745,combined_estimate:7360}},null,2));
console.log('SAVED: DigiKey 6014 ex tax, Akizuki 745 incl tax.');
