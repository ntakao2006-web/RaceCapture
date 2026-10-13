'use strict';
// Start/finish line settings (lap.py). Dashboard values arrive with the telemetry frame.
let lapLoaded=false;
function lapShow(data){
  const l=data.line;
  $('lap-width').value=l.width_m;$('lap-min').value=l.min_lap_s;
  $('lap-line-state').textContent=!l.enabled?'未設定':l.bearing===null?'登録済み・進行方向は最初の通過で決定':`登録済み・進行方向 ${Math.round(l.bearing)}°`;
  if(data.error)$('lap-result').textContent=data.error;
  lapLoaded=true;
}
async function lapCall(path,body,done){
  const data=await api(path,'POST',body);lapShow(data);$('lap-result').textContent=done;
}
$('lap-here').onclick=()=>action(()=>lapCall('/api/lap/here',{width_m:Number($('lap-width').value)},'現在地をラインとして保存しました。'));
$('lap-save').onclick=()=>action(()=>lapCall('/api/lap',{width_m:Number($('lap-width').value),min_lap_s:Number($('lap-min').value)},'保存しました。'));
$('lap-off').onclick=()=>action(()=>lapCall('/api/lap',{enabled:false},'ラップ計測をOFFにしました。周回数は残っています。'));
$('lap-reset').onclick=()=>{
  if(!confirm('周回数・ラップの記録を0に戻します。レース開始前だけ押してください。よろしいですか？'))return;
  action(()=>lapCall('/api/lap/reset',undefined,'周回数をリセットしました。次の通過から1周目です。'));
};
setInterval(()=>{if(page==='settings'&&!lapLoaded)api('/api/lap').then(lapShow).catch(()=>{});},500);
