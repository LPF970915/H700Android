#!/usr/bin/env python3
"""Derive a one-hop /init repair from verified P1; regular image files only."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import package_h700_v6a as base

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('/home/lpf/h700-dualabi-image-20261031')
WORK=Path('/home/lpf/h700-dualabi-entry-p1a-20261031')
OUT=ROOT/'out/dualabi-entry-p1a-20261031'
TARGET='/system/bin/h700-bootstrap/init'

def main():
    base.constrained()
    lock=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/image-lock.json').read_text())
    expected=next(e for e in lock['ranges'] if e['name']=='system')
    old=base.regular(PARENT/'system.candidate.raw')
    if old.stat().st_size!=8589934592 or base.sha(old)!=expected['sha256']:raise ValueError('P1 system input changed')
    if WORK.exists():raise ValueError('Preserve the previous repair stage; never overwrite it')
    WORK.mkdir();OUT.mkdir(exist_ok=True)
    new=WORK/'system.candidate.raw'
    subprocess.run(['cp','--sparse=always',str(old),str(new)],check=True)
    # Android10's first-stage linker calls readlink(/init) exactly once, before
    # proc/APEX is mounted. The returned path must itself select our namespace.
    before=base.debug(old,'stat /init')
    if 'Fast link dest: "/system/bin/init"' not in before:raise ValueError('Unexpected P1 entry link')
    if 'Fast link dest: "'+TARGET+'"' not in base.debug(old,'stat /system/bin/init'):raise ValueError('Unexpected P1 second hop')
    cfg=base.dump(old,'/system/etc/ld.config.txt',WORK/'ld.config.txt').read_text()
    if not cfg.startswith('dir.h700bootstrap = /system/bin/h700-bootstrap/\n'):raise ValueError('Bootstrap prefix must precede generic system paths')
    if '/system/bin/init'.startswith('/system/bin/h700-bootstrap/'):raise ValueError('Negative first-hop test failed')
    if not TARGET.startswith('/system/bin/h700-bootstrap/'):raise ValueError('Positive first-hop test failed')
    context=base.write(WORK/'init.context','u:object_r:init_exec:s0\x00')
    revision=base.write(WORK/'boot-entry-revision','p1a-one-hop-20261031\n')
    file_context=base.write(WORK/'file.context','u:object_r:system_file:s0\x00')
    commands=[
        'rm /init','symlink /init '+base.q(TARGET),
        'set_inode_field /init mode 0120750','set_inode_field /init uid 0','set_inode_field /init gid 2000',
        'ea_set -f '+base.q(context)+' /init security.selinux',
        'write '+base.q(revision)+' /system/etc/h700-prototype/boot-entry-revision',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision mode 0100644',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision uid 0',
        'set_inode_field /system/etc/h700-prototype/boot-entry-revision gid 0',
        'ea_set -f '+base.q(file_context)+' /system/etc/h700-prototype/boot-entry-revision security.selinux']
    script=base.write(WORK/'entry.debugfs.commands','\n'.join(commands)+'\n')
    with (WORK/'entry.debugfs.log').open('w') as log:
        subprocess.run(['debugfs','-w','-f',str(script),str(new)],stdout=log,stderr=subprocess.STDOUT,check=True)
    if 'Fast link dest: "'+TARGET+'"' not in base.debug(new,'stat /init'):raise ValueError('Direct root entry readback failed')
    if base.dump(new,'/system/etc/h700-prototype/boot-entry-revision',WORK/'revision.readback').read_bytes()!=revision.read_bytes():raise ValueError('Revision readback failed')
    with (WORK/'entry.fsck.log').open('w') as log:
        subprocess.run(['e2fsck','-f','-n',str(new)],stdout=log,stderr=subprocess.STDOUT,check=True)
    delta=OUT/'delta';delta.mkdir()
    ranges=[];offset=0;pending=None
    def flush():
        nonlocal pending
        if pending is None:return
        start,a,b=pending;index=len(ranges)
        oldfile=delta/f'{index:03d}.old.bin';newfile=delta/f'{index:03d}.new.bin'
        oldfile.write_bytes(a);newfile.write_bytes(b)
        ranges.append({'offset':start,'bytes':len(a),'old_sha256':hashlib.sha256(a).hexdigest(),
                       'new_sha256':hashlib.sha256(b).hexdigest(),'old_file':oldfile.name,'new_file':newfile.name})
        pending=None
    with old.open('rb') as a,new.open('rb') as b:
        while left:=a.read(4*1024**2):
            right=b.read(len(left))
            if left!=right:
                for i in range(0,len(left),4096):
                    x,y=left[i:i+4096],right[i:i+4096]
                    if x==y:continue
                    at=offset+i
                    if pending and pending[0]+len(pending[1])==at and len(pending[1])<65536:
                        pending=(pending[0],pending[1]+x,pending[2]+y)
                    else:flush();pending=(at,x,y)
            offset+=len(left)
        flush()
    if not ranges or sum(e['bytes'] for e in ranges)>1024**2:raise ValueError('Entry repair changed too many filesystem blocks')
    newsha=base.sha(new)
    gz=OUT/'H700_DualABI_P1a_system_entryfix_20261031.img.gz'
    with gz.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0,filename='') as z,new.open('rb') as f:
        while block:=f.read(8*1024**2):z.write(block)
    digest=hashlib.sha256();count=0
    with gzip.open(gz,'rb') as f:
        while block:=f.read(8*1024**2):digest.update(block);count+=len(block)
    if count!=8589934592 or digest.hexdigest()!=newsha:raise ValueError('System component gzip mismatch')
    result={'revision':'p1a-one-hop-20261031','partition_bytes':8589934592,'parent_system_sha256':expected['sha256'],
            'system_sha256':newsha,'gzip_file':gz.name,'gzip_sha256':base.sha(gz),'gzip_bytes':gz.stat().st_size,
            'root_init_target':TARGET,'first_stage_one_hop_check':True,'filesystem_check':True,
            'full_component_decompression':True,'ranges':ranges,'card_modified':False,'boot_pass':False}
    base.jsonwrite(OUT/'entry-lock.json',result)
    print('BOOT_ENTRY_REPAIR_COMPONENT_VERIFIED',len(ranges),sum(e['bytes'] for e in ranges),flush=True)

if __name__=='__main__':main()
