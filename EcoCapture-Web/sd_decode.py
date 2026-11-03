"""Decode standalone ELxxxxxx.BIN logs: python sd_decode.py FILE.BIN [OUTPUT.csv] [--config config.json] [--mount imu_mount.json].

With the logger's vehicle configuration, each configured CAN signal becomes a CSV
column decoded exactly as the logger does live (hardware.HardwareDecoder): a value
is kept for 1 s after its frame, and sensor-hub oil temperature adds <name>State
(0 OK, 1 open, 2 short, 3 bad frame, 4 no frame). Raw frames still go to .can.jsonl.

LongAccel/LatAccel/VertAccel are the car's axes from the mounting calibration, run
over the file exactly as the logger runs it live (imu_mount.py). The SD card holds
only the raw IMU, so the calibration starts from --mount (GET /api/imu/mount, or the
first imu_mount cell of the eMMC log of the same drive); without it, it is taken
again at the first stop. The calibration in use is in the imu_mount column.
"""
import argparse
import csv
import struct
import zlib
from pathlib import Path

def records(stream):
    expected=0;file_id=None
    while block:=stream.read(512):
        if len(block)!=512:raise ValueError('Truncated SD block')
        if block[:4]!=b'ELB2':raise ValueError('Invalid SD block signature')
        ident,sequence,used=struct.unpack_from('<IIH',block,4)
        if file_id is None:file_id=ident
        if ident!=file_id or sequence!=expected:raise ValueError('Missing or reordered SD block')
        if zlib.crc32(block[:508])!=struct.unpack_from('<I',block,508)[0]:raise ValueError('SD block CRC mismatch')
        if not 16<=used<=508:raise ValueError('Invalid SD payload length')
        expected+=1;pos=16
        while pos<used:
            if pos+6>used:raise ValueError('Truncated record header')
            kind,size,stamp=struct.unpack_from('<BBI',block,pos);pos+=6
            if pos+size>used:raise ValueError('Truncated record')
            yield kind,stamp,block[pos:pos+size]
            pos+=size

FIELDS=['mcu_ms','AccelX','AccelY','AccelZ','GyroX','GyroY','GyroZ','Roll','Pitch','LongAccel','LatAccel','VertAccel','Lat','Lon','Altitude','GPSSpeed','GPSFix','GPSSats','gnss_itow_ms','imu_raw','imu_calibration','imu_mount']

def can_columns(config):
    from models import signal_columns
    names=signal_columns(config)
    if clash:=set(names)&set(FIELDS):raise ValueError(f'CAN signal name clashes with an SD column: {sorted(clash)}')
    return names

def new_decoder():
    from hardware import HardwareDecoder
    return HardwareDecoder()

def convert(source,target,config=None,decoder=None,mount=None):
    """Pass the same decoder for consecutive files so a value (and the mounting calibration) is not lost at each
    file boundary. mount: a saved calibration (imu_mount.py state) to start from when no decoder is passed.
    Without config and decoder this needs only imu_mount.py next to it (the Web screen's download)."""
    nav=None;gnss_at=None;count=0;can_count=0;last_ms=None
    can_path=Path(str(target)+'.can.jsonl')
    import json
    extra=can_columns(config) if config is not None else []
    if config is not None:
        from models import log_value
        if decoder is None:decoder=new_decoder()
    if decoder is not None and decoder.last_ms is not None:last_ms=decoder.last_ms
    if decoder is not None:imu=decoder.mount
    else:
        from imu_mount import ImuMount
        imu=ImuMount()
    if mount and (decoder is None or decoder.last_ms is None):imu.load(mount)
    last_mount=None
    with Path(source).open('rb') as stream,Path(target).open('w',encoding='utf-8',newline='') as output,can_path.open('w',encoding='utf-8') as can:
        writer=csv.DictWriter(output,fieldnames=FIELDS+extra);writer.writeheader()
        for kind,stamp,data in records(stream):
            if last_ms is not None and stamp<last_ms:
                imu.restart()  # MCU restarted: the calibration stays, its short-term sums do not
                if decoder is not None:decoder.can_values.clear();decoder.can_states.clear()  # earlier frames are not current
            last_ms=stamp
            if decoder is not None:decoder.last_ms=stamp
            if kind==2:
                if len(data)!=92:raise ValueError('Invalid GNSS record')
                nav=data;gnss_at=stamp;imu.on_pvt(nav)
                continue
            if kind==3:
                if len(data)<7 or data[6]>8 or len(data)!=7+data[6]:raise ValueError('Invalid CAN record')
                frame={'mcu_ms':stamp,'channel':data[0],'id':struct.unpack_from('<I',data,1)[0],'extended':bool(data[5]&1),'rtr':bool(data[5]&2),'data':data[7:].hex()}
                can.write(json.dumps(frame)+'\n');can_count+=1
                if config is not None:decoder.feed_can([list(frame.values())],config)
                continue
            if kind not in (1,4):raise ValueError('Unknown record type')
            row={'mcu_ms':stamp}
            if nav is not None and (stamp-gnss_at)%2**32<1000:
                row.update(GPSFix=nav[20],GPSSats=nav[23],gnss_itow_ms=struct.unpack_from('<I',nav)[0])
                if nav[20]>=3 and nav[21]&1:
                    row.update(Lon=struct.unpack_from('<i',nav,24)[0]*1e-7,Lat=struct.unpack_from('<i',nav,28)[0]*1e-7,Altitude=struct.unpack_from('<i',nav,36)[0]/1000,GPSSpeed=struct.unpack_from('<i',nav,60)[0]*.0036)
            decoded=decoder.can_snapshot(stamp,config)[0] if config is not None else {}
            if extra:row.update((name,log_value(decoded.get(name))) for name in extra)
            if kind==1:
                if len(data)!=46:raise ValueError('Invalid IMU record')
                x=struct.unpack('<22h',data[:44])
                row.update(zip(['AccelX','AccelY','AccelZ'],(v/100 for v in x[:3])))
                row.update(zip(['GyroX','GyroY','GyroZ'],(v/16 for v in x[6:9])))
                row.update(Roll=x[10]/16,Pitch=x[11]/16,imu_raw=data.hex(),imu_calibration=data[45])
                speed=decoded.get('Speed') if isinstance(decoded.get('Speed'),(int,float)) else row.get('GPSSpeed')
                car=imu.add([x[0]/100,x[1]/100,x[2]/100],[x[6]/16,x[7]/16,x[8]/16],speed)
                if car:row.update(LongAccel=car[0],LatAccel=car[1],VertAccel=car[2])
                state=imu.state()
                if state is not last_mount:row['imu_mount']=json.dumps(state,separators=(',',':'));last_mount=state
            writer.writerow(row);count+=1
    return {'rows':count,'can_frames':can_count,'csv':str(target)}

def load_config(path):
    from models import Configuration
    return Configuration.model_validate_json(Path(path).read_text(encoding='utf-8'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Decode an ELxxxxxx.BIN from the V2 shield SD card')
    parser.add_argument('source',type=Path);parser.add_argument('target',type=Path,nargs='?')
    parser.add_argument('--config',type=Path,help="the logger's config.json (GET /api/config); adds a column per CAN signal")
    parser.add_argument('--mount',type=Path,help="the logger's mounting calibration (GET /api/imu/mount) to start from")
    args=parser.parse_args()
    target=args.target or args.source.with_suffix('.csv')
    if target.exists():raise SystemExit('Output already exists; choose a new filename')
    import json
    mount=json.loads(args.mount.read_text(encoding='utf-8')) if args.mount else None
    print(convert(args.source,target,load_config(args.config) if args.config else None,mount=mount))
