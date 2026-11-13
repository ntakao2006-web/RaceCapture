// PCのアプリの「コースと線」の段（2026-11-13、SP-4-4・SP-4-10・SP-4-11。SPEC.md 4章 T-5、7-5）。
// video_collect.html のあとに読み込む（$・esc・chip・last・load を使う）。video_collect.py が /course_lines.js で配る。
//
// 線の図とエディターは、見本（docs/design/ecologger_app_mock.html）の作りをそのまま移したもの：
//   航空写真（国土地理院のタイル）の上に、線を本当の幅と向きで描く。写真が読めない所は、方眼の上に同じ縮尺で描く
//   線を足す・消す、役目（コントロールライン／スタート／ゴール／セクターの終わり）
//   動かし方は、つまむ（真ん中＝場所、端＝向きと幅）・北南東西へ1 cm／10 cm／1 m・数字で入れる・車のいまの位置を使う
//   写真の寄り引き（＋・−・ホイール・2本指）と移動、「線に合わせる」
//   入れる前に、変わる所を見せる。LTEのときとレーシングスピード以上のときは4桁の確認
// 見本と違う所：「数える向き（両方向）」は出さない（本体は矢印の向きに横切ったときだけ数える。両方向の仕組みは本体に無い）。
// 線は本体の lap.json の line と同じ平らな形（コントロールラインは直下、start・goal、sectors）で受け渡しし、
// エディターの中では1本ずつの並び [{kind, lat, lon, bearing, width}] で持つ（kind：c・st・go・s）。

const KIND = { c: ['コントロールライン', '#ef4444', '周を数える'], st: ['スタート', '#f59e0b', '最初の1回（スタートが別の場所のとき）'], go: ['ゴール', '#a855f7', '最後の1回（ゴールが別の場所のとき）'], s: ['セクターの終わり', '#38bdf8', '区間を分ける'] };
const RACE_KEYS = ['min_lap_s', 'max_lap_s', 'total_laps', 'time_limit_s', 'margin_s', 'pit_offset_m', 'pit_max_kmh'];   // 線のほかにコースの設定が持つ値
const HOME = { lat: 36, lon: 138 };   // 線もコースの設定も無いときに写真を開く場所（日本のまんなかあたり）
function nameLines(ls) { let n = 0; ls.forEach(l => { l.name = l.kind === 's' ? `セクター${++n}の終わり` : KIND[l.kind][0]; }); return ls; }
function flatToLines(line) {
  const out = [], g = (kind, x) => ({ kind, lat: x.lat, lon: x.lon, bearing: x.bearing ?? null, width: x.width_m ?? 30 });
  if (!line || !line.enabled || line.lat == null || line.lon == null) return out;
  out.push(g('c', line));
  if (line.start) out.push(g('st', line.start));
  if (line.goal) out.push(g('go', line.goal));
  (line.sectors || []).forEach(x => out.push(g('s', x)));
  return nameLines(out);
}
function linesToFlat(lines, extra) {
  const gate = l => ({ lat: l.lat, lon: l.lon, bearing: l.bearing, width_m: l.width }), one = k => lines.find(l => l.kind === k);
  return { ...(extra || {}), ...(one('c') ? gate(one('c')) : {}), start: one('st') ? gate(one('st')) : null, goal: one('go') ? gate(one('go')) : null, sectors: lines.filter(l => l.kind === 's').map(gate) };
}
const raceOf = line => Object.fromEntries(RACE_KEYS.filter(k => line && k in line).map(k => [k, line[k]]));
const degText = b => b == null ? '通ったときに覚える' : `${b}°`;

// ---------------------------------------------------------------- 図（航空写真の上に線を実寸で描く）
const TILE = (z, x, y) => `https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/${z}/${x}/${y}.jpg`;
function tileXY(lat, lon, z) { const n = 2 ** z, r = lat * Math.PI / 180; return [(lon + 180) / 360 * n, (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n]; }
function fromTile(x, y, z) { const n = 2 ** z; return { lon: x / n * 360 - 180, lat: Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI }; }
const mppAt = (lat, z) => 156543.03392 * Math.cos(lat * Math.PI / 180) / 2 ** z;
function drawMap(elId, noteId, lines, center, z, handle) {
  // 航空写真（国土地理院のタイル）を並べ、その上に線を実寸で描く。写真が読めない所では方眼の上に同じ縮尺で描く
  const el = $(elId), W = el.clientWidth || 640, H = el.clientHeight || 360;
  const tz = Math.min(Math.floor(z), 18), S = 256 * 2 ** (z - tz);   // 写真は18までしか無いので、それより寄るときは引き伸ばす
  const [cx, cy] = tileXY(center.lat, center.lon, tz), mpp = mppAt(center.lat, z);
  const key = [center.lat, center.lon, z, W, H].join(',');
  if (el.dataset.key !== key) {
    let html = '';
    for (let tx = Math.floor(cx - W / 2 / S); tx <= Math.floor(cx + W / 2 / S); tx++) for (let ty = Math.floor(cy - H / 2 / S); ty <= Math.floor(cy + H / 2 / S); ty++)
      html += `<img alt="" draggable="false" src="${TILE(tz, tx, ty)}" style="width:${S}px; height:${S}px; left:${Math.round((tx - cx) * S + W / 2)}px; top:${Math.round((ty - cy) * S + H / 2)}px" onerror="this.remove(); document.getElementById('${noteId}').hidden = false">`;
    if (!el.querySelector('svg')) el.innerHTML = '<div class="photo"></div><svg></svg><span class="credit">航空写真：国土地理院</span>';
    el.querySelector('.photo').innerHTML = html; el.querySelector('svg').setAttribute('viewBox', `0 0 ${W} ${H}`);
    el.dataset.key = key;
    $(noteId).hidden = true; $(noteId).textContent = '航空写真を読み込めない所があるので（ネットにつながっていない・その場所の写真が無い）、そこは方眼の上に同じ縮尺で描いています（線の位置・向き・幅は実寸）。';
  }
  el._view = { cx, cy, z: tz, S, W, H, mpp };
  let svg = '';
  lines.forEach((l, k) => {
    const [lx, ly] = tileXY(l.lat, l.lon, tz), x = (lx - cx) * S + W / 2, y = (ly - cy) * S + H / 2, half = Math.max(3, l.width / 2 / mpp);
    const col = KIND[l.kind][1], op = l.dim ? 0.45 : 1, label = `<text x="${x + 8}" y="${y - half - 6}" font-size="12" font-weight="700" fill="#fff" stroke="#000" stroke-width="3" paint-order="stroke">${esc(l.name)}</text>`;
    if (l.bearing == null) {   // 向きをまだ覚えていない線（本体は、通ったときの向きを覚える）：幅を直径とする円で描く
      svg += `<g opacity="${op}"><circle cx="${x}" cy="${y}" r="${half}" fill="none" stroke="#fff" stroke-width="7"/><circle cx="${x}" cy="${y}" r="${half}" fill="none" stroke="${col}" stroke-width="4" stroke-dasharray="8 6"/>${label}</g>`;
      if (handle === k) svg += [['b', x + half, y], ['c', x, y]].map(([h, hx, hy]) => grip(h, hx, hy)).join('');
      return;
    }
    const rad = l.bearing * Math.PI / 180, nx = Math.cos(rad), ny = Math.sin(rad), dx = Math.sin(rad), dy = -Math.cos(rad), arrow = Math.max(18, Math.min(60, 25 / mpp));
    svg += `<g opacity="${op}"><line x1="${x - nx * half}" y1="${y - ny * half}" x2="${x + nx * half}" y2="${y + ny * half}" stroke="#fff" stroke-width="7" stroke-linecap="round"/>`
      + `<line x1="${x - nx * half}" y1="${y - ny * half}" x2="${x + nx * half}" y2="${y + ny * half}" stroke="${col}" stroke-width="4" stroke-linecap="round"/>`
      + `<line x1="${x}" y1="${y}" x2="${x + dx * arrow}" y2="${y + dy * arrow}" stroke="#22c55e" stroke-width="3" marker-end="url(#ah)"/>${label}</g>`;
    if (handle === k) svg += [['a', x - nx * half, y - ny * half], ['b', x + nx * half, y + ny * half], ['c', x, y]].map(([h, hx, hy]) => grip(h, hx, hy)).join('');
  });
  const bar = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000].find(m => m / mpp >= 60) || 5000;
  svg += `<g><rect x="10" y="${H - 26}" width="${bar / mpp}" height="5" fill="#fff" stroke="#000"/><text x="10" y="${H - 30}" font-size="11" fill="#fff" stroke="#000" stroke-width="3" paint-order="stroke">${bar} m</text></g>`;
  el.querySelector('svg').innerHTML = svg;
}
const grip = (h, hx, hy) => `<circle data-h="${h}" cx="${hx}" cy="${hy}" r="${h === 'c' ? 9 : 7}" fill="${h === 'c' ? '#fde047' : '#fff'}" stroke="#000" stroke-width="2" style="cursor:${h === 'c' ? 'move' : 'grab'}; touch-action:none"/>`;

// ---------------------------------------------------------------- いまの車・コース、線の図
const LN = { src: null, srcSig: '', picked: false, view: 'all', drawn: '', shownEnd: 0, plan: null, code: '' };
let ed = null, edCenter = null, edZoom = null, edAuto = 18;   // ed：編集中の線の写し。edCenter：写真の真ん中。edZoom：人が決めた寄り方（null なら線の幅に合わせる）
const lnCourses = () => ((last && last.course && last.course.courses) || []).filter(c => c.line);
const lnCourse = id => lnCourses().find(c => c.id === id);
const lnDevice = () => last && last.course && last.course.device;
const lnSrcLine = () => LN.src === 'device' ? (lnDevice() || {}).line : (lnCourse(LN.src) || {}).line;
const clock = t => new Date(t * 1000).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
const lnNote = (html, bad) => { $('ln-out').innerHTML = html ? `<div class="opres ${bad ? 'bad' : ''}">${html}</div>` : ''; };
const lnMsg = (text, bad) => { $('ln-msg').textContent = text; $('ln-msg').style.color = bad ? 'var(--bad)' : ''; };
function lnRacing() {   // 確認を1つ増やす速さ：[km/h, どこから決めたか]
  const c = last && last.course, dev = lnDevice(), co = lnCourse(dev && dev.live && dev.match) || lnCourse(ed ? ed.course : LN.src);
  return co ? [co.racing_speed_kmh, `コースの設定「${co.id}」`] : [(c && c.default_racing_kmh) || 60, 'コースの設定が分からないときの目安'];
}
function lnHome() {   // 線が1本も無いときに写真を開く場所
  const ls = flatToLines(lnSrcLine()), co = lnCourses()[0];
  return ls.length ? { lat: ls[0].lat, lon: ls[0].lon } : co ? { lat: co.line.lat, lon: co.line.lon } : { ...HOME };
}
function fitZoom(lines, W, H) {   // 線がぜんぶ入る寄り方
  const lat = lines.reduce((a, l) => a + l.lat, 0) / lines.length, lon = lines.reduce((a, l) => a + l.lon, 0) / lines.length;
  const span = Math.max(...lines.map(l => Math.max(Math.abs(l.lat - lat) * 111320 * 2 / H, Math.abs(l.lon - lon) * 111320 * Math.cos(lat * Math.PI / 180) * 2 / W) + l.width / Math.min(W, H)));
  return [{ lat, lon }, [18, 17, 16, 15, 14, 13, 12].find(z => span / mppAt(lat, z) <= 0.8) || 12];
}
function drawNow(lines) {
  const el = $('ln-map'); $('ln-empty').hidden = lines.length > 0;
  if (!lines.length) return drawMap('ln-map', 'ln-map-note', [], lnHome(), 17);
  if (LN.view === 'all') { const [center, z] = fitZoom(lines, el.clientWidth || 640, el.clientHeight || 360); drawMap('ln-map', 'ln-map-note', lines, center, z); }
  else drawMap('ln-map', 'ln-map-note', lines.map((l, k) => k === LN.view ? l : { ...l, dim: true }), lines[LN.view], 18);
}
function renderLines(s) {
  const c = s.course; if (!c) return;
  const dev = c.device, courses = lnCourses();
  // 見る線：本体の線（読めていれば）と、PCにあるコースの設定
  const opts = [...(dev ? [['device', dev.live ? '本体のいまの線' : '最後に分かっている本体の線']] : []), ...courses.map(x => [x.id, `PCにある設定：${x.name}（${x.id}）`])];
  const sig = JSON.stringify(opts);
  if (sig !== LN.srcSig) {
    LN.srcSig = sig;
    if (!opts.some(o => o[0] === LN.src) || (dev && !LN.picked)) LN.src = opts.length ? opts[0][0] : null;
    $('ln-src').innerHTML = opts.length ? opts.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('') : '<option value="">（見られる線がありません）</option>';
    $('ln-src').value = LN.src ?? ''; LN.drawn = '';
  }
  // 車とコース
  const veh = dev && dev.vehicle, live = dev && dev.live, matched = live && lnCourse(dev.match), hasLine = live && flatToLines(dev.line).length > 0;
  const car = !c.connected ? '本体が読めていないので、分かりません' : !veh ? '本体が読んでいる信号を、PCにある車の設定と比べられませんでした'
    : veh.same ? `本体が読んでいる信号は、車の設定「${esc(veh.id)}」（${esc(veh.name)}）と同じです ${chip('同じ', 'ok')}`
    : `本体が読んでいる信号は、車の設定「${esc(veh.id)}」と違う所が ${veh.count} つあります ${chip('違う', 'warn')}<details><summary>違う所（はじめの${veh.diffs.length}つ）</summary>${veh.diffs.map(d => `<div class="sub">${esc(d)}</div>`).join('')}</details>`;
  const course = !live ? `本体の線は読めていません ${chip('分からない')}` : matched ? `<b>${esc(matched.name)}</b>（コースの設定「${esc(matched.id)}」と同じ線）${chip('設定と同じ', 'ok')}`
    : hasLine ? `<b>設定に無い線</b>（PCにあるどのコースの設定とも違います）${chip('設定に無い線', 'warn')}` : `<b>本体に線がありません</b>（ラップは数えません）${chip('線なし', 'bad')}`;
  const v = live ? dev.speed_kmh : null;
  $('ln-head').innerHTML = `<div>車：${car}</div><div class="sub">本体は車の名前を持っていないので、読んでいる信号を設定と比べています（車の切り替えは、ここではできません）。</div>
    <div style="margin-top:6px">コース：${course}</div>` + (live ? `<div class="sub">${v == null ? '車速は分かりません（測位していない・値が届いていない）。止まっているものとして扱います。' : `車速 ${Math.round(v)} km/h`}${dev.running ? '・いま1周を数えている途中' : ''}${dev.laps != null ? `・完了 ${esc(dev.laps)}周` : ''}</div>` : '');
  $('ln-unread').hidden = c.connected;
  if (!c.connected) $('ln-unread').textContent = '本体の線は読めていません（ロガーがUSB・テザリングでつながっていません）。PCにあるコースの設定を見ること・線の下書きはできます。本体へ入れるときは、LTEで送ります。'
    + (dev ? `「最後に分かっている本体の線」は、${clock(dev.read_at)} に${dev.sent ? 'LTEで送って、本体の返事と照らした線' : '本体から読んだ線'}です。` : '') + (c.error ? ` ${c.error}` : '');
  $('ln-chip').innerHTML = LN.src === 'device' ? (live ? chip(`本体から読んだ値（${Math.max(0, Math.round(s.time - dev.read_at))}秒前・${c.via}）`, 'ok') : chip(`最後に分かっている値（${clock(dev.read_at)}）`, 'warn'))
    : LN.src ? chip('PCにある設定（本体の線ではありません）', 'info') : '';
  const [limit, why] = lnRacing();
  $('ln-gate').textContent = ` 線はいつでも変えられます。LTEで送るときと、${limit} km/h 以上で走っているとき（${why}）は、送る前に確認の数字を入れる手順が1つ増えます。`;
  // 図と表（中身か大きさが変わったときだけ描き直す）
  const lines = flatToLines(lnSrcLine());
  if (typeof LN.view === 'number' && LN.view >= lines.length) LN.view = 'all';
  const key = JSON.stringify([LN.src, LN.view, lines, $('ln-map').clientWidth]);
  if (!$('tab-lines').hidden && key !== LN.drawn) {
    LN.drawn = key;
    $('ln-tabs').innerHTML = lines.length > 1 ? [['all', '全体'], ...lines.map((l, k) => [k, l.name])].map(([k, t]) => `<button class="${String(k) === String(LN.view) ? 'primary' : ''}" data-view="${k}">${esc(t)}</button>`).join('') : '';
    $('ln-table').querySelector('tbody').innerHTML = lines.map(l => `<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${KIND[l.kind][1]}"></span> ${esc(l.name)}</td><td>${KIND[l.kind][2]}</td><td>${l.lat.toFixed(7)}, ${l.lon.toFixed(7)}</td><td>${l.width} m</td><td>${degText(l.bearing)}</td></tr>`).join('');
    drawNow(lines);
  }
  $('ln-edit').textContent = lines.length ? '線を引き直す・足す…' : '1本目の線を引く…';
  $('ln-apply').hidden = !(LN.src && LN.src !== 'device') || !!ed;   // 下書きを開いている間は出さない（下書きを黙って捨てない）
  if (ed) edGate();
  // 進み具合と結果（いまの様子の操作と同じバー。線を入れる操作のぶんだけ、この段にも出す）
  const op = s.now && s.now.op, mine = op && op.kind === 'line';
  $('ln-run').hidden = !(mine && op.running);
  if (mine && op.running) {
    const t = Math.max(0, s.time - op.started);
    $('ln-run-text').textContent = `${op.name}：${op.via}で送りました。${op.via === 'LTE' ? 'ロガーの返事' : '本体の返事'}を待っています…（${Math.round(t)}秒／最大${op.seconds}秒）`;
    $('ln-run-bar').style.width = Math.min(100, t / op.seconds * 100) + '%';
  }
  if (mine && !op.running && op.ended !== LN.shownEnd) {   // 終わった結果は1回だけ描く
    const first = LN.shownEnd === 0 && s.time - op.ended > 60; LN.shownEnd = op.ended;
    if (!first) lnNote(`<b>${op.ok ? '終わりました' : 'できませんでした'}：${esc(op.name)}（${esc(op.via)}）</b><br>` + op.lines.map(esc).join('<br>'), !op.ok);
    if (op.ok && !first) {   // 入ったら、下書きを閉じて、本体から読み直した線を出す
      ed = null; $('ln-editor').hidden = true; $('ln-confirm').hidden = true; lnMsg('');
      if (lnDevice()) { LN.src = 'device'; LN.picked = false; $('ln-src').value = 'device'; }
      LN.view = 'all'; LN.drawn = ''; renderLines(s);
    }
  }
}
window.renderLines = renderLines;
window.linesShown = () => { LN.drawn = ''; if (last) renderLines(last); if (ed) edDraw(); };
window.addEventListener('resize', () => { if (!$('tab-lines').hidden) window.linesShown(); });
$('ln-src').addEventListener('change', () => { LN.src = $('ln-src').value || null; LN.picked = true; LN.view = 'all'; LN.drawn = ''; lnMsg(''); if (last) renderLines(last); });
$('ln-tabs').addEventListener('click', e => { const b = e.target.closest('button[data-view]'); if (!b) return; LN.view = b.dataset.view === 'all' ? 'all' : +b.dataset.view; if (last) renderLines(last); });

// ---------------------------------------------------------------- 線のエディター（見本のとおり）
function zText() { const v = $('ed-map-view')._view; $('ed-ztext').textContent = v ? `写真の横幅 約${Math.round(v.W * v.mpp)} m` : ''; }
const edCur = () => ed.lines[ed.i];
function edZoomBy(d) { edZoom = Math.max(14, Math.min(22, (edZoom ?? edAuto) + d)); edDraw(); }
function edRule() {   // 線のそろい方（本体と同じ）：コントロールラインが1本。スタートとゴールは、あれば1本ずつ。幅は5〜200 m
  const n = k => ed.lines.filter(l => l.kind === k).length;
  if (!ed.lines.length) return 'まだ線がありません。「線を足す」で1本目を引きます。';
  if (n('c') !== 1) return 'コントロールライン（周を数える線）が1本要ります。';
  if (n('st') > 1 || n('go') > 1) return 'スタートの線とゴールの線は、それぞれ1本までです。';
  if (n('s') > 9) return 'セクターの線は9本までです。';
  for (const l of ed.lines) {
    if (!(l.width >= 5 && l.width <= 200)) return `「${l.name}」の幅を、5〜200 m にしてください。`;
    if (l.bearing != null && !(l.bearing >= 0 && l.bearing < 360)) return `「${l.name}」の進む向きを、0〜359.5° にしてください。`;
    if (l.bearing == null && l.kind === 's') return `「${l.name}」に、進む向きを入れてください（セクターの線は、向きを自分で覚えません）。`;
    if (!(Math.abs(l.lat) <= 90 && Math.abs(l.lon) <= 180)) return `「${l.name}」の場所（緯度・経度）を確かめてください。`;
  }
  return '';
}
function edDraw() {
  $('ed-rule').textContent = edRule(); $('ed-rule').style.color = edRule() ? 'var(--bad)' : '';
  if (!ed.lines.length) { if (!edCenter) edCenter = lnHome(); drawMap('ed-map-view', 'ed-map-note', [], edCenter, edZoom ?? 18); edAuto = 18; return zText(); }
  if (!edCenter) edCenter = { lat: edCur().lat, lon: edCur().lon };
  // 線の端のつまみが写真からはみ出さない寄り方にする（幅が広い線ほど引いて見せる）
  const H = $('ed-map-view').clientHeight || 360, lat = edCur().lat, z = [20, 19, 18, 17].find(z => edCur().width / mppAt(lat, z) <= H * 0.7) || 17;
  edAuto = z; drawMap('ed-map-view', 'ed-map-note', ed.lines.map((l, k) => k === ed.i ? l : { ...l, dim: true }), edCenter, edZoom ?? z, ed.i); zText();
}
const edOptions = () => { $('ed-which').innerHTML = ed.lines.map((l, k) => `<option value="${k}">${esc(l.name)}</option>`).join(''); $('ed-which').value = ed.i; };
function edForm() {   // 入力欄を、選んでいる線の値にする
  const has = ed.lines.length > 0; nameLines(ed.lines); edOptions();
  ['ed-which', 'ed-del', 'ed-kind', 'ed-lat', 'ed-lon', 'ed-bearing', 'ed-bearing-n', 'ed-width', 'ed-width-n', 'ed-step'].forEach(id => $(id).disabled = !has);
  $('ed-nudge').querySelectorAll('button').forEach(b => b.disabled = !has);
  if (!has) return;
  const l = edCur(); $('ed-kind').value = l.kind;
  $('ed-lat').value = l.lat.toFixed(7); $('ed-lon').value = l.lon.toFixed(7);
  $('ed-bearing').value = l.bearing ?? 0; $('ed-bearing-n').value = l.bearing ?? ''; $('ed-width').value = $('ed-width-n').value = l.width;
}
function edSync() {   // 入力欄の値を、選んでいる線へ入れて描き直す
  if (ed.lines.length) { const l = edCur(), kind = l.kind, num = id => $(id).value.trim() === '' ? NaN : +$(id).value;
    // 場所は、欄の字が変わったときだけ入れる（読んだ値を、欄の7桁に丸め直さない）
    if ($('ed-lat').value !== l.lat.toFixed(7) && isFinite(num('ed-lat'))) l.lat = num('ed-lat');
    if ($('ed-lon').value !== l.lon.toFixed(7) && isFinite(num('ed-lon'))) l.lon = num('ed-lon');
    l.bearing = isFinite(num('ed-bearing-n')) ? num('ed-bearing-n') : null;
    if (isFinite(num('ed-width-n'))) l.width = num('ed-width-n');
    l.kind = $('ed-kind').value;
    if (kind !== l.kind) { nameLines(ed.lines); edOptions(); } }
  edDraw();
}
function edMove(north_m, east_m) {   // 北・東へ何メートル動かすか
  const l = edCur();
  l.lat += north_m / 111320; l.lon += east_m / (111320 * Math.cos(l.lat * Math.PI / 180));
  $('ed-lat').value = l.lat.toFixed(7); $('ed-lon').value = l.lon.toFixed(7); edDraw();
}
$('ed-nudge').addEventListener('click', e => { const b = e.target.closest('button[data-n]'); if (!b || !ed) return; const m = +$('ed-step').value; edMove(+b.dataset.n * m, +b.dataset.e * m);
  lnMsg(`${b.textContent.trim()}へ ${$('ed-step').selectedOptions[0].textContent} 動かしました。`); });
(() => {   // つまんで動かす：真ん中の丸＝場所、端の丸＝向きと幅
  const el = $('ed-map-view'); let grip = null;
  const at = e => { const r = el.getBoundingClientRect(), v = el._view; return [(e.clientX - r.left) * v.W / r.width, (e.clientY - r.top) * v.H / r.height]; };
  let pan = null;
  el.addEventListener('pointerdown', e => { if (!ed || !el._view) return; const h = e.target.dataset && e.target.dataset.h, v = el._view; grip = h || 'pan'; if (!h) pan = { x: e.clientX, y: e.clientY, cx: v.cx, cy: v.cy, k: v.W / el.getBoundingClientRect().width }; try { el.setPointerCapture(e.pointerId); } catch (x) {} e.preventDefault(); });
  el.addEventListener('wheel', e => { if (!ed) return; e.preventDefault(); edZoomBy(e.deltaY < 0 ? 1 : -1); }, { passive: false });
  el.addEventListener('pointermove', e => {
    if (!grip || !ed) return; const v = el._view, [px, py] = at(e);
    if (grip === 'pan') { edCenter = fromTile(pan.cx - (e.clientX - pan.x) * pan.k / v.S, pan.cy - (e.clientY - pan.y) * pan.k / v.S, v.z); return edDraw(); }
    if (grip === 'c') { const g = fromTile(v.cx + (px - v.W / 2) / v.S, v.cy + (py - v.H / 2) / v.S, v.z); $('ed-lat').value = g.lat.toFixed(7); $('ed-lon').value = g.lon.toFixed(7); }
    else {
      const [lx, ly] = tileXY(edCur().lat, edCur().lon, v.z), x = (lx - v.cx) * v.S + v.W / 2, y = (ly - v.cy) * v.S + v.H / 2;
      let vx = px - x, vy = py - y; if (grip === 'a') { vx = -vx; vy = -vy; }
      const len = Math.hypot(vx, vy); if (len < 2) return;
      const bearing = Math.round(((Math.atan2(vy, vx) * 180 / Math.PI + 360) % 360) * 2) / 2 % 360, width = Math.max(5, Math.min(200, Math.round(len * 2 * v.mpp)));
      $('ed-bearing').value = $('ed-bearing-n').value = bearing; $('ed-width').value = $('ed-width-n').value = width;
    }
    edSync();
  });
  const end = () => { if (grip && grip !== 'pan') lnMsg('つまんで動かしました。数字も同じ値に変わっています。'); grip = null; };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
})();
(() => {   // 2本指でつまんで寄り引き（指の間が広がると寄る）。つまんでいる間は、線も写真も動かさない
  const el = $('ed-map-view'), pts = new Map(); let pinch = null, block = false;
  const dist = () => { const [a, b] = [...pts.values()]; return Math.hypot(a.x - b.x, a.y - b.y); };
  el.addEventListener('pointerdown', e => { pts.set(e.pointerId, { x: e.clientX, y: e.clientY }); try { el.setPointerCapture(e.pointerId); } catch (x) {} if (pts.size === 2) { pinch = { d: dist(), z: edZoom ?? edAuto }; block = true; e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  el.addEventListener('pointermove', e => { if (pts.has(e.pointerId)) pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pts.size === 2 && ed) { const d = dist(); if (d > 10 && pinch.d > 10) { edZoom = Math.max(14, Math.min(22, pinch.z + Math.log2(d / pinch.d))); edDraw(); } }
    if (block) { e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  const up = e => { pts.delete(e.pointerId); if (pts.size < 2) pinch = null; if (pts.size === 0) block = false; };
  el.addEventListener('pointerup', up, true); el.addEventListener('pointercancel', up, true);
})();
[['ed-bearing', 'ed-bearing-n'], ['ed-width', 'ed-width-n']].forEach(([a, b]) => {
  $(a).addEventListener('input', () => { $(b).value = $(a).value; edSync(); });
  $(b).addEventListener('input', () => { if ($(b).value !== '') $(a).value = $(b).value; edSync(); }); });
['ed-lat', 'ed-lon'].forEach(id => $(id).addEventListener('change', () => { edCenter = null; edSync(); }));
$('ed-kind').addEventListener('change', edSync);
$('ed-zin').onclick = () => edZoomBy(1); $('ed-zout').onclick = () => edZoomBy(-1); $('ed-zfit').onclick = () => { edZoom = null; edCenter = null; edDraw(); };
$('ed-which').addEventListener('change', () => { ed.i = +$('ed-which').value; edCenter = null; edForm(); edDraw(); });
$('ed-add').onclick = () => {
  const has = k => ed.lines.some(l => l.kind === k), kind = !has('c') ? 'c' : has('st') && !has('go') ? 'go' : 's';
  const at = edCenter || lnHome();   // いま見ている写真の真ん中に置く
  ed.lines.push({ kind, lat: at.lat + (ed.lines.length ? 0.00008 : 0), lon: at.lon + (ed.lines.length ? 0.00010 : 0), bearing: ed.lines.length ? (edCur().bearing ?? 0) : 0, width: 30 });
  ed.i = ed.lines.length - 1; edCenter = null; edForm(); edDraw();
  lnMsg(`「${edCur().name}」を、見ている写真の真ん中あたりに足しました。つまむか、数字で、場所・向き・幅を決めます。役目は下で変えられます。`);
};
$('ed-del').onclick = () => { if (!ed.lines.length) return; const name = edCur().name; ed.lines.splice(ed.i, 1); ed.i = Math.max(0, ed.i - 1); edCenter = null; edForm(); edDraw(); lnMsg(`「${name}」を消しました（本体へ入れるまでは、本体の線は変わりません）。`); };
function edGate() {   // LTEで送る・レーシングスピード以上のときは、確認が1つ増えることを先に出す
  const c = last && last.course, dev = lnDevice(), v = c && c.connected && dev ? dev.speed_kmh : null, [limit] = lnRacing(), fast = v != null && v >= limit;
  $('ed-lte').hidden = !!(c && c.connected) && !fast;
  $('ed-lte').textContent = fast ? `いまレーシングスピードで走っています（${Math.round(v)} km/h）。変えられますが、送る前に変わる所を見せて、4桁の数字を入れてもらいます。`
    : 'LTEで送ります。USB・テザリングより確認が1つ多く、送る前に変わる所を見せて、4桁の数字を入れてもらいます。走っている途中で変えたときは、新しい線を次に通った所からラップを数え直します。';
}
$('ln-edit').onclick = () => {
  const co = LN.src !== 'device' ? lnCourse(LN.src) : null, line = lnSrcLine();
  lnNote(''); lnMsg(''); $('ln-confirm').hidden = true;
  // 下書きの元：PCの設定から始めたときは、その設定の「線のほかの値」（1周の最短など）も一緒に送る。本体の線から始めたときは線だけ
  ed = { lines: flatToLines(line), i: LN.view === 'all' ? 0 : LN.view, course: co ? co.id : null, extra: co ? raceOf(co.line) : {} };
  edCenter = null; edZoom = null;
  $('ed-base').textContent = co ? `（元：PCにある設定「${co.id}」。本体へ入れるまでは下書きです）` : LN.src === 'device' ? '（元：本体の線。本体へ入れるまでは下書きです）' : '（新しく引きます。本体へ入れるまでは下書きです）';
  $('ln-editor').hidden = false; edGate(); edForm(); edDraw();
  const dev = lnDevice(), v = last && last.course && last.course.connected && dev ? dev.speed_kmh : null;
  if (v != null && v >= 1 && v < lnRacing()[0]) lnMsg(`車は動いています（${Math.round(v)} km/h）。`);
};
$('ed-cancel').onclick = () => { ed = null; $('ln-editor').hidden = true; $('ln-confirm').hidden = true; lnMsg('やめました。本体の線は変わっていません。'); };
$('ed-here').onclick = async () => {
  const r = await lnCall('/api/op/car_here');
  if (!r.ok) return lnMsg('いまは使えません。' + (r.error || ''), true);
  if (!ed.lines.length) $('ed-add').click();
  const moving = r.yaw != null && r.speed_kmh != null && r.speed_kmh >= 5;
  $('ed-lat').value = r.lat.toFixed(7); $('ed-lon').value = r.lon.toFixed(7);
  if (moving) $('ed-bearing').value = $('ed-bearing-n').value = Math.round(r.yaw * 2) / 2 % 360;
  edCenter = null; edSync();
  lnMsg(`車のいまの位置${r.hacc_m != null ? `（誤差 ${r.hacc_m.toFixed(1)} m）` : ''}を入れました。` + (moving ? `向きは、いま走っている向き（${Math.round(r.yaw * 2) / 2}°）にしました。` : '止まっているので、向きは変えていません（向きは走っているときにしか分かりません）。'));
};

// ---------------------------------------------------------------- 本体へ入れる（変わる所を見せる → 要るときは4桁 → 送る → 読み直した値）
async function lnCall(path, body = {}) {
  try {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Video-Collect': '1' }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    return { ...d, ok: r.ok, error: d.error || (r.ok ? '' : r.statusText) };
  } catch (x) { return { ok: false, error: 'アプリが止まっています（黒い窓を閉じましたか）' }; }
}
async function lnPlan(line, course) {
  lnNote(''); $('ln-confirm').hidden = true;
  const r = await lnCall('/api/op/line_plan', { line, course });
  if (!r.ok) return lnNote('<b>いまは使えません。</b>' + esc(r.error), true);
  if (r.problems) return lnNote(`<b>入れていません。線の形がおかしい所があります。</b><ul>${r.problems.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`, true);
  LN.plan = { line, course, byName: r.by_name };
  LN.code = r.need_code ? String(1000 + Math.floor(Math.random() * 9000)) : '';
  $('lnc-title').textContent = r.title;
  $('lnc-diff').innerHTML = `<ul>${r.changes.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` + r.notes.map(n => `<div style="font-size:13px; margin-top:2px">${esc(n)}</div>`).join('');
  $('lnc-code-row').hidden = !r.need_code; $('lnc-code').textContent = LN.code; $('lnc-input').value = ''; $('lnc-msg').textContent = '';
  $('lnc-send').textContent = r.direct ? '本体へ入れる' : '送る（線まるごと）';
  $('lnc-name').hidden = !r.by_name; $('lnc-name').textContent = r.by_name ? `名前だけ送る（本体に入れてある設定「${r.by_name}」を選ぶ）` : '';
  $('ln-confirm').hidden = false; $('ln-confirm').scrollIntoView({ block: 'nearest' }); if (r.need_code) $('lnc-input').focus();
}
async function lnSend(byName) {
  if (LN.code && $('lnc-input').value.trim() !== LN.code) { $('lnc-msg').textContent = '数字が違います。上の4桁をそのまま入れてください。'; return; }
  const p = LN.plan; if (!p) return;
  $('ln-confirm').hidden = true;
  const r = await lnCall('/api/op/line_set', { line: p.line, course: p.course, confirmed: !!LN.code, by_name: byName ? p.byName : null });
  if (!r.ok) lnNote('<b>いまは使えません。</b>' + esc(r.error), true);
  load();
}
$('ed-apply').onclick = () => { edSync(); const bad = edRule(); if (bad) return lnMsg('入れていません。' + bad, true); lnMsg(''); lnPlan(linesToFlat(ed.lines, ed.extra), ed.course); };
$('ln-apply').onclick = () => { const co = lnCourse(LN.src); if (!co || ed) return; lnMsg(''); lnPlan(linesToFlat(flatToLines(co.line), raceOf(co.line)), co.id); };
$('lnc-send').onclick = () => lnSend(false);
$('lnc-name').onclick = () => lnSend(true);
$('lnc-back').onclick = () => { $('ln-confirm').hidden = true; };
$('lnc-input').addEventListener('keydown', e => { if (e.key === 'Enter') $('lnc-send').click(); });
