"""Assemble only regular files: audited Source64 partitions plus clean userdata."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
sys.path.insert(0, str(REPO / 'tools/source64/storage'))
from package_h700_v6a import constrained
from android_bootimg import read_header, component_offsets, pack
from patch_ramdisk import parse, emit
import layout
constrained()
OUT = REPO / 'out/roc-os-source64-card-20261104'
OUT.mkdir(exist_ok=True)
WORK = next(Path('/home/lpf') / ('roc-os-source64-card-20261104-v%d' % n)
            for n in range(1, 100) if not (Path('/home/lpf') / ('roc-os-source64-card-20261104-v%d' % n)).exists())
WORK.mkdir()

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def run(args, codes=(0,)):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    with (WORK / 'commands.log').open('a') as f:
        f.write(json.dumps(list(map(str, args))) + '\n' + p.stdout + p.stderr)
    assert p.returncode in codes, (args, p.returncode, p.stdout[-1200:], p.stderr[-1200:])
    return p

def stage(name):
    print('CARD_STAGE', name, flush=True)
    (OUT / 'progress.json').write_text(json.dumps({'stage': name, 'work': str(WORK)}, indent=2)+'\n')

def main():
    assert shutil.disk_usage(WORK).free > 45*1024**3
    stage('validate immutable inputs')
    lock = json.loads((REPO / 'docs/baselines/roc-os-source64-round2-20261103/completion.json').read_text())
    audit = json.loads((REPO / 'out/roc-os-source64-round2-20261103/round2-audit-v7.json').read_text())
    assert lock['offline_parity_audit_passed'] and audit['passed']
    audited = Path(audit['work'])
    for name, spec in lock['images'].items():
        f = Path('/home/lpf/roc-os-source64-20261103/out/target/product/roc_os_source64') / name
        assert sha(f) == spec['sha256']
    source_prefix = Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
    contract = json.loads((REPO / 'out/roc-os-source64-round2-20261103/boot-contract.json').read_text())
    assert sha(source_prefix) == contract['prefix_sha256']
    bootfiles = Path(contract['work'])
    assert sha(bootfiles/'init') == contract['init_sha256']
    prefix = bytearray(source_prefix.read_bytes())
    boot_start, boot_length = layout.STARTS[3], layout.LENGTHS[3]
    template = WORK/'boot.parent.raw'
    template.write_bytes(prefix[boot_start:boot_start+boot_length])
    header, h = read_header(template)
    offsets = component_offsets(h)
    original = template.read_bytes()
    entries = parse(gzip.decompress(original[offsets['ramdisk']:offsets['ramdisk']+h['ramdisk_size']]))
    old = {e['name']: e for e in entries}
    assert old['init']['data'].startswith(b'#!/bin/sh')
    entries = [e for e in entries if not e['name'].startswith('grow/') and e['name'] != 'TRAILER!!!']
    selected = {'init': (bootfiles/'init').read_bytes(), 'grow/grow-userdata.sh': (bootfiles/'grow-userdata.sh').read_bytes()}
    for name, spec in audit['loose_static_tools'].items():
        f = audited/'loose-boot-tools'/name
        assert sha(f) == spec['sha256']
        selected['grow/'+name] = f.read_bytes()
    for name, body in selected.items():
        existing = next((e for e in entries if e['name'] == name), None)
        if existing is None:
            existing = dict(old['init']); existing['name'] = name; existing['ino'] = 10000+len(entries)
            entries.append(existing)
        existing.update(data=body, mode=stat.S_IFREG|0o755, uid=0, gid=0, nlink=1)
    entries.append(old['TRAILER!!!'])
    archive = b''.join(emit(e) for e in entries)
    ramdisk = WORK/'ramdisk.unified.gz'
    ramdisk.write_bytes(gzip.compress(archive, compresslevel=6, mtime=0))
    reparse = {e['name']:e for e in parse(gzip.decompress(ramdisk.read_bytes()))}
    assert len(reparse) == len(entries)
    for name, body in selected.items():
        assert reparse[name]['data'] == body and reparse[name]['mode'] == stat.S_IFREG|0o755
    for name,e in old.items():
        if name not in selected and not name.startswith('grow/'):
            assert reparse[name] == e
    def repack(rd, target):
        pack(argparse.Namespace(template=str(template),out=str(target),kernel=None,ramdisk=str(rd),second=None,dtb=None))
    oldrd = WORK/'ramdisk.parent.gz'
    oldrd.write_bytes(original[offsets['ramdisk']:offsets['ramdisk']+h['ramdisk_size']])
    identity = WORK/'boot.identity.raw'; repack(oldrd,identity)
    assert sha(identity) == sha(template), 'Vendor boot identity repack mismatch'
    newboot = WORK/'boot.unified.raw'; repack(ramdisk,newboot)
    nh, info = read_header(newboot); no = component_offsets(info); nb = newboot.read_bytes()
    allowed = bytearray(header); struct.pack_into('<I',allowed,16,len(ramdisk.read_bytes()))
    assert nh == allowed
    for component in ['kernel','second','dtb']:
        size = h.get('dt_size_detected',h['dt_size']) if component=='dtb' else h[component+'_size']
        assert original[offsets[component]:offsets[component]+size] == nb[no[component]:no[component]+size]
    stage('prepare compact GPT and boot prefix')
    primary, backup = layout.derive(prefix[:2048])
    prefix[:2048] = primary; prefix[boot_start:boot_start+boot_length] = nb
    parent = source_prefix.read_bytes()
    assert prefix[2048:boot_start] == parent[2048:boot_start]
    assert prefix[boot_start+boot_length:] == parent[boot_start+boot_length:]
    pref = WORK/'prefix.unified.raw'; pref.write_bytes(prefix)
    stage('create empty compatible userdata')
    data_bytes = layout.SEED_BYTES-layout.DATA_START-len(backup)
    userdata = WORK/'userdata.clean.raw'
    with userdata.open('xb') as f:f.truncate(data_bytes)
    run(['/usr/sbin/mke2fs','-q','-F','-t','ext4','-b','4096','-I','256','-L','userdata',
         '-U',str(layout.DATA_FS_UUID),'-O','^orphan_file,^metadata_csum_seed,^metadata_csum,^64bit',
         '-E','root_owner=1000:1000,lazy_itable_init=0,lazy_journal_init=0',userdata])
    context = WORK/'root-context'; context.write_bytes(b'u:object_r:system_data_root_file:s0\0')
    run(['/usr/sbin/debugfs','-w','-R','set_inode_field / mode 040771',userdata])
    run(['/usr/sbin/debugfs','-w','-R','ea_set -f '+str(context)+' / security.selinux',userdata])
    run(['/usr/sbin/e2fsck','-f','-n',userdata])
    run(['/usr/bin/qemu-aarch64',audited/'loose-boot-tools/e2fsck_static','-f','-n',userdata])
    run(['/usr/bin/qemu-aarch64',audited/'loose-boot-tools/roc-grow-userdata-gpt','--check-volume',userdata,'--image-test'])
    listing = run(['/usr/sbin/debugfs','-R','ls -l /',userdata]).stdout
    assert 'lost+found' in listing and not any(x in listing for x in ['media','system','accounts','preinstall'])
    stage('assemble sparse whole-card regular file')
    raw = WORK/'ROC_OS_ARM64_Source64_Clean_Test1_20261104.img'
    ranges = [('prefix',0,pref.stat().st_size,pref),('system',layout.STARTS[4],8*1024**3,audited/'system.raw'),
              ('vendor',layout.STARTS[5],2*1024**3,audited/'vendor.raw'),('userdata',layout.DATA_START,data_bytes,userdata)]
    records=[]
    with raw.open('xb') as dst:
        for name,offset,length,src in ranges:
            assert src.stat().st_size==length
            digest=hashlib.sha256(); dst.seek(offset)
            with src.open('rb') as f:
                while b:=f.read(4*1024**2):
                    digest.update(b)
                    if b.count(0)==len(b):dst.seek(len(b),1)
                    else:dst.write(b)
            records.append(dict(name=name,offset=offset,bytes=length,sha256=digest.hexdigest()))
        dst.seek(layout.SEED_BYTES-len(backup));dst.write(backup);dst.truncate(layout.SEED_BYTES)
        dst.flush();os.fsync(dst.fileno())
    records.append(dict(name='backup_gpt',offset=layout.SEED_BYTES-len(backup),bytes=len(backup),sha256=hashlib.sha256(backup).hexdigest()))
    stage('verify complete card ranges and filesystem bytes')
    full=hashlib.sha256()
    with raw.open('rb') as f:
        for record in records:
            assert f.tell()==record['offset'];digest=hashlib.sha256();left=record['bytes']
            while left:
                b=f.read(min(left,4*1024**2));assert b;left-=len(b);digest.update(b);full.update(b)
            assert digest.hexdigest()==record['sha256']
    assert raw.stat().st_size==layout.SEED_BYTES
    run(['/usr/bin/qemu-aarch64',audited/'loose-boot-tools/roc-grow-userdata-gpt','--check',raw,'--image-test'])
    stage('compress distributable image')
    gz=OUT/(raw.name+'.gz')
    assert not gz.exists(), 'Do not overwrite a previous release'
    with raw.open('rb') as src,gz.open('xb') as dst:
        with gzip.GzipFile(fileobj=dst,mode='wb',compresslevel=6,mtime=0,filename='') as compressor:
            shutil.copyfileobj(src,compressor,4*1024**2)
    stage('verify full gzip decompression')
    with gzip.open(gz,'rb') as src: decompressed=hashlib.file_digest(src,'sha256').hexdigest()
    assert decompressed==full.hexdigest()
    result=dict(passed=True,image=str(gz),bytes=gz.stat().st_size,sha256=sha(gz),raw_bytes=raw.stat().st_size,
                raw_sha256=decompressed,ranges=records,work=str(WORK),boot_kernel_dtb_preserved=True,
                factory_userdata_empty=True,Android_ARM64_fsck_passed=True,full_gzip_verified=True,
                whole_card_image_created=True,device_or_card_modified=False,device_boot_accepted=False,
                minimum_card_GB=64,scope='RG34XXSP H700 2GB engineering test; no third-party preloads/ROM/accounts',
                source_completion_sha256=sha(REPO/'docs/baselines/roc-os-source64-round2-20261103/completion.json'))
    (OUT/'image-result.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/(gz.name+'.sha256')).write_text(result['sha256']+'  '+gz.name+'\n')
    stage('complete: image verified, no device operation')
    print('CARD_IMAGE_READY',gz,flush=True)

main()
