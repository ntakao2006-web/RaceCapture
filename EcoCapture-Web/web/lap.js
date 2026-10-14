'use strict';
// Control / start / goal line settings (lap.py). Dashboard values arrive with the telemetry frame.
let lapLoaded=false;
const lapLines=()=>[...document.querySelectorAll('.lap-line')];
const lapField=(fieldset,name)=>fieldset.querySelector(`[data-lap-${name}]`);
function lapGate(line,target){
  if(target==='control')return line.enabled?{lat:line.lat,lon:line.lon,bearing:line.bearing,width_m:line.width_m}:null;
  return line[target];
}
function lapShow(data){
  const l=data.line;
  for(const f of lapLines()){
    const g=lapGate(l,f.dataset.target);
    lapField(f,'coord').value=g?`${g.lat.toFixed(6)}, ${g.lon.toFixed(6)}`:'';
    lapField(f,'width').value=g?g.width_m:30;
    lapField(f,'bearing').value=g&&g.bearing!==null?Math.round(g.bearing):'';
    lapField(f,'state').textContent=!g?'（未登録）':g.bearing===null?'（登録済み・向きは最初の通過で決定）':`（登録済み・向き ${Math.round(g.bearing)}°）`;
  }
  $('lap-min').value=l.min_lap_s;$('lap-total').value=l.total_laps??'';
  $('lap-line-state').textContent=!l.enabled?'未設定':[l.start&&'スタート',`コントロール`,l.goal&&'ゴール'].filter(Boolean).join('・')+(l.total_laps?`／${l.total_laps}周`:'');
  if(data.error)$('lap-result').textContent=data.error;
  lapLoaded=true;
}
function lapRead(fieldset){
  const text=lapField(fieldset,'coord').value.trim();
  if(!text)return null;
  const parts=text.split(/[,\s]+/).filter(Boolean).map(Number);
  if(parts.length!==2||!parts.every(Number.isFinite))throw new Error('座標は「緯度, 経度」の形で入れてください（例: 36.53212, 140.22755）。');
  const bearing=lapField(fieldset,'bearing').value;
  return {lat:parts[0],lon:parts[1],width_m:Number(lapField(fieldset,'width').value),bearing:bearing===''?null:Number(bearing)%360};
}
async function lapCall(path,body,done){
  const data=await api(path,'POST',body);lapShow(data);$('lap-result').textContent=done;
}
for(const f of lapLines()){
  f.querySelector('[data-lap-here]').onclick=()=>action(()=>lapCall('/api/lap/here',{target:f.dataset.target,width_m:Number(lapField(f,'width').value)},'現在地をラインとして保存しました。'));
  const clear=f.querySelector('[data-lap-clear]');
  if(clear)clear.onclick=()=>action(()=>lapCall('/api/lap',{[f.dataset.target]:null},'このラインを外しました。'));
}
$('lap-save').onclick=()=>action(()=>{
  const body={min_lap_s:Number($('lap-min').value),total_laps:$('lap-total').value===''?null:Number($('lap-total').value)};
  for(const f of lapLines()){
    const g=lapRead(f);
    if(f.dataset.target==='control')Object.assign(body,g?{enabled:true,...g}:{enabled:false});
    else body[f.dataset.target]=g;
  }
  return lapCall('/api/lap',body,'保存しました。');
});
$('lap-off').onclick=()=>action(()=>lapCall('/api/lap',{enabled:false},'ラップ計測をOFFにしました。周回数は残っています。'));
$('lap-reset').onclick=()=>{
  if(!confirm('周回数・ラップの記録を0に戻します。レース開始前だけ押してください。よろしいですか？'))return;
  action(()=>lapCall('/api/lap/reset',undefined,'周回数をリセットしました。次のスタート（またはライン通過）から1周目です。'));
};
setInterval(()=>{if(page==='settings'&&!lapLoaded)api('/api/lap').then(lapShow).catch(()=>{});},500);
