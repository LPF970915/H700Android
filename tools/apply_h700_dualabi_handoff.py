#!/usr/bin/env python3
"""Bounded P1b system/vendor deltas on the exact authorized spare; plan by default."""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
from h700_spare_guard import spare_guard

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/dualabi-bootchain-p1b-20261031'
REMOTE='/data/local/tmp/h700-dualabi-handoff-p1b-20261031'

def sha(file):
    with file.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    lock=json.loads((OUT/'handoff-lock.json').read_text(encoding='utf-8'))
    if not lock['filesystems_and_component_decompression'] or not lock['ramdisk_outside_chroot_negative_and_relative_positive']:raise ValueError('Handoff preparation incomplete')
    total=0
    for name,part,size in [('system',5,8589934592),('vendor',6,2147483648)]:
        c=lock['components'][name]
        if c['partition']!=part or c['bytes']!=size:raise ValueError('Unexpected partition geometry')
        extent=0
        for e in c['ranges']:
            if e['offset']%4096 or e['bytes']%4096 or not 0<=e['offset']<e['offset']+e['bytes']<=size:raise ValueError('Invalid patch range')
            for kind in ['old','new']:
                file=OUT/(name+'-delta')/e[kind+'_file']
                if file.parent!=OUT/(name+'-delta') or not file.is_file() or file.is_symlink() or file.stat().st_size!=e['bytes'] or sha(file)!=e[kind+'_sha256']:raise ValueError('Delta payload changed')
            extent+=e['bytes']
        if not c['ranges'] or extent>1024**2:raise ValueError('Excessive component delta')
        total+=extent
    if not args.execute:
        print('PLAN: exact original/spare CID and dynamic block-node guard; verify ALL old system/vendor blocks; write bounded deltas; uncached full8GiB+2GiB readback; original invariants. Bytes='+str(total));return
    if (OUT/'handoff-started.private.json').exists():raise ValueError('Prior handoff attempt retained; do not blindly replay')
    serial=json.loads((ROOT/'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text(encoding='utf-8'))['serial']
    cards=json.loads((ROOT/'out/dualabi-prototype-20261030/spare-card.private.json').read_text(encoding='utf-8'))['cards']['stdout']
    original=cards.split('/sys/block/mmcblk0\n')[1].splitlines()[4]
    spare=json.loads((ROOT/'out/dualabi-prototype-image-20261031/card-before.private.json').read_text(encoding='utf-8'))['cid']
    adb=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/platform-tools/adb.exe'
    if subprocess.check_output([str(adb),'-d','get-serialno']).decode().strip()!=serial:raise ValueError('USB mismatch')
    def call(*args,timeout=35):
        r=subprocess.run([str(adb),'-s',serial,*args],capture_output=True,timeout=timeout)
        if r.returncode:raise RuntimeError('ADB operation failed; preserve attempt evidence')
        return r.stdout.decode(errors='replace').replace('\r','').strip()
    guard=spare_guard(serial,original,spare,(5,6))
    file=OUT/'guard.private.sh';file.write_text(guard,encoding='utf-8',newline='\n')
    if call('shell',f'if [ -e {REMOTE} ]; then echo EXISTS; else echo NEW; fi')!='NEW':raise ValueError('Remote attempt already exists')
    call('shell',f'mkdir {REMOTE}; chmod 700 {REMOTE}')
    call('push',str(file),REMOTE+'/guard.sh')
    if call('shell','sh '+REMOTE+'/guard.sh')!='EXACT_SPARE_PARTITIONS_UNMOUNTED':raise ValueError('Spare identity/mount/node guard failed')
    invariant='cat /proc/sys/kernel/random/boot_id; pidof surfaceflinger system_server; sha256sum /system/framework/services.jar /system/app/RGSPNavigation/RGSPNavigation.apk /vendor/lib/egl/libGLES_mali.so; cat /proc/mounts'
    before=call('shell',invariant)
    (OUT/'handoff-before.private.json').write_text(json.dumps({'invariants':before,'model':call('shell','getprop ro.product.model')},indent=2),encoding='utf-8')
    script=guard+'set -o pipefail\n'
    # All target bytes and all old live blocks are checked BEFORE any mutation.
    for name in ['system','vendor']:
        c=lock['components'][name];part=c['partition']
        script+=f'blockdev --flushbufs /dev/block/mmcblk1p{part}\n'
        for i,e in enumerate(c['ranges']):
            newname=name+'-'+e['new_file'];oldname=name+'-'+e['old_file']
            call('push',str(OUT/(name+'-delta')/e['new_file']),REMOTE+'/'+newname)
            script+=f'[ "$(sha256sum {REMOTE}/{newname} | cut -d \' \' -f 1)" = {e["new_sha256"]} ]\n'
            script+=f'dd if=/dev/block/mmcblk1p{part} of={REMOTE}/{oldname} bs=4096 skip={e["offset"]//4096} count={e["bytes"]//4096}\n'
            script+=f'[ "$(sha256sum {REMOTE}/{oldname} | cut -d \' \' -f 1)" = {e["old_sha256"]} ]\n'
    script+='sh '+REMOTE+'/guard.sh\nmkdir '+REMOTE+'/write-started\n'
    for name in ['system','vendor']:
        c=lock['components'][name];part=c['partition']
        for e in c['ranges']:
            script+=f'dd if={REMOTE}/{name}-{e["new_file"]} of=/dev/block/mmcblk1p{part} bs=4096 seek={e["offset"]//4096} conv=notrunc\n'
    script+='sync\necho HANDOFF_DELTAS_WRITTEN\n'
    for name in ['system','vendor']:
        c=lock['components'][name];part=c['partition']
        script+=f'blockdev --flushbufs /dev/block/mmcblk1p{part}\necho READBACK_{name.upper()}\n'
        script+=f'dd if=/dev/block/mmcblk1p{part} bs=4194304 count={c["bytes"]//4194304} 2>/dev/null | sha256sum\n'
    file=OUT/'apply.private.sh';file.write_text(script,encoding='utf-8',newline='\n')
    call('push',str(file),REMOTE+'/apply.sh');call('shell','sh -n '+REMOTE+'/apply.sh')
    (OUT/'handoff-started.private.json').write_text(json.dumps({'revision':lock['revision'],'delta_bytes':total},indent=2),encoding='utf-8')
    print('APPLY_EXACT_SPARE_SYSTEM_VENDOR_DELTAS',total,flush=True)
    with (OUT/'apply.private.log').open('wb') as log:
        subprocess.run([str(adb),'-s',serial,'shell','-T','sh '+REMOTE+'/apply.sh'],stdout=log,stderr=subprocess.STDOUT,timeout=7200,check=True)
    text=(OUT/'apply.private.log').read_text(errors='replace')
    hashes=re.findall(r'(?m)^([a-f0-9]{64})\s',text)
    if 'HANDOFF_DELTAS_WRITTEN' not in text or hashes!=[lock['components'][n]['sha256'] for n in ['system','vendor']]:raise ValueError('Full partition readback mismatch')
    after=call('shell',invariant)
    (OUT/'handoff-after.private.json').write_text(json.dumps({'invariants':after},indent=2),encoding='utf-8')
    if before!=after:raise ValueError('Original work-system invariants changed')
    for name in ['system','vendor']:
        for e in lock['components'][name]['ranges']:
            call('pull',REMOTE+'/'+name+'-'+e['old_file'],str(OUT/(name+'-delta')/('device-'+e['old_file'])))
    result={'revision':lock['revision'],'delta_bytes':total,'system_sha256':hashes[0],'vendor_sha256':hashes[1],
            'uncached_full_partition_bytes_verified':10737418240,'original_work_system_invariants_unchanged':True,
            'userdata_gpt_kernel_boot0_not_written_by_this_patch':True,'dynamic_device_numbers_verified':True,'boot_acceptance':False}
    (OUT/'handoff-card-pass.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('P1B_SYSTEM_VENDOR_FULL_READBACK_AND_ORIGINAL_INVARIANTS_PASS',flush=True)

if __name__=='__main__':main()
