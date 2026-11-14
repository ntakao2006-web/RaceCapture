"""レポートの決めごとを、アプリの画面で見て直して保存する（2026-11-14、SP-5-2、`SPEC.md` 4章 A-3）。

    view(root, run, table)            画面に出すもの：走行記録から出した案（report_draft.py）と、前に保存したもの
    save(root, run, table, body)      画面で直したものを確かめて保存する。おかしければ ValueError（理由を全部並べる）

保存先は drive_logs/reports/<走行のid>.json（人の名前や覚え書きが入るので、リポジトリには入れない）。
形は、大会のあとの解析（tools/race_analysis/race_analysis.py）の設定ファイルと同じ名前の項目にそろえてある
（race_laps・stints・pit_laps・pit_out_laps・incident_laps・slow_all_laps・pre_pit_slow・window・notes）。

    run_analysis(root, run, runs, vehicle)   保存した決めごとで解析を流す（数分かかる。アプリは裏で動かす）

解析の設定は drive_logs/reports/<走行のid>.analysis.json、出力は drive_logs/reports/<走行のid>/（detail・pub）。
予選は、決めごとで選んであれば入れる。LTEの記録は入れない（届き方の項目が出ないだけ）。
解析は pandas・numpy・scipy が要る（tools/requirements.txt）。NCEC・SUGO の記録で作ったものなので、
信号やセクターの数が違う車・コースでは、途中で止まることがある（止まったら、解析が出した最後の文を画面に出す）。
画面は report.js（「走行を見る」の走行の行の「レポートの下書き」）。

スティントは、決勝の周とピットの周から決まるので、画面では入れさせない（ピットの周を直せばスティントも変わる）。
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import report_draft

REPORT_DIR = 'reports'
ANALYSIS = Path(__file__).resolve().parents[1] / 'race_analysis' / 'race_analysis.py'
NEEDS = ('pandas', 'numpy', 'scipy')
REASONS = {'incident': '一か所で遅れた（コースアウト・接触・黄旗など）', 'slow_all': '全体に遅い（渋滞・ペースを落とした）',
           'none': '遅い周に入れない'}
# 「ピットの前にペースを落とした周」は理由とは別の印（同じ周が、理由と両方に入ることがある。SUGO 11/8 の 22〜24・35〜37周目）
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
            'file': str(path_of(root, run)), 'has_results': (Path(root) / REPORT_DIR / run['id'] / 'pub' / 'facts.csv').is_file()}


def integers(value, label, problems):
    if not isinstance(value, list) or any(type(n) is not int for n in value):
        problems.append(f'{label}は、周の番号（数字）で入れてください')
        return []
    return value


def save(root, run, table, body):
    """body：{'name', 'race_laps': [a, b], 'pit_laps': [...], 'drivers': [...], 'slow': {周: 理由の鍵}, 'pre_pit': [周...], 'slow_memo': {周: 文},
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
    pre_pit = sorted(set(integers(body.get('pre_pit', []), 'ピットの前にペースを落とした周', problems)))
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
        'pre_pit_slow': ranges(pre_pit), 'slow_memo': memo,
        'quali': quali or None, 'notes': str(body.get('notes') or '').strip()[:4000],
    }
    path = path_of(root, run)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    temp.replace(path)
    return {'saved': result, 'file': str(path)}

# ---------------------------------------------------------------- 解析を流す
def missing_parts():
    return [name for name in NEEDS if importlib.util.find_spec(name) is None]


def analysis_config(root, run, saved, runs, vehicle):
    """保存した決めごとから、race_analysis.py の設定を作る。足りないものがあれば ValueError"""
    root = Path(root)
    if not saved:
        raise ValueError('先に、決めごとを保存してください')
    if not run.get('course'):
        raise ValueError('この走行はコースが分かりません（走った場所が、PCにあるどのコースの設定とも合いません）。解析は線の位置が要るので、流せません')
    if not vehicle:
        raise ValueError('車の設定がPCにありません（tools/setups/vehicles/）')
    cfg = {'name': saved.get('name') or run['id'], 'date': saved['date'], 'course': run['course'], 'vehicle': vehicle,
           'race_csv': str(root / run['log']), 'out_dir': str(root / REPORT_DIR / run['id']),
           **{k: saved[k] for k in ('window', 'race_laps', 'stints', 'pit_laps', 'pit_out_laps', 'incident_laps', 'slow_all_laps', 'pre_pit_slow')}}
    if saved.get('quali'):
        other = next((r for r in runs if r['id'] == saved['quali']['id']), None)
        if not other:
            raise ValueError('予選に選んだ走行が、PCに見つかりません。決めごとの「予選の走行」を選び直して保存してください')
        cfg.update(quali_csv=str(root / other['log']), quali_laps=saved['quali']['laps'])
    return cfg


def run_analysis(root, run, runs, vehicle, python=None, timeout=3600):
    """解析を流して {'out_dir', 'tables', 'facts', 'seconds'} を返す。できなければ ValueError（流す前）か RuntimeError（途中で止まった）"""
    root = Path(root)
    try:
        saved = json.loads(path_of(root, run).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = None
    cfg = analysis_config(root, run, saved, runs, vehicle)
    lacking = missing_parts()
    if lacking:
        raise ValueError(f'解析に要る部品（{"・".join(lacking)}）が、このPCのPythonに入っていません。tools/requirements.txt を見て入れてください')
    cfg_path = path_of(root, run).with_suffix('.analysis.json')
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    began = time.time()
    done = subprocess.run([python or sys.executable, str(ANALYSIS), str(cfg_path)], capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    pub = Path(cfg['out_dir']) / 'pub'
    if done.returncode:
        last = [line for line in (done.stderr or '').strip().splitlines() if line.strip()][-3:]
        raise RuntimeError('解析が途中で止まりました。' + ' ／ '.join(last)[:600])
    tables = sorted(p.name for p in pub.glob('*.csv'))
    facts = 0
    try:
        facts = max(0, len((pub / 'facts.csv').read_text(encoding='utf-8').splitlines()) - 1)
    except OSError:
        pass
    return {'out_dir': cfg['out_dir'], 'pub': str(pub), 'tables': tables, 'facts': facts, 'seconds': round(time.time() - began)}

# ---------------------------------------------------------------- 解析の結果を見る
VIEW_TABLES = ('facts', 'laps', 'temps', 'track', 'corners', 'compare')     # アプリの画面（analysis_view.js）が出す表


def results(root, run):
    """解析が出した表を、画面に出す形で返す。まだ流していなければ ValueError"""
    import csv
    pub = Path(root) / REPORT_DIR / run['id'] / 'pub'
    if not (pub / 'facts.csv').is_file():
        raise ValueError('この走行は、まだ解析を流していません。「保存した決めごとで解析を流す」を押してください')
    tables = {}
    for name in VIEW_TABLES:
        try:
            with open(pub / f'{name}.csv', encoding='utf-8', newline='') as f:
                tables[name] = list(csv.DictReader(f))
        except OSError:
            tables[name] = []
    name = ''
    try:
        name = json.loads(path_of(root, run).read_text(encoding='utf-8')).get('name', '')
    except (OSError, ValueError):
        pass
    made = time.strftime('%Y-%m-%d %H:%M', time.localtime((pub / 'facts.csv').stat().st_mtime))
    return {'id': run['id'], 'name': name, 'made': made, 'tables': tables}
