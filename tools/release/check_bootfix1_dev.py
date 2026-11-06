"""Exercise Bootfix1 device preparation in a private mount namespace only."""
from pathlib import Path
import hashlib, json, os, stat, subprocess

REPO=Path(__file__).resolve().parents[2]
WORK=Path('/home/lpf/roc-os-user-bootfix1-20261106-preflight-v1')
assert os.geteuid()==0
assert os.readlink('/proc/self/ns/mnt')!=os.readlink('/proc/1/ns/mnt'), 'Private mount namespace required'
WORK.mkdir(exist_ok=False)
helper=REPO/'tools/release/prepare_android_dev_bootfix1.sh'
entry=REPO/'tools/release/user_boot_init_bootfix1.sh'
result={'passed':False,'runtime_enforcing_accepted':False,'work':str(WORK),'cases':[],'policy':[]}
def run(args,ok=(0,)):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True)
    with (WORK/'commands.log').open('a') as f:f.write(json.dumps([str(x) for x in args])+'\n'+p.stdout+p.stderr)
    assert p.returncode in ok,(args,p.returncode,p.stdout,p.stderr)
    return p
def case(name,ids='179:5',expected=0):
    root=WORK/name;root.mkdir();(root/'dev').mkdir()
    sys=WORK/(name+'-sys')
    for n in [5,6,7]:
        f=sys/f'class/block/mmcblk7p{n}/dev';f.parent.mkdir(parents=True);f.write_text(ids+'\n' if n==5 else f'179:{n}\n')
    run(['/bin/sh',helper,root,sys,'/dev/mmcblk7p5','/dev/mmcblk7p6','/dev/mmcblk7p7'],(expected,))
    result['cases'].append({'name':name,'exit':expected})
    if expected:
        assert subprocess.run(['mountpoint','-q',root/'dev']).returncode!=0
    return root,sys
try:
    run(['/bin/sh','-n',helper]);run(['/bin/sh','-n',entry])
    box=Path('/home/lpf/roc-os-user-card-20261105-v9/busybox')
    libs='/home/lpf/roc-os-user-card-20261105-v9/boot-busybox-sysroot'
    run(['qemu-aarch64','-L',libs,box,'sh','-n',helper])
    run(['qemu-aarch64','-L',libs,box,'sh','-n',entry])
    root,sys=case('fresh')
    mount=next(l for l in Path('/proc/self/mountinfo').read_text().splitlines() if str(root/'dev') in l and ' - tmpfs ' in l)
    assert 'nosuid' in mount
    expected={'kmsg':(1,11,0o600),'random':(1,8,0o666),'urandom':(1,9,0o666),'ptmx':(5,2,0o666),'null':(1,3,0o666)}
    for name,(major,minor,mode) in expected.items():
        s=(root/'dev'/name).stat();assert stat.S_ISCHR(s.st_mode) and (os.major(s.st_rdev),os.minor(s.st_rdev),stat.S_IMODE(s.st_mode))==(major,minor,mode)
    for name in ['binder','hwbinder','vndbinder','input','.coldboot_done']:assert not (root/'dev'/name).exists()
    for name,n in [('system',5),('vendor',6),('userdata',7)]:
        assert os.readlink(root/'dev/block/by-name'/name)==f'/dev/block/mmcblk7p{n}'
        s=(root/f'dev/block/mmcblk7p{n}').stat();assert stat.S_ISBLK(s.st_mode) and (os.major(s.st_rdev),os.minor(s.st_rdev))==(179,n)
    before=(root/'dev/null').stat().st_ino
    run(['/bin/sh',helper,root,sys,'/dev/mmcblk7p5','/dev/mmcblk7p6','/dev/mmcblk7p7'],(3,))
    assert (root/'dev/null').stat().st_ino==before
    result['cases'].append({'name':'refuse_existing_mount','exit':3})
    case('invalid_id',ids='179:5:1',expected=2)
    case('non_numeric',ids='bad',expected=2)
    run(['qemu-aarch64','-L',libs,box,'mknod','-m','0600',root/'dev/arm64-null-probe','c','1','3'])
    assert stat.S_ISCHR((root/'dev/arm64-null-probe').stat().st_mode)
    result['cases'].append({'name':'actual_ARM64_BusyBox_mknod','exit':0})
    policy=REPO/'out/roc-os-user-rc1-firstboot-20261105/actual-rc1-precompiled_sepolicy'
    analyzer='/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin/sepolicy-analyze'
    probes=[('init','tmpfs','chr_file',p,True) for p in ['open','read','write','relabelfrom']]
    probes += [('init',t,'chr_file','relabelto',True) for t in ['null_device','ptmx_device','random_device','kmsg_device']]
    probes += [('ueventd','binder_device','chr_file','create',True),('init','device','chr_file','open',False),('init','device','chr_file','relabelfrom',False)]
    for domain,typ,kind,perm,allowed in probes:
        rule=f'neverallow {domain} {typ}:{kind} {perm};'
        p=run([analyzer,policy,'neverallow','-n',rule],(255 if allowed else 0,))
        result['policy'].append({'rule':rule,'allow_found':p.returncode==255})
    result['inputs']={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [helper,entry,policy]}
    result['passed']=True
finally:
    (WORK/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('BOOTFIX1_DEVICE_PREFLIGHT_PASS',flush=True)
