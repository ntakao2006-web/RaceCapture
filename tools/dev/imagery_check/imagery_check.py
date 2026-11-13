"""航空写真の位置の正しさを、走った跡を重ねて測る（SP-4-12）。

考え方：サーキットを何十周も走った跡は、舗装の上にしか乗らない。写真が実際の位置からずれていると、
跡の一部が舗装の外（芝・縁石の外）にはみ出す。そこで、跡を東西・南北へ少しずつずらしながら
「舗装の色の上に乗っている点の割合」を数え、割合がいちばん高くなるずらし方を、その写真のずれと見る。

  python tools/dev/imagery_check/imagery_check.py <sd_nav.pkl> <出力フォルダー> [開始UTC 終了UTC]

- 走った跡は tools/race_analysis/sd_gnss.py が作る sd_nav.pkl（SDの10Hzの解）。60 km/h以上・3D測位・誤差2 m以下だけを使う
- 写真は国土地理院（seamlessphoto）とEsri（World Imagery）のズーム18。出力フォルダーの tiles/ に取り置く
- 出力は位置を含むので、リポジトリの外（drive_logs の下）へ出すこと
"""
import io, math, os, sys, time, urllib.request
import numpy as np, pandas as pd
from PIL import Image, ImageDraw

Z = 18
SOURCES = {
    'gsi': ('国土地理院 seamlessphoto', 'https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg'),
    'esri': ('Esri World Imagery', 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'),
}


def tile_xy(lat, lon, z=Z):
    n = 2 ** z
    r = np.radians(lat)
    return (lon + 180) / 360 * n, (1 - np.log(np.tan(r) + 1 / np.cos(r)) / math.pi) / 2 * n


def fetch(name, url, x, y, folder):
    path = os.path.join(folder, f'{name}_{Z}_{x}_{y}.jpg')
    if not os.path.exists(path):
        req = urllib.request.Request(url.format(z=Z, x=x, y=y), headers={'User-Agent': 'imagery-check/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, 'wb') as f:
            f.write(data)
        time.sleep(0.05)
    return Image.open(path).convert('RGB')


def mosaic(name, url, x0, x1, y0, y1, folder):
    img = Image.new('RGB', ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            img.paste(fetch(name, url, x, y, folder), ((x - x0) * 256, (y - y0) * 256))
    return img


def asphalt_mask(rgb, px, py):
    """跡の点の下の色（ほとんどが舗装）から舗装の色の範囲を決め、その範囲の画素を舗装とする。"""
    a = rgb.astype(np.float32)
    val = a.mean(axis=2)
    sat = a.max(axis=2) - a.min(axis=2)
    v, s = val[py, px], sat[py, px]
    v_lo, v_hi = np.percentile(v, [10, 90])
    s_hi = np.percentile(s, 90)
    pad = (v_hi - v_lo) * 0.25
    return (val >= v_lo - pad) & (val <= v_hi + pad) & (sat <= s_hi)


def main():
    nav_path, out = sys.argv[1], sys.argv[2]
    t0, t1 = (sys.argv[3], sys.argv[4]) if len(sys.argv) > 4 else (None, None)
    os.makedirs(os.path.join(out, 'tiles'), exist_ok=True)
    nav = pd.read_pickle(nav_path)
    kmh = nav.gspeed * (3.6 if nav.gspeed.quantile(0.99) < 80 else 1)   # m/s で入っていれば km/h に
    ok = (nav.fix == 3) & (kmh >= 60) & (nav.hacc <= 2.0)
    if t0:
        ok &= (nav.utc >= t0) & (nav.utc <= t1)
    p = nav[ok]
    print(f'使う点 {len(p)}（全体 {len(nav)}）  誤差の中央 {p.hacc.median():.2f} m  速さの中央 {kmh[ok].median():.0f} km/h')
    lat, lon = p.lat.to_numpy(), p.lon.to_numpy()
    tx, ty = tile_xy(lat, lon)
    x0, x1, y0, y1 = int(tx.min()) - 1, int(tx.max()) + 1, int(ty.min()) - 1, int(ty.max()) + 1
    mpp = 156543.03392 * math.cos(math.radians(lat.mean())) / 2 ** Z
    print(f'写真 {x1 - x0 + 1}×{y1 - y0 + 1}枚  1画素 {mpp:.3f} m')
    fx, fy = (tx - x0) * 256, (ty - y0) * 256
    head = np.radians(p['head'].to_numpy())
    rows = []
    for name, (label, url) in SOURCES.items():
        img = mosaic(name, url, x0, x1, y0, y1, os.path.join(out, 'tiles'))
        rgb = np.asarray(img)
        H, W = rgb.shape[:2]
        mask = asphalt_mask(rgb, np.clip(fx.round().astype(int), 0, W - 1), np.clip(fy.round().astype(int), 0, H - 1))
        steps = np.arange(-8, 8.01, 0.25)   # m
        frac = np.zeros((len(steps), len(steps)))
        for i, north in enumerate(steps):
            for j, east in enumerate(steps):
                xi = np.clip((fx + east / mpp).round().astype(int), 0, W - 1)
                yi = np.clip((fy - north / mpp).round().astype(int), 0, H - 1)
                frac[i, j] = mask[yi, xi].mean()
        zero = frac[len(steps) // 2, len(steps) // 2]
        top = frac.max()
        w = np.clip(frac - (top - (top - np.median(frac)) * 0.15), 0, None)   # いちばん高い所の近くだけで重心を取る
        north = (w.sum(axis=1) * steps).sum() / w.sum()
        east = (w.sum(axis=0) * steps).sum() / w.sum()
        # 進む向きごと：東西に走る区間は南北のずれに、南北に走る区間は東西のずれに敏感
        ew = np.abs(np.sin(head)) > 0.9
        ns = np.abs(np.cos(head)) > 0.9

        def best(sel, axis):
            vals = []
            for d in steps:
                xi = np.clip((fx[sel] + (d if axis == 'e' else 0) / mpp).round().astype(int), 0, W - 1)
                yi = np.clip((fy[sel] - (d if axis == 'n' else 0) / mpp).round().astype(int), 0, H - 1)
                vals.append(mask[yi, xi].mean())
            vals = np.array(vals)
            ww = np.clip(vals - (vals.max() - (vals.max() - vals.min()) * 0.1), 0, None)
            return (ww * steps).sum() / ww.sum(), vals.max()

        n_ew, _ = best(ew, 'n')
        e_ns, _ = best(ns, 'e')
        rows.append(dict(source=label, on_asphalt_at_zero=round(float(zero), 4), on_asphalt_best=round(float(top), 4),
                         shift_north_m=round(float(north), 2), shift_east_m=round(float(east), 2),
                         north_from_eastwest_runs_m=round(float(n_ew), 2), east_from_northsouth_runs_m=round(float(e_ns), 2),
                         points_ew=int(ew.sum()), points_ns=int(ns.sum())))
        pd.DataFrame(frac, index=steps, columns=steps).to_csv(os.path.join(out, f'{name}_grid.csv'))
        # 目で見る用：跡を重ねた全体と、ホームストレートの拡大
        over = img.copy()
        d = ImageDraw.Draw(over)
        for x, y in zip(fx[::7], fy[::7]):
            d.point((x, y), fill=(255, 40, 40))
        small = over.copy()
        small.thumbnail((1600, 1600))
        small.save(os.path.join(out, f'{name}_overlay.jpg'), quality=85)
        # 東西に走る点がいちばん多いあたり（ホームストレート）を等倍で切り出す
        cx, cy = np.median(fx[ew]), np.median(fy[ew])
        box = (int(cx - 500), int(cy - 250), int(cx + 500), int(cy + 250))
        over.crop(box).resize((2000, 1000), Image.LANCZOS).save(os.path.join(out, f'{name}_straight.jpg'), quality=90)
        Image.fromarray((mask * 255).astype(np.uint8)).crop(box).save(os.path.join(out, f'{name}_mask_straight.png'))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(out, 'imagery_check.csv'), index=False)
    print(res.T.to_string())
    print('ずれの読み方：shift_north_m が +2 なら、跡を北へ2 mずらすと写真の舗装にいちばんよく乗る＝写真が北へ2 mずれている')


if __name__ == '__main__':
    main()
