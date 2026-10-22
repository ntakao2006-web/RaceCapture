import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const rows=JSON.parse(await fs.readFile(`${dir}/bom_data.json`,'utf8'));
const wb=Workbook.create();const s=wb.worksheets.add('BOM');s.showGridLines=false;
s.getRange('A2').values=[['UNO Q UPS 部品表']];
s.getRange('A3').values=[['1基板分・予備なし / 2026-10-16 / 40個・27品種']];
s.getRange('A4').values=[['DigiKey 34個、秋月 6個。数量は必要実装数。在庫は参照ページの表示値で、予約ではありません。']];
s.getRange('A5').values=[['試作設定：SYS 約4.19V、CAP 約3.95V。UNO Qの5V接続先・瞬停保持は実機未検証。']];
const head=['部品番号','数量','値','メーカー型番','パッケージ','購入先','注文番号','表示在庫','確認日','定格・仕様','フットプリント','購入ページ','在庫確認元','備考'];
const shortfp=fp=>{
 const f=fp.split(':')[1];
 if(f.startsWith('R_')||f.startsWith('C_'))return f.replace(/^[RC]_/,'').replace('_2012Metric',' / 2012').replace('_1608Metric',' / 1608').replace('_3216Metric',' / 3216');
 if(f.startsWith('HP-'))return 'D10 × L25 mm / P5 mm 横置き';
 if(f.startsWith('PinSocket'))return f.match(/1x\d+/)[0]+' / P2.54 mm ソケット';
 if(f.startsWith('TQFN'))return 'TQFN-16 + EP / 3 × 3 mm';
 if(f.startsWith('MSOP'))return 'MSOP-8 / 3 × 3 mm';
 return f;
};
const data=rows.map(r=>[r.References,r.Quantity,r.Value,r.MPN,shortfp(r.Footprint),r.Supplier,r.Supplier_Part_Number,r.Stock??'未確認',r.Stock_Checked==='未確認'?'未確認':new Date(r.Stock_Checked+'T00:00:00Z'),r.Rating,r.Footprint,r.URL,r.Stock_Source,r.Notes]);
s.getRange('A7:N34').values=[head,...data];
s.getRange('A35').values=[['合計']];s.getRange('B35').formulas=[['=SUM(B8:B34)']];
s.getRange('A2:N35').format.font={name:'Arial',size:10,color:'#202B33'};
s.getRange('A2').format.font={name:'Arial',size:15,bold:true};
s.getRange('A3:A5').format.font={name:'Arial',size:10,color:'#52616B'};
s.getRange('A7:N7').format={fill:'#243D53',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:28,horizontalAlignment:'center',verticalAlignment:'center'};
s.getRange('A8:N34').format.verticalAlignment='center';
s.getRange('A8:N34').format.wrapText=true;
s.getRange('A8:N34').format.rowHeight=44;
const widths=[24,7,12,27,29,11,30,13,14,65,65,85,85,55];
for(let i=0;i<widths.length;i++)s.getRangeByIndexes(6,i,29,1).format.columnWidth=widths[i];
s.getRange('B8:B35').setNumberFormat('0');s.getRange('H8:H34').setNumberFormat('#,##0');
s.getRange('I8:I34').setNumberFormat('yyyy-mm-dd');
s.getRange('B8:B35').format.horizontalAlignment='right';s.getRange('H8:H34').format.horizontalAlignment='right';
for(let i=0;i<rows.length;i++)if(i%2===1)s.getRange(`A${i+8}:N${i+8}`).format.fill='#F2F5F7';
s.getRange('A35:N35').format.borders={top:{style:'thin',color:'#667788'}};
s.getRange('A35:B35').format.font={name:'Arial',size:10,bold:true};
s.freezePanes.freezeRows(7);s.freezePanes.freezeColumns(2);
wb.recalculate();
if(s.getRange('B35').values[0][0]!==40)throw Error('BOM total mismatch');
console.log((await wb.inspect({kind:'table',range:'BOM!A30:H35',include:'values,formulas',tableMaxRows:6,tableMaxCols:8,maxChars:1500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},summary:'Error scan'})).ndjson);
for(const [name,range] of [['bom_top','A1:I20'],['bom_bottom','A21:I35'],['details_top','J7:N20'],['details_bottom','J21:N34']]){
 const img=await wb.render({sheetName:'BOM',range,scale:1,format:'png'});
 await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await img.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/UNO_Q_UPS_BOM.xlsx`);
try{const sharp=(await import('sharp')).default;await sharp(`${dir}/schematic_svg/logger_v2_ups.svg`,{density:180}).png().toFile(`${dir}/schematic.png`);}catch(e){console.log('SVG preview:',e.message);}
console.log('Saved UNO_Q_UPS_BOM.xlsx');
