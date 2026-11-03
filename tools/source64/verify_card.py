"""Close the sparse-build-to-card hash chain; read-only artifact checks."""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
R=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'tools'))
from package_h700_v6a import constrained
constrained()
O=R/'out/roc-os-source64-card-20261104'
a=json.loads((O/'image-result.json').read_text())
p=json.loads((R/'docs/baselines/roc-os-source64-round2-20261103/completion.json').read_text())
def sha(f):
    with f.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
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
for name in ['system','vendor']:
    f=Path('/home/lpf/roc-os-source64-20261103/out/target/product/roc_os_source64')/(name+'.img')
    assert sha(f)==p['images'][name+'.img']['sha256']
    assert expanded(f)==next(x['sha256'] for x in a['ranges'] if x['name']==name)
    print('CARD_SOURCE_RANGE_PASS',name,flush=True)
w=Path(a['work']);data=w/'userdata.clean.raw'
s=subprocess.run(['/usr/sbin/debugfs','-R','stat /',str(data)],capture_output=True,text=True,check=True)
(O/'userdata-root-check.txt').write_text(s.stdout+s.stderr)
assert 'Mode:  0771' in s.stdout and 'User:  1000   Group:  1000' in s.stdout
assert 'u:object_r:system_data_root_file:s0' in s.stdout
result=dict(passed=True,source_sparse_ranges_match_card=True,compressed_sha256=a['sha256'],
            userdata_root_uid=1000,userdata_root_gid=1000,userdata_root_mode='0771',
            userdata_context='u:object_r:system_data_root_file:s0',device_modified=False)
(O/'final-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('CARD_FINAL_CHECK_PASS',flush=True)
