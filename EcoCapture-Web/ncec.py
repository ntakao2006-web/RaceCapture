"""Confirmed fields from the supplied NCEC 2005 MT / NOPRO specification (2026-09-06)."""
from collections import deque
from models import Signal

FIELDS=[
 ('RPM','rpm',0x201,0,'uint16',.25,0,None),
 ('Speed','km/h',0x201,4,'uint16',.01,-100,None),
 *[(name,'km/h',0x4B0,index*2,'uint16',.01,-100,None) for index,name in enumerate(('WheelFrontA','WheelFrontB','WheelRearA','WheelRearB'))],
 ('WaterTemp','°C',0x240,1,'uint8',1,-40,None),
 ('WaterTempBackup','°C',0x420,0,'uint8',1,-40,None),
 ('Throttle','%',0x240,3,'uint8',100/255,0,None),
 ('IntakeTemp','°C',0x240,4,'uint8',1,-40,None),
 ('FuelLevelRaw','%',0x430,0,'uint8',100/255,0,None),
 ('ClutchDisengaged','',0x231,1,'uint8',1,0,2),
]
LABELS=dict(zip([x[0] for x in FIELDS],['回転数','車速','前A輪速','前B輪速','後A輪速','後B輪速','水温','水温（冗長）','スロットル','吸気温','燃料（生値）','クラッチ断']))
LABELS['FuelLevel']='燃料（2秒平均）'
OBD_PIDS=[0x04,0x05,0x0B,0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x1F,0x33,0x34,0x42,0x43,0x44,0x45,0x47,0x49,0x4A,0x4C]

def preset():
 return {'profile':'ncec-2005-mt','can_bitrate':500000,'signals':[Signal(name=n,unit=u,can_id=i,byte_offset=b,data_type=t,endian='big',scale=s,offset=o,bit_mask=m).model_dump() for n,u,i,b,t,s,o,m in FIELDS],
 'vehicle':'NCEC 2005 MT / DSCなし / 後期エンジン・NOPRO MZ-TUNE+',
 'source_date':'2026-09-06','rpm_display_max':8000,'hardware_connected':False,'transmit_enabled':False,
 'obd':{'request_id':0x7E0,'response_id':0x7E8,'confirmed_pids':OBD_PIDS,'enabled':False},
 'notes':['輪速のA/Bと左右の対応は未確定です。','燃料は生値と2秒移動平均を分け、満タンを100%へ再補正しません。','油温・油圧・舵角・ブレーキ圧は取得対象に含めません。','回転数の式の実測検証範囲は3439rpmまでです。','CAN受信回路未接続。診断要求を含めCAN送信は行いません。']}

class Decoder:
 def __init__(self):self.fuel=deque();self.last_time=None;self.counter=None;self.counter_time=None;self.anomalies=0
 def decode(self,can_id,data,timestamp_ms):
  if self.last_time is not None and timestamp_ms<self.last_time:raise ValueError('時刻は昇順にしてください')
  self.last_time=timestamp_ms
  values={}
  for n,u,i,b,t,s,o,m in FIELDS:
   if can_id!=i:continue
   width=2 if t=='uint16' else 1
   if len(data)<b+width:raise ValueError(f'0x{can_id:X}のデータが短すぎます')
   raw=int.from_bytes(data[b:b+width],'big')
   values[n]=int(bool(raw&m)) if m is not None else raw*s+o
  if 'FuelLevelRaw' in values:
   self.fuel.append((timestamp_ms,values['FuelLevelRaw']))
   while self.fuel and self.fuel[0][0]<timestamp_ms-2000:self.fuel.popleft()
   while len(self.fuel)>2048:self.fuel.popleft()
   values['FuelLevel']=sum(v for _,v in self.fuel)/len(self.fuel)
  quality=None
  if can_id==0x211:
   if len(data)!=8:raise ValueError('0x211は8バイト必要です')
   current=data[7]
   if self.counter is not None and timestamp_ms-self.counter_time<=100:
    delta=(current-self.counter)%256
    quality={'counter':current,'delta':delta,'continuous':delta==1}
    if delta!=1:self.anomalies+=1
   else:quality={'counter':current,'delta':None,'continuous':None}
   self.counter=current;self.counter_time=timestamp_ms
  return {'timestamp_ms':timestamp_ms,'can_id':f'{can_id:03X}','values':values,'counter_quality':quality}

def decode_text(text):
 decoder=Decoder();rows=[]
 lines=[line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
 if len(lines)>500:raise ValueError('1回500フレームまでです')
 for number,line in enumerate(lines,1):
  try:
   fields=line.split();stamp=int(fields[0]);can_id=int(fields[1],16);data=bytes.fromhex(''.join(fields[2:]))
   if stamp<0 or not 0<=can_id<=0x7ff or not 1<=len(data)<=8:raise ValueError('時刻・標準ID・データ長を確認してください')
   rows.append(decoder.decode(can_id,data,stamp))
  except (ValueError,IndexError) as exc:raise ValueError(f'{number}行目: {exc}') from exc
 return {'rows':rows,'labels':LABELS,'counter_anomalies':decoder.anomalies,'note':'カウンタ異常は欠落・重複・順序・送信元再起動の可能性を示し、欠落数の断定はしません。'}
