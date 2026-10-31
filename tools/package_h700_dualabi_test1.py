#!/usr/bin/env python3
"""Create the first immutable ARM64 test image from pinned offline P1b inputs."""
from pathlib import Path
import gzip
import hashlib
import json
import re
import subprocess
import zipfile
import package_h700_v6a as base
import package_h700_dualabi_prototype as proto
from apply_h700_dualabi_runtime import patched

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/dualabi-test1-20261031'
WORK = Path('/home/lpf/h700-dualabi-test1-20261031')
P1 = Path('/home/lpf/h700-dualabi-image-20261031')
P1B = Path('/home/lpf/h700-dualabi-handoff-p1b-20261031')
RELEASE = 'H700_RG34XXSP_2GB_ARM64_Test1_GSI10_20261031_NoROM'
IMAGE_MARKER = 'dualabi-test1-20261031'


def main():
    base.constrained()
    if WORK.exists():
        raise ValueError('Preserve the previous test1 stage; no replay')
    WORK.mkdir()
    OUT.mkdir(exist_ok=True)
    p1 = json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/image-lock.json').read_text())
    p1b = json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-handoff-p1b-20261031/handoff-lock.json').read_text())
    overlay = json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/overlay-lock.json').read_text())
    ranges = []
    for entry in p1['ranges']:
        name = entry['name']
        source = (P1B if name in ['system','vendor'] else P1)/(name+'.candidate.raw')
        expected = p1b['components'][name]['sha256'] if name in ['system','vendor'] else entry['sha256']
        base.regular(source)
        print('TEST1_VERIFY_PARENT', name, flush=True)
        if source.stat().st_size != entry['bytes'] or base.sha(source) != expected:
            raise ValueError('Pinned P1b range changed: '+name)
        ranges.append({**entry,'sha256':expected,'source':source})
    system = WORK/'system.candidate.raw'
    subprocess.run(['cp','--sparse=always',str(P1B/'system.candidate.raw'),str(system)],check=True)
    old_prop = base.dump(system,'/system/etc/prop.default',WORK/'prop.default.before')
    if base.sha(old_prop) != overlay['system']['/system/etc/prop.default']['sha256']:
        raise ValueError('Unknown property input')
    prop = WORK/'prop.default'
    prop.write_bytes(patched(old_prop.read_bytes()) + ('ro.h700.prototype.image='+IMAGE_MARKER+'\n').encode())
    navigation = base.regular(OUT/'RGSPNavigation64Test1.apk')
    nav_lock = json.loads((OUT/'apps-build.json').read_text())['RGSPNavigation64Test1.apk']
    if base.sha(navigation) != nav_lock['sha256']:
        raise ValueError('Navigation input changed')
    files = {
        '/system/etc/prop.default':(prop,'0100644','u:object_r:system_file:s0'),
        '/system/app/RGSPNavigation/RGSPNavigation.apk':(navigation,'0100644','u:object_r:system_file:s0'),
        '/system/bin/h700-prototype-setup.sh':(ROOT/'tools/arm64_probe/test1_setup.sh','0100755','u:object_r:shell_exec:s0'),
        '/system/etc/h700-prototype/H700_ANBERNIC_keys.cfg':(ROOT/'config/retroarch/android/H700_ANBERNIC_keys.cfg','0100644','u:object_r:system_file:s0'),
        '/system/etc/h700-prototype/retroarch-test.cfg':(ROOT/'config/retroarch/android/H700_DualABI_Test1.cfg','0100644','u:object_r:system_file:s0'),
        '/system/etc/h700-prototype/image-revision':(base.write(WORK/'image-revision',IMAGE_MARKER+'\n'),'0100644','u:object_r:system_file:s0'),
    }
    subprocess.run(['bash','-n',str(ROOT/'tools/arm64_probe/test1_setup.sh')],check=True)
    proto.WORK = WORK
    modified = proto.modify(system,files,'u:object_r:system_file:s0')
    # Ensure all inherited P1 overlays remain exact apart from the explicit files.
    checked = 0
    for inside,record in overlay['system'].items():
        if inside in files or inside == '/system/bin/init':
            continue
        sample = base.dump(system,inside,WORK/'inherited-readback.tmp')
        if base.sha(sample) != record['sha256']:
            raise ValueError('Inherited overlay changed: '+inside)
        checked += 1
    for path,target in [('/init','/system/bin/h700-bootstrap/init'),('/system/bin/init','h700-bootstrap/init')]:
        if 'Fast link dest: "'+target+'"' not in base.debug(system,'stat '+base.q(path)):
            raise ValueError('P1b handoff link changed')
    if base.dump(system,'/system/etc/h700-prototype/boot-entry-revision',WORK/'entry-revision').read_text().strip() != p1b['revision']:
        raise ValueError('P1b entry revision changed')
    listing=base.dump(system,'/system/etc/h700-prototype/apps.list',WORK/'apps.list').read_text().splitlines()
    if len(listing)!=4:
        raise ValueError('Only four locked prototype apps are allowed')
    for line in listing:
        package,filename,abi,digest=line.split()
        sample=base.dump(system,'/system/etc/h700-prototype/apks/'+filename,WORK/filename)
        if base.sha(sample)!=digest:
            raise ValueError('APK payload changed')
        if filename=='H700AbiProbe64.apk':
            with zipfile.ZipFile(sample) as z:
                libs=[n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
                if libs!=['lib/arm64-v8a/libh700_abi_probe.so'] or z.read(libs[0])[:5]!=b'\x7fELF\x02':
                    raise ValueError('Probe no longer ARM64-only')
    # Both ordinary and bootstrap selectors must survive in the selected API29 file.
    ld=base.dump(system,'/system/etc/ld.config.29.txt',WORK/'ld.config.29.txt').read_text()
    if not ld.startswith('dir.h700bootstrap = /system/bin/h700-bootstrap/\n') or '[h700bootstrap]' not in ld:
        raise ValueError('Private bootstrap selector lost')
    for entry in ranges:
        if entry['name']=='system':entry['source']=system;entry['sha256']=base.sha(system)
    target=OUT/(RELEASE+'.img.gz')
    if target.exists():raise ValueError('Preserve existing test1 image')
    digest=hashlib.sha256()
    with target.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0,filename='') as z:
        for entry in ranges:
            print('TEST1_COMPRESS',entry['name'],flush=True)
            with entry['source'].open('rb') as f:
                while block:=f.read(8*1024**2):digest.update(block);z.write(block)
    total=0;verify=hashlib.sha256()
    with gzip.open(target,'rb') as f:
        for entry in ranges:
            count=entry['bytes'];part=hashlib.sha256()
            while count:
                block=f.read(min(count,8*1024**2))
                if not block:raise ValueError('Short full-image decompression')
                count-=len(block);total+=len(block);part.update(block);verify.update(block)
            if part.hexdigest()!=entry['sha256']:raise ValueError('Decompressed range mismatch')
        if f.read(1):raise ValueError('Extra image tail')
    if total!=p1['bytes'] or verify.hexdigest()!=digest.hexdigest():raise ValueError('Full image mismatch')
    result={'release':RELEASE,'bytes':total,'sha256':digest.hexdigest(),'gzip_bytes':target.stat().st_size,
            'gzip_sha256':base.sha(target),'ranges':[{k:v for k,v in e.items() if k!='source'} for e in ranges],
            'layout':p1['layout'],'runtime_marker':p1['marker'],'image_marker':IMAGE_MARKER,
            'entry_revision':p1b['revision'],'full_gzip_decompression_verified':True,
            'all_decompressed_range_hashes_verified':True,'modified_files':modified,
            'inherited_overlay_files_readback':checked,'factory_tail_from_pinned_clean_parent':True,
            'fresh_whole_card_flash':False,'fresh_first_boot':False,'rom_bios_accounts_saves':False,
            'contains_official_runtime_probe_fixture_core_or_cube':False}
    base.jsonwrite(OUT/'image-lock.json',result)
    print('TEST1_IMAGE_ALL_RANGES_AND_DECOMPRESSION_PASS',flush=True)


if __name__=='__main__':main()
