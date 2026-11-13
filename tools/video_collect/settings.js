// PCのアプリの「設定」の段（2026-11-13、SP-3-8。SPEC.md 4章 S-1、7-5）。
// video_collect.html のあとに読み込む（$・esc・chip・last・load を使う）。video_collect.py が /settings.js で配る。
//
// 焼き込みの見た目（計器の配置・レンズ・露出・音・針の補間）を、1画面で見る・変える・前へ戻す。
//   見る      本体のいまの中身は、段を開いたときと「読み直す」を押したときだけ読む（/api/op/set_read）。
//             読んだものは /api/state の now.settings に入っていて、画面はそこから描く
//   変える    どのボタンも、確認 → 送る → 同じバー → 本体から読み直した値、の順（サーバー側は settings_ops.py）
//   前へ戻す  送る前の値を本体に1つ控えてある。控えが無いときは、押したときにそう出る
// ボタンは押せなくしない。使えないときは、押したときに理由と直し方が出る（サーバーが返す）。

const ST = { shown: '', shownEnd: 0, pending: null, reading: false, phase: '' };
const ST_GROUPS = [
  ['hud', '計器の配置', '動画に焼き込む計器（メーター・数字・コース図）の並び。PCの hud.ini を書きかえて送ります。'],
  ['lens', 'レンズ', 'カメラの歪みの補正とズーム。PCの lens.json（道具で決めた値）を送ります。'],
  ['exposure', '露出（明るさ）', '明るさの決め方。明るい日に外が白く飛ぶときは「録画プログラムが決める」にします。'],
  ['audio', '音', 'カメラのマイクの音量と、低音カット・リミッター。'],
  ['smooth', '針の補間', '針やバーをなめらかに動かすための、値の待ち方と読む回数。'],
];
const ST_KEEP = '録画は止まりません。送る前の本体の値は、本体に1つ控えます（「前の値へ戻す」で戻せます）。';
const ST_SOON = '本体は約1秒で読み、次のコマから変わります。';
const ST_LATER = '<b>録画は止めません。効くのは、次に録画が始まったとき（本体の電源を入れ直したとき）からです。</b>いまの録画は、始まったときの値のままです。';

const stNote = (html, bad) => { $('st-out').innerHTML = html ? `<div class="opres ${bad ? 'bad' : ''}">${html}</div>` : ''; if (html) $('st-out').scrollIntoView({ block: 'nearest' }); };
const stList = lines => (lines || []).map(t => `<div${t.startsWith('★') ? ' style="color:var(--bad)"' : ''}>${esc(t)}</div>`).join('');
async function stCall(path, body = {}) {
  try {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Video-Collect': '1' }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    return { ...d, ok: r.ok, error: d.error || (r.ok ? '' : r.statusText) };
  } catch (x) { return { ok: false, error: 'アプリが止まっています（黒い窓を閉じましたか）' }; }
}

// ---------------------------------------------------------------- 読む
async function stRead(quiet) {
  if (ST.reading) return;
  ST.reading = true; $('st-when').textContent = '本体から読んでいます…（テザリングのときは数秒）';
  const r = await stCall('/api/op/set_read');
  ST.reading = false;
  if (!r.ok && !quiet) stNote('<b>いまは読めません。</b>' + esc(r.error), true);
  load();
}
window.settingsShown = () => stRead(true);   // 段を開いたとき
$('st-read').onclick = () => { stNote(''); stRead(false); };

// ---------------------------------------------------------------- 描く
function stButtons(g) {
  const b = (act, text, cls = '') => `<button data-st="${act}" class="${cls}">${text}</button>`, back = b(`restore:${g}`, '前の値へ戻す…');
  if (g === 'hud') return b('hud:send', 'PCの hud.ini を本体へ送る…', 'primary') + b('hud:default', '元の配置へ戻す…') + back + b('open:hud_preview', '計器の配置をPCで見る（別の窓）');
  if (g === 'lens') return b('lens:send', 'PCの lens.json を本体へ送る…', 'primary') + b('lens:off', '補正をやめる…') + back + b('open:lens_view', 'レンズをPCで見る（別の窓）') + b('open:lens_preview', 'レンズを本体のモニターで決める（別の窓）');
  if (g === 'exposure') return b('exposure:own', '録画プログラムが決める（白飛び対策）…') + b('exposure:camera', 'カメラ任せ…') + b('exposure:brighter', '明るく（目標 +15）…') + b('exposure:darker', '暗く（目標 −15）…') + back;
  return b(`${g}:write`, '本体へ書く…', 'primary') + back;
}
function stForm(g, dev) {
  const v = (dev && dev.values) || {};
  if (g === 'audio') return `<div class="kv" style="margin-top:8px">
      <label class="k" for="st-mic">マイクの音量</label><span class="row"><input class="in" id="st-mic" style="width:7em" value="${esc(v.mic_volume ?? '')}" placeholder="-15dB"><span class="sub">dBで（−95〜0。0が最大。割れるときは −21・−27 と下げる）</span></span>
      <label class="k" for="st-hpf">低音カット</label><span class="row"><input class="in" id="st-hpf" type="number" min="0" max="1000" style="width:7em" value="${esc(v.highpass_hz ?? '')}" placeholder="100"> Hz<span class="sub">（これより低い唸りを削る。0で削らない）</span></span>
      <label class="k" for="st-gain">録画で足す音量</label><span class="row"><input class="in" id="st-gain" type="number" min="-40" max="20" style="width:7em" value="${esc(v.gain_db ?? '')}" placeholder="0"> dB<span class="sub">（−40〜20。ふつうは0）</span></span>
      <label class="k" for="st-limit">リミッター</label><span class="row"><select class="in" id="st-limit"><option value="1">入（大きすぎる所だけ下げる）</option><option value="0"${v.limiter === '0' ? ' selected' : ''}>切</option></select></span>
    </div><div class="sub" style="margin-top:4px">値を変えた項目だけを書きます（ほかの項目・書いてあるメモはそのまま）。</div>`;
  if (g === 'smooth') return `<div class="kv" style="margin-top:8px">
      <label class="k" for="st-ms">値を待つ長さの上限</label><span class="row"><input class="in" id="st-ms" type="number" min="0" max="300" style="width:7em" value="${esc(v.smooth_ms ?? '')}" placeholder="150"> ミリ秒<span class="sub">（0〜300。既定150。0で補間しない。大きいと針が景色より遅れる）</span></span>
      <label class="k" for="st-hz">走行データを読む回数</label><span class="row"><input class="in" id="st-hz" type="number" min="1" max="100" style="width:7em" value="${esc(v.telemetry_hz ?? '')}" placeholder="25"> 回／秒<span class="sub">（1〜100。既定25。本体が重いときは10）</span></span>
    </div><div class="sub" style="margin-top:4px">値を変えた項目だけを書きます。</div>`;
  return '';
}
function stCards(v) {
  const d = v.device, pc = v.pc || {};
  return ST_GROUPS.map(([g, title, what]) => {
    const dev = d && d[g], mine = pc[g];
    let head = '';
    if (g === 'hud' && dev) head = dev.which === 'own' ? chip('自分の配置', 'info') : dev.which === 'default' ? chip('元の配置') : '';
    if (g === 'hud' && dev && dev.level && dev.level !== 'ok') head += ' ' + chip(dev.level === 'heavy' ? '重すぎる' : '重さぎりぎり', dev.level === 'heavy' ? 'bad' : 'warn');
    if (g === 'exposure' && dev && dev.mode) head = chip(dev.mode === 'camera' ? 'カメラ任せ' : '録画プログラムが決める', 'info');
    return `<div class="panel" id="st-card-${g}">
      <h2>${esc(title)} ${head}</h2><div class="sub">${esc(what)}</div>
      <div style="margin-top:8px"><b>本体のいま</b>${d ? '' : ' <span class="sub">' + esc(v.connected ? '読めませんでした' : '本体がつながっていないので読めません') + '</span>'}</div>
      ${dev ? `<div style="font-size:14px">${stList(dev.lines)}</div>` : ''}
      ${mine ? `<div style="margin-top:8px"><b>PCにある${g === 'hud' ? ' hud.ini' : ' lens.json'}</b>${mine.saved ? ` <span class="sub">${esc(mine.saved)}に保存</span>` : ''} ${mine.ok ? '' : chip('送れません', 'bad')}</div>
        <div style="font-size:14px">${stList(mine.lines)}</div><div class="sub" style="overflow-wrap:anywhere">${esc(mine.path)}</div>` : ''}
      ${stForm(g, dev)}
      <div class="row" style="margin-top:10px">${stButtons(g)}</div>
      <div class="sub" style="margin-top:6px">${dev ? esc(dev.prev || '控え：まだありません（このアプリから変えると、変える前の値を1つ残します）') : ''}</div>
    </div>`;
  }).join('');
}
function renderSettings(s) {
  const n = s.now; if (!n) return;
  const v = n.settings;
  // つながり方が変わったら、段が見えているときだけ1回読み直す（見張りのたびには読まない）
  if (ST.phase !== n.phase) { const first = ST.phase === ''; ST.phase = n.phase; if (!first && !$('tab-settings').hidden && (n.phase === 'connected' || n.phase === 'waiting')) stRead(true); }
  if (v && !ST.reading) $('st-when').textContent = `${Math.max(0, Math.round(s.time - v.read_at))}秒前に読んだ値です（自動では読み直しません）` + (v.device ? `　${v.via}・録画：${v.device.recording ? '録っている' : '止まっている（カメラ待ち等）'}` : '');
  $('st-unread').hidden = !(v && v.error); if (v && v.error) $('st-unread').textContent = v.error;
  if (v && ST.shown !== String(v.read_at)) { ST.shown = String(v.read_at); $('st-cards').innerHTML = stCards(v); }   // 入力中の欄を消さないよう、読み直したときだけ描く
  // 進み具合と結果（いまの様子の操作と同じバー。設定の操作のぶんだけ、この段に出す）
  const op = n.op, mine = op && op.kind === 'settings';
  $('st-run').hidden = !(mine && op.running);
  if (mine && op.running) {
    const t = Math.max(0, s.time - op.started);
    $('st-run-text').textContent = `${op.name}：${op.via}で本体へ送っています。本体の返事を待っています…（${Math.round(t)}秒／最大${op.seconds}秒）`;
    $('st-run-bar').style.width = Math.min(100, t / op.seconds * 100) + '%';
  }
  if (mine && !op.running && op.ended !== ST.shownEnd) {   // 終わった結果は1回だけ描く
    const old = ST.shownEnd === 0 && s.time - op.ended > 60; ST.shownEnd = op.ended;
    if (!old) stNote(`<b>${op.ok ? '終わりました' : 'できませんでした'}：${esc(op.name)}（${esc(op.via)}）</b><br>` + op.lines.map(esc).join('<br>'), !op.ok);
  }
}
window.renderSettings = renderSettings;

// ---------------------------------------------------------------- 変える（確認 → 送る → 同じバー → 読み直した値）
function stAsk(title, body, onSend) {
  ST.pending = onSend; stNote(''); $('stc-title').textContent = title; $('stc-body').innerHTML = body;
  $('st-confirm').hidden = false; $('st-confirm').scrollIntoView({ block: 'nearest' });
}
$('stc-cancel').onclick = () => { $('st-confirm').hidden = true; ST.pending = null; };
$('stc-send').onclick = () => { const go = ST.pending; ST.pending = null; $('st-confirm').hidden = true; if (go) go(); };
async function stPost(path, body) {
  $('st-confirm').hidden = true; stNote('');
  const r = await stCall(path, body);
  if (!r.ok) stNote('<b>いまは使えません。</b>' + esc(r.error), true);
  else if (r.opened) stNote(esc(r.opened));
  load();
}
const stView = () => (last && last.now && last.now.settings) || {};
// 欄のうち、読んだときの値から変えたものだけ（変えていない既定の値を、わざわざ本体のファイルへ書かない）。空の欄は送らない
function stChanged(g, values) { const was = ((stView().device || {})[g] || {}).values || {}; return Object.fromEntries(Object.entries(values).filter(([k, x]) => x !== '' && x !== String(was[k] ?? ''))); }
const stPcLines = g => { const p = (stView().pc || {})[g]; return p ? `<div style="margin:4px 0">PCのファイル：${stList(p.lines)}</div>` : ''; };
const ST_ASK = {
  'hud:send': () => ['PCの hud.ini を、本体へ送ります', stPcLines('hud') + ST_SOON + ST_KEEP + '<br>重すぎる配置・書き方の誤りがある配置は送りません。'],
  'hud:default': () => ['計器を、元の配置へ戻します', '本体にある自分の配置（hud.ini）を消して、はじめから入っている配置で描きます。' + ST_SOON + ST_KEEP],
  'lens:send': () => ['PCの lens.json を、本体へ送ります', stPcLines('lens') + ST_SOON + ST_KEEP],
  'lens:off': () => ['レンズの補正をやめます', '本体のレンズの値（lens.json）を消して、カメラの映像をそのまま録ります。' + ST_SOON + ST_KEEP],
  'exposure:own': () => ['露出を「録画プログラムが決める」にします', '窓の外の明るさを見て、録画プログラムが露出を決めます（白飛び対策）。' + ST_SOON + ST_KEEP],
  'exposure:camera': () => ['露出を「カメラ任せ」にします', 'カメラの自動の露出に戻します（明るい日は外が白く飛ぶことがあります）。' + ST_SOON + ST_KEEP],
  'exposure:brighter': () => ['露出の目標を、15だけ明るくします', '「録画プログラムが決める」のときの目標の明るさを上げます（カメラ任せのときは、一緒に「録画プログラムが決める」になります）。' + ST_SOON + ST_KEEP],
  'exposure:darker': () => ['露出の目標を、15だけ暗くします', '「録画プログラムが決める」のときの目標の明るさを下げます（カメラ任せのときは、一緒に「録画プログラムが決める」になります）。' + ST_SOON + ST_KEEP],
};
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-st]'); if (!b) return;
  const [kind, what] = b.dataset.st.split(':');
  if (kind === 'open') return stPost('/api/op/set_open', { tool: what });
  if (kind === 'restore') {
    const name = ST_GROUPS.find(x => x[0] === what)[1], dev = (stView().device || {})[what];
    if (!dev || !dev.prev) return stPost('/api/op/set_restore', { group: what });   // 控えが無い・読めていないときは、理由がそのまま出る
    const later = what === 'audio' || what === 'smooth';
    return stAsk(`${name}を、前の値へ戻します`, esc(dev.prev) + '<br>控えていた値を本体へ入れ直し、いまの値を代わりに控えます（もう一度押すと、戻す前に戻ります）。' + (later ? ST_LATER : '録画は止まりません。' + ST_SOON),
      () => stPost('/api/op/set_restore', { group: what }));
  }
  if (kind === 'audio') {
    const values = stChanged('audio', { mic_volume: $('st-mic').value.trim(), highpass_hz: $('st-hpf').value.trim(), gain_db: $('st-gain').value.trim(), limiter: $('st-limit').value });
    if (!Object.keys(values).length) return stNote('<b>変える値がありません。</b>欄の値を変えてから押してください。', true);
    const names = { mic_volume: 'マイクの音量', highpass_hz: '低音カット（Hz）', gain_db: '録画で足す音量（dB）', limiter: 'リミッター' };
    return stAsk('音の設定を、本体へ書きます', '変えるもの：' + Object.entries(values).map(([k, x]) => `${names[k]} → ${esc(k === 'limiter' ? (x === '0' ? '切' : '入') : x)}`).join('、') + '（ほかの項目はそのまま）<br>' + ST_LATER + '<br>変える前の値は、本体に1つ控えます。',
      () => stPost('/api/op/set_audio', { values }));
  }
  if (kind === 'smooth') {
    const values = stChanged('smooth', { smooth_ms: $('st-ms').value.trim(), telemetry_hz: $('st-hz').value.trim() });
    if (!Object.keys(values).length) return stNote('<b>変える値がありません。</b>欄の値を変えてから押してください。', true);
    const names = { smooth_ms: '値を待つ長さの上限（ミリ秒）', telemetry_hz: '走行データを読む回数（回／秒）' };
    return stAsk('針の補間の設定を、本体へ書きます', '変えるもの：' + Object.entries(values).map(([k, x]) => `${names[k]} → ${esc(x)}`).join('、') + '（ほかの項目はそのまま）<br>' + ST_LATER + '<br>変える前の値は、本体に1つ控えます。',
      () => stPost('/api/op/set_smooth', { values }));
  }
  const ask = ST_ASK[b.dataset.st]; if (!ask) return;
  const [title, body] = ask();
  stAsk(title, body, () => stPost(`/api/op/set_${kind}`, { what }));
});
if (last) renderSettings(last);
if (!$('tab-settings').hidden) stRead(true);   // はじめから「設定」の段で開いたとき
