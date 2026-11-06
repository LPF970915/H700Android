"""Independently close the source sparse-to-card chain without modifying images."""
from pathlib import Path
import gzip,hashlib,json,re,struct,subprocess,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from package_h700_v6a import constrained
constrained()
O=R/'out/roc-os-user-card-rc3-20261106';a=json.loads((O/'image-result.json').read_text())
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
assert 'u:object_r:system_data_file:s0' in s.stdout
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
assert json.loads((w/'rc2-repair-audit.json').read_text())['passed']
assert json.loads((w/'rc3-repair-audit.json').read_text())['passed']
assert a['authenticated_ADB_retained'] and not a['ADB_root_allowed'] and not a['network_ADB']
for name,h in a['packaging_inputs_sha256'].items():assert sha(R/name)==h,name
lock=json.loads((R/'out/source64-user-candidate-20261104/result-lock.json').read_text())
for name,h in lock['repo_compile_inputs_sha256'].items():assert sha(R/name)==h,name
# Independently read the boot partition from the assembled whole-card file.
from android_bootimg import read_header,component_offsets
from patch_ramdisk import parse
card=w/Path(a['image']).name.removesuffix('.gz')
with card.open('rb') as f:f.seek(155189248);boot=f.read(67108864)
assert hashlib.sha256(boot).hexdigest()==sha(w/'boot.unified.raw')
assert sha(w/'boot.unified.raw')=='04e11bbdb1d14f8672439d948b6f5cbe95e3294634304cd510df10e3064ced49','RC2 working boot must be preserved'
boot_copy=w/'final-card-boot.raw';boot_copy.write_bytes(boot)
_,info=read_header(boot_copy);offsets=component_offsets(info)
assert info['cmdline']=='selinux=1 enforcing=1 androidboot.selinux=enforcing'
entries={e['name']:e for e in parse(gzip.decompress(boot[offsets['ramdisk']:offsets['ramdisk']+info['ramdisk_size']]))}
for name,source in [('init','user_boot_init_rc2.sh'),('grow/prepare-android-dev-bootfix1.sh','prepare_android_dev_bootfix1.sh')]:
 assert entries[name]['data']==(R/'tools/release'/source).read_bytes(),name
 assert entries[name]['mode']==0o100755 and entries[name]['uid']==0 and entries[name]['gid']==0
for node,mode,uid,gid,context in [('/misc',0o1771,1000,9998,'system_data_file'),('/misc/adb',0o2750,1000,2000,'adb_keys_file'),('/misc/adb/adb_keys',0o640,1000,2000,'adb_keys_file')]:
 s=subprocess.run(['/usr/sbin/debugfs','-R','stat '+node,str(data)],capture_output=True,text=True,check=True).stdout
 found=re.search(r'Mode:\s+([0-7]+)',s)
 assert found and int(found[1],8)==mode and f'User:  {uid:4d}   Group:  {gid:4d}' in s,(node,s)
 assert 'u:object_r:'+context+':s0' in s
public=w/'final-ADB-public-key'
subprocess.run(['/usr/sbin/debugfs','-R',f'dump /misc/adb/adb_keys {public}',str(data)],capture_output=True,text=True,check=True)
assert sha(public)=='817982431f56cba42111e2244f7ecc244d2867cbfe5a59c4c6a31b0b99c6e123'
mali=w/'files/vendor/modules/mali_kbase.ko';module=mali.read_bytes()
assert module[:6]==b'\x7fELF\x02\x01' and int.from_bytes(module[18:20],'little')==183
assert b'vermagic=4.9.170 ' in module
result={'passed':True,'source_sparse_ranges_match_card':True,'gzip_sha256':a['sha256'],'raw_sha256':a['raw_sha256'],'userdata_root_uid':1000,'userdata_root_gid':1000,'userdata_root_mode':'0771','userdata_context':'u:object_r:system_data_file:s0','runtime_or_release_accepted':False,'device_modified':False}
result['actual_ELF']=paired
result.update(actual_whole_card_boot_sha256=sha(boot_copy),actual_boot_cmdline=info['cmdline'],actual_ramdisk_entries_match_RC2=True,authenticated_ADB_public_key_seed_verified=True,Mali_ARM64_kernel_4_9_170=True,repo_compile_guards_unchanged=True)
(O/'final-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('USER_CARD_FINAL_CHECK_PASS',flush=True)
