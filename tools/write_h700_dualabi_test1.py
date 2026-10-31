#!/usr/bin/env python3
"""Fresh test1 writer for the exact authorized spare. Default is offline plan.

Only the user-authorized second card is accepted. Never infers a target from
capacity alone, never replays an interrupted write, never touches the work card.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

from dualabi_image_layout import IMAGE_BYTES, relocate_gpt
from h700_spare_guard import spare_guard

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/dualabi-test1-20261031'
SESSION=ROOT/'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json'
IDENTITY=ROOT/'out/dualabi-prototype-20261030/spare-card.private.json'
REMOTE='/data/local/tmp/h700-dualabi-test1-20261031'
ADB=Path(os.environ.get('LOCALAPPDATA',''))/'Android/Sdk/platform-tools/adb.exe'

def sha(file):
    with file.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    lock=json.loads((OUT/'image-lock.json').read_text())
    preflight=json.loads((OUT/'boot-preflight-lock.json').read_text())
    if not preflight['offline_boot_inputs_pass'] or preflight['image_sha256']!=lock['sha256']:raise ValueError('Offline boot-input audit required')
    image=OUT/(lock['release']+'.img.gz')
    if lock['bytes']!=IMAGE_BYTES or not lock['full_gzip_decompression_verified']:raise ValueError('Unverified image')
    if not args.execute:
        print('PLAN: verify exact USB/card identity; preserve spare metadata; write only the authorized second card; relocate backup GPT without resizing partitions; full readback. No device access.')
        return
    if sha(image)!=lock['gzip_sha256'] or image.stat().st_size!=lock['gzip_bytes']:raise ValueError('Image changed')
    serial=json.loads(SESSION.read_text())['serial']
    recorded=json.loads(IDENTITY.read_text())['cards']['stdout']
    lines=recorded.split('/sys/block/mmcblk1\n',1)[1].splitlines()
    sectors=int(lines[0]);cid=lines[4]
    if sectors!=244277248 or not re.fullmatch('[a-fA-F0-9]{32}',cid):raise ValueError('Private spare identity not recognized')
    size=sectors*512
    def adb(*args,timeout=40):
        r=subprocess.run([str(ADB),'-s',serial,*args],capture_output=True,timeout=timeout)
        if r.returncode:
            save('transport-operation-failure.private.json',{'rc':r.returncode,
                 'stdout':r.stdout.decode(errors='replace'),'stderr':r.stderr.decode(errors='replace')})
            raise RuntimeError('ADB operation failed; inspect private receipt')
        return r.stdout.decode('utf-8','replace').replace('\r','').strip()
    if subprocess.check_output([str(ADB),'-d','get-serialno']).decode().strip()!=serial:raise ValueError('USB identity mismatch')
    for prop,value in [('ro.serialno',serial),('ro.product.device','rgsp'),('persist.vendor.rgsp.input_profile','rg34xxsp')]:
        if adb('shell','getprop '+prop)!=value:raise ValueError('Wrong device/profile')
    if adb('shell','id -u')!='0':raise ValueError('Root required')
    if adb('shell','cat /sys/block/mmcblk1/device/cid')!=cid:raise ValueError('Spare CID mismatch')
    if adb('shell','cat /sys/block/mmcblk1/size')!=str(sectors):raise ValueError('Spare size mismatch')
    if adb('shell','getprop ro.h700.prototype'):raise ValueError('Must run from the original working system')
    before=adb('shell','cat /proc/sys/kernel/random/boot_id; pidof surfaceflinger system_server; sha256sum /system/framework/services.jar /vendor/lib/egl/libGLES_mali.so; cat /proc/mounts')
    if args.verify_only:
        original=json.loads((OUT/'card-before.private.json').read_text())['invariants']
        if before!=original:raise ValueError('Working-system invariants changed')
    else:
        if (OUT/'card-write-started.private.json').exists():raise ValueError('Prior write attempt retained; use --verify-only or inspect it, never blindly replay')
        save('card-before.private.json',{'invariants':before,'cid':cid,'sectors':sectors})
        space=adb('shell','df -k /data').splitlines()[-1].split()
        if int(space[3])*1024<image.stat().st_size+256*1024**2:raise ValueError('Insufficient device staging space')
    original_cid=recorded.split('/sys/block/mmcblk0\n',1)[1].splitlines()[4]
    guard=spare_guard(serial,original_cid,cid,(5,6))
    guard += """number=$(cat /sys/block/mmcblk1/dev)
major=${number%:*}; minor=${number#*:}
[ "$(stat -c %t:%T /dev/block/mmcblk1)" = "$(printf '%x:%x' "$major" "$minor")" ]
"""
    guardfile=OUT/'spare-guard.private.sh';guardfile.write_text(guard,encoding='utf-8',newline='\n')
    if not args.verify_only:
        if adb('shell',f'if [ -e {REMOTE} ]; then echo EXISTS; else echo NEW; fi')!='NEW':raise ValueError('Remote preservation directory already exists')
        adb('shell',f'mkdir {REMOTE}; chmod 700 {REMOTE}')
    adb('push',str(guardfile),REMOTE+'/guard.sh')
    if adb('shell',f'sh {REMOTE}/guard.sh')!='EXACT_SPARE_PARTITIONS_UNMOUNTED':raise ValueError('Spare guard failed')
    with gzip.open(image,'rb') as f:head=f.read(2048)
    physical_head,physical_backup=relocate_gpt(head,size)
    if hashlib.sha256(physical_head).hexdigest()!=preflight['checks']['relocated_primary_sha256'] or hashlib.sha256(physical_backup).hexdigest()!=preflight['checks']['relocated_backup_sha256']:
        raise ValueError('Physical GPT differs from independently audited fixture')
    header=OUT/'spare-primary.private.bin';backup=OUT/'spare-backup.private.bin'
    header.write_bytes(physical_head);backup.write_bytes(physical_backup)
    expected=hashlib.sha256();count=0
    with gzip.open(image,'rb') as f:
        if f.read(2048)!=head:raise ValueError('Image header changed')
        expected.update(physical_head);count=2048
        while block:=f.read(8*1024**2):expected.update(block);count+=len(block)
    if count!=IMAGE_BYTES:raise ValueError('Image stream length mismatch')
    if not args.verify_only:
        adb('shell',f'sh {REMOTE}/guard.sh; dd if=/dev/block/mmcblk1 of={REMOTE}/before-head.bin bs=4096 count=2048; dd if=/dev/block/mmcblk1 of={REMOTE}/before-tail.bin bs=512 skip={sectors-128} count=128',timeout=60)
        adb('pull',REMOTE+'/before-head.bin',str(OUT/'spare-before-head.private.bin'))
        adb('pull',REMOTE+'/before-tail.bin',str(OUT/'spare-before-tail.private.bin'))
        print('PUSH_VERIFIED_IMAGE',flush=True)
        with (OUT/'card-push.private.log').open('wb') as log:
            subprocess.run([str(ADB),'-s',serial,'push',str(image),REMOTE+'/image.img.gz'],stdout=log,stderr=subprocess.STDOUT,timeout=3600,check=True)
        for file,name in [(header,'primary.bin'),(backup,'backup.bin')]:adb('push',str(file),REMOTE+'/'+name)
        script=guard+f'''set -o pipefail
[ "$(sha256sum {REMOTE}/image.img.gz | cut -d ' ' -f 1)" = {lock['gzip_sha256']} ]
[ "$(sha256sum {REMOTE}/primary.bin | cut -d ' ' -f 1)" = {sha(header)} ]
[ "$(sha256sum {REMOTE}/backup.bin | cut -d ' ' -f 1)" = {sha(backup)} ]
mkdir {REMOTE}/write-started
gzip -dc {REMOTE}/image.img.gz | dd of=/dev/block/mmcblk1 bs=4194304
sync
dd if={REMOTE}/backup.bin of=/dev/block/mmcblk1 bs=512 seek={sectors-3} conv=notrunc
sync
dd if={REMOTE}/primary.bin of=/dev/block/mmcblk1 bs=512 conv=notrunc
sync
echo SPARE_WRITE_COMPLETE
'''
        writefile=OUT/'spare-write.private.sh';writefile.write_text(script,encoding='utf-8',newline='\n')
        adb('push',str(writefile),REMOTE+'/write.sh')
        save('card-write-started.private.json',{'image_sha256':lock['sha256'],'expected_readback_sha256':expected.hexdigest(),'cid':cid,'sectors':sectors})
        print('WRITE_AUTHORIZED_SPARE_ONLY',flush=True)
        with (OUT/'card-write.private.log').open('wb') as log:
            subprocess.run([str(ADB),'-s',serial,'shell','-T','sh '+REMOTE+'/write.sh'],stdout=log,stderr=subprocess.STDOUT,timeout=14400,check=True)
        if 'SPARE_WRITE_COMPLETE' not in (OUT/'card-write.private.log').read_text(errors='replace'):raise ValueError('No write completion marker')
    print('FULL_CARD_IMAGE_RANGE_READBACK',flush=True)
    # Android10's ARM32 toybox head stores -c in int: never use head -c 32GiB.
    check=guard+f'''set -o pipefail
blockdev --flushbufs /dev/block/mmcblk1
echo SPARE_CACHE_INVALIDATED
{{ dd if=/dev/block/mmcblk1 bs=4194304 count=7733 2>/dev/null && dd if=/dev/block/mmcblk1 bs=512 skip=63348736 count=3 2>/dev/null; }} | sha256sum
dd if=/dev/block/mmcblk1 bs=512 skip={sectors-3} count=3 2>/dev/null | sha256sum
'''
    checkfile=OUT/'spare-readback.private.sh';checkfile.write_text(check,encoding='utf-8',newline='\n')
    adb('push',str(checkfile),REMOTE+'/readback.sh')
    with (OUT/'card-readback.private.log').open('wb') as log:
        subprocess.run([str(ADB),'-s',serial,'shell','-T','sh '+REMOTE+'/readback.sh'],stdout=log,stderr=subprocess.STDOUT,timeout=14400,check=True)
    text=(OUT/'card-readback.private.log').read_text(errors='replace')
    if 'SPARE_CACHE_INVALIDATED' not in text:raise ValueError('Block cache was not invalidated before readback')
    hashes=re.findall(r'(?m)^([a-f0-9]{64})\s',text)
    if hashes!=[expected.hexdigest(),sha(backup)]:raise ValueError('Card readback mismatch; preserve all evidence')
    after=adb('shell','cat /proc/sys/kernel/random/boot_id; pidof surfaceflinger system_server; sha256sum /system/framework/services.jar /vendor/lib/egl/libGLES_mali.so; cat /proc/mounts')
    save('card-after.private.json',{'invariants':after})
    if before!=after:raise ValueError('Working-system invariants changed after spare write')
    save('card-pass.json',{'image_sha256':lock['sha256'],'card_written':True,'image_range_bytes':IMAGE_BYTES,
                         'readback_sha256':expected.hexdigest(),'physical_backup_sha256':sha(backup),
                         'full_readback_pass':True,'working_system_unchanged':True,
                         'block_cache_invalidated':True,
                         'partitions_resized':False,'physical_boot_pending':True})
    print('SPARE_FULL_READBACK_AND_WORKING_SYSTEM_PASS',flush=True)

if __name__=='__main__':
    try:
        main()
    except subprocess.SubprocessError as error:
        OUT.mkdir(exist_ok=True)
        save('transport-failure.private.json',{'error':repr(error)})
        raise SystemExit('Transport stopped; private evidence retained. Inspect before any retry.') from None
