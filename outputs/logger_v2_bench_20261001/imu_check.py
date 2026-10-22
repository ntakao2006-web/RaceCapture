from gnss_service import Gnss
import json,pathlib,time,struct,math,collections,os
g=Gnss();c=g.c;out=pathlib.Path('/data/bench-20261001/imu');out.mkdir(exist_ok=True);report={}
def cmd(s):return c.command(s)['result']
def read(page,reg,n=1):
 r=cmd(f'J{page},{reg},{n}');assert r.startswith('data:'),r;return bytes.fromhex(r[5:])
def write(page,reg,v):assert cmd(f'K{page},{reg},{v}')=='written'
def state():return c.state()['imu']
def wait(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:g.drain();g.frames=[];time.sleep(.03)
def mode(m):write(0,0x3d,m);wait(.04 if m==0 else .2)
def sample(name,duration):
 before=state();bg=c.state();start=time.monotonic();rows=[];pvt=[];sats=[]
 with (out/(name+'.jsonl')).open('w') as f:
  while time.monotonic()-start<duration:
   s=state();b=bytes.fromhex(s['raw']);v=struct.unpack_from('<22h',b)
   s.update({'host_s':time.monotonic()-start,'acc_m_s2':[x/100 for x in v[:3]],'mag_uT':[x/16 for x in v[3:6]],'gyro_deg_s':[x/16 for x in v[6:9]],'euler_deg':[x/16 for x in v[9:12]],'quat':[x/16384 for x in v[12:16]],'linear_acc_m_s2':[x/100 for x in v[16:19]],'gravity_m_s2':[x/100 for x in v[19:22]],'temp_C':struct.unpack_from('<b',b,44)[0],'calib':b[45]})
   rows.append(s);f.write(json.dumps(s)+'\n');g.drain()
   for frame in g.frames:
    if frame[2:4]==b'\x01\x07' and len(frame)==100:pvt.append(struct.unpack_from('<I',frame,6)[0]);sats.append(frame[29])
   g.frames=[];time.sleep(.03)
  f.flush();os.fsync(f.fileno())
 after=state();ag=c.state();norm=lambda vv:math.sqrt(sum(x*x for x in vv))
 summary={'host_rows':len(rows),'mcu_samples':after['seq']-before['seq'],'mcu_elapsed_ms':after['mcu_ms']-before['mcu_ms'],'imu_errors_delta':after['errors']-before['errors'],'gnss_i2c_errors_delta':ag['i2c_errors']-bg['i2c_errors'],'gnss_pvt_count':len(pvt),'gnss_itow_intervals_ms':dict(collections.Counter((b-a)%604800000 for a,b in zip(pvt,pvt[1:]))),'acc_norm_min_max':[min(norm(s['acc_m_s2']) for s in rows),max(norm(s['acc_m_s2']) for s in rows)],'gyro_norm_max':max(norm(s['gyro_deg_s']) for s in rows),'quat_norm_min_max':[min(norm(s['quat']) for s in rows),max(norm(s['quat']) for s in rows)],'euler_axis_ranges':[[min(s['euler_deg'][i] for s in rows),max(s['euler_deg'][i] for s in rows)] for i in range(3)],'last':rows[-1]}
 (out/(name+'.summary.json')).write_text(json.dumps(summary,indent=2));print(name,json.dumps(summary),flush=True);return summary
def irq_config(threshold,mask):
 mode(0);write(1,0x10,0);write(1,0x0f,0);write(1,0x12,0xe0);write(1,0x13,2);write(1,0x14,threshold);cmd('A');write(1,0x10,0x20);write(1,0x0f,mask);mode(1)
try:
 report['probe']=cmd('I');assert report['probe'] in ['address=40','address=41'],report
 report['ids_initial']=read(0,0,7).hex();assert report['ids_initial'].startswith('a0')
 report['mode_initial']=read(0,0x3d)[0];mode(1)
 report['reset']=cmd('H');report['ids_after_hardware_reset']=read(0,0,7).hex();report['mode_after_hardware_reset']=read(0,0x3d)[0];assert report['mode_after_hardware_reset']!=1
 mode(0)
 write(0,0x3f,1);wait(1);report['self_test']=read(0,0x36)[0];assert report['self_test']==15
 mode(1);write(0,0x3f,0x20);wait(1);report['ids_after_soft_reset']=read(0,0,7).hex();report['mode_after_soft_reset']=read(0,0x3d)[0];assert report['mode_after_soft_reset']!=1
 mode(0);write(0,0x3b,0);write(0,0x3e,0);mode(12);cmd('Q');wait(1)
 report['status_ndof']=read(0,0x39,2).hex();assert report['status_ndof']=='0500'
 report['baseline_400k']=sample('baseline_400k',20)
 cmd('Z');report['baseline_100k']=sample('baseline_100k',15);cmd('F')
 irq_config(255,0x20);cmd('A');wait(.5);quiet=state();report['high_threshold_quiet']=quiet;assert quiet['int_pin']==0
 irq_config(1,0);cmd('A');wait(.3);masked=state();first=read(0,0x37)[0];second=read(0,0x37)[0];report['masked']={'snapshot':masked,'status_first':first,'status_second':second};assert masked['int_pin']==0 and first&0x20 and second==0
 irq_config(1,0x20);wait(.3);latched=state();wait(.4);held=state();report['latched']={'first':latched,'held':held};assert latched['int_pin']==1 and latched['irq_status']&0x20 and held['irq_rise']==latched['irq_rise']
 cycles=[]
 for i in range(12):
  mode(0);cmd('A');wait(.03);low=state();assert low['int_pin']==0
  mode(1);wait(.12);high=state();cycles.append({'low':low,'high':high});assert high['int_pin']==1 and high['irq_rise']>low['irq_rise'] and high['irq_status']&0x20
 report['irq_cycles']=cycles;report['pps_exti_conflict_test']=cmd('E')
 mode(0);write(1,0x10,0);write(1,0x0f,0);cmd('A');mode(12);wait(.5)
 report['irq_disabled_final']=state();assert report['irq_disabled_final']['int_pin']==0
 report['movement_ready']=True
except Exception as e:
 report['error']=str(e);print('ERROR',repr(e),flush=True)
finally:
 (out/'automated_report.json').write_text(json.dumps(report,indent=2));print('AUTOMATED_RESULT',json.dumps({k:v for k,v in report.items() if k not in ['baseline_400k','baseline_100k','irq_cycles']}),flush=True)
