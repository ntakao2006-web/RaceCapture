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

Only the operations below exist; nothing runs a shell or changes settings.
"""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

OPS = ('status', 'lap_reset', 'lap_count', 'lap_start', 'log_start')
COMMAND_WINDOW_MS = 10 * 60 * 1000
SEEN_KEEP = 500
ID_RE = re.compile(r'^[0-9a-f]{8,64}$')


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
        try:
            message = await self.execute(op, command.get('arg'))
            ok = True
        except Exception as exc:  # noqa: BLE001  the pit gets the reason, the logger carries on
            ok, message = False, str(getattr(exc, 'detail', None) or exc) or type(exc).__name__
        result = {'id': command_id, 'op': op, 'ok': ok, 'message': message}
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
        raise ValueError(f'unknown op {op}')
