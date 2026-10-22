from pathlib import Path
import re,json
root=Path(__file__).resolve().parents[2]
out=Path(__file__).parent
def blocks(s,kind,indent=1):
    for m in re.finditer(r'^'+r'\t'*indent+r'\('+re.escape(kind)+r'(?=[\s)])',s,re.M):
        start=m.start()+indent; depth=0; quote=False; esc=False
        for i in range(start,len(s)):
            c=s[i]
            if quote:
                if esc: esc=False
                elif c=='\\': esc=True
                elif c=='"': quote=False
            elif c=='"': quote=True
            elif c=='(': depth+=1
            elif c==')':
                depth-=1
                if depth==0:
                    yield start,i+1,s[start:i+1];break
def props(b):
    return dict(re.findall(r'\(property "([^"\\]+)" "((?:[^"\\]|\\.)*)"',b))
if __name__=='__main__':
    sch=(root/'circuit/logger_v2_ups/logger_v2_ups.kicad_sch').read_text(encoding='utf-8')
    pcb=(root/'circuit/logger_v2_ups/logger_v2_ups.kicad_pcb').read_text(encoding='utf-8')
    ss={props(b).get('Reference'):props(b) for _,_,b in blocks(sch,'symbol')}
    pp={props(b).get('Reference'):(props(b),re.match(r'\(footprint "([^"]+)"',b)[1]) for _,_,b in blocks(pcb,'footprint')}
    for ref,p in ss.items():
        if not ref or ref.startswith('#'):continue
        if ref not in pp:print('MISSING PCB',ref);continue
        q,fp=pp[ref]
        for k in ['Value','MPN','DigiKey','Footprint']:
            v=fp if k=='Footprint' else q.get(k,'')
            if p.get(k,'')!=v:print(ref,k,p.get(k,''),'PCB:',v)
    print('components',len([r for r in ss if r and not r.startswith('#')]),'PCB footprints',len(pp))
