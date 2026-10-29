"""Initial LoggerV2 dashboard setup; run with RaceCapture stopped."""
import copy
import json
from pathlib import Path

path=Path('/home/arduino/.config/racecapture/prefs.json')
p=json.loads(path.read_text())
backup=path.with_name('prefs.before-logger-v2.json')
if not backup.exists(): backup.write_text(json.dumps(p,indent=2))
general=p['general_prefs']
general['preferences'].update(conn_type='WiFi',last_known_device='127.0.0.1',
    startup_screen='Dashboard',full_screen_mode='0',distance_units='kilometers',
    temperature_units='Celsius',send_telemetry='0',global_help='False')
general['setup']['setup_enabled']='0'
# 2.19.0 still shows the first-run gauge help with global_help off; it only stays hidden
# when this flag is not True. A non-touch HDMI monitor has no way to press GOT IT.
general.setdefault('help',{})['dashboard_gauge_help']='False'
general['dashboard_preferences'].update(last_dash_screen='dashboard_logger_v2_imu',bottom_gauge_bar_enabled='0')
defaults=json.loads(Path('/opt/racecapture/_internal/resource/defaults/default_dashboard.json').read_text())
template=next(iter(defaults.values()))['gauges'][0]['config']
pages={
    'vehicle':('LoggerV2 - Vehicle',['Speed','RPM','Throttle','GPSSpeed','WaterTemp','BatteryVolt','GPSFix','GPSSats','Distance']),
    'imu':('LoggerV2 - IMU',['AccelX','AccelY','AccelZ','GyroX','GyroY','GyroZ','Roll','Pitch','IMUTemp']),
    'status':('LoggerV2 - Status',['CalSystem','CalGyro','CalAccel','CalMag','SDLogging','SDErrors','SDDropped','CAN1Rx','CAN2Rx'])}
for key,(title,names) in pages.items():
    gauges=[]
    for i,name in enumerate(names):
        config=copy.deepcopy(template)
        config['Channel']={'channel':name,'overrides':{}}
        visual=config['Settings']['visual_settings']
        visual.update(show_channel_unit=True,corner_radius_pct=.08,outline_thickness_pct=.025,
            outline_color=[.10,.65,.85,1],background_color=[.03,.09,.12,1],
            channel_labels_font_size_pct=[.50,.16,.12],channel_name_position='bottom',channel_unit_position='top')
        visual['channel_labels_colors']=[[.9,.94,.98,1]]*3
        gauges.append(dict(config=config,center_x=(i%3+.5)/3,center_y=1-(i//3+.5)/3,
            size_hint_x=.32,size_hint_y=.31))
    p['dashboard']['dashboard_logger_v2_'+key]=dict(dash_name=title,dash_type='freeform',locked=True,gauges=gauges)
p['dashboard'].update({k:v for k,v in defaults.items() if v['dash_name']=='Raw Channels'})
tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(p,indent=2));tmp.replace(path)
