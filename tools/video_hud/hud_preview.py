"""走行映像に焼き込む計器（hud.ini）の見た目を、PCのブラウザで確かめる（Preview-HUD.cmd）。

hud.ini を保存するたびに描き直す。並べるのは次の3つ:
  - 普段：hud.ini の [preview] の仮の値
  - 赤：しきい値（alarm_at・alarm_below）のある計器を、赤になる値にしたもの
  - 数値が来ていない：値が何も無いとき（show = nodata の計器が出る。時刻も出ない）
ページの上に、塗る面積から見積もった重さ（GPUの時間）を出す（hud_layout.estimate、手順書5-15の実測から）。
組み立ては本体と同じ規則（hud_layout.py ＝ 本体の hud_layout.h の写し）。文字は本体と同じ文字の一覧表を、
GPUと同じく画素の真ん中で直線補間して貼る。本体の動画はYUV（色は縦横半分の細かさ）なので、色の縁は少しにじむ。

背景：--bg の画像（jpg・png）か動画（ts・mp4、真ん中あたりの1コマ）。無ければこのフォルダの preview_bg.jpg／.png、
それも無ければ作った絵。録画した動画には計器が焼き込まれているので、背景に使うと元の計器も写る。

  python hud_preview.py                      # hud.ini を見る（ブラウザが開く。止めるときはこの窓を閉じる）
  python hud_preview.py 別の.ini --bg 写真.jpg
  python hud_preview.py --once 出力フォルダ   # 3枚をPNGに書いて終わる
"""
import argparse
import html
import http.server
import json
import math
import socketserver
import sys
import threading
import time
import webbrowser
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_layout  # noqa: E402

HERE = Path(__file__).resolve().parent
W, H = 1920, 1080
STATES = [('normal', '普段（[preview] の値）'), ('alarm', '赤（しきい値を越えたとき）'), ('nodata', '数値が来ていない')]


# ---------------------------------------------------------------- 背景
def make_background():
    """空と道のような色の絵（背景の画像が無いとき）"""
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    sky = np.array([.55, .66, .78], np.float32) * (1 - y * .35)[..., None]
    road = np.array([.30, .31, .33], np.float32) + (y[..., None] - .55) * .25
    img = np.where((y < .55)[..., None], sky, road) * np.ones((1, W, 1), np.float32)
    return np.clip(img, 0, 1)


def load_background(path):
    if path is None:
        for name in ('preview_bg.jpg', 'preview_bg.png'):
            if (HERE / name).exists():
                path = HERE / name
                break
    if path is None:
        return make_background(), '作った絵'
    path = Path(path)
    if path.suffix.lower() in ('.ts', '.mp4', '.mkv', '.mov'):
        import cv2
        cap = cv2.VideoCapture(str(path))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f'{path}: 動画から1コマを取り出せませんでした')
        im = Image.fromarray(frame[..., ::-1])
    else:
        im = Image.open(path).convert('RGB')
    im = im.resize((W, H), Image.BILINEAR)
    return np.asarray(im, np.float32) / 255, str(path)


# ---------------------------------------------------------------- 描く
def rasterize(quads, font, bg):
    """四角形を背景へ重ねる。GPUと同じく画素の真ん中が中に入るところを塗り、不透明度で混ぜる"""
    img = bg.copy()
    atlas = np.frombuffer(font.pixels, np.uint8).reshape(font.height, font.width).astype(np.float32) / 255
    for xs, ys, u0, v0, u1, v1, c in quads:
        ix0, ix1 = max(0, math.ceil(min(xs) - .5)), min(W, math.ceil(max(xs) - .5))
        iy0, iy1 = max(0, math.ceil(min(ys) - .5)), min(H, math.ceil(max(ys) - .5))
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        px = np.arange(ix0, ix1, dtype=np.float64) + .5
        py = np.arange(iy0, iy1, dtype=np.float64) + .5
        if u0 < 0:  # 塗りつぶし（回った四角も）
            X, Y = np.meshgrid(px, py)
            cross = [(xs[(i + 1) % 4] - xs[i]) * (Y - ys[i]) - (ys[(i + 1) % 4] - ys[i]) * (X - xs[i]) for i in range(4)]
            inside = np.all([cr >= 0 for cr in cross], axis=0) | np.all([cr <= 0 for cr in cross], axis=0)
            a = c[3] * inside.astype(np.float32)
        else:  # 文字：一覧表を直線補間で貼る（端は端の画素を使う）
            tx = (u0 + (px - xs[0]) / (xs[1] - xs[0]) * (u1 - u0)) * font.width - .5
            ty = (v0 + (py - ys[0]) / (ys[2] - ys[0]) * (v1 - v0)) * font.height - .5
            x0 = np.floor(tx).astype(int)
            y0 = np.floor(ty).astype(int)
            fx, fy = (tx - x0)[None, :], (ty - y0)[:, None]
            xa, xb = np.clip(x0, 0, font.width - 1), np.clip(x0 + 1, 0, font.width - 1)
            ya, yb = np.clip(y0, 0, font.height - 1), np.clip(y0 + 1, 0, font.height - 1)
            top = atlas[np.ix_(ya, xa)] * (1 - fx) + atlas[np.ix_(ya, xb)] * fx
            bot = atlas[np.ix_(yb, xa)] * (1 - fx) + atlas[np.ix_(yb, xb)] * fx
            a = c[3] * (top * (1 - fy) + bot * fy)
        a = a[..., None].astype(np.float32)
        region = img[iy0:iy1, ix0:ix1]
        img[iy0:iy1, ix0:ix1] = region * (1 - a) + np.array(c[:3], np.float32) * a
    return img


def to_png(img):
    buf = BytesIO()
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(buf, 'PNG', compress_level=1)
    return buf.getvalue()


def render_states(hud, font, bg, utc=None):
    """3つの状態の PNG（bytes）"""
    utc = time.time() if utc is None else utc
    nan = [math.nan] * len(hud.refs)
    cases = {
        'normal': (hud_layout.values_from(hud, hud.preview), utc, 0.0),
        'alarm': (hud_layout.values_from(hud, hud_layout.alarm_table(hud, hud.preview)), utc, 0.0),
        'nodata': (nan, None, hud.nodata_after + 1),
    }
    return {name: to_png(rasterize(hud_layout.build(hud, font, *cases[name]), font, bg)) for name, _ in STATES}


# ---------------------------------------------------------------- ブラウザで見る
PAGE = '''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>計器の見た目</title>
<style>
:root { --bg:#f4f5f7; --fg:#1d2026; --sub:#5b6270; --card:#fff; --line:#d9dce3; --err:#b3261e; --errbg:#fdecea; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181d; --fg:#e8eaee; --sub:#9aa1ad; --card:#20232a; --line:#353a44; --err:#ffb4ab; --errbg:#3b1d1b; } }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.6 system-ui, "Segoe UI", "Yu Gothic UI", sans-serif; }
main { max-width:1500px; margin:0 auto; padding:16px; }
h1 { font-size:20px; margin:0 0 4px; }
.sub { color:var(--sub); font-size:13px; margin:0 0 12px; word-break:break-all; }
.load { border-radius:8px; padding:8px 14px; margin:0 0 12px; font-weight:600; }
.load.ok { background:#e6f4ea; color:#1e6b34; } .load.edge { background:#fff4d6; color:#7a5200; } .load.heavy { background:#fdecea; color:#b3261e; }
@media (prefers-color-scheme: dark) { .load.ok { background:#16301f; color:#8fd6a5; } .load.edge { background:#3a2f12; color:#f2cf73; } .load.heavy { background:#3b1d1b; color:#ffb4ab; } }
.err { display:none; background:var(--errbg); color:var(--err); border:1px solid var(--err); border-radius:8px; padding:10px 14px; margin:0 0 12px; white-space:pre-wrap; }
figure { margin:0 0 18px; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; }
figcaption { font-weight:600; margin:0 0 6px; }
img { width:100%; height:auto; display:block; border-radius:4px; background:#000; }
</style></head><body><main>
<h1>走行映像の計器の見た目</h1>
<p class="sub" id="info">読み込み中…</p>
<div class="load" id="load"></div>
<div class="err" id="err"></div>
<div id="shots">__FIGS__</div>
</main>
<script>
let shown = -1;
async function poll() {
  try {
    const s = await (await fetch('/state', {cache: 'no-store'})).json();
    document.getElementById('info').textContent = s.info;
    const l = document.getElementById('load');
    l.className = 'load ' + (s.level || ''); l.textContent = s.load || '';
    const e = document.getElementById('err');
    e.style.display = s.error ? 'block' : 'none';
    e.textContent = s.error ? s.error + (s.version > 0 ? '\\n（下の絵は、最後に正しく読めたときのもの）' : '') : '';
    if (s.version !== shown && s.version > 0) {
      shown = s.version;
      for (const img of document.querySelectorAll('img[data-name]')) img.src = '/img/' + img.dataset.name + '.png?v=' + s.version;
    }
  } catch (_) {
    document.getElementById('info').textContent = '確認ツールが止まっています（Preview-HUD.cmd をもう一度開く）';
  }
  setTimeout(poll, 700);
}
poll();
</script></body></html>'''


class Watcher:
    """hud.ini（と背景）を見張って、変わったら描き直す"""

    def __init__(self, ini, bg_path):
        self.ini, self.bg_path = Path(ini), bg_path
        self.font = hud_layout.load_font()
        self.bg, self.bg_name = load_background(bg_path)
        self.lock = threading.Lock()
        self.version, self.images, self.error, self.info = 0, {}, '', ''
        self.load, self.level = '', ''
        self.key = None

    def check(self):
        try:
            st = self.ini.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        if key == self.key:
            return
        self.key = key
        error, images, info, load, level = '', None, '', '', ''
        try:
            hud = hud_layout.load(self.ini)
            images = render_states(hud, self.font, self.bg)
            screens, ms, level = hud_layout.estimate(hud, self.font)
            load = hud_layout.describe_estimate(screens, ms, level)
            info = (f'{self.ini}（計器 {len(hud.items)}個・値 {len(hud.refs)}種類）を見ています。保存すると描き直します。'
                    f' 背景：{self.bg_name}。描いた時刻 {time.strftime("%H:%M:%S")}')
        except hud_layout.HudError as e:
            error = f'{self.ini.name} の {e}'
        except FileNotFoundError:
            error = f'{self.ini} が見つかりません'
        except UnicodeDecodeError:
            error = f'{self.ini.name} の文字コードがUTF-8ではありません（メモ帳なら「名前を付けて保存」でUTF-8を選ぶ）'
        with self.lock:
            self.error = error
            if images:
                self.images, self.version, self.info = images, self.version + 1, info
                self.load, self.level = load, level
            elif not self.info:
                self.info = f'{self.ini} を見ています'

    def loop(self):
        while True:
            try:
                self.check()
            except Exception as e:  # 何があっても見張りは続ける
                with self.lock:
                    self.error = f'描けませんでした：{e!r}'
            time.sleep(.4)


def serve(watcher, open_browser=True):
    figs = ''.join(f'<figure><figcaption>{html.escape(cap)}</figcaption>'
                   f'<a href="/img/{name}.png" target="_blank"><img data-name="{name}" alt="{html.escape(cap)}"></a></figure>'
                   for name, cap in STATES)
    page = PAGE.replace('__FIGS__', figs).encode('utf-8')

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/':
                body, ctype = page, 'text/html; charset=utf-8'
            elif path == '/state':
                with watcher.lock:
                    body = json.dumps({'version': watcher.version, 'error': watcher.error, 'info': watcher.info,
                                       'load': watcher.load, 'level': watcher.level}).encode()
                ctype = 'application/json'
            elif path.startswith('/img/') and path.endswith('.png'):
                with watcher.lock:
                    body = watcher.images.get(path[5:-4])
                if body is None:
                    self.send_error(404)
                    return
                ctype = 'image/png'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    threading.Thread(target=watcher.loop, daemon=True).start()
    print(f'計器の見た目：{url}')
    print(f'{watcher.ini} を保存するたびに描き直します。止めるときはこの窓を閉じてください。')
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description='走行映像の計器（hud.ini）の見た目をPCで確かめる')
    ap.add_argument('ini', nargs='?', default=str(HERE / 'hud.ini'))
    ap.add_argument('--bg', help='背景の画像（jpg・png）か動画（ts・mp4）')
    ap.add_argument('--once', metavar='DIR', help='3枚をPNGに書いて終わる')
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    watcher = Watcher(args.ini, args.bg)
    if args.once:
        watcher.check()
        if watcher.error:
            sys.exit(watcher.error)
        out = Path(args.once)
        out.mkdir(parents=True, exist_ok=True)
        for name, data in watcher.images.items():
            (out / f'{name}.png').write_bytes(data)
        print(f'{out} に書きました：{", ".join(n + ".png" for n in watcher.images)}')
        print(watcher.load)
        return
    serve(watcher, not args.no_browser)


if __name__ == '__main__':
    main()
