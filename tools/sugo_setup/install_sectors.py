"""セクターのタイム（2026-11-07、SUGO）を本体（Ver.2）と自宅の5Bへ入れる。

何も付けなければ確かめるだけで、どちらも変えない:
  - 本体: 入れ替えるファイルが、リポジトリのどれかの版と同じか（Lintarohさんなどが本体で直した版を上書きしないため）
  - 5B:   ブリッジのファイルがリポジトリのどれかの版と同じか
--apply で本体へ入れる（記録は止めない。止めずに deploy.sh を流せば途切れは作り直しの十数秒で済む）:
  1. 本体の今のファイルを ~/EcoCapture-Web/.bak-sectors-<日時>/ へ、DASHの2つを /opt/logger-v2-racecapture/*.pre-sectors-<日時> へ、
     イメージを ecocapture-web:pre-sectors-<日時> へ控える
  2. lap.py・models.py・podium.py・test_lap.py を置いて deploy.sh（本体の試験を全部流してから作り直す。
     試験が落ちたら作り直さないので、動いているEcoCaptureは前のまま。そのときはファイルも控えへ戻す）
  3. DASHの試験を本体の /tmp で流し、通ったら dash_model.py・ecocapture_dash.py を入れて、DASHが動いていれば再起動（画面が約5秒消える）
  4. sugo_setup.py --apply: コントロールラインをビーコンの位置へ移し、セクターの線3本を足す。
     ラインの中心が変わるのでラップの記録が消える（--no-line で飛ばす。あとで sugo_setup.py --apply）
--server で5Bのブリッジ（live_bridge.py・laps.html）を入れ替えて再起動する（ピットのタイム表に S1〜S4 の列が出る）。
  控えは5Bの ~/home_telemetry/*.20261107-before-sectors。本体と別にいつ入れてもよい（古い本体からはセクターが来ないだけ）。

戻すとき（本体）: 控えのフォルダのファイルを ~/EcoCapture-Web へ戻して deploy.sh、DASHは *.pre-sectors-<日時> を戻して
systemctl restart ecocapture-dash。ラインは sugo_setup.py --restore lap.json.bak-<日時>。

つなぎ方は sugo_setup.py と同じ: 既定は ssh unoq（Pixelのテザリング）、--adb でUSBのadb。5Bは ssh ecorun-home。
  python install_sectors.py                 # 確かめるだけ
  python install_sectors.py --apply         # 本体へ入れる（ラインも移す）
  python install_sectors.py --server        # 5Bへ入れる
  python install_sectors.py --apply --server
"""
import argparse
import hashlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dash_check  # noqa: E402  (Device: ssh/adb, AS_ROOT)
import sugo_setup  # noqa: E402

WEB = '/home/arduino/EcoCapture-Web'
DASH_DIR = '/opt/logger-v2-racecapture'
WEB_FILES = ['lap.py', 'models.py', 'podium.py', 'test_lap.py', 'test_podium.py']
DASH_FILES = ['dash_model.py', 'ecocapture_dash.py']
DASH_TEST = ['dash_model.py', 'ecocapture_dash.py', 'test_dash_model.py', 'display_load_control.py']
SERVER = 'ecorun-home'
SERVER_DIR = '/home/ntakao/home_telemetry'
SERVER_FILES = ['live_bridge.py', 'laps.html']
SERVER_SERVICE = 'ecorun-vm-bridge'


def norm_hash(data):
    """sha256 with CRLF taken as LF (some files on the unit came over with CRLF; the content is what counts)."""
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def known_hashes(path):
    """norm_hash of every version of `path` in the repository's history, and of the working copy."""
    rel = path.relative_to(REPO).as_posix()
    commits = subprocess.run(['git', '-C', str(REPO), 'log', '--format=%H', '--', rel],
                             capture_output=True, text=True, check=True).stdout.split()
    found = {norm_hash(path.read_bytes())}
    for commit in commits:
        blob = subprocess.run(['git', '-C', str(REPO), 'show', f'{commit}:{rel}'], capture_output=True)
        if blob.returncode == 0:
            found.add(norm_hash(blob.stdout))
    return found


def remote_hashes(run, paths):
    """{path: norm_hash or None} of files over there (CRLF taken as LF)."""
    script = '; '.join(f"if [ -e {p} ]; then tr -d '\\r' < {p} | sha256sum | cut -c1-64; else echo none; fi" for p in paths)
    code, out = run(script)
    lines = out.split()
    if code or len(lines) != len(paths):
        raise RuntimeError(f'ハッシュを読めません: {out[-300:]}')
    return {p: None if h == 'none' else h for p, h in zip(paths, lines)}


def check_files(label, run, pairs):
    """pairs: [(local Path, remote path)]. Prints each and returns True when all are a known version."""
    there = remote_hashes(run, [r for _, r in pairs])
    ok = True
    for local, remote in pairs:
        now, new = there[remote], norm_hash(local.read_bytes())
        if now == new:
            state = '新しい版が入っている'
        elif now is None:
            state = '★無い'; ok = False
        elif now in known_hashes(local):
            state = 'リポジトリの前の版（入れ替えてよい）'
        else:
            state = '★リポジトリのどの版とも違う（本体で直された？）'; ok = False
        print(f'  {label} {remote}: {state}')
    return ok


def device_pairs():
    return ([(REPO / 'EcoCapture-Web' / n, f'{WEB}/{n}') for n in WEB_FILES] +
            [(REPO / 'RaceCapture-UNOQ' / n, f'{DASH_DIR}/{n}') for n in DASH_FILES])


def install_device(dev, stamp, move_line, use_adb, host):
    run = lambda command, timeout=200: dev.run(command, timeout)
    bak = f'{WEB}/.bak-sectors-{stamp}'
    stage = f'/tmp/sectors-{stamp}'
    code, out = run(f'mkdir -p {bak} {stage}/web {stage}/dash && cd {WEB} && cp -p {" ".join(WEB_FILES)} {bak}/ && '
                    f'docker tag ecocapture-web:0.2.0 ecocapture-web:pre-sectors-{stamp} && echo ok')
    if code or 'ok' not in out:
        sys.exit(f'控えを作れません: {out[-300:]}')
    print(f'1. 控え: {bak}/、イメージ ecocapture-web:pre-sectors-{stamp}')
    for name in WEB_FILES:
        dev.put(REPO / 'EcoCapture-Web' / name, f'{stage}/web/{name}')
    for name in DASH_TEST:
        dev.put(REPO / 'RaceCapture-UNOQ' / name, f'{stage}/dash/{name}')
    got = remote_hashes(run, [f'{stage}/web/{n}' for n in WEB_FILES] + [f'{stage}/dash/{n}' for n in DASH_TEST])
    want = [norm_hash((REPO / 'EcoCapture-Web' / n).read_bytes()) for n in WEB_FILES] + \
           [norm_hash((REPO / 'RaceCapture-UNOQ' / n).read_bytes()) for n in DASH_TEST]
    if list(got.values()) != want:
        sys.exit('送ったファイルが本体で壊れています（何も入れ替えていません）')

    print('2. deploy.sh を流しています（本体の試験を全部流してから作り直す。数分かかる）')
    code, out = run(f'cp {" ".join(f"{stage}/web/{n}" for n in WEB_FILES)} {WEB}/ && cd {WEB} && '
                    f'sh deploy.sh > {stage}/deploy.log 2>&1; echo "rc=$?"; tail -25 {stage}/deploy.log', timeout=1200)
    if code or 'rc=0' not in out:
        run(f'cp -p {" ".join(f"{bak}/{n}" for n in WEB_FILES)} {WEB}/')
        print(out)
        sys.exit('2. ★deploy.sh が失敗しました。ファイルは控えへ戻しました（EcoCaptureが前のまま動いているか確かめる）')
    code, out = run('for i in $(seq 30); do curl -s -m 5 -o /dev/null http://127.0.0.1:8080/api/lap && break; sleep 2; done; '
                    'docker ps --filter name=ecocapture-web --format "{{.Status}}"; '
                    'curl -s -m 10 http://127.0.0.1:8080/api/lap | python3 -c "import json,sys; d=json.load(sys.stdin); '
                    "print('sectors' in d['line'], 'Sector' in d['values'])\"")
    print(f'2. deploy.sh: 済み（{" ".join(out.split())}）')
    if 'True True' not in out:
        sys.exit('★新しいlap.pyで動いていません')

    code, out = run(f'cd {stage}/dash && python3 -m unittest test_dash_model 2>&1 | tail -1')
    if 'OK' not in out:
        sys.exit(f'3. ★DASHの試験が本体で通りません（DASHは入れ替えていません）: {out}')
    active = run('systemctl is-active ecocapture-dash.service')[1].strip() == 'active'
    root = (' && '.join(f'cp -p {DASH_DIR}/{n} {DASH_DIR}/{n}.pre-sectors-{stamp}' for n in DASH_FILES) +
            f' && install -m 644 {stage}/dash/dash_model.py {DASH_DIR}/ && install -m 755 {stage}/dash/ecocapture_dash.py {DASH_DIR}/' +
            (' && systemctl restart ecocapture-dash.service' if active else '') + ' && echo ok')
    code, out = run(dash_check.AS_ROOT + "'" + root + "'", timeout=120)
    if 'ok' not in out:
        sys.exit(f'3. ★DASHを入れられません: {out[-300:]}')
    print(f'3. DASH: 試験が通り、入れた（{"再起動した" if active else "DASHは動いていなかったので再起動していない"}）。'
          f'控えは {DASH_DIR}/*.pre-sectors-{stamp}')
    run(f'rm -rf {stage}')

    if move_line:
        print('4. ラインとセクターの線:')
        args = ['--apply'] + (['--adb'] if use_adb else ['--host', host])
        return sugo_setup.main(args)
    print('4. ラインは変えていない（あとで sugo_setup.py --apply）')
    return 0


def server_run(command, timeout=120):
    done = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', SERVER, command],
                          capture_output=True, text=True, encoding='utf-8', errors='replace',
                          stdin=subprocess.DEVNULL, timeout=timeout)
    return done.returncode, (done.stdout + done.stderr).strip()


def install_server():
    src = REPO / 'tools' / 'home_telemetry'
    tag = '20261107-before-sectors'
    code, out = server_run(' && '.join(f'([ -e {SERVER_DIR}/{n}.{tag} ] || cp -p {SERVER_DIR}/{n} {SERVER_DIR}/{n}.{tag})'
                                       for n in SERVER_FILES) + ' && mkdir -p /tmp/sectors-bridge && echo ok')
    if 'ok' not in out:
        sys.exit(f'5Bで控えを作れません: {out[-300:]}')
    for name in SERVER_FILES:
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(src / name), f'{SERVER}:/tmp/sectors-bridge/{name}'],
                       check=True, stdin=subprocess.DEVNULL, timeout=120)
    code, out = server_run('cd /tmp/sectors-bridge && python3 -m py_compile live_bridge.py && '
                           f'cp live_bridge.py laps.html {SERVER_DIR}/ && sudo -n systemctl restart {SERVER_SERVICE} && '
                           f'sleep 5 && systemctl is-active {SERVER_SERVICE}', timeout=60)
    print(f'5B: {" ".join(out.split())}（控えは {SERVER_DIR}/*.{tag}）')
    return 0 if out.strip().endswith('active') and 'inactive' not in out else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='本体へ入れる')
    parser.add_argument('--server', action='store_true', help='5Bのブリッジへ入れる')
    parser.add_argument('--no-line', action='store_true', help='本体へ入れても、ラインとセクターの線は変えない')
    parser.add_argument('--force', action='store_true', help='本体・5Bのファイルがリポジトリのどの版とも違っても入れる')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    parser.add_argument('--skip-device', action='store_true', help='本体を見ない（5Bだけ）')
    args = parser.parse_args(argv)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    result = 0
    if not args.skip_device:
        dev = dash_check.Device(args.adb, args.host)
        print('本体:')
        try:
            ok = check_files('', lambda c: dev.run(c), device_pairs())
        except (RuntimeError, subprocess.SubprocessError) as error:
            print(f'  ★本体につながりません（テザリング・USBを確かめる）: {str(error)[-200:]}')
            if args.apply:
                return 1
            ok, result = False, 1
        if args.apply:
            if not ok and not args.force:
                sys.exit('★本体のファイルに知らない版があるので入れません（中身を確かめて --force）')
            result |= install_device(dev, stamp, not args.no_line, args.adb, args.host)
    print('5B:')
    ok = check_files('', server_run, [(REPO / 'tools' / 'home_telemetry' / n, f'{SERVER_DIR}/{n}') for n in SERVER_FILES])
    if args.server:
        if not ok and not args.force:
            sys.exit('★5Bのファイルに知らない版があるので入れません（中身を確かめて --force）')
        result |= install_server()
    if not args.apply and not args.server:
        print('（確かめただけで、本体・5Bは変えていません。入れるときは --apply / --server）')
    return result


if __name__ == '__main__':
    sys.exit(main())
