"""Independently close the source sparse-to-card chain without modifying images."""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from package_h700_v6a import constrained
constrained()
O=R/'out/roc-os-user-card-20261105';a=json.loads((O/'image-result.json').read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert a['passed'] and a['full_gzip_verified'] and sha(Path(a['image']))==a['sha256']
def expanded(f):
    digest=hashlib.sha256();blocks=0;zero=b'\0'*(4*1024**2)
    with f.open('rb') as s:
        magic,major,minor,fh,ch,bs,total,n,crc=struct.unpack('<I4H4I',s.read(28))
        assert magic==0xed26ff3a and major==1 and fh>=28 and ch>=12
        s.read(fh-28)
        for _ in range(n):
            kind,reserved,count,size=struct.unpack('<2H2I',s.read(12));s.read(ch-12)
            length=count*bs;blocks+=count
            if kind==0xcac1:
                assert size==ch+length
                while length:
                    b=s.read(min(length,len(zero)));assert b;digest.update(b);length-=len(b)
            elif kind in (0xcac2,0xcac3):
                assert size==ch+(4 if kind==0xcac2 else 0)
                fill=s.read(4)*(len(zero)//4) if kind==0xcac2 else zero
                while length:
                    b=fill[:min(length,len(fill))];digest.update(b);length-=len(b)
            else:
                assert kind==0xcac4 and count==0 and size==ch+4;s.read(4)
        assert blocks==total and not s.read(1)
    return digest.hexdigest()

built=json.loads((R/'out/source64-user-candidate-20261104'/a['source_user_build']).read_text())
assert built['passed'] and sha(R/'out/source64-user-candidate-20261104'/a['source_user_build'])==a['source_build_receipt_sha256']
for name in ['system','vendor']:
 source=Path('/home/lpf/roc-os-user-20261104/out/target/product/roc_os_source64')/(name+'.img')
 assert sha(source)==built['images'][name+'.img']['sha256']
 assert expanded(source)==next(x['sha256'] for x in a['ranges'] if x['name']==name),name
 print('USER_CARD_SOURCE_RANGE_PASS',name,flush=True)
w=Path(a['work']);data=w/'userdata.clean.raw'
s=subprocess.run(['/usr/sbin/debugfs','-R','stat /',str(data)],capture_output=True,text=True,check=True)
(O/'userdata-root-check.txt').write_text(s.stdout+s.stderr)
assert 'Mode:  0771' in s.stdout and 'User:  1000   Group:  1000' in s.stdout
assert 'u:object_r:system_data_root_file:s0' in s.stdout
paired=dict(built['actual_ELF'])
for name,bits,machine in [('bin/linker64',2,183),('bin/linker',1,40),('lib64/libart.so',2,183),('lib/libart.so',1,40)]:
 path='system/apex/com.android.runtime.release/'+name
 dest=w/'paired-ELF'/path;dest.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run(['/usr/sbin/debugfs','-R','dump /'+path+' '+str(dest),str(w/'system.raw')],capture_output=True,text=True,check=True)
 with dest.open('rb') as f:header=f.read(20)
 assert header[:6]==b'\x7fELF'+bytes([bits,1]) and int.from_bytes(header[18:20],'little')==machine,path
 assert sha(dest)==sha(Path('/home/lpf/roc-os-user-20261104/out/target/product/roc_os_source64')/path)
 paired[path]={'ELF_class':bits,'e_machine':machine,'sha256':sha(dest)}
assert len(paired)==10
result={'passed':True,'source_sparse_ranges_match_card':True,'gzip_sha256':a['sha256'],'raw_sha256':a['raw_sha256'],'userdata_root_uid':1000,'userdata_root_gid':1000,'userdata_root_mode':'0771','userdata_context':'u:object_r:system_data_root_file:s0','runtime_or_release_accepted':False,'device_modified':False}
result['actual_ELF']=paired
(O/'final-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('USER_CARD_FINAL_CHECK_PASS',flush=True)
