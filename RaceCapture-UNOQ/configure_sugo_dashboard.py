"""Add the SUGO 120-minute endurance dashboard and temperature alerts; run with RaceCapture stopped.

Thresholds follow ncec-roadster track/thermal-limits.md (oil 110 caution / 120 cooling lap /
130 pit in; water is about oil - 10 through the heat exchanger). Re-run to change them.
"""
import argparse
import copy
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--oil-limits',default='110,120,130',help='yellow,red,pit-in in C')
parser.add_argument('--water-limits',default='100,110,120',help='yellow,red,pit-in in C')
parser.add_argument('--no-oil',action='store_true',help='show Speed instead of OilTemp')
args=parser.parse_args()

path=Path('/home/arduino/.config/racecapture/prefs.json')
p=json.loads(path.read_text())
backup=path.with_name('prefs.before-sugo.json')
if not backup.exists(): backup.write_text(json.dumps(p,indent=2))
defaults=json.loads(Path('/opt/racecapture/_internal/resource/defaults/default_dashboard.json').read_text())
template=next(iter(defaults.values()))['gauges'][0]['config']

def gauge(name,i):
    config=copy.deepcopy(template)
    config['Channel']={'channel':name,'overrides':{}}
    visual=config['Settings']['visual_settings']
    # Times are drawn as m:ss and the clock as h:mm:ss, so their "Min" unit would mislead.
    visual.update(show_channel_unit=name in ('WaterTemp','OilTemp','RPM','Speed'),
        corner_radius_pct=.08,outline_thickness_pct=.025,
        outline_color=[.10,.65,.85,1],background_color=[.03,.09,.12,1],channel_alert_element='background',
        channel_labels_font_size_pct=[.50,.16,.12],channel_name_position='bottom',channel_unit_position='top')
    visual['channel_labels_colors']=[[.9,.94,.98,1]]*3
    return dict(config=config,center_x=(i%3+.5)/3,center_y=1-(i//3+.5)/3,size_hint_x=.32,size_hint_y=.31)

# Top: temperatures and revs. Middle: running lap, last lap, best. Bottom: race time, clock, lap number.
# The "Lap Time" gauge type is not used: it titles the running lap "LapTime", like the last lap.
names=['WaterTemp','Speed' if args.no_oil else 'OilTemp','RPM','ElapsedTime','LapTime','BestLap',
    'SessionTime','Utc','CurrentLap']
gauges=[gauge(n,i) for i,n in enumerate(names)]
p['dashboard']['dashboard_logger_v2_sugo']=dict(dash_name='SUGO 120min',dash_type='freeform',locked=True,gauges=gauges)
p['general_prefs']['dashboard_preferences']['last_dash_screen']='dashboard_logger_v2_sugo'

YELLOW,RED=[1.0,.75,0.0,1.0],[.9,.05,.05,1.0]
def color(rgba): return {'color_alertaction':{'color':rgba}}
def rule(kind,low,high,actions):
    return dict(enabled=True,range_type=kind,low_threshold=low,high_threshold=high,
        activate_sec=1.0,deactivate_sec=5.0,alert_actions=actions)
def alerts(channel,limits):
    caution,cooling,pit=(float(v) for v in limits.split(','))
    return {'channel':channel,'alert_rules':[
        rule('-',caution,cooling-.1,[color(YELLOW)]),
        rule('-',cooling,pit-.1,[color(RED)]),
        # The popup's octagon is drawn over its text, so the message goes without a shape.
        rule('>=',pit,0.0,[color(RED),{'popup_alertaction':{'message':'PIT IN','shape':'none','color':RED}}])]}
p.setdefault('alerts',{})
p['alerts']['WaterTemp']=alerts('WaterTemp',args.water_limits)
p['alerts']['OilTemp']=alerts('OilTemp',args.oil_limits)

tmp=path.with_suffix('.sugo.tmp');tmp.write_text(json.dumps(p,indent=2));tmp.replace(path)
print('SUGO dashboard registered:',names,'water',args.water_limits,'oil',args.oil_limits)
