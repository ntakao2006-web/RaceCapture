import configparser
import json
from pathlib import Path
p=Path('/home/arduino/.kivy/config.ini')
c=configparser.ConfigParser()
if p.exists(): c.read(p)
if not c.has_section('kivy'): c.add_section('kivy')
c.set('kivy','default_font',"['Noto Sans CJK JP', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc']")
if not c.has_section('graphics'): c.add_section('graphics')
for k,v in dict(width='1280',height='800',multisamples='0',maxfps='30',fullscreen='auto',borderless='1',position='custom',left='0',top='0').items(): c.set('graphics',k,v)
if not c.has_section('modules'): c.add_section('modules')
c.set('modules','fastnav','')
with p.open('w') as f: c.write(f)

prefs=Path('/home/arduino/.config/racecapture/prefs.json')
if prefs.exists():
    data=json.loads(prefs.read_text())
    data['general_prefs']['preferences']['full_screen_mode']='1'
    tmp=prefs.with_suffix('.display.tmp')
    tmp.write_text(json.dumps(data,indent=2))
    tmp.replace(prefs)
