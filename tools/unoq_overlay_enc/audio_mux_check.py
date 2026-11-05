"""音を混ぜた .ts を確かめる（audio_mux_test.c の結果。ffmpeg・ffprobe が要る。PCならWSLで）
  python3 audio_mux_check.py <出力.ts> <t0>
  - 映像・音の流れがあり、ffmpegで最後まで読めること（誤りが出ないこと）
  - 音のPTSが1152サンプル（24ms）ずつ続いていること（抜け・重なり）
  - ピッ（audio_beep.py が CLOCK_MONOTONIC の毎秒の頭に鳴らす）の頭が、PTSから戻した時刻で毎秒の頭に来ること
    （t = PTSの秒 − 0.5 + t0。MP2の符号化の遅れ約10msと、パイプの遅れの分だけ後ろへずれる）
"""
import json
import subprocess
import sys

path, t0 = sys.argv[1], float(sys.argv[2])
info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], capture_output=True, text=True, check=True).stdout)
kinds = {s['codec_type']: s for s in info['streams']}
print('streams:', ', '.join(f"{s['codec_type']} {s['codec_name']}" + (f" {s.get('sample_rate')}Hz {s.get('channels')}ch {s.get('bit_rate')}" if s['codec_type'] == 'audio' else f" {s.get('width')}x{s.get('height')}") for s in info['streams']))
ok = 'video' in kinds and 'audio' in kinds and kinds['audio']['codec_name'] == 'mp2'

err = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True).stderr.strip()
print('decode errors:', err[:500] if err else 'none')
ok = ok and not err

pk = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_packets', '-show_entries', 'packet=pts,duration', '-of', 'json', path],
                               capture_output=True, text=True, check=True).stdout)['packets']
pts = [int(p['pts']) for p in pk if 'pts' in p]
gaps = [b - a for a, b in zip(pts, pts[1:])]
# 1152/48000秒＝2160（90kHz）。時刻の追いかけで1フレームあたり±1%（±22）まで動かす。0.5秒より大きい空きはマイクが止まった所（録り直し）
outages = [(i, g) for i, g in enumerate(gaps) if g > 45000]
bad = [(i, g) for i, g in enumerate(gaps) if abs(g - 2160) > 150 and g <= 45000]  # PESの中はffprobeが2160ずつ補うので、PESの境に数フレーム分（1.7msまで）出る
print(f'audio packets: {len(pts)}, first pts {pts[0] / 90000:.3f} s, last {pts[-1] / 90000:.3f} s, gaps not 24ms: {len(bad)} {bad[:8]}, '
      f'outages: {len(outages)} ' + ' '.join(f'{g / 90000:.2f}s' for _, g in outages))
vp = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_packets', '-show_entries', 'packet=pts', '-of', 'json', path],
                               capture_output=True, text=True, check=True).stdout)['packets']
vpts = [int(p['pts']) for p in vp if 'pts' in p]
print(f'video packets: {len(vpts)}, first pts {vpts[0] / 90000:.3f} s, last {vpts[-1] / 90000:.3f} s')

raw = subprocess.run(['ffmpeg', '-v', 'error', '-copyts', '-i', path, '-map', '0:a', '-af', 'aresample=async=1:first_pts=0',
                      '-f', 's16le', '-ac', '1', '-ar', '48000', '-'], capture_output=True, check=True).stdout
import array
a = array.array('h'); a.frombytes(raw[:len(raw) // 2 * 2])
win, onsets, inside = 240, [], False  # 5msごとの大きさ
for s in range(0, len(a) - win, win):
    e = max(abs(x) for x in a[s:s + win])
    if e > 4000 and not inside:
        onsets.append(s / 48000); inside = True
    elif e < 1000:
        inside = False
fr = []
for tau in onsets:
    t = tau - 0.5 + t0
    fr.append((t + 0.5) % 1.0 - 0.5)  # 毎秒の頭からのずれ（秒）
print('beeps:', len(onsets), 'offset from the second (ms):', ' '.join(f'{x * 1000:+.0f}' for x in fr))
sync = bool(fr) and all(-0.01 <= x <= 0.06 for x in fr)
print('RESULT:', 'OK' if ok and not bad and sync else 'NG')
