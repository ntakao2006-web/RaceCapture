"""Expose real LoggerV2 telemetry to the official RaceCapture app on loopback.

The existing acquisition service remains the sole owner of Arduino RouterBridge.
No simulated samples, CAN transmission, firmware updating, or sensor reconfiguration.
"""
import asyncio
import json
import logging
import math
import time
import urllib.request
from datetime import datetime

API = 'http://127.0.0.1:8080'
LOG = logging.getLogger('logger-v2-rcp')

def api(path, data=None):
    req = urllib.request.Request(API + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'X-EcoCapture': '1'})
    with urllib.request.urlopen(req, timeout=2) as r:
        return json.load(r)

def channel(name, unit='', low=-1000, high=1000, precision=3):
    ranges = {'RPM': (0, 10000, 0), 'Speed': (0, 250, 1), 'GPSSpeed': (0, 250, 1),
        'Lat': (-90, 90, 7), 'Lon': (-180, 180, 7), 'GPSFix': (0, 5, 0),
        'GPSSats': (0, 60, 0), 'Roll': (-180, 180, 2), 'Pitch': (-180, 180, 2),
        'Yaw': (0, 360, 2), 'Throttle': (0, 100, 1), 'WaterTemp': (-40, 150, 1),
        'BatteryVolt': (0, 20, 2), 'OilTemp': (-40, 180, 1),
        'OilTempState': (0, 4, 0), 'OilTempOpen': (0, 1, 0),
        'LapCount': (0, 1000, 0), 'CurrentLap': (0, 1000, 0), 'Utc': (0, 0, 0)}
    if name in TIME_CHANNELS:
        ranges[name] = (0, 0, 4)
    low, high, precision = ranges.get(name, (low, high, precision))
    unit = {'°': 'deg', '°/s': 'deg/s', 'm/s²': 'm/s2', '°C': 'C'}.get(unit, unit)
    return dict(nm=name, ut=unit, min=low, max=high, prec=precision, sr=10)

# Lap timer values from EcoCapture (lap.py), in minutes like RaceCapture's own
# time channels, so the app formats them as m:ss. SessionTime carries RaceTime
# (since the first control line crossing); ElapsedTime is the running lap.
TIME_CHANNELS = ('LapTime', 'BestLap', 'ElapsedTime', 'SessionTime')
LAP_VALUES = {'LapCount': 'LapCount', 'CurrentLap': 'CurrentLap', 'LapTime': 'LapTime',
    'BestLap': 'BestLap', 'ElapsedTime': 'ElapsedTime', 'SessionTime': 'RaceTime'}

EXTRA = [('IMUTemp','C'), ('CalSystem',''), ('CalGyro',''), ('CalAccel',''), ('CalMag',''),
    ('QuatW',''), ('QuatX',''), ('QuatY',''), ('QuatZ',''), ('GPSHAcc','m'),
    ('CAN1Rx',''), ('CAN2Rx',''), ('SDErrors',''), ('SDDropped',''), ('SDLogging',''),
    ('BridgeErrors',''), ('IMUErrors',''), ('LapCount',''), ('CurrentLap',''),
    ('LapTime','Min'), ('BestLap','Min'), ('ElapsedTime','Min'), ('SessionTime','Min'), ('Utc','')]

def utc_millis(text):
    """ISO time from the sample (GNSS first, else the host clock) as RaceCapture's Utc."""
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp() * 1000
    except (AttributeError, TypeError, ValueError):
        return None

class Source:
    def __init__(self):
        self.frame = {}
        self.updated = 0
        self.meta = []
        self.config = {}
        self.last_config = 0

    async def poll(self):
        while True:
            started = time.monotonic()
            try:
                if started - self.last_config > 5:
                    config = await asyncio.to_thread(api, '/api/config')
                    base = await asyncio.to_thread(api, '/api/channels')
                    meta = [channel(c['name'], c['unit']) for c in base]
                    names = {c['nm'] for c in meta}
                    for sig in config.get('signals', []):
                        if sig['name'] not in names:
                            meta.append(channel(sig['name'], sig['unit']))
                            names.add(sig['name'])
                        if sig.get('conversion') == 'sensorhub_oiltemp':
                            for suffix in ('State','Open'):
                                name=sig['name']+suffix
                                if name not in names:
                                    meta.append(channel(name, precision=0))
                                    names.add(name)
                    meta.extend(channel(n, u) for n, u in EXTRA if n not in names)
                    self.config, self.meta, self.last_config = config, meta, started
                frame = await asyncio.to_thread(api, '/api/telemetry')
                self.frame, self.updated = frame, time.monotonic()
            except Exception as e:
                LOG.warning('Acquisition service unavailable: %s', e)
            await asyncio.sleep(max(.01, .1 - (time.monotonic() - started)))

    def fresh(self):
        return time.monotonic() - self.updated < 1 and self.frame.get('status', {}).get('connected', False)

    def sample(self, with_meta=False):
        s = self.frame.get('sample') or {}
        values = {}
        if self.fresh():
            values.update(s.get('values', {}))
            values.update(s.get('can_signals', {}))
            values['IMUTemp'] = s.get('imu_temperature_C')
            for field, name in zip(('system','gyro','accel','mag'), ('CalSystem','CalGyro','CalAccel','CalMag')):
                values[name] = (s.get('imu_calibration') or {}).get(field)
            for name, value in zip(('QuatW','QuatX','QuatY','QuatZ'), s.get('quaternion') or []):
                values[name] = value
            values['GPSHAcc'] = s.get('gnss_hacc_m')
            lap = s.get('lap') or {}
            for name, key in LAP_VALUES.items():
                values[name] = lap.get(key)
            values['Utc'] = utc_millis(s.get('gnss_utc') or s.get('host_utc'))
            h = self.frame['status'].get('hardware', {})
            counts = h.get('can_counts', [0,0])
            values.update(CAN1Rx=counts[0], CAN2Rx=counts[1], SDErrors=h.get('sd_errors'),
                SDDropped=h.get('sd_queue_dropped'), SDLogging=h.get('sd_logging'),
                BridgeErrors=self.frame['status'].get('bridge_errors'), IMUErrors=h.get('imu_errors'))
        data, masks = [], [0] * ((len(self.meta) + 31) // 32)
        for i, c in enumerate(self.meta):
            v = values.get(c['nm'])
            if type(v) in (int, float) and math.isfinite(v):
                data.append(v)
                masks[i // 32] |= 1 << (i % 32)
        result = {'t': s.get('mcu_ms', 0), 'd': data + masks}
        if with_meta: result['meta'] = self.meta
        return {'s': result}

    def status(self):
        f = self.frame.get('status', {})
        s = self.frame.get('sample') or {}
        v, h = s.get('values', {}), f.get('hardware', {})
        return {'status': {
            'system': {'model': 'LoggerV2 / UNO Q', 'ver_major': 2, 'ver_minor': 17,
                       'ver_bugfix': 0, 'uptime': h.get('mcu_ms', 0) // 1000},
            'GPS': {'init': v.get('GPSFix') or 0, 'qual': int(bool(v.get('GPSFix'))),
                    # RCP status uses numeric coordinates even before a fix. qual/init
                    # carry validity; telemetry Lat/Lon remain absent in the mask.
                    'lat': v.get('Lat') or 0, 'lon': v.get('Lon') or 0, 'sats': v.get('GPSSats') or 0, 'DOP': 0},
            'logging': {'status': int(bool(h.get('sd_logging'))), 'dur': f.get('logging', {}).get('elapsed_s', 0)},
            'track': {'status': 0, 'valid': False, 'trackId': 0, 'inLap': 0, 'armed': 0}}}

async def client(reader, writer, source):
    LOG.info('RaceCapture connected')
    hz, last_sent, last_meta, buffer = 0, 0, None, b''
    async def send(value):
        writer.write((json.dumps(value, separators=(',', ':'), allow_nan=False) + '\r\n').encode())
        await asyncio.wait_for(writer.drain(), 2)
    try:
        while True:
            try:
                data = await asyncio.wait_for(reader.read(8192), .02)
                if not data: break
                buffer += data
                if len(buffer) > 65536: raise ValueError('Command too large')
            except asyncio.TimeoutError:
                pass
            buffer = buffer.replace(b'\r', b'\n')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if not line.strip(): continue
                obj = json.loads(line)
                if not isinstance(obj, dict) or len(obj) != 1: continue
                cmd, arg = next(iter(obj.items()))
                if cmd not in ('s', 'getStatus'): LOG.info('Command %s', cmd)
                if cmd == 'getVer':
                    await send({'ver': {'name':'RCPMK3', 'fname':'LoggerV2 / UNO Q real sensors',
                        'major':2, 'minor':17, 'bugfix':0, 'serial':'LOGGER-V2-3263089125',
                        'git_info':'uno-q-bridge-1.0', 'release_type':'development'}})
                elif cmd == 'getCapabilities':
                    await send({'capabilities': {'flags':['telemstream'], 'telemetryMaxHz':10,
                        'channels':dict.fromkeys(('analog','imu','gpio','timer','pwm','can','obd2','canChan'),0),
                        'sampleRates':{'gps':10,'sensor':100}, 'db':{'tracks':0,'sectors':0}}})
                elif cmd == 'getMeta': await send({'meta':source.meta})
                elif cmd == 'getStatus': await send(source.status())
                elif cmd == 's': await send(source.sample(bool(isinstance(arg,dict) and arg.get('meta'))))
                elif cmd == 'setTelemetry':
                    rate = arg.get('rate', -1) if isinstance(arg,dict) else -1
                    if type(rate) in (int,float) and math.isfinite(rate) and rate >= 0:
                        hz = min(rate, 10)
                        LOG.info('Telemetry rate %s, transport %s',hz,arg.get('transport'))
                        last_meta = None
                        await send({cmd:{'rc':1,'rate':hz}})
                    else: await send({cmd:{'rc':-1,'error':'Invalid telemetry rate'}})
                elif cmd == 'log':
                    hz = 10 if (arg.get('en',True) if isinstance(arg,dict) else arg) else 0
                    last_meta = None
                    await send({'logStart' if hz else 'logEnd':1})
                elif cmd in ('getLapCfg','getTrackCfg','getCanCfg','getObd2Cfg','getConnCfg','getImuCfg','getGpsCfg','getAnalogCfg'):
                    await send({cmd[3:4].lower()+cmd[4:]:{}})
                else:
                    await send({cmd:{'rc':-1,'error':'Use LoggerV2 settings in the USB browser for this operation'}})
            now = time.monotonic()
            if hz and now - last_sent >= 1/hz:
                if not source.fresh(): raise ConnectionError('Live sensor data is unavailable')
                await send(source.sample(last_meta != source.meta))
                last_meta, last_sent = source.meta, now
    except (OSError, ValueError, asyncio.TimeoutError) as e:
        LOG.warning('Connection ended: %s', e)
    finally:
        writer.close()
        await writer.wait_closed()
        LOG.info('RaceCapture disconnected')

async def main():
    source = Source()
    poll = asyncio.create_task(source.poll())
    server = await asyncio.start_server(lambda r,w: client(r,w,source), '127.0.0.1', 7223)
    async with server: await server.serve_forever()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    asyncio.run(main())
