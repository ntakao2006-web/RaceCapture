"""小さなQRコードの作り手（2026-11-13、SP-3・SP-6-3）。

PCからスマホへ合言葉を渡すQR（phone_key.py）のためのもの。合言葉を外の部品やWebのサービスへ渡さないように、
Pythonの標準の部品だけで作る（入れるものを増やさない）。できるのは次の形だけ:
  バイトモード・誤り訂正レベルM・バージョン1〜10（213バイトまで）。表紙のURL＋合言葉は110バイトほど。

  matrix = qr.make(b'https://...')   # 行のリスト。1が黒。まわりの白い余白は含まない

仕様は JIS X 0510（ISO/IEC 18004）。試験（test_phone_key.py）で、PCに segno があれば同じ絵になることを確かめる。
"""

# バージョン → (誤り訂正の語数/ブロック, [(ブロック数, データの語数), ...])。レベルM
BLOCKS = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
         9: [6, 26, 46], 10: [6, 28, 50]}
MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0,
         lambda x, y: (x // 3 + y // 2) % 2 == 0, lambda x, y: x * y % 2 + x * y % 3 == 0,
         lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0, lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]

# GF(256) の表（x^8+x^4+x^3+x^2+1）
EXP, LOG = [0] * 512, [0] * 256
_v = 1
for _i in range(255):
    EXP[_i], LOG[_v] = _v, _i
    _v <<= 1
    if _v & 0x100:
        _v ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def capacity(version):
    """そのバージョンに入るバイト数（バイトモード・レベルM）"""
    data = sum(n * k for n, k in BLOCKS[version][1])
    return (data * 8 - 4 - (8 if version < 10 else 16)) // 8


def rs_remainder(data, n):
    """リード・ソロモンの誤り訂正の語（n個）"""
    gen = [1]
    for i in range(n):   # gen(x) *= (x - α^i)：「x倍」と「α^i倍」を足す
        gen = [a ^ (EXP[LOG[b] + i] if b else 0) for a, b in zip(gen + [0], [0] + gen)]
    rem = [0] * n
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i in range(n):
                if gen[i + 1]:
                    rem[i] ^= EXP[LOG[gen[i + 1]] + LOG[factor]]
    return rem


def codewords(data, version):
    """データ → 並べる語の列（詰め物・誤り訂正・ブロックの混ぜ合わせまで）"""
    ec, groups = BLOCKS[version]
    total = sum(n * k for n, k in groups)
    bits = [0, 1, 0, 0] + [(len(data) >> i) & 1 for i in range(7 if version < 10 else 15, -1, -1)]
    for byte in data:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, total * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    words += [(0xEC, 0x11)[i % 2] for i in range(total - len(words))]
    blocks, at = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[at:at + size])
            at += size
    eccs = [rs_remainder(b, ec) for b in blocks]
    out = [b[i] for i in range(max(map(len, blocks))) for b in blocks if i < len(b)]
    return out + [e[i] for i in range(ec) for e in eccs]


def bch(value, bits, gen):
    """value のあとへ付ける BCH の余り（形式・バージョンの情報用）"""
    rem = value << bits
    top = rem.bit_length()
    for i in range(top - 1, bits - 1, -1):
        if rem >> i & 1:
            rem ^= gen << (i - bits)
    return rem


def build(version, words, mask):
    """決まった模様を置き、語を並べ、マスクをかけた絵を返す"""
    size = version * 4 + 17
    m = [[0] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        if 0 <= x < size and 0 <= y < size:
            m[y][x], fixed[y][x] = int(bool(dark)), True

    for i in range(size):                      # タイミング
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):   # 位置の目印（まわりの白い帯も）
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    pos = ALIGN[version]
    for cy in pos:                             # 位置合わせの小さい目印
        for cx in pos:
            if (cx, cy) in ((6, 6), (6, pos[-1]), (pos[-1], 6)):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    fmt = ((mask << 10) | bch(mask, 10, 0x537)) ^ 0x5412    # レベルMは上の2ビットが00
    bit = lambda v, i: v >> i & 1  # noqa: E731
    for i in range(6):
        put(8, i, bit(fmt, i))
    put(8, 7, bit(fmt, 6)); put(8, 8, bit(fmt, 7)); put(7, 8, bit(fmt, 8))  # noqa: E702
    for i in range(9, 15):
        put(14 - i, 8, bit(fmt, i))
    for i in range(8):
        put(size - 1 - i, 8, bit(fmt, i))
    for i in range(8, 15):
        put(8, size - 15 + i, bit(fmt, i))
    put(8, size - 8, 1)
    if version >= 7:
        info = (version << 12) | bch(version, 12, 0x1F25)
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            put(a, b, bit(info, i))
            put(b, a, bit(info, i))
    i, right, test = 0, size - 1, MASKS[mask]   # 語を右下からジグザグに置く
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if (right + 1) & 2 == 0 else vert
                if fixed[y][x]:
                    continue
                dark = i < len(words) * 8 and words[i >> 3] >> (7 - (i & 7)) & 1
                m[y][x] = int(bool(dark) ^ test(x, y))
                i += 1
        right -= 2
    return m


def penalty(m):
    """読みにくさの点（小さいほど良い）。マスクを選ぶのに使う"""
    size, score = len(m), 0
    lines = [''.join(map(str, row)) for row in m] + [''.join(str(m[y][x]) for y in range(size)) for x in range(size)]
    for line in lines:
        run = 1
        for a, b in zip(line, line[1:] + 'x'):
            if a == b:
                run += 1
            else:
                score += run - 2 if run >= 5 else 0
                run = 1
        for pattern in ('10111010000', '00001011101'):
            at = line.find(pattern)
            while at >= 0:
                score += 40
                at = line.find(pattern, at + 1)
    for y in range(size - 1):
        for x in range(size - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    dark = sum(map(sum, m))
    return score + abs(dark * 20 - size * size * 10) // (size * size) * 10   # 黒の割合が50%から5%ずれるごとに10点


def make(data, mask=None):
    """QRの絵（行のリスト、1が黒）。data はバイト列。入りきらなければ ValueError"""
    data = bytes(data)
    version = next((v for v in BLOCKS if len(data) <= capacity(v)), None)
    if version is None:
        raise ValueError(f'長すぎてQRに入りません（{len(data)}バイト。{capacity(10)}バイトまで）')
    words = codewords(data, version)
    if mask is not None:
        return build(version, words, mask)
    return min((build(version, words, k) for k in range(8)), key=penalty)
