'use strict';
// Phone course-walk screen (field.py): register the three lap lines where you stand.
const $=id=>document.getElementById(id);
const NAMES={start:'スタート',control:'コントロール',goal:'ゴール'};
const GOOD_HACC_M=2.5;
const key=(()=>{
  const fromUrl=new URLSearchParams(location.search).get('k');
  try{if(fromUrl)localStorage.setItem('field-key',fromUrl);return fromUrl||localStorage.getItem('field-key')||'';}
  catch{return fromUrl||'';}
})();
let last=null,busy=false,messageTimer=0;

function say(text,ok=false){
  const m=$('message');m.textContent=text;m.hidden=!text;m.classList.toggle('ok',ok);
  clearTimeout(messageTimer);if(ok)messageTimer=setTimeout(()=>{m.hidden=true;},6000);
}
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',
    headers:{'Content-Type':'application/json','X-EcoCapture':'1','X-Field-Key':key},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(8000)});
  const data=await response.json().catch(()=>({detail:response.statusText}));
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'操作できませんでした。');
  return data;
}
async function act(fn){
  if(busy)return;busy=true;
  try{await fn();}catch(error){say(error.message);}finally{busy=false;}
}
function gateOf(line,target){
  if(target==='control')return line.enabled?{lat:line.lat,lon:line.lon,bearing:line.bearing}:null;
  return line[target];
}
function distance(a,b){
  const k=111320,x=(b.lon-a.lon)*k*Math.cos(a.lat*Math.PI/180),y=(b.lat-a.lat)*k;
  return Math.hypot(x,y);
}
const fmtDist=m=>m<1000?`${Math.round(m)} m`:`${(m/1000).toFixed(2)} km`;
const lapClock=min=>{if(!Number.isFinite(min))return '—';const s=min*60;return `${Math.floor(s/60)}:${(s%60).toFixed(1).padStart(4,'0')}`;};

function badge(id,text,kind){const b=$(id);b.textContent=text;b.className=`badge ${kind||''}`;}
function show(d){
  last=d;
  const g=d.gnss,fixed=d.connected&&g.lat!==null&&g.lon!==null;
  $('link').textContent=d.connected?'ロガー接続中':'ロガーの受信待ち';$('link').classList.toggle('bad',!d.connected);
  if(!d.connected)badge('gnss-badge','ロガー受信なし','bad');
  else if(!fixed)badge('gnss-badge','測位なし','bad');
  else if(g.hacc_m!==null&&g.hacc_m>GOOD_HACC_M)badge('gnss-badge','精度が低い','warn');
  else badge('gnss-badge','測位OK','ok');
  $('gnss-sats').textContent=g.sats??'—';
  $('gnss-hacc').textContent=g.hacc_m===null||g.hacc_m===undefined?'—':`${g.hacc_m.toFixed(1)} m`;
  $('gnss-speed').textContent=g.speed===null||g.speed===undefined?'—':`${g.speed.toFixed(0)} km/h`;
  const lg=d.logging;
  if(!lg.active)badge('rec-badge','記録していない','bad');
  else if(lg.sd_warning)badge('rec-badge','● 記録中（本体のみ）','warn');
  else badge('rec-badge','● 記録中','ok');
  const line=d.lap.line;
  for(const card of document.querySelectorAll('.line')){
    const t=card.dataset.target,gate=gateOf(line,t);
    card.classList.toggle('registered',!!gate);
    card.querySelector('[data-state]').textContent=!gate?'未登録':
      gate.bearing===null?'登録済み（向きは最初の通過で決まる）':`登録済み（向き ${Math.round(gate.bearing)}°）`;
    card.querySelector('[data-dist]').textContent=!gate?'':fixed?`ここから ${fmtDist(distance(g,gate))}`:'—';
    card.querySelector('[data-here]').disabled=!fixed;
  }
  $('count-mode').textContent=!line.enabled?'数え方：— （コントロール未登録）':line.start
    ?'数え方：エコラン式 — スタートから最初のコントロール通過までが1周目'
    :'数え方：サーキット式 — 最初のコントロール通過は数えず、次の通過で1周目。エコランの周回にするにはスタートを登録';
  $('count-mode').classList.toggle('circuit',line.enabled&&!line.start);
  $('total-now').textContent=line.total_laps?`${line.total_laps}周`:'指定なし';
  for(const b of document.querySelectorAll('[data-total]'))
    b.setAttribute('aria-pressed',String(String(line.total_laps??'')===b.dataset.total));
  const v=d.lap.values;
  $('lap-now').textContent=!line.enabled?'ライン未登録':d.lap.finished?`ゴール済み・${v.LapCount}周`:
    d.lap.running?`${v.CurrentLap}周目を走行中（${lapClock(v.ElapsedTime)}）`:`${v.LapCount}周・スタート待ち`;
  $('qr-show').disabled=!line.enabled;
}

async function poll(){
  if(!key){say('合言葉がありません。ロガーの管理画面（設定 → ラップ計測）のQRから開いてください。');return;}
  if(document.hidden){setTimeout(poll,1000);return;}
  try{show(await api('/api/field/state'));if($('message').textContent.startsWith('ロガーに'))say('');}
  catch(error){
    $('link').textContent='接続できません';$('link').classList.add('bad');
    say(error.name==='TimeoutError'||error instanceof TypeError?'ロガーにつながりません。スマホとロガーが同じテザリング（Wi-Fi）にいるか確かめてください。':error.message);
  }
  setTimeout(poll,1000);
}

for(const card of document.querySelectorAll('.line')){
  const t=card.dataset.target;
  card.querySelector('[data-here]').onclick=()=>{
    const old=last&&gateOf(last.lap.line,t);
    if(old&&!confirm(`${NAMES[t]}ラインは登録済みです。今いる場所で置き換えますか？`))return;
    act(async()=>{
      const d=await api('/api/field/here',{target:t});
      const h=d.here||{};
      say(`${NAMES[t]}ラインを登録しました（${h.fixes>1?`${h.fixes}点の平均・ばらつき ${h.spread_m} m`:'その場の1点。止まって押すと平均で登録します'}）。`,true);
      card.classList.remove('just');void card.offsetWidth;card.classList.add('just');
      $('qr').hidden=true;
      if(last)show({...last,lap:d});
    });
  };
}
for(const b of document.querySelectorAll('[data-total]'))
  b.onclick=()=>act(async()=>{
    const total=b.dataset.total===''?null:Number(b.dataset.total);
    const d=await api('/api/field/total',{total_laps:total});
    say(total?`規定周回数を${total}周にしました。`:'規定周回数を指定なしにしました。',true);
    if(last)show({...last,lap:d});
  });
$('reset').onclick=()=>{
  if(!confirm('周回数とラップを0に戻します。スタートの直前だけ押してください。よろしいですか？'))return;
  act(async()=>{const d=await api('/api/field/reset',{});say('周回数をリセットしました。スタートから1周目を数えます。',true);if(last)show({...last,lap:d});});
};
$('qr-show').onclick=()=>act(async()=>{
  const d=await api('/api/field/code');
  $('qr-svg').innerHTML=d.svg;$('qr-id').textContent=d.id;
  $('qr-warn').textContent=d.unknown_bearing.length?`${d.unknown_bearing.join('・')}ラインの向きが未定です。各スマホが最初の通過で別々に決めます。`:'';
  $('qr').hidden=false;
});
poll();
