import{validChannel,validDatabase,streamPoint,dayKey}from"./live-core.js";
import{databaseUrl as deployedDatabase}from"./config.js";
import{GsiRouteMap}from"./route-map.js";
const $=id=>document.getElementById(id),state=$("state"),dashboard=$("dashboard"),setup=$("setup");
const map=new GsiRouteMap($("route"),$("map-status"));
let channel="",database="",points=[],source,meta={},configured=false;
const number=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):"--";
function config(){const q=new URLSearchParams(location.search);channel=(q.get("id")||"").toLowerCase();database=(deployedDatabase||q.get("db")||"").replace(/\/$/,"");return validChannel(channel)&&validDatabase(database)}
async function start(){
  if(!config()){setup.hidden=false;state.textContent="リンク確認";return} configured=true;
  dashboard.hidden=false;state.textContent="履歴読込中";
  try{
    const from=Date.now()-30*60000,days=[...new Set([dayKey(from),dayKey(Date.now())])];
    const results=await Promise.all(days.map(d=>fetch(`${database}/channels/${channel}/history/${d}.json?orderBy=%22%24key%22&startAt=%22${from}%22`,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json()})));
    points=results.flatMap(x=>Object.values(x||{})).filter(p=>Number.isFinite(p?.t)&&p.t>=from&&p.d).sort((a,b)=>a.t-b.t).slice(-1800);
    const mr=await fetch(`${database}/channels/${channel}/meta.json`,{cache:"no-store"});if(mr.ok)meta=await mr.json()||{};render();
    source=new EventSource(`${database}/channels/${channel}/latest.json`);
    for(const type of["put","patch"])source.addEventListener(type,e=>{
      const p=streamPoint(e.data);if(!p||!Number.isFinite(p.t))return;
      points=points.filter(x=>x.t!==p.t&&x.t>Date.now()-30*60000);points.push(p);points.sort((a,b)=>a.t-b.t);points=points.slice(-1800);render();
    });
    source.onopen=()=>{$("error").textContent="";updateState()};
    source.onerror=()=>{state.textContent="再接続中";state.className="state error"};
  }catch(e){state.textContent="接続エラー";state.className="state error";setup.hidden=false;$("error").textContent=e.message}
}
function value(d,...keys){for(const k of keys)if(Number.isFinite(d?.[k]))return d[k];return NaN}
function updateState(){if(!configured)return;const live=points.at(-1)?.t>Date.now()-15000;state.textContent=live?"LIVE":"更新待ち";state.className=live?"state":"state off"}
function render(){
  points=points.filter(p=>p.t>Date.now()-30*60000&&p.t<=Date.now()+15000);
  const p=points.at(-1),fresh=p?.t>Date.now()-15000,d=fresh?p?.d||{}:{},demo=p?.demo??meta.demo,vehicle=p?.vehicle??meta.vehicle;
  const fields={speed:["GPSSpeed",1],rpm:["RPM",0],ax:["LongAccel",2],ay:["LatAccel",2],az:["VertAccel",2],alt:["Altitude",1],sats:["GPSSats",0],acc:["GPSHAcc",1],lat:["Lat",7],lon:["Lon",7],steering:["SteeringAngle",1],water:["WaterTemp",1],oil:["OilTemp",1],vehicleSpeed:["Speed",0]};
  for(const[id,[key,precision]]of Object.entries(fields))$(id).textContent=number(value(d,key),precision);
  $("speed").textContent=number(value(d,"GPSSpeed","Speed"),1);
  const names={ux250h:"レクサス UX250h · MZAH10",lx:"レクサス LX",roadster:"ロードスター",cub:"カブ",none:"車載CAN接続なし"};
  $("vehicle").textContent=(demo?"DEMO · ":"")+(names[vehicle]||vehicle||"--");
  $("updated").textContent=p?new Date(p.t).toLocaleTimeString():"--";
  updateState();map.setPoints(points);
}
$("map-in").addEventListener("click",()=>map.zoom(1));
$("map-out").addEventListener("click",()=>map.zoom(-1));
$("map-fit").addEventListener("click",()=>map.fit());
addEventListener("resize",()=>map.schedule());setInterval(render,5000);start();
