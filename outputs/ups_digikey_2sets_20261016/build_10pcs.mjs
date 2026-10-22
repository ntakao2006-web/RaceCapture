import fs from 'node:fs/promises';
import {SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const rows=JSON.parse(await fs.readFile(`${dir}/bom_data.json`,'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${dir}/UNO_Q_UPS_DigiKey_2sets_spares.xlsx`));
const s=wb.worksheets.getItem('BOM');
s.getRange('A2').values=[['UNO Q UPS｜DigiKey購入用BOM・小型部品は各10個']];
s.getRange('A3').values=[['2セット用 / 全27品種 / 必要80個＋余り140個＝注文220個']];
s.getRange('D4').values=[['抵抗・MLCC・MOSFETは各10個。IC・コネクタ・インダクタ・ポリマーCは必要数。']];
s.getRange('A6').values=[['スーパーキャパシタは12個で10個以上の単価を適用。全品の価格最適化・総額比較は未実施。']];
s.getRange('F8').values=[['余り']];
s.getRange('F9:F35').format.font.color='#202B33';
for(let i=0;i<rows.length;i++){
 const r=rows[i],n=i+9;
 const bulk=r.References.startsWith('R')||r.References.startsWith('Q')||r.Rating.includes('MLCC');
 s.getRange(`G${n}`).formulas=[[bulk?`=ROUNDUP(E${n}/10,0)*10`:`=E${n}`]];
 s.getRange(`F${n}`).formulas=[[`=G${n}-E${n}`]];
 r.Order_Quantity=bulk?Math.ceil(r.Required_2sets/10)*10:r.Required_2sets;
 r.Spare=r.Order_Quantity-r.Required_2sets;
}
wb.recalculate();
if(JSON.stringify(s.getRange('D36:G36').values[0])!==JSON.stringify([40,80,140,220]))throw Error('Total mismatch');
for(let i=0;i<rows.length;i++)if(s.getRange(`G${i+9}`).values[0][0]!==rows[i].Order_Quantity)throw Error('Row mismatch');
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},summary:'Formula check'})).ndjson);
for(const [name,range] of [['10pcs_top','A1:J22'],['10pcs_bottom','A23:J36']]){const img=await wb.render({sheetName:'BOM',range,scale:1,format:'png'});await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/UNO_Q_UPS_DigiKey_2sets_10pcs.xlsx`);
const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
const csv=data=>'\ufeff'+data.map(r=>r.map(cell).join(',')).join('\r\n')+'\r\n';
await fs.writeFile(`${dir}/DigiKey_upload_2sets_10pcs.csv`,csv([['DigiKey Part Number','Quantity','Customer Reference'],...rows.map(r=>[r.Supplier_Part_Number,r.Order_Quantity,r.References])]));
const keys=Object.keys(rows[0]);await fs.writeFile(`${dir}/BOM_full_2sets_10pcs.csv`,csv([keys,...rows.map(r=>keys.map(k=>r[k]))]));
console.log('Saved 27 lines / 220 parts / 140 spare.');
