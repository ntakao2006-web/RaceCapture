"""Add only the SensorHub dashboard; run with RaceCapture stopped."""
import copy
import json
from pathlib import Path

path=Path('/home/arduino/.config/racecapture/prefs.json')
p=json.loads(path.read_text())
defaults=json.loads(Path('/opt/racecapture/_internal/resource/defaults/default_dashboard.json').read_text())
template=next(iter(defaults.values()))['gauges'][0]['config']
gauges=[]
for i,name in enumerate(('OilTemp','OilTempOpen','OilTempState')):
    config=copy.deepcopy(template)
    config['Channel']={'channel':name,'overrides':{}}
    visual=config['Settings']['visual_settings']
    visual.update(show_channel_unit=True,corner_radius_pct=.08,outline_thickness_pct=.025,
        outline_color=[.10,.65,.85,1],background_color=[.03,.09,.12,1],
        channel_labels_font_size_pct=[.50,.16,.12],channel_name_position='bottom',channel_unit_position='top')
    visual['channel_labels_colors']=[[.9,.94,.98,1]]*3
    gauges.append(dict(config=config,center_x=(i+.5)/3,center_y=.5,size_hint_x=.32,size_hint_y=.8))
p['dashboard']['dashboard_logger_v2_oiltemp']=dict(
    dash_name='OilTemp / Open: 1=OPEN / State: 0=OK 1=OPEN 2=SHORT 3=DATA 4=LINK',
    dash_type='freeform',locked=True,gauges=gauges)
p['general_prefs']['dashboard_preferences']['last_dash_screen']='dashboard_logger_v2_oiltemp'
temp=path.with_suffix('.oiltemp.tmp');temp.write_text(json.dumps(p,indent=2));temp.replace(path)
print('OilTemp dashboard registered; other dashboards preserved.')
