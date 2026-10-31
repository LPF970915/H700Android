#!/usr/bin/env python3
"""Offline boot-input audit, regular staged files only; run with capped wrapper."""
from pathlib import Path
import hashlib
import io
import json
import re
import tempfile
import zipfile
import package_h700_v6a as base
from package_h700_dualabi_prototype import WORK, OUT, MARKER
from dualabi_image_layout import prototype_gpt, relocate_gpt

def main():
    base.constrained()
    image=json.loads((OUT/'image-lock.json').read_text())
    if not image['full_gzip_decompression_verified']:raise ValueError('Image gate missing')
    stage=json.loads((WORK/'partitions-verified.json').read_text())
    for entry in stage['ranges']:
        file=Path(entry['path']);base.regular(file)
        if file.stat().st_size!=entry['bytes'] or base.sha(file)!=entry['sha256']:raise ValueError('Staged partition changed')
    system=WORK/'system.candidate.raw';vendor=WORK/'vendor.candidate.raw'
    gsi=Path('/home/lpf/h700-arm64-isolated-20261030/gsi-system.img')
    scratch=Path(tempfile.mkdtemp(prefix='audit-',dir=WORK))
    results={}
    def read(img,path):
        return base.dump(img,path,scratch/'sample').read_bytes()
    def text(img,path):return read(img,path).decode()
    for name,bits in [('app_process64',64),('app_process32',32)]:
        data=read(system,'/system/bin/'+name)
        if data[:5]!=b'\x7fELF'+bytes([2 if bits==64 else 1]):raise ValueError('App process ELF class mismatch')
        results[name]=hashlib.sha256(data).hexdigest()
    rc=text(system,'/init.zygote64_32.rc')
    if not all(s in rc for s in ['service zygote /system/bin/app_process64','service zygote_secondary /system/bin/app_process32']):raise ValueError('Dual Zygote declarations missing')
    if 'import /init.${ro.zygote}.rc' not in text(system,'/init.rc'):raise ValueError('Zygote import missing')
    props=text(system,'/system/etc/prop.default')
    for line in ['ro.zygote=zygote64_32','ro.h700.prototype='+MARKER,'ro.debuggable=1','ro.secure=0','ro.adb.secure=0']:
        if props.splitlines().count(line)!=1:raise ValueError('Prototype property mismatch')
    build=text(system,'/system/build.prop')
    expected={'ro.zygote':'zygote64_32','ro.debuggable':'1','ro.secure':'0','ro.adb.secure':'0',
              'ro.hardware.gralloc':'h700proto','ro.product.device':'rgsp'}
    # Android's boot-property map can override prop.default with later inputs.
    # Check those actual GSI/BSP inputs rather than trusting one file alone.
    later_values=[build,text(vendor,'/build.prop')]
    if base.debug(vendor,'stat /default.prop').strip():later_values.append(text(vendor,'/default.prop'))
    for value in later_values:
        for line in value.splitlines():
            key,sep,actual=line.partition('=')
            if sep and key in expected and actual!=expected[key]:raise ValueError('Later boot property conflicts: '+key)
    if not re.search(r'^ro.product.cpu.abilist64=arm64-v8a$',build,re.M):raise ValueError('ARM64 ABI not advertised')
    if not re.search(r'^ro.product.cpu.abilist32=armeabi-v7a,armeabi$',build,re.M):raise ValueError('ARM32 ABI missing')
    # These must remain paired with the official runtime, not the old BSP DEX.
    for path in ['/system/framework/services.jar','/system/framework/framework.jar',
                 '/system/apex/com.android.runtime.release/lib64/libart.so',
                 '/system/apex/com.android.runtime.release/lib/libart.so',
                 '/system/apex/com.android.runtime.release/lib64/bionic/libc.so',
                 '/system/apex/com.android.runtime.release/lib/bionic/libc.so']:
        data=read(system,path)
        if data!=read(gsi,path):raise ValueError('GSI ART/framework coherence failed')
        results[path]=hashlib.sha256(data).hexdigest()
    apk=read(system,'/system/etc/h700-prototype/apks/H700AbiProbe64.apk')
    with zipfile.ZipFile(io.BytesIO(apk)) as z:
        libs=[n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
        if libs!=['lib/arm64-v8a/libh700_abi_probe.so'] or z.read(libs[0])[:5]!=b'\x7fELF\x02':raise ValueError('Sentinel JNI not ARM64-only')
    linker_rc=text(system,'/init.usb.rc')
    if 'service adbd /system/bin/bootstrap/linker64 /system/bin/h700-bootstrap/adbd' not in linker_rc:raise ValueError('Private adbd loader missing')
    for path in ['/system/bin/h700-bootstrap/init','/system/bin/h700-bootstrap/adbd','/system/bin/bootstrap/linker64']:
        if read(system,path)[:5]!=b'\x7fELF\x02':raise ValueError('Bootstrap executable not ELF64')
    init_stat=base.debug(system,'stat /init')
    if 'Fast link dest: "/system/bin/init"' not in init_stat:raise ValueError('Root init link unexpected')
    configs=[p for p in stage['overlay']['system'] if '/ld.config.' in p]
    if len(configs)<4:raise ValueError('Linker configuration coverage insufficient')
    for path in configs:
        value=text(system,path)
        if not value.startswith('dir.h700bootstrap = /system/bin/h700-bootstrap/\n'):raise ValueError('Bootstrap linker prefix order wrong')
        if '[h700bootstrap]' not in value or 'namespace.default.search.paths = /system/${LIB}/bootstrap' not in value:raise ValueError('Private bootstrap pool missing')
    parent_vendor=base.WORK/'vendor.candidate.raw'
    if read(vendor,'/lib/egl/libGLES_mali.so')!=read(parent_vendor,'/lib/egl/libGLES_mali.so'):raise ValueError('Original Mali32 changed')
    for path in ['/lib64/egl/libGLES_mali.so','/lib64/hw/gralloc.h700proto.so','/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so']:
        if read(vendor,path)[:5]!=b'\x7fELF\x02':raise ValueError('Missing ELF64 graphics driver')
    fst=text(vendor,'/etc/fstab.sun50iw9p1')
    if 'voldmanaged=' in fst:raise ValueError('Prototype must not expose boot-card hardware partitions to GSI vold')
    for name in ['system','vendor','data']:
        if stage['layout']['partitions'][name]['partuuid'] not in fst:raise ValueError('Prototype fstab identity mismatch')
    with (base.WORK/'prefix.raw').open('rb') as f:head,backup,layout=prototype_gpt(f.read(2048))
    with (WORK/'prefix.candidate.raw').open('rb') as f:
        if f.read(2048)!=head:raise ValueError('Prototype compact GPT differs')
    physical_head,physical_backup=relocate_gpt(head,125069950976)
    results.update({'dual_zygote':True,'coherent_gsi_art_framework':True,'arm64_only_sentinel':True,
                    'private_bootstrap':True,'mali32_preserved':True,'mali64_present':True,
                    'relocated_primary_sha256':hashlib.sha256(physical_head).hexdigest(),
                    'relocated_backup_sha256':hashlib.sha256(physical_backup).hexdigest()})
    base.jsonwrite(OUT/'boot-preflight-lock.json',{'image_sha256':image['sha256'],'offline_boot_inputs_pass':True,
                   'first_boot_verified':False,'checks':results})
    print('DUAL_ABI_OFFLINE_BOOT_INPUTS_PASS',flush=True)

if __name__=='__main__':main()
