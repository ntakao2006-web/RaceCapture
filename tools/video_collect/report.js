// 「走行を見る」のレポートの下書き（SP-5-2、2026-11-14）。video_collect.html の $・esc・chip・lapTime・hhmm・mins と、
// 走行の行の下の欄（openLaps・lapsHtml・loadRuns）を使う。
// 走行記録から出した案（report_draft.py）を欄に入れて見せ、人が直して保存する（report_ops.py。置き場は drive_logs/reports/）。
let RP = null;   // いま開いている下書き：{id, d（/api/report の返事）}

const rpList = text => (text.match(/\d+/g) || []).map(Number);
function rpStints(race, pits) {   // report_ops.stints_of と同じ
  const out = []; let start = race[0];
  for (const n of [...new Set(pits)].sort((a, b) => a - b)) { out.push([start, n]); start = n + 1; }
  if (start <= race[1]) out.push([start, race[1]]);
  return out;
}
/** 欄に入れる最初の値：保存したものがあればそれ、無ければ案 */
function rpStart(d) {
  const a = d.draft.auto, s = d.saved;
  if (!s) return {name: '', race: a.race_laps || [], pits: a.pit_laps || [], drivers: [], window: a.window || ['', ''], notes: '', quali: null,
    slow: Object.fromEntries((a.slow_laps || []).map(n => [n, ''])), memo: {}, prePit: []};
  const slow = {};
  (a.slow_laps || []).forEach(n => { slow[n] = 'none'; });       // 案に出たが保存では外した周
  s.incident_laps.forEach(n => { slow[n] = 'incident'; });
  for (const [x, y] of s.slow_all_laps) for (let n = x; n <= y; n++) slow[n] = 'slow_all';
  const prePit = [];
  for (const [x, y] of s.pre_pit_slow) for (let n = x; n <= y; n++) { prePit.push(n); if (!(n in slow)) slow[n] = 'none'; }
  return {name: s.name, race: s.race_laps, pits: s.pit_laps, drivers: s.drivers || [], window: s.window, notes: s.notes, quali: s.quali, slow, memo: s.slow_memo || {}, prePit};
}
function rpForm(d) {
  const v = rpStart(d), a = d.draft.auto, times = Object.fromEntries(d.laps.map(l => [l.lap, l]));
  if (!d.laps.length) return `<div class="banner warn">${esc(d.draft.notes[0] || 'この走行には、タイムのある周がありません。')}</div>`;
  const reasons = n => `<select data-rp-slow="${n}"><option value="">理由を選ぶ…</option>${Object.entries(d.reasons).map(([k, t]) => `<option value="${k}" ${v.slow[n] === k ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>`;
  const slowRows = Object.keys(v.slow).map(Number).sort((x, y) => x - y).map(n => `<tr><td>${n}</td><td>${times[n] ? lapTime(times[n].time_s) : '—'}</td>
    <td>${reasons(n)}</td><td style="text-align:center"><input type="checkbox" data-rp-prepit="${n}" ${v.prePit.includes(n) ? 'checked' : ''} aria-label="${n}周目はピットの前にペースを落とした"></td><td><input type="text" data-rp-memo="${n}" value="${esc(v.memo[n] || '')}" placeholder="覚え書き（黄旗・1コーナーで飛び出した など）" style="width:100%"></td></tr>`).join('');
  const others = d.others.map(o => `<option value="${esc(o.id)}" ${v.quali && v.quali.id === o.id ? 'selected' : ''}>${hhmm(o.start)}から・${mins(o.minutes)}・${o.laps}周</option>`).join('');
  return `<div class="result plain" style="margin-top:4px">
    <b>レポートの下書き</b>　${d.saved ? chip('保存したものを開いています', 'ok') + ` <span class="sub">${esc(String(d.saved.saved_at).replace('T', ' ').slice(0, 16))}</span>` : chip('走行記録から出した案', 'warn')}
    <div class="sub" style="margin:4px 0">数字の欄は、走行記録から出した案です。合っているかを見て、違う所を直してから保存します。名前・理由・覚え書きは、記録からは分からないので入れてください（空でも保存できます）。</div>
    ${d.draft.notes.map(n => `<div class="sub">・${esc(n)}</div>`).join('')}
    <table style="margin-top:8px">
      <tr><th style="width:11em">大会の名前</th><td><input type="text" id="rp-name" value="${esc(v.name)}" placeholder="例：SUGO 120分耐久" style="width:100%"></td></tr>
      <tr><th>決勝の周</th><td><input class="num" id="rp-first" type="number" value="${v.race[0] ?? ''}"> 周目 から <input class="num" id="rp-last" type="number" value="${v.race[1] ?? ''}"> 周目 まで
        <span class="sub">（この走行の周は ${d.laps[0].lap}〜${d.laps[d.laps.length - 1].lap}。フォーメーションラップや、チェッカーのあとの周は外します）</span></td></tr>
      <tr><th>ピットに入った周</th><td><input type="text" id="rp-pits" value="${esc(v.pits.join(', '))}" placeholder="例：25, 38（無ければ空）" style="width:14em">
        <span class="sub">（案は、10秒以上止まっていた周です。ピットを出た周は、その次の周になります）</span></td></tr>
      <tr><th>スティント</th><td id="rp-stints"></td></tr>
      <tr><th>時刻の範囲</th><td><input class="num" id="rp-w0" type="text" value="${esc(v.window[0] || '')}" style="width:5.5em"> から <input class="num" id="rp-w1" type="text" value="${esc(v.window[1] || '')}" style="width:5.5em"> まで
        <span class="sub">（記録の欠けを数える範囲。案は、最初の周の5分前から最後の周の5分後）</span></td></tr>
      <tr><th>予選の走行</th><td><select id="rp-quali"><option value="">予選なし・この日のほかの走行ではない</option>${others}</select>
        <span id="rp-quali-laps" ${v.quali ? '' : 'hidden'}>　<input class="num" id="rp-q0" type="number" value="${v.quali ? v.quali.laps[0] : ''}"> 周目 から <input class="num" id="rp-q1" type="number" value="${v.quali ? v.quali.laps[1] : ''}"> 周目 まで</span></td></tr>
    </table>
    <div style="margin-top:10px"><b>遅い周</b> <span class="sub">案は、ピットの周とその次を除いて、そのスティントの中央値より6%以上遅い周です。理由は、乗った人・見ていた人が選びます。</span></div>
    ${slowRows ? `<div class="scroll"><table><tr><th>周</th><th>タイム</th><th>理由</th><th title="ピットに入る前の数周で、わざとペースを落としたとき（理由と両方に付けられます）">ピット前の<br>ペースダウン</th><th>覚え書き</th></tr>${slowRows}</table></div>` : '<div class="sub">遅い周の候補はありません。</div>'}
    <div class="row" style="margin-top:6px"><span class="sub">ほかの周を足す：</span><input class="num" id="rp-add" type="number" placeholder="周"><button id="rp-add-go">足す</button></div>
    <div style="margin-top:10px"><b>覚え書き</b> <span class="sub">（天気・路面・車の変更・起きたこと）</span></div>
    <textarea id="rp-notes" rows="4" style="width:100%;font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--text);box-sizing:border-box">${esc(v.notes)}</textarea>
    <div class="row" style="margin-top:8px"><button class="primary" id="rp-save">保存する</button>${d.saved ? '<button id="rp-redo">走行記録の案に戻す</button>' : ''}<button id="rp-close">閉じる</button></div>
    <div id="rp-out"></div>
    <div class="sub" style="margin-top:6px">保存先：${esc(d.file)}（人の名前や覚え書きが入るので、公開のリポジトリには入りません）。</div>
    <div style="margin-top:12px"><b>解析を流す</b> <span class="sub">保存した決めごとで、周・セクター・温度・油圧・走りの比べなどの表を作ります（数分かかります。走行記録と動画は変えません）。</span></div>
    <div class="row" style="margin-top:6px"><button id="rp-run" ${d.saved ? '' : 'disabled title="先に保存してください"'}>保存した決めごとで解析を流す</button>
      <button id="rp-view" ${d.has_results ? '' : 'disabled title="まだ解析を流していません"'}>結果を見る</button></div>
    <div id="rp-run-out"></div>
    <div id="rp-view-out"></div>
    <div class="sub" style="margin-top:6px">「結果を見る」は、数字とグラフをこの画面に出します（ネットにつながっていなくても見られます）。この解析はNCEC・SUGOの記録で作ったものなので、信号やセクターの数が違う車・コースでは、途中で止まることがあります。LTEの届き方の項目は出ません。</div>
  </div>`;
}
function rpShowStints() {
  const box = $('rp-stints'); if (!box) return;
  const race = [Number($('rp-first').value), Number($('rp-last').value)], pits = rpList($('rp-pits').value);
  if (!Number.isInteger(race[0]) || !Number.isInteger(race[1]) || race[0] > race[1] || !$('rp-first').value || !$('rp-last').value) { box.innerHTML = '<span class="sub">決勝の周を入れると出ます</span>'; return; }
  const stints = rpStints(race, pits.filter(n => n >= race[0] && n < race[1])), old = [...document.querySelectorAll('[data-rp-driver]')].map(i => i.value);
  const start = RP && RP.drivers ? RP.drivers : [];
  box.innerHTML = stints.map(([x, y], i) => `<div class="row" style="margin:2px 0"><span style="min-width:11em">${i + 1}：${x}〜${y}周目（${y - x + 1}周）</span>
    <input type="text" data-rp-driver="${i}" value="${esc(old[i] ?? start[i] ?? '')}" placeholder="ドライバー" style="width:12em;flex:0 1 auto"></div>`).join('')
    + '<div class="sub">スティントは、決勝の周とピットの周から決まります（ピットの周を直すと変わります）。</div>';
}
function rpBody() {
  const slow = {}, memo = {};
  document.querySelectorAll('[data-rp-slow]').forEach(s => { slow[s.dataset.rpSlow] = s.value; });
  document.querySelectorAll('[data-rp-memo]').forEach(i => { if (i.value.trim()) memo[i.dataset.rpMemo] = i.value; });
  const drivers = [...document.querySelectorAll('[data-rp-driver]')].map(i => i.value.trim());
  const prePit = [...document.querySelectorAll('[data-rp-prepit]')].filter(c => c.checked).map(c => Number(c.dataset.rpPrepit));
  const q = $('rp-quali').value;
  return {id: RP.id, name: $('rp-name').value, race_laps: [Number($('rp-first').value), Number($('rp-last').value)], pit_laps: rpList($('rp-pits').value),
    drivers: drivers.some(Boolean) ? drivers : [], slow, pre_pit: prePit, slow_memo: memo, window: [$('rp-w0').value.trim(), $('rp-w1').value.trim()], notes: $('rp-notes').value,
    quali: q ? {id: q, laps: [Number($('rp-q0').value), Number($('rp-q1').value)]} : null};
}
function rpDraw(d, fromDraft) {
  RP = {id: d.id, d, drivers: !fromDraft && d.saved ? d.saved.drivers : []};
  lapsHtml = rpForm(fromDraft ? {...d, saved: null} : d);
  const row = document.querySelector(`tr.lapsrow[data-for="${CSS.escape(d.id)}"] td`);
  if (row) row.innerHTML = lapsHtml;
  rpShowStints();
}
document.addEventListener('click', async e => {
  const open = e.target.closest('button[data-report]');
  if (open) {
    const id = open.dataset.report;
    openLaps = id; lapsHtml = '<div class="sub">走行記録から案を作っています…（初めて開く走行は、長さによって数十秒かかります）</div><div class="bar"><div class="busy"></div></div>';
    await loadRuns();
    try { const r = await fetch('/api/report?id=' + encodeURIComponent(id)), d = await r.json();
      if (openLaps !== id) return;
      if (!r.ok) { lapsHtml = `<div class="banner bad">${esc(d.error || '読めませんでした')}</div>`; loadRuns(); return; }
      rpDraw(d, false);
    } catch (x) { lapsHtml = '<div class="banner bad">読めませんでした（アプリが止まっていませんか）</div>'; loadRuns(); }
    return;
  }
  if (!RP) return;
  if (e.target.id === 'rp-close') { RP = null; openLaps = null; lapsHtml = ''; loadRuns(); return; }
  if (e.target.id === 'rp-redo') { rpDraw(RP.d, true); $('rp-out').innerHTML = '<div class="sub">走行記録の案に戻しました（まだ保存していません。保存したものは、保存するまで残っています）。</div>'; return; }
  if (e.target.id === 'rp-add-go') {
    const n = Number($('rp-add').value), lap = RP.d.laps.find(l => l.lap === n);
    if (!lap) { $('rp-out').innerHTML = '<div class="banner warn">その周は、この走行にありません。</div>'; return; }
    if (document.querySelector(`[data-rp-slow="${n}"]`)) { $('rp-out').innerHTML = '<div class="sub">その周は、もう表にあります。</div>'; return; }
    const keep = rpBody();          // 入れかけの欄を残したまま、1行足して描き直す
    const d = {...RP.d, saved: {name: keep.name, race_laps: keep.race_laps, pit_laps: keep.pit_laps, drivers: keep.drivers, window: keep.window, notes: keep.notes, quali: keep.quali,
      incident_laps: [], slow_all_laps: [], pre_pit_slow: keep.pre_pit.map(n => [n, n]), slow_memo: keep.slow_memo, saved_at: ''}};
    const was = RP.d; rpDraw(d, false); RP.d = was;
    Object.entries({...keep.slow, [n]: ''}).forEach(([k, val]) => { const s = document.querySelector(`[data-rp-slow="${k}"]`); if (s) s.value = val; });
    if (!document.querySelector(`[data-rp-slow="${n}"]`)) {   // 表に無い周は、行を足す
      const t = document.querySelector('[data-rp-slow]');
      const table = t ? t.closest('table') : null;
      const html = `<tr><td>${n}</td><td>${lapTime(lap.time_s)}</td><td><select data-rp-slow="${n}"><option value="">理由を選ぶ…</option>${Object.entries(RP.d.reasons).map(([k, x]) => `<option value="${k}">${esc(x)}</option>`).join('')}</select></td>
        <td style="text-align:center"><input type="checkbox" data-rp-prepit="${n}" aria-label="${n}周目はピットの前にペースを落とした"></td><td><input type="text" data-rp-memo="${n}" placeholder="覚え書き" style="width:100%"></td></tr>`;
      if (table) table.insertAdjacentHTML('beforeend', html);
      else $('rp-add').closest('.row').insertAdjacentHTML('beforebegin', `<div class="scroll"><table><tr><th>周</th><th>タイム</th><th>理由</th><th>ピット前の<br>ペースダウン</th><th>覚え書き</th></tr>${html}</table></div>`);
    }
    if (!was.saved) { const c = document.querySelector('.lapsrow .result .chip.ok'); if (c) c.outerHTML = chip('走行記録から出した案', 'warn'); }
    return;
  }
  if (e.target.id === 'rp-view') { showAnalysis(RP.id, $('rp-view-out')); return; }
  if (e.target.id === 'rp-run') {
    try {
      const r = await fetch('/api/report_run', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Video-Collect': '1'}, body: JSON.stringify({id: RP.id})}), x = await r.json();
      if (!r.ok) { $('rp-run-out').innerHTML = `<div class="banner bad"><b>流していません。</b>${esc(x.error || '')}</div>`; return; }
      rpRunShown = 0; if (window.load) load();
    } catch (x) { $('rp-run-out').innerHTML = '<div class="banner bad">始められませんでした（アプリが止まっていませんか）</div>'; }
    return;
  }
  if (e.target.id === 'rp-save') {
    const body = rpBody(), unset = Object.entries(body.slow).filter(([, val]) => !val).map(([k]) => k);
    if (unset.length) { $('rp-out').innerHTML = `<div class="banner warn">遅い周の理由が選ばれていません：${unset.join('・')}周目。分からなければ「遅い周に入れない」を選んでください。</div>`; return; }
    try {
      const r = await fetch('/api/report_save', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Video-Collect': '1'}, body: JSON.stringify(body)}), x = await r.json();
      if (!r.ok) { $('rp-out').innerHTML = `<div class="banner bad"><b>保存していません。</b><br>${esc(x.error || '').split(' ／ ').join('<br>')}</div>`; return; }
      RP.d = {...RP.d, saved: x.saved}; rpDraw(RP.d, false);
      $('rp-out').innerHTML = `<div class="result"><b>保存しました。</b>決勝 ${x.saved.race_laps[0]}〜${x.saved.race_laps[1]}周目・スティント ${x.saved.stints.length}つ・ピット ${x.saved.pit_laps.length}回。
        <div class="row" style="margin-top:6px"><button data-open="${esc(x.file.replace(/[\\/][^\\/]*$/, ''))}">置き場を開く</button></div></div>`;
    } catch (x) { $('rp-out').innerHTML = '<div class="banner bad">保存できませんでした（アプリが止まっていませんか）</div>'; }
  }
});
// 解析の様子：/api/state の analysis を見て出す（video_collect.html の render から呼ばれる）
let rpRunShown = 0;
function renderReportRun(s) {
  const a = s.analysis, box = $('rp-run-out'); if (!a || !box || !RP || a.run !== RP.id) return;
  if (a.running) { const t = Math.round(s.time - a.started);
    box.innerHTML = `<div class="sub" style="margin-top:6px">解析を流しています…（${Math.floor(t / 60)}分${String(t % 60).padStart(2, '0')}秒。初めての走行は、走行記録を読むので長くかかります）</div><div class="bar"><div class="busy"></div></div>`;
    rpRunShown = 0; return; }
  if (rpRunShown === a.started) return;
  rpRunShown = a.started;
  box.innerHTML = a.ok ? `<div class="result"><b>解析ができました。</b>表 ${a.tables.length} 個・数字 ${a.facts} 個（${Math.floor(a.seconds / 60)}分${String(a.seconds % 60).padStart(2, '0')}秒）
      <div class="notes">${esc(a.tables.join('・'))}</div><div class="row" style="margin-top:6px"><button id="rp-view-now">結果を見る</button><button data-open="${esc(a.pub)}">表の置き場を開く</button></div></div>`
    : `<div class="banner bad"><b>できませんでした。</b>${esc(a.error).split(' ／ ').join('<br>')}</div>`;
  if (a.ok) { RP.d = {...RP.d, has_results: true}; const v = $('rp-view'); if (v) { v.disabled = false; v.title = ''; }
    $('rp-view-now').onclick = () => showAnalysis(RP.id, $('rp-view-out')); }
}
document.addEventListener('input', e => { if (RP && ['rp-first', 'rp-last', 'rp-pits'].includes(e.target.id)) rpShowStints(); });
document.addEventListener('change', e => { if (RP && e.target.id === 'rp-quali') $('rp-quali-laps').hidden = !e.target.value; });
document.addEventListener('click', e => { if (e.target.closest('button[data-laps]')) RP = null; }, true);   // 「周を見る」へ切り替えたら下書きを閉じる
