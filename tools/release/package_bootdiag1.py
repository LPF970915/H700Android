"""Private diagnostic image: Bootfix1 plus early authenticated USB ADB only."""
from pathlib import Path
import base64, datetime, gzip, hashlib, json, subprocess, sys
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
from package_h700_v6a import constrained
constrained()
OUT=REPO/'out/roc-os-user-bootdiag1-20261106-v2';OUT.mkdir(exist_ok=False)
WORK=Path('/home/lpf/roc-os-user-bootdiag1-20261106-v2');WORK.mkdir(exist_ok=False)
BASE=Path('/home/lpf/roc-os-user-card-20261105-v9')
PARENT=REPO/'out/roc-os-user-card-bootfix1-20261106/ROC_OS_ARM64_User_RC1_Bootfix1_20261106.img.gz'
TARGET=OUT/'ROC_OS_ARM64_User_BootDiag1_20261106.img.gz'
RC=REPO/'tools/release/roc-usb-bootdiag1.rc'
KEY=REPO/'out/roc-os-user-rc1-firstboot-20261105/bootdiag1-public-key'
SYS_START=222298112;SYS_LEN=8589934592;DATA_START=10959716352;DATA_LEN=21474836480;TOTAL=32434554368
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args,codes=(0,)):
    x=subprocess.run([str(a) for a in args],capture_output=True,text=True)
    with (WORK/'commands.log').open('a') as f:f.write(json.dumps([str(a) for a in args])+'\n'+x.stdout+x.stderr)
    assert x.returncode in codes,(args,x.returncode,x.stdout[-1200:],x.stderr[-1200:])
    return x
def debug(image,command,write=False):
    return run(['/usr/sbin/debugfs',*(['-w'] if write else []),'-R',command,image]).stdout
def stage(name,**kwargs):
    x={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':name,**kwargs}
    print(json.dumps(x),flush=True);(OUT/'progress.json').write_text(json.dumps(x,indent=2)+'\n')
def attrs(image,path,mode,uid,gid,context):
    for field,value in [('mode',mode),('uid',uid),('gid',gid)]:debug(image,f'set_inode_field {path} {field} {value}',True)
    f=WORK/('context-'+context.replace(':','_'));f.write_bytes(context.encode()+b'\0')
    debug(image,f'ea_set -f {f} {path} security.selinux',True)
def check_attrs(image,path,mode,uid,gid,context):
    s=debug(image,'stat '+path)
    assert f'Mode:  {mode}' in s and f'User:  {uid:4d}   Group:  {gid:4d}' in s,(path,s)
    assert context in s,(path,s)
def dumped(image,path,name):
    dest=WORK/name;debug(image,f'dump {path} {dest}');assert dest.is_file();return dest
result={'passed':False,'diagnostic_only':True,'release_accepted':False,'runtime_accepted':False,'physical_card_written':False,'work':str(WORK),'image':str(TARGET),'ADB_authentication':True,'ADB_root_allowed':False,'network_ADB':False,'SELinux_enforcing_requested':True}
try:
    stage('guard frozen inputs and validate diagnostic RC')
    assert sha(PARENT)=='3f697d7d93357156585564c03053bfaa5f1e2c5d1f9690f8104576d882abbb23'
    assert sha(BASE/'system.raw')=='a456fd08e2cf5166fd66c8308e18768659d2f638248a9d665db98fe9d702eab6'
    assert sha(BASE/'userdata.clean.raw')=='324d48635a79cbdf292250071992f689605113561b5ce9bf9ede4105ab1e3134'
    assert sha(KEY)=='817982431f56cba42111e2244f7ecc244d2867cbfe5a59c4c6a31b0b99c6e123'
    assert len(base64.b64decode(KEY.read_text().strip(),validate=True))==524
    assert len(base64.b64decode(Path('/mnt/c/Users/LPF/.android/adbkey.pub').read_text().split()[0],validate=True))==524
    assert KEY.read_text().strip()==Path('/mnt/c/Users/LPF/.android/adbkey.pub').read_text().split()[0]
    result['host_public_key_sha256']=sha(KEY);result['diagnostic_rc_sha256']=sha(RC)
    host='/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin'
    run([host+'/host_init_verifier',RC])
    policy=REPO/'out/roc-os-user-rc1-firstboot-20261105/actual-rc1-precompiled_sepolicy'
    for rule in ['adbd adb_keys_file:file read','adbd adb_keys_file:file open','adbd adb_keys_file:dir search','init system_radio_prop:property_service set','init configfs:file write']:
        run([host+'/sepolicy-analyze',policy,'neverallow','-n','neverallow '+rule+';'],(255,))
    assert 'on post-fs-data\n' in RC.read_text() and 'setprop ro.adb.secure' not in RC.read_text() and 'setprop ro.debuggable' not in RC.read_text()
    stage('prepare private filesystem copies')
    system=WORK/'system.diag.raw';data=WORK/'userdata.diag.raw'
    for src,dest in [(BASE/'system.raw',system),(BASE/'userdata.clean.raw',data)]:
        assert src.is_file() and not src.is_symlink();run(['/bin/cp','--reflink=auto','--sparse=always',src,dest])
    assert system.stat().st_size==SYS_LEN and data.stat().st_size==DATA_LEN
    assert 'File not found' in run(['/usr/sbin/debugfs','-R','stat /system/etc/init/roc-usb-bootdiag1.rc',system]).stderr
    debug(system,f'write {RC} /system/etc/init/roc-usb-bootdiag1.rc',True)
    attrs(system,'/system/etc/init/roc-usb-bootdiag1.rc','0100644',0,0,'u:object_r:system_file:s0')
    check_attrs(system,'/system/etc/init/roc-usb-bootdiag1.rc','0644',0,0,'u:object_r:system_file:s0')
    assert sha(dumped(system,'/system/etc/init/roc-usb-bootdiag1.rc','diag-rc.readback'))==sha(RC)
    # These are the stock directory identities from init.rc, with only a public
    # ADB key accepted by this workstation. No private key or passwords copied.
    debug(data,'mkdir /misc',True);attrs(data,'/misc','041771',1000,9998,'u:object_r:system_data_file:s0')
    debug(data,'mkdir /misc/adb',True);attrs(data,'/misc/adb','042750',1000,2000,'u:object_r:adb_keys_file:s0')
    debug(data,f'write {KEY} /misc/adb/adb_keys',True);attrs(data,'/misc/adb/adb_keys','0100640',1000,2000,'u:object_r:adb_keys_file:s0')
    check_attrs(data,'/misc/adb/adb_keys','0640',1000,2000,'u:object_r:adb_keys_file:s0')
    assert sha(dumped(data,'/misc/adb/adb_keys','public-key.readback'))==sha(KEY)
    check_attrs(data,'/','0771',1000,1000,'u:object_r:system_data_root_file:s0')
    for node in ['/system/bin/init','/system/bin/adbd','/system/bin/bootstrap/linker64','/system/build.prop','/default.prop','/system/etc/selinux/plat_sepolicy.cil','/system/etc/init/h700-usb-configfs.rc']:
        name=node.strip('/').replace('/','_')
        a=dumped(BASE/'system.raw',node,'old-'+name);b=dumped(system,node,'new-'+name);assert sha(a)==sha(b),node
    for p in [system,data]:run(['/usr/sbin/e2fsck','-f','-n',p])
    fsck=BASE/'loose-boot-tools/e2fsck_static';assert fsck.is_file()
    run(['/usr/bin/qemu-aarch64',fsck,'-f','-n',data])
    result['system_sha256']=sha(system);result['userdata_sha256']=sha(data)
    stage('stream diagnostic image; only system and seeded-public-key userdata change')
    oldhash=hashlib.sha256();newhash=hashlib.sha256();position=0
    with gzip.open(PARENT,'rb') as source,TARGET.open('xb') as physical,system.open('rb') as sy,data.open('rb') as da:
        with gzip.GzipFile(filename='',fileobj=physical,mode='wb',compresslevel=6,mtime=0) as dest:
            while True:
                b=source.read(4*1024**2)
                if not b:break
                oldhash.update(b)
                for start,length,replacement in [(SYS_START,SYS_LEN,sy),(DATA_START,DATA_LEN,da)]:
                    left=max(0,min(len(b),start-position));right=max(0,min(len(b),start+length-position))
                    if right>left:
                        replacement.seek(position+left-start);chunk=replacement.read(right-left);assert len(chunk)==right-left
                        temp=bytearray(b);temp[left:right]=chunk;b=bytes(temp)
                dest.write(b);newhash.update(b);position+=len(b)
                if position%(4*1024**3)==0:stage('stream diagnostic image',bytes=position,total=TOTAL)
    assert position==TOTAL and oldhash.hexdigest()=='f335a2db7c12d8e8cd3438b554c5ec1c3c3ff393bfcf023a1e7f6e1ed15c6f61'
    result.update(raw_sha256=newhash.hexdigest(),sha256=sha(TARGET),bytes=TARGET.stat().st_size,raw_bytes=TOTAL)
    stage('independent complete decompression and replacement-region comparison')
    newhash=hashlib.sha256();position=0
    with gzip.open(PARENT,'rb') as old,gzip.open(TARGET,'rb') as new,system.open('rb') as sy,data.open('rb') as da:
        while True:
            a=old.read(1024**2);b=new.read(1024**2);assert len(a)==len(b)
            if not a:break
            expected=bytearray(a)
            for start,length,part in [(SYS_START,SYS_LEN,sy),(DATA_START,DATA_LEN,da)]:
                left=max(0,min(len(a),start-position));right=max(0,min(len(a),start+length-position))
                if right>left:
                    part.seek(position+left-start);chunk=part.read(right-left);assert len(chunk)==right-left
                    expected[left:right]=chunk
            assert b==expected
            newhash.update(b);position+=len(b)
    assert position==TOTAL and newhash.hexdigest()==result['raw_sha256']
    result.update(passed=True,full_gzip_verified=True,boot_vendor_all_other_ranges_identical_to_Bootfix1=True)
    (OUT/(TARGET.name+'.sha256')).write_text(result['sha256']+'  '+TARGET.name+'\n')
    (OUT/'README.txt').write_text('PRIVATE DIAGNOSTIC IMAGE, NOT RELEASE.\nUSB ADB authentication uses only this workstation public key.\nUser/root refusal/enforcing retained; no network ADB.\nBootfix1 boot and original vendor retained.\nFlash spare TF1 only; connect USB even if logo remains.\n')
    stage('complete',sha256=result['sha256'])
finally:
    (OUT/'image-result.json').write_text(json.dumps(result,indent=2)+'\n')
