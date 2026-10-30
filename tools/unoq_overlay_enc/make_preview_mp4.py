"""焼き込み録画（.ts、1080p・10Mbps）から、見る・送る用の小さいMP4を作る（PCのVLCを使う）。

  python make_preview_mp4.py <録画.ts> <出力.mp4> [--start 60] [--stop 150] [--width 960] [--kbps 1500]

- VLCで縮めてH.264にし直す。キーフレームは元の録画と同じく約1秒ごと（32コマごと）にする
- VLCのMP4は、1コマ目がキーフレーム（IDR）なのに目次（stss）に入れないことがある。ブラウザ等は目次で最初の
  キーフレームを探すので、次のキーフレームまで絵が止まって見える（2026-10-30、手順書5-15）。書いたあとで目次に1コマ目を足す
- 元の .ts は1秒ごとにIDRがあり、そのままで正しく再生できる（これは見る・送る用の写しを作るだけ）
"""
import argparse
import struct
import subprocess
import sys
from pathlib import Path

VLC = Path(r'C:\Program Files\VideoLAN\VLC\vlc.exe')
CONTAINERS = {b'moov', b'trak', b'mdia', b'minf', b'stbl', b'edts', b'dinf', b'udta', b'mvex'}


def parse(b, off, end):
    """[(種類, 中身 or 子の一覧)]"""
    out = []
    while off + 8 <= end:
        size, typ = struct.unpack('>I4s', b[off:off + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack('>Q', b[off + 8:off + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - off
        body = (parse(b, off + hdr, off + size) if typ in CONTAINERS else b[off + hdr:off + size])
        out.append([typ, body])
        off += size
    return out


def build(boxes):
    out = b''
    for typ, body in boxes:
        data = build(body) if isinstance(body, list) else body
        out += struct.pack('>I4s', 8 + len(data), typ) + data
    return out


def walk(boxes, typ):
    for box in boxes:
        if box[0] == typ:
            yield box
        if isinstance(box[1], list):
            yield from walk(box[1], typ)


def fix_first_keyframe(path):
    """目次（stss）に1コマ目が無ければ足す。足したら True"""
    b = Path(path).read_bytes()
    top = parse(b, 0, len(b))
    order = [t for t, _ in top]
    if b'moov' not in order or b'mdat' not in order:
        raise RuntimeError(f'{path}: moov・mdat が見つかりません')
    moov = next(box for box in top if box[0] == b'moov')
    old = len(build([moov]))  # 目次を直す前の大きさ（後ろのmdatがずれる量を出すのに使う）
    changed = False
    for stss in walk(moov[1], b'stss'):
        body = stss[1]
        n = struct.unpack('>I', body[4:8])[0]
        samples = list(struct.unpack(f'>{n}I', body[8:8 + 4 * n]))
        if samples and samples[0] != 1:
            stss[1] = body[:4] + struct.pack(f'>I{n + 1}I', n + 1, 1, *samples)
            changed = True
    if not changed:
        return False
    delta = 0
    if order.index(b'moov') < order.index(b'mdat'):  # moov が前にあると、mdat が後ろへずれる分を足す
        delta = len(build([moov])) - old
        if delta:
            for stco in walk(moov[1], b'stco'):
                n = struct.unpack('>I', stco[1][4:8])[0]
                offs = struct.unpack(f'>{n}I', stco[1][8:8 + 4 * n])
                stco[1] = stco[1][:8] + struct.pack(f'>{n}I', *(o + delta for o in offs))
            for co64 in walk(moov[1], b'co64'):
                n = struct.unpack('>I', co64[1][4:8])[0]
                offs = struct.unpack(f'>{n}Q', co64[1][8:8 + 8 * n])
                co64[1] = co64[1][:8] + struct.pack(f'>{n}Q', *(o + delta for o in offs))
    Path(path).write_bytes(build(top))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--start', type=float)
    ap.add_argument('--stop', type=float)
    ap.add_argument('--width', type=int, default=960)
    ap.add_argument('--kbps', type=int, default=1500)
    args = ap.parse_args()
    if not VLC.exists():
        sys.exit(f'VLCが見つかりません：{VLC}')
    dst = Path(args.dst).resolve()
    height = args.width * 9 // 16
    sout = (f'#transcode{{vcodec=h264,venc=x264{{keyint=32,min-keyint=32}},vb={args.kbps},width={args.width},'
            f'height={height},acodec=none}}:std{{access=file,mux=mp4,dst="{dst}"}}')
    cmd = [str(VLC), '-I', 'dummy', '--dummy-quiet', '--no-repeat', '--no-loop']
    if args.start is not None:
        cmd.append(f'--start-time={args.start}')
    if args.stop is not None:
        cmd.append(f'--stop-time={args.stop}')
    cmd += [str(Path(args.src).resolve()), '--sout', sout, 'vlc://quit']
    subprocess.run(cmd, check=True)
    if not dst.exists():
        sys.exit('VLCがMP4を書きませんでした')
    fixed = fix_first_keyframe(dst)
    print(f'{dst}（{dst.stat().st_size / 1048576:.1f}MiB）' + ('。1コマ目をキーフレームの目次に足した' if fixed else ''))


if __name__ == '__main__':
    main()
