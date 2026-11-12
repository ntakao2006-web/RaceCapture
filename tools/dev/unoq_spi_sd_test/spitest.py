#!/usr/bin/env python3
"""試験ファーム（unoq_spi_sd_test）へ arduino-router 経由で命令を送り、状態を読む。

UNO Q 本体の Python には msgpack が無いので、必要な分だけの MessagePack を自前で持つ。
使い方: python3 spitest.py stat
        python3 spitest.py cmd "sdinit"   （命令を送り、完了するまで待って結果を表示）
"""
import json
import socket
import struct
import sys
import time

SOCK = '/var/run/arduino-router.sock'


def pack(o):
    if isinstance(o, bool):
        return b'\xc3' if o else b'\xc2'
    if isinstance(o, int):
        if 0 <= o < 128:
            return bytes([o])
        return b'\xce' + struct.pack('>I', o)
    if isinstance(o, str):
        b = o.encode()
        return (bytes([0xa0 | len(b)]) if len(b) < 32 else b'\xd9' + bytes([len(b)])) + b
    if isinstance(o, list):
        return bytes([0x90 | len(o)]) + b''.join(pack(x) for x in o)
    raise TypeError(o)


def unpack(b, i=0):
    t = b[i]
    if t < 0x80:
        return t, i + 1
    if 0x90 <= t <= 0x9f:
        out = []; i += 1
        for _ in range(t & 15):
            v, i = unpack(b, i); out.append(v)
        return out, i
    if 0xa0 <= t <= 0xbf:
        n = t & 31; return b[i + 1:i + 1 + n].decode(), i + 1 + n
    if t == 0xc0:
        return None, i + 1
    if t in (0xc2, 0xc3):
        return t == 0xc3, i + 1
    if t == 0xd9:
        n = b[i + 1]; return b[i + 2:i + 2 + n].decode(), i + 2 + n
    if t == 0xda:
        n = struct.unpack('>H', b[i + 1:i + 3])[0]; return b[i + 3:i + 3 + n].decode(), i + 3 + n
    if t == 0xcc:
        return b[i + 1], i + 2
    if t == 0xcd:
        return struct.unpack('>H', b[i + 1:i + 3])[0], i + 3
    if t == 0xce:
        return struct.unpack('>I', b[i + 1:i + 5])[0], i + 5
    if t == 0xd0:
        return struct.unpack('>b', b[i + 1:i + 2])[0], i + 2
    if t == 0xd2:
        return struct.unpack('>i', b[i + 1:i + 5])[0], i + 5
    if t >= 0xe0:
        return t - 256, i + 1
    raise ValueError(hex(t))


def call(method, args, msgid=[1]):
    s = socket.socket(socket.AF_UNIX); s.settimeout(15); s.connect(SOCK)
    msgid[0] += 1
    s.sendall(pack([0, msgid[0], method, args]))
    buf = b''
    while True:
        buf += s.recv(65536)
        try:
            msg, _ = unpack(buf)
            if msg[1] == msgid[0]:
                s.close()
                if msg[2]:
                    raise RuntimeError(msg[2])
                return msg[3]
        except (IndexError, ValueError):
            continue


def stat():
    return json.loads(call('spitest.stat', []))


if __name__ == '__main__':
    if sys.argv[1] == 'stat':
        print(json.dumps(stat(), ensure_ascii=False))
    elif sys.argv[1] == 'cmd':
        before = stat()['completed']
        call('spitest.cmd', [sys.argv[2]])
        end = time.time() + float(sys.argv[3]) if len(sys.argv) > 3 else time.time() + 600
        while time.time() < end:
            time.sleep(0.5)
            try:
                st = stat()
            except Exception:
                continue  # 書き込み中はBridgeの応答が遅れることがある
            if st['completed'] > before:
                print(json.dumps(st, ensure_ascii=False)); break
