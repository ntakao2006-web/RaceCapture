"""「設定」の段の、作りものの本体（試験 test_settings_ops.py と、本体なしで画面を見る dev_app.py が使う）。

settings_ops.py と、いまの道具（hud_apply・lens_apply・exposure_apply）が組み立てるシェルのコマンドを読んで、
/home/arduino/ecologger-video/ のファイルと、録画（overlay_rec）が設定を読み直して状態のファイルを書く動きを真似る。
本物のシェルは動かさない（コマンドの書き方そのものは、試験の「本物の sh で動かす」組が確かめる）。
"""
import re
import time

import settings_ops as so

R = so.REMOTE
HUD_STATUS, LENS_STATUS, EXPO_STATUS = f'{R}/hud_status.txt', f'{R}/lens.json.status', f'{R}/exposure.ini.status'
DEFAULT_INI = '/opt/ecologger-video/hud_default.ini'


class FakeUnoQ:
    """run(command, data=None) が本体の代わり。files は {本体でのパス: (inode, 中身のbytes, 時刻)}"""

    def __init__(self, ready=True, active=True, version=3, accepts=True):
        self.ready, self.active, self.version, self.accepts = ready, active, version, accepts
        self.files, self.ino, self.commands, self.fail = {}, 100, [], None
        self.hud_seen = self.lens_seen = self.expo_seen = None
        self.clock = 1794000000   # 本体の時計（2026-11-07ごろ。控えの時刻に出る）
        self.tick()

    # ---- ファイル
    def put(self, name, data):
        self.ino += 1
        self.clock += 60
        self.files[f'{R}/{name}'] = (self.ino, data if isinstance(data, bytes) else data.encode('utf-8'), self.clock)

    def text(self, name):
        entry = self.files.get(f'{R}/{name}')
        return None if entry is None else entry[1].decode('utf-8')

    def has(self, name):
        return f'{R}/{name}' in self.files

    def remove(self, name):
        self.files.pop(f'{R}/{name}', None)

    # ---- 録画が約1秒ごとにすること
    def tick(self):
        if not self.active:
            return
        at = time.strftime('%Y-%m-%d %H:%M:%S')
        # 計器（overlay_rec.c の hud_check）
        path = f'{R}/hud.ini' if self.has('hud.ini') else DEFAULT_INI
        ino, data, _ = self.files.get(path, (1, b'x' * 10, 0))
        key = (path, str(ino), str(len(data)))
        if key != self.hud_seen:
            self.hud_seen = key
            items = so.hud_summary(data).get('items', 0) if path != DEFAULT_INI else 19
            if self.accepts or path == DEFAULT_INI:
                self.hud_loaded, bad, error = (*key, items), ('', '0', '0'), ''
            else:
                bad, error = key, f'{path} 3行目: 読めない（前の配置のまま）'
            loaded = getattr(self, 'hud_loaded', ('', '0', '0', 0))
            self.files[HUD_STATUS] = (0, (f'version=3\nat={at}\nloaded={loaded[0]}\nino={loaded[1]}\nsize={loaded[2]}\nitems={loaded[3]}\n'
                                          f'bad={bad[0]}\nbad_ino={bad[1]}\nbad_size={bad[2]}\nerror={error}\n').encode(), self.clock)
        # レンズ（lens_check）
        entry = self.files.get(f'{R}/lens.json')
        key = None if entry is None else (entry[0], len(entry[1]))
        if key != self.lens_seen or LENS_STATUS not in self.files:
            self.lens_seen = key
            text = ('on=0\nino=0\nsize=-1\n' if key is None else f'on=1\nino={key[0]}\nsize={key[1]}\n') + \
                f"at={at}\nmsg={'ファイルが無い（補正しない）' if key is None else '読んだ'}\n"
            self.files[LENS_STATUS] = (0, text.encode(), self.clock)
        # 露出（ae_main）
        entry = self.files.get(f'{R}/exposure.ini')
        key = None if entry is None else (entry[0], len(entry[1]))
        if key != self.expo_seen or EXPO_STATUS not in self.files:
            self.expo_seen = key
            ini = '' if entry is None else entry[1].decode()
            mode = (re.search(r'^\s*mode\s*=\s*(\w+)', ini, re.M) or [None, 'own'])[1]
            self.expo_n = getattr(self, 'expo_n', 0) + 1
            text = (f'at=2026-11-13 10:00:{self.expo_n:02d}\nmode={mode}\nexposure_ms=0.7\ngain=3\ngain_range=0-100\nroi_mean=118\nroi_hi=220\n'
                    f"msg={'設定ファイルが無いので既定の値' if entry is None else '設定ファイルを読んだ'}\n")
            self.files[EXPO_STATUS] = (0, text.encode(), self.clock)

    # ---- コマンド
    def run(self, command, data=None):
        self.commands.append(command)
        if self.fail and self.fail in command:
            raise RuntimeError('本体でのコマンドが失敗しました: 作りものの失敗')
        out = self.answer(command, data)
        self.tick()
        return out

    def group_files(self, command):
        return re.search(r'for f in ([^;]+); do', command).group(1).split()

    def answer(self, command, data):
        cat = lambda path: self.files[path][1].decode('utf-8') if path in self.files else ''  # noqa: E731
        active = self.active
        if command.startswith(f'if [ -f {DEFAULT_INI}'):               # hud_apply.device_state
            return (f'READY={int(self.ready)}\nVERSION={self.version}\nACTIVE={"active" if active else "inactive"}\n' + cat(HUD_STATUS))
        if command.startswith('if grep -q OVERLAY_LENS'):              # lens_apply.device_state
            return f'READY={int(self.ready)}\nACTIVE={int(active)}\n' + cat(LENS_STATUS)
        if command.startswith('if grep -q OVERLAY_EXPOSURE'):          # exposure_apply.device_state
            return f'@@R{int(self.ready)}\n@@A{int(active)}\n@@I\n{cat(R + "/exposure.ini")}\n@@S\n{cat(EXPO_STATUS)}'
        if command == so.read_command():
            out = ''
            for name in command.split('for f in ', 2)[1].split(';')[0].split():
                if self.has(name):
                    out += f'@@F {name} {self.files[f"{R}/{name}"][2]}\n{self.text(name)}\n'
            for name in command.split('for f in ', 2)[2].split(';')[0].split():
                if self.has(name):
                    out += f'@@N {name} {self.files[f"{R}/{name}"][2]}\n'
            return out + '@@END\n'
        if command.endswith('echo KEPT'):
            for f in self.group_files(command):
                self.remove(f'prev/{f}')
                self.remove(f'prev/{f}.none')
                self.clock += 60
                if self.has(f):
                    self.files[f'{R}/prev/{f}'] = (0, self.files[f'{R}/{f}'][1], self.clock)
                else:
                    self.files[f'{R}/prev/{f}.none'] = (0, b'', self.clock)
            return 'KEPT\n'
        if command.endswith('echo HAVE') or command.endswith('echo SWAPPED'):
            names = self.group_files(command)
            if not all(self.has(f'prev/{f}') or self.has(f'prev/{f}.none') for f in names):
                return 'NOPREV\n'
            if command.endswith('echo HAVE'):
                return 'HAVE\n'
            out = ''
            for f in names:
                now = self.files.get(f'{R}/{f}')
                old = self.files.get(f'{R}/prev/{f}')
                self.remove(f'prev/{f}')
                self.remove(f'prev/{f}.none')
                self.clock += 60
                if now is None:
                    self.files[f'{R}/prev/{f}.none'] = (0, b'', self.clock)
                else:
                    self.files[f'{R}/prev/{f}'] = (0, now[1], self.clock)
                if old is None:
                    self.remove(f)
                    out += f'@@S {f} -\n'
                else:
                    self.put(f, old[1])
                    out += f'@@S {f} {self.ino} {len(old[1])}\n'
            return out + 'SWAPPED\n'
        m = re.search(r'cat > (\S+)\.tmp', command)
        if m:                                                          # 書き込み（道具の push・write_ini・settings_ops.write_command）
            name = m.group(1)[len(R) + 1:]
            self.put(name, data or b'')
            return f'{self.ino} {len(data or b"")}\n' if 'stat -c' in command else 'ok\n'
        m = re.fullmatch(r'rm -f (\S+)', command)
        if m:
            self.files.pop(m.group(1), None)
            return ''
        m = re.fullmatch(r'cat (\S+) 2>/dev/null; true', command)
        if m:
            return cat(m.group(1))
        m = re.fullmatch(r'\[ -f (\S+) \] && echo yes; true', command)
        if m:
            return 'yes\n' if m.group(1) in self.files else ''
        raise AssertionError(f'作りものの本体が知らないコマンド: {command}')
