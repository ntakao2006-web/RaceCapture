"""PCからスマホへ、LTEの命令の合言葉を渡すQRを出す（2026-11-13、SP-3・SP-6-3）。

  python phone_key.py        # 窓にQRを出す。スマホのカメラで読むと、ピットの表紙が開いて合言葉が入る

QRの中身は「ピットの表紙のアドレス ＋ #k=<合言葉>」。# のあとはサーバーへ送られず、表紙（home.html）が読んですぐ
アドレスから消し、ロガーに「状態を聞く」を送って合っているかを確かめてから、そのスマホの中にだけ覚える。

- 合言葉はPCの %USERPROFILE%\\.ecologger\\remote_command.json のもの（remote_command_pc.py setup で作る）。
- 表紙のアドレスは、同じファイルの中継のURLから作る（wss://<ホスト>/ws/audio/<ルーム> → https://<ホスト>/live/home?room=<ルーム>）。
  違う場所で開くときは、同じファイルに "home_url" を書く（例：時計の部屋なら後ろに &sheet=clock）。
- QRは qr.py で作る（外の部品・Webのサービスへ合言葉を渡さない）。合言葉とアドレスは、画面の文字にも記録にも出さない。
- QRに期限は無い（合言葉そのものなので）。出したままにしないように、窓は2分で閉じる。
  渡しすぎたとき・スマホを無くしたときは `remote_command_pc.py setup --new` で合言葉を作り直す（前に渡した機器からは送れなくなる）。
"""
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qr  # noqa: E402
import remote_command_pc as rc  # noqa: E402

CLOSE_S = 120
MODULE_PX, QUIET = 6, 4


def cover_url(local):
    """ピットの表紙のアドレス（合言葉なし）。作れなければ ValueError"""
    if local.get('home_url'):
        return str(local['home_url']).split('#', 1)[0]
    u = urlparse(local.get('url') or '')
    room = u.path.rstrip('/').rsplit('/', 1)[-1]
    if u.scheme not in ('ws', 'wss') or not u.hostname or not room:
        raise ValueError('中継のURLがPCにありません（本体をつないで `remote_command_pc.py setup` を1回する）')
    return f"{'https' if u.scheme == 'wss' else 'http'}://{u.netloc}/live/home?room={quote(room)}"


def pair_url(local):
    """QRに入れるアドレス（表紙 ＋ #k=<合言葉>）"""
    if not local.get('secret'):
        raise ValueError('合言葉がPCにありません（本体をつないで `remote_command_pc.py setup` を1回する）')
    return f"{cover_url(local)}#k={local['secret']}"


def describe(local):
    """窓に出す行き先（合言葉・アドレスの全体は出さない）"""
    u = urlparse(cover_url(local))
    room = dict(p.split('=', 1) for p in u.query.split('&') if '=' in p).get('room', '?')
    return f'行き先：ピットの表紙（ルーム {room}）'


def show():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('スマホへ合言葉を渡す')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=16)
    frame.pack()
    try:
        local = rc.load_local()
        matrix, where = qr.make(pair_url(local).encode()), describe(local)
    except ValueError as exc:
        ttk.Label(frame, text=f'QRを出せません。\n{exc}', wraplength=420).pack(anchor='w')
        ttk.Button(frame, text='閉じる', command=root.destroy).pack(pady=(12, 0))
        root.mainloop()
        return 1
    ttk.Label(frame, text='スマホのカメラで読み取ってください', font=('', 13, 'bold')).pack(anchor='w')
    ttk.Label(frame, wraplength=420, justify='left', text=(
        'ピットの表紙が開き、合言葉が入ります。ロガーが動いていれば、その場で合っているかを確かめて、'
        'そのスマホに覚えます。動いていないときは「確かめずに覚える」を選べます。')).pack(anchor='w', pady=(4, 10))
    side = (len(matrix) + QUIET * 2) * MODULE_PX
    canvas = tk.Canvas(frame, width=side, height=side, background='white', highlightthickness=0)
    canvas.pack()
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                x0, y0 = (x + QUIET) * MODULE_PX, (y + QUIET) * MODULE_PX
                canvas.create_rectangle(x0, y0, x0 + MODULE_PX, y0 + MODULE_PX, fill='black', outline='')
    ttk.Label(frame, text=where, foreground='#444').pack(anchor='w', pady=(10, 0))
    ttk.Label(frame, wraplength=420, justify='left', foreground='#b3261e', text=(
        'このQRには合言葉そのものが入っています。写真に撮って送ったり、画面を共有・配信したりしないでください。'
        '期限はありません。渡しすぎたとき・スマホを無くしたときは、合言葉を作り直します'
        '（前に渡した機器からは送れなくなります）。')).pack(anchor='w', pady=(6, 0))
    foot = ttk.Frame(frame)
    foot.pack(fill='x', pady=(12, 0))
    left = ttk.Label(foot, foreground='#666')
    left.pack(side='left')
    ttk.Button(foot, text='閉じる', command=root.destroy).pack(side='right')

    def tick(n):
        if n <= 0:
            root.destroy()
            return
        left.configure(text=f'あと{n}秒で、この窓を閉じます')
        root.after(1000, tick, n - 1)
    tick(CLOSE_S)
    root.lift()
    root.attributes('-topmost', True)
    root.after(300, lambda: root.attributes('-topmost', False))
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(show())
