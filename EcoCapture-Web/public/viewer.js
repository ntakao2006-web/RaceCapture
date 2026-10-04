'use strict';
const $=id=>document.getElementById(id),fmt=(v,n=1)=>Number.isFinite(v)?v.toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
let page='dashboard',track=[],trend=[],frame=null,lastSeq=null;
const clock=s=>[Math.floor(s/3600),Math.floor(s/60)%60,Math.floor(s)%60].map(v=>String(v).padStart(2,'0')).join(':');
const mapView=new window.EcoMap();mapView.gapSeconds=3;
const groups={'gnss-values':[['Lat','緯度','°',6],['Lon','経度','°',6],['GPSSpeed','GNSS速度','km/h',1],['Altitude','標高','m',1],['Yaw','方位','°',1],['GPSFix','測位状態','',0],['GPSSats','衛星数','',0]],'accel-values':[['AccelX','加速度 X','m/s²',2],['AccelY','加速度 Y','m/s²',2],['AccelZ','加速度 Z','m/s²',2],['LongAccel','前後加速度','g',3],['LatAccel','左右加速度','g',3]],'gyro-values':[['GyroX','角速度 X','°/s',2],['GyroY','角速度 Y','°/s',2],['GyroZ','角速度 Z','°/s',2],['Roll','ロール','°',2],['Pitch','ピッチ','°',2]]};
for(const [id,rows]of Object.entries(groups)){for(const [name,label,unit,digits]of rows){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd'),value=document.createElement('span');dt.textContent=label;value.dataset.value=name;value.dataset.digits=digits;value.textContent='—';dd.append(value,` ${unit}`);row.append(dt,dd);$(id).append(row);}}
document.querySelectorAll('.nav').forEach(button=>button.onclick=()=>{page=button.dataset.page;document.querySelectorAll('.page').forEach(p=>p.hidden=p.id!==page);document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b===button));render();});
$('clear-track').onclick=()=>{track=[];render();};
function canvas(id){const c=$(id);if(!c.clientWidth)return null;const w=c.clientWidth,h=c.clientHeight,dpr=devicePixelRatio||1;if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);}const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return {ctx,w,h};}
function render(){
  const s=frame?.status||{},v=frame?.sample?.values||{};
  document.querySelectorAll('[data-value]').forEach(e=>e.textContent=fmt(v[e.dataset.value],Number(e.dataset.digits||1)));
  $('device-name').textContent=s.device||'EcoLogger V2';$('connection').textContent=s.connected?'● 受信中':'接続待ち';$('rate').textContent='閲覧専用 / 更新 1 Hz';
  $('rpm-bar').max=s.profile==='ncec-2005-mt'?8000:6000;
  $('rpm-value').textContent=['demo-vehicle','ncec-2005-mt'].includes(s.profile)?fmt(v.RPM,0):'—';$('rpm-bar').value=['demo-vehicle','ncec-2005-mt'].includes(s.profile)?v.RPM||0:0;$('rpm-hint').textContent=['demo-vehicle','ncec-2005-mt'].includes(s.profile)?`スロットル ${fmt(v.Throttle,1)} %`:'車載CAN接続なし';$('profile-label').textContent=s.profile==='ncec-2005-mt'?'NCEC 2005 MT / NOPRO':s.profile==='demo-vehicle'?'車両表示':'車載CAN接続なし';
  $('sample-seq').textContent=`SEQ ${frame?.sample?.seq??'—'}`;const recording=s.logging?.active;$('rec-badge').textContent=recording===true?'● REC':recording===false?'○ STANDBY':'状態不明';$('rec-badge').classList.toggle('recording',recording===true);$('rec-time').textContent=recording===true?clock(s.logging.elapsed_s):'—';$('rec-rows').textContent=`${s.logging?.rows??'—'} samples`;
  $('footer-status').textContent=s.connected?'閲覧専用・UNO Qから受信中':'UNO Qとの接続を待っています';
  $('hardware-status').replaceChildren(...Object.entries(s.sensors||{}).map(([k,v])=>{const span=document.createElement('span');span.textContent=`${k.toUpperCase()} ${v}`;return span;}));
  if(page==='gnss')mapView.update(track,frame?.sample&&Number.isFinite(v.Lon)&&Number.isFinite(v.Lat)?[v.Lon,v.Lat]:null);
  if(page==='dashboard'){const c=canvas('speed-chart');if(c){const {ctx,w,h}=c,now=performance.now()/1000;ctx.strokeStyle='#ddd';ctx.font='12px Segoe UI';for(let i=0;i<4;i++){const y=10+(h-30)*i/3;ctx.beginPath();ctx.moveTo(30,y);ctx.lineTo(w,y);ctx.stroke();ctx.fillStyle='#666';ctx.fillText(String(60-20*i),0,y+4);}ctx.strokeStyle='#222';ctx.lineWidth=2;ctx.beginPath();trend.forEach((p,i)=>{const x=30+(w-30)*(1-(now-p[0])/60),y=h-20-p[1]/60*(h-30);if(!i||p[0]-trend[i-1][0]>3)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();}}
  if(page==='imu'){const c=canvas('g-chart');if(c){const {ctx,w,h}=c,r=Math.min(w,h)/2-30;ctx.strokeStyle='#ccc';for(const scale of [.5,1]){ctx.beginPath();ctx.arc(w/2,h/2,r*scale,0,2*Math.PI);ctx.stroke();}ctx.beginPath();ctx.moveTo(w/2-r,h/2);ctx.lineTo(w/2+r,h/2);ctx.moveTo(w/2,h/2-r);ctx.lineTo(w/2,h/2+r);ctx.stroke();if(frame?.sample){ctx.fillStyle='#b82428';ctx.beginPath();ctx.arc(w/2+v.LatAccel*r,h/2-v.LongAccel*r,6,0,2*Math.PI);ctx.fill();}}$('diagnostics').textContent=s.connected?'データ受信中':'接続待ち';}
}
window.addEventListener('resize',render);
async function poll(){
  try{const response=await fetch('/api/telemetry',{signal:AbortSignal.timeout(4000)});if(!response.ok)throw Error();frame=await response.json();if(frame.sample&&lastSeq!==frame.sample.seq){const now=performance.now()/1000,v=frame.sample.values;if(lastSeq!==null&&frame.sample.seq<lastSeq){track=[];trend=[];}lastSeq=frame.sample.seq;if(Number.isFinite(v.Lon)&&Number.isFinite(v.Lat))track.push([v.Lon,v.Lat,now]);track=track.filter(p=>now-p[2]<=300);if(Number.isFinite(v.GPSSpeed))trend.push([now,v.GPSSpeed]);trend=trend.filter(p=>now-p[0]<=60);}}
  catch{frame=null;mapView.update(track,null);}render();setTimeout(poll,1000);
}
poll();
