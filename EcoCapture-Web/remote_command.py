"""Commands from the pit over LTE (2026-11-06, for SUGO): fix the lap count, start a lap or the
recording that did not start, or just ask how the logger is doing.

They ride the relay's existing `logger.config` message (pit -> loggers only, passed through as
is), so the relay server needs no change. The relay lets anyone who knows the room connect, even
as a logger, so every command is signed: HMAC-SHA256 over id|t|op|arg with a secret that never
travels (`private/remote_command.json`, put there over USB/ssh by tools/remote_command). A command
id is used once (remembered across restarts), and when the GNSS time is known a command more than
COMMAND_WINDOW_MS away from it is refused, so a captured command cannot be played again later.

    pit:    {"type":"logger.config","data":{"command":{"id":..,"t":<unix ms>,"op":..,"arg":..,"sig":..}}}
    logger: {"type":"logger.config","data":{"command_result":{"id":..,"op":..,"ok":..,"message":..,"status":{..}}}}

Only the operations below exist; nothing runs a shell, and the only settings they change are
the lap lines (2026-11-13, SPEC.md 7-5): `course_select` takes the name of a course file put on
the logger beforehand (setups/courses/<name>.json under the data folder, the same form as
tools/setups/courses/), `line_set` takes the lines themselves in the form of lap.json's line.
Neither stops the recording and neither is refused while the car is moving: asking the person to
confirm is the sending screen's job. The lap.json from before the change is kept once
(lap.json.bak-remote), the running lap is dropped so that laps count from the next pass of the new
line, and the answer carries `line`, read back from lap.json.
"""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

OPS = ('status', 'lap_reset', 'lap_count', 'lap_start', 'log_start', 'course_select', 'line_set')
LINE_OPS = ('course_select', 'line_set')
COMMAND_WINDOW_MS = 10 * 60 * 1000
SEEN_KEEP = 500
ID_RE = re.compile(r'^[0-9a-f]{8,64}$')
NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')  # a course name: nothing that could leave the folder
PREVIOUS_LAP = 'lap.json.bak-remote'


class Refused(ValueError):
    """A command that cannot run; `extra` goes into the answer next to the message."""
    def __init__(self, message, **extra):
        super().__init__(message)
        self.extra = extra


def payload(command_id, t, op, arg):
    return f'{command_id}|{t}|{op}|{json.dumps(arg, separators=(",", ":"), sort_keys=True)}'.encode()


def sign(secret, command_id, t, op, arg=None):
    return hmac.new(bytes.fromhex(secret), payload(command_id, t, op, arg), hashlib.sha256).hexdigest()


def write_private(path, data):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


class RemoteCommands:
    def __init__(self, root, runtime, gnss_ms=None):
        private = Path(root) / 'private'
        self.secret_path = private / 'remote_command.json'
        self.seen_path = private / 'remote_command_seen.json'
        self.courses = Path(root) / 'setups' / 'courses'
        self.changed = False  # whether the last line command changed anything
        self.runtime = runtime
        self.gnss_ms = gnss_ms or (lambda: None)  # GNSS UTC now (ms) or None
        self.actions = {}  # 'log_start' -> async function, filled in by server.py
        try:
            self.seen = json.loads(self.seen_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.seen = []

    def secret(self):
        """Read every time, so a secret put in place over USB works without a restart."""
        try:
            secret = json.loads(self.secret_path.read_text(encoding='utf-8')).get('secret', '')
            bytes.fromhex(secret)
            return secret if len(secret) >= 32 else None
        except (OSError, ValueError, AttributeError):
            return None

    def refuse(self, command):
        """Why this command must not run, or None."""
        if not isinstance(command, dict):
            return 'bad command'
        command_id, t, op, sig = command.get('id'), command.get('t'), command.get('op'), command.get('sig')
        if not isinstance(command_id, str) or not ID_RE.match(command_id) or type(t) is not int or not isinstance(sig, str):
            return 'bad command'
        if op not in OPS:
            return f'unknown op {op}'
        secret = self.secret()
        if secret is None:
            return 'no secret on the logger'
        if not hmac.compare_digest(sign(secret, command_id, t, op, command.get('arg')), sig):
            return 'bad signature'
        if command_id in self.seen:
            return 'already used'
        now = self.gnss_ms()
        if now is not None and abs(now - t) > COMMAND_WINDOW_MS:
            return 'too old or from the future'
        return None

    def remember(self, command_id):
        self.seen = (self.seen + [command_id])[-SEEN_KEEP:]
        try:
            write_private(self.seen_path, self.seen)
        except OSError:
            pass  # still refused for the rest of this run

    def status(self):
        runtime = self.runtime
        state = runtime.status()
        logging = state.get('logging') or {}
        laps = runtime.laps
        values = laps.values()
        return {
            'logging': bool(logging.get('active')), 'log_s': round(logging.get('elapsed_s') or 0),
            'hz': state.get('receive_hz'), 'gnss': self.gnss_ms() is not None,
            'sd': bool((state.get('hardware') or {}).get('sd_logging')),
            'video': bool((state.get('video') or {}).get('recording')),
            'lap': {'enabled': laps.line.enabled, 'count': values.get('LapCount'), 'current': values.get('CurrentLap'),
                    'running': laps.state.get('lap_start_ms') is not None, 'finished': bool(laps.state.get('finished')),
                    'race_min': None if values.get('RaceTime') is None else round(values['RaceTime'], 1)},
        }

    async def run(self, command):
        command_id = command.get('id') if isinstance(command, dict) else None
        op = command.get('op') if isinstance(command, dict) else None
        reason = self.refuse(command)
        if reason:
            return {'id': command_id, 'op': op, 'ok': False, 'message': reason}
        self.remember(command_id)
        extra = {}
        try:
            message = await self.execute(op, command.get('arg'))
            ok = True
        except Exception as exc:  # noqa: BLE001  the pit gets the reason, the logger carries on
            ok, message = False, str(getattr(exc, 'detail', None) or exc) or type(exc).__name__
            extra = getattr(exc, 'extra', None) or {}
        if ok and op in LINE_OPS:
            try:
                extra = {'line': self.line_summary()}
            except Exception:  # noqa: BLE001
                ok, message = False, 'line set, but it could not be read back'
        result = {'id': command_id, 'op': op, 'ok': ok, 'message': message, **extra}
        try:
            result['status'] = self.status()
        except Exception:  # noqa: BLE001
            pass
        return result

    async def execute(self, op, arg):
        laps = self.runtime.laps
        if op == 'status':
            return 'ok'
        if op == 'lap_reset':
            laps.reset()
            return 'laps reset to 0'
        if op == 'lap_count':
            if type(arg) is not int or not 0 <= arg <= 999:
                raise ValueError('lap count must be 0-999')
            laps.set_count(arg)
            return f'lap count set to {arg}'
        if op == 'lap_start':
            laps.start_now()
            return 'lap started now'
        if op == 'log_start':
            action = self.actions.get('log_start')
            if action is None:
                raise RuntimeError('log_start not available')
            if (self.runtime.status().get('logging') or {}).get('active'):
                return 'already logging'
            await action()
            return 'logging started'
        if op == 'course_select':
            name = arg.get('name') if isinstance(arg, dict) and len(arg) == 1 else None  # the name and nothing else
            self.change_line(self.course_line(name))
            return f'course {name} set' if self.changed else f'course {name} was already set'
        if op == 'line_set':
            self.change_line(self.typed_line(arg))
            return 'line set' if self.changed else 'line was already set'
        raise ValueError(f'unknown op {op}')

    # ---- the lap lines (course_select, line_set)
    def course_names(self):
        try:
            return sorted(p.stem for p in self.courses.glob('*.json') if NAME_RE.match(p.stem))
        except OSError:
            return []

    @staticmethod
    def valid_line(data):
        """LapLine checks the values (lap.py), so the limits are the same as on the logger's own screens."""
        from lap import LapLine  # here, not at the top: the PC tools import this module only to sign
        from pydantic import ValidationError
        try:
            return LapLine.model_validate({**data, 'enabled': True})
        except ValidationError as exc:
            raise Refused('bad line: ' + '; '.join(
                f"{'.'.join(map(str, e['loc'])) or 'line'}: {e['msg']}" for e in exc.errors()[:3])) from None

    def course_line(self, name):
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise Refused('bad course name')
        try:
            data = json.loads((self.courses / f'{name}.json').read_text(encoding='utf-8'))
        except FileNotFoundError:
            raise Refused(f'no course {name}', courses=self.course_names()) from None
        except (OSError, ValueError):
            raise Refused(f'course {name} cannot be read') from None
        if not isinstance(data, dict) or data.get('id') != name or not isinstance(data.get('line'), dict):
            raise Refused(f'course {name} is not a course file')
        return self.valid_line({k: v for k, v in data['line'].items() if k != 'set_at'})

    def typed_line(self, arg):
        """The lines as sent: the control line (lat, lon; bearing and width_m optional) with start, goal
        and sectors, which are none when left out. The race options (shortest lap, laps to run, pit
        lane, ...) stay as they are unless sent too."""
        if not isinstance(arg, dict) or 'set_at' in arg or arg.get('enabled', True) is not True:
            raise Refused('bad line')
        if arg.get('lat') is None or arg.get('lon') is None:
            raise Refused('bad line: lat and lon required')
        from lap import LapLine
        width = LapLine.model_fields['width_m'].default
        return self.valid_line({**self.runtime.laps.line.model_dump(), 'bearing': None, 'width_m': width,
                                'start': None, 'goal': None, 'sectors': [], **arg})

    def change_line(self, line):
        laps = self.runtime.laps
        lines = lambda l: (*(l.gate(t) for t in ('control', 'start', 'goal')), l.sectors)
        moved = lines(line) != lines(laps.line)
        self.changed = line.model_dump(exclude={'set_at'}) != laps.line.model_dump(exclude={'set_at'})
        if not self.changed:
            return  # sent twice: the copy of the line before the first one stays
        try:
            if laps.path.exists():
                temp = laps.path.with_name(PREVIOUS_LAP + '.tmp')
                temp.write_bytes(laps.path.read_bytes())
                temp.replace(laps.path.with_name(PREVIOUS_LAP))
        except OSError:
            raise Refused('the line before the change could not be kept; nothing changed') from None
        laps.configure(line)
        if moved:
            laps.restart_lap()  # laps count from the next pass of the new line (SPEC.md 7-5)

    def line_summary(self):
        """What lap.json holds now, short enough for the LTE link: each line as [lat, lon, bearing,
        width_m], how many sector lines, the id shown with the QR code (lap.line_code) and the name of
        the course file on the logger that it equals, if any."""
        from lap import LapLine, line_code
        line = LapLine.model_validate(json.loads(self.runtime.laps.path.read_text(encoding='utf-8'))['line'])
        short = lambda g: None if g is None else [round(g.lat, 7), round(g.lon, 7), g.bearing, g.width_m]
        now = line.model_dump(exclude={'set_at'})
        name = None
        for candidate in self.course_names():
            try:
                if self.course_line(candidate).model_dump(exclude={'set_at'}) == now:
                    name = candidate
                    break
            except ValueError:
                pass
        return {'name': name, 'control': short(line.gate('control')), 'start': short(line.start), 'goal': short(line.goal),
                'sectors': len(line.sectors), 'id': line_code(line)[1], 'at': line.set_at, 'changed': self.changed}
