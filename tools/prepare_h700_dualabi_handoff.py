#!/usr/bin/env python3
"""Repair P1a for the actual retained pre-switch_root ramdisk contract."""
from pathlib import Path
import gzip,hashlib,json,os,re,shutil,struct,subprocess
import package_h700_v6a as base
from h700_image_delta import block_delta
from dualabi_image_layout import STARTS,LENGTHS

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('/home/lpf/h700-dualabi-image-20261031')
SYSTEM_PARENT=Path('/home/lpf/h700-dualabi-entry-p1a-20261031/system.candidate.raw')
WORK=Path('/home/lpf/h700-dualabi-handoff-p1b-20261031')
OUT=ROOT/'out/dualabi-bootchain-p1b-20261031'
REVISION='p1b-ramdisk-handoff-20261031'

def ramdisk_init(prefix):
    with prefix.open('rb') as f:
        f.seek(STARTS[3]);h=f.read(2048)
        if h[:8]!=b'ANDROID!':raise ValueError('Unknown pinned boot format')
        kernel=struct.unpack_from('<I',h,8)[0];size=struct.unpack_from('<I',h,16)[0];page=struct.unpack_from('<I',h,36)[0]
        start=STARTS[3]+page+((kernel+page-1)//page)*page
        if page!=2048 or size>16*1024**2 or start+size>STARTS[3]+LENGTHS[3]:raise ValueError('Unexpected ramdisk bounds')
        f.seek(start);data=gzip.decompress(f.read(size))
    at=0;found=[]
    while at<len(data):
        h=data[at:at+110]
        if h[:6] not in [b'070701',b'070702']:raise ValueError('Unknown cpio')
        fields=[int(h[6+i*8:14+i*8],16) for i in range(13)]
        size,n=fields[6],fields[11];name=data[at+110:at+110+n-1].decode()
        offset=(at+110+n+3)&~3;body=data[offset:offset+size]
        if name=='init':found.append(body)
        if name=='TRAILER!!!':break
        at=(offset+size+3)&~3
    if len(found)!=1:raise ValueError('Ramdisk init not unique')
    return found[0]

def edit(image,commands,name):
    script=base.write(WORK/(name+'.commands'),'\n'.join(commands)+'\n')
    with (WORK/(name+'.debugfs.log')).open('w') as log:
        subprocess.run(['debugfs','-w','-f',str(script),str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)
    with (WORK/(name+'.fsck.log')).open('w') as log:
        subprocess.run(['e2fsck','-f','-n',str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)

def main():
    base.constrained()
    p1=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/image-lock.json').read_text())
    p1a=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-entry-p1a-20261031/entry-lock.json').read_text())
    parent_ranges={r['name']:r for r in p1['ranges']}
    for path,expected in [(PARENT/'prefix.candidate.raw',parent_ranges['prefix']['sha256']),
                          (PARENT/'vendor.candidate.raw',parent_ranges['vendor']['sha256']),
                          (SYSTEM_PARENT,p1a['system_sha256'])]:
        base.regular(path)
        if base.sha(path)!=expected:raise ValueError('Pinned parent changed')
    if WORK.exists():raise ValueError('Retain previous handoff stage before another attempt')
    WORK.mkdir();OUT.mkdir(exist_ok=True)
    init=ramdisk_init(PARENT/'prefix.candidate.raw')
    if b'[ -x /android-root/system/bin/init ]' not in init or b'switch_root /android-root /init selinux_setup' not in init:raise ValueError('Ramdisk handoff contract changed')
    if b'mount -o bind /proc /android-root/proc' not in init:raise ValueError('Unexpected proc handoff')
    old_system=SYSTEM_PARENT;old_vendor=PARENT/'vendor.candidate.raw'
    system=WORK/'system.candidate.raw';vendor=WORK/'vendor.candidate.raw'
    for a,b in [(old_system,system),(old_vendor,vendor)]:subprocess.run(['cp','--sparse=always',str(a),str(b)],check=True)
    prior=base.debug(old_system,'stat /system/bin/init')
    target=re.search(r'Fast link dest: "(.*?)"',prior).group(1)
    if target!='/system/bin/h700-bootstrap/init':raise ValueError('Expected P1a absolute link')
    fixture=WORK/'handoff-fixture/system/bin';(fixture/'h700-bootstrap').mkdir(parents=True)
    real=base.dump(old_system,'/system/bin/h700-bootstrap/init',fixture/'h700-bootstrap/init');real.chmod(0o755)
    if real.read_bytes()[:5]!=b'\x7fELF\x02':raise ValueError('Private init changed ABI')
    os.symlink(target,fixture/'init')
    if os.access(fixture/'init',os.X_OK):raise ValueError('Negative ramdisk-context regression did not fail')
    (fixture/'init').unlink();os.symlink('h700-bootstrap/init',fixture/'init')
    if not os.access(fixture/'init',os.X_OK):raise ValueError('Relative handoff regression failed')
    context=base.write(WORK/'init.context','u:object_r:init_exec:s0\x00')
    normal=base.write(WORK/'system.context','u:object_r:system_file:s0\x00')
    revision=base.write(WORK/'revision',REVISION+'\n')
    edit(system,['rm /system/bin/init','symlink /system/bin/init h700-bootstrap/init',
        'set_inode_field /system/bin/init mode 0120777','set_inode_field /system/bin/init uid 0','set_inode_field /system/bin/init gid 0',
        'ea_set -f '+base.q(context)+' /system/bin/init security.selinux',
        'rm /system/etc/h700-prototype/boot-entry-revision',
        'write '+base.q(revision)+' /system/etc/h700-prototype/boot-entry-revision',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision mode 0100644',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision uid 0',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision gid 0',
        'ea_set -f '+base.q(normal)+' /system/etc/h700-prototype/boot-entry-revision security.selinux'],'system')
    if 'Fast link dest: "h700-bootstrap/init"' not in base.debug(system,'stat /system/bin/init'):raise ValueError('Relative link readback failed')
    if 'Fast link dest: "/system/bin/h700-bootstrap/init"' not in base.debug(system,'stat /init'):raise ValueError('Root direct link changed')
    fst=base.dump(old_vendor,'/etc/fstab.sun50iw9p1',WORK/'fstab');text=fst.read_text();aliases={}
    for name,n in [('system',5),('vendor',6),('data',7)]:
        ids=p1['layout']['partitions'][name];old=ids['old_partuuid'];new=ids['partuuid']
        if init.count(("'"+old+':mmcblk0p'+str(n)+"'").encode())!=1:raise ValueError('Ramdisk alias does not match pinned legacy identity')
        oldpath='/dev/block/by-partuuid/'+old;newpath='/dev/block/by-partuuid/'+new
        if text.count(newpath)!=1:raise ValueError('Not an ordinary by-partuuid symlink path')
        text=text.replace(newpath,oldpath);aliases[name]={'boot_alias':oldpath,'real_gpt_partuuid':new,'device':'mmcblk0p'+str(n)}
    base.write(fst,text)
    vcontext=base.write(WORK/'vendor.context','u:object_r:vendor_configs_file:s0\x00')
    edit(vendor,['rm /etc/fstab.sun50iw9p1','write '+base.q(fst)+' /etc/fstab.sun50iw9p1',
        'set_inode_field /etc/fstab.sun50iw9p1 mode 0100644','set_inode_field /etc/fstab.sun50iw9p1 uid 0','set_inode_field /etc/fstab.sun50iw9p1 gid 0',
        'ea_set -f '+base.q(vcontext)+' /etc/fstab.sun50iw9p1 security.selinux'],'vendor')
    if base.dump(vendor,'/etc/fstab.sun50iw9p1',WORK/'fstab.readback').read_bytes()!=fst.read_bytes():raise ValueError('Alias readback failed')
    if base.dump(system,'/system/etc/h700-prototype/boot-entry-revision',WORK/'revision.readback').read_bytes()!=revision.read_bytes():raise ValueError('Revision readback failed')
    components={}
    for name,part,old,new in [('system',5,old_system,system),('vendor',6,old_vendor,vendor)]:
        print('P1B_DELTA_AND_COMPONENT',name,flush=True)
        ranges=block_delta(old,new,OUT/(name+'-delta'))
        expected=base.sha(new);gz=OUT/('H700_DualABI_P1b_'+name+'_20261031.img.gz')
        with gz.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0,filename='') as z,new.open('rb') as f:
            while b:=f.read(8*1024**2):z.write(b)
        total=0;digest=hashlib.sha256()
        with gzip.open(gz,'rb') as f:
            while b:=f.read(8*1024**2):digest.update(b);total+=len(b)
        if total!=new.stat().st_size or digest.hexdigest()!=expected:raise ValueError('Component decompression failed')
        components[name]={'partition':part,'bytes':total,'parent_sha256':base.sha(old),'sha256':expected,
                          'ranges':ranges,'gzip_file':gz.name,'gzip_bytes':gz.stat().st_size,'gzip_sha256':base.sha(gz)}
    result={'revision':REVISION,'components':components,'legacy_boot_aliases':aliases,
            'ramdisk_init_sha256':hashlib.sha256(init).hexdigest(),'ramdisk_outside_chroot_negative_and_relative_positive':True,
            'prefix_kernel_boot0_unchanged':True,'real_gpt_guids_unchanged':True,'auto_grow_retained_in_pinned_ramdisk':True,
            'filesystems_and_component_decompression':True,'card_modified':False,'boot_pass':False}
    base.jsonwrite(OUT/'handoff-lock.json',result)
    print('P1B_HANDOFF_COMPONENTS_VERIFIED',sum(sum(r['bytes'] for r in c['ranges']) for c in components.values()),flush=True)

if __name__=='__main__':main()
