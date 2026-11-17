"""Execute the composed early helper with real mother BusyBox on ordinary files.

No host swap syscall: the command boundary intercepts every swapon/swapoff.
Creation uses an 8MiB scaled constant; an independent sparse 2GiB file only
checks mkswap's real 64-bit header handling, never usable swap allocation.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AUDIT = REPO / 'out/memory-swap-20261117/boot-audit-v3'
WORK = Path('/home/lpf/roc-os-h700-swap-fixtures-20261117-v2')
OUT = REPO / 'out/memory-swap-20261117/helper-tests-v2'
SCALE = 8 * 1024**2

BOUNDARY = r'''#!/usr/bin/python3
from pathlib import Path
import json,os,subprocess,sys,time
case=Path(__file__).resolve().parent
cfg=json.loads((case/'config.json').read_text())
args=sys.argv[1:]
with (case/'events.jsonl').open('a') as stream:stream.write(json.dumps(args)+'\n')
command=args[0]
if command=='swapoff':sys.exit(98)
if command=='swapon':
    assert len(args)==2 and args[1]==str(case/'root/data/roc-swap/swapfile-2g')
    if cfg.get('swapon_fail'):sys.exit(1)
    with (case/'swaps').open('a') as stream:stream.write(args[1]+' file 8188 0 -1\n')
    sys.exit(0)
if command=='sync':sys.exit(1 if cfg.get('sync_fail') else 0)
if command=='df':
    print('Filesystem 1024-blocks Used Available Capacity Mounted on')
    print('/dev/fixture 999999 100 '+str(cfg.get('free_kib',999999))+' 1% '+str(case/'root/data'))
    sys.exit(0)
if command=='mkswap' and cfg.get('mkswap_fail'):sys.exit(1)
if command=='dd' and any(x.startswith('of=') for x in args):
    if cfg.get('dd_fail'):sys.exit(1)
    if cfg.get('dd_slow'):time.sleep(20)
    if cfg.get('dd_short'):args=[('count=1' if x.startswith('count=') else x) for x in args]
os.execv('/usr/bin/qemu-aarch64',['/usr/bin/qemu-aarch64','-L',cfg['sysroot'],cfg['busybox']]+args)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) <= {0, 1}
    WORK.mkdir(exist_ok=False)
    OUT.mkdir(parents=True, exist_ok=False)
    audit = json.loads((AUDIT / 'result.json').read_text())
    assert audit['passed'] is True
    box, sysroot = Path(audit['busybox_path']), Path(audit['sysroot'])
    assert sha(box) == audit['busybox_sha256']
    command = ['/usr/bin/qemu-aarch64', '-L', str(sysroot), str(box)]
    source = (HERE / 'h700_optional_axes.sh').read_text()
    # Only fixture paths, byte counts, deadline and expected fixture UID/GID
    # change. The production source and every branch remain unchanged.
    transformed = source.replace('swap_bytes=2147483648', 'swap_bytes='+str(SCALE)).replace(
        'swap_blocks=2048', 'swap_blocks=8').replace('swap_usable_kib=2097148', 'swap_usable_kib=8188').replace(
        'swap_last_page=524287', 'swap_last_page=2047').replace('swap_required_kib=2621440', 'swap_required_kib=12288').replace(
        'swap_timeout=300', 'swap_timeout=1').replace("swap_owner='0 0'", "swap_owner='%d %d'" % (os.geteuid(), os.getegid()))
    assert source != transformed
    rows = []

    def case(name, setup=None, expected_calls=0, **cfg):
        root = WORK / name
        (root / 'root/data').mkdir(parents=True)
        (root / 'swaps').write_text('Filename Type Size Used Priority\n')
        mounts = '/dev/fixture '+str(root/'root/data')+' '+cfg.get('filesystem','ext4')+' '+cfg.get('mount_flags','rw,noatime')+' 0 0\n'
        (root / 'mounts').write_text(mounts)
        (root / 'modules').write_text('')
        (root / 'cmdline').write_text('androidboot.roc_model='+cfg.get('model','rgsp')+' androidboot.roc_sticks='+cfg.get('sticks','0'))
        (root / 'config.json').write_text(json.dumps({'busybox':str(box),'sysroot':str(sysroot),**cfg}))
        boundary = root / 'busybox-boundary'
        boundary.write_text(BOUNDARY)
        boundary.chmod(0o755)
        script = root / 'helper.sh'
        script.write_text(transformed.replace('swap_proc=/proc/swaps', 'swap_proc='+str(root/'swaps')).replace(
            'swap_mounts=/proc/mounts', 'swap_mounts='+str(root/'mounts')))
        if setup:setup(root)
        started = time.monotonic()
        result = subprocess.run(command + ['sh', str(script), str(root/'root'), str(root/'modules'), str(boundary),
                                 '4.9.170', str(root/'cmdline'), str(root/'sysmodules')], capture_output=True, text=True, timeout=18)
        assert result.returncode == 0, (name,result.stdout,result.stderr)
        assert '[h700-input]' in result.stdout, (name,result.stdout,result.stderr)
        events = [json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]
        calls = [e for e in events if e[0] == 'swapon']
        assert len(calls) == expected_calls, (name,calls,result.stdout,result.stderr)
        assert not any(e[0]=='swapoff' for e in events)
        output = OUT / (name+'.txt')
        output.write_text(result.stdout+result.stderr)
        row = {'name':name,'passed':True,'swapon_calls_mocked':len(calls),
               'normal_input_helper_continued':True,'elapsed_seconds':time.monotonic()-started}
        rows.append(row)
        return root, events, row

    first, events, _ = case('first_create_zero_stick', expected_calls=1)
    final = first/'root/data/roc-swap/swapfile-2g'
    assert final.stat().st_size == SCALE and stat.S_IMODE(final.stat().st_mode)==0o600
    assert final.stat().st_blocks*512 >= SCALE
    assert final.read_bytes()[4086:4096] == b'SWAPSPACE2'
    assert not final.with_name('swapfile-2g.new').exists()
    write = [e for e in events if e[0]=='dd' and any(x.startswith('of=') for x in e)]
    assert len(write)==1 and 'conv=fsync' in write[0] and 'count=8' in write[0]
    assert not any(x.startswith('seek=') for x in write[0])
    def seed(root):
        directory=root/'root/data/roc-swap';directory.mkdir(mode=0o700)
        shutil.copyfile(final,directory/'swapfile-2g');(directory/'swapfile-2g').chmod(0o600)
    def noformat(events):
        assert not any(e[0]=='mkswap' or e[0]=='dd' and any(x.startswith('of=') for x in e) for e in events)
    reused, events, _ = case('reuse_without_reformat',seed,expected_calls=1)
    noformat(events)
    def active(root):
        seed(root);(root/'swaps').write_text(str(root/'root/data/roc-swap/swapfile-2g')+' file 8188 0 -1\n')
    _, events, _ = case('already_active',active)
    noformat(events)
    def active_small(root):
        seed(root);(root/'swaps').write_text(str(root/'root/data/roc-swap/swapfile-2g')+' file 60 0 -1\n')
    _,events,_=case('active_smaller_swap_preserved',active_small);noformat(events)
    def header_small(root):
        seed(root)
        with (root/'root/data/roc-swap/swapfile-2g').open('r+b') as stream:
            stream.seek(1028);stream.write(struct.pack('<I',15))
    _,events,_=case('smaller_header_rejected',header_small);noformat(events)
    case('free_space_guard',free_kib=12287)
    case('different_filesystem',filesystem='f2fs')
    case('readonly_data',mount_flags='ro')
    case('dd_error',dd_fail=True)
    short,events,_=case('dd_short_write',dd_short=True)
    assert not any(e[0]=='mkswap' for e in events)
    timed,events,row=case('dd_creation_deadline',dd_slow=True)
    assert row['elapsed_seconds'] < 12 and any(e[:2]==['kill','-KILL'] for e in events)
    case('mkswap_error',mkswap_fail=True)
    case('sync_error',sync_fail=True)
    failed,_,_=case('swapon_error_nonfatal',expected_calls=1,swapon_fail=True)
    assert (failed/'root/data/roc-swap/swapfile-2g').is_file()
    def wrongsize(root):
        seed(root);(root/'root/data/roc-swap/swapfile-2g').write_bytes(b'invalid')
    wrong,events,_=case('wrong_size_preserved',wrongsize)
    noformat(events);assert (wrong/'root/data/roc-swap/swapfile-2g').read_bytes()==b'invalid'
    def badmode(root):seed(root);(root/'root/data/roc-swap/swapfile-2g').chmod(0o644)
    _,events,_=case('wrong_mode_preserved',badmode);noformat(events)
    def hardlink(root):seed(root);os.link(root/'root/data/roc-swap/swapfile-2g',root/'elsewhere')
    _,events,_=case('hardlink_preserved',hardlink);noformat(events)
    def finalsymlink(root):
        directory=root/'root/data/roc-swap';directory.mkdir(mode=0o700)
        (root/'elsewhere').write_bytes(b'keep');(directory/'swapfile-2g').symlink_to(root/'elsewhere')
    linked,events,_=case('final_symlink_preserved',finalsymlink);noformat(events)
    assert (linked/'elsewhere').read_bytes()==b'keep'
    def stagesymlink(root):
        directory=root/'root/data/roc-swap';directory.mkdir(mode=0o700)
        (root/'elsewhere').write_bytes(b'keep');(directory/'swapfile-2g.new').symlink_to(root/'elsewhere')
    linked,events,_=case('stage_symlink_preserved',stagesymlink);noformat(events)
    assert (linked/'elsewhere').read_bytes()==b'keep'
    def stageactive(root):
        directory=root/'root/data/roc-swap';directory.mkdir(mode=0o700)
        stage=directory/'swapfile-2g.new';stage.write_bytes(b'keep');stage.chmod(0o600)
        (root/'swaps').write_text(str(stage)+' file 8188 0 -1\n')
    active_stage,events,_=case('active_stage_preserved',stageactive);noformat(events)
    assert (active_stage/'root/data/roc-swap/swapfile-2g.new').read_bytes()==b'keep'
    assert not any(e[0]=='rm' for e in events)
    def stale(root):
        directory=root/'root/data/roc-swap';directory.mkdir(mode=0o700)
        stage=directory/'swapfile-2g.new';stage.write_bytes(b'incomplete');stage.chmod(0o600)
    _,events,_=case('interrupted_stage_recreated',stale,expected_calls=1)
    assert any(e[0]=='rm' for e in events)
    case('two_stick_model_still_gets_swap',expected_calls=1,model='rg35xxh',sticks='2')
    # Actual mkswap verifies the 2GiB boundary with no full disk allocation.
    large=WORK/'header-only-2g.fixture'
    with large.open('wb') as stream:stream.truncate(2147483648)
    complete=subprocess.run(command+['mkswap',str(large)],capture_output=True,text=True,check=True)
    with large.open('rb') as stream:header=stream.read(4096)
    assert header[4086:4096]==b'SWAPSPACE2'
    assert struct.unpack_from('<II',header,1024)==(1,524287)
    (OUT/'actual-mkswap-2g-header.txt').write_text(complete.stdout+complete.stderr)
    controls={str(p):sha(p) for p in (HERE/'h700_optional_axes.sh',HERE/'swap_prefix.sh',HERE/'compose.py',Path(__file__),
        REPO/'tools/input_profiles/stick_sampling_v2/h700_optional_axes.sh',AUDIT/'result.json',AUDIT/'kernel-evidence.json',
        AUDIT/'init.test8.sh',AUDIT/'applets.txt',AUDIT/'busybox',HERE/'audit_boot.py',HERE/'composition.json')}
    kernel=json.loads((AUDIT/'kernel-evidence.json').read_text())
    controls.update(kernel['retained_source_controls'])
    controls[kernel['config_path']]=kernel['config_sha256']
    for p in sysroot.rglob('*'):
        if p.is_file() and not p.is_symlink():controls[str(p)]=sha(p)
    receipt={'schema':'roc.h700.swap2g-host.v1','passed':True,'swap_bytes':2147483648,'default_enabled':True,
        'physical_acceptance':False,'actual_host_swapon':False,'helper_sha256':sha(HERE/'h700_optional_axes.sh'),
        'reuse_size_or_space_guard':True,'failure_nonfatal':True,'no_RAM_identity_gate':True,
        'kernel_evidence':{'path':str(AUDIT/'kernel-evidence.json'),'sha256':sha(AUDIT/'kernel-evidence.json')},
        'busybox_evidence':{'path':str(AUDIT/'result.json'),'sha256':sha(AUDIT/'result.json')},
        'controls':controls,'cases':len(rows),'rows':rows,'scaled_creation_bytes':SCALE,
        'real_mkswap_exact_2GiB_header':True,'mkswap_2GiB_fixture_sparse_not_usable_swap':True,
        'free_space_and_swapon_and_sync_mocked':True,'data_files_and_dd_fsync_and_mkswap_real':True,
        'fixture_owner_uid_gid_substituted':True,'production_create_timeout_seconds':300,
        'deadline_scope':'dd wait only; no strict total IO deadline or D-state termination guarantee',
        'boot_or_device_changed':False}
    (OUT/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('controls','rows')},indent=2))


if __name__=='__main__':main()
