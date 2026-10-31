#!/usr/bin/env python3
"""Reversible API29 linker-config selection test on the exact P1b spare boot."""
import argparse,hashlib,json,os,subprocess,shlex
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/dualabi-runtime-p1c-20261031'
REMOTE='/data/local/tmp/h700-p1c-vndk29-20261031'
TARGET='/system/etc/ld.config.27.txt'
SOURCE='/system/etc/ld.config.29.txt'

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--rollback',action='store_true');args=parser.parse_args()
    overlay=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/overlay-lock.json').read_text(encoding='utf-8'))['system']
    old=overlay[TARGET]['sha256'];new=overlay[SOURCE]['sha256']
    if not args.execute:
        print('PLAN: exact P1b boot/card/USB/API identity; same init mount namespace; preserve configs; bind existing API29 config over selected27; automatic next service retry; explicit guarded rollback. No device access.');return
    OUT.mkdir(exist_ok=True)
    serial=json.loads((ROOT/'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text(encoding='utf-8'))['serial']
    cid=json.loads((ROOT/'out/dualabi-prototype-image-20261031/card-before.private.json').read_text(encoding='utf-8'))['cid']
    adb=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/platform-tools/adb.exe'
    if subprocess.check_output([str(adb),'-d','get-serialno']).decode().strip()!=serial:raise ValueError('Wrong USB transport')
    def call(*a,timeout=35):
        try:
            r=subprocess.run([str(adb),'-s',serial,*a],capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired as error:
            (OUT/'command-failure.private.json').write_text(json.dumps({'rc':'timeout','stdout':(error.stdout or b'').decode(errors='replace'),'stderr':(error.stderr or b'').decode(errors='replace')},indent=2),encoding='utf-8')
            raise RuntimeError('Prototype command timed out; inspect private receipt before retry') from None
        if r.returncode:
            (OUT/'command-failure.private.json').write_text(json.dumps({'rc':r.returncode,'stdout':r.stdout.decode(errors='replace'),'stderr':r.stderr.decode(errors='replace')},indent=2),encoding='utf-8')
            raise RuntimeError('Guarded prototype command failed; private receipt retained')
        return r.stdout.decode(errors='replace').replace('\r','').strip()
    identity=call('shell','getprop ro.serialno; cat /sys/block/mmcblk0/device/cid; getprop ro.h700.prototype; cat /system/etc/h700-prototype/boot-entry-revision; getprop ro.product.device; getprop persist.vendor.rgsp.input_profile; id -u; getprop ro.vndk.version; getprop ro.build.version.sdk; getprop ro.vendor.build.version.sdk')
    if identity.splitlines()!=[serial,cid,'rg34xxsp-dualabi-gsi10-p1-20261031','p1b-ramdisk-handoff-20261031','rgsp','rg34xxsp','0','27','29','29']:raise ValueError('Prototype/API/card identity mismatch')
    before=call('shell','cat /proc/sys/kernel/random/boot_id; readlink /proc/self/ns/mnt; readlink /proc/1/ns/mnt')
    lines=before.splitlines()
    if len(lines)!=3 or lines[1]!=lines[2]:raise ValueError('Require same init/shell mount namespace')
    if args.rollback:
        current=call('shell','sha256sum '+TARGET).split()[0]
        if current==old:print('ORIGINAL_CONFIG_ALREADY_VISIBLE');return
        if current!=new:raise ValueError('Unknown current config, no unmount')
        result=call('shell','sh '+REMOTE+'/rollback.sh')
        (OUT/'vndk29-rollback.private.json').write_text(json.dumps({'result':result},indent=2),encoding='utf-8')
        print(result);return
    if (OUT/'vndk29-bind.private.json').exists():raise ValueError('Prior bind attempt retained; inspect or rollback rather than replay')
    if call('shell','sha256sum '+TARGET).split()[0]!=old or call('shell','sha256sum '+SOURCE).split()[0]!=new:raise ValueError('Known source config changed')
    if call('shell',f'if [ -e {REMOTE} ]; then echo EXISTS; else echo NEW; fi')!='NEW':raise ValueError('Remote preservation directory exists')
    call('shell',f'mkdir {REMOTE}; chmod 700 {REMOTE}')
    for path,label in [(TARGET,'ld27.before'),(SOURCE,'ld29.source')]:call('pull',path,str(OUT/label))
    if sha(OUT/'ld27.before')!=old or sha(OUT/'ld29.source')!=new:raise ValueError('Config pull mismatch')
    if not (OUT/'ld29.source').read_text(encoding='utf-8').startswith('dir.h700bootstrap = /system/bin/h700-bootstrap/\n'):raise ValueError('Private bootstrap selector lost')
    guard=f'''[ "$(getprop ro.serialno)" = {shlex.quote(serial)} ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = {shlex.quote(cid)} ]
[ "$(getprop ro.h700.prototype)" = rg34xxsp-dualabi-gsi10-p1-20261031 ]
[ "$(cat /system/etc/h700-prototype/boot-entry-revision)" = p1b-ramdisk-handoff-20261031 ]
[ "$(id -u)" = 0 ]
'''
    rollback='set -eu\n'+guard+f'''[ "$(sha256sum {TARGET} | cut -d ' ' -f 1)" = {new} ]
awk '$5=="{TARGET}" {{found=1}} END {{exit !found}}' /proc/self/mountinfo
umount {TARGET}
[ "$(sha256sum {TARGET} | cut -d ' ' -f 1)" = {old} ]
echo VNDK27_CONFIG_RESTORED
'''
    (OUT/'vndk29-rollback.private.sh').write_text(rollback,encoding='utf-8',newline='\n')
    call('push',str(OUT/'vndk29-rollback.private.sh'),REMOTE+'/rollback.sh')
    call('push',str(OUT/'ld29.source'),REMOTE+'/ld.config.runtime.txt')
    call('shell',f'chmod 0444 {REMOTE}/ld.config.runtime.txt; chcon u:object_r:system_file:s0 {REMOTE}/ld.config.runtime.txt')
    script='set -eu\n'+guard+f'''[ "$(sha256sum {TARGET} | cut -d ' ' -f 1)" = {old} ]
[ "$(sha256sum {REMOTE}/ld.config.runtime.txt | cut -d ' ' -f 1)" = {new} ]
mount -o bind {REMOTE}/ld.config.runtime.txt {TARGET}
[ "$(sha256sum /proc/1/root{TARGET} | cut -d ' ' -f 1)" = {new} ]
echo API29_CONFIG_VISIBLE_TO_INIT
'''
    file=OUT/'vndk29-bind.private.sh';file.write_text(script,encoding='utf-8',newline='\n');call('push',str(file),REMOTE+'/bind.sh');call('shell','sh -n '+REMOTE+'/bind.sh')
    (OUT/'vndk29-bind.private.json').write_text(json.dumps({'boot_and_namespace':before,'old_sha256':old,'new_sha256':new,'attempt_started':True},indent=2),encoding='utf-8')
    result=call('shell','sh '+REMOTE+'/bind.sh')
    after=call('shell','cat /proc/sys/kernel/random/boot_id; sha256sum '+TARGET+'; getprop init.svc.surfaceflinger; getprop sys.boot_completed')
    if after.splitlines()[0]!=lines[0]:raise ValueError('Prototype rebooted during bind')
    (OUT/'vndk29-bind-result.private.json').write_text(json.dumps({'result':result,'state':after},indent=2),encoding='utf-8')
    print(result)

if __name__=='__main__':main()
