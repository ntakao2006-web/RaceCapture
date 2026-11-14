"""レポートの決めごとを、アプリの画面で見て直して保存する（2026-11-14、SP-5-2、`SPEC.md` 4章 A-3）。

    view(root, run, table)            画面に出すもの：走行記録から出した案（report_draft.py）と、前に保存したもの
    save(root, run, table, body)      画面で直したものを確かめて保存する。おかしければ ValueError（理由を全部並べる）

保存先は drive_logs/reports/<走行のid>.json（人の名前や覚え書きが入るので、リポジトリには入れない）。
形は、大会のあとの解析（tools/race_analysis/race_analysis.py）の設定ファイルと同じ名前の項目にそろえてある
（race_laps・stints・pit_laps・pit_out_laps・incident_laps・slow_all_laps・pre_pit_slow・window・notes）。
解析を流すには、このほかに予選の走行とLTEの記録の場所が要る（いまは手で足す。アプリから流す所はまだ無い）。
画面は report.js（「走行を見る」の走行の行の「レポートの下書き」）。

スティントは、決勝の周とピットの周から決まるので、画面では入れさせない（ピットの周を直せばスティントも変わる）。
"""
import json
import re
import time
from pathlib import Path

import report_draft

REPORT_DIR = 'reports'
REASONS = {'incident': '一か所で遅れた（コースアウト・接触・黄旗など）', 'slow_all': '全体に遅い（渋滞・ペースを落とした）',
           'pre_pit': 'ピットの前にペースを落とした', 'none': '遅い周に入れない'}
HHMM = re.compile(r'^([01]?\d|2[0-3]):[0-5]\d$')


def path_of(root, run):
    return Path(root) / REPORT_DIR / f"{run['id']}.json"


def ranges(laps):
    """続いた周をまとめる：[22, 23, 24, 35] → [[22, 24], [35, 35]]"""
    out = []
    for n in sorted(set(laps)):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def stints_of(race_laps, pit_laps):
    first, last = race_laps
    out, start = [], first
    for n in sorted(pit_laps):
        out.append([start, n])
        start = n + 1
    if start <= last:
        out.append([start, last])
    return out


def view(root, run, table):
    saved = None
    try:
        saved = json.loads(path_of(root, run).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    d = report_draft.draft(run, table)
    laps = [{'lap': lap['lap'], 'time_s': lap['time_s'], 'stop_s': lap.get('stop_s')} for lap in table.get('laps', []) if lap.get('time_s')]
    return {'id': run['id'], 'day': run.get('day'), 'draft': d, 'saved': saved, 'laps': laps, 'reasons': REASONS,
            'file': str(path_of(root, run))}


def integers(value, label, problems):
    if not isinstance(value, list) or any(type(n) is not int for n in value):
        problems.append(f'{label}は、周の番号（数字）で入れてください')
        return []
    return value


def save(root, run, table, body):
    """body：{'name', 'race_laps': [a, b], 'pit_laps': [...], 'drivers': [...], 'slow': {周: 理由の鍵}, 'slow_memo': {周: 文},
              'window': [HH:MM, HH:MM], 'notes': 文, 'quali': {'id': 走行のid, 'laps': [a, b]} か None}"""
    problems = []
    known = {lap['lap'] for lap in table.get('laps', []) if lap.get('time_s')}
    race = integers(body.get('race_laps'), '決勝の周', problems)
    if len(race) != 2 or race[0] > race[1]:
        problems.append('決勝の周は「最初の周」と「最後の周」の2つで、最初が最後より小さくなるように入れてください')
        race = []
    elif not {race[0], race[1]} <= known:
        problems.append(f'決勝の周（{race[0]}〜{race[1]}）が、この走行の周（{min(known)}〜{max(known)}）に入っていません' if known
                        else 'この走行には、タイムのある周がありません')
        race = []
    pits = sorted(set(integers(body.get('pit_laps', []), 'ピットに入った周', problems)))
    if race:
        outside = [n for n in pits if not race[0] <= n <= race[1]]
        if outside:
            problems.append(f'ピットに入った周 {outside} が、決勝の周（{race[0]}〜{race[1]}）の外です')
        if race[1] in pits:
            problems.append(f'最後の周（{race[1]}周目）はピットの周にできません（ピットへ戻って終わったなら、決勝の周をその前までにします）')
    stints = stints_of(race, pits) if race and not problems else []
    drivers = body.get('drivers') or []
    if not isinstance(drivers, list) or any(not isinstance(x, str) for x in drivers):
        problems.append('ドライバーは、名前を並べて入れてください')
        drivers = []
    drivers = [x.strip()[:40] for x in drivers]
    if stints and any(drivers) and len(drivers) != len(stints):
        problems.append(f'ドライバーが {len(drivers)} 人ぶん入っていますが、スティントは {len(stints)} つです（ピットの周で区切られます）。数を合わせるか、空にしてください')
    slow = body.get('slow') or {}
    memo = body.get('slow_memo') or {}
    by_reason = {key: [] for key in REASONS}
    try:
        for lap, reason in slow.items():
            if reason not in REASONS:
                problems.append(f'{lap}周目の理由が選ばれていません')
            else:
                by_reason[reason].append(int(lap))
        memo = {str(int(lap)): str(text).strip()[:200] for lap, text in memo.items() if str(text).strip()}
    except (ValueError, TypeError, AttributeError):
        problems.append('遅い周の入れ方が読めません')
    window = body.get('window') or []
    if not (isinstance(window, list) and len(window) == 2 and all(isinstance(t, str) and HHMM.match(t) for t in window)):
        problems.append('時刻の範囲は「10:20」の形で、始めと終わりを入れてください')
    quali = body.get('quali')
    if quali:
        laps = quali.get('laps') if isinstance(quali, dict) else None
        if not isinstance(quali, dict) or not isinstance(quali.get('id'), str) or not (
                isinstance(laps, list) and len(laps) == 2 and all(type(n) is int for n in laps) and laps[0] <= laps[1]):
            problems.append('予選は、走行を選び、周を「最初」と「最後」で入れてください（無ければ「予選なし」にします）')
            quali = None
    if problems:
        raise ValueError(' ／ '.join(problems))
    result = {
        'format': 1, 'run': run['id'], 'saved_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'name': str(body.get('name') or '').strip()[:80], 'date': run.get('day'), 'race_csv': run.get('log'),
        'window': window, 'race_laps': race, 'stints': stints, 'drivers': drivers,
        'pit_laps': pits, 'pit_out_laps': [n + 1 for n in pits if n + 1 <= race[1]],
        'incident_laps': sorted(by_reason['incident']), 'slow_all_laps': ranges(by_reason['slow_all']),
        'pre_pit_slow': ranges(by_reason['pre_pit']), 'slow_memo': memo,
        'quali': quali or None, 'notes': str(body.get('notes') or '').strip()[:4000],
    }
    path = path_of(root, run)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    temp.replace(path)
    return {'saved': result, 'file': str(path)}
