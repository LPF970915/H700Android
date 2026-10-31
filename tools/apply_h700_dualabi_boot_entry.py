#!/usr/bin/env python3
"""Apply the verified P1a system entry fix to the exact unmounted spare only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/dualabi-entry-p1a-20261031'
REMOTE='/data/local/tmp/h700-dualabi-entry-p1a-20261031'

def sha(file):
    with file.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--reuse-parent-observation',action='store_true',help='Reuse a same-session observation younger than 15 minutes; live old-block checks and final full hash remain mandatory')
    args=parser.parse_args()
    lock=json.loads((OUT/'entry-lock.json').read_text(encoding='utf-8'))
    if not all(lock[k] for k in ['first_stage_one_hop_check','filesystem_check','full_component_decompression']):raise ValueError('Entry component not verified')
    ranges=lock['ranges']
    if not ranges or sum(e['bytes'] for e in ranges)>1024**2:raise ValueError('Unexpected patch extent')
    for e in ranges:
        if e['offset']%4096 or e['bytes']%4096 or not 0<=e['offset']<e['offset']+e['bytes']<=8589934592:raise ValueError('Out-of-bounds patch range')
        for kind in ['old','new']:
            file=OUT/'delta'/e[kind+'_file']
            if file.parent!=OUT/'delta' or not file.is_file() or file.is_symlink() or file.stat().st_size!=e['bytes'] or sha(file)!=e[kind+'_sha256']:raise ValueError('Patch payload changed')
    if not args.execute:
        print('PLAN: exact old-card/USB/spare CID guard; parent system hash; verified tiny block repair if unchanged, otherwise verified system component; full 8GiB uncached readback. No device access.');return
    serial=json.loads((ROOT/'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text(encoding='utf-8'))['serial']
    cards=json.loads((ROOT/'out/dualabi-prototype-20261030/spare-card.private.json').read_text(encoding='utf-8'))['cards']['stdout']
    oldcid=cards.split('/sys/block/mmcblk0\n')[1].splitlines()[4]
    cid=json.loads((ROOT/'out/dualabi-prototype-image-20261031/card-before.private.json').read_text(encoding='utf-8'))['cid']
    if not all(re.fullmatch('[0-9a-fA-F]{32}',v) for v in [oldcid,cid]):raise ValueError('Private identity invalid')
    adb=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/platform-tools/adb.exe'
    if subprocess.check_output([str(adb),'-d','get-serialno']).decode().strip()!=serial:raise ValueError('Wrong USB transport')
    def call(*argv,timeout=35):
        r=subprocess.run([str(adb),'-s',serial,*argv],capture_output=True,timeout=timeout)
        if r.returncode:raise RuntimeError('ADB operation failed; inspect private receipts')
        return r.stdout.decode(errors='replace').replace('\r','').strip()
    guard=f'''set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.serialno)" = {shlex.quote(serial)} ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ -z "$(getprop ro.h700.prototype)" ]
[ "$(id -u)" = 0 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = {oldcid} ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = {cid} ]
[ "$(cat /sys/block/mmcblk1/size)" = 244277248 ]
[ "$(cat /sys/block/mmcblk1/mmcblk1p5/start)" = 434176 ]
[ "$(cat /sys/block/mmcblk1/mmcblk1p5/size)" = 16777216 ]
[ "$(cat /sys/block/mmcblk1/mmcblk1p5/dev)" = 179:21 ]
[ -b /dev/block/mmcblk1p5 ]
grep -q '^/dev/mmcblk0p5 / ' /proc/mounts
grep -q '^/dev/mmcblk0p7 /data ' /proc/mounts
! grep -q mmcblk1 /proc/mounts
! grep -q mmcblk1 /proc/swaps
awk '$3 ~ /^179:/ {{split($3,a,":");if(a[2]>=16&&a[2]<=31) bad=1}} END {{exit bad}}' /proc/self/mountinfo
for d in /sys/block/mmcblk1 /sys/block/mmcblk1/mmcblk1p*; do
 [ -d "$d/holders" ]
 [ -z "$(ls -A "$d/holders")" ]
done
echo EXACT_SPARE_SYSTEM_UNMOUNTED
'''
    guardfile=OUT/'entry-guard.private.sh';guardfile.write_text(guard,encoding='utf-8',newline='\n')
    if (OUT/'entry-apply-started.private.json').exists():raise ValueError('Prior repair attempt retained; inspect it rather than replay')
    if call('shell',f'if [ -e {REMOTE} ]; then echo EXISTS; else echo NEW; fi')!='NEW':raise ValueError('Remote attempt directory exists')
    call('shell',f'mkdir {REMOTE}; chmod 700 {REMOTE}')
    call('push',str(guardfile),REMOTE+'/guard.sh')
    if call('shell','sh '+REMOTE+'/guard.sh')!='EXACT_SPARE_SYSTEM_UNMOUNTED':raise ValueError('Spare guard failed')
    observation=OUT/'parent-system-hash.private.json'
    if args.reuse_parent_observation:
        if not observation.is_file() or not 0<=time.time()-observation.stat().st_mtime<=900:raise ValueError('Parent observation is not recent')
        prior=json.loads(observation.read_text(encoding='utf-8'))
    else:
        print('OBSERVE_PARENT_SYSTEM_HASH',flush=True)
        boot=call('shell','cat /proc/sys/kernel/random/boot_id')
        value=call('shell','set -eu; set -o pipefail; blockdev --flushbufs /dev/block/mmcblk1p5; dd if=/dev/block/mmcblk1p5 bs=4194304 count=2048 2>/dev/null | sha256sum',timeout=1800)
        if call('shell','cat /proc/sys/kernel/random/boot_id')!=boot:raise ValueError('Device rebooted during observation')
        prior={'rc':0,'stdout':value+'\n','boot_id':boot}
        observation.write_text(json.dumps(prior,indent=2),encoding='utf-8')
    if prior['rc']!=0:raise ValueError('Parent system observation failed')
    observed=re.findall(r'(?m)^([a-f0-9]{64})\s',prior['stdout'])
    if len(observed)!=1:raise ValueError('Missing parent system hash')
    mode='delta' if observed[0]==lock['parent_system_sha256'] else 'system-component'
    invariant='cat /proc/sys/kernel/random/boot_id; pidof surfaceflinger system_server; sha256sum /system/framework/services.jar /system/app/RGSPNavigation/RGSPNavigation.apk /vendor/lib/egl/libGLES_mali.so; cat /proc/mounts'
    before=call('shell',invariant)
    (OUT/'entry-before.private.json').write_text(json.dumps({'invariants':before},indent=2),encoding='utf-8')
    script=guard+'set -o pipefail\n'
    if mode=='delta':
        # Verify every old block before the first mutation; preserve old bytes.
        for i,e in enumerate(ranges):
            call('push',str(OUT/'delta'/e['new_file']),REMOTE+'/'+e['new_file'])
            script+=f'[ "$(sha256sum {REMOTE}/{e["new_file"]} | cut -d \' \' -f 1)" = {e["new_sha256"]} ]\n'
            script+=f'dd if=/dev/block/mmcblk1p5 of={REMOTE}/{e["old_file"]} bs=4096 skip={e["offset"]//4096} count={e["bytes"]//4096}\n'
            script+=f'[ "$(sha256sum {REMOTE}/{e["old_file"]} | cut -d \' \' -f 1)" = {e["old_sha256"]} ]\n'
        script+='mkdir '+REMOTE+'/write-started\n'
        for e in ranges:
            script+=f'dd if={REMOTE}/{e["new_file"]} of=/dev/block/mmcblk1p5 bs=4096 seek={e["offset"]//4096} conv=notrunc\n'
    else:
        image=OUT/lock['gzip_file']
        if sha(image)!=lock['gzip_sha256']:raise ValueError('System component changed')
        with (OUT/'entry-push.private.log').open('wb') as log:
            subprocess.run([str(adb),'-s',serial,'push',str(image),REMOTE+'/system.img.gz'],stdout=log,stderr=subprocess.STDOUT,timeout=3600,check=True)
        script+=f'[ "$(sha256sum {REMOTE}/system.img.gz | cut -d \' \' -f 1)" = {lock["gzip_sha256"]} ]\n'
        script+='mkdir '+REMOTE+'/write-started\n'
        script+=f'gzip -dc {REMOTE}/system.img.gz | dd of=/dev/block/mmcblk1p5 bs=4194304\n'
    script+='sync\nblockdev --flushbufs /dev/block/mmcblk1p5\necho ENTRY_WRITTEN_AND_CACHE_INVALIDATED\n'
    script+='dd if=/dev/block/mmcblk1p5 bs=4194304 count=2048 2>/dev/null | sha256sum\n'
    file=OUT/'entry-apply.private.sh';file.write_text(script,encoding='utf-8',newline='\n')
    call('push',str(file),REMOTE+'/apply.sh')
    call('shell','sh -n '+REMOTE+'/apply.sh')
    (OUT/'entry-apply-started.private.json').write_text(json.dumps({'mode':mode,'system_sha256':lock['system_sha256']},indent=2),encoding='utf-8')
    print('APPLY_SPARE_SYSTEM_ENTRY_FIX_MODE='+mode,flush=True)
    with (OUT/'entry-apply.private.log').open('wb') as log:
        subprocess.run([str(adb),'-s',serial,'shell','-T','sh '+REMOTE+'/apply.sh'],stdout=log,stderr=subprocess.STDOUT,timeout=7200,check=True)
    text=(OUT/'entry-apply.private.log').read_text(errors='replace')
    if 'ENTRY_WRITTEN_AND_CACHE_INVALIDATED' not in text or re.findall(r'(?m)^([a-f0-9]{64})\s',text)!=[lock['system_sha256']]:raise ValueError('Repaired system readback mismatch')
    after=call('shell',invariant)
    (OUT/'entry-after.private.json').write_text(json.dumps({'invariants':after},indent=2),encoding='utf-8')
    if before!=after:raise ValueError('Original work system invariants changed')
    for e in ranges:
        if mode=='delta':call('pull',REMOTE+'/'+e['old_file'],str(OUT/'delta'/('device-'+e['old_file'])))
    result={'revision':lock['revision'],'mode':mode,'partition':'spare system only','bytes_verified':8589934592,
            'system_sha256':lock['system_sha256'],'uncached_full_system_readback':True,'original_work_system_invariants_unchanged':True,
            'userdata_vendor_gpt_not_written':True,'boot_acceptance':False}
    (OUT/'entry-card-pass.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('SPARE_ENTRY_REPAIR_FULL_SYSTEM_READBACK_PASS',flush=True)

if __name__=='__main__':main()
