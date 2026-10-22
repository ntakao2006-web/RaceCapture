import json,re
from pathlib import Path

path=Path('circuit/SensorHub/SensorHub.kicad_sch')
source=path.read_text(encoding='utf-8')
tokens=list(re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',source))
index=0
def parse():
    global index
    token=tokens[index];index+=1
    if token.group()!='(':
        value=token.group()
        return json.loads(value) if value.startswith('"') else value
    values=[]
    while tokens[index].group()!=')':values.append(parse())
    end=tokens[index].end();index+=1
    return Node(values,token.start(),end)
class Node(list):
    def __init__(self,values,start,end):super().__init__(values);self.start=start;self.end=end
def children(node,key):return [x for x in node if isinstance(x,Node) and x[0]==key]
def child(node,key):return next(iter(children(node,key)),None)
root=parse()
if __name__=='__main__':
    for symbol in children(root,'symbol'):
        props={x[1]:x[2] for x in children(symbol,'property')}
        if props.get('Reference') in ('U1','U2','U3'):
            print(props.get('Reference'),child(symbol,'lib_id'),child(symbol,'at'),child(symbol,'mirror'))
    for symbol in child(root,'lib_symbols')[1:]:
        if isinstance(symbol,Node) and symbol[1]=='SensorHub:PIC18F26Q84-xSP':
            for unit in children(symbol,'symbol'):
                for pin in children(unit,'pin'):
                    if child(pin,'number')[1] in ('14','21','22','23','24','25'):
                        print('PIN',child(pin,'number'),child(pin,'name'),child(pin,'at'))
    for label in children(root,'label'):
        if label[1]=='PullUpCLK':print('LABEL',source[label.start:label.end])
    for wire in children(root,'wire'):
        pts=child(wire,'pts')[1:]
        if any(40<float(p[1])<120 and 30<float(p[2])<56 for p in pts):
            print('WIRE',source[wire.start:wire.end])
