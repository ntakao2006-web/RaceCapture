'use strict';
let deviceBusy=false,deviceNetworkTick=0,deviceWiFiBusy=false,wifiScanLoaded=false;
function deviceText(id,text){document.getElementById(id).textContent=text;}
function showNetwork(value){
  deviceText('wifi-state',value.addresses.length?`接続中：${value.connection} / ${value.addresses.join(', ')}`:`未接続 / ${value.state}`);
  const root=$('wifi-viewer-links');root.replaceChildren();
  if(value.viewer_urls.length){const p=document.createElement('p');p.textContent='同じWi-Fiから開く閲覧用サイト：';root.append(p);for(const url of value.viewer_urls){const a=document.createElement('a');a.href=url;a.textContent=url;a.target='_blank';a.rel='noopener noreferrer';root.append(a);}}
}
function showShare(value){
  const url=$('share-url');url.hidden=!value.url;$('share-copy').hidden=!value.url;url.textContent=value.url||'';if(value.url)url.href=value.url;else url.removeAttribute('href');
  deviceText('share-state',value.enabled?(value.url?'公開中':'公開用接続を準備中です。Wi-Fi接続を確認してください。'):'公開停止中');
  $('share-start').disabled=value.enabled;$('share-stop').disabled=!value.enabled;
}
async function refreshDevice(){
  if(page!=='settings'||$('device').hidden||document.hidden||deviceBusy)return;deviceBusy=true;
  try{
    const stats=await api('/api/device/system');
    if(stats.memory_total){deviceText('system-cpu',format(stats.cpu_percent,1));deviceText('system-memory',format(stats.memory_used/stats.memory_total*100,1));deviceText('system-temperature',format(stats.temperature_c,1));deviceText('system-disk',format(stats.disk_free/1073741824,1));deviceText('system-summary',`${stats.cpu_cores} コア / メモリ ${format(stats.memory_used/1048576,0)} / ${format(stats.memory_total/1048576,0)} MiB / Swap ${format(stats.swap_used/1048576,0)} MiB / 稼働 ${elapsed(stats.uptime_s)} / ${stats.process_count} プロセス`);
      $('system-processes').replaceChildren(...stats.processes.map(p=>{const row=document.createElement('tr');for(const v of [p.pid,p.name,format(p.cpu_percent,1),format(p.rss_bytes/1048576,1)]){const td=document.createElement('td');td.textContent=v;row.append(td);}return row;}));}
    deviceText('system-error','');
    if(performance.now()-deviceNetworkTick>6000){deviceNetworkTick=performance.now();const [wifi,share]=await Promise.all([api('/api/device/wifi'),api('/api/device/sharing')]);showNetwork(wifi);showShare(share);}
  }catch(error){deviceText('system-error',error.message);}finally{deviceBusy=false;}
}
function selectSettingsTab(uno){
  $('device').hidden=!uno;$('settings-can').hidden=uno;
  $('settings-uno-tab').setAttribute('aria-selected',String(uno));$('settings-can-tab').setAttribute('aria-selected',String(!uno));
  deviceNetworkTick=0;if(uno){refreshDevice();if(!wifiScanLoaded)scanWifi();}
}
$('settings-can-tab').onclick=()=>selectSettingsTab(false);
$('settings-uno-tab').onclick=()=>selectSettingsTab(true);
document.querySelector('[data-page="settings"]').addEventListener('click',()=>refreshDevice());
setInterval(refreshDevice,3000);
function wifiBusy(value){deviceWiFiBusy=value;for(const id of ['wifi-scan','wifi-connect','wifi-disconnect'])$(id).disabled=value;}
async function scanWifi(){
  if(deviceWiFiBusy)return;
  wifiBusy(true);const list=$('wifi-networks'),previous=list.value;list.disabled=true;
  $('wifi-scan').textContent='検索中…';deviceText('wifi-result','周囲のWi-Fiを検索しています…');
  try{
    const networks=await api('/api/device/wifi/scan','POST',{});
    if(!Array.isArray(networks))throw new Error('検索結果を取得できませんでした。再検索してください。');
    list.replaceChildren();const initial=document.createElement('option');initial.value='';initial.textContent=networks.length?'ネットワークを選択してください':'見つかりませんでした（SSIDを直接入力できます）';list.append(initial);
    for(const network of networks){
      const option=document.createElement('option');option.value=network.ssid;option.dataset.security=network.security||'';
      option.disabled=option.dataset.security.includes('802.1X');
      option.textContent=`${network.ssid}（${network.signal}% / ${option.disabled?'企業認証・未対応':network.security||'オープン'}）`;list.append(option);
    }
    if(networks.some(n=>n.ssid===previous))list.value=previous;
    wifiScanLoaded=true;deviceText('wifi-result',networks.length?`${networks.length} 件見つかりました。ネットワークを選び、パスワードを入力してください。`:'Wi-Fiが見つかりませんでした。再検索するかSSIDを直接入力してください。');
  }catch(error){deviceText('wifi-result',`検索できませんでした：${error.message} 再検索するかSSIDを直接入力してください。`);}
  finally{wifiBusy(false);list.disabled=list.options.length<2;$('wifi-scan').textContent='再検索';}
}
$('wifi-scan').onclick=scanWifi;
$('wifi-networks').onchange=()=>{
  const option=$('wifi-networks').selectedOptions[0];if(!option||!option.value)return;
  $('wifi-ssid').value=option.value;const security=option.dataset.security||'';
  $('wifi-security').value=security.includes('WPA3')&&!security.includes('WPA2')?'sae':security&&security!=='--'?'wpa-psk':'open';
  deviceText('wifi-result',`${option.value} を選択しました。${$('wifi-security').value==='open'?'接続して保存を押してください。':'パスワードを入力して接続してください。'}`);
};
$('wifi-form').onsubmit=async event=>{event.preventDefault();if(deviceWiFiBusy)return;wifiBusy(true);deviceText('wifi-result','接続しています…');const data={ssid:$('wifi-ssid').value,password:$('wifi-password').value,security:$('wifi-security').value};$('wifi-password').value='';try{const result=await api('/api/device/wifi/connect','POST',data);showNetwork(result.network);deviceText('wifi-result','接続して保存しました。次回から自動接続します。');}catch(error){deviceText('wifi-result',error.message);}finally{data.password='';wifiBusy(false);deviceNetworkTick=0;}};
$('wifi-disconnect').onclick=async()=>{if(deviceWiFiBusy)return;wifiBusy(true);try{showNetwork(await api('/api/device/wifi/disconnect','POST',{}));deviceText('wifi-result','Wi-Fiを切断しました。');}catch(error){deviceText('wifi-result',error.message);}finally{wifiBusy(false);}};
for(const [id,enabled] of [['share-start',true],['share-stop',false]])$(id).onclick=async()=>{$(id).disabled=true;try{showShare(await api('/api/device/sharing','POST',{enabled}));deviceNetworkTick=0;}catch(error){deviceText('share-state',error.message);$(id).disabled=false;}};
$('share-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('share-url').href);deviceText('share-state','リンクをコピーしました。');}catch{deviceText('share-state','リンクを選択してコピーしてください。');}};
