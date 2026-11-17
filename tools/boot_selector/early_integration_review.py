"""Read-only independent integration audit; writes a new review receipt only.

POSIX command-boundary status modelling supplements source review. It is not
execution of the original U-Boot hush parser or display hardware.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/'out/boot-selector-integration-20261114/early-integration-review-v1'
WORK=Path('/home/lpf/roc-os-h700-manual-selector-20261114-v1')
SOURCE=Path('/home/lpf/h700-android10/longan/brandy/brandy-2.0/u-boot-2018')
sys.path[:0]=[str(REPO/'tools/release'),str(REPO/'tools')]
import h700_manual_selector as manual
from h700_panel_boot import decode_env,ENV_OFFSET,ENV_SIZE
from rg35xxh_display import BOOT_OFFSET,BOOT_BYTES
from h700_panel_profiles import validate_profile


def require(value,message):
    if not value:raise ValueError(message)


def sha(blob):return hashlib.sha256(blob).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    preparation=json.loads((REPO/'out/roc-os-h700-manual-selector-20261114/preparation.json').read_text())
    require(preparation['passed'],'Parent preparation incomplete')
    with (WORK/'prefix.manual.raw').open('rb') as stream:
        stream.seek(ENV_OFFSET);environment=decode_env(stream.read(ENV_SIZE))
        stream.seek(BOOT_OFFSET);boot=stream.read(BOOT_BYTES)
    parts=manual.parts(boot)
    address=0x45000000+parts['dtb']['offset']
    require(address==0x465c2000 and address==int(preparation['integration']['kernel_dtb_address'],16),
            'Actual prepared Android v2 DTB offset differs')
    require(parts['dtb']['offset']==22814720 and parts['dtb']['bytes']==137600,
            'Actual prepared DTB layout changed')
    require(validate_profile(parts['dtb']['data'])==0,'Prepared kernel default720 profile differs')
    env=dict(environment);script=env['roc_selector_apply']
    require(script==manual.kernel_script(parts['dtb']['offset']),'Prepared environment differs from reviewed generator')
    require(env['bootcmd']=='run setargs_nand boot_normal','Unexpected original bootcmd')
    require(env['boot_normal']=='sunxi_flash read 45000000 boot && run roc_selector_apply && bootm 45000000',
            'Non-short-circuiting boot command')
    (OUT/'actual-kernel-script.txt').write_text(script+'\n')
    before=json.loads((REPO/'out/roc-os-h700-universal-rg35xxh-20261107/env-inspection.json').read_text())[0]['values']
    require(env['setargs_nand']==before['setargs_nand'] and env['setargs_mmc']==before['setargs_mmc'],
            'Existing bootargs generators changed')

    stub='''
count=0
fdt() {
  if [ "$1" = addr ]; then
    printf 'ADDR|%s\\n' "$2"
    [ "$FAIL" != addr ]; return $?
  fi
  [ "$1" = set ] || return 2
  count=$((count+1))
  printf 'CELL|%s|%s|%s\\n' "$2" "$3" "$4"
  [ "$FAIL" != "$count" ]
}
setenv() {
  printf 'ENV|%s|' "$1"
  key=$1; shift; printf '%s\\n' "$*"
  [ "$FAIL" != "$key" ] || return 1
  case "$key" in
    roc_clamshell) roc_clamshell=$1;;
    bootargs) bootargs="$*";;
    *) return 2;;
  esac
}
'''
    rows=[]
    # Shell syntax is checked independently, then failure propagation modelled
    # at command boundaries using original U-Boot source reviewed below.
    subprocess.run(['/bin/dash','-n'],input=script,text=True,check=True)
    subprocess.run(['/bin/dash','-n',str(REPO/'tools/boot_selector/selector_init.sh')],check=True)
    for model in manual.SUPPORTED:
        for route in ('selector','start_once','start_saved'):
            failures=[''] if route!='selector' else ['', 'addr', *map(str,range(1,13)), 'roc_clamshell','bootargs']
            for fail in failures:
                childenv={'PATH':'/usr/bin:/bin','roc_active_model':model,'roc_boot_route':route,
                          'bootargs':'original=preserved console=ttyS0,115200','FAIL':fail}
                run=subprocess.run(['/bin/dash','-c',stub+script+'\n'],env=childenv,text=True,capture_output=True)
                require(not run.stderr,'Unexpected shell stderr')
                lines=run.stdout.splitlines()
                cells=[line.split('|')[2:] for line in lines if line.startswith('CELL|')]
                if not fail:
                    profile=int(model=='rg35xxh');expected={'roc_panel_profile':profile,**manual.TIMINGS[profile]}
                    require(cells==[[key,'<0x'+format(value,'x')+'>'] for key,value in expected.items()],
                            'Cell quoting/order/value differs from complete selected profile')
                    expected_args='original=preserved console=ttyS0,115200 androidboot.roc_model='+model+\
                        ' androidboot.roc_clamshell='+str(int(profile==0))+' androidboot.roc_route='+route
                    require('ENV|bootargs|'+expected_args in lines and run.returncode==0,'Bootargs append/status differs')
                else:
                    require(run.returncode!=0,'Failure incorrectly returned successful apply')
                    if fail not in ('bootargs',):
                        require(not any(line.startswith('ENV|bootargs|') for line in lines),'Failed profile still appended bootargs')
                    if fail.isdigit():require(len(cells)==int(fail),'Failed FDT set did not stop remaining setters')
                rows.append({'model':model,'route':route,'failure':fail,'status':run.returncode,
                             'cells_executed':len(cells),'stdout':lines})

    # Preserve source excerpts backing U-Boot-specific interpretation.
    selected={
        'cmd/fdt.c':[(93,150),(253,306),(762,817)],
        'common/cli.c':[(121,143)],
        'common/cli_hush.c':[(1898,1931)],
        'board/sunxi/board_common.c':[(318,338),(350,391),(417,474)],
        'board/sunxi/board_helper.c':[(245,290),(418,460),(522,556)],
    }
    sources={}
    for relative,ranges in selected.items():
        data=(SOURCE/relative).read_bytes();lines=data.decode().splitlines()
        excerpt='\n'.join(str(n)+': '+lines[n-1] for first,last in ranges for n in range(first,last+1))+'\n'
        filename=relative.replace('/','__')+'.txt';(OUT/filename).write_text(excerpt)
        sources[relative]={'sha256':sha(data),'excerpt':filename,
                           'binary_build_equivalence':'source correspondence only; not established for entire binary'}
    original=(REPO/'out/roc-os-h700-universal-rg35xxh-20261107/toc/16793600-u-boot.bin').read_bytes()
    def cstring(pointer):return original[pointer-0x4a000000:].split(b'\0',1)[0].decode()
    actual_recovery_strings={hex(off):cstring(struct.unpack_from('<I',original,off)[0])
                             for off in (0x3494,0x3498,0x349c)}
    early=json.loads((REPO/'out/rg34xx-boot-analysis-20261114/early-fdt-at-17954816.json').read_text())
    recovery=early['/soc@03000000/key_boot_recovery/recovery_key']
    volume=early['/soc@03000000/gpio_keys/keyvol-/gpios']
    require(recovery[1:3]==[7,9] and volume[1:3]==[4,2], 'GPIO recovery conflicts with bootstrap PE2')
    require(not any('/recovery_key/' in key or '/fastboot_key/' in key for key in early),
            'Unreviewed LRADC recovery/fastboot range present')
    boot0=REPO/'out/rg34xx-boot-analysis-20261114/boot0-at-8192.bin'
    b0=boot0.read_bytes()
    require(sha(b0)=='50e31b5a9734e95ad98af769cfe53cdbed84e02db2f70d4de75a8ed98bc81ace','Pinned boot0 differs')
    for name,start,end,thumb,path,base in [
        ('boot0_uart_key',0x22934,0x22a18,True,boot0,0x20000),
        ('boot0_rtc_fel',0x22cac,0x22d20,True,boot0,0x20000),
        ('uboot_actual_arm_relocation_loop',0x4a00136c,0x4a0013d4,False,
          REPO/'out/roc-os-h700-universal-rg35xxh-20261107/toc/16793600-u-boot.bin',0x4a000000)]:
        args=['arm-linux-gnueabihf-objdump','-D','-b','binary','-m','arm']
        if thumb:args+=['-Mforce-thumb']
        args+=['--adjust-vma='+hex(base),'--start-address='+hex(start),'--stop-address='+hex(end),str(path)]
        (OUT/(name+'.txt')).write_text(subprocess.check_output(args,text=True))
    # Original relocation values must not target the new cave, either.
    pointer_references=[]
    for at in range(0xe6450,0xfdaa0,8):
        cell,kind=struct.unpack_from('<II',original,at)
        value=struct.unpack_from('<I',original,cell-0x4a000000)[0]&~1
        if 0x4a026500<=value<0x4a0268a0:pointer_references.append(hex(cell))
    require(not pointer_references,'Original dynamic relocation value enters reclaimed hook cave')
    result={'passed':True,'scope':'read-only independent integration source review plus POSIX API/status model',
            'actual_uboot_hush_executed':False,'physical_bootstrap_accepted':False,
            'actual_prepared_kernel_dtb_offset':parts['dtb']['offset'],'actual_prepared_kernel_dtb_address':hex(address),
            'actual_prepared_dtb_sha256':sha(parts['dtb']['data']),
            'kernel_script_sha256':sha(script.encode()),'modelled_command_boundary_cases':len(rows),
            'setargs_nand_and_mmc_preserved':True,
            'failure_prevents_bootm_via_source_review':True,
            'kernel_fdt_transaction':'12 same-size setters; failure can leave earlier RAM cells changed but && refuses bootm; no partially configured kernel handoff',
            'early_display_order':'original clocks retained; first display deferred until env/profile; pre-env early logo suppressed; board_late logo runs after bridge and does not reapply numeric panel geometry in reviewed source',
            'gpio_bootstrap':{'actual_pre_env_recovery_strings':actual_recovery_strings,
                             'recovery_gpio':'PH9','bootstrap_volume_down_gpio':'PE2',
                             'saved_recovery_config':recovery,'saved_volume_config':volume,
                             'lr_adc_recovery_fastboot_range_nodes':'absent in pinned actual early FDT',
                             'boot0_key_press_path':'actual Thumb reads UART0 0x05000000 RX/LSR, not PE2',
                             'boot0_explicit_fel_path':'actual Thumb tests RTC 0x07000108 magic',
                             'boundary':'no PE2 conflict found in inspected original software; BROM and physical held-key acceptance remain unverified'},
            'original_relocation_values_enter_new_cave':pointer_references,
            'supersedes_early_audit_v1':{'explicit35H_Test2_failure':'not established: user flashed default720 gzip; do not call selected35H physically failed',
                                       'relocation_loop_disassembly':'old forced-Thumb dump invalid for ARM loop; corrected ARM dump included'},
            'sources':sources,'cases':rows}
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','sources')},ensure_ascii=False))


if __name__=='__main__':main()
