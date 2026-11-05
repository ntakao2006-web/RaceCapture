"""EcoCapture DASH（車載画面、task_sugo_20261108_breakdown.md SG-2-6）を本体で確かめる・入れる。

何も付けなければ、本体へは入れずに確かめるだけ（サービス・記録・設定・ほかの画面アプリには触らない）:
  1. 一式を本体の /tmp/ecocapture-dash-check に置き、本体のPythonでDASHの試験（test_dash_model）を流す
  2. 本体のXorg :2（HDMIの画面。モニターが無くても動いている）で全部の状態を描き、PCへ持ち帰る
  3. 本物の走行データで1枚描く（いまの値がどう出るか）
  4. 作り物の走行で30秒動かして、CPU・メモリを測る（同じ間のRaceCaptureアプリと比べる）
  5. HDMIへの音の出口を無音で開け、流せるかだけを見る（音は出ない）
  終わったら /tmp の一式を消す。画像と結果は outputs/dash_check_<日時>/ へ。
--sound warn     : モニターをつないだ状態で、HDMIから警告音（高い「ピピピ…」を6回、約10秒）を1回鳴らす（--volume 既定0.3）。鳴らす前に3秒数える
--install        : 本体へ入れて、今と次の電源ONからDASHにする（rootが要るので、EcoCaptureのDockerイメージから
                   nsenterで install-dash.sh を流す）。戻すのは Show-RaceCapture.cmd --boot

つなぎ方は sugo_setup.py と同じ: 既定は ssh unoq（Pixelのテザリング）、--adb でUSBのadb。
  python dash_check.py
  python dash_check.py --sound warn --volume 0.3
  python dash_check.py --install
"""
import argparse
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / 'RaceCapture-UNOQ'
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))

WORK = '/tmp/ecocapture-dash-check'
CHECK_FILES = ['ecocapture_dash.py', 'dash_model.py', 'test_dash_model.py', 'display_load_control.py']
INSTALL_FILES = ['ecocapture_dash.py', 'dash_model.py', 'display_load_control.py', 'dash_switch.sh',
                 'ecocapture-dash.service', 'ecocapture-dash.sudoers', 'install-dash.sh']
STATES = ['normal', 'start', 'pit', 'pitbox', 'warn', 'warnpress', 'warn2', 'warn3', 'lost', 'stale']
SOUND_DEVICE = 'plughw:CARD=ArduinoImolaHPH,DEV=3'
SOUND_ROUTE = 'SEC_MI2S_RX Audio Mixer MultiMedia4'
# root on the UNO Q without a password (memory: project_unoq_adb_access): the EcoCapture image, nsenter into PID 1
AS_ROOT = 'docker run --rm --privileged --pid=host --user 0 --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 -t 1 -m -p -- /bin/sh -c '
DASH = f'cd {WORK} && DISPLAY=:2 GDK_BACKEND=x11 timeout 40 python3 ecocapture_dash.py --no-pause'


class Device:
    def __init__(self, use_adb, host):
        self.host = host
        self.adb = None
        if use_adb:
            from collect_logs import adb_command
            self.adb = adb_command()
            if not self.adb:
                sys.exit('adbが見つかりません')

    def run(self, command, timeout=200):
        head = [*self.adb, 'shell'] if self.adb else ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', self.host]
        done = subprocess.run([*head, command], capture_output=True, text=True, encoding='utf-8', errors='replace',
                              stdin=subprocess.DEVNULL, timeout=timeout)
        return done.returncode, (done.stdout + done.stderr).strip()

    def put(self, local, remote):
        command = [*self.adb, 'push', str(local), remote] if self.adb else \
            ['scp', '-q', '-o', 'BatchMode=yes', str(local), f'{self.host}:{remote}']
        subprocess.run(command, check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)

    def get(self, remote, local):
        command = [*self.adb, 'pull', remote, str(local)] if self.adb else \
            ['scp', '-q', '-o', 'BatchMode=yes', f'{self.host}:{remote}', str(local)]
        return subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, timeout=120).returncode == 0


def stage(dev, files, folder):
    code, out = dev.run(f'mkdir -p {folder}')
    if code:
        sys.exit(f'本体に {folder} を作れません: {out}')
    for name in files:
        dev.put(SRC / name, f'{folder}/{name}')


def check(dev, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    def note(text):
        print(text); lines.append(text)

    dev.run(f'rm -rf {WORK}')
    stage(dev, CHECK_FILES, WORK)
    dev.run(f"""printf '%s' '{{"sound": {{"enabled": false}}}}' > {WORK}/quiet.json""")
    code, out = dev.run(f'cd {WORK} && python3 -m unittest test_dash_model 2>&1 | grep -E "^(Ran|OK|FAILED)" | tr "\n" " "')
    note(f'1. 本体での試験: {"通った" if " OK" in f" {out}" else "★失敗"}（{out.strip()}）')

    _, screen = dev.run("DISPLAY=:2 xdpyinfo 2>/dev/null | grep dimensions | awk '{print $2}'; cat /sys/class/drm/card0-DP-1/status")
    note(f'2. 画面 :2 の大きさと、HDMI: {" / ".join(screen.split())}')
    if dev.run('systemctl is-active racecapture-touch.service')[1].strip() == 'active':
        note('   （画像の上の暗い帯は、動いているタッチの切り替えバーが重なったもの。DASHを入れるとバーは止まる）')
    for state in STATES:
        code, out = dev.run(f'{DASH} --config {WORK}/quiet.json --state {state} --snapshot {WORK}/{state}.png')
        got = code == 0 and dev.get(f'{WORK}/{state}.png', out_dir / f'{state}.png')
        note(f'   {state}: {"描けた" if got else "★描けない " + out[-300:]}')

    code, out = dev.run(f'{DASH} --config {WORK}/quiet.json --snapshot {WORK}/live.png')
    got = code == 0 and dev.get(f'{WORK}/live.png', out_dir / 'live.png')
    note(f'3. 本物の走行データで: {"描けた（live.png）" if got else "★描けない " + out[-300:]}')

    measure = f"""
cd {WORK}
hz=$(getconf CLK_TCK)
DISPLAY=:2 GDK_BACKEND=x11 python3 ecocapture_dash.py --no-pause --demo --config {WORK}/quiet.json >/dev/null 2>&1 &
P=$!
sleep 8
ticks() {{ [ $# -gt 0 ] || {{ echo 0; return; }}; awk '{{s+=$14+$15}} END {{print s+0}}' "$@" </dev/null 2>/dev/null; }}
rc() {{ for p in $(cat /sys/fs/cgroup/system.slice/racecapture-app.service/cgroup.procs 2>/dev/null); do echo /proc/$p/stat; done; }}
a=$(ticks /proc/$P/stat); r1=$(ticks $(rc)); sleep 30
b=$(ticks /proc/$P/stat); r2=$(ticks $(rc))
rss=$(awk '/VmRSS/ {{print $2}}' /proc/$P/status)
temp=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1)
kill $P; wait $P 2>/dev/null
echo "$(( (b - a) * 100 / (30 * hz) )) $(( (r2 - r1) * 100 / (30 * hz) )) $rss $temp"
"""
    code, out = dev.run(measure, timeout=120)
    try:
        dash_cpu, rc_cpu, rss, temp = out.split()[-4:]
        note(f'4. 負荷（30秒）: DASH 1コアの{dash_cpu}%・{int(rss) // 1024}MB、同じ間のRaceCaptureアプリ {rc_cpu}%、本体の温度 {int(temp) / 1000:.0f}℃')
    except ValueError:
        note(f'4. 負荷: ★測れない {out[-300:]}')

    silent = f"""cd {WORK} && python3 -c "import dash_model; open('silent.wav', 'wb').write(dash_model.tone_wav('warn', 0.0))" &&
amixer -c ArduinoImolaHPH cget name='{SOUND_ROUTE}' | tail -1; aplay -q -D {SOUND_DEVICE} silent.wav; echo "rc=$?" """
    code, out = dev.run(silent)
    note(f'5. HDMIへの音の出口（無音）: {"流せた" if "rc=0" in out else "★流せない"}（{" ".join(out.split())[:300]}）')

    dev.run(f'rm -rf {WORK}')
    (out_dir / 'result.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'画像と結果: {out_dir}')
    return 0 if all('★' not in line for line in lines) else 1


def sound(dev, kind, volume):
    dev.run(f'rm -rf {WORK}')
    stage(dev, ['ecocapture_dash.py', 'dash_model.py'], WORK)
    length = '高い「ピピピ…」を6回（約10秒）'
    for k in (3, 2, 1):
        print(f'{k}秒後に本体のHDMIから鳴らします：{length}、音量{volume}')
        time.sleep(1)
    code, out = dev.run(f'cd {WORK} && python3 ecocapture_dash.py --sound {kind} --volume {volume}; echo "rc=$?"; '
                        f"amixer -c ArduinoImolaHPH cget name='{SOUND_ROUTE}' | tail -1")
    dev.run(f'rm -rf {WORK}')
    print('鳴らし終えました（本体の上では正常に流れた）' if 'rc=0' in out else f'★本体で流せませんでした: {out}')
    print('モニターのスピーカーから聞こえたかを確かめてください。聞こえなければ、HD7Hの音量・ミュートを見てから、'
          'USBのオーディオとスピーカーへ切り替える（~/.config/ecocapture-dash.json の sound.device）')
    return 0 if 'rc=0' in out else 1


def install(dev):
    stage(dev, INSTALL_FILES, '/home/arduino/RaceCapture-UNOQ')
    _, before = dev.run('systemctl is-enabled racecapture-app.service racecapture-touch.service 2>&1 | tr "\\n" " "')
    print(f'入れる前の電源ON時の起動: racecapture-app・racecapture-touch = {before}')
    code, out = dev.run(AS_ROOT + shlex.quote('sh /home/arduino/RaceCapture-UNOQ/install-dash.sh'), timeout=300)
    print(out[-1500:])
    if code:
        print('★入れられませんでした。RaceCaptureアプリのままです（必要なら Show-RaceCapture.cmd --boot）')
        return 1
    time.sleep(8)
    _, status = dev.run('systemctl is-active ecocapture-dash.service; journalctl -u ecocapture-dash -n 5 --no-pager 2>/dev/null | tail -5')
    print(f'DASHのサービス: {status}')
    print('戻すとき: tools/sugo_setup/Show-RaceCapture.cmd --boot')
    return 0 if status.startswith('active') else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sound', choices=['warn'], help='モニターをつないだ状態で警告音を1回鳴らす')
    parser.add_argument('--volume', type=float, default=0.3)
    parser.add_argument('--install', action='store_true', help='本体へ入れて、今と次の電源ONからDASHにする')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    dev = Device(args.adb, args.host)
    if args.sound:
        return sound(dev, args.sound, args.volume)
    if args.install:
        return install(dev)
    return check(dev, REPO / 'outputs' / f'dash_check_{datetime.now():%Y%m%d_%H%M}')


if __name__ == '__main__':
    sys.exit(main())
