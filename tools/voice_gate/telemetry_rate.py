"""Telemetry rows per second and voice counters of the logger, from its own status API (ER-10-6).

Runs on the UNO Q host:  python3 telemetry_rate.py 60 [label]
Prints one line per 5 s and a summary, so voice on/off can be compared on the same link.
"""
import json
import sys
import time
import urllib.request

URL = 'http://127.0.0.1:8080/api/podium'


def status():
    with urllib.request.urlopen(URL, timeout=3) as r:
        return json.load(r)['status']


def main(seconds, label=''):
    first = last = status()
    t0 = tl = time.monotonic()
    rates = []
    while time.monotonic() - t0 < seconds:
        time.sleep(5)
        s, now = status(), time.monotonic()
        rate = (s['frames'] - last['frames']) / (now - tl)
        rates.append(rate)
        print(f"{now - t0:5.0f}s  {rate:4.1f} 件/秒  state={s['state']} link={s.get('active_link')} voice={s['voice']}"
              f" 受信{s['voice_packets'] - last['voice_packets']:3d} 送信{s['voice_sent'] - last['voice_sent']:3d}"
              f" 一時停止{s['voice_pauses']} 再接続{s['reconnects']} 最終送信{s['last_sent_age_ms']}ms", flush=True)
        last, tl = s, now
    total = (last['frames'] - first['frames']) / (tl - t0)
    print(f"[{label}] 平均 {total:.2f} 件/秒（5秒ごとの最小 {min(rates):.1f}・最大 {max(rates):.1f}）"
          f" 音声受信 {last['voice_packets'] - first['voice_packets']} 件・送信 {last['voice_sent'] - first['voice_sent']} 件"
          f" 一時停止 {last['voice_pauses'] - first['voice_pauses']} 回・再接続 {last['reconnects'] - first['reconnects']} 回"
          f" 理由 {last.get('voice_reason')}")


if __name__ == '__main__':
    main(float(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else '')
