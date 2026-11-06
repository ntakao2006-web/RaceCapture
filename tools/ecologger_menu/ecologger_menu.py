"""Ver.2（UNO Q）をPCから操作する道具をまとめたメニュー（デスクトップのショートカットから開く）。

上の段に本体の状態（記録・受信・測位・SD・録画・LTE・画面・ラップ・温度）を出し、
下の段のボタンで、これまで別々に置いてあった .cmd を開く。

つなぎ方は自動で選ぶ：USB直結のadbで届けばそれ、届かなければPixelのテザリング（ssh unoq、
名前が引けなければIPで探す＝tools/collect_logs/unoq_ssh.py）。--adb を受け付ける道具には、
USBでつながっているときだけ --adb を付けて開く。

このメニュー自身が本体へ書き込むのは「HDMIの画面の切り替え」だけ（dash_switch.sh、記録には触らない）。
ラップのリセットは Reset-Laps.cmd を、確かめてから開く。状態は30秒ごとに読む（読むだけ）。

    python ecologger_menu.py            # ふだん（デスクトップのショートカットは pythonw でこれを開く）
    python ecologger_menu.py --once     # 窓を出さずに状態を1回読んで表示する（確かめる用）
"""
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS / 'video_collect'))
sys.path.insert(0, str(TOOLS / 'collect_logs'))

import video_collect  # noqa: E402  本体の探し方（find_link：adb → ssh）をそのまま使う

API = 'http://127.0.0.1:8080'
DASH_SWITCH = '/opt/logger-v2-racecapture/dash_switch.sh'
REFRESH_S = 30

STATUS_SCRIPT = f'''
echo '@@S'; curl -s -m 6 {API}/api/status
echo; echo '@@L'; curl -s -m 6 {API}/api/lap
echo; echo '@@D'; {DASH_SWITCH} status 2>&1
echo '@@H'; cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null
echo '@@U'; cat /proc/uptime
exit 0
'''

# (見出し, [(ボタン, .cmd, 追加の引数, USBなら --adb を付けるか, 説明)])
TOOL_GROUPS = [
    ('回収', [
        ('動画を回収', 'video_collect/Collect-Video.cmd', [], False,
         '走行ごとの一覧・吸い出し・本体から消す・SDカード（ブラウザで開く）'),
        ('走行ログを回収', 'collect_logs/Collect-Logs.cmd', [], False,
         'SDカードと本体から新しい走行ログをまとめて取る（元は消さない）'),
    ]),
    ('焼き込み映像', [
        ('計器の配置をPCで見る', 'video_hud/Preview-HUD.cmd', [], False, 'hud.ini を保存するたびに描き直す'),
        ('計器の配置を本体へ送る', 'video_hud/Apply-HUD.cmd', [], True, 'hud.ini を本体の録画へ'),
        ('レンズをPCで見る', 'lens_view/Lens-View.cmd', [], False, 'カメラをPCにつないで補正・ズームを決める'),
        ('レンズを本体のモニターで決める', 'lens_view/Lens-Preview.cmd', [], True, '録画に写る絵を本体のモニターに出す'),
        ('レンズの値を本体へ送る', 'lens_view/Apply-Lens.cmd', [], True, 'lens.json を本体の録画へ'),
        ('露出（明るさ）を見る・切り替える', 'video_exposure/Exposure.cmd', [], True,
         '白飛び対策／カメラ任せに戻す／明るく・暗く'),
    ]),
    ('LTEの電波（コースウォーク）', [
        ('電波の記録を始める', 'lte_antenna/Start-RadioWalk.cmd', [], False, '30分'),
        ('電波の記録を止めて回収', 'lte_antenna/Fetch-RadioWalk.cmd', [], False, 'drive_logs へ'),
    ]),
]


# ---------------------------------------------------------------- 状態を読む
def sections(text):
    """'@@X' で区切られた出力を {'X': 中身} にする"""
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith('@@') and len(line) == 3:
            key = line[2]
            out[key] = []
        elif key:
            out[key].append(line)
    return {k: '\n'.join(v).strip() for k, v in out.items()}


def load_json(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def fmt_bytes(n):
    if n is None:
        return '?'
    return f'{n / 2**30:.1f} GiB' if n >= 2**30 else f'{n / 2**20:.0f} MiB'


def fmt_duration(s):
    s = int(s)
    return f'{s // 3600}時間{s % 3600 // 60:02d}分' if s >= 3600 else f'{s // 60}分{s % 60:02d}秒'


def summarize(text):
    """本体の出力から、画面に出す (項目, 値, 注意か) の一覧を作る"""
    parts = sections(text)
    status, lap = load_json(parts.get('S')), load_json(parts.get('L'))
    rows = []
    if not status:
        rows.append(('EcoCapture', '応答がありません（本体のEcoCaptureが止まっているかも）', True))
    else:
        sensors = status.get('sensors') or {}
        log = status.get('logging') or {}
        if log.get('active'):
            rows.append(('記録', f"記録中 {fmt_duration(log.get('elapsed_s') or 0)}（{log.get('name')}）", False))
        else:
            rows.append(('記録', '止まっています' + (f"（{log['error']}）" if log.get('error') else ''), True))
        hz = status.get('receive_hz') or 0
        rows.append(('受信', f'{hz} Hz' if status.get('connected') else '基板から届いていません', not status.get('connected') or hz < 80))
        rows.append(('測位', sensors.get('gnss', '?'), '待ち' in str(sensors.get('gnss', ''))))
        rows.append(('IMU・CAN', f"{sensors.get('imu', '?')} ／ {sensors.get('can', '?')}", False))
        warn = log.get('sd_warning')
        rows.append(('SDカード', warn or sensors.get('sd', '?'), bool(warn)))
        video = status.get('video') or {}
        rec = '録画中' if video.get('recording') else '録画していない'
        rows.append(('録画', f"{rec}・カメラ {sensors.get('camera', '?')}・あと約{video.get('minutes_left', '?')}分"
                             f"・未回収 {video.get('uncollected', '?')}本（{fmt_bytes(video.get('uncollected_bytes'))}）",
                     not video.get('recording')))
        rows.append(('本体の空き', fmt_bytes(status.get('storage_free_bytes')), (status.get('storage_free_bytes') or 0) < 2**30))
        podium = status.get('podium') or {}
        radio = podium.get('radio') or {}
        lte = '送信OFF' if not podium.get('enabled') else podium.get('message') or podium.get('state') or '?'
        if radio.get('rsrp') is not None:
            lte += f"（RSRP {radio['rsrp']} dBm）"
        rows.append(('LTE', lte, not podium.get('enabled') or podium.get('state') not in ('streaming', 'waiting_gps')))
    if lap:
        values = lap.get('values') or {}
        line = lap.get('line') or {}
        rows.append(('ラップ', f"{values.get('LapCount', '?')}周（ライン {'有効' if line.get('enabled') else '無効'}）",
                     not line.get('enabled')))
    screen = parts.get('D', '')
    if 'ecocapture-dash: active' in screen:
        rows.append(('HDMIの画面', 'EcoCapture DASH', False))
    elif 'racecapture-app: active' in screen:
        rows.append(('HDMIの画面', 'RaceCaptureアプリ', False))
    else:
        rows.append(('HDMIの画面', screen.replace('\n', ' ／ ') or '?', True))
    temps = [int(t) / 1000 for t in parts.get('H', '').split() if t.strip().lstrip('-').isdigit()]
    if temps:
        rows.append(('本体の温度', f'{max(temps):.0f}℃', max(temps) >= 80))
    uptime = parts.get('U', '').split()
    if uptime:
        rows.append(('起動から', fmt_duration(float(uptime[0])), False))
    return rows


class Device:
    """本体とのつなぎ。見つけたつなぎ方を覚えておき、失敗したら探し直す"""

    def __init__(self, log):
        self.link, self.log = None, log
        self.lock = threading.Lock()

    def find(self):
        quiet = lambda *a, **k: None  # noqa: E731
        self.link = video_collect.find_link('unoq', log=quiet)
        return self.link

    def run(self, script, timeout=40):
        with self.lock:
            for attempt in (0, 1):
                if self.link is None and not self.find():
                    raise OSError('本体が見つかりません（USBのケーブル、またはPCと本体が同じテザリングにいるか）')
                try:
                    return self.link.run(script, timeout=timeout)
                except (OSError, subprocess.SubprocessError):
                    self.link = None
                    if attempt:
                        raise

    @property
    def usb(self):
        return isinstance(self.link, video_collect.AdbLink)

    def label(self):
        return self.link.label() if self.link else 'つながっていません'


# ---------------------------------------------------------------- 窓
class Menu:
    def __init__(self, root):
        self.root = root
        self.device = Device(self.add_log)
        self.busy = False
        root.title('EcoLogger Ver.2 操作メニュー')
        root.geometry("1000x900")
        root.minsize(900, 700)
        style = ttk.Style()
        try:
            style.theme_use('vista')
        except tk.TclError:
            pass
        font = ('Yu Gothic UI', 10)
        root.option_add('*Font', font)
        style.configure('Head.TLabel', font=('Yu Gothic UI', 11, 'bold'))
        style.configure('Warn.TLabel', foreground='#b3261e')
        style.configure('TButton', padding=(8, 4))

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill='both', expand=True)

        top = ttk.Frame(outer)
        top.pack(fill='x')
        self.conn = ttk.Label(top, text='本体を探しています…', style='Head.TLabel')
        self.conn.pack(side='left')
        ttk.Button(top, text='状態を読み直す', command=self.refresh).pack(side='right')

        box = ttk.LabelFrame(outer, text='本体の状態', padding=8)
        box.pack(fill='x', pady=(8, 8))
        self.grid = ttk.Frame(box)
        self.grid.pack(fill='x')
        self.grid.columnconfigure(1, weight=1)
        self.updated = ttk.Label(box, text='', foreground='#666')
        self.updated.pack(anchor='e')

        cols = ttk.Frame(outer)
        cols.pack(fill='x')
        cols.columnconfigure(0, weight=1, uniform='c')
        cols.columnconfigure(1, weight=1, uniform='c')
        left, right = ttk.Frame(cols), ttk.Frame(cols)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        right.grid(row=0, column=1, sticky='nsew', padx=(4, 0))

        ops = ttk.LabelFrame(left, text='画面・ラップ（SUGO）', padding=8)
        ops.pack(fill='x', pady=(0, 8))
        ttk.Button(ops, text='HDMIをDASHにする', width=26, command=lambda: self.switch_screen('dash')).grid(row=0, column=0, sticky='w', pady=1)
        ttk.Button(ops, text='HDMIをRaceCaptureにする', width=26, command=lambda: self.switch_screen('racecapture')).grid(row=1, column=0, sticky='w', pady=1)
        self.boot = tk.BooleanVar(value=False)
        ttk.Checkbutton(ops, text='電源を入れたときも\nこの画面にする', variable=self.boot).grid(row=0, column=1, rowspan=2, sticky='w', padx=8)
        ttk.Button(ops, text='ラップを0周に戻す…', width=26, command=self.reset_laps).grid(row=2, column=0, sticky='w', pady=(6, 1))
        ttk.Label(ops, text='予選のあと決勝の前に。\nラインはそのまま', foreground='#666').grid(row=2, column=1, sticky='w', padx=8)

        for n, (title, tools) in enumerate(TOOL_GROUPS):
            frame = ttk.LabelFrame(right if n == 1 else left, text=title, padding=8)
            frame.pack(fill='x', pady=(0, 8))
            frame.columnconfigure(1, weight=1)
            for i, (label, cmd, args, adb_ok, note) in enumerate(tools):
                ttk.Button(frame, text=label, width=26,
                           command=lambda c=cmd, a=args, o=adb_ok: self.launch(c, a, o)).grid(row=i, column=0, sticky='w', pady=1)
                ttk.Label(frame, text=note, foreground='#666', wraplength=190).grid(row=i, column=1, sticky='w', padx=8)

        lte = ttk.LabelFrame(right, text='LTEで（本体から離れているとき・5Bの中継経由）', padding=8)
        lte.pack(fill='x', pady=(0, 8))
        for i, (label, op) in enumerate([('状態を聞く', 'status'), ('ラップを0周に戻す…', 'lap_reset'),
                                         ('周回数を直す…', 'lap_count'), ('いまから計測を始める…', 'lap_start'),
                                         ('記録を始める…', 'log_start')]):
            ttk.Button(lte, text=label, width=22, command=lambda o=op: self.remote(o)).grid(row=i // 2, column=i % 2, sticky='w', padx=(0, 6), pady=1)
        ttk.Label(lte, text='返事まで数秒〜30秒。結果は下のメモに出ます', foreground='#666').grid(row=3, column=0, columnspan=2, sticky='w', pady=(4, 0))

        misc = ttk.LabelFrame(left, text='開く', padding=8)
        misc.pack(fill='x', pady=(0, 8))
        ttk.Button(misc, text='drive_logs（回収したもの）', width=26, command=lambda: self.open_path(REPO / 'drive_logs')).pack(anchor='w', pady=1)
        ttk.Button(misc, text='hud.ini（計器の配置）', width=26, command=lambda: self.open_path(TOOLS / 'video_hud' / 'hud.ini')).pack(anchor='w', pady=1)
        ttk.Button(misc, text='SUGOの当日の手順書', width=26, command=lambda: self.open_path(REPO / 'sugo_day_manual_20261108.html')).pack(anchor='w', pady=1)

        logbox = ttk.LabelFrame(right, text='メモ（操作の結果）', padding=4)
        logbox.pack(fill='both', expand=True, pady=(0, 8))
        self.log = tk.Text(logbox, height=8, width=40, wrap='word', state='disabled', background='#fafafa', relief='flat')
        self.log.pack(fill='both', expand=True)

        self.refresh()
        self.root.after(REFRESH_S * 1000, self.tick)

    # -- 共通
    def add_log(self, text):
        def put():
            self.log.configure(state='normal')
            self.log.insert('end', f"{datetime.now():%H:%M:%S}  {text}\n")
            self.log.see('end')
            self.log.configure(state='disabled')
        self.root.after(0, put)

    def background(self, work, done):
        def run():
            try:
                result, error = work(), None
            except Exception as exc:  # noqa: BLE001  画面に出して続ける
                result, error = None, exc
            self.root.after(0, lambda: done(result, error))
        threading.Thread(target=run, daemon=True).start()

    def show_conn(self):
        self.conn.configure(text=('● ' if self.device.link else '○ ') + self.device.label(),
                            foreground='#1b6e2e' if self.device.link else '#b3261e')

    # -- 状態
    def tick(self):
        self.refresh(quiet=True)
        self.root.after(REFRESH_S * 1000, self.tick)

    def refresh(self, quiet=False):
        if self.busy:
            return
        self.busy = True
        if not quiet:
            self.conn.configure(text='本体を読んでいます…', foreground='#444')
        self.background(lambda: summarize(self.device.run(STATUS_SCRIPT)), self.show_status)

    def show_status(self, rows, error):
        self.busy = False
        self.show_conn()
        for child in self.grid.winfo_children():
            child.destroy()
        if error:
            ttk.Label(self.grid, text=str(error), style='Warn.TLabel', wraplength=680).grid(row=0, column=0, columnspan=2, sticky='w')
            self.updated.configure(text=f'{datetime.now():%H:%M:%S} 読めませんでした（{REFRESH_S}秒ごとに読み直します）')
            return
        for i, (name, value, warn) in enumerate(rows):
            ttk.Label(self.grid, text=name, width=11).grid(row=i, column=0, sticky='nw', pady=1)
            ttk.Label(self.grid, text=('★ ' if warn else '') + str(value), wraplength=820,
                      style='Warn.TLabel' if warn else 'TLabel').grid(row=i, column=1, sticky='w', pady=1)
        self.updated.configure(text=f'{datetime.now():%H:%M:%S} に読みました（{REFRESH_S}秒ごと）')

    # -- 本体を操作
    def switch_screen(self, which):
        args = which + (' --boot' if self.boot.get() else '')
        name = 'EcoCapture DASH' if which == 'dash' else 'RaceCaptureアプリ'
        self.add_log(f'HDMIの画面を{name}にします' + ('（電源を入れたときも）' if self.boot.get() else '') + '…')

        def done(out, error):
            if error:
                self.add_log(f'画面の切り替えに失敗しました: {error}')
            else:
                self.add_log('切り替えました（記録はそのまま）: ' + ' ／ '.join(out.strip().splitlines()))
            self.refresh(quiet=True)
        self.background(lambda: self.device.run(f'{DASH_SWITCH} {args} 2>&1', timeout=60), done)

    def reset_laps(self):
        if not messagebox.askyesno('ラップを0周に戻す',
                                   'Ver.2のラップの記録（周回数・ラップタイム）を消して0周に戻します。\n'
                                   'ラインの設定はそのままです。記録は止まりません。\n\n戻しますか？', icon='warning'):
            return
        self.launch('sugo_setup/Reset-Laps.cmd', [], True)

    # -- LTEで命令（tools/remote_command）
    def remote(self, op):
        sys.path.insert(0, str(TOOLS / 'remote_command'))
        import remote_command_pc as rc
        arg = None
        if op == 'lap_count':
            arg = simpledialog.askinteger('周回数を直す', '完了した周回数（0〜999）を入れてください。\n'
                                          'ラップタイムの記録はそのまま、周回数だけが変わります。',
                                          minvalue=0, maxvalue=999, parent=self.root)
            if arg is None:
                return
        elif op != 'status':
            text = {'lap_reset': 'ラップの記録を消して0周に戻します（ラインはそのまま）。',
                    'lap_start': 'いまの時刻からラップの計測を始めます（スタートを取り逃したとき）。\n計測中なら何もしません。',
                    'log_start': '本体の記録を始めます（記録が止まっているとき）。'}[op]
            if not messagebox.askyesno(rc.OP_LABEL[op], text + '\n\nLTEで送りますか？', icon='warning'):
                return
        self.add_log(f'LTEで「{rc.OP_LABEL[op]}{"" if arg is None else f"（{arg}周）"}」を送ります…')

        def done(result, error):
            if error:
                self.add_log(f'送れませんでした: {error}')
                return
            for line in rc.describe(result):
                self.add_log(line)
        self.background(lambda: rc.send(op, arg, log=lambda *a: None), done)

    # -- 道具を開く
    def launch(self, cmd, args, adb_ok):
        path = TOOLS / cmd
        extra = ['--adb'] if adb_ok and self.device.usb else []
        self.add_log(f'{path.name} {" ".join(args + extra)}を開きました'.replace('  ', ' ')
                     + ('（USB）' if extra else '（テザリング）' if adb_ok else ''))
        subprocess.Popen(['cmd', '/c', str(path), *args, *extra], cwd=str(path.parent),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)

    def open_path(self, path):
        if not path.exists():
            self.add_log(f'見つかりません: {path}')
            return
        os.startfile(str(path))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--once' in argv:
        device = Device(print)
        started = time.monotonic()
        rows = summarize(device.run(STATUS_SCRIPT))
        print(f'つなぎ方: {device.label()}（{time.monotonic() - started:.1f}秒）')
        for name, value, warn in rows:
            print(f"{'★' if warn else ' '} {name}: {value}")
        return 0
    root = tk.Tk()
    Menu(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
