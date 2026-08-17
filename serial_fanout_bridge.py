#!/usr/bin/env python3
"""
ESP32実機の1本のUSBシリアルポートを、race_captureの複数インスタンスが
同時に読み取れるようにするfan-outブリッジ。

設計:
- 実ポート(例: /dev/ttyACM0)を本デーモンだけが唯一readする
- pty.openpty()で仮想ポートをconsumer数ぶん作成し、slave側に安定したパスで
  シンボリックリンクを張る(race_capture側の`last_known_device`にはこのリンク先を設定する)
- 実ポートから読んだバイト列を、そのまま全consumerのmaster側へブロードキャストする
- 書き込み方向(コマンド送信)はサポートしない。表示専用用途のみを想定
"""
import argparse
import errno
import os
import select
import sys
import time

import serial


def create_virtual_port(link_path):
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    if os.path.islink(link_path) or os.path.exists(link_path):
        os.remove(link_path)
    os.symlink(slave_path, link_path)
    return master_fd, slave_path


def open_real_port(device, baudrate):
    return serial.Serial(device, baudrate=baudrate, timeout=1)


def main():
    parser = argparse.ArgumentParser(description="ESP32シリアルポートのfan-outブリッジ")
    parser.add_argument("--device", required=True, help="実ポート (例: /dev/ttyACM0)")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument(
        "--link",
        action="append",
        required=True,
        help="仮想ポートのリンク先パス。複数指定可 (例: --link /tmp/rc_vport1 --link /tmp/rc_vport2)",
    )
    args = parser.parse_args()

    consumers = {}  # master_fd -> link_path
    for link_path in args.link:
        master_fd, slave_path = create_virtual_port(link_path)
        consumers[master_fd] = link_path
        print("virtual port ready: {} -> {}".format(link_path, slave_path), flush=True)

    ser = None
    while True:
        try:
            if ser is None:
                ser = open_real_port(args.device, args.baudrate)
                print("real port opened: {}".format(args.device), flush=True)

            data = ser.read(4096)
            if not data:
                continue

            dead = []
            for master_fd in consumers:
                try:
                    os.write(master_fd, data)
                except OSError as e:
                    # consumer側がまだ何も開いていない(EIO)場合は無視して継続
                    if e.errno not in (errno.EIO, errno.EAGAIN):
                        dead.append(master_fd)
            for fd in dead:
                print("consumer fd {} write failed, dropping".format(fd), flush=True)
                del consumers[fd]

        except serial.SerialException as e:
            print("real port error: {}. reconnecting in 1s...".format(e), flush=True)
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            ser = None
            time.sleep(1)
        except KeyboardInterrupt:
            break

    if ser is not None:
        ser.close()


if __name__ == "__main__":
    main()
