"""Derive a new ordinary gzip card image by replacing only RC1's boot region."""
from pathlib import Path
import argparse, datetime, gzip, hashlib, json, stat, struct, subprocess, sys
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
from android_bootimg import read_header,component_offsets,pack
from patch_ramdisk import parse,emit
from package_h700_v6a import constrained
constrained()
OUT=REPO/'out/roc-os-user-card-bootfix1-20261106'
OUT.mkdir(exist_ok=False)
WORK=Path('/home/lpf/roc-os-user-card-bootfix1-20261106-v1')
WORK.mkdir(exist_ok=False)
PARENT=REPO/'out/roc-os-user-card-20261105/ROC_OS_ARM64_User_RC1_20261105.img.gz'
TARGET=OUT/'ROC_OS_ARM64_User_RC1_Bootfix1_20261106.img.gz'
START=155189248;LENGTH=67108864;TOTAL=32434554368
PARENT_GZ='c549d011a1a332e92a1b317601f6128e2b849813ec40bdac988eaa05913e4ee5'
PARENT_RAW='44dfc8e35744f92260c64005e2fc4ca0410c6205bcbd8d92f62bea13fc99c8ed'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stage(name,**extra):
    r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':name,**extra}
    print(json.dumps(r),flush=True);(OUT/'progress.json').write_text(json.dumps(r,indent=2)+'\n')
result={'passed':False,'runtime_or_release_accepted':False,'device_modified':False,'work':str(WORK),'parent':str(PARENT),'image':str(TARGET)}
try:
    stage('verify frozen parent and reviewed bootfix inputs')
    assert sha(PARENT)==PARENT_GZ
    preflight=Path('/home/lpf/roc-os-user-bootfix1-20261106-preflight-v1/result.json')
    pre=json.loads(preflight.read_text());assert pre['passed'] and not pre['runtime_enforcing_accepted']
    for name,digest in pre['inputs'].items():assert sha(REPO/name)==digest,name
    result['preflight_sha256']=sha(preflight)
    result['inputs']=pre['inputs']
    template=Path('/home/lpf/roc-os-user-card-20261105-v9/boot.unified.raw')
    raw=template.read_bytes();assert len(raw)==LENGTH
    # The actual failed card's boot independently matched this parent.
    assert sha(template)=='477776fd1748fb2cfa6631d82594f4797f1ca9dfc2a92000ef3c420444f196ac'
    old_header,h=read_header(template);offsets=component_offsets(h)
    assert h['cmdline']=='selinux=1 enforcing=1 androidboot.selinux=enforcing'
    oldrd=raw[offsets['ramdisk']:offsets['ramdisk']+h['ramdisk_size']]
    entries=parse(gzip.decompress(oldrd));old={e['name']:dict(e) for e in entries}
    assert old['init']['data']==(REPO/'tools/release/user_boot_init.sh').read_bytes()
    replacements={'init':REPO/'tools/release/user_boot_init_bootfix1.sh','grow/prepare-android-dev-bootfix1.sh':REPO/'tools/release/prepare_android_dev_bootfix1.sh'}
    assert 'grow/prepare-android-dev-bootfix1.sh' not in old
    for name,source in replacements.items():
        body=source.read_bytes();assert b'\r' not in body
        e=next((e for e in entries if e['name']==name),None)
        if e is None:
            e=dict(old['init']);e['name']=name;e['ino']=max(x['ino'] for x in entries)+1
            entries.insert(-1,e)
        e.update(data=body,mode=stat.S_IFREG|0o755,uid=0,gid=0,nlink=1)
    re={e['name']:e for e in entries}
    assert set(re)==set(old)|{'grow/prepare-android-dev-bootfix1.sh'}
    for name,e in old.items():
        if name!='init':assert re[name]==e,name
    ramdisk=WORK/'ramdisk.gz';ramdisk.write_bytes(gzip.compress(b''.join(emit(e) for e in entries),compresslevel=6,mtime=0))
    parentrd=WORK/'parent.ramdisk.gz';parentrd.write_bytes(oldrd)
    identity=WORK/'identity.boot.raw'
    pack(argparse.Namespace(template=str(template),out=str(identity),kernel=None,ramdisk=str(parentrd),second=None,dtb=None))
    assert identity.read_bytes()==raw
    newboot=WORK/'boot.bootfix1.raw'
    pack(argparse.Namespace(template=str(template),out=str(newboot),kernel=None,ramdisk=str(ramdisk),second=None,dtb=None))
    newraw=newboot.read_bytes();assert len(newraw)==LENGTH
    nh,info=read_header(newboot);no=component_offsets(info)
    allowed=bytearray(old_header);struct.pack_into('<I',allowed,16,ramdisk.stat().st_size)
    assert nh==allowed
    for component in ['kernel','second','dtb']:
        size=h.get('dt_size_detected',h['dt_size']) if component=='dtb' else h[component+'_size']
        assert raw[offsets[component]:offsets[component]+size]==newraw[no[component]:no[component]+size]
    result.update(boot_sha256=sha(newboot),parent_boot_sha256=sha(template),kernel_dtb_preserved=True,system_vendor_userdata_preserved=True,cmdline=info['cmdline'])
    stage('stream parent with boot replacement')
    parenthash=hashlib.sha256();newhash=hashlib.sha256();position=0
    with gzip.open(PARENT,'rb') as src,TARGET.open('xb') as physical:
        with gzip.GzipFile(filename='',fileobj=physical,mode='wb',compresslevel=6,mtime=0) as dst:
            while True:
                b=src.read(4*1024**2)
                if not b:break
                parenthash.update(b)
                if position<START+LENGTH and position+len(b)>START:
                    left=max(0,START-position);right=min(len(b),START+LENGTH-position)
                    a=bytearray(b);a[left:right]=newraw[position+left-START:position+right-START];b=bytes(a)
                dst.write(b);newhash.update(b);position+=len(b)
                if position%(4*1024**3)==0:stage('stream parent with boot replacement',bytes=position,total=TOTAL)
    assert position==TOTAL and parenthash.hexdigest()==PARENT_RAW
    result.update(bytes=TARGET.stat().st_size,sha256=sha(TARGET),raw_bytes=position,raw_sha256=newhash.hexdigest(),parent_gzip_sha256=PARENT_GZ,parent_raw_sha256=PARENT_RAW)
    stage('independent decompression and all non-boot byte comparison')
    childhash=hashlib.sha256();position=0
    # Compare the complete expanded images, with independent read boundaries.
    with gzip.open(PARENT,'rb') as a,gzip.open(TARGET,'rb') as b:
        while True:
            oldchunk=a.read(1024**2);newchunk=b.read(1024**2)
            assert len(oldchunk)==len(newchunk)
            if not oldchunk:break
            childhash.update(newchunk)
            left=max(0,min(len(newchunk),START-position));right=max(0,min(len(newchunk),START+LENGTH-position))
            if right>left:
                assert oldchunk[:left]==newchunk[:left] and oldchunk[right:]==newchunk[right:]
                assert newchunk[left:right]==newraw[position+left-START:position+right-START]
            else:assert oldchunk==newchunk
            position+=len(oldchunk)
    assert position==TOTAL and childhash.hexdigest()==result['raw_sha256']
    result.update(passed=True,full_gzip_verified=True,every_non_boot_byte_identical_to_RC1=True)
    (OUT/(TARGET.name+'.sha256')).write_text(result['sha256']+'  '+TARGET.name+'\n')
    (OUT/'README.txt').write_text('ROC OS ARM64 User RC1 Bootfix1 test candidate.\nOnly boot handoff differs from original RC1.\nRaw image bytes: '+str(TOTAL)+'\nMinimum 64GB spare TF1, TF2 empty.\nActual boot/enforcing acceptance pending. No automatic flash.\n')
    stage('complete',sha256=result['sha256'])
finally:
    (OUT/'image-result.json').write_text(json.dumps(result,indent=2)+'\n')
