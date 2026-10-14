'use strict';
const $ = id => document.getElementById(id);
let config, channels = [], latest = null, lastMessage = 0, socket, retry = 0, page = 'dashboard';
let trend = [], track = [], solveTrack = [], lastSeq = null, deleteTarget = null;
const format = (value, digits = 1) => Number.isFinite(value) ? value.toLocaleString('en-US', {minimumFractionDigits:digits, maximumFractionDigits:digits}) : '—';
const elapsed = s => [Math.floor(s/3600), Math.floor(s/60)%60, Math.floor(s)%60].map(x=>String(x).padStart(2,'0')).join(':');
const lapClock = minutes => { if (!Number.isFinite(minutes)) return '—'; const s = minutes*60; return `${Math.floor(s/60)}:${(s%60).toFixed(1).padStart(4,'0')}`; };
const bytes = n => n >= 1048576 ? `${format(n/1048576,1)} MiB` : `${format(n/1024,1)} KiB`;
function message(text, error = false) { $('message').textContent = text; $('message').hidden = !text; if (error) console.error(text); }
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: {'Content-Type':'application/json','X-EcoCapture':'1'}, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(path.startsWith('/api/device/')||path==='/api/podium/check'?50000:10000)});
  if (!response.ok) {
    const data = await response.json().catch(()=>({detail:response.statusText}));
    throw new Error(typeof data.detail === 'string' ? data.detail : data.detail.map(x=>`${x.loc.slice(1).join('.')}: ${x.msg}`).join(' / '));
  }
  return response.json();
}
async function action(fn) { try { await fn(); } catch (error) { message(error.message, true); } }
function readings(id, names) {
  const root = $(id); root.replaceChildren();
  for (const name of names) {
    const channel = channels.find(x=>x.name===name), row=document.createElement('div'), dt=document.createElement('dt'), dd=document.createElement('dd');
    dt.textContent=channel.label; const value=document.createElement('span'); value.dataset.value=name;
    value.dataset.digits = ['Lat','Lon'].includes(name) ? '6' : ['GPSFix','GPSSats','GNSSHz'].includes(name) ? '0' : '2';
    value.textContent='—'; dd.append(value, ` ${channel.unit}`); row.append(dt,dd); root.append(row);
  }
}
function switchPage(name) {
  page=name;
  document.querySelectorAll('.page').forEach(x=>x.hidden=x.id!==name);
  document.querySelectorAll('.nav').forEach(x=>{x.classList.toggle('active',x.dataset.page===name); x.setAttribute('aria-current',x.dataset.page===name?'page':'false');});
  if(name==='logs') action(loadLogs);
  draw();
}
document.querySelectorAll('.nav').forEach(x=>x.addEventListener('click',()=>switchPage(x.dataset.page)));
function openLinkedPage() {
  const name = location.hash.slice(1);
  if (['dashboard','gnss','imu','logs','settings'].includes(name)) switchPage(name);
}
window.addEventListener('hashchange', openLinkedPage);
function connect() {
  socket = new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  socket.onopen = () => { retry = 0; };
  socket.onmessage = event => {
    try {
      const frame=JSON.parse(event.data); if(frame.type!=='telemetry')return;
      lastMessage=performance.now(); latest=frame; update(frame);
    } catch(error) { message(`受信形式エラー: ${error.message}`, true); }
  };
  socket.onerror = () => socket.close();
  socket.onclose = () => { invalidate(); setTimeout(connect, Math.min(5000,500*2**Math.min(retry++,4))); };
}
function invalidate() {
  document.querySelectorAll('[data-value]').forEach(x=>x.textContent='—');
  $('rpm-value').textContent='—'; $('rpm-bar').value=0; $('connection').textContent='接続待ち / 値は無効';
  ['lap-count','lap-elapsed','lap-last','lap-best'].forEach(id=>$(id).textContent='—');
  $('signal-tiles').querySelectorAll('strong').forEach(x=>x.textContent='—');
  $('rate').textContent='受信 — Hz'; $('start-log').disabled=true; $('footer-status').textContent='通信待ち';
  $('rec-badge').textContent='記録状態を確認中'; $('rec-badge').classList.remove('recording');
  $('rec-time').textContent='—'; $('stop-log').disabled=true; $('save-config').disabled=true;
  latest=null; drawG(null);mapView.update(track,null);
}
function update(frame) {
  const s=frame.status, v=frame.sample?.values || {};
  document.querySelectorAll('[data-value]').forEach(x=>x.textContent=format(v[x.dataset.value],Number(x.dataset.digits||1)));
  const vehicle=config?.profile==='demo-vehicle'||config?.profile==='ncec-2005-mt';
  $('rpm-bar').max=config?.profile==='ncec-2005-mt'?8000:6000;
  $('rpm-value').textContent=vehicle ? format(v.RPM,0) : '—'; $('rpm-bar').value=vehicle ? v.RPM||0 : 0;
  $('rpm-hint').textContent=vehicle ? `スロットル ${format(v.Throttle,1)} %` : '車載CAN接続なし';
  $('profile-label').textContent=config?.profile==='ncec-2005-mt'?'NCEC 2005 MT / NOPRO':vehicle?'車両表示':'車載CAN接続なし';
  const lap=frame.sample?.lap||{};
  $('lap-count').textContent=Number.isFinite(lap.LapCount)?String(lap.LapCount):'—';
  $('lap-elapsed').textContent=lapClock(lap.ElapsedTime);$('lap-last').textContent=lapClock(lap.LapTime);$('lap-best').textContent=lapClock(lap.BestLap);
  $('lap-hint').textContent=lap.LapCount===undefined||lap.LapCount===null?'ラップ計測は未設定です（Settings → ラップ計測）':lap.CurrentLap===0?'ライン通過を待っています（最初の通過から1周目）':'';
  $('connection').textContent=s.connected?'● MCU受信中':'MCU通信待ち / 値は無効';
  $('device-name').textContent=s.device; $('rate').textContent=`受信 ${format(s.receive_hz,1)} Hz`;
  $('sample-seq').textContent=`SEQ ${frame.sample?.seq ?? '—'}`;
  $('storage-free').textContent=`（空き ${format(s.storage_free_bytes/1073741824,2)} GiB）`;
  $('hardware-status').replaceChildren(...Object.entries(s.sensors||{}).map(([k,v])=>{const span=document.createElement('span');span.textContent=`${k.toUpperCase()} ${v}`;return span;}));
  if($('imu-calibration'))$('imu-calibration').textContent=frame.sample?.imu_calibration?'IMU校正（0〜3）：'+Object.entries(frame.sample.imu_calibration).map(([k,v])=>`${k} ${v}`).join(' / '):'IMU校正：受信待ち';
  const tiles=(config?.signals||[]).slice(0,8);$('signal-tiles').hidden=!tiles.length;
  $('signal-tiles').replaceChildren(...tiles.map(signal=>{const a=document.createElement('article'),label=document.createElement('span'),value=document.createElement('strong'),unit=document.createElement('small');label.textContent=signal.name;value.textContent=format(frame.sample?.can_signals?.[signal.name],signal.conversion==='ntc'?1:2);unit.textContent=signal.unit;a.append(label,value,unit);return a;}));
  $('can-live').replaceChildren(...(config?.signals||[]).map(signal=>{const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=signal.name;dd.textContent=`${format(frame.sample?.can_signals?.[signal.name],2)} ${signal.unit}`;row.append(dt,dd);return row;}));
  const log=s.logging; $('rec-badge').textContent=log.active?(log.sd_warning?'● REC（本体のみ）':'● REC'):'○ STANDBY';
  $('rec-warning').textContent=log.sd_warning||''; $('rec-warning').hidden=!log.sd_warning; $('rec-badge').classList.toggle('recording',log.active);
  $('rec-time').textContent=elapsed(log.elapsed_s); $('rec-rows').textContent=`${log.rows.toLocaleString()} samples`;
  $('start-log').disabled=log.active||!s.connected; $('stop-log').disabled=!log.active; $('save-config').disabled=log.active;
  $('footer-status').textContent=`受信 ${s.received.toLocaleString()} 件 · ${s.age_ms??'—'} ms · 内蔵eMMC`;
  const diagnostics={'MCU生成':`${s.mcu_generation_hz} Hz`,'Linux受信':`${format(s.receive_hz,1)} Hz（まとめて取得）`,'回収周期':`${s.poll_target_hz} 回/秒`,'受信件数':s.received,'Bridgeエラー累計':s.bridge_errors,'MCU再起動検知':s.mcu_resets,'最終受信から':`${s.age_ms??'—'} ms`,'通信状態':s.error||'正常','記録状態':log.error||'正常','IMU読み出しエラー':s.hardware?.imu_errors??'—','GNSS読み出しエラー':s.hardware?.gnss_errors??'—','IMU割り込み':s.hardware?.imu_irq??'—','Bridge未転送（SD記録は別）':s.hardware?.dropped??'—','SD記録エラー':s.hardware?.sd_errors??'—','SD用バッファ欠落':s.hardware?.sd_queue_dropped??'—','CAN溢れ':JSON.stringify(s.hardware?.can_overflow??[]),'SD操作':s.sd_copy?.error|| (s.sd_copy?.active?s.sd_copy.operation==='read'?`${s.sd_copy.read_sectors??0} セクタ読出し済み`:`読出し ${s.sd_copy.read_sectors??0} / 書込み ${s.sd_copy.written_sectors??0} セクタ`:s.sd_copy?.verified?'照合済み':'待機')};
  $('diagnostics').replaceChildren(...Object.entries(diagnostics).map(([k,v])=>{const d=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;d.append(dt,dd);return d;}));
  if(log.error) message(`記録エラー：${log.error}`, true);
  if(s.config_error) message('保存設定を読めなかったため初期設定を使用しています。Settingsで内容を確認してください。');
  if(frame.sample && lastSeq!==frame.sample.seq) {
    const now=performance.now()/1000;
    if(lastSeq!==null && frame.sample.seq<lastSeq) {trend=[]; track=[];}
    if(Number.isFinite(v.GPSSpeed))trend.push([now,v.GPSSpeed]); trend=trend.filter(p=>now-p[0]<=60);
    if(Number.isFinite(v.Lon)&&Number.isFinite(v.Lat))track.push([v.Lon,v.Lat,now]); track=track.filter(p=>now-p[2]<=300);
    lastSeq=frame.sample.seq;
  }
  draw();
}
setInterval(()=>{if(lastMessage && performance.now()-lastMessage>1500 && latest)invalidate();},250);
function canvas(id) {
  const c=$(id); if(!c.clientWidth)return null;
  const dpr=window.devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;
  if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);}
  const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.font='12px Segoe UI';
  return {ctx,w,h};
}
function drawTrend() {
  const c=canvas('speed-chart');if(!c)return;const {ctx,w,h}=c;
  const left=32,top=8,bottom=h-20;
  for(let i=0;i<=3;i++){const y=top+(bottom-top)*i/3;ctx.strokeStyle='#e6e6e6';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w,y);ctx.stroke();ctx.fillStyle='#777';ctx.fillText(String(60-i*20),0,y+4);}
  if(trend.length<2)return;
  const now=performance.now()/1000;ctx.strokeStyle='#222';ctx.lineWidth=1.8;ctx.beginPath();
  trend.forEach(([t,s],i)=>{const x=left+(w-left)*(1-(now-t)/60),y=bottom-s/60*(bottom-top);if(i===0||t-trend[i-1][0]>1)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  ctx.fillStyle='#777';ctx.fillText('−60 s',left,h-2);ctx.fillText('現在',w-27,h-2);
}
function drawTrack(id, points) {
  const c=canvas(id);if(!c)return;const {ctx,w,h}=c;ctx.fillStyle='#fafafa';ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#ebebeb';for(let x=0;x<w;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}for(let y=0;y<h;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  ctx.fillStyle='#555';ctx.fillText('N ↑',w-35,22);
  if(points.length<2){ctx.fillText('経路データを待っています',20,h/2);return;}
  const lon0=points[0][0],lat0=points[0][1]; const p=points.map(a=>[(a[0]-lon0)*111320*Math.cos(lat0*Math.PI/180),(a[1]-lat0)*111320,a[2]]);
  const xs=p.map(a=>a[0]),ys=p.map(a=>a[1]),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),scale=Math.min((w-60)/Math.max(20,x1-x0),(h-60)/Math.max(20,y1-y0));
  const xy=a=>[w/2+(a[0]-(x0+x1)/2)*scale,h/2-(a[1]-(y0+y1)/2)*scale];ctx.strokeStyle='#b82428';ctx.lineWidth=2;ctx.beginPath();
  p.forEach((a,i)=>{const [x,y]=xy(a);if(!i||(a[2]!==undefined&&a[2]-p[i-1][2]>1))ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  const [x,y]=xy(p.at(-1));ctx.fillStyle='#b82428';ctx.beginPath();ctx.arc(x,y,5,0,2*Math.PI);ctx.fill();
  ctx.fillStyle='#555';ctx.fillText(`表示幅 約 ${Math.round(w/scale)} m`,15,h-12);
}
function drawG(v) {
  const c=canvas('g-chart');if(!c)return;const {ctx,w,h}=c;const r=Math.min(w,h)/2-30;
  ctx.strokeStyle='#ccc';[.5,1].forEach(s=>{ctx.beginPath();ctx.arc(w/2,h/2,r*s,0,2*Math.PI);ctx.stroke();});
  ctx.beginPath();ctx.moveTo(w/2-r,h/2);ctx.lineTo(w/2+r,h/2);ctx.moveTo(w/2,h/2-r);ctx.lineTo(w/2,h/2+r);ctx.stroke();
  if(v&&Number.isFinite(v.LatAccel)&&Number.isFinite(v.LongAccel)){ctx.fillStyle='#b82428';ctx.beginPath();ctx.arc(w/2+v.LatAccel*r,h/2-v.LongAccel*r,6,0,2*Math.PI);ctx.fill();}
}
function draw(){if(page==='dashboard')drawTrend();if(page==='gnss'){const v=latest?.sample?.values;mapView.update(track,v&&Number.isFinite(v.Lat)&&Number.isFinite(v.Lon)?[v.Lon,v.Lat]:null);}if(page==='imu')drawG(latest?.sample?.values);if(page==='logs'&&solveTrack.length)drawTrack('solve-chart',solveTrack);}
window.addEventListener('resize',draw);
$('clear-track').onclick=()=>{track=[];draw();};
$('start-log').onclick=()=>action(async()=>{await api('/api/log/start','POST');message('UNO Qで記録を開始しました。');});
$('stop-log').onclick=()=>action(async()=>{await api('/api/log/stop','POST');message('記録を停止しました。Loggingからダウンロードできます。');});
$('refresh-logs').onclick=()=>action(loadLogs);
async function loadLogs(){
  try{const files=await api('/api/sd/logs');$('sd-log-list').replaceChildren();for(const f of files){const p=document.createElement('p');p.textContent=`EL${String(f.index).padStart(6,'0')}.BIN — ${bytes(f.size)} ${f.active?'記録中':''} `;if(!f.active){const a=document.createElement('a');a.href=`/api/sd/logs/${f.index}/download`;a.textContent='ダウンロード';a.download='';p.append(a);}$('sd-log-list').append(p);}}catch(e){$('sd-log-list').textContent=e.message;}
  const list=await api('/api/logs');$('log-list').replaceChildren();$('logs-empty').hidden=!!list.length;
  for(const log of list){
    const tr=document.createElement('tr');[log.name,bytes(log.size),log.active?'記録中':'保存済み'].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td);});
    const td=document.createElement('td'),row=document.createElement('div');row.className='button-row';
    if(!log.active){const a=document.createElement('a');a.href=`/api/logs/${encodeURIComponent(log.name)}/download`;a.textContent='CSV';a.download=log.name;row.append(a);
      const meta=document.createElement('a');meta.href=`/api/logs/${encodeURIComponent(log.name)}/metadata`;meta.textContent='メタデータ';meta.download=log.name+'.meta.json';row.append(meta);
      const solve=document.createElement('button');solve.textContent='解析';solve.onclick=()=>action(()=>solveLog(log));row.append(solve);
      const raw=document.createElement('a');raw.href=`/api/logs/${encodeURIComponent(log.name)}/can`;raw.textContent='CAN生データ';raw.download=log.name+'.can.jsonl';row.append(raw);
      const sd=document.createElement('button');sd.textContent='SDへコピー';sd.onclick=()=>action(async()=>{await api(`/api/logs/${encodeURIComponent(log.name)}/sd`,'POST');message('SDへのコピーを開始しました。診断欄で進捗を確認できます。');});row.append(sd);
      const del=document.createElement('button');del.textContent='削除';del.onclick=()=>{deleteTarget=log.name;$('delete-name').textContent=log.name;$('delete-dialog').showModal();};row.append(del);
    }else row.textContent='停止後に操作できます';td.append(row);tr.append(td);$('log-list').append(tr);
  }
}
$('cancel-delete').onclick=()=>$('delete-dialog').close();
$('confirm-delete').onclick=()=>action(async()=>{if(!deleteTarget)return;await api(`/api/logs/${encodeURIComponent(deleteTarget)}`,'DELETE');$('delete-dialog').close();deleteTarget=null;await loadLogs();});
async function solveLog(log){
  if(log.size>20*1024*1024)throw new Error('ブラウザ内解析は20 MiBまでです。CSVをダウンロードして解析してください。');
  const response=await fetch(`/api/logs/${encodeURIComponent(log.name)}/download`);if(!response.ok)throw new Error('ログを取得できませんでした');
  const text=await response.text(),lines=text.trim().split(/\r?\n/),head=lines.shift().split(','),idx=k=>head.indexOf(k);
  const data=lines.filter(Boolean).map(x=>x.split(','));if(!data.length)throw new Error('サンプルがありません');
  const speeds=data.filter(x=>x[idx('GPSSpeed')]).map(x=>Number(x[idx('GPSSpeed')]));const first=Number(data[0][idx('Distance')]),last=Number(data.at(-1)[idx('Distance')]);
  const seconds=(Date.parse(data.at(-1)[idx('host_utc')])-Date.parse(data[0][idx('host_utc')]))/1000;
  const stride=Math.max(1,Math.ceil(data.length/10000));solveTrack=data.filter((x,i)=>i%stride===0&&x[idx('Lon')]&&x[idx('Lat')]).map(x=>[Number(x[idx('Lon')]),Number(x[idx('Lat')])]);
  $('solve-panel').hidden=false;$('solve-name').textContent=log.name;
  $('solve-summary').textContent=`${data.length.toLocaleString()} 件 · ${elapsed(Math.max(0,seconds))} · 平均 ${format(speeds.reduce((a,b)=>a+b,0)/speeds.length,1)} km/h · 最高 ${format(speeds.reduce((a,b)=>Math.max(a,b),0),1)} km/h · 距離 ${last>=first?format(last-first,3)+' km':'MCU再起動のため計算不可'}`;draw();
}
function signalRow(signal={channel:1,name:'',unit:'',can_id:256,extended:false,byte_offset:0,data_type:'uint16',endian:'little',scale:1,offset:0}){
  const row=document.createElement('div');row.className='signal-row';
  const fields=[['channel','CAN系統',['1','2']],['name','信号名'],['unit','単位'],['can_id','CAN ID（16進）'],['extended','ID形式',['標準','拡張']],['byte_offset','バイト位置'],['data_type','データ型',['uint8','int8','uint16','int16','uint32','int32']],['endian','バイト順',['little','big']],['scale','倍率'],['offset','オフセット'],['bit_mask','ビットマスク（省略可）'],['conversion','換算',['linear','ntc']],['pullup_ohm','プルアップ抵抗Ω（サーミスタ）'],['ntc_points','校正値 温度℃:抵抗Ω（サーミスタ）']];
  for(const [key,label,options] of fields){const l=document.createElement('label');l.textContent=label;let input;
    if(options){input=document.createElement('select');options.forEach((v,i)=>{const o=document.createElement('option');o.value=key==='extended'?String(Boolean(i)):v;o.textContent=key==='conversion'?(v==='ntc'?'サーミスタ（比率→℃）':'直線（倍率・オフセット）'):v;input.append(o);});input.value=String(signal[key]??(key==='channel'?1:options[0]));input.required=true;}
    else{input=document.createElement('input');input.value=key==='can_id'?signal[key].toString(16).toUpperCase():key==='ntc_points'?(signal.ntc_points||[]).map(([t,r])=>`${t}:${r}`).join(', '):(signal[key]??'');
      if(key==='ntc_points')input.placeholder='例 20:12000, 60:2500, 100:680';
      if(['channel','scale','offset','byte_offset','bit_mask','pullup_ohm'].includes(key)){input.type='number';input.step=key==='byte_offset'?'1':'any';if(key==='byte_offset'){input.min='0';input.max='7';}}
      if(key==='can_id')input.pattern='(?:0[xX])?[0-9a-fA-F]{1,8}';
      if(key==='name'){input.pattern='[A-Za-z][A-Za-z0-9_]{0,31}';input.maxLength=32;}if(key==='unit')input.maxLength=16;input.required=!['unit','bit_mask','pullup_ohm','ntc_points'].includes(key);}
    input.dataset.field=key;l.append(input);row.append(l);
  }
  const remove=document.createElement('button');remove.type='button';remove.textContent='信号を削除';remove.className='remove-signal';remove.onclick=()=>row.remove();row.append(remove);$('signal-list').append(row);
}
// Sensor hub analog frame (sensorhub_generic_spec.md 4-2, draft): hub n ch k -> 0x500+n*0x10+(k-1),
// bytes 2-3 = ratio to the sensor 5 V (uint16, 0..65535). Calibration points are measured per sensor.
$('add-hub-oil').onclick=()=>{
  if([...document.querySelectorAll('.signal-row [data-field=name]')].some(x=>x.value==='OilTemp')){message('OilTempはすでにあります。');return;}
  signalRow({channel:2,name:'OilTemp',unit:'°C',can_id:0x500,extended:false,byte_offset:2,data_type:'uint16',endian:'little',scale:1/65535,offset:0,conversion:'ntc',pullup_ohm:null,ntc_points:[]});
  $('config-status').textContent='センサーハブ（ハブ0・ch1）の油温を追加しました。プルアップ抵抗値と校正値を入れて保存してください。';
};
$('add-signal').onclick=()=>{if($('signal-list').children.length>=64){message('信号は64個までです。');return;}signalRow();};
function loadConfig(){ $('config-auto-record').checked=config.auto_record!==false; $('config-name').value=config.device_name;$('config-profile').value=config.profile;$('config-bitrate').value=config.can_bitrate;$('signal-list').replaceChildren();config.signals.forEach(signalRow); }
$('config-form').onsubmit=event=>{event.preventDefault();action(async()=>{
  const signals=[...document.querySelectorAll('.signal-row')].map(row=>{const result={};row.querySelectorAll('[data-field]').forEach(input=>{const key=input.dataset.field;result[key]=(key==='bit_mask'||key==='pullup_ohm')&&!input.value?null:key==='ntc_points'?input.value.split(',').map(x=>x.trim()).filter(Boolean).map(x=>x.split(':').map(Number)):key==='can_id'?parseInt(input.value,16):key==='extended'?input.value==='true':['channel','scale','offset','byte_offset','bit_mask','pullup_ohm'].includes(key)?Number(input.value):input.value;});return result;});
  const value={schema:1,auto_record:$('config-auto-record').checked,device_name:$('config-name').value,profile:$('config-profile').value,can_bitrate:Number($('config-bitrate').value),signals};
  const result=await api('/api/config','POST',value);config=result.config;$('config-status').textContent='保存済み';message(result.message);document.dispatchEvent(new Event('ecocapture-config-saved'));
});};
async function boot(){
  try {
    [config,channels]=await Promise.all([api('/api/config'),api('/api/channels')]);loadConfig();
    readings('gnss-values',['Lat','Lon','GPSSpeed','Altitude','Yaw','GPSFix','GPSSats','GNSSHz']);
    readings('accel-values',['AccelX','AccelY','AccelZ','LongAccel','LatAccel','VertAccel']);
    readings('gyro-values',['GyroX','GyroY','GyroZ','Roll','Pitch']);message('');connect();openLinkedPage();
  } catch(error) {message('UNO Qへの接続を待っています。USB接続と起動状態を確認してください。');setTimeout(boot,2000);}
}
const mapView = new window.EcoMap();
boot();

$('load-ncec').onclick=()=>action(async()=>{
  const preset=await api('/api/can/ncec');
  config={...config,profile:preset.profile,can_bitrate:preset.can_bitrate,signals:preset.signals};loadConfig();
  $('config-status').textContent='NCEC定義を読み込みました。保存すると確定します。';
});
let ncecCsv='';
$('decode-ncec').onclick=()=>action(async()=>{
  $('download-ncec').disabled=true;ncecCsv='';$('ncec-rows').replaceChildren();
  const result=await api('/api/can/ncec/decode','POST',{text:$('ncec-input').value});
  const lines=['timestamp_ms,can_id,signal,value'];
  for(const frame of result.rows){
    for(const [signal,value] of Object.entries(frame.values)){
      const tr=document.createElement('tr');for(const text of [frame.timestamp_ms,frame.can_id,result.labels[signal]||signal,format(value,3)]){const td=document.createElement('td');td.textContent=text;tr.append(td);}$('ncec-rows').append(tr);
      lines.push([frame.timestamp_ms,frame.can_id,signal,value].join(','));
    }
    if(frame.counter_quality){lines.push([frame.timestamp_ms,frame.can_id,'Counter',frame.counter_quality.counter].join(','));if(frame.counter_quality.delta!==null)lines.push([frame.timestamp_ms,frame.can_id,'CounterDelta',frame.counter_quality.delta].join(','));}
  }
  $('ncec-result').textContent=`${result.rows.length}フレーム / カウンタ異常 ${result.counter_anomalies}件`;
  ncecCsv=lines.join('\r\n');$('download-ncec').disabled=lines.length<2;
});
$('download-ncec').onclick=()=>{const url=URL.createObjectURL(new Blob([ncecCsv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='ncec-decoded.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
