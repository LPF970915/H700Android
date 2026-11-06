"""Assemble only regular files: audited Source64 partitions plus clean userdata."""
from pathlib import Path
import argparse
import base64
import datetime
import gzip
import hashlib
import json
import os
import re
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
OUT = REPO / 'out/roc-os-user-card-rc3-20261106'
OUT.mkdir(exist_ok=True)
WORK = next(Path('/home/lpf') / ('roc-os-user-card-rc3-20261106-v%d' % n)
            for n in range(1, 100) if not (Path('/home/lpf') / ('roc-os-user-card-rc3-20261106-v%d' % n)).exists())
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

def seed_adb(image):
    key=REPO/'out/roc-os-user-rc1-firstboot-20261105/bootdiag1-public-key'
    assert sha(key)=='817982431f56cba42111e2244f7ecc244d2867cbfe5a59c4c6a31b0b99c6e123'
    assert len(base64.b64decode(key.read_text().strip(),validate=True))==524
    assert key.read_text().strip()==Path('/mnt/c/Users/LPF/.android/adbkey.pub').read_text().split()[0]
    def debug(command):return run(['/usr/sbin/debugfs','-w','-R',command,image]).stdout
    def attrs(path,mode,uid,gid,context):
        for field,value in [('mode',mode),('uid',uid),('gid',gid)]:debug(f'set_inode_field {path} {field} {value}')
        f=WORK/('context-'+context.replace(':','_'));f.write_bytes(context.encode()+b'\0')
        debug(f'ea_set -f {f} {path} security.selinux')
    debug('mkdir /misc');attrs('/misc','041771',1000,9998,'u:object_r:system_data_file:s0')
    debug('mkdir /misc/adb');attrs('/misc/adb','042750',1000,2000,'u:object_r:adb_keys_file:s0')
    debug(f'write {key} /misc/adb/adb_keys');attrs('/misc/adb/adb_keys','0100640',1000,2000,'u:object_r:adb_keys_file:s0')
    for path,mode,uid,gid,context in [('/','0771',1000,1000,'system_data_file'),('/misc','1771',1000,9998,'system_data_file'),('/misc/adb','2750',1000,2000,'adb_keys_file'),('/misc/adb/adb_keys','0640',1000,2000,'adb_keys_file')]:
        s=run(['/usr/sbin/debugfs','-R','stat '+path,image]).stdout
        found=re.search(r'Mode:\s+([0-7]+)',s)
        assert found and int(found[1],8)==int(mode,8) and f'User:  {uid:4d}   Group:  {gid:4d}' in s,(path,s)
        assert 'u:object_r:'+context+':s0' in s,(path,s)
    back=WORK/'public-key.readback'
    run(['/usr/sbin/debugfs','-R',f'dump /misc/adb/adb_keys {back}',image])
    assert sha(back)==sha(key)

def main():
    assert shutil.disk_usage(WORK).free > 45*1024**3
    stage('release tool regression checks')
    run([sys.executable,'-m','unittest','discover','-s',REPO/'tools/release','-p','test_release_tools.py','-v'])
    stage('validate immutable inputs')
    from audit_rc3_card import audit as audit_user
    user_audit, audit = audit_user(WORK, run)
    lock = {'images': user_audit['images']}
    audited = WORK
    tools_root = Path(audit['work'])
    # Use the previously audited identical ARM64 loose tools; keep the new
    # partition audit and its raw filesystem copies separate from old products.
    (WORK/'loose-boot-tools').mkdir()
    for name, spec in audit['loose_static_tools'].items():
        source = tools_root/'loose-boot-tools'/name
        assert sha(source) == spec['sha256']
        shutil.copyfile(source,WORK/'loose-boot-tools'/name)
        (WORK/'loose-boot-tools'/name).chmod(0o755)
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
    bootbox=WORK/'busybox';bootbox.write_bytes(old['bin/busybox']['data']);bootbox.chmod(0o755)
    bootlibs=WORK/'boot-busybox-sysroot'
    for entry in entries:
        name=entry['name']
        if name.startswith(('lib/','usr/lib/')) and stat.S_ISREG(entry['mode']):
            assert '..' not in Path(name).parts
            dest=bootlibs/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(entry['data']);dest.chmod(0o755)
    (bootlibs/'lib/aarch64-linux-gnu').symlink_to('.',target_is_directory=True)
    (bootlibs/'lib64').symlink_to('lib',target_is_directory=True)
    applets=run(['/usr/bin/qemu-aarch64','-L',bootlibs,bootbox,'--list']).stdout.splitlines()
    assert all(name in applets for name in ['sha256sum','cut','insmod','chown','chmod','switch_root'])
    probe=WORK/'boot-hash-probe';probe.write_bytes(b'ROC OS boot identity probe\n')
    assert run(['/usr/bin/qemu-aarch64','-L',bootlibs,bootbox,'sha256sum',probe]).stdout.split()[0]==sha(probe)
    entries = [e for e in entries if not e['name'].startswith('grow/') and e['name'] != 'TRAILER!!!']
    selected = {'init': (REPO/'tools/release/user_boot_init_rc2.sh').read_bytes(), 'grow/grow-userdata.sh': (bootfiles/'grow-userdata.sh').read_bytes(), 'grow/prepare-android-dev-bootfix1.sh': (REPO/'tools/release/prepare_android_dev_bootfix1.sh').read_bytes()}
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
    # Android user init and the header both request enforcing. This is an
    # offline boot contract, not evidence of successful runtime enforcement.
    boot_bytes=bytearray(newboot.read_bytes())
    command=b'selinux=1 enforcing=1 androidboot.selinux=enforcing'
    boot_bytes[64:576]=command+b'\0'*(512-len(command))
    newboot.write_bytes(boot_bytes)
    nh, info = read_header(newboot); no = component_offsets(info); nb = newboot.read_bytes()
    allowed = bytearray(header); struct.pack_into('<I',allowed,16,len(ramdisk.read_bytes()))
    allowed[64:576]=command+b'\0'*(512-len(command))
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
    context = WORK/'root-context'; context.write_bytes(b'u:object_r:system_data_file:s0\0')
    run(['/usr/sbin/debugfs','-w','-R','set_inode_field / mode 040771',userdata])
    run(['/usr/sbin/debugfs','-w','-R','ea_set -f '+str(context)+' / security.selinux',userdata])
    seed_adb(userdata)
    run(['/usr/sbin/e2fsck','-f','-n',userdata])
    run(['/usr/bin/qemu-aarch64',audited/'loose-boot-tools/e2fsck_static','-f','-n',userdata])
    run(['/usr/bin/qemu-aarch64',audited/'loose-boot-tools/roc-grow-userdata-gpt','--check-volume',userdata,'--image-test'])
    listing = run(['/usr/sbin/debugfs','-R','ls -l /',userdata]).stdout
    assert 'lost+found' in listing and not any(x in listing for x in ['media','system','accounts','preinstall'])
    stage('assemble sparse whole-card regular file')
    raw = WORK/'ROC_OS_ARM64_User_RC3_20261106.img'
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
                factory_userdata_empty_except_host_public_ADB_key=True,authenticated_ADB_retained=True,ADB_root_allowed=False,network_ADB=False,userdata_context="u:object_r:system_data_file:s0",Android_ARM64_fsck_passed=True,full_gzip_verified=True,
                whole_card_image_created=True,device_or_card_modified=False,device_boot_accepted=False,
                minimum_card_GB=64,scope='RG34XXSP H700 2GB user RC3; offline verified flashable test candidate; runtime and formal release unaccepted',
                source_user_build=user_audit['build_receipt'],user_partition_audit='user-partition-audit.json',
                boot_cmdline=command.decode(),unauthenticated_failure_shell_removed=True,
                signing_identity='ROC OS production-v1',formal_release_allowed=False,
                source_build_receipt_sha256=sha(REPO/'out/source64-user-candidate-20261104'/user_audit['build_receipt']))
    result['packaging_inputs_sha256']={str(p.relative_to(REPO)):sha(p) for p in [Path(__file__),REPO/'tools/release/audit_rc2_card.py',REPO/'tools/release/audit_rc3_card.py',REPO/'tools/release/audit_candidate_card.py',REPO/'tools/release/user_boot_init_rc2.sh',REPO/'tools/release/prepare_android_dev_bootfix1.sh']}
    result['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT/'image-result.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/(gz.name+'.sha256')).write_text(result['sha256']+'  '+gz.name+'\n')
    stage('complete: image verified, no device operation')
    print('CARD_IMAGE_READY',gz,flush=True)

try:
    main()
except Exception as error:
    (WORK/'failure.json').write_text(json.dumps({'passed':False,'error':repr(error),'work':str(WORK)},indent=2)+'\n')
    raise
