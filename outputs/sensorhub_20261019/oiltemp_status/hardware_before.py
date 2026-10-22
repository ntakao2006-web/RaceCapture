"""Decode actual MCU register snapshots; missing/stale measurements stay null."""
import struct
import math
from collections import deque
from models import CHANNELS

class HardwareDecoder:
    def __init__(self):
        self.distance=0.0
        self.last_itow=None
        self.seen_itow=None
        self.gnss_hz=None
        self.gnss_intervals=deque(maxlen=20)
        self.can_values={}
        self.last_ms=None
        self.last_can=[]

    def decode(self, status, batch, config):
        if self.last_ms is not None and status['mcu_ms'] < self.last_ms:
            self.can_values.clear();self.distance=0;self.last_itow=None
            self.seen_itow=None;self.gnss_hz=None;self.gnss_intervals.clear()
        self.last_ms=status['mcu_ms']
        self.last_can=batch.get('can',[])
        for stamp,channel,can_id,extended,rtr,data in self.last_can:
            if rtr:continue
            raw=bytes.fromhex(data)
            for sig in config.signals:
                if sig.channel!=channel or sig.can_id!=can_id or sig.extended!=bool(extended):continue
                width=int(sig.data_type.lstrip('uint'))//8
                if len(raw)<sig.byte_offset+width:continue
                value=int.from_bytes(raw[sig.byte_offset:sig.byte_offset+width],sig.endian,signed=sig.data_type.startswith('int'))
                value=int(bool(value&sig.bit_mask)) if sig.bit_mask else value*sig.scale+sig.offset
                if sig.conversion=='ntc':
                    value=sig.ntc_celsius(value)
                    if value is None:continue
                if math.isfinite(value):
                    history=self.can_values.setdefault(sig.name,deque())
                    history.append((stamp,value))
                    while history and (stamp-history[0][0])%2**32>1500:history.popleft()
        nav=bytes.fromhex(status['nav'])
        valid_nav=len(nav)==92 and status['gnss_at'] and (status['mcu_ms']-status['gnss_at'])%2**32<1000
        fix=valid_nav and nav[20]>=3 and bool(nav[21]&1)
        gps={}
        itow=struct.unpack_from('<I',nav)[0] if valid_nav else None
        gnss_utc=None
        if valid_nav:
            if self.seen_itow is not None:
                dt=(itow-self.seen_itow)%604800000
                if dt and dt<=1000:
                    # Status snapshots may skip a receiver solution. A single
                    # 200 ms host gap must not relabel a 100 ms receiver as 5 Hz.
                    self.gnss_intervals.append(dt)
                    self.gnss_hz=1000/min(self.gnss_intervals)
            self.seen_itow=itow
            gps.update(GPSFix=nav[20],GPSSats=nav[23],GNSSHz=self.gnss_hz)
            if nav[11]&3==3:
                year=struct.unpack_from('<H',nav,4)[0]
                gnss_utc=f'{year:04}-{nav[6]:02}-{nav[7]:02}T{nav[8]:02}:{nav[9]:02}:{nav[10]:02}Z'
        if fix:
            gps.update(Lon=struct.unpack_from('<i',nav,24)[0]*1e-7,Lat=struct.unpack_from('<i',nav,28)[0]*1e-7,Altitude=struct.unpack_from('<i',nav,36)[0]/1000,GPSSpeed=struct.unpack_from('<i',nav,60)[0]*.0036,Yaw=struct.unpack_from('<i',nav,64)[0]*1e-5)
            if self.last_itow is not None:
                dt=(itow-self.last_itow)%604800000
                if 0<dt<=1000:self.distance+=gps['GPSSpeed']*dt/3600000
            self.last_itow=itow
            gps['Distance']=self.distance
        else:self.last_itow=None
        samples=[]
        for seq,stamp,data in batch.get('rows',[]):
            raw=bytes.fromhex(data)
            if len(raw) not in (0,46):raise ValueError('Invalid BNO055 snapshot')
            imu_ok=len(raw)==46
            if not imu_ok:raw=bytes(46)
            x=struct.unpack('<22h',raw[:44]);v=dict.fromkeys(CHANNELS)
            v.update(gps)
            if imu_ok:
                for i,name in enumerate(('AccelX','AccelY','AccelZ')):v[name]=x[i]/100
                for i,name in enumerate(('GyroX','GyroY','GyroZ')):v[name]=x[6+i]/16
                v.update(Roll=x[10]/16,Pitch=x[11]/16,LongAccel=x[16]/980.665,LatAccel=x[17]/980.665,VertAccel=x[18]/980.665)
            decoded={name:next((value for at,value in reversed(history) if (stamp-at)%2**32<=1000),None) for name,history in self.can_values.items()}
            for name,value in decoded.items():
                if name in v:v[name]=value
            samples.append({'schema':1,'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':stamp,'values':v,'can_signals':decoded,'gnss_utc':gnss_utc,'gnss_itow_ms':itow,'imu_raw':data,'imu_calibration':({'system':raw[45]>>6,'gyro':raw[45]>>4&3,'accel':raw[45]>>2&3,'mag':raw[45]&3} if imu_ok else None),'imu_temperature_C':(raw[44] if raw[44]<128 else raw[44]-256) if imu_ok else None,'quaternion':[q/16384 for q in x[12:16]] if imu_ok else None,'gnss_hacc_m':struct.unpack_from('<I',nav,40)[0]/1000 if fix else None})
        return samples,{'imu':'正常' if status['imu_address'] else '未検出','gnss':'測位中' if fix else '測位待ち' if valid_nav else '未受信','can':f"CAN1 {status['can_counts'][0]} フレーム（受信専用） / CAN2 センサーハブ {status['can_counts'][1]} フレーム",'sd':'未検出' if not status['sd_ready'] else '記録欠落あり' if status.get('sd_queue_dropped') else 'FAT32を認識できません' if status.get('sd_mounted') is False or status.get('sd_mounted')==0 else f"記録中 EL{status.get('sd_file',0):06}.BIN" if status.get('sd_logging') else '保存エラー' if status.get('sd_errors') else '認識済み' if status['sd_ready'] else '未検出','lte':'電源OFF / SIM・アンテナ未接続','camera':'未接続'}
