#!/usr/bin/env python3
"""フロー制御つきの送信（Linux → SPI → STM32 → SD の通し試験用）。

エンコーダが一定レートで映像を出す状況を模擬する：
  ・「生産量」は時間に比例して増える（rate KB/s）。送れなかった分は Linux 側に溜まる（＝必要なバッファ量を記録）
  ・STM32 から Bridge 経由で「SDへ書き終えたバイト数」（spitest.rd）を読み、
    送った量 − 書き終えた量 + 次の塊 ≦ 受け皿（RING）のときだけ送る（クレジット方式）

使い方: python3 spi_fc.py <速度Hz> <合計MB> <生産レートKB/s> [塊バイト=32768]
事前に試験ファームで sdinit 済み・e2e 実行中であること。spidev は bufsiz を広げておくこと。
"""
import array
import fcntl
import socket
import struct
import sys
import time

from spitest import pack, unpack, SOCK

SPI_IOC_MESSAGE_1 = 0x40206B00   # _IOW('k', 0, struct spi_ioc_transfer[1])
SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04
RING = 65536                     # 試験ファームの受け皿


class Rpc:
    """arduino-router への接続を張りっぱなしにして呼ぶ（毎回つなぎ直すと遅い）"""

    def __init__(self):
        self.s = socket.socket(socket.AF_UNIX); self.s.settimeout(5); self.s.connect(SOCK)
        self.id = 100; self.buf = b''

    def call(self, method, args=()):
        self.id += 1
        self.s.sendall(pack([0, self.id, method, list(args)]))
        while True:
            try:
                msg, n = unpack(self.buf)
                self.buf = self.buf[n:]
                if msg[1] == self.id:
                    if msg[2]:
                        raise RuntimeError(msg[2])
                    return msg[3]
                continue
            except (IndexError, ValueError):
                self.buf += self.s.recv(65536)


def main():
    hz, total_mb, rate_kbs = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    chunk = int(sys.argv[4]) if len(sys.argv) > 4 else 32768
    total = int(total_mb * 1024 * 1024) // chunk * chunk
    rate = rate_kbs * 1000
    fd = open('/dev/spidev0.0', 'rb+', buffering=0)
    fcntl.ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, struct.pack('I', hz))
    rpc = Rpc()
    u32 = lambda v: v & 0xFFFFFFFF
    r0 = u32(rpc.call('spitest.rd'))
    sent = ctr = done = 0
    max_backlog = waits = polls = 0
    rpc_ms = []
    t0 = time.time()
    while sent < total:
        produced = min(total, int(rate * (time.time() - t0)))
        if produced - sent < chunk:
            time.sleep(0.001); continue
        if sent - done + chunk > RING:  # 手元の記録で空きが足りないときだけ問い合わせる
            t = time.time()
            done = u32(u32(rpc.call('spitest.rd')) - r0); polls += 1
            rpc_ms.append((time.time() - t) * 1000)
            if sent - done + chunk > RING:
                waits += 1; time.sleep(0.001); continue
        buf = array.array('I', range(ctr, ctr + chunk // 4)); ctr += chunk // 4
        addr, _ = buf.buffer_info()
        tr = struct.pack('<QQIIHBBBBBB', addr, 0, chunk, hz, 0, 8, 0, 0, 0, 0, 0)
        fcntl.ioctl(fd, SPI_IOC_MESSAGE_1, tr)
        sent += chunk
        max_backlog = max(max_backlog, produced - sent + chunk)
    el = time.time() - t0
    rpc_ms.sort(); rpc_ms = rpc_ms or [0]
    print(f'sent {sent/1e6:.1f}MB in {el:.1f}s = {sent/el/1e3:.0f}KB/s (目標 {rate_kbs:.0f}KB/s)  '
          f'Linux側に溜まった最大量={max_backlog/1024:.0f}KB  空き待ち={waits}回  '
          f'rd問い合わせ {polls}回 中央値{rpc_ms[len(rpc_ms)//2]:.1f}ms 最大{rpc_ms[-1]:.1f}ms  last_word={ctr-1}')


if __name__ == '__main__':
    main()
