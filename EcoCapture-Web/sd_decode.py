"""Decode standalone ELxxxxxx.BIN logs: python sd_decode.py FILE.BIN [OUTPUT.csv]."""
import csv
import struct
import sys
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

FIELDS=['mcu_ms','AccelX','AccelY','AccelZ','GyroX','GyroY','GyroZ','Roll','Pitch','LongAccel','LatAccel','VertAccel','Lat','Lon','Altitude','GPSSpeed','GPSFix','GPSSats','gnss_itow_ms','imu_raw','imu_calibration']
def convert(source,target):
    nav=None;gnss_at=None;count=0;can_count=0
    can_path=Path(str(target)+'.can.jsonl')
    import json
    with Path(source).open('rb') as stream,Path(target).open('w',encoding='utf-8',newline='') as output,can_path.open('w',encoding='utf-8') as can:
        writer=csv.DictWriter(output,fieldnames=FIELDS);writer.writeheader()
        for kind,stamp,data in records(stream):
            if kind==2:
                if len(data)!=92:raise ValueError('Invalid GNSS record')
                nav=data;gnss_at=stamp;continue
            if kind==3:
                if len(data)<7 or data[6]>8 or len(data)!=7+data[6]:raise ValueError('Invalid CAN record')
                can.write(json.dumps({'mcu_ms':stamp,'channel':data[0],'id':struct.unpack_from('<I',data,1)[0],'extended':bool(data[5]&1),'rtr':bool(data[5]&2),'data':data[7:].hex()})+'\n');can_count+=1;continue
            if kind not in (1,4):raise ValueError('Unknown record type')
            row={'mcu_ms':stamp}
            if kind==1:
                if len(data)!=46:raise ValueError('Invalid IMU record')
                x=struct.unpack('<22h',data[:44])
                row.update(zip(['AccelX','AccelY','AccelZ'],(v/100 for v in x[:3])))
                row.update(zip(['GyroX','GyroY','GyroZ'],(v/16 for v in x[6:9])))
                row.update(Roll=x[10]/16,Pitch=x[11]/16,LongAccel=x[16]/980.665,LatAccel=x[17]/980.665,VertAccel=x[18]/980.665,imu_raw=data.hex(),imu_calibration=data[45])
            if nav is not None and (stamp-gnss_at)%2**32<1000:
                row.update(GPSFix=nav[20],GPSSats=nav[23],gnss_itow_ms=struct.unpack_from('<I',nav)[0])
                if nav[20]>=3 and nav[21]&1:
                    row.update(Lon=struct.unpack_from('<i',nav,24)[0]*1e-7,Lat=struct.unpack_from('<i',nav,28)[0]*1e-7,Altitude=struct.unpack_from('<i',nav,36)[0]/1000,GPSSpeed=struct.unpack_from('<i',nav,60)[0]*.0036)
            writer.writerow(row);count+=1
    return {'rows':count,'can_frames':can_count,'csv':str(target)}

if __name__=='__main__':
    source=Path(sys.argv[1]);target=Path(sys.argv[2]) if len(sys.argv)>2 else source.with_suffix('.csv')
    if target.exists():raise SystemExit('Output already exists; choose a new filename')
    print(convert(source,target))
