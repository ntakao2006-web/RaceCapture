"""EcoLogger V2: STM32 Bridge -> local CSV + REST/WebSocket. No host-generated telemetry."""
import asyncio
import csv
import json
import os
import re
import shutil
import time
import uuid
import httpx
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sd_storage import SDStorage
from sd_timestamp import stamp_logs
from models import CHANNELS, LAP_CHANNELS, Configuration, validate_sample
from podium import PodiumSender
from lap import LapLine, LapTimer

ROOT = Path(os.environ.get("ECOCAPTURE_DATA", "/data"))
ROOT.mkdir(parents=True, exist_ok=True)
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
CONFIG_PATH = ROOT / "config.json"
RESERVE_BYTES = 256 * 1024 * 1024
# Dashcam-style retention: below this free space, delete the oldest finished
# logs (never the one being written). RESERVE_BYTES stays as the hard floor.
KEEP_FREE_BYTES = int(os.environ.get("ECOCAPTURE_KEEP_FREE_BYTES", 1024 * 1024 * 1024))
PUBLIC_DIR=ROOT/'public'
PUBLIC_DIR.mkdir(exist_ok=True)


def atomic_json(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


class Recorder:
    def __init__(self):
        self.file = None
        self.can_file = None
        self.writer = None
        self.name = None
        self.rows = 0
        self.started = None
        self.started_mono = None
        self.error = None
        self.last_sync = 0
        self.last_check = 0

    def start(self, config):
        if self.file:
            return
        # eMMC records independently of the SD card; old logs make room as needed.
        if self.make_room() < RESERVE_BYTES:
            raise HTTPException(507, "内蔵ストレージの空き容量が不足しています")
        self.started = datetime.now(timezone.utc).isoformat()
        self.started_mono = time.monotonic()
        self.name = "LOG_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8] + ".csv"
        self.rows = 0
        self.error = None
        atomic_json(LOGS / (self.name + ".meta.json"), {
            "schema": 1, "demo": False, "source": "logger-v2-hardware", "storage": "UNO Q internal eMMC",
            "started_utc": self.started, "config": config.model_dump(),
            "mcu_generation_hz": 100, "linux_poll_target_hz": 20,
            "clock": "host_utc is Linux reception time, not GNSS time; mcu_ms wraps at 2^32",
            "units": {k: unit for k, (_, unit) in {**CHANNELS, **LAP_CHANNELS}.items()}, "state": "recording"
        })
        self.file = (LOGS / self.name).open("x", encoding="utf-8", newline="")
        self.can_file = (LOGS / (self.name + ".can.jsonl")).open("x",encoding="utf-8")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["schema", "demo", "source", "host_utc", "seq", "mcu_ms", *CHANNELS,"gnss_utc","gnss_itow_ms","imu_raw","imu_temperature_C","imu_calibration","quaternion","gnss_hacc_m","can_signals",*LAP_CHANNELS])
        self.last_sync = time.monotonic()
        self.last_check = 0

    def append(self, sample):
        if not self.file:
            return
        now = time.monotonic()
        try:
            if now - self.last_check >= 1:
                self.last_check = now
                if self.make_room() < RESERVE_BYTES:
                    raise OSError("Storage reserve reached (256 MiB)")
            self.writer.writerow([1, int(sample["demo"]), sample["source"], sample["host_utc"], sample["seq"], sample["mcu_ms"],
                                  *(sample["values"][k] for k in CHANNELS),sample.get("gnss_utc"),sample.get("gnss_itow_ms"),sample.get("imu_raw"),sample.get("imu_temperature_C"),json.dumps(sample.get("imu_calibration")),json.dumps(sample.get("quaternion")),sample.get("gnss_hacc_m"),json.dumps(sample.get("can_signals",{})),*((sample.get("lap") or {}).get(k) for k in LAP_CHANNELS)])
            self.rows += 1
            if now - self.last_sync >= 1:
                if self.can_file:self.can_file.flush();os.fsync(self.can_file.fileno())
                self.file.flush()
                os.fsync(self.file.fileno())
                self.last_sync = now
        except OSError as exc:
            self.error = str(exc)
            self.stop()

    def stop(self):
        if not self.file:
            return
        if self.can_file:
            self.can_file.flush();os.fsync(self.can_file.fileno());self.can_file.close();self.can_file=None
        file, self.file = self.file, None
        try:
            file.flush()
            os.fsync(file.fileno())
        except OSError as exc:
            self.error = str(exc)

        finally:
            file.close()
        try:
            path = LOGS / (self.name + ".meta.json")
            meta = json.loads(path.read_text())
            meta.update(state="error" if self.error else "closed", rows=self.rows,
                        ended_utc=datetime.now(timezone.utc).isoformat(), error=self.error)
            atomic_json(path, meta)
        except OSError as exc:
            self.error = str(exc)

    def make_room(self):
        free=shutil.disk_usage(ROOT).free
        if free>=KEEP_FREE_BYTES:return free
        closed=sorted((p for p in LOGS.glob('LOG_*.csv') if not (self.file and p.name==self.name)),key=lambda p:p.stat().st_mtime)
        for path in closed:
            if free>=KEEP_FREE_BYTES:break
            self.delete_log(path)
            free=shutil.disk_usage(ROOT).free
        return free

    def delete_log(self,path):
        # A file that cannot be removed must not stop the recording in progress.
        targets=[path.with_name(path.name+suffix) for suffix in ('','.meta.json','.can.jsonl','.sd-journal.jsonl')]
        for target in targets+[ROOT/'sd-journals'/(path.name+'.timestamps.jsonl')]:
            with suppress(OSError):
                if target.is_file() and not target.is_symlink():target.unlink()

    def status(self):
        return {"active": self.file is not None, "name": self.name, "rows": self.rows,
                "elapsed_s": time.monotonic() - self.started_mono if self.file else 0, "error": self.error}


class Runtime:
    def __init__(self):
        self.config_error = None
        try:
            self.config = Configuration.model_validate_json(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else Configuration()
        except (ValueError, OSError) as exc:
            self.config = Configuration()
            self.config_error = str(exc)
        self.sample = None
        self.received_at = 0
        self.received = 0
        self.bridge_errors = 0
        self.error = None
        self.resets = 0
        self.times = deque(maxlen=20)
        self.recorder = Recorder()
        self.sd = SDStorage(ROOT / "sd-journals")
        self.hardware = {}
        self.sensors = {}
        self.bridge = None
        self.sd_files_task = None
        self.sd_files_key = None
        self.auto_started = False
        self.auto_start_task = None
        self._frame_at = -1.0
        self._frame_text = ''
        self.podium = PodiumSender(ROOT,self)
        self.laps = LapTimer(ROOT)
        self.podium_task = None
        self.podium_checking = False
        self.record_lock = asyncio.Lock()
        self.record_sd_first = None
        self.sd_note = None

    def status(self):
        age = time.monotonic() - self.received_at if self.sample else None
        fresh = age is not None and age < 1.0
        duration = self.times[-1][0] - self.times[0][0] if len(self.times) > 1 else 0
        return {"device": self.config.device_name, "version": "0.2.0", "demo": False,
                "source": "logger-v2-hardware", "connected": fresh,
                "age_ms": round(age * 1000) if age is not None else None,
                "receive_hz": round(sum(count for _,count in list(self.times)[1:]) / duration, 1) if duration and fresh else 0,
                "mcu_generation_hz": 100, "poll_target_hz": 4 if self.sd.status.get('active') else 20, "received": self.received,
                "bridge_errors": self.bridge_errors, "mcu_resets": self.resets, "error": self.error,
                "config_error": self.config_error, "storage": "internal-emmc",
                "storage_free_bytes": shutil.disk_usage(ROOT).free,
                "sensors": self.sensors if fresh else {k:"通信待ち" for k in self.sensors}, "hardware": self.hardware,
                "logging": {**self.recorder.status(),"sd_warning":self.sd_warning()}, "sd_copy": self.sd.status, "podium":self.podium.status()}

    def sd_warning(self):
        if not self.recorder.file or not self.bridge:return None
        if (self.hardware.get('sd_logging') or self.record_sd_first is not None) and not self.hardware.get('sd_errors'):return None
        return self.sd_note or 'SDに記録されていません。本体（eMMC）には記録しています。'

    def envelope(self):
        status = self.status()
        return {"type": "telemetry", "status": status, "sample": self.sample if status["connected"] else None}

    def websocket_frame(self):
        # Reuse one serialization across browsers within a display frame.
        now = time.monotonic()
        if now - self._frame_at >= 0.1:
            self._frame_text = json.dumps(self.envelope(), ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            self._frame_at = now
        return self._frame_text

    async def collect(self):
        from telemetry_bridge import TelemetryBridge
        from hardware import HardwareDecoder
        self.bridge=bridge=TelemetryBridge();decoder=HardwareDecoder()
        configured=False
        status_at=0.0
        while True:
            tick=time.monotonic()
            try:
                if not configured:
                    await bridge.command('C'+str(self.config.can_bitrate));configured=True
                # GNSS updates at 10 Hz. Repeating this large snapshot at 20 Hz
                # consumes UART bandwidth needed by vehicle CAN and IMU batches.
                if time.monotonic()-status_at>=.1:
                    self.hardware=json.loads(await bridge.call('logger.status'))
                    status_at=time.monotonic()
                batch=json.loads(await bridge.call('logger.take'))
                samples,self.sensors=decoder.decode(self.hardware,batch,self.config)
                self.sensors['lte']=self.podium.status()['message']
                if self.recorder.can_file:
                    for frame in decoder.last_can:self.recorder.can_file.write(json.dumps(frame)+"\n")
                for sample in samples:
                    sample=validate_sample(sample)
                    if self.sample and sample['mcu_ms'] < self.sample['mcu_ms']:self.resets+=1;configured=False
                    sample['host_utc']=datetime.now(timezone.utc).isoformat()
                    sample['lap']=self.laps.update(sample)
                    self.sample=sample;self.received_at=time.monotonic();self.received+=1
                    if not self.auto_started and self.config.auto_record:
                        self.auto_started=True
                        self.auto_start_task=asyncio.create_task(self.start_on_boot())
                    self.recorder.append(sample)
                if samples:self.times.append((self.received_at,len(samples)))
                self.error=None
            except Exception as exc:
                self.error=str(exc);self.bridge_errors+=1
                await asyncio.sleep(.5)
            # SD transfers are only allowed with recording stopped. Drain live
            # samples in 25-sample batches so telemetry status requests leave
            # bandwidth for the card, without stopping sensor acquisition.
            interval=.25 if self.sd.status.get('active') else .05
            await asyncio.sleep(max(0,interval-(time.monotonic()-tick)))

    async def start_on_boot(self):
        try:
            await start_log()
        except Exception as exc:
            self.recorder.error=getattr(exc,'detail',None) or str(exc)


runtime = Runtime()


def public_snapshot():
    status=runtime.status()
    safe={key:status[key] for key in ('device','version','demo','source','connected','age_ms','receive_hz','received')}
    safe['profile']=runtime.config.profile
    safe['sensors']=status['sensors']
    safe['logging']={key:status['logging'][key] for key in ('active','elapsed_s','rows')}
    sample=None
    if status['connected']:
        sample={key:runtime.sample[key] for key in ('schema','source','demo','seq','mcu_ms','host_utc')}
        sample['values']={key:runtime.sample['values'][key] for key in CHANNELS}
        sample['lap']=runtime.laps.values()
    return {'type':'telemetry','status':safe,'sample':sample,'_exported_monotonic':time.monotonic()}


async def export_public():
    while True:
        payload=public_snapshot()
        try:
            # The viewer can only read this directory. No passwords, LAN info, config or log paths.
            temp=PUBLIC_DIR/'telemetry.tmp'
            temp.write_text(json.dumps(payload,allow_nan=False))
            temp.replace(PUBLIC_DIR/'telemetry.json')
        except OSError:pass
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app):
    # Incomplete sessions remain downloadable and are explicitly marked after a restart.
    for path in LOGS.glob("*.csv.meta.json"):
        try:
            meta = json.loads(path.read_text())
            if meta.get("state") == "recording":
                meta["state"] = "interrupted"
                atomic_json(path, meta)
        except (ValueError, OSError):
            pass
    task = asyncio.create_task(runtime.collect())
    public_task=asyncio.create_task(export_public())
    runtime.podium_task=asyncio.create_task(runtime.podium.run())
    yield
    task.cancel()
    public_task.cancel()
    runtime.podium_task.cancel()
    if runtime.auto_start_task:
        runtime.auto_start_task.cancel()
        with suppress(asyncio.CancelledError):await runtime.auto_start_task
    with suppress(asyncio.CancelledError):
        await runtime.podium_task
    with suppress(asyncio.CancelledError):
        await task
    with suppress(asyncio.CancelledError):
        await public_task
    runtime.recorder.stop()


app = FastAPI(title="EcoLogger V2 / EcoCapture-Web", lifespan=lifespan)


def same_origin(origin, host):
    return urlparse(origin).netloc == host


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if urlparse('//'+request.headers.get('host','')).hostname not in ('127.0.0.1','localhost','::1','testserver'):
        return JSONResponse({'detail':'USB管理画面はlocalhostで開いてください'},status_code=403)
    if request.method in {"POST", "DELETE", "PUT"}:
        origin = request.headers.get("origin")
        if origin and not same_origin(origin, request.headers.get("host")):
            return JSONResponse({"detail": "別のサイトからの操作は受け付けません"}, status_code=403)
        if request.headers.get("x-ecocapture") != "1":
            return JSONResponse({"detail": "操作ヘッダーが必要です"}, status_code=403)
        if int(request.headers.get("content-length", "0")) > 65536:
            return JSONResponse({"detail": "設定が大きすぎます"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://cyberjapandata.gsi.go.jp; connect-src 'self'; frame-ancestors http://127.0.0.1:6080 http://localhost:6080"
    return response


async def device_request(path,body=None):
    try:
        transport=httpx.AsyncHTTPTransport(uds='/run/ecocapture-admin/agent.sock')
        async with httpx.AsyncClient(transport=transport,base_url='http://agent',timeout=50) as client:
            response=await (client.get(path) if body is None else client.post(path,json=body))
            result=response.json()
        if response.status_code>=400:raise HTTPException(response.status_code,result.get('detail','UNO Qの処理に失敗しました'))
        return result
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'UNO Q管理サービスに接続できません')


@app.get('/api/device/system')
async def device_system():return await device_request('/system')


@app.get('/api/device/wifi')
async def device_wifi():return await device_request('/wifi')


@app.post('/api/device/wifi/scan')
async def device_scan():return await device_request('/wifi/scan',{})


@app.post('/api/device/wifi/connect')
async def device_connect(request:Request):
    return await device_request('/wifi/connect',await request.json())


@app.post('/api/device/wifi/disconnect')
async def device_disconnect():return await device_request('/wifi/disconnect',{})


@app.get('/api/device/sharing')
async def device_sharing():return await device_request('/sharing')


@app.post('/api/device/sharing')
async def device_share_set(request:Request):return await device_request('/sharing',await request.json())


@app.get("/api/status")
def status():
    return runtime.status()


@app.get('/api/podium')
def podium_config():
    return {'config':runtime.podium.store.public(),'status':runtime.podium.status(),
            'channels':[{'name':n,'label':label,'unit':unit} for n,(label,unit) in CHANNELS.items()]+
                       [{'name':s.name,'label':s.name,'unit':s.unit} for s in runtime.config.signals if s.name not in CHANNELS]}


@app.post('/api/podium')
async def save_podium(request:Request):
    if runtime.podium_checking:raise HTTPException(409,'LTEの点検完了後に保存してください。')
    try:
        body=await request.json()
        if not isinstance(body,dict):raise ValueError()
        runtime.podium.store.update(body,[*CHANNELS,*(s.name for s in runtime.config.signals)])
    except (ValueError,TypeError):
        # Pydantic's default error payload echoes input (including the streaming key).
        raise HTTPException(400,'設定を確認してください。送信ONには送信キーが必要です。LTEではさらにSIM・アンテナ確認とAPNが必要です。')
    except OSError:raise HTTPException(507,'LTE設定を保存できませんでした。')
    if runtime.podium_task:
        runtime.podium_task.cancel()
        with suppress(asyncio.CancelledError):await runtime.podium_task
        runtime.podium_task=asyncio.create_task(runtime.podium.run())
    return podium_config()


@app.post('/api/podium/check')
async def check_podium(watchdog:bool=False):
    if runtime.podium_checking or runtime.podium.store.config.enabled or runtime.sd.status.get('active'):
        raise HTTPException(409,'LTE送信とSD操作を止めてから点検してください。')
    if not runtime.bridge:raise HTTPException(503,'MCU通信を待っています。')
    from sim7070 import SIM7070
    runtime.podium_checking=True
    modem=SIM7070(runtime.bridge)
    report={'at':False,'rf_off':False,'flow_control':False,'tcp_commands':False,'power_off':False}
    try:
        await modem.uart.power(True);await asyncio.sleep(3)
        await modem.command('AT');report['at']=True
        await modem.command('AT+CFUN=0');report['rf_off']=True
        await modem.command('ATE0')
        await modem.command('AT+IFC=2,2');report['flow_control']=True
        identity=await modem.command('AT+GMM')
        report['model']='SIM7070' if b'SIM7070' in identity else '未確認'
        capabilities=await modem.command('AT+CLAC',15)
        report['tcp_commands']=True if all(command in capabilities for command in (b'+CAOPEN',b'+CASEND',b'+CARECV')) else None
        report['capability_names']=[c.decode() for c in (b'+CAOPEN',b'+CASEND',b'+CARECV',b'+CIPSTART',b'+CIPSEND') if c in capabilities]
        report['message']='UARTを確認しました。TCP通信はSIM・LTEアンテナ接続後に確認してください。'
        report['uart_queries']=0
        for _ in range(20):
            await modem.command('AT+CSQ');report['uart_queries']+=1
        if watchdog:
            # Ordinary sensor/SD status polling must not keep LTE powered forever.
            await asyncio.sleep(21)
            state=json.loads(await runtime.bridge.call('logger.lter'))
            report['watchdog_power_off']=state['power']==0
    except Exception:
        report['message']='LTEの点検に失敗しました。配線・電源またはファームを確認してください。'
    finally:
        try:
            await modem.close();await asyncio.sleep(.1)
            state=json.loads(await runtime.bridge.call('logger.lter'))
            report.update(power_off=state['power']==0,uart_overflows=state['overflows'],uart_rx_bytes=state['rx_bytes'],uart_tx_bytes=state['tx_bytes'])
        except Exception:report['power_off']=False
        runtime.podium_checking=False
    return report


@app.get("/api/telemetry")
def telemetry():
    return runtime.envelope()


@app.get("/api/config")
def config():
    return runtime.config.model_dump()


@app.post("/api/config")
async def save_config(value: Configuration):
    if runtime.recorder.file:
        raise HTTPException(409, "設定を保存する前に記録を停止してください")
    if runtime.bridge:
        await runtime.bridge.command("C"+str(value.can_bitrate))
    atomic_json(CONFIG_PATH, value.model_dump())
    runtime.config = value
    runtime.config_error = None
    return {"config": value.model_dump(), "applied_to_can": runtime.bridge is not None, "message": "設定を保存しました。CAN1は受信専用、CAN2はセンサーハブ受信で動作します。"}


@app.get("/api/can/channels")
def channels():
    return {"signals": [s.model_dump() for s in runtime.config.signals], "hardware_connected": bool(sum(runtime.hardware.get("can_counts",[]))), "applied": runtime.bridge is not None}


@app.get('/api/can/ncec')
def ncec_preset():
    from ncec import preset
    return preset()


@app.post('/api/can/ncec/decode')
async def ncec_decode(request: Request):
    from ncec import decode_text
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get('text'), str) or len(body['text']) > 50000:
        raise HTTPException(400, 'CANテキストを確認してください')
    try:
        return decode_text(body['text'])
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get('/api/lap')
def lap_status():
    return runtime.laps.public()


@app.post('/api/lap')
async def save_lap(request:Request):
    try:
        body=await request.json()
        if not isinstance(body,dict):raise ValueError()
        runtime.laps.configure(LapLine.model_validate({**runtime.laps.line.model_dump(),**body}))
    except (ValueError,TypeError):raise HTTPException(400,'ラップ設定を確認してください。')
    except OSError:raise HTTPException(507,'ラップ設定を保存できませんでした。')
    return runtime.laps.public()


@app.post('/api/lap/here')
async def lap_here(request:Request):
    body=await request.json() if int(request.headers.get('content-length','0')) else {}
    if not runtime.status()['connected']:raise HTTPException(409,'MCUからの受信を待っています。')
    try:runtime.laps.set_here(runtime.sample,body.get('width_m') if isinstance(body,dict) else None)
    except ValueError:raise HTTPException(409,'GNSSが測位していません。屋外で測位してから登録してください。')
    except OSError:raise HTTPException(507,'ラップ設定を保存できませんでした。')
    return runtime.laps.public()


@app.post('/api/lap/reset')
async def lap_reset():
    try:runtime.laps.reset()
    except OSError:raise HTTPException(507,'ラップ記録を消去できませんでした。')
    return runtime.laps.public()


@app.get("/api/channels")
def all_channels():
    return [{"name": key, "label": label, "unit": unit} for key, (label, unit) in CHANNELS.items()]


async def start_sd():
    """Start SD logging next to the eMMC CSV. Returns a warning, or None when SD is recording."""
    if not runtime.hardware.get('sd_mounted'):
        return 'SDカードが認識されていません。本体（eMMC）にだけ記録しています。電源を入れ直すとSDも記録します。'
    if runtime.hardware.get('sd_errors',0):
        return 'SD異常が残っています。本体（eMMC）にだけ記録しています。カードを確認して電源を入れ直してください。'
    try:
        before=json.loads(await runtime.bridge.call('logger.status'))
        if runtime.record_sd_first is None:
            runtime.record_sd_first=before.get('sd_file',0)+(0 if before.get('sd_logging') else 1)
        result=await runtime.bridge.command("LOG1")
        if result!='recording':raise RuntimeError('SD start rejected')
        for _ in range(50):
            state=json.loads(await runtime.bridge.call('logger.status'))
            if state.get('sd_logging'):break
            await asyncio.sleep(.1)
        else:raise RuntimeError('SD start not confirmed')
    except Exception:
        runtime.record_sd_first=None
        with suppress(Exception):await runtime.bridge.command('LOG0')
        return 'SD記録の開始を確認できませんでした。本体（eMMC）にだけ記録しています。'
    return None


@app.post("/api/log/start")
async def start_log():
    async with runtime.record_lock:
        if runtime.sd.status.get("active"):raise HTTPException(409,"SD操作完了後に記録を開始してください")
        if not runtime.status()["connected"]:
            raise HTTPException(409, "MCUからの受信を確認してから記録を開始してください")
        # eMMC always records; a missing or failing SD card is only a warning.
        runtime.recorder.start(runtime.config)
        if runtime.bridge and not runtime.hardware.get('sd_logging'):
            runtime.sd_note=await start_sd()
        return runtime.status()["logging"]


@app.post("/api/log/stop")
async def stop_log():
    async with runtime.record_lock:
        runtime.auto_started=True
        state={}
        if runtime.bridge and runtime.record_sd_first is None and not runtime.hardware.get('sd_logging'):
            # SD never started for this recording: closing the eMMC CSV must not wait on it.
            with suppress(Exception):await runtime.bridge.command("LOG0")
        elif runtime.bridge:
            try:
                result=await runtime.bridge.command("LOG0")
                state=json.loads(await runtime.bridge.call('logger.status'))
                if result!='stopped' or state.get('sd_logging'):
                    raise RuntimeError('SD stop not confirmed')
            except Exception:
                raise HTTPException(503,'SD保存の完了を確認できません。電源を切らず再度停止してください。')
        runtime.recorder.stop()
        runtime.sd_note=None
        if runtime.bridge and state.get('sd_errors',0):
            runtime.record_sd_first=None
            runtime.sd.status={'active':False,'error':'SD異常を検出しました。本体の予備記録を保存しました。SDを確認して電源を入れ直してください。'}
            raise HTTPException(503,runtime.sd.status['error'])
        if runtime.bridge and runtime.record_sd_first is not None:
            runtime.sd.status={'active':True,'operation':'timestamp','error':None}
            try:
                first=runtime.record_sd_first;last=state['sd_file']
                stamped=await stamp_logs(runtime.bridge,first,last,
                    datetime.fromisoformat(runtime.recorder.started),datetime.now(timezone.utc),
                    ROOT/'sd-journals'/(runtime.recorder.name+'.timestamps.jsonl'))
                meta_path=LOGS/(runtime.recorder.name+'.meta.json')
                meta=json.loads(meta_path.read_text());meta['sd_files']=[f'EL{i:06}.BIN' for i in stamped]
                meta['sd_timestamp_timezone']='Asia/Tokyo';atomic_json(meta_path,meta)
                runtime.record_sd_first=None
            except Exception:
                runtime.sd.status['error']='記録は停止済みですが、SDの日時設定を確認できませんでした。'
                raise HTTPException(503,runtime.sd.status['error'])
            finally:
                runtime.sd.status['active']=False
        return runtime.recorder.status()


def log_path(name):
    if not re.fullmatch(r"(?:DEMO|LOG)_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}\.csv", name):
        raise HTTPException(400, "不正なファイル名です")
    path = LOGS / name
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "ログが見つかりません")
    return path


@app.get("/api/logs")
def list_logs():
    result = []
    for path in sorted(LOGS.glob("*.csv"), reverse=True):
        stat = path.stat()
        result.append({"name": path.name, "size": stat.st_size, "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                       "active": runtime.recorder.file is not None and path.name == runtime.recorder.name, "demo": path.name.startswith("DEMO_")})
    return result


@app.get("/api/logs/{name}/download")
def download(name: str):
    path = log_path(name)
    if runtime.recorder.file and runtime.recorder.name == name:
        raise HTTPException(409, "記録停止後にダウンロードしてください")
    return FileResponse(path, media_type="text/csv", filename=name)


@app.get("/api/logs/{name}/metadata")
def metadata(name: str):
    path = log_path(name).with_suffix(".csv.meta.json")
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.delete("/api/logs/{name}")
async def delete_log(name: str):
    path = log_path(name)
    if runtime.recorder.file and name == runtime.recorder.name:
        raise HTTPException(409, "記録中のログは削除できません")
    path.unlink()
    path.with_suffix(".csv.meta.json").unlink(missing_ok=True)
    return {"deleted": name}


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    if urlparse('//'+ws.headers.get('host','')).hostname not in ('127.0.0.1','localhost','::1','testserver'):
        await ws.close(code=1008)
        return
    origin = ws.headers.get("origin")
    if origin and not same_origin(origin, ws.headers.get("host")):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            await asyncio.wait_for(ws.send_text(runtime.websocket_frame()), timeout=2)
            await asyncio.sleep(0.1)
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError, OSError):
        pass




@app.post('/api/logs/{name}/sd')
async def copy_to_sd(name:str):
    path=log_path(name)
    if runtime.recorder.file:raise HTTPException(409,'記録を停止してからSDへコピーしてください')
    if not runtime.bridge:raise HTTPException(503,'MCU接続待ちです')
    try:runtime.sd.start(path,runtime.bridge)
    except RuntimeError as exc:raise HTTPException(409,str(exc))
    return runtime.sd.status

@app.get('/api/logs/{name}/can')
async def raw_can_log(name:str):
    path=log_path(name)
    if runtime.recorder.name==name and runtime.recorder.file:raise HTTPException(409,'記録停止後にダウンロードしてください')
    target=path.with_name(path.name+'.can.jsonl')
    if not target.exists():raise HTTPException(404,'CAN生ログがありません')
    return FileResponse(target,media_type='application/x-ndjson',filename=target.name)

@app.get('/api/sd/logs')
async def sd_logs():
    if not runtime.bridge:raise HTTPException(503,'MCU接続待ちです')
    if runtime.sd.status.get('active'):raise HTTPException(409,'SD操作中です')
    if runtime.hardware.get('sd_logging'):
        raise HTTPException(409,'記録停止後にSDログ一覧を取得してください')
    # Share one scan between the native UI, web UI and downloads. Repeated
    # timed-out UI requests must not queue hundreds of duplicate MCU commands.
    key=(runtime.resets,runtime.hardware.get('sd_file'),runtime.hardware.get('sd_bytes'))
    async def scan():
        files=[]
        while True:
            if runtime.hardware.get('sd_logging'):
                raise HTTPException(409,'記録停止後にSDログ一覧を取得してください')
            page=json.loads(await runtime.bridge.command('FILES'+str(len(files))))
            files.extend(page)
            if len(page)<16:return files
    try:
        task=runtime.sd_files_task
        if task is None or (task.done() and (task.cancelled() or task.exception() is not None or runtime.sd_files_key!=key)):
            task=runtime.sd_files_task=asyncio.create_task(scan())
            runtime.sd_files_key=key
        files=await asyncio.shield(task)
        return files
    except (ValueError,OSError,RuntimeError) as exc:raise HTTPException(503,str(exc))

@app.get('/api/sd/logs/{index}/download')
async def sd_download(index:int):
    from fastapi.responses import StreamingResponse
    if runtime.recorder.file or runtime.hardware.get('sd_logging'):raise HTTPException(409,'記録停止後にSDログをダウンロードしてください')
    if runtime.sd.status.get('active'):raise HTTPException(409,'SD操作中です')
    files=await sd_logs();entry=next((x for x in files if x['index']==index),None)
    if not entry:raise HTTPException(404,'SDログが見つかりません')
    # Only expose ELB2 contiguous preallocated logger files from the FAT directory.
    boot=bytes.fromhex((await runtime.bridge.sector(0))[5:]);import struct
    part,size=struct.unpack_from('<II',boot,454)
    bpb=bytes.fromhex((await runtime.bridge.sector(part))[5:])
    base=part+struct.unpack_from('<H',bpb,14)[0]+bpb[16]*struct.unpack_from('<I',bpb,36)[0]
    start=base+(entry['cluster']-2)*bpb[13]
    count=(entry['size']+511)//512
    if entry['cluster']<2 or start<base or start+count>part+size or entry['size']>4*1024*1024:raise HTTPException(400,'SDログの範囲が不正です')
    runtime.sd.status={'active':True,'operation':'read','name':f'EL{index:06}.BIN','read_sectors':0,'error':None}
    async def blocks():
        try:
            for n in range(count):
                result=await runtime.bridge.sector(start+n)
                if not result.startswith('data:'):raise OSError(result)
                runtime.sd.status['read_sectors']=n+1
                yield bytes.fromhex(result[5:])[:min(512,entry['size']-n*512)]
        except Exception as exc:
            runtime.sd.status['error']=str(exc) or type(exc).__name__
            raise
        finally:runtime.sd.status['active']=False
    return StreamingResponse(blocks(),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="EL{index:06}.BIN"','Content-Length':str(entry['size'])})

@app.get('/api/sd/logs/{index}/summary')
async def sd_summary(index:int):
    import io,struct,math
    from sd_decode import records
    response=await sd_download(index)
    raw=bytearray()
    async for block in response.body_iterator:raw.extend(block)
    count=0;imu=0;can=0;first=None;last=None;elapsed=0;track=[];speeds=[];distance=0.0
    try:
        for kind,stamp,data in records(io.BytesIO(raw)):
            count+=1
            if first is None:first=stamp
            if last is not None:elapsed+=(stamp-last)%2**32 if (stamp-last)%2**32<60000 else 0
            last=stamp
            if kind==1:imu+=1
            if kind==3:can+=1
            if kind!=2:continue
            if len(data)!=92:raise ValueError('Invalid GNSS record')
            if data[20]<3 or not data[21]&1:continue
            lon=struct.unpack_from('<i',data,24)[0]*1e-7;lat=struct.unpack_from('<i',data,28)[0]*1e-7
            speeds.append(max(0,struct.unpack_from('<i',data,60)[0]*.0036))
            if track:
                a,b=track[-1];dy=math.radians(lat-a);dx=math.radians(lon-b)
                h=math.sin(dy/2)**2+math.cos(math.radians(a))*math.cos(math.radians(lat))*math.sin(dx/2)**2
                distance+=6371*2*math.asin(min(1,math.sqrt(h)))
            track.append([lat,lon])
    except ValueError as exc:raise HTTPException(422,str(exc))
    return {'records':count,'imu':imu,'can':can,'seconds':elapsed/1000,'max_speed':max(speeds,default=0),
            'average_speed':sum(speeds)/len(speeds) if speeds else 0,'distance_km':distance,
            'track':[[lon,lat] for lat,lon in track[::max(1,(len(track)+1999)//2000)]]}

@app.get('/api/sd/decoder')
def sd_decoder():return FileResponse(Path(__file__).parent/'sd_decode.py',filename='sd_decode.py')

app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
