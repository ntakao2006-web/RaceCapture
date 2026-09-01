import{validChannel,validDatabase,streamPoint,dayKey,niceGridMeters,formatGridMeters}from"./live-core.js";
import{databaseUrl as deployedDatabase}from"./config.js";
const $=id=>document.getElementById(id),state=$("state"),dashboard=$("dashboard"),setup=$("setup"),canvas=$("route"),ctx=canvas.getContext("2d");
let channel="",database="",points=[],source,meta={},configured=false;
const number=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):"--";
function config(){const q=new URLSearchParams(location.search);channel=(q.get("id")||"").toLowerCase();database=(deployedDatabase||q.get("db")||"").replace(/\/$/,"");return validChannel(channel)&&validDatabase(database)}
async function start(){
  if(!config()){setup.hidden=false;state.textContent="リンク確認";return} configured=true;
  dashboard.hidden=false;state.textContent="履歴読込中";
  try{
    const from=Date.now()-30*60000,days=[...new Set([dayKey(from),dayKey(Date.now())])];
    const results=await Promise.all(days.map(d=>fetch(`${database}/channels/${channel}/history/${d}.json?orderBy=%22%24key%22&startAt=%22${from}%22`,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json()})));
    points=results.flatMap(x=>Object.values(x||{})).filter(p=>p?.t>=from).sort((a,b)=>a.t-b.t).slice(-1800);
    const mr=await fetch(`${database}/channels/${channel}/meta.json`,{cache:"no-store"});if(mr.ok)meta=await mr.json()||{};render();
    source=new EventSource(`${database}/channels/${channel}/latest.json`);
    for(const type of["put","patch"])source.addEventListener(type,e=>{const p=streamPoint(e.data);if(!p)return;points.push(p);points=points.filter(x=>x.t>Date.now()-30*60000).slice(-1800);render();});
    source.onopen=()=>{$("error").textContent="";updateState()};source.onerror=()=>{state.textContent="再接続中";state.className="state error"};
  }catch(e){state.textContent="接続エラー";state.className="state error";setup.hidden=false;$("error").textContent=e.message}
}
function value(d,...keys){for(const k of keys)if(Number.isFinite(d?.[k]))return d[k];return NaN}
function updateState(){if(!configured)return;const live=points.at(-1)?.t>Date.now()-15000;state.textContent=live?"LIVE":"更新待ち";state.className=live?"state":"state off"}
function render(){const p=points.at(-1),d=p?.d||{},demo=p?.demo??meta.demo,vehicle=p?.vehicle??meta.vehicle;$("speed").textContent=number(value(d,"GPSSpeed","Speed"),1);$("rpm").textContent=number(value(d,"RPM"),0);$("ax").textContent=number(value(d,"LongAccel"),2);$("ay").textContent=number(value(d,"LatAccel"),2);$("az").textContent=number(value(d,"VertAccel"),2);$("alt").textContent=number(value(d,"Altitude"),1);$("sats").textContent=number(value(d,"GPSSats"),0);$("acc").textContent=number(value(d,"GPSHAcc"),1);$("lat").textContent=number(value(d,"Lat"),7);$("lon").textContent=number(value(d,"Lon"),7);$("vehicle").textContent=(demo?"DEMO · ":"")+(vehicle||"--");$("updated").textContent=p?new Date(p.t).toLocaleTimeString():"--";updateState();draw()}
function draw(){
  const ratio=devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);ctx.fillStyle="#050505";ctx.fillRect(0,0,w,h);
  const route=points.map(p=>({lat:value(p.d,"Lat"),lon:value(p.d,"Lon")})).filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon));
  if(route.length<1){$("grid-scale").textContent="1グリッド = --";return}
  const mean=route.reduce((a,p)=>({lat:a.lat+p.lat/route.length,lon:a.lon+p.lon/route.length}),{lat:0,lon:0}),cos=Math.cos(mean.lat*Math.PI/180);const xy=route.map(p=>({x:(p.lon-mean.lon)*cos,y:-(p.lat-mean.lat)})),xs=xy.map(p=>p.x),ys=xy.map(p=>p.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),spanX=Math.max(maxX-minX,1e-6),spanY=Math.max(maxY-minY,1e-6),scale=Math.min(Math.max(w-36,1)/spanX,Math.max(h-36,1)/spanY),ox=(w-(minX+maxX)*scale)/2,oy=(h-(minY+maxY)*scale)/2;
  const pixelsPerMeter=scale/111320,gridMeters=niceGridMeters(70/pixelsPerMeter),gridPx=gridMeters*pixelsPerMeter;$("grid-scale").textContent=`1グリッド = ${formatGridMeters(gridMeters)}`;
  ctx.strokeStyle="#202020";ctx.lineWidth=1;for(let x=((ox%gridPx)+gridPx)%gridPx;x<w;x+=gridPx){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}for(let y=((oy%gridPx)+gridPx)%gridPx;y<h;y+=gridPx){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}
  ctx.strokeStyle="#ff3030";ctx.lineWidth=3;ctx.lineJoin="round";ctx.beginPath();xy.forEach((p,i)=>(i?ctx.lineTo(p.x*scale+ox,p.y*scale+oy):ctx.moveTo(p.x*scale+ox,p.y*scale+oy)));ctx.stroke();const last=xy.at(-1);ctx.fillStyle="#fff";ctx.beginPath();ctx.arc(last.x*scale+ox,last.y*scale+oy,8,0,Math.PI*2);ctx.fill();ctx.fillStyle="#ff3030";ctx.beginPath();ctx.arc(last.x*scale+ox,last.y*scale+oy,4,0,Math.PI*2);ctx.fill()
}
addEventListener("resize",draw);setInterval(updateState,5000);start();
