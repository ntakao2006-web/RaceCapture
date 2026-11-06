"""UNO Q（Ver.2）へ ssh でつなぐときの「つなぎ先」を決める。

`ssh unoq`（~/.ssh/config の Host unoq ＝ uno-q.local）は、Pixelのテザリングでも
名前（mDNS）が引けなくなることがある（2026-11-06、IPでは届くのに名前だけ引けなかった）。
そのときは次の順に探して、見つかったIPアドレスで同じ `unoq` の設定（ユーザー・鍵）のままつなぐ：

  1. いつもどおり `ssh unoq`
  2. 前回見つけたIPアドレス（%USERPROFILE%\\.ecologger\\unoq_ip.txt）
  3. PCと同じネットワーク（/24）で ssh の口（22番）が開いている機械を探し、
     `hostname` が uno-q と答えたもの

IPでつなぐときも、本体の鍵は名前（uno-q.local）で覚えている鍵と照らし合わせる（HostKeyAlias）。
別の機械に取り違えてつなぐことはない（鍵が違えば ssh が断る）。

`unoq` 以外の接続先（--host で別の名前を渡したとき）はそのまま使う。

道具からの使い方：
    import unoq_ssh
    head = unoq_ssh.ssh_cmd('unoq', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8')   # ['ssh', ..., 'unoq']
    scp = ['scp', '-q', *unoq_ssh.target_opts('unoq'), 'file', 'unoq:/tmp/']

.cmd からの使い方（ssh と同じ引数で、つなぎ先だけ探してくれる）：
    python unoq_ssh.py /opt/logger-v2-racecapture/dash_switch.sh dash
    python unoq_ssh.py --find          # 探すだけ（見つかったつなぎ先を表示）
"""
import concurrent.futures
import ipaddress
import os
import socket
import subprocess
import sys
from pathlib import Path

ALIAS = 'unoq'              # ~/.ssh/config の Host
MDNS_NAME = 'uno-q.local'   # 同じ Host の HostName（本体の鍵はこの名前で known_hosts にある）
HOSTNAME = 'uno-q'          # 本体の hostname
# PCの道具の置き場は %USERPROFILE%\.ecologger。%LOCALAPPDATA% は Claude のアプリから動かしたときだけ
# アプリ専用の場所へ振り替えられ、ショートカットから開いた道具と別のファイルになっていた（2026-11-07）
CACHE = Path.home() / '.ecologger' / 'unoq_ip.txt'
OLD_CACHES = [Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'EcoLogger' / 'unoq_ip.txt']

_found = {}  # host -> ssh の追加オプション（1回のプログラムの中では1回だけ探す）


def _log(message):
    print(message, file=sys.stderr, flush=True)


def ip_opts(ip):
    """IPアドレスでつなぐときの ssh/scp のオプション（鍵は名前で照合）"""
    return ['-o', f'HostName={ip}', '-o', f'HostKeyAlias={MDNS_NAME}']


def probe(opts, timeout=6):
    """そのつなぎ方で本体（hostname が uno-q）に入れれば True"""
    try:
        done = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', f'ConnectTimeout={timeout}', *opts, ALIAS, 'hostname'],
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              stdin=subprocess.DEVNULL, timeout=timeout + 15)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == HOSTNAME


def local_networks():
    """PCの今のIPv4アドレスから、探す /24 の一覧（テザリング・Wi-Fiらしいものを先に）"""
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    try:  # 外へ出るときに使うアドレス（実際には送らない）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 53))
            addresses.add(s.getsockname()[0])
    except OSError:
        pass
    nets = []
    for a in addresses:
        ip = ipaddress.ip_address(a)
        if ip.is_loopback or ip.is_link_local or not ip.is_private:
            continue
        net = ipaddress.ip_network(f'{a}/24', strict=False)
        if net not in [n for n, _ in nets]:
            nets.append((net, ip))
    # WSL・Hyper-V の仮想の口（172.16〜31）は後回し
    nets.sort(key=lambda n: n[0].subnet_of(ipaddress.ip_network('172.16.0.0/12')))
    return nets[:6]


def ssh_ports_open(net, own, timeout=0.6):
    """その /24 で 22番が開いているアドレス"""
    def check(ip):
        try:
            with socket.create_connection((str(ip), 22), timeout=timeout):
                return str(ip)
        except OSError:
            return None
    hosts = [ip for ip in net.hosts() if ip != own]
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        return [ip for ip in pool.map(check, hosts) if ip]


def read_cache():
    for path in (CACHE, *OLD_CACHES):
        try:
            return path.read_text(encoding='utf-8').strip() or None
        except OSError:
            continue
    return None


def write_cache(ip):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(ip + '\n', encoding='utf-8')
    except OSError:
        pass


def find(log=_log):
    """つなぎ先を探して ssh の追加オプションを返す（名前で届けば []）。見つからなければ None"""
    if probe([]):
        return []
    log(f'{MDNS_NAME} でつながらないので、IPアドレスで本体を探します…')
    cached = read_cache()
    if cached and probe(ip_opts(cached), timeout=3):  # 古いアドレスなら早めに諦めて探す
        log(f'前回のIPアドレス {cached} でつながりました')
        return ip_opts(cached)
    for net, own in local_networks():
        for ip in ssh_ports_open(net, own):
            if ip != cached and probe(ip_opts(ip)):
                write_cache(ip)
                log(f'本体が {ip} で見つかりました（{net} を探しました）')
                return ip_opts(ip)
    log('本体が見つかりませんでした（PCと本体が同じテザリングにいるか、本体の電源が入っているかを確かめてください）')
    return None


def target_opts(host=ALIAS, log=_log):
    """host へつなぐときに ssh/scp へ足すオプション。unoq 以外はそのまま（[]）。
    見つからなかったときも [] を返し、ssh 自身のエラーで知らせる"""
    if host != ALIAS:
        return []
    if host not in _found:
        _found[host] = find(log)
    return _found[host] or []


def ssh_cmd(host=ALIAS, *options):
    """['ssh', *options, （見つけたつなぎ先のオプション）, host]"""
    return ['ssh', *options, *target_opts(host), host]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['--find']:
        opts = target_opts()
        if _found.get(ALIAS) is None:
            return 1
        print('つなぎ先: ' + ('ssh unoq（名前で届く）' if not opts else ' '.join(opts)))
        return 0
    return subprocess.call([*ssh_cmd(ALIAS, '-o', 'ConnectTimeout=8'), *argv])


if __name__ == '__main__':
    sys.exit(main())
