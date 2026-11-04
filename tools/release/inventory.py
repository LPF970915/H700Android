"""Content inventory of regular source files; symlinks recorded, never followed."""
import argparse,hashlib,json,os,stat,time
from pathlib import Path
EXCLUDED={'.git','.repo','__pycache__'}
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inventory(root,output):
 root=Path(root).resolve();output=Path(output).absolute()
 if output.is_relative_to(root):raise ValueError('Inventory output must be outside source tree')
 count=total=links=0;checkpoint=0;start=time.time()
 with output.open('x',encoding='utf-8') as stream:
  for base,dirs,files in os.walk(root,followlinks=False):
   dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not (Path(base)==root and d=='out'))
   for name in sorted(files+list(dirs)):
    p=Path(base)/name;s=p.lstat();rel=p.relative_to(root).as_posix()
    if stat.S_ISLNK(s.st_mode):
     row={'path':rel,'type':'symlink','target':os.readlink(p)};links+=1
     if name in dirs:dirs.remove(name)
    elif stat.S_ISREG(s.st_mode):
     h=sha(p);after=p.stat()
     if (s.st_ino,s.st_size,s.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('Input changed during inventory: '+rel)
     row={'path':rel,'type':'file','bytes':s.st_size,'mode':stat.S_IMODE(s.st_mode),'sha256':h};count+=1;total+=s.st_size
    else:continue
    stream.write(json.dumps(row,ensure_ascii=True)+'\n')
   if count-checkpoint>=5000:
    checkpoint=count
    output.with_suffix('.progress.json').write_text(json.dumps({'files':count,'bytes':total,'seconds':round(time.time()-start)}))
 return {'files':count,'bytes':total,'symlinks':links,'sha256':sha(output),'exclusions':sorted(EXCLUDED),'seconds':round(time.time()-start,2),'complete_repo_manifest':False}
def verify(root,manifest):
 root=Path(root).resolve();expected=set()
 for line in Path(manifest).read_text().splitlines():
  x=json.loads(line);rel=Path(x['path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe inventory path')
  p=root/rel;expected.add(x['path'])
  # Reject symlink ancestors even when a file's bytes happen to match.
  for a in p.parents:
   if a==root:break
   if a.is_symlink():raise ValueError('Symlink ancestor')
  if x['type']=='symlink':assert p.is_symlink() and os.readlink(p)==x['target']
  else:assert not p.is_symlink() and p.is_file() and p.stat().st_size==x['bytes'] and stat.S_IMODE(p.stat().st_mode)==x['mode'] and sha(p)==x['sha256'],x['path']
 actual=set()
 for b,ds,fs in os.walk(root,followlinks=False):
  ds[:]=[d for d in ds if d not in EXCLUDED and not (Path(b)==root and d=='out')]
  for n in fs+list(ds):
   p=Path(b)/n
   if p.is_symlink() or p.is_file():actual.add(p.relative_to(root).as_posix())
   if p.is_symlink() and n in ds:ds.remove(n)
 assert actual==expected,'Added or removed source inputs'
 return True
if __name__=='__main__':
 from sys import path
 path.insert(0,str(Path(__file__).resolve().parents[1]))
 from package_h700_v6a import constrained
 constrained()
 ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('manifest');ap.add_argument('--verify',action='store_true');a=ap.parse_args()
 print(verify(a.root,a.manifest) if a.verify else json.dumps(inventory(a.root,a.manifest)))
