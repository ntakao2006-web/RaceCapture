'use strict';
let podiumLoaded=false,podiumTick=0,podiumBusy=false;
document.addEventListener('ecocapture-config-saved',()=>{podiumLoaded=false;});
function podiumState(s){
  $('podium-state').textContent=`${s.message}${s.link==='auto'&&s.active_link?`（自動：今は${s.active_link==='wifi'?'Wi-Fi':'LTE'}）`:''}${s.destination==='server'&&s.target&&s.target.count>1?`（送信先：${s.target.kind==='podium'?'Podiumへ直接':s.target.index===0?'主サーバー':`予備${s.target.index}`} ${s.target.host}）`:''} · 送信 ${s.frames} 件 / 再接続 ${s.reconnects} 回${s.last_sent_age_ms===null?'':` / 最終送信 ${s.last_sent_age_ms} ms前`}${s.voice==='on'?` · 音声受信中（${s.voice_packets} 件）`:s.voice==='paused'?` · 音声を一時停止中（テレメトリ優先・${s.voice_pauses} 回目）`:''}`;
}
async function loadPodium(){
  const data=await api('/api/podium'),c=data.config;podiumState(data.status);
  $('podium-apn').value=c.apn;$('podium-user').value=c.username;$('podium-host').value=c.host;$('podium-port').value=c.port;
  $('podium-hardware').checked=c.hardware_ready;document.querySelector(`input[name=podium-link][value=${c.link}]`).checked=true;document.querySelector(`input[name=podium-destination][value=${c.destination}]`).checked=true;$('podium-server-url').value=c.server_url;$('podium-backup-urls').value=(c.backup_server_urls||[]).join('\n');$('podium-fallback-direct').checked=!!c.fallback_direct;$('podium-voice').checked=!!c.voice_receive;$('podium-enabled').checked=c.enabled;
  $('podium-key').placeholder=c.key_configured?'保存済み / 空欄で変更しない':'Podiumの送信キー';
  $('podium-password').placeholder=c.password_configured?'保存済み / 空欄で変更しない':'APNパスワード（必要な場合）';
  $('podium-channels').replaceChildren(...data.channels.map(ch=>{const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=ch.name;box.checked=c.channels.includes(ch.name);label.append(box,` ${ch.label} (${ch.name})`);return label;}));
  podiumLoaded=true;
}
$('podium-form').onsubmit=event=>{event.preventDefault();action(async()=>{
  podiumBusy=true;
  const data={link:document.querySelector('input[name=podium-link]:checked').value,destination:document.querySelector('input[name=podium-destination]:checked').value,server_url:$('podium-server-url').value.trim(),backup_server_urls:$('podium-backup-urls').value.split('\n').map(x=>x.trim()).filter(Boolean),fallback_direct:$('podium-fallback-direct').checked,voice_receive:$('podium-voice').checked,enabled:$('podium-enabled').checked,hardware_ready:$('podium-hardware').checked,apn:$('podium-apn').value,username:$('podium-user').value,password:$('podium-password').value,device_id:$('podium-key').value,host:$('podium-host').value,port:Number($('podium-port').value),channels:[...$('podium-channels').querySelectorAll('input:checked')].map(x=>x.value)};
  $('podium-password').value='';$('podium-key').value='';
  try{await api('/api/podium','POST',data);await loadPodium();$('podium-result').textContent='送信設定を保存しました。';}
  finally{data.password='';data.device_id='';podiumBusy=false;}
});};
$('podium-stop').onclick=()=>action(async()=>{await api('/api/podium','POST',{enabled:false});await loadPodium();});
$('podium-check').onclick=()=>action(async()=>{
  $('podium-check').disabled=true;$('podium-result').textContent='LTEの電源と通信を点検しています…';
  try{const r=await api('/api/podium/check','POST',{});$('podium-result').textContent=`${r.model||'LTE'} / AT応答 ${r.at?'OK':'NG'} / 電波OFF ${r.rf_off?'OK':'NG'} / UART制御 ${r.flow_control?'OK':'NG'} / TCP ${r.tcp_commands?'コマンド一覧で確認':'SIM接続後に確認'} / 最後に電源OFF ${r.power_off?'OK':'未確認'}`;}
  finally{$('podium-check').disabled=false;}
});
setInterval(()=>{
  if(page!=='settings'||$('device').hidden||podiumBusy)return;
  if(!podiumLoaded){podiumBusy=true;loadPodium().catch(e=>{$('podium-result').textContent=e.message;}).finally(()=>{podiumBusy=false;});}
  else if(performance.now()-podiumTick>3000){podiumTick=performance.now();api('/api/podium').then(data=>podiumState(data.status)).catch(()=>{});}
},500);
