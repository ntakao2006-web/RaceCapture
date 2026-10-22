import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const rows=JSON.parse(await fs.readFile(`${dir}/../ups_digikey_2sets_20261016/bom_data.json`,'utf8'));
const choices=[
 ['J1','103786','FH-1x10SG/RH','Chang Enn','10P ピンソケット',1,2,40,'2.54mm、メス、短足。3A/接点。高さ8.5mm。'],
 ['J2, J4','103785','FH-1x8SG/RH','Chang Enn','8P ピンソケット',1,4,30,'2.54mm、メス、短足。3A/接点。高さ8.5mm。'],
 ['J3','103784','FH-1x6SG/RH','Chang Enn','6P ピンソケット',1,2,25,'2.54mm、メス、短足。3A/接点。高さ8.5mm。'],
 ['Q1, Q2','104256','2N7002K','PANJIT','Nch MOSFET',40,1,200,'SOT-23、1=G/2=S/3=D。60V/300mA。制御用の置換品。'],
 ['C5','115331','C2012X7R1H105KT000N','TDK','1µF 50V X7R',10,1,100,'0805(2012)、±10%。在庫限り・通販残2パック（確認時）。']
];
const ak=choices.map(([refs,code,mpn,maker,label,pack,order,price,note])=>{
 const r=rows.find(r=>r.References===refs);if(!r)throw Error(refs);
 return {...r,Design_MPN:r.MPN,Design_Manufacturer:r.Manufacturer,MPN:mpn,Manufacturer:maker,Supplier:'秋月',Supplier_Part_Number:code,Label:label,Pack_Size:pack,Order_Units:order,Unit_Price_Tax_Included:price,Order_Quantity:pack*order,Spare:pack*order-r.Required_2sets,Notes:note,URL:`https://akizukidenshi.com/catalog/g/g${code}`};
});
const moved=new Set(ak.map(r=>r.References));
const dk=rows.filter(r=>!moved.has(r.References)).map(r=>{
 const bulk=r.References.startsWith('R')||r.Rating.includes('MLCC');
 const q=bulk?Math.ceil(r.Required_2sets/10)*10:r.Required_2sets;
 return {...r,Order_Quantity:q,Spare:q-r.Required_2sets};
});
const all=[...dk,...ak],refs=all.flatMap(r=>r.References.split(',').map(x=>x.trim()));
if(refs.length!==40||new Set(refs).size!==40)throw Error('Reference coverage');
const sum=(arr,k)=>arr.reduce((n,r)=>n+r[k],0);
if(sum(all,'Required_2sets')!==80||sum(dk,'Order_Quantity')!==192||sum(ak,'Order_Quantity')!==58)throw Error('Quantity totals');
const wb=Workbook.create(),s=wb.worksheets.add('DigiKey'),a=wb.worksheets.add('秋月');
function style(sh,last,widths){
 sh.showGridLines=false;sh.getRange(`A1:Q${last}`).format.font={name:'Arial',size:10,color:'#263747'};
 widths.forEach((w,i)=>sh.getRangeByIndexes(0,i,last,1).format.columnWidth=w);
 sh.getRange('A2').format.font={name:'Arial',size:17,bold:true,color:'#163D52'};
 sh.freezePanes.freezeRows(8);sh.freezePanes.freezeColumns(1);
}
function header(sh,r){sh.getRange(r).format={fill:'#163D52',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:34,verticalAlignment:'center'};}
style(s,35,[24,13,30,9,9,10,9,35,55,70,70,5,85]);
s.getRange('A2:H2').merge();s.getRange('A2').values=[['UNO Q UPS｜DigiKey用 BOM']];
s.getRange('A3:H3').merge();s.getRange('A3').values=[['2セット分・22品種 / 必要66個 / 注文192個 / 2026-10-16確認']];
s.getRange('A4:B4').values=[['製作セット数',2]];
s.getRange('C4:H4').merge();s.getRange('C4').values=[['抵抗・MLCCは各10個。その他は必要数。注文はF列。']];
s.getRange('A5:H5').merge();s.getRange('A5').values=[['IC・電源部品・E96抵抗・7FスーパーキャパシタはDigiKey。秋月分は別シート。']];
s.getRange('A6:H6').merge();s.getRange('A6').values=[['数量割引を使う購入数です。全品の価格・送料を含む総額は未集計。']];
const end=8+dk.length,total=end+1;
s.getRange(`A8:M${end}`).values=[['部品番号','値','購入メーカー型番','1セット','必要数','注文数','余り','DigiKey注文番号','メーカー / フットプリント','仕様','備考','','購入ページ'],...dk.map(r=>[r.References,r.Value,r.MPN,r.Quantity,null,r.Order_Quantity,null,r.Supplier_Part_Number,`${r.Manufacturer}\n${r.Footprint}`,r.Rating,r.Notes,'',r.URL])];
header(s,'A8:M8');
for(let i=0;i<dk.length;i++){const n=9+i;s.getRange(`E${n}`).formulas=[[`=D${n}*$B$4`]];s.getRange(`G${n}`).formulas=[[`=F${n}-E${n}`]];if(i%2)s.getRange(`A${n}:M${n}`).format.fill='#F0F5F7';}
s.getRange(`A9:M${end}`).format.wrapText=true;s.getRange(`A9:M${end}`).format.rowHeight=58;s.getRange(`A9:M${end}`).format.verticalAlignment='center';
s.getRange(`F9:F${total}`).format.fill='#DDF1E8';s.getRange(`D9:G${total}`).setNumberFormat('0');s.getRange(`A${total}`).values=[['合計']];for(const c of ['D','E','F','G'])s.getRange(`${c}${total}`).formulas=[[`=SUM(${c}9:${c}${end})`]];
s.getRange(`D9:G${total}`).format.horizontalAlignment='center';
s.getRange('B29:B30').values=[['電源IC'],['比較器']];
s.getRange(`A${total}:H${total}`).format.font.bold=true;
s.getRange('A33:H33').merge();s.getRange('A33').values=[['CAP：Eaton 7F ×12個。基板1枚は2直列×3並列＝公称10.5F。保持時間は実機未確認。']];
style(a,25,[19,29,30,10,10,11,12,10,10,13,13,13,55,32,5,85,85]);
a.getRange('A2:L2').merge();a.getRange('A2').values=[['UNO Q UPS｜秋月 買い物リスト']];
a.getRange('A3:L3').merge();a.getRange('A3').values=[['2セット分・5品種 / 必要14個 / 購入58個（8個＋2パック） / 税込550円・送料別']];
a.getRange('A4:B4').values=[['製作セット数',2]];
a.getRange('C4:L4').merge();a.getRange('C4').values=[['カートに入れる数はG列。F列は1個／1パックに含まれる部品数。']];
a.getRange('A5:L5').merge();a.getRange('A5').values=[['ピンソケットはメス・短足です。MOSFETは40個入り1袋、C5は10個入り1袋。']];
a.getRange('A6:L6').merge();a.getRange('A6').values=[['2026-10-16価格・在庫確認。C5は通販残2袋のため、売切時の代替を下に記載。']];
a.getRange('A8:Q13').values=[['部品番号','商品','購入メーカー型番','販売コード','必要数','入数\n個/単位','注文\n単位数','購入個数','余り','単位価格\n税込円','小計\n税込円','販売単位','置換仕様・備考','現行設計MPN','','購入ページ','寸法・ピン配置確認元'],...ak.map(r=>[r.References,r.Label,r.MPN,r.Supplier_Part_Number,null,r.Pack_Size,r.Order_Units,null,null,r.Unit_Price_Tax_Included,null,r.Pack_Size===1?'個':'パック',r.Notes,r.Design_MPN,'',r.URL,r.References.startsWith('J')?'https://akizukidenshi.com/goodsaffix/FH-1X00SGRH.pdf':r.References.startsWith('Q')?'https://akizukidenshi.com/goodsaffix/2N7002K.pdf':r.URL])];
header(a,'A8:Q8');
for(let i=0;i<ak.length;i++){const n=9+i;a.getRange(`E${n}`).formulas=[[`=${ak[i].Quantity}*$B$4`]];a.getRange(`H${n}`).formulas=[[`=F${n}*G${n}`]];a.getRange(`I${n}`).formulas=[[`=H${n}-E${n}`]];a.getRange(`K${n}`).formulas=[[`=G${n}*J${n}`]];if(i%2)a.getRange(`A${n}:Q${n}`).format.fill='#F0F5F7';}
a.getRange('A9:Q13').format.wrapText=true;a.getRange('A9:Q13').format.rowHeight=82;a.getRange('A9:Q13').format.verticalAlignment='center';
a.getRange('G9:G13').format.fill='#DDF1E8';a.getRange('E9:K14').setNumberFormat('0');a.getRange('J9:K14').setNumberFormat('¥#,##0');
a.getRange('A14').values=[['合計']];for(const c of ['E','H','I','K'])a.getRange(`${c}14`).formulas=[[`=SUM(${c}9:${c}13)`]];a.getRange('A14:L14').format.font.bold=true;
a.getRange('E9:I14').format.horizontalAlignment='center';a.getRange('J9:K14').format.horizontalAlignment='center';
const notes=[
 '購入代替品はN列の現行設計MPNと区別して記載。今回の分割では回路図・PCBファイルを変更していません。',
 'ソケット：P2.54mm、既存穴1.0mmに対し推奨穴1.02±0.05mm。最大外形は既存コートヤード内。',
 '接点定格は旧Samtec 4.7Aから3Aへ。現在の制御用MOSFETは同じピン配置・SOT-23で置換。実機動作は未確認。',
 'C5売切時：DigiKey 399-C0805C105K5RACTUCT-ND / KEMET C0805C105K5RACTU を10個追加。重複購入不要。',
 'スーパーキャパシタはDigiKeyのEaton 7Fを継続。小型抵抗・他のMLCCは値／サイズ／特性を維持して各10個。',
 'この表は基板実装部品40点×2セットを対象。基板製造、UNO Q本体、配線材・取付ねじ等は含みません。'
];
notes.forEach((text,i)=>{const n=17+i;a.getRange(`A${n}:L${n}`).merge();a.getRange(`A${n}`).values=[[text]];a.getRange(`A${n}:L${n}`).format.rowHeight=30;a.getRange(`A${n}:L${n}`).format.wrapText=true;});
wb.recalculate();
if(JSON.stringify(s.getRange(`D${total}:G${total}`).values[0])!==JSON.stringify([33,66,192,126]))throw Error('DK formulas');
for(const [cell,val] of [['E14',14],['H14',58],['I14',44],['K14',550]])if(a.getRange(cell).values[0][0]!==val)throw Error(cell);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},summary:'Error scan'})).ndjson);
for(const [sheet,range,name] of [['DigiKey','A1:H20','digikey_top'],['DigiKey','A21:H33','digikey_bottom'],['秋月','A1:L22','akizuki'],['秋月','M8:N13','substitutions']]){const img=await wb.render({sheetName:sheet,range,scale:1,format:'png'});await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/UNO_Q_UPS_2sets_DigiKey_Akizuki.xlsx`);
const csv=data=>'\ufeff'+data.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
await fs.writeFile(`${dir}/DigiKey_upload_2sets.csv`,csv([['DigiKey Part Number','Quantity','Customer Reference'],...dk.map(r=>[r.Supplier_Part_Number,r.Order_Quantity,r.References])]));
await fs.writeFile(`${dir}/Akizuki_shopping_2sets.csv`,csv([['販売コード','商品','購入型番','注文数量','注文単位','入数','購入個数','2セット必要数','余り','税込単価円','税込小計円','部品番号','URL','備考'],...ak.map(r=>[r.Supplier_Part_Number,r.Label,r.MPN,r.Order_Units,r.Pack_Size===1?'個':'パック',r.Pack_Size,r.Order_Quantity,r.Required_2sets,r.Spare,r.Unit_Price_Tax_Included,r.Unit_Price_Tax_Included*r.Order_Units,r.References,r.URL,r.Notes])]));
await fs.writeFile(`${dir}/selection.json`,JSON.stringify({date:'2026-10-16',DigiKey:dk,Akizuki:ak,totals:{required:80,order:250,spare:170,akizuki_yen_tax_included:550}},null,2));
console.log('Saved: DK22 lines/192 pcs; Akizuki5 lines/58 pcs/550 JPY; required80/order250/spare170.');
