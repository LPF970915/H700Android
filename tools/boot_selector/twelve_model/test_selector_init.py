"""Run actual selector-init branches only in ordinary, path-rewritten fixtures.

No block node, device, mount, grow or reboot is ever opened/executed. The saved
script copy redirects every absolute device/sys/proc/grow/run path below each
new fixture; block/character predicates become regular-file predicates. Native
selector, boot-state, sleep, sync and reboot are recorded command stubs.
"""
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

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name('selector_init.sh')
PREFIX = Path('/home/lpf/roc-os-h700-shared-panel-20261114-v1/prefix.shared.raw')
BOOT = 155189248
sys.path.insert(0, str(REPO / 'tools'))
from patch_ramdisk import parse


STUB = r'''#!/usr/bin/python3
from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parent.parent
cfg=json.loads((root/'config.json').read_text())
name=Path(sys.argv[0]).name
args=sys.argv[1:]
with (root/'events.jsonl').open('a') as f:f.write(json.dumps({'name':name,'args':args})+'\n')
if name=='roc-boot-state':
    if args[:1]==['--result']:
        if cfg.get('parse_rc',0):sys.exit(cfg['parse_rc'])
        print(cfg.get('fields','model='+cfg.get('chosen','rg34xxsp')+'\nsave='+str(cfg.get('save',0))),end='\n')
        sys.exit(0)
    if len(args)<3 or args[0]!='--partition' or args[1]!=str(root/'dev/mmcblk0p3'):
        sys.exit(89)
    action=args[2]
    if action=='status':sys.exit(cfg.get('status_rc',0))
    if action=='clear-next':sys.exit(cfg.get('clear_rc',0))
    if action in ('save','once') and len(args)==4:
        sys.exit(cfg.get(action+'_rc',0))
    sys.exit(88)
if name=='roc-boot-selector':
    index_path=root/'selector-count'
    index=int(index_path.read_text()) if index_path.exists() else 0
    index_path.write_text(str(index+1))
    sequence=cfg.get('selector_rc',[0])
    code=sequence[min(index,len(sequence)-1)]
    if code==0:
        output=Path(args[args.index('--output')+1])
        output.write_text(json.dumps({'schema':2,'model_id':cfg.get('chosen','rg34xxsp'),'save_default':bool(cfg.get('save',0))}))
    sys.exit(code)
if name=='busybox':
    assert args==['reboot','-f']
    sys.exit(cfg.get('reboot_rc',77))
if name in ('sleep','sync'):sys.exit(0)
sys.exit(87)
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare_busybox(output):
    # Read only the bounded mother boot header and compressed ramdisk range.
    with PREFIX.open('rb') as stream:
        stream.seek(BOOT)
        header = stream.read(2048)
        assert header[:8] == b'ANDROID!'
        kernel, ramdisk = struct.unpack_from('<I', header, 8)[0], struct.unpack_from('<I', header, 16)[0]
        page = struct.unpack_from('<I', header, 36)[0]
        assert page == 2048 and kernel == 17686536 and 0 < ramdisk < 8*1024**2
        offset = page + ((kernel+page-1)//page)*page
        stream.seek(BOOT+offset)
        compressed = stream.read(ramdisk)
    entries = parse(gzip.decompress(compressed))
    matches = [item for item in entries if item['name'] == 'bin/busybox']
    assert len(matches) == 1
    binary = matches[0]['data']
    assert binary[:4] == b'\x7fELF'
    machine = struct.unpack_from('<H', binary, 18)[0]
    assert machine in (40,183)
    path = output / 'busybox'
    path.write_bytes(binary)
    path.chmod(0o755)
    qemu = '/usr/bin/qemu-arm' if machine == 40 else '/usr/bin/qemu-aarch64'
    assert Path(qemu).is_file()
    sysroot = output / 'mother-sysroot'
    sysroot.mkdir()
    libraries = {}
    for item in entries:
        name = item['name']
        if name == 'lib64':
            assert stat.S_ISLNK(item['mode']) and item['data'] == b'lib'
            (sysroot / 'lib64').symlink_to('lib')
            continue
        if not name.startswith('lib/') or len(Path(name).parts) != 2:
            continue
        target = sysroot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISREG(item['mode']):
            target.write_bytes(item['data'])
            target.chmod(0o755)
            libraries[name] = sha(item['data'])
        elif stat.S_ISLNK(item['mode']):
            link = item['data'].decode()
            assert not link.startswith('/') and '..' not in Path(link).parts
            target.symlink_to(link)
    runner = [qemu, '-L', str(sysroot), str(path)]
    applets = subprocess.run([*runner,'--list'],check=True,capture_output=True,text=True).stdout.splitlines()
    assert {'sh','readlink','cat','mkdir','sleep','sync','reboot'} <= set(applets)
    syntax = subprocess.run([*runner,'sh','-n',str(SOURCE)],capture_output=True,text=True)
    assert syntax.returncode == 0, syntax.stderr
    features = 'tries=0; tries=$((tries+1)); [ "$tries" -eq 1 ] || exit 9; ' \
               'while IFS= read -r row; do [ "$row" = "model=rg35xxh" ] || exit 8; done\n'
    read_test = subprocess.run([*runner,'sh','-c',features], input='model=rg35xxh\n',capture_output=True,text=True)
    assert read_test.returncode == 0
    return {'sha256': sha(binary), 'bytes':len(binary), 'elf_machine':machine,
            'qemu':qemu, 'script_n_passed':True, 'read_r_IFS_arithmetic_passed':True,
            'required_applets_present':True, 'actual_mother_libraries_sha256':libraries}, [*runner,'sh']


def run_case(base, label, config, *, model='rg34xxsp',lid='1',route='selector',
             cmdline=None, expected_rc=0, actions=(), selector_count=1,
             absent_fb=False, prior_output=False, invalid_arg=False, shell=None):
    root=base/label
    root.mkdir()
    for name in ['dev/input','sys/class/block','proc','grow','run','stubs']:
        (root/name).mkdir(parents=True,exist_ok=True)
    target=root/'sdc0/mmc_host/mmc0/mmc0:0001/block/mmcblk0'
    target.mkdir(parents=True)
    (root/'sys/class/block/mmcblk0').symlink_to(target)
    (root/'dev/mmcblk0p3').write_bytes(b'ordinary fixture; never a block node')
    if not absent_fb:(root/'dev/fb0').write_bytes(b'ordinary framebuffer fixture')
    if prior_output:(root/'run/roc-selector-result.json').write_text('{}')
    (root/'proc/cmdline').write_text(cmdline if cmdline is not None else
        f'console=ttyS0 androidboot.roc_model={model} androidboot.roc_route={route} androidboot.roc_clamshell={lid}')
    (root/'config.json').write_text(json.dumps(config))
    stub=root/'stubs/command-stub'
    stub.write_text(STUB.replace(chr(92)*2,chr(92)))
    stub.chmod(0o755)
    for name in ['roc-boot-state','roc-boot-selector','busybox','sleep','sync']:
        path=(root/'grow'/name) if name.startswith('roc-') else (root/'stubs'/name)
        path.symlink_to(stub)
    original=SOURCE.read_text()
    transformed=original.replace('export PATH=/bin:/sbin:/usr/bin:/usr/sbin',
                                  'export PATH='+str(root/'stubs')+':/bin:/sbin:/usr/bin:/usr/sbin')
    for name in ['dev','sys','proc','grow','run']:
        transformed=transformed.replace('/'+name+'/',str(root/name)+'/')
    transformed=transformed.replace('mkdir -p /run','mkdir -p '+str(root/'run'))
    transformed=transformed.replace('[ -b ', '[ -f ').replace('[ -c ', '[ -f ')
    transformed=transformed.replace('/bin/busybox reboot -f',str(root/'stubs/busybox')+' reboot -f')
    script=root/'selector-init.fixture.sh'
    script.write_text(transformed)
    for forbidden in [' /dev/',' /grow/',' /proc/',' /sys/','/bin/busybox reboot','[ -b ','[ -c ']:
        assert forbidden not in transformed, forbidden
    arg=str(root/'dev/mmcblk0') if not invalid_arg else 'invalid-TF1'
    completed=subprocess.run([*(shell or ['/bin/sh']),str(script),arg],capture_output=True,text=True,timeout=8)
    (root/'stdout.txt').write_text(completed.stdout)
    (root/'stderr.txt').write_text(completed.stderr)
    events=[json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()] if (root/'events.jsonl').exists() else []
    actual_actions=[event['args'][2] for event in events if event['name']=='roc-boot-state' and event['args'][:1]==['--partition']]
    for event in events:
        if event['name']=='roc-boot-state' and event['args'][:1]==['--partition'] and event['args'][2] in ('save','once'):
            assert event['args'][3]==config.get('chosen','rg34xxsp'), (label,event)
        if event['name']=='roc-boot-selector':
            argv=event['args']
            for key,value in [('--fb',str(root/'dev/fb0')),('--input-directory',str(root/'dev/input')),
                              ('--output',str(root/'run/roc-selector-result.json')),('--initial-model',model),
                              ('--available-models','rg34xx,rg34xxsp,rgsp,rgcubexx,rg35xxplus,rg35xx_2025,rg28xx,rg35xxh,rg40xxh,rg40xxv,rg35xxsp,rg35xxpro'),('--rotation','90' if model=='rg28xx' else '0'),('--timeout','300')]:
                assert argv[argv.index(key)+1]==value, (label,key,argv)
    count=sum(event['name']=='roc-boot-selector' for event in events)
    assert completed.returncode==expected_rc, (label,completed.returncode,completed.stdout,completed.stderr,events)
    assert actual_actions==list(actions),(label,actual_actions,actions,events)
    assert count==selector_count,(label,count,events)
    attempted_reboot=any(event['name']=='busybox' for event in events)
    assert attempted_reboot==(expected_rc==77 or config.get('reboot_rc')==0),(label,events)
    return {'case':label,'returncode':completed.returncode,'actions':actual_actions,
            'selector_calls':count,'attempted_stub_reboot':attempted_reboot,
            'sleep_calls':sum(event['name']=='sleep' for event in events),'passed':True,
            'script_sha256':sha(script.read_bytes()),'events':events}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert os.name=='posix' and not args.work.exists() and not args.output.exists()
    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True)
    source_sha=sha(SOURCE.read_bytes())
    busybox, guest_shell=prepare_busybox(args.output)
    rows=[]
    def case(label,config,**kwargs):
        rows.append(run_case(args.work,label,config,**kwargs))
    for route in ['start_once','start_saved']:
        case(route,{},route=route,actions=['status','clear-next'],selector_count=0)
        case(route+'_clear_error',{'clear_rc':5},route=route,actions=['status','clear-next'],selector_count=0,expected_rc=1)
    case('same_active_no_save',{},actions=['status','clear-next'])
    case('same_active_save',{'save':1},actions=['status','save'])
    case('same_active_35h',{'chosen':'rg35xxh','save':1},model='rg35xxh',lid='0',actions=['status','save'])
    case('different_once',{'chosen':'rg35xxh'},actions=['status','once'],expected_rc=77)
    case('different_save',{'chosen':'rgsp','save':1},actions=['status','save'],expected_rc=77)
    case('different_once_error',{'chosen':'rg35xxh','once_rc':6},actions=['status','once'],expected_rc=1)
    case('same_save_error',{'save':1,'save_rc':6},actions=['status','save'],expected_rc=1)
    case('timeouts_then_success',{'selector_rc':[3,3,0]},actions=['status','clear-next'],selector_count=3)
    case('reopened_once_same_35h',{'chosen':'rg35xxh'},model='rg35xxh',lid='0',actions=['status','clear-next'])
    case('reopened_once_clear_error',{'chosen':'rg35xxh','clear_rc':6},model='rg35xxh',lid='0',actions=['status','clear-next'],expected_rc=1)
    case('timeout_then_error',{'selector_rc':[3,7]},actions=['status'],selector_count=2,expected_rc=1)
    case('selector_error',{'selector_rc':[7]},actions=['status'],expected_rc=1)
    case('status_error',{'status_rc':9},actions=['status'],selector_count=0,expected_rc=1)
    case('parse_error',{'parse_rc':4},actions=['status'],expected_rc=1)
    for label,fields in [('bad_chosen','model=unknown\nsave=1'),('bad_save','model=rg34xxsp\nsave=2'),
                         ('extra_field','model=rg34xxsp\nsave=0\nother=x'),('duplicate_chosen','model=rgsp\nmodel=rg34xxsp\nsave=0')]:
        case(label,{'fields':fields},actions=['status'],expected_rc=1)
    case('prior_output',{},actions=['status'],expected_rc=1,selector_count=0,prior_output=True)
    case('absent_fb',{},actions=['status'],expected_rc=1,selector_count=0,absent_fb=True)
    assert rows[-1]['sleep_calls']==20
    case('invalid_tf1',{},actions=[],expected_rc=1,selector_count=0,invalid_arg=True)
    case('model_lid_mismatch',{},model='rg35xxh',lid='1',actions=[],expected_rc=1,selector_count=0)
    case('duplicate_model',{},cmdline='androidboot.roc_model=rg34xxsp androidboot.roc_model=rgsp androidboot.roc_route=selector androidboot.roc_clamshell=1',actions=[],expected_rc=1,selector_count=0)
    valid={'roc_model':'rg34xxsp','roc_route':'selector','roc_clamshell':'1'}
    for name in valid:
        others=' '.join('androidboot.'+key+'='+value for key,value in valid.items() if key!=name)
        empty='androidboot.'+name+'= '+others
        duplicate='androidboot.'+name+'= androidboot.'+name+'='+valid[name]+' '+others
        case('empty_'+name,{},cmdline=empty,actions=[],expected_rc=1,selector_count=0)
        case('empty_prefix_duplicate_'+name,{},cmdline=duplicate,actions=[],expected_rc=1,selector_count=0)
    for name in ['roc_route','roc_clamshell']:
        line=' '.join('androidboot.'+key+'='+value for key,value in valid.items())
        case('nonempty_duplicate_'+name,{},cmdline=line+' androidboot.'+name+'='+valid[name],
             actions=[],expected_rc=1,selector_count=0)
    for label,fields in [('empty_chosen','model=\nsave=0'),('empty_save','model=rg34xxsp\nsave='),
                         ('empty_prefix_duplicate_chosen','model=\nmodel=rg34xxsp\nsave=0'),
                         ('empty_prefix_duplicate_save','model=rg34xxsp\nsave=\nsave=0'),
                         ('nonempty_duplicate_save','model=rg34xxsp\nsave=1\nsave=0')]:
        case(label,{'fields':fields},actions=['status'],expected_rc=1)
    case('reboot_returned',{'chosen':'rg35xxh','reboot_rc':0},actions=['status','once'],expected_rc=1)
    # Actual mother BusyBox executes the same transformed branch copies too.
    case('guest_same_save',{'save':1},actions=['status','save'],shell=guest_shell)
    case('guest_reopened_once_same_35h',{'chosen':'rg35xxh'},model='rg35xxh',lid='0',actions=['status','clear-next'],shell=guest_shell)
    case('guest_saved_clear',{},route='start_saved',actions=['status','clear-next'],selector_count=0,shell=guest_shell)
    case('guest_different_once',{'chosen':'rg35xxh'},actions=['status','once'],expected_rc=77,shell=guest_shell)
    case('guest_timeout_then_error',{'selector_rc':[3,7]},actions=['status'],selector_count=2,expected_rc=1,shell=guest_shell)
    case('guest_empty_duplicate_model',{},cmdline='androidboot.roc_model= androidboot.roc_model=rg34xxsp androidboot.roc_route=selector androidboot.roc_clamshell=1',
         actions=[],expected_rc=1,selector_count=0,shell=guest_shell)
    case('guest_empty_duplicate_save',{'fields':'model=rg34xxsp\nsave=\nsave=0'},actions=['status'],expected_rc=1,shell=guest_shell)
    from models import ALL_MODEL_IDS, MODEL_METADATA
    for model in ALL_MODEL_IDS:
        lid=str(int(MODEL_METADATA[model]['lid']))
        for shell_id,shell in [('host',None),('mother_busybox',guest_shell)]:
            case(shell_id+'_all12_saved_'+model,{'chosen':model},model=model,lid=lid,
                 route='start_saved',actions=['status','clear-next'],selector_count=0,shell=shell)
            case(shell_id+'_all12_same_'+model,{'chosen':model},model=model,lid=lid,
                 actions=['status','clear-next'],shell=shell)
            case(shell_id+'_all12_save_'+model,{'chosen':model,'save':1},model=model,lid=lid,
                 actions=['status','save'],shell=shell)
            case(shell_id+'_all12_once_'+model,{'chosen':model},model='rg35xxh',lid='0',
                 actions=['status','clear-next'] if model=='rg35xxh' else ['status','once'],
                 expected_rc=0 if model=='rg35xxh' else 77,shell=shell)
    assert sha(SOURCE.read_bytes())==source_sha, 'Root script changed during the fixture run'
    report={'passed':True,'source_sha256':source_sha,'test_source_sha256':sha(Path(__file__).read_bytes()),
            'source':str(SOURCE),'cases':len(rows),
            'rows':rows,'mother_busybox':busybox,'physical_operations':False,
            'path_rewritten_copies_only':True,'ordinary_fixture_files_only':True,
            'actual_root_script_unchanged':True}
    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(rows),'source_sha256':source_sha,'mother_busybox':busybox}))


if __name__=='__main__':
    main()
