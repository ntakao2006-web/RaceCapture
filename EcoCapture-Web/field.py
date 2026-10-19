"""Course-walk screen for a phone on the same Wi-Fi (the phone's tethering).

The USB admin UI (server.app) only answers on localhost, so a phone cannot open
it, and it should not: it can change Wi-Fi, delete logs and so on. This second
app listens on the LAN with only what the course walk needs: GNSS state, the
three lap lines registered at the current position, the required lap count,
the lap reset and the line QR code for the Android loggers.

Every API call needs the key from `field_token` in the data directory. The
admin UI shows the URL with the key as a QR code; the phone page keeps the key
in its URL and in localStorage.
"""
import hmac
import os
import secrets
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from lap import LapLine, line_qr

FIELD_PORT = int(os.environ.get('ECOCAPTURE_FIELD_PORT', 8082))
MDNS_NAME = os.environ.get('ECOCAPTURE_MDNS_NAME', 'uno-q.local')
WEB = Path(__file__).parent / 'web'
PAGES = {'/': ('field.html', 'text/html'), '/field.js': ('field.js', 'text/javascript'),
         '/field.css': ('field.css', 'text/css')}
LINE_NAMES = {'start': 'スタート', 'control': 'コントロール', 'goal': 'ゴール'}


def load_token(root):
    path = Path(root) / 'field_token'
    try:
        token = path.read_text(encoding='ascii').strip()
        if len(token) >= 8:
            return token
    except (OSError, ValueError):
        pass
    token = secrets.token_urlsafe(9)
    temp = path.with_suffix('.tmp')
    temp.write_text(token, encoding='ascii')
    os.chmod(temp, 0o600)
    temp.replace(path)
    return token


def field_urls(token, addresses=()):
    return [f'http://{host}:{FIELD_PORT}/?k={token}' for host in (MDNS_NAME, *addresses)]


def create_app(runtime, token):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            key = request.headers.get('x-field-key') or request.query_params.get('k') or ''
            if not hmac.compare_digest(key.encode(), token.encode()):
                return JSONResponse({'detail': '合言葉が違います。管理画面のQRから開き直してください。'}, status_code=403)
            if request.method != 'GET':
                if request.headers.get('x-ecocapture') != '1':
                    return JSONResponse({'detail': '操作ヘッダーが必要です'}, status_code=403)
                if int(request.headers.get('content-length', '0')) > 4096:
                    return JSONResponse({'detail': '内容が大きすぎます'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    for route, (name, media) in PAGES.items():
        app.add_api_route(route, lambda name=name, media=media: FileResponse(WEB / name, media_type=media), methods=['GET'])

    async def body_of(request):
        try:
            body = await request.json()
        except ValueError:
            body = {}
        return body if isinstance(body, dict) else {}

    @app.get('/api/field/state')
    def state():
        status = runtime.status()
        sample = runtime.sample if status['connected'] else None
        values = (sample or {}).get('values', {})
        logging = status['logging']
        lap = runtime.laps.public()
        lap.pop('laps', None)
        return {'connected': status['connected'],
                'gnss': {'fix': values.get('GPSFix'), 'sats': values.get('GPSSats'), 'lat': values.get('Lat'),
                         'lon': values.get('Lon'), 'speed': values.get('GPSSpeed'),
                         'hacc_m': (sample or {}).get('gnss_hacc_m')},
                'logging': {'active': logging.get('active'), 'error': logging.get('error'),
                            'sd_warning': logging.get('sd_warning')},
                'lap': lap}

    @app.post('/api/field/here')
    async def here(request: Request):
        target = (await body_of(request)).get('target')
        if target not in LINE_NAMES:
            raise HTTPException(400, 'ラインの種類を確認してください。')
        if not runtime.status()['connected']:
            raise HTTPException(409, 'ロガーの受信を待っています。')
        try:
            runtime.laps.set_here(runtime.sample, None, target)
        except ValueError:
            raise HTTPException(409, 'GNSSが測位していません。空が開けた所で、測位してから押してください。')
        except OSError:
            raise HTTPException(507, 'ラインを保存できませんでした。')
        return runtime.laps.public()

    @app.post('/api/field/total')
    async def total(request: Request):
        value = (await body_of(request)).get('total_laps')
        try:
            runtime.laps.configure(LapLine.model_validate({**runtime.laps.line.model_dump(), 'total_laps': value}))
        except ValueError:
            raise HTTPException(400, '規定周回数を確認してください。')
        except OSError:
            raise HTTPException(507, '規定周回数を保存できませんでした。')
        return runtime.laps.public()

    @app.post('/api/field/reset')
    async def reset():
        try:
            runtime.laps.reset()
        except OSError:
            raise HTTPException(507, '周回数を消去できませんでした。')
        return runtime.laps.public()

    @app.get('/api/field/code')
    def code():
        line = runtime.laps.line
        if not line.enabled:
            raise HTTPException(409, 'コントロールラインを先に登録してください。')
        return line_qr(line)

    return app


class FieldServer(uvicorn.Server):
    """Runs next to the main uvicorn in the same event loop. The main server owns
    SIGTERM/SIGINT; this one is stopped from the main app's lifespan."""
    def install_signal_handlers(self):  # uvicorn < 0.29
        pass

    @contextmanager
    def capture_signals(self):  # uvicorn >= 0.29
        yield


async def serve(server):
    """uvicorn exits the process when it cannot bind; here that only disables the screen."""
    try:
        await server.serve()
    except (SystemExit, OSError) as exc:
        print(f'course-walk screen stopped: {exc!r}')


def make_server(runtime, root):
    app = create_app(runtime, load_token(root))
    return FieldServer(uvicorn.Config(app, host='0.0.0.0', port=FIELD_PORT, log_level='warning',
                                      access_log=False, ws='none', lifespan='off'))
