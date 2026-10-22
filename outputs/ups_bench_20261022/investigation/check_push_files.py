from pathlib import Path
import subprocess,re,json,collections,tarfile,zipfile
root=Path.cwd()
paths=set(filter(None,subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z']).decode().split('\0')))
paths.update(filter(None,subprocess.check_output(['git','diff','--name-only','-z'],stderr=subprocess.DEVNULL).decode().split('\0')))
hits=[]; sizes=[]; groups=collections.Counter()
patterns={
 'private_key':rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----',
 'github_token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
 'cloud_key':rb'\bAKIA[0-9A-Z]{16}\b',
 'credential_assignment':rb'''(?im)["']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|wifi[_-]?password|podium[_-]?(?:token|key))["']?\s*[:=]\s*["']([^"'\r\n]{5,})["']''',
 'bearer':rb'(?i)bearer\s+[A-Za-z0-9._-]{24,}',
}
for f in sorted(paths):
 p=root/f
 if not p.is_file():continue
 size=p.stat().st_size; sizes.append((size,f));groups[f.split('/')[0]]+=size
 if size>64*1024*1024:continue
 try:data=p.read_bytes()
 except OSError:continue
 archive=[]
 try:
  if p.suffix in ['.tar','.tgz']:
   with tarfile.open(p) as a:
    archive=[(m.name,a.extractfile(m).read()) for m in a.getmembers() if m.isfile() and m.size<8*1024*1024]
  elif p.suffix=='.zip':
   with zipfile.ZipFile(p) as a:
    archive=[(m.filename,a.read(m)) for m in a.infolist() if not m.is_dir() and m.file_size<8*1024*1024]
 except (tarfile.TarError,zipfile.BadZipFile):pass
 for name,body in archive:
  if b'\0' in body[:4000]:continue
  for kind,pat in patterns.items():
   for m in re.finditer(pat,body):
    hits.append({'path':f+'::'+name,'line':body[:m.start()].count(b'\n')+1,'kind':kind})
 if b'\0' in data[:4000]:continue
 for name,pat in patterns.items():
  for m in re.finditer(pat,data):
   value=m.group(1) if m.lastindex else m.group(0)
   if name=='credential_assignment' and (value.startswith((b'${',b'os.',b'process.',b'example',b'YOUR_',b'your_',b'<',b'test',b'dummy',b'config',b'payload',b'settings',b'args.',b'request.')) or len(value)>200):continue
   hits.append({'path':f,'line':data[:m.start()].count(b'\n')+1,'kind':name})
print(json.dumps({'count':len(sizes),'total_mb':sum(x[0] for x in sizes)/1e6,'groups_mb':{k:round(v/1e6,2) for k,v in groups.items()},'largest':sorted(sizes,reverse=True)[:10],'credential_candidates':hits},indent=2))
