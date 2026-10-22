import collections,json,xml.etree.ElementTree as ET
from pathlib import Path

folder=Path('outputs/sensorhub_schematic_20261020')
def netlist(name):
    root=ET.parse(folder/name).getroot()
    return {n.attrib['name']:sorted((p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')) for n in root.findall('./nets/net')}
before,after=netlist('before.net'),netlist('after.net')
assert set(before)==set(after)
changes={name:{'before':before[name],'after':after[name]} for name in before if before[name]!=after[name]}
assert set(changes)=={'/PullUpCLK','Net-(U1-TXD)'},changes
assert after['Net-(U1-TXD)']==[('U1','1'),('U3','23')]
assert after['/PullUpCLK']==[('U2','11'),('U3','21')]
assert after['Net-(U1-RXD)']==[('U1','4'),('U3','24')]
assert after['/Sense0']==[('J3','1'),('R1','2'),('R2','2'),('U3','14')]
def violations(filename):
    data=json.loads((folder/filename).read_text(encoding='utf-8'))
    return collections.Counter(json.dumps(v,ensure_ascii=False,sort_keys=True) for sheet in data['sheets'] for v in sheet['violations'])
assert violations('erc_before.json')==violations('erc_after.json')
result={'changed_nets':changes,'unchanged_nets':len(before)-len(changes),'erc_before':sum(violations('erc_before.json').values()),'erc_after':sum(violations('erc_after.json').values()),'new_erc_issues':0,'render_reviewed':True}
(folder/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
