import uuid
from inspect_schematic import path,source,root,children,child

edits=[]
clock=next(n for n in children(root,'label') if n[1]=='PullUpCLK' and child(n,'at')[1:3]==['81.28','43.18'])
old=source[clock.start:clock.end]
edits.append((clock.start,clock.end,old.replace('(at 81.28 43.18 0)','(at 81.28 38.1 0)')))
tx=next(n for n in children(root,'wire') if [p[1:] for p in child(n,'pts')[1:]]==[['81.28','38.1'],['105.41','38.1']])
original_uuid=child(tx,'uuid')[1]
segments=[((81.28,43.18),(96.52,43.18)),((96.52,43.18),(96.52,38.1)),((96.52,38.1),(105.41,38.1))]
def number(value):return format(value,'.10g')
def wire(a,b,uid):
    return '(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)'%(*map(number,a),*map(number,b),uid)
replacement='\n\t'.join(wire(a,b,original_uuid if i==0 else str(uuid.uuid4())) for i,(a,b) in enumerate(segments))
edits.append((tx.start,tx.end,replacement))
for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
with path.open('w',encoding='utf-8',newline='\n') as output:output.write(source)
print('CAN TX: U3.23/RB2 -> U1.1/TXD; PullUpCLK: U3.21/RB0 -> U2.11')
