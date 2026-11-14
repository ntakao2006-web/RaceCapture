// 解析の結果を、アプリの中で見る（SP-5-2、2026-11-14）。video_collect.html の $・esc・chip を使う。
// 解析（tools/race_analysis/race_analysis.py）が出した表（drive_logs/reports/<走行のid>/pub/*.csv）を /api/report_data で読み、
// 大会によらない形で出す：主な数字・周ごとのタイム・周の一覧・温度・コースと速度・ベストとの差・数字の一覧。
// 外のライブラリは使わない（ネットにつながっていなくても見られるように、グラフは自前のSVG）。
// 大会ごとの文章つきのページ（tools/race_analysis/report_page.html）とは別物で、こちらは数字とグラフだけ。
const AV_COLORS = ['#4f8cff', '#e08a2e', '#2a9d5c', '#b07cf0', '#d9534f', '#3bb8c4'];
const AV_KIND = {'通常': '#4f8cff', '一か所で減速': '#d9534f', '全体に遅い': '#e08a2e', '予選': '#b07cf0'};   // ほかは灰色
const avNum = v => (v === '' || v == null) ? NaN : Number(v);
const avMmss = s => Number.isFinite(s) ? `${Math.floor(s / 60)}:${(s % 60).toFixed(3).padStart(6, '0')}` : '—';

/** グラフの枠。{svg を作る文字列の部品, x(), y()} を返す。xs・ys は [最小, 最大] */
function avFrame(xs, ys, opt) {
  const W = 760, H = opt.h || 260, m = {l: 52, r: 14, t: 10, b: 30}, iw = W - m.l - m.r, ih = H - m.t - m.b;
  const x = v => m.l + (v - xs[0]) / ((xs[1] - xs[0]) || 1) * iw, y = v => m.t + ih - (v - ys[0]) / ((ys[1] - ys[0]) || 1) * ih;
  const ticks = (a, b, n) => { const span = (b - a) || 1, step0 = Math.pow(10, Math.floor(Math.log10(span / n))), step = [1, 2, 5, 10].map(k => k * step0).find(s => span / s <= n) || step0 * 10;
    const out = []; for (let v = Math.ceil(a / step) * step; v <= b + step * 1e-6; v += step) out.push(Math.round(v / step) * step); return out; };
  const fx = opt.fx || (v => String(Math.round(v * 100) / 100)), fy = opt.fy || (v => String(Math.round(v * 100) / 100));
  let g = '';
  for (const v of ticks(ys[0], ys[1], 5)) g += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-width="1"/><text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${esc(fy(v))}</text>`;
  for (const v of (opt.xticks || ticks(xs[0], xs[1], 8))) g += `<text x="${x(v)}" y="${H - 10}" text-anchor="middle">${esc(fx(v))}</text>`;
  if (opt.ylabel) g += `<text x="${m.l}" y="${m.t + 2}" text-anchor="start" dominant-baseline="hanging" opacity=".8">${esc(opt.ylabel)}</text>`;
  return {W, H, m, iw, ih, x, y, g, wrap: inner => `<div class="scroll"><svg viewBox="0 0 ${W} ${H}" style="width:100%;min-width:520px;height:auto;font-size:11px;fill:var(--muted)" role="img" aria-label="${esc(opt.label || '')}">${g}${inner}</svg></div>`};
}
const avPath = (pts, x, y) => pts.filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1])).map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
const avLegend = items => `<div class="row" style="gap:12px;margin-top:2px">${items.map(([c, t]) => `<span class="sub"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c};margin-right:4px"></span>${esc(t)}</span>`).join('')}</div>`;
const avSection = (title, note, body) => `<div style="margin-top:16px"><b>${esc(title)}</b>${note ? ` <span class="sub">${esc(note)}</span>` : ''}${body}</div>`;

function avTiles(F) {
  const f = k => F[k] ? F[k].text : null;
  const tiles = [['決勝のベスト', f('best_lap'), f('best_lap_no') ? `${f('best_lap_no')}周目` : ''], ['予選のベスト', f('q_best'), f('q_best_no') ? `予選の${f('q_best_no')}周目` : ''],
    ['セクターのベストの和', f('theo_best'), f('theo_gap') ? `ベストより${f('theo_gap')}秒速い` : ''], ['決勝で走った周', f('race_laps') ? f('race_laps') + ' 周' : null, f('race_start') && f('race_finish') ? `${f('race_start')}〜${f('race_finish')}` : ''],
    ['油温の最高（決勝）', f('oil_race_max') ? f('oil_race_max') + '℃' : null, '']].filter(t => t[1]);
  return `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:8px">${tiles.map(([a, b, c]) =>
    `<div style="border:1px solid var(--line);border-radius:8px;padding:8px 10px"><div class="sub">${esc(a)}</div><div style="font-size:22px;font-weight:600">${esc(b)}</div><div class="sub">${esc(c)}</div></div>`).join('')}</div>`;
}
function avLapChart(laps) {
  const L = laps.filter(r => r.session === '決勝').map(r => ({lap: avNum(r.lap), t: avNum(r.lap_s), kind: r.kind, stint: r.stint})).filter(d => Number.isFinite(d.t));
  if (!L.length) return '';
  const sorted = L.map(d => d.t).sort((a, b) => a - b), med = sorted[Math.floor(sorted.length / 2)], ymax = med * 1.25, ymin = sorted[0] - 1;
  const F = avFrame([L[0].lap - 0.6, L[L.length - 1].lap + 0.6], [ymin, ymax], {h: 280, fy: v => avMmss(v).slice(0, -4), fx: v => v + '周', label: '周ごとのタイム'});
  let s = '';
  [...new Set(L.map(d => d.stint))].forEach((st, i) => { const g = L.filter(d => d.stint === st); if (i % 2 === 0) return;
    s += `<rect x="${F.x(g[0].lap - 0.5)}" y="${F.m.t}" width="${F.x(g[g.length - 1].lap + 0.5) - F.x(g[0].lap - 0.5)}" height="${F.ih}" fill="var(--chip)" opacity=".6"/>`; });
  let over = 0;        // 枠より遅い周が続くと、タイムの文字が重なるので、1つおきに段を下げる
  for (const d of L) {
    const c = AV_KIND[d.kind] || 'var(--muted)';
    const ty = F.m.t + 24 + (d.t > ymax ? (over++ % 2) * 12 : (over = 0));
    s += d.t > ymax ? `<path d="M${F.x(d.lap) - 5},${F.m.t + 12}L${F.x(d.lap) + 5},${F.m.t + 12}L${F.x(d.lap)},${F.m.t + 3}Z" fill="${c}"><title>${d.lap}周目 ${avMmss(d.t)}（${esc(d.kind)}）</title></path><text x="${F.x(d.lap)}" y="${ty}" text-anchor="middle">${avMmss(d.t).slice(0, -4)}</text>`
      : `<circle cx="${F.x(d.lap)}" cy="${F.y(d.t)}" r="4" fill="${c}"><title>${d.lap}周目 ${avMmss(d.t)}（${esc(d.kind)}）</title></circle>`;
  }
  return avSection('周ごとのタイム（決勝）', '点が1周。上の三角は、枠より遅い周（ピットなど）。帯はスティント。点にマウスを置くと周とタイムが出ます。',
    F.wrap(s) + avLegend([[AV_KIND['通常'], '通常'], [AV_KIND['一か所で減速'], '一か所で減速'], [AV_KIND['全体に遅い'], '全体に遅い'], ['var(--muted)', 'ピット・ピット明け・スタート・最後の周・遅い周']]));
}
function avLapTable(laps) {
  if (!laps.length) return '';
  const sec = ['s1', 's2', 's3', 's4'].filter(k => laps.some(r => r[k] !== '' && r[k] != null));
  const cell = (r, k) => { const v = avNum(r[k]); return `<td style="${String(r[k + '_isbest']).toLowerCase() === 'true' ? 'color:var(--ok);font-weight:600' : ''}">${Number.isFinite(v) ? v.toFixed(3) : '—'}</td>`; };
  return avSection('周の一覧', '緑はそのセクターのベスト。', `<div class="scroll" style="max-height:420px;overflow:auto"><table><tr><th>周</th><th>種類</th><th>始まり</th><th>タイム</th><th>ベスト差</th>${sec.map(k => `<th>${k.toUpperCase()}</th>`).join('')}<th>最高速</th><th>油温の最高</th></tr>
    ${laps.map(r => `<tr><td>${r.session === '予選' ? '予選 ' : ''}${esc(r.lap)}</td><td>${esc(r.kind)}</td><td>${esc(r.start_jst)}</td><td>${avMmss(avNum(r.lap_s))}</td><td>${esc(r.to_best_txt || '')}</td>${sec.map(k => cell(r, k)).join('')}
      <td>${Number.isFinite(avNum(r.vmax)) ? avNum(r.vmax).toFixed(0) : '—'}</td><td>${Number.isFinite(avNum(r.oil_max)) ? avNum(r.oil_max).toFixed(0) + '℃' : '—'}</td></tr>`).join('')}</table></div>`);
}
function avTemps(temps) {
  const T = temps.map((r, i) => ({i, oil: avNum(r.oil), water: avNum(r.water), t: r.time_jst}));
  const vals = T.flatMap(d => [d.oil, d.water]).filter(Number.isFinite); if (!vals.length) return '';
  const step = Math.max(1, Math.round(T.length / 8)), xt = T.filter(d => d.i % step === 0).map(d => d.i);
  const F = avFrame([0, T.length - 1], [Math.floor(Math.min(...vals) / 10) * 10, Math.ceil(Math.max(...vals) / 10) * 10], {xticks: xt, fx: v => String(T[v].t).slice(0, 5), ylabel: '℃', label: '油温と水温'});
  return avSection('油温と水温', '10秒ごとの平均。線が切れている所は、値が無い時間（エンジンを切っていたなど）。',
    F.wrap(['oil', 'water'].map((k, n) => { let d = '', pen = false; for (const p of T) { if (!Number.isFinite(p[k])) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${F.x(p.i).toFixed(1)},${F.y(p[k]).toFixed(1)}`; pen = true; }
      return `<path d="${d}" fill="none" stroke="${AV_COLORS[n ? 0 : 1]}" stroke-width="1.5"/>`; }).join('')) + avLegend([[AV_COLORS[1], '油温'], [AV_COLORS[0], '水温']]));
}
function avTrack(track, corners) {
  const P = track.map(r => ({x: avNum(r.x), y: avNum(r.y), v: avNum(r.Speed)})).filter(p => Number.isFinite(p.x) && Number.isFinite(p.y)); if (P.length < 10) return '';
  const xs = P.map(p => p.x), ys = P.map(p => p.y), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const W = 760, pad = 26, k = Math.min((W - 2 * pad) / ((x1 - x0) || 1), 420 / ((y1 - y0) || 1)), H = (y1 - y0) * k + 2 * pad;
  const X = v => pad + (v - x0) * k, Y = v => H - pad - (v - y0) * k;          // 北が上
  const vs = P.map(p => p.v).filter(Number.isFinite), v0 = Math.min(...vs), v1 = Math.max(...vs);
  const color = v => { const t = (v - v0) / ((v1 - v0) || 1); return `hsl(${(240 - 240 * t).toFixed(0)} 80% 55%)`; };     // 遅い＝青 → 速い＝赤
  let s = '';
  for (let i = 1; i < P.length; i++) s += `<line x1="${X(P[i - 1].x).toFixed(1)}" y1="${Y(P[i - 1].y).toFixed(1)}" x2="${X(P[i].x).toFixed(1)}" y2="${Y(P[i].y).toFixed(1)}" stroke="${color(P[i].v)}" stroke-width="4" stroke-linecap="round"/>`;
  for (const c of corners) { const cx = avNum(c.x), cy = avNum(c.y); if (Number.isFinite(cx) && Number.isFinite(cy)) s += `<text x="${X(cx) + 8}" y="${Y(cy) - 6}" style="fill:var(--text);font-weight:600">${esc(c.name)}</text>`; }
  return avSection('コースと速度（ベストの周）', `色が速度（青 ${v0.toFixed(0)} km/h 〜 赤 ${v1.toFixed(0)} km/h）。C1〜は、速度が大きく落ちるコーナー。上が北。`,
    `<div class="scroll"><svg viewBox="0 0 ${W} ${H.toFixed(0)}" style="width:100%;min-width:420px;max-width:760px;height:auto;font-size:12px" role="img" aria-label="コースと速度">${s}</svg></div>`);
}
function avCompare(compare) {
  const labels = [...new Set(compare.map(r => r.label))]; if (!labels.length) return '';
  const rows = l => compare.filter(r => r.label === l).map(r => [avNum(r.s), avNum(r.delta), avNum(r.speed)]);
  const all = compare.map(r => avNum(r.s)).filter(Number.isFinite), sx = [Math.min(...all), Math.max(...all)], km = v => (v / 1000).toFixed(1) + 'km';
  const chart = (col, ys, opt) => { const F = avFrame(sx, ys, {...opt, fx: km});
    return F.wrap(labels.map((l, i) => `<path d="${avPath(rows(l).map(p => [p[0], p[col]]), F.x, F.y)}" fill="none" stroke="${AV_COLORS[i % AV_COLORS.length]}" stroke-width="1.5"/>`).join('')); };
  const ds = compare.map(r => avNum(r.delta)).filter(Number.isFinite), sp = compare.map(r => avNum(r.speed)).filter(Number.isFinite);
  return avSection('ベストの周との差（道のりごと）', 'ベストの周を0として、そこまでに何秒遅れているか。線が上がっている所でタイムを失っています。',
      chart(1, [Math.min(0, ...ds), Math.max(...ds)], {ylabel: '秒', label: 'ベストの周との差'}) + avLegend(labels.map((l, i) => [AV_COLORS[i % AV_COLORS.length], l])))
    + avSection('速度（道のりごと）', '', chart(2, [Math.floor(Math.min(...sp) / 20) * 20, Math.ceil(Math.max(...sp) / 20) * 20], {ylabel: 'km/h', label: '速度'}));
}
function avFacts(facts) {
  return avSection('数字の一覧', `解析が出した数字すべて（${facts.length} 個）。言葉で絞り込めます。`,
    `<div class="row" style="margin-top:4px"><input type="text" id="av-find" placeholder="例：油温・スティント・LTE" style="max-width:20em"></div>
     <div class="scroll" style="max-height:360px;overflow:auto"><table id="av-facts"><tr><th>何の数字か</th><th>値</th></tr>${facts.map(f => `<tr><td style="white-space:normal">${esc(f.label)}</td><td>${esc(f.text)}</td></tr>`).join('')}</table></div>`);
}
async function showAnalysis(id, box) {
  box.innerHTML = '<div class="sub">解析の結果を読んでいます…</div>';
  let d;
  try { const r = await fetch('/api/report_data?id=' + encodeURIComponent(id)); d = await r.json();
    if (!r.ok) { box.innerHTML = `<div class="banner warn">${esc(d.error || '読めませんでした')}</div>`; return; }
  } catch (x) { box.innerHTML = '<div class="banner bad">読めませんでした（アプリが止まっていませんか）</div>'; return; }
  const T = d.tables, F = Object.fromEntries((T.facts || []).map(f => [f.key, f]));
  const parts = [[avTiles, [F]], [avLapChart, [T.laps || []]], [avLapTable, [T.laps || []]], [avTemps, [T.temps || []]], [avTrack, [T.track || [], T.corners || []]], [avCompare, [T.compare || []]], [avFacts, [T.facts || []]]];
  let html = `<div class="result plain" style="margin-top:10px"><b>解析の結果</b>　<span class="sub">${esc(d.name || '')}・${esc(d.made)} に作ったもの</span>
    <div class="sub">数字とグラフだけを出しています。出来事の説明や読み解きの文は入っていません（決めごとの覚え書きは、上の欄にあります）。</div>`;
  for (const [fn, args] of parts) { try { html += fn(...args); } catch (x) { html += `<div class="banner warn" style="margin-top:8px">この部分は出せませんでした（${esc(fn.name)}：${esc(x.message)}）。表の形が、この画面の知っている形と違います。</div>`; } }
  box.innerHTML = html + '<div class="row" style="margin-top:10px"><button id="av-close">結果を閉じる</button></div></div>';
  const find = $('av-find');
  if (find) find.oninput = () => { const q = find.value.trim(); document.querySelectorAll('#av-facts tr').forEach((tr, i) => { if (i) tr.hidden = !!q && !tr.textContent.includes(q); }); };
  $('av-close').onclick = () => { box.innerHTML = ''; };
  box.scrollIntoView({block: 'nearest'});
}
