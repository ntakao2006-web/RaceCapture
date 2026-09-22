from pathlib import Path
import copy,json,hashlib
import sexpdata as sx
P=Path(__file__).resolve().parents[1]
def ch(a,k):return [z for z in a if isinstance(z,list) and z and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
path=P/'logger_v2.kicad_sch';old=sx.loads(path.read_text(encoding='utf-8'));a=copy.deepcopy(old)
parts={prop(c,'Reference')[2]:c for c in ch(a,'symbol')}
mapping={f'D{i}':'logger_v2_custom:LED_0805_2012Metric_ShieldSilk' for i in range(1,9)}
mapping.update({'U3':'logger_v2_custom:AE_BNO055_BO_ShieldSilk','J5':'logger_v2_custom:PinSocket_1x08_P2.54mm_Vertical_ShieldSilk'})
oldparts={prop(c,'Reference')[2]:c for c in ch(old,'symbol')}
for ref,fp in mapping.items():prop(parts[ref],'Footprint')[2]=fp
restore=copy.deepcopy(a)
for c in ch(restore,'symbol'):
    ref=prop(c,'Reference')[2]
    if ref in mapping:prop(c,'Footprint')[2]=prop(oldparts[ref],'Footprint')[2]
assert restore==old,'Unexpected change outside target Footprint fields'
path.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf-8')
metadata=P/'output/design_review_20260907/reviewed_parts_metadata.json'
rows=json.loads(metadata.read_text(encoding='utf-8'))
for row in rows:
    if row['Reference'] in mapping:row['Footprint']=mapping[row['Reference']]
metadata.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'modified_fields':mapping,'only_footprint_fields_changed':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
