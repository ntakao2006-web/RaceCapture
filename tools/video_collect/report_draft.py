"""レポートの決めごとの下書き（2026-11-14、SP-5-2、`SPEC.md` 4章 A-3）。

大会のあとの解析（tools/race_analysis/race_analysis.py）は、大会ごとの決めごとを設定ファイルに人が書いている
（例 tools/race_analysis/sugo_20261108.json）。そのうち、周の表（run_laps.py）から出せるものをここで出し、
人が決めるものは「人が入れる」と分けて返す。出すのは案で、人が直してから使う。

    d = draft(run, table)        # run：run_index の1つ、table：run_laps の周の表

    d['auto']   走行記録から出したもの（人が確かめる）
        race_laps      [最初の周, 最後の周]。走行の中の、タイムのある周の端から端まで（最初の周で止まっていたら、その周は外す）
        pit_laps       ピットに入った周（止まっていた秒が PIT_STOP_S 以上。その周は遅い）
        pit_out_laps   ピットを出た周（ピットの周の次）
        stints         [[最初の周, 最後の周（ピットの周）], ...]
        slow_laps      ピットでもその次でもないのに、スティントの中央値より SLOW_RATIO 倍以上遅い周（理由は人が見る）
        window         ["HH:MM", "HH:MM"]。最初の周の始まりの5分前から、最後の周の終わりの5分後まで
    d['manual'] 人が入れるもの（[{'key', 'label', 'why'}]）
    d['notes']  下書きを読むときの注意

周の番号は周の表と同じ（本体が数えた周回数。電源をまたいで続くので、1から始まるとは限らない）。
解析の設定の番号（LapCount + 1 ＝ その周が終わったときの周回数）と同じ数え方。
"""
from datetime import datetime, timedelta, timezone
from statistics import median

JST = timezone(timedelta(hours=9))
PIT_STOP_S = 10.0     # これ以上止まっていた周をピットの周とみる（置いた値。SUGO 11/8 決勝では、ピットの2周が約1400秒、ほかは最大9秒）
SLOW_RATIO = 1.06     # スティントの中央値のこの倍より遅い周を「遅い周」に挙げる（lap_survey.py と同じ）
WINDOW_PAD_S = 300

MANUAL = [
    {'key': 'name', 'label': '大会の名前', 'why': '走行記録には入っていない'},
    {'key': 'race_laps', 'label': '決勝の周の範囲', 'why': '案は走行の端から端まで。フォーメーションラップやチェッカーのあとの周を外すのは人が決める'},
    {'key': 'quali', 'label': '予選の走行と、その周の範囲', 'why': 'どの走行が予選かは記録からは分からない'},
    {'key': 'drivers', 'label': 'スティントごとのドライバー', 'why': '走行記録には入っていない'},
    {'key': 'slow_reasons', 'label': '遅い周の理由（黄旗・コースアウト・渋滞・ピット前のペースダウンなど）',
     'why': '記録から分かるのは「遅かった」ことまで。理由は乗った人・見ていた人にしか分からない'},
    {'key': 'notes', 'label': '覚え書き（天気・路面・車の変更・起きたこと）', 'why': '走行記録には入っていない'},
]


def hhmm(t):
    return datetime.fromtimestamp(t, JST).strftime('%H:%M')


def draft(run, table):
    laps = [lap for lap in table.get('laps', []) if lap.get('time_s')]
    notes = []
    if not laps:
        return {'auto': {}, 'manual': MANUAL, 'notes': ['この走行には、タイムのある周がありません（線を通っていない・線が無かった）。']}
    numbers = [lap['lap'] for lap in laps]
    if numbers != sorted(set(numbers)):
        # 途中でラップを0周に戻すと番号が重なる。最後に戻したあとの分だけを使う
        last_reset = max(i for i in range(len(numbers)) if i == 0 or numbers[i] <= numbers[i - 1])
        laps = laps[last_reset:]
        notes.append('走行の途中でラップを0周に戻しています。最後に戻したあとの周だけで下書きを作りました。')
    if len(laps) > 1 and (laps[0].get('stop_s') or 0) >= PIT_STOP_S:
        # 走行の最初の周で止まっていたのは、スタート前の待ち（グリッド・ピットロード）。決勝の周に入れない
        notes.append(f"最初の周（{laps[0]['lap']}周目）は止まっていた時間があるので、スタート前の周とみて決勝の周から外しました。")
        laps = laps[1:]
    first, last = laps[0]['lap'], laps[-1]['lap']
    by = {lap['lap']: lap for lap in laps}
    missing = [n for n in range(first, last + 1) if n not in by]
    if missing:
        notes.append(f'周の番号が飛んでいます（{missing[:5]}{"…" if len(missing) > 5 else ""}）。線を通ったのを数え損ねたか、周回数を手で直しています。')
    if any('stop_s' not in lap for lap in laps):
        notes.append('止まっていた秒が周の表に無いので、ピットの周は出せません（周の表を作り直すと出ます）。')
    pits = [lap['lap'] for lap in laps if (lap.get('stop_s') or 0) >= PIT_STOP_S and lap['lap'] != last]
    stints, start = [], first
    for n in pits:
        stints.append([start, n])
        start = n + 1
    if start <= last:
        stints.append([start, last])
    pit_out = [n + 1 for n in pits if n + 1 in by]
    slow = []
    for a, b in stints:
        clean = [by[n]['time_s'] for n in range(a, b + 1) if n in by and n not in pits and n not in pit_out]
        if len(clean) < 3:
            continue
        mid = median(clean)
        slow += [n for n in range(a, b + 1) if n in by and n not in pits and n not in pit_out and by[n]['time_s'] > mid * SLOW_RATIO]
    auto = {'race_laps': [first, last], 'pit_laps': pits, 'pit_out_laps': pit_out, 'stints': stints, 'slow_laps': slow}
    if laps[0].get('start') is not None and laps[-1].get('end') is not None:
        auto['window'] = [hhmm(laps[0]['start'] - WINDOW_PAD_S), hhmm(laps[-1]['end'] + WINDOW_PAD_S)]
    if (laps[-1].get('stop_s') or 0) >= PIT_STOP_S:
        notes.append(f'最後の周（{last}周目）は止まっていた時間があります。チェッカーのあとにピットへ戻った周なら、決勝の周から外してください。')
    notes.append('タイムは本体が数えたものです（公式の計測ではありません）。')
    return {'auto': auto, 'manual': MANUAL, 'notes': notes}
