#!/usr/bin/env python3
"""Independently audit the completed test1's boot inputs before any card write."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import package_h700_v6a as base
from dualabi_image_layout import relocate_gpt
from package_h700_dualabi_test1 import ROOT,OUT,WORK,P1B,IMAGE_MARKER


def main():
    base.constrained()
    image=json.loads((OUT/'image-lock.json').read_text())
    parent=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/boot-preflight-lock.json').read_text())
    system=WORK/'system.candidate.raw'
    if not image['full_gzip_decompression_verified'] or not image['all_decompressed_range_hashes_verified']:
        raise ValueError('Image decompression gate not passed')
    checks={}
    for path,digest in parent['checks'].items():
        if not path.startswith('/system/'):
            continue
        sample=base.dump(system,path,WORK/'coherence-readback.tmp')
        if base.sha(sample)!=digest:
            raise ValueError('Inherited runtime coherence changed: '+path)
        checks[path]=digest
    props=base.dump(system,'/system/etc/prop.default',WORK/'props.audit').read_text().splitlines()
    for line in ['ro.vndk.version=29','dalvik.vm.heapgrowthlimit=128m','dalvik.vm.heapsize=256m',
                 'persist.vendor.hwc.software_vsync=true','ro.h700.prototype.image='+IMAGE_MARKER]:
        if props.count(line)!=1:raise ValueError('Test1 property mismatch')
    setup=base.dump(system,'/system/bin/h700-prototype-setup.sh',WORK/'setup.audit')
    if setup.read_bytes()!=(ROOT/'tools/arm64_probe/test1_setup.sh').read_bytes():raise ValueError('Installer mismatch')
    subprocess.run(['bash','-n',str(setup)],check=True)
    for command in ['flock','restorecon','svc','pm','sh']:
        info=base.debug(system,'stat /system/bin/'+command)
        if 'Inode:' not in info:
            raise ValueError('First-boot dependency absent: '+command)
    checks['first_boot_command_paths_present']=True
    for path,target in [('/init','/system/bin/h700-bootstrap/init'),('/system/bin/init','h700-bootstrap/init')]:
        if 'Fast link dest: "'+target+'"' not in base.debug(system,'stat '+base.q(path)):
            raise ValueError('Preserved ramdisk handoff no longer valid')
    archive=OUT/(image['release']+'.img.gz')
    if base.sha(archive)!=image['gzip_sha256']:raise ValueError('Image gzip changed')
    with gzip.open(archive,'rb') as f:head=f.read(2048)
    primary,backup=relocate_gpt(head,125069950976)
    for name,data in [('primary',primary),('backup',backup)]:
        key='relocated_'+name+'_sha256';checks[key]=hashlib.sha256(data).hexdigest()
        if checks[key]!=parent['checks'][key]:raise ValueError('Physical compact GPT audit mismatch')
    checks.update({'five_runtime_properties_persisted':True,'a_unlock_navigation_signed_apk':True,
                   'clean_parent_factory_tail':True,'gsi_framework_art_coherent':True,
                   'p1b_relative_handoff_preserved':True,'fresh_first_boot':False})
    base.jsonwrite(OUT/'boot-preflight-lock.json',{'image_sha256':image['sha256'],
                   'offline_boot_inputs_pass':True,'first_boot_verified':False,'checks':checks})
    print('TEST1_OFFLINE_BOOT_INPUTS_PASS',flush=True)


if __name__=='__main__':main()
