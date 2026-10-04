"""Keep exported loader names; shorten private C++ names to fit UNO Q's 64 KiB slot."""
import subprocess
import sys
import struct
from pathlib import Path
tool, source, target = sys.argv[1:]
names = subprocess.check_output([tool+'nm', '--defined-only', '-P', source], text=True)
mapping = Path(target+'.symbols')
keep = {'_Z10__loopHookv', '_Z11initVariantv'}
mapping.write_text(''.join(f'{line.split()[0]} z{i:x}\n' for i,line in enumerate(names.splitlines())
                         if line.split()[0].startswith('_Z') and line.split()[0] not in keep))
subprocess.run([tool+'objcopy', '--redefine-syms='+str(mapping), source, target], check=True)

# GNU strip retains ARM $t/$d disassembly mapping symbols even when unreferenced
# in this relocatable LLEXT. Remove ONLY those unused symbols, and remap every
# relocation index. Code/data, exported functions and undefined imports stay intact.
b=Path(target).read_bytes()
Path(target+'.unpruned').write_bytes(b)
h=list(struct.unpack_from('<16sHHIIIIIHHHHHH',b))
assert h[0][4:6]==b'\x01\x01' and h[1]==1 and h[2]==40 and h[10]==0 and h[11]==40
sections=[list(struct.unpack_from('<10I',b,h[6]+i*40)) for i in range(h[12])]
payload=[b[s[4]:s[4]+s[5]] if s[1]!=8 else b'' for s in sections]
symidx=next(i for i,s in enumerate(sections) if s[1]==2)
symbols=list(struct.iter_unpack('<IIIBBH',payload[symidx]))
strings=payload[sections[symidx][6]]
refs={info>>8 for i,s in enumerate(sections) if s[1]==9 and s[6]==symidx
      for _,info in struct.iter_unpack('<II',payload[i])}
keep=[]
for i,s in enumerate(symbols):
    name=strings[s[0]:].split(b'\0',1)[0]
    if name in (b'$t',b'$d') and s[3]==0 and i not in refs:continue
    keep.append(i)
remap={old:new for new,old in enumerate(keep)}
assert refs<=remap.keys()
payload[symidx]=b''.join(struct.pack('<IIIBBH',*symbols[i]) for i in keep)
sections[symidx][5]=len(payload[symidx])
sections[symidx][7]=sum(i<sections[symidx][7] for i in keep)
for i,s in enumerate(sections):
    if s[1]==9 and s[6]==symidx:
        payload[i]=b''.join(struct.pack('<II',offset,(remap[info>>8]<<8)|(info&255))
                            for offset,info in struct.iter_unpack('<II',payload[i]))
out=bytearray(b[:52])
for i,s in enumerate(sections[1:],1):
    align=max(1,s[8]);out.extend(bytes((-len(out))%align));s[4]=len(out)
    out.extend(payload[i])
out.extend(bytes((-len(out))%4));h[6]=len(out)
for s in sections:out.extend(struct.pack('<10I',*s))
out[:52]=struct.pack('<16sHHIIIIIHHHHHH',*h)
for i,s in enumerate(sections):
    if s[1]!=8 and s[2]&2:assert out[s[4]:s[4]+s[5]]==payload[i]
Path(target).write_bytes(out)
print(f'Removed {len(symbols)-len(keep)} unused ARM mapping symbols; preserved {len(refs)} referenced symbols')
