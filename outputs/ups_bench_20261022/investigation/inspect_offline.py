from pathlib import Path
import sys, json, re, urllib.request, hashlib
import xml.etree.ElementTree as ET
import pypdfium2 as pdfium

root=Path(__file__).resolve().parents[3]
out=Path(__file__).parent
sys.path.insert(0,str(root/'outputs/ups_revision_20261016'))
from inspect_design import blocks,props

tree=ET.parse(out/'current.xml')
components={c.attrib['ref']:c.findtext('value') for c in tree.findall('./components/comp')}
nets={n.attrib['name']:[f"{x.attrib['ref']}.{x.attrib['pin']}" for x in n.findall('node')] for n in tree.findall('./nets/net')}
pcb=(root/'circuit/logger_v2_ups/logger_v2_ups.kicad_pcb').read_text(encoding='utf-8')
selected={}
for _,_,b in blocks(pcb,'footprint'):
    p=props(b); ref=p.get('Reference','')
    if ref in ['C6','C7','C8','C12','C13','C14','R1','R2','R3','R4','R5','R6','R7','R8','R9','R10','R12','U1','U2','C1','C2']:
        pads=[]
        for _,_,pad in blocks(b,'pad',indent=2):
            pads.append({'number':re.search(r'\(pad "([^"]*)"',pad)[1],
                         'net':(re.search(r'\(net \d+ "([^"]+)"',pad) or [None,None])[1]})
        selected[ref]={'value':p.get('Value'),'pads':pads}
data={'components':components,'nets':nets,'pcb_selected':selected,
      'hashes':{name:hashlib.sha256((root/'circuit/logger_v2_ups'/name).read_bytes()).hexdigest() for name in ['logger_v2_ups.kicad_sch','logger_v2_ups.kicad_pcb']},
      'calculated':{'backup_v':1.2*(30.1+12.1)/12.1,'cap_full_v':.5*(332+12.4+49.9)/49.9,
                    'charge_cap_current_a':.5,'backup_peak_a':5*20/(100*25.5/(100+25.5)),
                    'cap_bank_f':10.5,'balance_current_a':3.9509/2000,
                    'bank_discharge_time_constant_s':21000,
                    'full_bank_energy_j':.5*10.5*(3.9509**2),
                    'charge_supply_threshold_v':1.23*(30.1+12.1)/12.1,
                    'example_4_8v_backup_min_charge_supply_v':4.8*1.025,
                    'example_one_vs_three_caps_smaller_bank_v':3.9509*21/(7+21)},
      'findings':{
          'ups_objective':'Keep Linux running without reboot across brief USB power interruptions lasting a few seconds.',
          'latest_user_smoke_report':'User recollection is uncertain; user now considers that smoke probably did not occur. No smoke event or component damage has been confirmed.',
          'design_caps':'C6,C7,C8: +CAP to CAP-MID; C12,C13,C14: CAP-MID to GND; pad 1 positive in footprint.',
          'protection_gap':'Only total bank voltage feedback; no individual-bank overvoltage clamp or reverse-voltage protection.',
          'smoke_cause':'Unconfirmed; inspect actual polarity, parallel capacitor connectivity, CAP-MID shorts, R4/R6 and FBCH divider. Do not re-energize suspected vented cells.',
          'uno_q_power_path':'Header 5V_USB_VBUS -> D2801 -> 5V_SYS -> U2801 3.8V -> U2802 3.3V; U2802 EN is driven by U2801 PG.',
          'led_limit':'D27201 power LED is on PWR_3P8V. Blue SoC/MCU indicators use PWR_3P3V and controlled signals; blue LED identity is not confirmed.',
          'replug':'SYS is directly on header/USB VBUS; no dedicated hot-plug current limiting or reverse blocking in UPS schematic. Does not prove a capacitor smoke source.'}}
(out/'inspection.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'pcb_selected':selected,'calculated':data['calculated']},indent=2))
docs=[('uno-q','https://docs.arduino.cc/resources/schematics/ABX00162-schematics.pdf',[19,20,21]),
      ]
for name,url,pages in docs:
    path=out/f'{name}.pdf'
    if not path.exists():
        with urllib.request.urlopen(url,timeout=25) as response: path.write_bytes(response.read())
    doc=pdfium.PdfDocument(path)
    for page in pages:
        doc[page].render(scale=2).to_pil().save(out/f'{name}-{page+1}.png')
print('Evidence saved',out)
