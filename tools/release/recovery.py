"""Offline ROC userdata backup/restore. Regular image files only; no ADB/disks."""
import argparse,hashlib,json,os,stat,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source64/storage'))
import layout
CHUNK=4*1024**2

def regular(path):
 p=Path(path).absolute()
 for a in [p,*p.parents]:
  if a.is_symlink():raise ValueError('Symlink path refused')
 s=p.lstat()
 if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise ValueError('Require private regular file, no hardlinks/devices')
 return p

def region_hash(f,start,length):
 h=hashlib.sha256();f.seek(start)
 while length:
  b=f.read(min(CHUNK,length))
  if not b:raise ValueError('Short image')
  h.update(b);length-=len(b)
 return h.hexdigest()

def geometry(path,check_fs=True):
 p=regular(path);size=p.stat().st_size
 if size<layout.SEED_BYTES or size%512:raise ValueError('Wrong image size')
 with p.open('rb') as f:
  h=f.read(2048);f.seek(size-1536);tail=f.read(1536)
  if not layout.valid_header(h[512:1024],h[1024:]) or not layout.valid_header(tail[1024:],tail[:1024]):raise ValueError('GPT CRC invalid; no automatic repair')
  a,b=h[512:1024],tail[1024:]
  if struct.unpack_from('<Q',a,72)[0]!=2 or struct.unpack_from('<Q',b,72)[0]!=size//512-3:raise ValueError('Wrong GPT table location')
  if struct.unpack_from('<QQ',a,40)!=(4,size//512-4) or struct.unpack_from('<QQ',b,40)!=(4,size//512-4):raise ValueError('Wrong usable LBA bounds')
  if a[56:72]!=layout.DISK_GUID or b[56:72]!=layout.DISK_GUID or h[1024:]!=tail[:1024]:raise ValueError('Wrong source64 GPT or primary/backup mismatch')
  if struct.unpack_from('<QQ',a,24)!=(1,size//512-1) or struct.unpack_from('<QQ',b,24)!=(size//512-1,1):raise ValueError('GPT physical endpoints mismatch')
  table=h[1024:]
  if any(table[896:]):raise ValueError('Unexpected p8/ROMS')
  for i in range(6):
   start,end=struct.unpack_from('<QQ',table,i*128+32)
   if (start*512,(end-start+1)*512)!=(layout.STARTS[i],layout.LENGTHS[i]):raise ValueError('Protected partition geometry mismatch')
  e=table[768:896];start,end=struct.unpack_from('<QQ',e,32)
  if e[16:32]!=layout.DATA_GUID or start*512!=layout.DATA_START or end!=size//512-4:raise ValueError('Wrong userdata extent')
  f.seek(start*512+1024);sb=f.read(1024)
  if check_fs and (sb[56:58]!=b'\x53\xef' or sb[104:120]!=layout.DATA_FS_UUID.bytes):raise ValueError('Wrong userdata ext4 UUID/superblock')
 return {'image_bytes':size,'start':start*512,'bytes':(end-start+1)*512,'filesystem_uuid':str(layout.DATA_FS_UUID),'gpt_sha256':hashlib.sha256(h+tail).hexdigest()}

def backup(image,bundle):
 image=regular(image);g=geometry(image);bundle=Path(bundle).absolute()
 if bundle.exists() or any(p.is_symlink() for p in [bundle,*bundle.parents]):raise ValueError('New non-symlink backup directory required')
 bundle.mkdir(parents=True,mode=0o700);target=bundle/'userdata.ext4'
 with image.open('rb') as src,os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as dst:
  src.seek(g['start']);left=g['bytes'];h=hashlib.sha256()
  while left:
   b=src.read(min(CHUNK,left))
   if not b:raise ValueError('Short source image')
   h.update(b)
   if b.count(0)==len(b):dst.seek(len(b),1)
   else:dst.write(b)
   left-=len(b)
  dst.truncate(g['bytes']);dst.flush();os.fsync(dst.fileno())
 with image.open('rb') as src:
  g['protected_sha256']=[region_hash(src,0,g['start']),region_hash(src,g['start']+g['bytes'],g['image_bytes']-g['start']-g['bytes'])]
 g.update(schema=1,sha256=h.hexdigest(),scope='userdata only; no GPT/boot/system/vendor restore')
 with os.fdopen(os.open(bundle/'backup.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(json.dumps(g,indent=2)+'\n')
 return g

def restore(image,bundle,execute=False):
 image=regular(image);meta=regular(Path(bundle)/'backup.json');data=regular(Path(bundle)/'userdata.ext4');m=json.loads(meta.read_text());g=geometry(image,check_fs=False)
 if m.get('schema')!=1 or any(m[k]!=g[k] for k in ['image_bytes','start','bytes','filesystem_uuid','gpt_sha256']):raise ValueError('Backup/target identity or geometry mismatch')
 if data.stat().st_size!=g['bytes']:raise ValueError('Backup size mismatch')
 if image==data or os.path.samefile(image,data):raise ValueError('Backup cannot be restore target')
 with data.open('rb') as src:
  if region_hash(src,0,g['bytes'])!=m['sha256']:raise ValueError('Backup checksum mismatch')
 with image.open('rb') as target:
  protected=[region_hash(target,0,g['start']),region_hash(target,g['start']+g['bytes'],g['image_bytes']-g['start']-g['bytes'])]
 if protected!=m.get('protected_sha256'):raise ValueError('Protected OS/boot content differs from backup; migration is not restore')
 plan={'mode':'execute' if execute else 'plan','target':str(image),'start':g['start'],'bytes':g['bytes'],'backup_sha256':m['sha256']}
 if not execute:return plan
 # Backup is fully validated before opening the target for any write.
 with image.open('r+b') as dst,data.open('rb') as src:
  before=[region_hash(dst,0,g['start']),region_hash(dst,g['start']+g['bytes'],g['image_bytes']-g['start']-g['bytes'])]
  dst.seek(g['start']);left=g['bytes']
  while left:
   b=src.read(min(CHUNK,left))
   if not b:raise ValueError('Short backup')
   dst.write(b);left-=len(b)
  dst.flush();os.fsync(dst.fileno())
  assert region_hash(dst,g['start'],g['bytes'])==m['sha256'],'Restored data readback failed'
  assert before==[region_hash(dst,0,g['start']),region_hash(dst,g['start']+g['bytes'],g['image_bytes']-g['start']-g['bytes'])],'Protected ranges changed'
 plan['readback_verified']=True;return plan

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['inspect','backup','restore']);ap.add_argument('image');ap.add_argument('--bundle');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 if a.action!='inspect' and not a.bundle:ap.error('--bundle required')
 if a.action!='restore' and a.execute:ap.error('--execute is restore-only')
 print(json.dumps(geometry(a.image) if a.action=='inspect' else backup(a.image,a.bundle) if a.action=='backup' else restore(a.image,a.bundle,a.execute),indent=2))
