import json, shutil
from pathlib import Path
root=Path('/home/arduino/ecocapture-v2-data').resolve(strict=True)
assert str(root)=='/home/arduino/ecocapture-v2-data' and not root.is_symlink()
config=root/'config.json'
value=json.loads(config.read_text());value['auto_record']=False
config.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
deleted=[]
for name in ('logs','demo-logs','sd-journals','bench-20261001','lte-podium-20261002'):
    target=root/name
    assert target.resolve().parent==root and not target.is_symlink()
    if target.exists():
        count=sum(p.is_file() for p in target.rglob('*'))
        size=sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
        shutil.rmtree(target);deleted.append(dict(name=name,files=count,bytes=size))
    if name=='logs':target.mkdir()
for name in ('telemetry.json',):
    target=root/'public'/name
    if target.exists():target.unlink()
print(json.dumps(dict(deleted=deleted,auto_record=False)))
