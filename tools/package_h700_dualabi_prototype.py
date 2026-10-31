#!/usr/bin/env python3
"""Build a separate GSI10/H700 feasibility image. Regular files only, no device I/O."""
from pathlib import Path, PurePosixPath
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET

import package_h700_v6a as base
from android_sparse_to_raw import convert
from dualabi_image_layout import prototype_gpt, relocate_gpt, IMAGE_BYTES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/dualabi-prototype-image-20261031'
WORK = Path('/home/lpf/h700-dualabi-image-20261031')
PRODUCT = Path('/home/lpf/h700-dualabi-prototype-20261030/out/target/product/rgsp64proto')
BSP = Path('/home/lpf/h700-release-v6b-20261030/system.candidate.raw')
GSI_SHA = '0bbbf53e1164b032eace999cbd6bf0877ab636819a2e929f63079ccfe71095c7'
MARKER = 'rg34xxsp-dualabi-gsi10-p1-20261031'
RELEASE = 'H700_RG34XXSP_2GB_DualABI_P1_GSI10_20261031_NoROM'

def needed(file):
    return re.findall(r'Shared library: \[(.*?)\]', subprocess.check_output(['readelf','-d',str(file)],text=True))

def native_file(file):
    seen=set()
    while file.is_symlink():
        if file in seen: raise ValueError('Native symlink cycle')
        seen.add(file); target=os.readlink(file)
        file = PRODUCT/'system'/target.lstrip('/') if target.startswith('/apex/') else PRODUCT/target.lstrip('/') if target.startswith('/') else file.parent/target
    base.regular(file)
    if not file.resolve().is_relative_to(PRODUCT.resolve()): raise ValueError('Native input escaped product')
    if file.read_bytes()[:5] != b'\x7fELF\x02': raise ValueError('Require ELF64 native input')
    return file

def find_native(name):
    if '/' in name or '..' in name: raise ValueError('Invalid ELF dependency')
    for directory in ['system/lib64/bootstrap','system/lib64','system/lib64/vndk-sp-29','system/lib64/vndk-29','vendor/lib64']:
        try: return native_file(PRODUCT/directory/name)
        except (OSError,ValueError): pass
    raise ValueError('Missing real native runtime: '+name)

def extract_tree(image, inside, directory):
    directory.mkdir()
    subprocess.run(['debugfs','-R','rdump '+base.q(inside)+' '+base.q(directory),str(image)],check=True,capture_output=True)
    nested=directory/PurePosixPath(inside).name
    return nested if nested.is_dir() else directory

def image_stat(image, inside):
    return base.debug(image,'stat '+base.q(inside))

def modify(image, mapping, label_default, links=None):
    """Write and read back every owned overlay, including labels and Unix mode."""
    commands=[]; directories=set()
    for inside in list(mapping)+(list(links) if links else []):
        p=PurePosixPath(inside).parent
        while str(p)!='/': directories.add(str(p));p=p.parent
    for directory in sorted(directories,key=lambda p:(p.count('/'),p)):
        commands.append('mkdir '+base.q(directory))
    expected={}
    for i,(inside,(source,mode,label)) in enumerate(sorted(mapping.items())):
        base.regular(source)
        context=base.write(WORK/('label-'+str(i)+'.txt'),label+'\x00')
        commands += ['rm '+base.q(inside),'write '+base.q(source)+' '+base.q(inside),
                     'set_inode_field '+base.q(inside)+' mode '+mode,
                     'set_inode_field '+base.q(inside)+' uid 0','set_inode_field '+base.q(inside)+' gid 0',
                     'ea_set -f '+base.q(context)+' '+base.q(inside)+' security.selinux']
        expected[inside]={'sha256':base.sha(source),'mode':mode,'selinux':label}
    for inside,target in (links or {}).items():
        commands += ['rm '+base.q(inside),'symlink '+base.q(inside)+' '+base.q(target)]
    script=base.write(WORK/(image.stem+'.debugfs.commands'),'\n'.join(commands)+'\n')
    with (WORK/(image.stem+'.debugfs.log')).open('w') as log:
        subprocess.run(['debugfs','-w','-f',str(script),str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)
    for i,(inside,record) in enumerate(expected.items()):
        sample=base.dump(image,inside,WORK/'readback.tmp')
        if base.sha(sample)!=record['sha256']:raise ValueError('Overlay readback: '+inside)
        attr=WORK/'readback.context'
        if attr.exists():attr.unlink()
        base.debug(image,'ea_get -f '+base.q(attr)+' '+base.q(inside)+' security.selinux')
        if attr.read_bytes()!=record['selinux'].encode()+b'\x00':raise ValueError('Overlay label: '+inside)
        expected_mode = int(record['mode'], 8) & 0o7777
        info = image_stat(image, inside)
        if not re.search(r'Mode:\s+0*'+format(expected_mode,'o')+r'\b',info):raise ValueError('Overlay mode: '+inside)
        if not re.search(r'User:\s+0\s+Group:\s+0\b',info):raise ValueError('Overlay owner: '+inside)
    for inside,target in (links or {}).items():
        if 'Fast link dest: "'+target+'"' not in image_stat(image,inside):raise ValueError('Link readback: '+inside)
    with (WORK/(image.stem+'.fsck.log')).open('w') as log:
        subprocess.run(['e2fsck','-f','-n',str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)
    return expected

def main():
    base.constrained()
    passed=json.loads((ROOT/'out/dualabi-prototype-20261030/window.pass.json').read_text())
    if not all(passed.get(k) for k in ['swap','composed_green_window','layer_removed','baseline_unchanged']):raise ValueError('Window gate not passed')
    if passed['bundle_lock_sha256']!=base.sha(ROOT/'out/dualabi-prototype-20261030/window-bundle/bundle-lock.json'):raise ValueError('Window input changed')
    if WORK.exists():raise ValueError('Preserve existing prototype stage before a new attempt')
    WORK.mkdir();OUT.mkdir(exist_ok=True)
    parent=json.loads((ROOT/'docs/baselines/rg34xxsp-v6b-mt-20261030/image-lock.json').read_text())
    inputs={}
    for entry in parent['ranges']:
        path=BSP if entry['name']=='system' else base.WORK/(entry['name']+('.candidate.raw' if entry['name']=='vendor' else '.raw'))
        base.regular(path)
        print('VERIFY_PARENT',entry['name'],flush=True)
        if path.stat().st_size!=entry['bytes'] or base.sha(path)!=entry['sha256']:raise ValueError('Parent input changed')
        inputs[entry['name']]=path
    archive=ROOT/'out/arm64-isolated-20261030/aosp_arm64-exp-QJR1.191112.001-6004257.zip'
    if base.sha(archive)!=GSI_SHA:raise ValueError('GSI archive mismatch')
    sparse=Path('/home/lpf/h700-arm64-isolated-20261030/gsi-system.img')
    with zipfile.ZipFile(archive) as z:
        member=next(n for n in z.namelist() if n.endswith('system.img'))
        with z.open(member) as src:
            if hashlib.file_digest(src,'sha256').hexdigest()!=base.sha(sparse):raise ValueError('Extracted GSI changed')
    system=WORK/'system.candidate.raw';vendor=WORK/'vendor.candidate.raw'
    with sparse.open('rb') as f:
        magic=f.read(4);f.seek(1080);ext4=f.read(2)
    if magic==b'\x3a\xff\x26\xed':convert(str(sparse),str(system))
    elif ext4==b'\x53\xef':subprocess.run(['cp','--sparse=always',str(sparse),str(system)],check=True)
    else:raise ValueError('GSI is neither Android sparse nor raw ext4')
    with system.open('r+b') as f:f.truncate(8589934592)
    subprocess.run(['resize2fs',str(system)],check=True)
    for name in ['prefix','vendor','factory_tail']:
        dest=WORK/(name+'.candidate.raw')
        subprocess.run(['cp','--sparse=always',str(inputs[name]),str(dest)],check=True)
    prefix=WORK/'prefix.candidate.raw';tail=WORK/'factory_tail.candidate.raw'
    with prefix.open('r+b') as f:
        old=f.read(2048);head,backup,layout=prototype_gpt(old);f.seek(0);f.write(head)
    with tail.open('r+b') as f:f.seek(-1536,2);f.write(backup)
    # Independently validate Python's compact GPT with the existing C checker.
    fixture=WORK/'gpt-metadata-only.raw'
    with fixture.open('xb') as f:f.write(head);f.seek(IMAGE_BYTES-1536);f.write(backup)
    hostcheck=WORK/'grow-gpt-host'
    subprocess.run(['gcc','-O2','-Wall','-Wextra','-Werror',str(ROOT/'tools/rgsp_grow_gpt.c'),'-o',str(hostcheck)],check=True)
    subprocess.run([str(hostcheck),'--check',str(fixture),'--image-test'],check=True)
    # The checker intentionally recovers one damaged primary from its backup.
    # Both damaged headers must be rejected. No block-device tests on the host.
    with fixture.open('r+b') as f:f.seek(528);f.write(b'\x00\x00\x00\x00')
    recovered=subprocess.run([str(hostcheck),'--check',str(fixture),'--image-test'],capture_output=True)
    if recovered.returncode!=0:raise ValueError('Backup recovery positive test failed')
    with fixture.open('r+b') as f:f.seek(IMAGE_BYTES-512+16);f.write(b'\x00\x00\x00\x00')
    if subprocess.run([str(hostcheck),'--check',str(fixture),'--image-test'],capture_output=True).returncode==0:raise ValueError('CRC negative test failed')
    with fixture.open('r+b') as f:f.write(head);f.seek(IMAGE_BYTES-1536);f.write(backup)
    physical_bytes=125069950976
    physical_head,physical_backup=relocate_gpt(head,physical_bytes)
    physical_fixture=WORK/'gpt-relocated-metadata-only.raw'
    with physical_fixture.open('xb') as f:f.write(physical_head);f.seek(physical_bytes-1536);f.write(physical_backup)
    subprocess.run([str(hostcheck),'--check',str(physical_fixture),'--image-test'],check=True)
    maps={};vmaps={}
    def add(inside,source,mode='0100644',label='u:object_r:system_file:s0'):
        maps[inside]=(Path(source),mode,label)
    # Dedicated init/adbd dependency pool; ordinary GSI ART/framework stays intact.
    queue=[]
    for name,label in [('init','init_exec'),('adbd','adbd_exec')]:
        file=native_file(PRODUCT/'system/bin'/name)
        add('/system/bin/h700-bootstrap/'+name,file,'0100755','u:object_r:'+label+':s0');queue+=needed(file)
    linker=native_file(PRODUCT/'system/bin/bootstrap/linker64')
    add('/system/bin/bootstrap/linker64',linker,'0100755','u:object_r:system_linker_exec:s0')
    done=set()
    while queue:
        name=queue.pop(0)
        if name in done or name=='ld-android.so':continue
        done.add(name);file=find_native(name);queue+=needed(file)
        add('/system/lib64/bootstrap/'+name,file,label='u:object_r:system_lib_file:s0')
    section='\n[h700bootstrap]\nnamespace.default.isolated = false\nnamespace.default.search.paths = /system/${LIB}/bootstrap\n'
    config_listing=base.debug(system,'ls -p /system/etc')
    config_names=[line.split('/')[5] for line in config_listing.splitlines() if '/ld.config.' in line]
    for name in config_names:
        file=base.dump(system,'/system/etc/'+name,WORK/name)
        text=file.read_text();text='dir.h700bootstrap = /system/bin/h700-bootstrap/\n'+text+section
        base.write(file,text);add('/system/etc/'+name,file)
    fallback=base.write(WORK/'ld.config.fallback.txt','dir.h700bootstrap = /system/bin/h700-bootstrap/\n'+section)
    add('/system/etc/ld.config.txt',fallback)
    usb=base.dump(system,'/init.usb.rc',WORK/'init.usb.rc')
    text=usb.read_text()
    if text.count('service adbd /system/bin/adbd')!=1:raise ValueError('Unexpected GSI adbd declaration')
    base.write(usb,text.replace('service adbd /system/bin/adbd','service adbd /system/bin/bootstrap/linker64 /system/bin/h700-bootstrap/adbd'))
    add('/init.usb.rc',usb,'0100750','u:object_r:rootfs:s0')
    # The retained vendor policy needs its matching platform CIL/mapping and su.
    policy=extract_tree(BSP,'/system/etc/selinux',WORK/'bsp-policy')
    for file in sorted(policy.rglob('*')):
        if file.is_file() and file.name!='plat_mac_permissions.xml':add('/system/etc/selinux/'+file.relative_to(policy).as_posix(),file)
    # Keep the GSI signer-to-seinfo mapping for its unmodified platform APKs.
    for inside in ['/file_contexts.bin','/system/etc/cgroups.json','/system/etc/task_profiles.json']:
        file=base.dump(BSP,inside,WORK/('bsp-'+Path(inside).name));add(inside,file)
    for inside in ['/system/etc/init/rgsp_fix63_graphics.rc','/system/etc/init/rgsp-single-console.rc',
                   '/system/etc/rgsp-graphics-diag.sh','/system/lib/modules/mali_kbase.ko']:
        file=base.dump(BSP,inside,WORK/Path(inside).name);add(inside,file,'0100755' if inside.endswith('.sh') else '0100644')
    for name in ['h700-usb-configfs.rc','h700-network-validation-defaults.rc','h700-media-compat.rc']:
        add('/system/etc/init/'+name,base.PRODUCT/name)
    add('/system/bin/h700-network-validation-defaults.sh',base.PRODUCT/'h700-network-validation-defaults.sh','0100755')
    # Only test software is staged; no ROM/BIOS/accounts/saves or device data.
    selection=json.loads((ROOT/'config/pegasus/preinstall-apks-v6b.json').read_text())
    tests=[('H700AbiProbe64','com.roc.h700.abiprobe','arm64-v8a',PRODUCT/'system/app/H700AbiProbe64/H700AbiProbe64.apk')]
    for identifier,abi in [('MTManager','arm64-v8a'),('RetroArch','armeabi-v7a'),('PPSSPP','armeabi-v7a')]:
        app=next(a for a in selection if a['id']==identifier);file=ROOT/app['file']
        if base.sha(file)!=app['sha256']:raise ValueError('Selected APK changed')
        tests.append((identifier,app['package'],abi,file))
    for identifier,package,abi,file in tests:
        add('/system/etc/h700-prototype/apks/'+identifier+'.apk',file)
    for key in ['system:/system/priv-app/AT4K/AT4K.apk','system:/system/app/RGSPNavigation/RGSPNavigation.apk']:
        source,digest=base.PIN[key]
        if base.sha(ROOT/source)!=digest:raise ValueError('Launcher/navigation changed')
        add(key.split(':',1)[1],ROOT/source)
    for name in ['Vendor_0001_Product_0001_Version_0100.kl','Vendor_0001_Product_0001.kl','ANBERNIC-keys.kl']:
        add('/system/usr/keylayout/'+name,base.PRODUCT/'ANBERNIC-keys.kl')
    add('/system/media/wallpapers/IMG_3111.jpg',base.PRODUCT/'wallpapers/IMG_3111.jpg')
    prop=base.dump(system,'/system/etc/prop.default',WORK/'prop.default')
    overrides={'ro.product.device':'rgsp','ro.h700.prototype':MARKER,'ro.zygote':'zygote64_32',
               'ro.config.low_ram':'true','ro.config.wallpaper':'/system/media/wallpapers/IMG_3111.jpg',
               'ro.debuggable':'1','ro.secure':'0','ro.adb.secure':'0','persist.sys.usb.config':'adb',
               'persist.vendor.rgsp.input_profile':'rg34xxsp','ro.hardware.gralloc':'h700proto',
               'ro.product.locale':'zh-CN','persist.sys.timezone':'Asia/Shanghai','ro.sf.lcd_density':'213',
               'dalvik.vm.dex2oat-threads':'1','dalvik.vm.boot-dex2oat-threads':'1','pm.dexopt.install':'verify'}
    text=prop.read_text()
    for name,value in overrides.items():
        text=re.sub(r'^'+re.escape(name)+r'=.*\n','',text,flags=re.M)
    base.write(prop,text+'\n'+''.join(k+'='+v+'\n' for k,v in overrides.items()));add('/system/etc/prop.default',prop)
    setup=ROOT/'tools/arm64_probe/prototype_setup.sh';rc=ROOT/'tools/arm64_probe/prototype_setup.rc'
    subprocess.run(['bash','-n',str(setup)],check=True)
    add('/system/bin/h700-prototype-setup.sh',setup,'0100755','u:object_r:shell_exec:s0')
    add('/system/etc/init/h700-prototype-setup.rc',rc)
    app_list=base.write(WORK/'prototype-apps.list',''.join(pkg+' '+identifier+'.apk '+abi+' '+base.sha(file)+'\n' for identifier,pkg,abi,file in tests))
    add('/system/etc/h700-prototype/apps.list',app_list)
    fst=base.dump(vendor,'/etc/fstab.sun50iw9p1',WORK/'fstab.sun50iw9p1')
    text=fst.read_text()
    for name in ['system','vendor','data']:
        old=layout['partitions'][name]['old_partuuid'];new=layout['partitions'][name]['partuuid']
        if text.count(old)!=1:raise ValueError('Unexpected PARTUUID in fstab: '+name)
        text=text.replace(old,new)
    # Keep only emulated internal storage during the feasibility test. Stock GSI
    # vold must not enumerate/offer to format the boot card's hardware partitions.
    text='\n'.join(l for l in text.splitlines() if 'voldmanaged=' not in l)+'\n';base.write(fst,text)
    vmaps['/etc/fstab.sun50iw9p1']=(fst,'0100644','u:object_r:vendor_configs_file:s0')
    manifest=base.dump(vendor,'/etc/vintf/manifest.xml',WORK/'manifest.xml')
    text=manifest.read_text()
    tree=ET.fromstring(text);found=0
    for hal in tree.findall('hal'):
        if hal.findtext('name')=='android.hardware.graphics.mapper':
            transport=hal.find('transport')
            if transport is None or transport.get('arch') not in ('32','32+64'):raise ValueError('Unexpected mapper transport')
            if transport.get('arch')=='32':
                pattern=r'(<name>android\.hardware\.graphics\.mapper</name>\s*<transport arch=")32("\s*>passthrough</transport>)'
                text,n=re.subn(pattern,r'\g<1>32+64\2',text)
                if n!=1:raise ValueError('Mapper transport patch not unique')
            found+=1
    if found!=1:raise ValueError('Mapper VINTF declaration not unique')
    base.write(manifest,text);vmaps['/etc/vintf/manifest.xml']=(manifest,'0100644','u:object_r:vendor_configs_file:s0')
    for bits,lib in [(32,'lib'),(64,'lib64')]:
        for name in ['gralloc.h700proto.so','android.hardware.graphics.mapper@2.0-impl-2.1.so']:
            file=base.regular(PRODUCT/('vendor/'+lib+'/hw/'+name))
            vmaps['/'+lib+'/hw/'+name]=(file,'0100644','u:object_r:same_process_hal_file:s0')
    mali=Path('/home/lpf/h700-android10/android/hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so')
    if base.sha(mali)!='03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8':raise ValueError('Mali64 changed')
    vmaps['/lib64/egl/libGLES_mali.so']=(mali,'0100644','u:object_r:same_process_hal_file:s0')
    print('WRITE_AND_VERIFY_SYSTEM_OVERLAY',len(maps),flush=True)
    records={'system':modify(system,maps,'system_file',{'/system/bin/init':'/system/bin/h700-bootstrap/init'}),
             'vendor':modify(vendor,vmaps,'vendor_file')}
    ranges=[]
    for name,path in [('prefix',prefix),('system',system),('vendor',vendor),('factory_tail',tail)]:
        ranges.append({'name':name,'offset':sum(x['bytes'] for x in ranges),'bytes':path.stat().st_size,'sha256':base.sha(path),'path':str(path)})
    if sum(x['bytes'] for x in ranges)!=IMAGE_BYTES:raise ValueError('Prototype range mismatch')
    base.jsonwrite(WORK/'partitions-verified.json',{'ranges':ranges,'overlay':records,'layout':layout,'marker':MARKER})
    target=OUT/(RELEASE+'.img.gz');digest=hashlib.sha256()
    if target.exists():raise ValueError('Do not overwrite prototype output')
    with target.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0,filename='') as gz:
        for entry in ranges:
            print('COMPRESS',entry['name'],flush=True)
            with Path(entry['path']).open('rb') as src:
                while block:=src.read(8*1024**2):digest.update(block);gz.write(block)
    verify=hashlib.sha256();count=0
    with gzip.open(target,'rb') as f:
        while block:=f.read(8*1024**2):count+=len(block);verify.update(block)
    if count!=IMAGE_BYTES or verify.hexdigest()!=digest.hexdigest():raise ValueError('Full decompression mismatch')
    result={'release':RELEASE,'bytes':count,'sha256':digest.hexdigest(),'gzip_sha256':base.sha(target),'gzip_bytes':target.stat().st_size,
            'ranges':[{k:v for k,v in e.items() if k!='path'} for e in ranges],'layout':layout,'marker':MARKER,
            'gsi_sha256':GSI_SHA,'full_gzip_decompression_verified':True,'card_written':False,'first_boot_verified':False,
            'test_apps':[{'package':p,'abi':a,'sha256':base.sha(f)} for _,p,a,f in tests]}
    base.jsonwrite(OUT/'image-lock.json',result);base.jsonwrite(OUT/'overlay-lock.json',records)
    print('DUAL_ABI_PROTOTYPE_IMAGE_VERIFIED',target.name,flush=True)

if __name__=='__main__':main()
