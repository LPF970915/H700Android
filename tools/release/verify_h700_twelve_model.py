"""Independent Test8 whole-card verifier; ordinary files only.

The producer/integrator is not imported. The complete published gzip is expanded
to a fresh sparse raw, compared to the producer raw byte-for-byte, and every
range is hashed. Prefix structures and all filesystem payload/metadata changes
are independently inspected against the fixed, accepted Test7 parent.
"""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import json
import os
import re
import shlex
import stat
import struct
import subprocess
import sys
import time
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from verify_h700_navigation_test6 import metadata_inventory, parse_metadata

NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img'
BASE = Path('/home/lpf/roc-os-h700-manual-selector-test7-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test7_BootHandoff_20261116.img')
BASE_SHA = '8f7ffefdf4c2437ece46462b21315ccba15b57926adef2fd46c3eb3fe2c647c4'
ACCEPTANCE = REPO / 'out/roc-os-h700-manual-selector-test7-20261116/acceptance.json'
ACCEPTANCE_SHA = '2e4714d91951b6f6dd46edb736b86adc9b50b2da5d5bfc71661ea2557de4acdb'
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
RAW_BYTES = 32434554368
RANGES = {'prefix': (0, 222298112), 'system': (222298112, 8589934592),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
PARENT_SHA = {'prefix':'3cf8eb9ea03ce7ce7902aec56911507bdbfc09549f533226ffe78494e9970807',
    'system':'6ab9b9423f2cf21f365d9e028d37f7311a678f220645cadbd7f1ba491a9ca59a',
    'vendor':'bcf0706cd474b54b7f908aa234100a352773e0d603a11f4fa00787079e0f6fa0',
    'userdata':'637a02240df99491b9616503c69cd41638b7604c927675762e640014b3cd7d86',
    'backup_gpt':'ba9ba2c16fbb57653f2d5b221bb2f0c2ee698550f1d9dc33df30b5565d23c5dc'}
TOC_START, TOC_BYTES = 16793600, 1310720
ENV_START, ENV_BYTES = 138412032, 131072
BOOT_START, BOOT_BYTES = 155189248, 67108864
PANEL = '/soc@03000000/lcd0@01c0c000'
CERT = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
LID = '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk'
RC = '/system/etc/init/roc-model-display.rc'
MODULE, LOADER = '/modules/h700_stick_axes.ko', '/bin/rgsp-stick-axes.sh'
NAV = '/system/app/ROCNavigation/ROCNavigation.apk'
FRAMEWORK = '/system/framework/framework.jar'
NAV_SHA = '8b3227dc5db5d3fa79a6d99d26647f4c2746f4ecd864609f0d23a29ff61c55d8'
FRAMEWORK_SHA = '60ab589c7f638dd03954dc379d614ee5ca3242bf0708aec7cd88c578c0f4c8e0'
NATIVE = Path('/home/lpf/h700-android10/android')
SDK_PINS = {
    'prebuilts/jdk/jdk9/linux-x86/bin/java': '0fc49ba9e906db74a7d3cb0b4a44b9e0916e1e487b45431c0cb7ed281cd7ef65',
    'prebuilts/sdk/tools/linux/bin/zipalign': '7c4efc4f8b3c7454f42473f653b758200a68dac4ed79df37c1d4b8661c83887f',
    'prebuilts/sdk/tools/linux/lib/apksigner.jar': 'b9b61b17a11523da8e10e454f35ef1093397014e22b67323576816456e64537c',
}
MODELS = {
    'rg34xx': (2,0,0,'landscape',720,480,720,480,0),
    'rg34xxsp': (0,1,2,'clamshell',720,480,720,480,0),
    'rgsp': (0,1,0,'clamshell',720,480,720,480,0),
    'rgcubexx': (3,0,2,'landscape',720,720,720,720,0),
    'rg35xxplus': (4,0,0,'portrait',640,480,640,480,0),
    'rg35xx_2025': (4,0,0,'portrait',640,480,640,480,0),
    'rg28xx': (5,0,0,'landscape',480,640,640,480,90),
    'rg35xxh': (1,0,2,'landscape',640,480,640,480,0),
    'rg40xxh': (6,0,2,'landscape',640,480,640,480,0),
    'rg40xxv': (7,0,1,'portrait',640,480,640,480,0),
    'rg35xxsp': (8,1,0,'clamshell',640,480,640,480,0),
    'rg35xxpro': (9,0,2,'portrait',640,480,640,480,0),
}
PROPS = ('lcd_x','lcd_y','lcd_dclk_freq','lcd_hbp','lcd_ht','lcd_hspw',
         'lcd_vbp','lcd_vt','lcd_vspw','lcd_hv_clk_phase','lcd_hv_sync_polarity','lcd_frm')
TIMINGS = (
    (720,480,26,46,820,2,20,536,5,1,3,1),
    (640,480,24,46,770,20,15,520,4,2,3,1),
    (720,480,26,46,820,2,20,536,5,1,3,1),
    (720,720,48,46,1060,2,20,755,5,0,0,1),
    (640,480,24,46,770,20,15,520,4,2,3,1),
    (480,640,24,56,586,6,26,686,6,0,0,0),
    (640,480,24,46,770,20,15,522,4,2,3,1),
    (640,480,24,46,770,20,15,522,4,2,3,1),
    (640,480,48,48,1414,8,48,566,4,2,3,1),
    (640,480,24,46,770,20,14,528,4,2,3,1),
)
REQUIRED = {'module','input_receipt','early_helper','android_loader','menu',
            'menu_receipt','selector_hook','selector_receipt','early_uboot','early_receipt',
            'kernel','panel_receipt','lid','lid_receipt','display_rc',
            'boot_state','boot_state_receipt','native_start_receipt'}
PREVIEW_MODELS = ('rg35xxh','rg34xxsp','rgcubexx')


def check(value, reason):
    if not value: raise ValueError(reason)


def ordinary(path):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts and
          (path.is_relative_to(Path('/home/lpf')) or path.is_relative_to(REPO)),
          'Ordinary workspace path required: '+str(path))
    check(all(not p.is_symlink() for p in (path,*path.parents)), 'Symlink path rejected: '+str(path))
    check(stat.S_ISREG(path.lstat().st_mode), 'Regular file required: '+str(path))
    return path


def digest(data): return hashlib.sha256(data).hexdigest()


def sha(path):
    with ordinary(path).open('rb') as reader: return hashlib.file_digest(reader,'sha256').hexdigest()


def read_json(path): return json.loads(ordinary(path).read_text())


def write_json(path,value): Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def fresh(path):
    path=Path(path)
    check(path.is_absolute() and '..' not in path.parts and
          (path.is_relative_to(Path('/home/lpf')) or path.is_relative_to(REPO)), 'Fresh workspace path required')
    check(not path.exists() and all(not p.is_symlink() for p in path.parents), 'Fresh non-symlink path required')
    return path


def receipt_controls(receipt, label, required=()):
    """Bind proof inputs at their recorded paths, including non-repository tools."""
    values=receipt.get('controls')
    check(isinstance(values,dict) and values,'Missing tested controls: '+label)
    canonical={}
    for name,value in values.items():
        path=Path(name)
        if not path.is_absolute():path=REPO/path
        path=ordinary(path)
        check(str(path) not in canonical and sha(path)==value,
              'Changed/duplicate tested control: '+label+':'+str(path))
        canonical[str(path)]=value
    for path in required:
        path=ordinary(path)
        check(canonical.get(str(path))==sha(path),'Untested required control: '+label+':'+str(path))
    return canonical


def unique_cases(rows, fields, label):
    check(isinstance(rows,list) and rows,'Missing execution cases: '+label)
    result={}
    for row in rows:
        check(row.get('passed',row.get('pass')) is True,'Failed execution case: '+label)
        key=tuple(row[field] for field in fields)
        check(key not in result,'Duplicate execution case: '+label+':'+str(key))
        result[key]=row
    return result


def loading_receipt_bindings(menu, selector):
    """Require the tested loading paths as part of the delivered components."""
    check(menu.get('loading_text')=='加载中，请稍后' and
          menu.get('loading_only_has_no_input_or_result') is True,
          'Native component lacks the agreed framebuffer-only loading path')
    check(menu['selection']=={'schema':2,'model_id':'rg35xxh','save_default':True},
          'Native confirmed-menu loading comparison is not bound')
    check(set(menu['previews'])=={
        f'{kind}-{geometry}.ppm' for kind in ('menu','loading')
        for geometry in ('640x480','720x480','720x720','480x640')},
        'Incomplete native loading/menu geometry coverage')
    check(menu['loading_only_models']==12,'Incomplete native loading model count')
    loading=unique_cases(menu['loading_only_cases'],('architecture','model'),'native loading')
    check(set(loading)=={(architecture,model) for architecture in ('host','aarch64') for model in MODELS},
          'Incomplete actual host/AArch64 loading model topology')
    for model,metadata in MODELS.items():
        host=loading['host',model];arm=loading['aarch64',model]
        for row in (host,arm):
            check(row['native_size']==list(metadata[4:6]) and row['rotation']==metadata[-1] and
                  row['no_input_or_selection_arguments'] is True,
                  'Loading model geometry/input scope changed: '+model)
        check(host['ppm_sha256']==arm['ppm_sha256'],'Actual host/AArch64 loading frame mismatch: '+model)
    rejections=set()
    for row in menu['loading_only_rejections']:
        command=row['command']
        check(row['pass'] is True and isinstance(command,list), 'Loading-only negative control failed')
        if len(command)==1: architecture='host'
        else:
            check(len(command)==2 and command[0]=='/usr/bin/qemu-aarch64',
                  'Unexpected loading-only negative-control runner')
            architecture='aarch64'
        key=(architecture,row['forbidden'])
        check(key not in rejections,'Duplicate loading-only negative control')
        rejections.add(key)
    check(rejections=={(architecture,argument) for architecture in ('host','aarch64')
                      for argument in ('--output','--input-directory','--inputs')},
          'Incomplete loading-only input/result rejection controls')
    check(selector.get('loading_frame_has_no_input_or_result') is True and
          selector.get('loading_failures_do_not_block_android') is True and
          selector.get('physical_operations') is False and
          selector.get('path_rewritten_copies_only') is True and
          selector.get('ordinary_fixture_files_only') is True,
          'Selector loading fixture scope or behavior is incomplete')
    test=REPO/'tools/boot_selector/twelve_model/test_selector_init_rescue.py'
    check(selector['test_source_sha256']==sha(test),'Loading fixture tested source changed')
    rows={}
    check(selector['cases']==len(selector['rows']),'Loading fixture case count mismatch')
    for row in selector['rows']:
        check(row['passed'] is True and row['case'] not in rows,'Failed/duplicate selector fixture')
        rows[row['case']]=row
    for architecture in ('host','mother_busybox'):
        for model,metadata in MODELS.items():
            for route in ('saved','once_loading'):
                row=rows.get(f'{architecture}_all12_{route}_{model}')
                check(row is not None and row['returncode']==0 and
                      row['actions']==['status','clear-next'] and row['selector_calls']==0 and
                      row['loading_only_calls']==1 and row['attempted_stub_reboot'] is False and
                      row['sleep_calls']==0,'Missing saved/once loading fixture: '+model)
                events=row['events']
                check([e['name'] for e in events]==['roc-boot-state','roc-boot-state','roc-boot-selector'],
                      'Saved/once loading path performs unexpected work: '+model)
                argv=events[-1]['args']
                check(len(argv)==5 and argv[:2]==['--loading-only','--fb'] and
                      argv[3:]==['--rotation',str(metadata[-1])],
                      'Saved/once loading path reads input or uses wrong orientation: '+model)
    for route in ('start_once','start_saved'):
        for suffix,loading,sleeps in (('loading_error_continues',1,0),
                                       ('loading_absent_fb_continues',0,20)):
            row=rows.get(route+'_'+suffix)
            check(row is not None and row['returncode']==0 and
                  row['actions']==['status','clear-next'] and row['selector_calls']==0 and
                  row['loading_only_calls']==loading and row['sleep_calls']==sleeps and
                  row['attempted_stub_reboot'] is False,
                  'Loading failure unexpectedly blocks Android: '+route)


def early_preview_bindings(early, receipt_path, artifact):
    check(early.get('manual_panel_recovery') is True and early.get('preview_next_start')=='2' and
          early.get('preview_returns_to_selector') is True and
          early['persistent_environment_writes'] is False and early['automatic_profile_probe'] is False and
          early['timing_row_u32_cells']==13 and early['all_original_relocations']==11978 and
          early['early_clock_init_preserved'] is True and early['first_display_after_environment'] is True,
          'Incomplete early preview/control-FDT semantics')
    check(early['preview_ui_representatives']==list(PREVIEW_MODELS) and
          set(early['preview_canonical_models'])==set(MODELS) and
          early['supported_profiles']=={model:metadata[0] for model,metadata in MODELS.items()},
          'Early preview/model catalog differs from the independent twelve-model intent')
    receipt_controls(early,'early preview',(
        REPO/'tools/boot_selector/twelve_model/early_profile_bridge_rescue.py',
        REPO/'tools/boot_selector/twelve_model/early_profile_bridge_rescue.S',
        REPO/'tools/boot_selector/twelve_model/models.py',
        REPO/'tools/boot_selector/reference_model.py'))
    check(sha(artifact)==early['patched_sha256'],'Early preview artifact changed')
    path=ordinary(receipt_path.parent/'execution.json')
    check(sha(path)==early['execution_sha256'],'Early preview execution receipt changed')
    execution=read_json(path)
    check(execution['passed'] is True and early['host_cases']==len(execution['cases']),
          'Incomplete early preview execution case count')
    rows={}
    for row in execution['cases']:
        key=(row['case'],row['slide'])
        check(key not in rows and row['slide'] in (0,0x1000000),'Duplicate/unrecognized early machine case')
        rows[key]=row
    for model,metadata in MODELS.items():
        for slide in (0,0x1000000):
            for prefix,route in (('saved_','start_saved'),('saved_hotkey_','selector'),
                                 ('next_','start_once'),('next_hotkey_','selector'),
                                 ('preview_','selector'),('preview_hotkey_','selector')):
                row=rows.get((prefix+model,slide))
                check(row is not None and row['sets']=={'roc_active_model':model,'roc_boot_route':route}
                      and row['profile_values']==[metadata[0],*TIMINGS[metadata[0]]] and row['r0']==0
                      and row['SP_callee_saved_r9'] is True and row['relocation_records']==11978,
                      'Missing/incorrect original or preview early route: '+prefix+model)
                if prefix.startswith('preview'):
                    check(row['env']['roc_next_start']=='2' and row['env']['roc_next_model']==model
                          and row['env']['roc_saved_model']!=model,
                          'Preview must override a conflicting saved default without writing it: '+model)
    return {'path':str(path),'sha256':sha(path),'preview_models':list(PREVIEW_MODELS),
            'all12_preview_routes_on_two_slides':True,'saved_and_once_routes_retained':True}


def native_start_bindings(receipt, receipt_path, menu, menu_receipt_path, artifact):
    check(receipt['passed'] is True and receipt['cases']==24 and
          receipt['all12_actual_native_start'] is True and receipt['actual_host_and_aarch64'] is True and
          receipt['hardware_accessed'] is False and receipt['simulation_only'] is True and
          receipt['loading_text']=='加载中，请稍后','Incomplete final host/AArch64 Start execution')
    receipt_controls(receipt,'actual native Start',(
        REPO/'tools/boot_selector/twelve_model/test_native_model_start.py',
        REPO/'tools/boot_selector/twelve_model/models.py',REPO/'tools/boot_selector/reference_model.py',
        menu_receipt_path,artifact,artifact.with_name('roc-boot-selector-host')))
    rows=unique_cases(receipt['rows'],('architecture','model'),'actual native Start')
    check(set(rows)=={(architecture,model) for architecture in ('host','aarch64') for model in MODELS},
          'Incomplete actual twelve-model host/AArch64 Start topology')
    loading={(row['architecture'],row['model']):row for row in menu['loading_only_cases']}
    for (architecture,model),row in rows.items():
        metadata=MODELS[model]
        selected={'schema':2,'model_id':model,'save_default':False}
        check(row['script']=='DDA' and row['selected']==selected and row['all12_available_mask'] is True and
              row['native_size']==list(metadata[4:6]) and row['rotation']==metadata[-1] and
              row['loading_frame_sha256']==loading[architecture,model]['ppm_sha256'],
              'Actual model Start lost availability, model or immediate loading frame: '+model)
        stem=receipt_path.parent/(model+'-'+architecture)
        check(read_json(stem.with_suffix('.json'))==selected and
              sha(stem.with_suffix('.ppm'))==row['loading_frame_sha256'],
              'Actual native Start outputs changed: '+model+':'+architecture)


def native_rescue_bindings(menu, artifact):
    check(menu.get('manual_panel_recovery') is True and menu.get('preview_exit_code')==4 and
          menu.get('preview_profiles')==3 and menu.get('catalog_electrical_profiles')==10 and
          menu.get('volume_press_release_guard') is True,
          'Native menu lacks the agreed three-profile manual recovery')
    controls=dict(menu['sha256'])
    for name,value in menu.get('controls',{}).items():
        check(name not in controls or controls[name]==value,'Conflicting native control hash: '+name)
        controls[name]=value
    receipt_controls({'controls':controls},'native rescue',(
        REPO/'tools/boot_selector/twelve_model/selector_rescue.c',
        REPO/'tools/boot_selector/twelve_model/build_native_rescue.py',
        REPO/'tools/boot_selector/twelve_model/generate_assets_rescue.py',
        REPO/'tools/boot_selector/twelve_model/test_native_rescue.py',
        REPO/'tools/boot_selector/twelve_model/models.py',
        REPO/'tools/boot_selector/reference_model.py',
        artifact,artifact.with_name('roc-boot-selector-host')))
    assets=[name for name in controls if Path(name).name=='assets.h']
    check(len(assets)==1,'Native rescue must bind one exact generated asset header')
    rescue=menu['rescue']
    check(rescue['profile_cycle']==list(PREVIEW_MODELS) and
          rescue['host_and_actual_aarch64'] is True and rescue['hardware_accessed'] is False and
          rescue['runtime_FIFO_is_ordinary_fixture'] is True,
          'Unexpected manual trial profile cycle or execution scope')
    rows=unique_cases(rescue['preview_cases'],('architecture','active_model','direction'),'manual preview')
    check(set(rows)=={(architecture,model,direction) for architecture in ('host','aarch64')
                     for model in MODELS for direction in ('down','up')},
          'Incomplete actual host/AArch64 three-profile manual preview topology')
    geometries={MODELS[model][6:8]:index for index,model in enumerate(PREVIEW_MODELS)}
    for (architecture,active,direction),row in rows.items():
        anchor=geometries[MODELS[active][6:8]]
        target=PREVIEW_MODELS[(anchor+(1 if direction=='down' else -1))%3]
        check(row['highlighted_model'] in MODELS and row['highlighted_model']!=active and
              row['target_model']==target and row['returncode']==4 and
              row['script']=='DAURR'+('N' if direction=='down' else 'P') and
              row['save_was_enabled_before_preview'] is True and
              row['result']=={'schema':2,'model_id':target,'save_default':False},
              'Manual preview used the highlight, changed save state or confirmed Android: '+active)
        stem=artifact.parent/'rescue-fixtures'/(active+'-'+direction+'-'+architecture)
        check(read_json(stem.with_suffix('.json'))==row['result'] and
              sha(stem.with_suffix('.ppm'))==row['ppm_sha256'],
              'Actual native manual-preview outputs changed: '+active+':'+architecture)
    blind=unique_cases(rescue['blind_runtime_cases'],('architecture','framebuffer'),'blind manual preview')
    check(set(blind)=={(architecture,framebuffer) for architecture in ('host','aarch64')
                      for framebuffer in ('missing','regular')},
          'Incomplete actual input-only fallback execution topology')
    for row in blind.values():
        active=row['active_model'];direction=row['direction']
        check(active in MODELS and direction in ('down','up'),'Unknown blind preview input/model')
        anchor=geometries[MODELS[active][6:8]]
        target=PREVIEW_MODELS[(anchor+(1 if direction=='down' else -1))%3]
        check(row['normal_confirm_blocked'] is True and row['result_before_volume'] is False and
              row['input_FIFO_ordinary'] is True and row['hardware_accessed'] is False and
              row['returncode']==4 and row['result']=={'schema':2,'model_id':target,'save_default':False},
              'Invisible framebuffer fallback allowed confirmation or changed preview behavior')
        result=artifact.parent/'rescue-fixtures'/('blind-'+row['architecture']+'-'+row['framebuffer'])/'result.json'
        check(read_json(result)==row['result'],'Actual blind-preview result changed')


def boot_state_bindings(receipt, receipt_path, artifact):
    """Bind both executed helpers and their preservation/negative controls."""
    source=REPO/'tools/boot_selector/twelve_model/boot_state_preview.c'
    tests_path=receipt_path.parent/'boot-state-tests.json'
    host=artifact.with_name('boot-state-host')
    check(receipt['schema']=='roc.h700.boot-state-preview.v1' and receipt['pass'] is True and
          Path(receipt['source'])==source and receipt['source_sha256']==sha(source) and
          Path(receipt['artifact'])==artifact and receipt['artifact_sha256']==sha(artifact) and
          receipt['preview_keeps_saved_default'] is True and receipt['preview_next_start']=='2' and
          receipt['hardware_accessed'] is False,'Preview helper source/artifact/semantics binding')
    receipt_controls(receipt,'boot-state preview',(
        source,REPO/'tools/boot_selector/twelve_model/test_boot_state_preview.py',
        REPO/'tools/boot_selector/twelve_model/build_native_rescue.py',tests_path,host,artifact))
    binaries={}
    for row in receipt['binaries']:
        architecture=row['architecture']
        check(architecture not in binaries and architecture in ('host','aarch64'),
              'Duplicate/unknown preview helper architecture')
        path=host if architecture=='host' else artifact
        check(Path(row['path'])==path and row['sha256']==sha(path) and row['bytes']==path.stat().st_size,
              'Executed preview helper binary changed: '+architecture)
        binaries[architecture]=row
    check(set(binaries)=={'host','aarch64'},'Missing executed preview helper architecture')
    arm=artifact.read_bytes()
    check(arm[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',arm,18)[0]==183,
          'Preview helper is not an actual little-endian AArch64 ELF')
    phoff=struct.unpack_from('<Q',arm,32)[0]
    phsize,phcount=struct.unpack_from('<HH',arm,54)
    check(phsize==56 and phcount>0 and phoff+phsize*phcount<=len(arm) and
          all(struct.unpack_from('<I',arm,phoff+index*phsize)[0]!=3 for index in range(phcount)),
          'Preview helper unexpectedly requires an interpreter')
    tests=read_json(tests_path)
    check(tests['pass'] is True and tests['hardware_io'] is False and
          tests['architectures']==receipt['rows'],'Preview helper execution receipt mismatch')
    prefix=ordinary(tests['source_prefix'])
    check(prefix==Path('/home/lpf/roc-os-h700-shared-panel-20261114-v1/prefix.shared.raw'),
          'Preview fixtures did not use the retained source environment')
    with prefix.open('rb') as stream:
        stream.seek(ENV_START);part=stream.read(16*1024**2)
    check(len(part)==16*1024**2 and digest(part)==tests['source_partition_sha256'] and
          digest(part[:ENV_BYTES])==tests['source_environment_sha256'] and
          len(environment(part[:ENV_BYTES]))==tests['original_rows'],
          'Retained source environment fixture identity changed')
    architectures={}
    env_negative={'missing-schema','wrong-schema','missing-hook-key','missing-hook-call',
                  'bad-saved','bad-next','next-start-zero','next-start-two','next-start-three',
                  'next-without-start','start-without-next','duplicate-schema','duplicate-saved'}
    file_negative={'badCRC','wrong-size','symlink','hardlink','partition-kind-regular','fifo',
                   'directory','nonzero-padding','unknown-model'}
    json_positive={'native','reordered'}
    json_negative={'extra','duplicate','schema-string','schema-bool','schema-float','save-int',
                   'save-string','model-alias','escape','trailing','missing','NUL',
                   'vertical-whitespace','oversize','empty'}
    for arch in receipt['rows']:
        architecture=arch['architecture']
        check(architecture in binaries and architecture not in architectures and arch['pass'] is True and
              arch['checks']==len(arch['cases'])+3,'Incomplete preview helper execution checks')
        architectures[architecture]=arch
        named={};preview={};actions=[]
        for index,row in enumerate(arch['cases']):
            if 'action' in row:
                check(row['action'] in ('status','save','once','clear-next','preview') and
                      row['crc_valid'] is True and row['tail_16m_preserved'] is True,
                      'Helper action lost CRC/partition-tail preservation')
                fields={}
                for line in row['status'].splitlines():
                    key,value=line.split('=',1)
                    check(key not in fields,'Duplicate helper status field')
                    fields[key]=value
                check(set(fields)=={'saved','next','next_start'} and
                      fields['saved'] in ('',*MODELS) and fields['next'] in ('',*MODELS) and
                      (not fields['next'] and fields['next_start']=='' or
                       fields['next'] and fields['next_start'] in ('1','2')),
                      'Invalid helper status result')
                if row['action']=='preview':
                    check(row['model'] in PREVIEW_MODELS and fields['next']==row['model'] and
                          fields['next_start']=='2','Preview helper selected an ordinary Android route')
                if row['action']=='once':
                    check(fields['next']==row['model'] and fields['next_start']=='1',
                          'Ordinary once did not replace preview marker')
                if row['action'] in ('save','clear-next'):
                    check(fields['next']==fields['next_start']=='', 'Confirmation did not consume preview')
                if row['action']=='save':check(fields['saved']==row['model'],'Save lost selected default')
                actions.append((row,fields))
                continue
            name=row['case']
            if name=='preview-preserves-saved':
                key=(row['saved_model'],row['representative'])
                check(key not in preview and key[0] in MODELS and key[1] in PREVIEW_MODELS and
                      row['next_start']=='2' and row['pass'] is True and index>0,
                      'Duplicate/failed saved-model preview case')
                previous=arch['cases'][index-1]
                check(previous.get('action')=='preview' and previous['model']==key[1] and
                      previous['status']=='saved='+key[0]+'\nnext='+key[1]+'\nnext_start=2',
                      'Preview preservation assertion does not bind actual immediately preceding status')
                preview[key]=row
            else:
                check(name not in named,'Duplicate helper negative/preservation case: '+name)
                named[name]=row
        check(set(preview)=={(model,target) for model in MODELS for target in PREVIEW_MODELS},
              'Incomplete twelve saved defaults by three preview representatives')
        check(set(named)==env_negative|file_negative|{'no-leading-empty-preserved',
              'preview-only-three-representatives'}|{'result-'+name for name in json_positive|json_negative},
              'Preview helper negative-control topology changed')
        for name in env_negative:
            check(named[name]['rejected_status_and_write'] is True and named[name]['unchanged'] is True,
                  'Invalid environment was accepted or modified: '+name)
        for name in file_negative:check(named[name]['rejected'] is True,'Unsafe helper input accepted: '+name)
        for name in json_positive|json_negative:
            check(named['result-'+name]['accepted'] is (name in json_positive),
                  'Helper result parser contract changed: '+name)
        restricted=named['preview-only-three-representatives']
        check(restricted['pass'] is True and restricted['unchanged'] is True and
              restricted['rejected_models']==sorted(set(MODELS)-set(PREVIEW_MODELS)) and
              named['no-leading-empty-preserved']['pass'] is True,
              'Preview allowed an unapproved representative or changed vendor leading-row rules')
        # The final sequence exercises all three explicit ways of consuming an
        # outstanding preview and checks that the saved default is retained.
        last=list(MODELS)[-1]
        check([(row['action'],row['model']) for row,fields in actions[-5:]]==[
            ('once','rg35xxh'),('preview','rg34xxsp'),('clear-next',None),
            ('preview','rgcubexx'),('save','rgsp')] and
              all(fields['saved']==last for row,fields in actions[-5:-1]),
              'Preview once/clear/save consumption or saved-default preservation changed')
    check(set(architectures)==set(binaries),'Incomplete preview helper execution architectures')


def selector_rescue_bindings(selector, artifact):
    check(selector['manual_panel_recovery'] is True and selector['preview_exit_code']==4 and
          selector['preview_profiles']==3 and selector['preview_cycle']==list(PREVIEW_MODELS) and
          selector['preview_keeps_saved_default'] is True and selector['preview_next_start']=='2' and
          selector['preview_persists_until_normal_confirmation'] is True and
          selector['no_automatic_panel_cycling'] is True and
          selector['no_automatic_reboot_without_manual_choice'] is True and
          selector['actual_root_script_unchanged'] is True,'Selector preview behavior/scope changed')
    receipt_controls(selector,'selector rescue',(
        artifact,REPO/'tools/boot_selector/twelve_model/test_selector_init_rescue.py',
        REPO/'tools/boot_selector/twelve_model/test_native_rescue.py',
        REPO/'tools/boot_selector/twelve_model/models.py',REPO/'tools/boot_selector/reference_model.py'))
    rows=unique_cases(selector['rows'],('case',),'selector rescue')
    rows={key[0]:value for key,value in rows.items()}
    geometries={MODELS[model][6:8]:index for index,model in enumerate(PREVIEW_MODELS)}
    for shell in ('host','mother_busybox'):
        for active,metadata in MODELS.items():
            for direction in ('down','up'):
                row=rows[shell+'_preview_'+direction+'_'+active]
                anchor=geometries[metadata[6:8]]
                target=PREVIEW_MODELS[(anchor+(1 if direction=='down' else -1))%3]
                saved=list(MODELS)[(list(MODELS).index(active)+1)%len(MODELS)]
                check(row['shell_id']==shell and row['active_model']==active and
                      row['chosen_model']==row['preview_target']==target and row['direction']==direction and
                      row['route']=='selector' and row['native_exit_code']==4 and
                      row['returncode']==77 and row['actions']==['status','preview','status'] and
                      row['selector_calls']==1 and row['loading_only_calls']==0 and
                      row['preview_saved_default_unchanged'] is True and
                      row['final_environment']=={'saved':saved,'next':target,'next_start':'2'} and
                      row['preview_readback_verified'] is True and
                      row['reboot_no_return_boundary_modeled'] is True and
                      row['attempted_stub_reboot'] is True and row['fatal_wait_entered'] is False and
                      [event['name'] for event in row['events']][-2:]==['sync','busybox'],
                      'Selector preview lost active geometry, saved default or readback/reboot order: '+active)
            for action in ('same','save','once'):
                row=rows[shell+'_all12_'+action+'_'+active]
                expected=['status','save'] if action=='save' else ['status','clear-next'] if (
                    action=='same' or active=='rg35xxh') else ['status','once']
                check(row['actions']==expected and row['selector_calls']==1 and
                      row['returncode']==(77 if expected[-1]=='once' else 0),
                      'Normal twelve-model confirmation route regressed: '+active+':'+action)
        for active in PREVIEW_MODELS:
            row=rows[shell+'_preview_pending_wait_then_confirm_'+active]
            check(row['returncode']==0 and row['actions']==['status','clear-next'] and
                  row['selector_calls']==2 and row['preview_kept_until_explicit_confirmation'] is True and
                  row['final_environment']=={'saved':'rgsp','next':'','next_start':''},
                  'Pending preview was consumed before normal confirmation')
        retry_actions={name:['status','clear-next'] for name in (
            'parse_error','invalid_fields','save_requested','unknown_model','nonrepresentative','nonadjacent',
            'initial_state_invalid')}
        retry_actions['write_error']=['status','preview','clear-next']
        retry_actions.update({'readback_'+name:['status','preview','status','clear-next'] for name in (
            'status_error','changed_saved','wrong_next','wrong_marker','duplicate','extra')})
        for name,expected in retry_actions.items():
            row=rows[shell+'_preview_'+name+'_retries']
            check(row['returncode']==0 and row['native_exit_code']==4 and row['selector_calls']==2 and
                  row['actions']==expected and row['preview_failure_requires_later_explicit_confirmation'] is True and
                  row['preview_saved_default_unchanged'] is True and
                  row['attempted_stub_reboot'] is False and row['fatal_wait_entered'] is False,
                  'Failed preview fell through to Android without later explicit confirmation: '+name)
        for name,expected in (
            ('unsafe_output',['status','preview']),
            ('retry_cleanup_failure',['status','preview']),
            ('sync_failure',['status','preview','status']),
            ('reboot_returned_0',['status','preview','status']),
            ('reboot_returned_7',['status','preview','status'])):
            suffix=name if name.startswith('reboot_returned') else name+'_stops'
            row=rows[shell+'_preview_'+suffix]
            check(row['returncode']==78 and row['selector_calls']==1 and row['actions']==expected and
                  row['fatal_wait_entered'] is True and row['native_exit_code']==4,
                  'Unrecoverable preview failure escaped fatal wait: '+name)
        row=rows[shell+'_preview_absent_framebuffer']
        check(row['returncode']==77 and row['actions']==['status','preview','status'] and
              row['selector_calls']==1 and row['sleep_calls']==20 and
              row['final_environment']=={'saved':'rgsp','next':'rg34xxsp','next_start':'2'} and
              row['reboot_no_return_boundary_modeled'] is True,
              'Missing framebuffer prevented manual volume recovery')


def receipt_bindings(inputs):
    """Bind tested artifacts to actual receipt fields, not merely receipt paths."""
    paths={}; hashes={}
    check(set(inputs)==REQUIRED,'Incomplete/extra frozen component set')
    for key,row in inputs.items():
        path=ordinary(row['path']); value=sha(path)
        check(value==row['sha256'],'Component hash mismatch: '+key)
        paths[key]=path; hashes[key]=value
    receipts={key:read_json(path) for key,path in paths.items() if key.endswith('_receipt')}
    for key,row in receipts.items(): check(row.get('passed',row.get('pass')) is True,'Failed component: '+key)
    i=receipts['input_receipt']
    check(i['schema']=='roc.h700.explicit-input-candidate.v1' and i['module_sha256']==hashes['module']
          and Path(i['module_path'])==paths['module'] and i['no_RAM_identity_gate'] is True
          and i['catalog_models']==12 and i['no_stick_models']==6
          and i['single_stick_models']==1 and i['dual_stick_models']==5,'Input candidate/artifact binding')
    check(i['source_sha256']['h700_optional_axes.sh']==hashes['early_helper'] and
          i['source_sha256']['rgsp-stick-axes.sh']==hashes['android_loader'],'Input loader receipt binding')
    for name,value in i['source_sha256'].items():
        check('/' not in name and sha(REPO/'tools/input_profiles'/name)==value,'Input source proof binding: '+name)
    for name,value in i['proof_sha256'].items():
        check(sha(REPO/name)==value,'Input proof binding changed: '+name)
    m=receipts['menu_receipt']
    check(m['sha256'].get(str(paths['menu']))==hashes['menu'] and m['static'] is True,
          'Native menu receipt artifact binding')
    for name,value in m['sha256'].items():check(sha(name)==value,'Native menu tested input/artifact changed: '+name)
    for key in ('host_test','actual_aarch64_test'):
        check(m[key]['pass'] is True and m[key]['models']==12,'Incomplete native menu model tests')
    s=receipts['selector_receipt']
    check(Path(s['source'])==paths['selector_hook'] and s['source_sha256']==hashes['selector_hook'],
          'Selector init receipt artifact binding')
    loading_receipt_bindings(m,s)
    native_rescue_bindings(m,paths['menu'])
    selector_rescue_bindings(s,paths['selector_hook'])
    boot_state_bindings(receipts['boot_state_receipt'],paths['boot_state_receipt'],paths['boot_state'])
    native_start_bindings(receipts['native_start_receipt'],paths['native_start_receipt'],m,
                          paths['menu_receipt'],paths['menu'])
    p=receipts['panel_receipt']
    for arch,component in [('kernel','kernel')]:
        row=p['architectures'][arch]
        check(row['patched_sha256']==hashes[component] and
              Path(row.get('patched_file',row.get('file')))==paths[component]
              and row['original_bytes']==paths[component].stat().st_size,'Panel artifact/receipt binding: '+arch)
    e=receipts['early_receipt']
    check(e['patched_sha256']==hashes['early_uboot'] and e['physical_display_accepted'] is False,
          'Early bridge receipt/final artifact mismatch')
    source=ordinary(e['input_dispatch']['path'])
    check(sha(source)==e['input_dispatch']['sha256']==p['architectures']['uboot']['patched_sha256']
          and source==Path(p['architectures']['uboot'].get('patched_file',p['architectures']['uboot'].get('file'))),
          'Early bridge did not start from final panel U-Boot')
    early_preview_bindings(e,paths['early_receipt'],paths['early_uboot'])
    lid=receipts['lid_receipt']
    check(lid['artifact_sha256']==hashes['lid'] and Path(lid['artifact'])==paths['lid']
          and lid['platform_certificate_sha256']==CERT and lid['old_and_new_Android10_signature_verified'] is True
          and lid['model_gate_checks']>=600 and lid['state_checks']>=3000,'Lid4 signed production receipt binding')
    return paths,hashes,receipts


def inputs_check(prep,result):
    check(prep['schema']=='roc.h700.twelve-model-preparation.v1' and prep['passed'] is True,'Foreign/incomplete preparation')
    check(result['schema']=='roc.h700.twelve-model-image.v1' and result['passed'] is True,'Foreign/incomplete image receipt')
    check(result['raw_bytes']==RAW_BYTES and result['parent_raw_sha256']==BASE_SHA,'Incorrect raw/parent identity')
    check(set(result['integrated_models'])==set(MODELS) and len(result['integrated_models'])==12
          and result['electrical_profiles']==10 and result['ram_identity_gate'] is False,'Incomplete twelve-model report')
    check(result['manual_panel_recovery'] is True and result['preview_next_start']=='2' and
          result['menu_preview_models']==list(PREVIEW_MODELS) and
          result['menu_visible_on_all_models_accepted'] is False,
          'Image recovery report lost the three trial profiles or overstates physical visibility')
    check(result['physical_card_written'] is False and result['all_H700_models_accepted'] is False,'Physical acceptance must remain pending')
    check(sha(ACCEPTANCE)==ACCEPTANCE_SHA and sha(REPO/'docs/SPACE_REVIEW_20261028.md')==SPACE_SHA,
          'Protected baseline/preservation receipt changed')
    parent=read_json(ACCEPTANCE)
    check(parent['offline_passed'] is True and parent['image']['raw_sha256']==BASE_SHA
          and parent['implementation']['Navigation18_sha256']==NAV_SHA
          and parent['implementation']['framework_sha256']==FRAMEWORK_SHA,'Parent acceptance semantic binding')
    paths,hashes,receipts=receipt_bindings(prep['inputs'])
    controls=prep['controls']
    check(all(sha(name)==value for name,value in controls.items()),'Frozen source/control changed')
    for key,path in paths.items(): check(controls.get(str(path))==hashes[key],'Artifact absent from producer controls: '+key)
    manifests=[]
    for name in controls:
        if name.endswith('.json'):
            row=read_json(name)
            if isinstance(row,dict) and row.get('schema')=='roc.h700.twelve-model-inputs.v1':manifests.append(row)
    check(len(manifests)==1 and manifests[0]['inputs']==prep['inputs'],'Frozen manifest/prepared component semantic binding')
    return paths,hashes,receipts


def sparse_write(writer,data):
    if data.count(0)==len(data): writer.seek(len(data),os.SEEK_CUR)
    else: writer.write(data)


def stream(reader,folder,label,compare=None,complete=False):
    """Hash every byte, save selected partitions, optionally compare every byte."""
    names=('prefix','system','vendor')
    writers={name:(folder/(label+'.'+name+'.raw')).open('xb') for name in names}
    if complete: writers['raw']=(folder/'expanded.raw').open('xb')
    hashes={name:hashlib.sha256() for name in RANGES}; total=0; whole=hashlib.sha256(); head=b'';tail=b''
    try:
        while block:=reader.read(4*1024**2):
            end=total+len(block); check(end<=RAW_BYTES,'Expanded image exceeds fixed card size')
            if compare is not None: check(compare.read(len(block))==block,'Producer raw differs from actual gzip at '+str(total))
            whole.update(block)
            if total<1024**2: head+=block[:min(len(block),1024**2-total)]
            tail=(tail+block)[-1536:]
            if complete: sparse_write(writers['raw'],block)
            for name,(offset,length) in RANGES.items():
                lo,hi=max(total,offset),min(end,offset+length)
                if lo>=hi: continue
                data=block[lo-total:hi-total]; hashes[name].update(data)
                if name in writers:sparse_write(writers[name],data)
            total=end
        check(total==RAW_BYTES,'Incomplete entire raw stream')
        if compare is not None:check(compare.read(1)==b'','Producer raw has unexpected suffix')
        for name,writer in writers.items():
            writer.truncate(RAW_BYTES if name=='raw' else RANGES[name][1]);writer.flush();os.fsync(writer.fileno())
    finally:
        for writer in writers.values():writer.close()
    return {'bytes':total,'sha256':whole.hexdigest(),'ranges':{k:v.hexdigest() for k,v in hashes.items()},'head':head,'tail':tail}


def verify_gpt(head,tail):
    check(head[510:512]==b'\x55\xaa','Protective MBR signature')
    pair=[];tables=[]
    for block,absolute in [(head[512:1024],512),(tail[-512:],RAW_BYTES-512)]:
        check(block[:8]==b'EFI PART','GPT signature')
        size,crc=struct.unpack_from('<II',block,12);check(92<=size<=512,'GPT header length')
        raw=bytearray(block[:size]);raw[16:20]=bytes(4)
        check(zlib.crc32(raw)==crc,'GPT header checksum')
        current,backup,first,last=struct.unpack_from('<4Q',block,24)
        lba,count,width,array_crc=struct.unpack_from('<QIII',block,72)
        check(current*512==absolute and 0<count<=128 and width==128,'GPT geometry')
        offset,length=lba*512,count*width
        table=head[offset:offset+length] if offset<len(head) else tail[offset-(RAW_BYTES-len(tail)):offset-(RAW_BYTES-len(tail))+length]
        check(len(table)==length and zlib.crc32(table)==array_crc,'GPT entry-array checksum')
        pair.append((current,backup,first,last,block[56:72]));tables.append(table)
    check(pair[0][0]==pair[1][1]==1 and pair[0][1]==pair[1][0]==RAW_BYTES//512-1
          and pair[0][2:]==pair[1][2:] and tables[0]==tables[1],'GPT primary/backup correspondence')
    entries=[]
    for offset in range(0,len(tables[0]),128):
        row=tables[0][offset:offset+128]
        if row[:16]==bytes(16):continue
        first,last=struct.unpack_from('<QQ',row,32);check(first<=last,'Reversed GPT partition')
        entries.append({'name':row[56:128].decode('utf-16le').rstrip('\0'),'offset':first*512,'bytes':(last-first+1)*512})
    for name in ('system','vendor','userdata'):
        check(sum((r['offset'],r['bytes'])==RANGES[name] and r['name']==name for r in entries)==1,'GPT partition identity: '+name)
    return entries


def toc(prefix):
    raw=prefix[TOC_START:TOC_START+TOC_BYTES]
    check(struct.unpack_from('<I',raw,16)[0]==0x89119800,'TOC1 magic')
    crc=struct.unpack_from('<I',raw,20)[0];count,size=struct.unpack_from('<II',raw,32)
    check(1<=count<=64 and 64+count*368<=size<=len(raw) and size%4==0,'TOC1 bounds')
    check((sum(struct.unpack_from('<'+str(size//4)+'I',raw))-crc+0x5f0a6c39)&0xffffffff==crc,'TOC1 checksum')
    rows=[]
    for index in range(count):
        pos=64+index*368;name=raw[pos:pos+64].split(b'\0')[0].decode('ascii');offset,length=struct.unpack_from('<II',raw,pos+64)
        check(offset>=64+count*368 and length>0 and offset+length<=size,'TOC1 item bounds')
        rows.append({'name':name,'offset':TOC_START+offset,'bytes':length,'sha256':digest(raw[offset:offset+length])})
    check(len({r['name'] for r in rows})==len(rows) and {'u-boot','monitor','dtb'}<={r['name'] for r in rows},'TOC1 item set')
    return rows


def boot_parts(blob):
    check(len(blob)==BOOT_BYTES and blob[:8]==b'ANDROID!','Android boot header')
    check(struct.unpack_from('<II',blob,36)==(2048,2),'Android page/header version')
    check(struct.unpack_from('<IQ',blob,1632)==(0,0) and struct.unpack_from('<I',blob,1644)[0]==1660,'Android v2 recovery/header layout')
    parts={};offset=2048
    for name,field in [('kernel',8),('ramdisk',16),('second',24),('dtb',1648)]:
        length=struct.unpack_from('<I',blob,field)[0];end=offset+length;padded=(end+2047)&~2047
        check(end<=padded<=len(blob) and not any(blob[end:padded]),'Android component bounds/zero padding: '+name)
        parts[name]={'offset':offset,'bytes':length,'data':blob[offset:end]};offset=padded
    check(parts['kernel']['bytes']==17686536 and parts['dtb']['bytes']==137600,'Fixed kernel/DTB capacity')
    check(struct.unpack_from('>II',parts['dtb']['data'])==(0xd00dfeed,137600),'Kernel DTB header length')
    check(blob[offset:]==b'\xff'*(len(blob)-offset),'Android boot erased tail')
    return parts


def cpio(raw):
    entries=[];names=set();pos=0
    while pos+110<=len(raw):
        check(raw[pos:pos+6]==b'070701','CPIO newc signature')
        fields=raw[pos+6:pos+110];check(re.fullmatch(rb'[0-9a-fA-F]{104}',fields),'Malformed CPIO hex')
        numbers=[int(fields[i:i+8],16) for i in range(0,104,8)]
        size,nlen=numbers[6],numbers[11];nend=pos+110+nlen;start=(nend+3)&~3;end=start+size;nextpos=(end+3)&~3
        check(1<=nlen<=4096 and nextpos<=len(raw),'CPIO entry overflow')
        namebytes=raw[pos+110:nend];check(namebytes[-1:]==b'\0' and b'\0' not in namebytes[:-1],'CPIO filename')
        name=namebytes[:-1].decode();check(name not in names and not name.startswith('/') and '..' not in name.split('/'),'CPIO duplicate/unsafe member')
        check(not any(raw[nend:start]) and not any(raw[end:nextpos]),'CPIO padding')
        entries.append({'name':name,'fields':numbers,'data':raw[start:end]});names.add(name);pos=nextpos
        if name=='TRAILER!!!':
            check(size==0 and not any(raw[pos:]),'CPIO trailing bytes');return entries
    raise ValueError('CPIO trailer missing')


def environment(blob):
    check(len(blob)==ENV_BYTES and zlib.crc32(blob[4:])==struct.unpack_from('<I',blob)[0],'Environment CRC')
    end=blob.find(b'\0\0',4);check(end>=4 and not any(blob[end+2:]),'Environment termination/tail')
    rows=[]
    for index,raw in enumerate(blob[4:end].split(b'\0')):
        check(b'=' in raw or index==0 and raw==b'','Environment key/value')
        rows.append(tuple(raw.decode('ascii').split('=',1)) if raw else ('',''))
    check(len(dict(rows))==len(rows),'Duplicate environment key');return rows


def expected_commands():
    values={'boot_normal':'run roc_selector_apply','roc_selector_schema':'2',
      'roc_selector_apply':'run roc_load_boot roc_dispatch roc_boot_args roc_boot_kernel',
      'roc_load_boot':'sunxi_flash read 45000000 boot','roc_dispatch':'run roc_apply_${roc_active_model}',
      'roc_fdt_addr':'fdt addr ${fdtcontroladdr}'}
    for profile,row in enumerate(TIMINGS):
        for name,value in [('roc_panel_profile',profile),*zip(PROPS,row)]:
            values[f'roc_{profile}_{name}']=f"fdt set {PANEL} {name} '<0x{value:x}>'"
    for model,(profile,lid,sticks,form,nw,nh,lw,lh,rotation) in MODELS.items():
        keys=[f'roc_{profile}_{name}' for name in ('roc_panel_profile',*PROPS)]
        values['roc_apply_'+model]='run '+' '.join(['roc_fdt_addr',*keys,'roc_lid'+str(lid)])
        metadata={'model':model,'clamshell':lid,'route':'${roc_boot_route}','sticks':sticks,
                  'form_factor':form,'native_width':nw,'native_height':nh,'logical_width':lw,
                  'logical_height':lh,'rotation':rotation,'panel_profile':profile}
        values['roc_boot_args_'+model]='setenv bootargs ${bootargs} '+' '.join('androidboot.roc_'+k+'='+str(v) for k,v in metadata.items())
    values.update(roc_lid0='setenv roc_clamshell 0',roc_lid1='setenv roc_clamshell 1',
                  roc_boot_args='run roc_boot_args_${roc_active_model}',roc_boot_kernel='bootm 45000000')
    return values


def emulate_routes(values):
    """Independent simple-parser interpreter of the actual delivered environment."""
    rows=[]
    for model,meta in MODELS.items():
        for route in ('selector','start_once','start_saved'):
            env=dict(values,roc_active_model=model,roc_boot_route=route,bootargs='console=ttyS0',fdtcontroladdr='4bf00000')
            fdt={};calls=[];selected=None;booted=False
            def expand(value):
                return re.sub(r'\$\{([^}]+)\}',lambda m:env.get(m[1],''),value)
            def execute(name,depth=0):
                nonlocal selected,booted
                check(depth<20 and len(calls)<100,'Run recursion/call limit');calls.append(name)
                check(name in env,'Missing actual route variable: '+name)
                line=expand(env[name]);check(not any(x in line for x in (';','&&','\n')),'Non-simple parser command')
                argv=shlex.split(line);check(argv and len(argv)<100,'Route argument limit')
                if argv[0]=='run':
                    for key in argv[1:]:execute(key,depth+1)
                elif argv[:3]==['sunxi_flash','read','45000000']:
                    check(argv==['sunxi_flash','read','45000000','boot'],'Wrong boot load')
                elif argv[:2]==['fdt','addr']:
                    check(argv==['fdt','addr','4bf00000'],'Actual route lost control FDT handoff');selected=argv[2]
                elif argv[:2]==['fdt','set']:
                    check(selected=='4bf00000' and len(argv)==5 and argv[2]==PANEL,'FDT edit target')
                    check(re.fullmatch(r'<0x[0-9a-f]+>',argv[4]),'FDT edit cell');fdt[argv[3]]=int(argv[4][1:-1],16)
                elif argv[0]=='setenv':
                    check(len(argv)>=3,'setenv arity');env[argv[1]]=' '.join(argv[2:])
                elif argv[0]=='bootm':
                    check(argv==['bootm','45000000'] and not booted,'Final bootm target');booted=True
                else:raise ValueError('Unexpected actual route command: '+line)
            execute('boot_normal')
            profile,lid,sticks,form,nw,nh,lw,lh,rotation=meta
            check(booted and fdt=={'roc_panel_profile':profile,**dict(zip(PROPS,TIMINGS[profile]))},'Actual electrical timing route: '+model)
            wanted={'model':model,'clamshell':str(lid),'route':route,'sticks':str(sticks),'form_factor':form,
                    'native_width':str(nw),'native_height':str(nh),'logical_width':str(lw),'logical_height':str(lh),
                    'rotation':str(rotation),'panel_profile':str(profile)}
            args=dict(x.split('=',1) for x in env['bootargs'].split() if x.startswith('androidboot.roc_'))
            check(args=={'androidboot.roc_'+k:v for k,v in wanted.items()} and env['roc_clamshell']==str(lid),
                  'Actual Android metadata route: '+model)
            rows.append({'model':model,'route':route,'panel_profile':profile,'calls':calls,'bootargs':env['bootargs']})
    return rows


def verify_prefix(before,after,paths,receipts,folder):
    check(len(before)==len(after)==RANGES['prefix'][1] and digest(before)==PARENT_SHA['prefix'],'Exact Test7 prefix')
    oldtoc,newtoc=toc(before),toc(after)
    check([(r['name'],r['offset'],r['bytes']) for r in oldtoc]==[(r['name'],r['offset'],r['bytes']) for r in newtoc],'TOC1 item layout changed')
    uboot=next(r for r in oldtoc if r['name']=='u-boot');start,length=uboot['offset'],uboot['bytes']
    check(length==1048576 and after[start:start+length]==paths['early_uboot'].read_bytes(),'Actual final U-Boot artifact')
    windows=sorted([(TOC_START+20,TOC_START+24),(start,start+length),(ENV_START,ENV_START+ENV_BYTES),(BOOT_START,BOOT_START+BOOT_BYTES)])
    cursor=0
    for first,last in windows:
        check(cursor<=first<last<=len(before) and before[cursor:first]==after[cursor:first],'Unrelated prefix bytes changed')
        cursor=last
    check(before[cursor:]==after[cursor:],'Unexpected prefix suffix change')
    boot0=after[8192:8192+65536]
    check(boot0[4:12]==b'eGON.BT0' and struct.unpack_from('<I',boot0,16)[0]==len(boot0),'Boot0 identity/length')
    stored=struct.unpack_from('<I',boot0,12)[0]
    check((sum(struct.unpack('<'+str(len(boot0)//4)+'I',boot0))-stored+0x5f0a6c39)&0xffffffff==stored,'Boot0 checksum')
    oldboot=before[BOOT_START:BOOT_START+BOOT_BYTES];newboot=after[BOOT_START:BOOT_START+BOOT_BYTES]
    old,new=boot_parts(oldboot),boot_parts(newboot)
    check(oldboot[:16]==newboot[:16] and oldboot[20:2048]==newboot[20:2048],'Boot header changed outside ramdisk size')
    check(new['kernel']['data']==paths['kernel'].read_bytes(),'Actual final kernel artifact')
    check(new['second']['data']==old['second']['data'] and new['dtb']['data']==old['dtb']['data'],'Android second/DTB changed')
    compressed=new['ramdisk']['data']
    check(compressed[:4]==b'\x1f\x8b\x08\x00' and compressed[4:8]==bytes(4),'Ramdisk deterministic gzip flags/mtime')
    oldrd,newrd=cpio(gzip.decompress(old['ramdisk']['data'])),cpio(gzip.decompress(compressed))
    check([r['name'] for r in oldrd]==[r['name'] for r in newrd],'CPIO topology/order changed')
    replacement={'grow/roc-boot-selector':paths['menu'],'grow/roc-selector-init.sh':paths['selector_hook'],
                 'grow/h700-optional-axes.sh':paths['early_helper'],
                 'grow/roc-boot-state':paths['boot_state']}
    delta=[]
    for left,right in zip(oldrd,newrd):
        name=left['name'];fields=left['fields'].copy()
        if name in replacement:
            fields[6]=len(right['data']);check(right['data']==replacement[name].read_bytes(),'Actual CPIO candidate mismatch: '+name)
            if right['data']!=left['data']:delta.append(name)
        else:check(left['data']==right['data'],'Unrelated CPIO payload changed: '+name)
        check(right['fields']==fields,'CPIO metadata changed: '+name)
    check(set(delta)==set(replacement),'Expected exactly four changed CPIO member payloads')
    check(next(r for r in newrd if r['name']=='init')==next(r for r in oldrd if r['name']=='init'),
          'Original TF1/init handoff changed')
    busybox=next(r for r in newrd if r['name']=='bin/busybox')['data']
    mother=receipts['selector_receipt']['mother_busybox']
    check(mother['sha256']==digest(busybox) and mother['bytes']==len(busybox) and
          mother['script_n_passed'] is True and mother['read_r_IFS_arithmetic_passed'] is True and
          mother['required_applets_present'] is True,
          'Selector fixtures did not execute the actual inherited ramdisk BusyBox')
    oldenv=environment(before[ENV_START:ENV_START+ENV_BYTES]);newenv=environment(after[ENV_START:ENV_START+ENV_BYTES]);values=dict(newenv)
    check(dict(oldenv)['roc_fdt_addr']=='fdt addr ${fdtcontroladdr}' and values['roc_fdt_addr']==dict(oldenv)['roc_fdt_addr'],'Test7 FDT handoff lost')
    commands=expected_commands()
    expected=[(k,commands.get(k,v)) for k,v in oldenv if not k.startswith('roc_')]
    expected += [(k,v) for k,v in commands.items() if k not in dict(expected)]
    check(newenv==expected,'Unexpected actual full environment, variable ordering or model route')
    check(len(newenv)<256 and len(new['ramdisk']['data'])<BOOT_BYTES-new['kernel']['bytes']-2048-new['dtb']['bytes'],
          'Boot-state environment/ramdisk capacity')
    rows=emulate_routes(values);write_json(folder/'actual-environment-route-execution.json',rows)
    return {'allowed_prefix_windows':windows,'boot0_TOC_environment_checksums':True,
      'final_uboot_sha256':digest(after[start:start+length]),'final_kernel_sha256':digest(new['kernel']['data']),
      'early_control_DTB_byte_exact':True,'Android_DTB_byte_exact':True,'init_byte_exact':True,
      'boot_state_sha256':sha(paths['boot_state']),'boot_state_matches_validated_artifact':True,
      'actual_ramdisk_BusyBox_bound_to_hook_fixtures':True,
      'changed_CPIO_payloads':sorted(delta),'environment_rows':len(newenv),'actual_environment_routes':len(rows),
      'kernel_DTB_offset':new['dtb']['offset'],'kernel_DTB_loaded_address':hex(0x45000000+new['dtb']['offset']),
      'Test7_control_FDT_handoff_preserved':True,'ramdisk_compressed_bytes':new['ramdisk']['bytes']}


def bind_handoff_proof(output,result,prefix):
    """Bind the separately executed final machine proof to this actual gzip."""
    path=ordinary(output/'final-handoff.json')
    value=sha(path);check(value==result['final_handoff_sha256'],'Final machine proof receipt identity')
    proof=read_json(path)
    check(proof['schema']=='roc.test8.twelve-model-final-handoff.v1' and proof['passed'] is True
          and proof['positive_cases']==24 and proof['negative_cases']==2
          and proof['kernel_boundaries']==52 and proof['all12_final_timing_and_feature_args'] is True,
          'Incomplete final machine-code handoff proof')
    check(proof['physical_device_accessed'] is False and proof['physical_card_accessed'] is False,
          'Unexpected physical machine proof scope')
    identities=proof['inputs'];parts=boot_parts(prefix[BOOT_START:BOOT_START+BOOT_BYTES])
    items=toc(prefix);uboot=next(r for r in items if r['name']=='u-boot')
    expected={'prefix_sha256':digest(prefix),'uboot_sha256':uboot['sha256'],
              'toc_sha256':digest(prefix[TOC_START:TOC_START+TOC_BYTES]),
              'environment_sha256':digest(prefix[ENV_START:ENV_START+ENV_BYTES]),
              'boot_sha256':digest(prefix[BOOT_START:BOOT_START+BOOT_BYTES])}
    for name,value in expected.items():check(identities[name]==value,'Machine proof does not bind actual gzip: '+name)
    for name,row in parts.items():
        check(identities['boot_components'][name]=={'offset':row['offset'],'bytes':row['bytes'],'sha256':digest(row['data'])},
              'Machine proof actual boot component mismatch: '+name)
    check(identities['loaded_fdt_address']==hex(0x45000000+parts['dtb']['offset']),
          'Machine proof wrong final loaded-DTB address')
    check(all(sha(name)==value for name,value in proof['controls'].items()),'Machine proof controls changed')
    positives={};negatives=[]
    for row in proof['cases']:
        check(row['passed'] is True and row['slide'] in (0,0x1000000),'Failed/unrecognized final handoff case')
        model=row['model'];check(model in MODELS,'Unknown final handoff model')
        if row['mode']=='controladdr':
            key=(model,row['slide']);check(key not in positives,'Duplicate positive machine case');positives[key]=row
            meta=MODELS[model];profile=meta[0]
            check(row['final_DTB']['panel']=={'roc_panel_profile':profile,**dict(zip(PROPS,TIMINGS[profile]))},
                  'Final machine proof loses independent thirteen-cell model intent: '+model)
        else:
            check(row['mode']=='wrong-loaded-tight' and model=='rg28xx','Unexpected machine negative');negatives.append(row)
    check(set(positives)=={(model,slide) for model in MODELS for slide in (0,0x1000000)}
          and len(negatives)==2 and {r['slide'] for r in negatives}=={0,0x1000000},'Machine proof topology')
    return {'path':str(path),'sha256':sha(path),'actual_gzip_prefix_bound':True,'positive_cases':24,
            'negative_cases':2,'kernel_boundaries':52,'all_final_boot_component_bytes_bound':True}


def tree(root):
    rows={}
    def visit(folder):
        for path in sorted(folder.iterdir()):
            info=path.lstat();name='/'+path.relative_to(root).as_posix()
            check('..' not in PurePosixPath(name).parts,'Unsafe extracted rootfs path')
            if stat.S_ISLNK(info.st_mode):row={'kind':'link','target':os.readlink(path)}
            elif stat.S_ISREG(info.st_mode):row={'kind':'file','bytes':info.st_size,'sha256':sha(path)}
            elif stat.S_ISDIR(info.st_mode):row={'kind':'directory'};visit(path)
            else:raise ValueError('Unexpected rootfs node: '+name)
            rows[name]=row
    visit(root);return rows


def verify_filesystem(partition,folder,paths,run):
    before_img=folder/('parent.'+partition+'.raw');after_img=folder/('actual.'+partition+'.raw')
    evidence=folder/(partition+'-independent');evidence.mkdir()
    inventories=[];metadatas=[];roots=[]
    for label,image in [('before',before_img),('after',after_img)]:
        run(['/usr/sbin/e2fsck','-f','-n',image],partition+'-'+label+'-readonly-fsck')
        directory=evidence/label;directory.mkdir()
        run(['/usr/sbin/debugfs','-R','rdump / '+str(directory),image],partition+'-'+label+'-dump')
        items=tree(directory);check(len(items)>(3000 if partition=='system' else 200),'Incomplete actual '+partition+' tree')
        inventory=metadata_inventory(image,items,evidence,label,
                                     lambda command,suffix:run(command,partition+'-'+suffix))
        # Include filesystem root, which rdump's child tree does not inventory.
        root=parse_metadata(run(['/usr/sbin/debugfs','-R','stat /',image],partition+'-'+label+'-root-stat'),'/')
        roots.append(root)
        inventories.append(items);metadatas.append(inventory)
        write_json(evidence/(label+'-tree.json'),items)
    before,after=inventories;oldmeta,newmeta=metadatas
    check(roots[0]==roots[1],'Filesystem root owner/mode/label changed: '+partition)
    changed=sorted(k for k in before.keys()&after.keys() if before[k]!=after[k])
    added=sorted(after.keys()-before.keys());removed=sorted(before.keys()-after.keys())
    expect_changed=[LID] if partition=='system' else sorted([MODULE,LOADER])
    expect_added=[RC] if partition=='system' else []
    check((changed,added,removed)==(expect_changed,expect_added,[]),'Unexpected complete '+partition+' payload delta')
    for name in before:check(oldmeta[name]==newmeta[name],'Existing actual owner/mode/label changed: '+name)
    if partition=='system':
        check(newmeta[RC]==oldmeta['/system/etc/init/bootstat.rc'],'Display RC actual metadata differs from reviewed init template')
        payload={LID:paths['lid'],RC:paths['display_rc']}
        check(before[NAV]['sha256']==after[NAV]['sha256']==NAV_SHA and
              before[FRAMEWORK]['sha256']==after[FRAMEWORK]['sha256']==FRAMEWORK_SHA,'Inherited Navigation18/framework changed')
        check(not any(re.search(r'/ROCReleaseLid/.+\.(?:odex|vdex|oat|art)$',x) for x in after),'Stale Lid preopt payload')
        runtime=[name for name,row in before.items() if row['kind']=='file' and re.search(r'\.(?:art|oat|odex|vdex|prof)$',name)]
        check(runtime and all(before[name]==after[name] for name in runtime),'Inherited complete ART/preopt/profile byte change')
        sdk=NATIVE/'prebuilts/sdk/tools/linux'
        for relative,value in SDK_PINS.items():check(sha(NATIVE/relative)==value,'Frozen Android signing tool changed')
        apk=evidence/'after'/LID.lstrip('/')
        signature=run([NATIVE/'prebuilts/jdk/jdk9/linux-x86/bin/java','-Xmx256m','-jar',sdk/'lib/apksigner.jar',
                       'verify','--min-sdk-version','29','--max-sdk-version','29','--verbose','--print-certs',apk],
                       'actual-installed-Lid4-Android10-signature')
        check(re.findall(r'certificate SHA-256 digest: (\w+)',signature)==[CERT],'Actual installed Lid4 production signer')
        run([sdk/'bin/zipalign','-c','4',apk],'actual-installed-Lid4-alignment')
    else:payload={MODULE:paths['module'],LOADER:paths['android_loader']};runtime=[]
    for name,path in payload.items():check(after[name]['kind']=='file' and after[name]['sha256']==sha(path),'Actual installed artifact mismatch: '+name)
    return {'before_nodes':len(before),'after_nodes':len(after),'changed':changed,'added':added,'removed':removed,
            'all_original_owners_modes_labels_preserved':True,'inherited_runtime_files_byte_exact':len(runtime),
            'before_tree_sha256':sha(evidence/'before-tree.json'),'after_tree_sha256':sha(evidence/'after-tree.json')}


def main(args):
    constrained();started=time.monotonic()
    check(args.work.is_dir() and args.output.is_dir(),'Producer work/output missing')
    destination=fresh(args.output/'independent-verify.json');folder=fresh(args.work/'independent-verification');folder.mkdir()
    report={'schema':'roc.h700.twelve-model-independent.v1','passed':False,'independent':True,
      'physical_display_accepted':False,'physical_input_accepted':False,'physical_navigation_accepted':False,
      'all_H700_models_accepted':False,'device_accessed':False,'images_modified':False}
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(NATIVE/'prebuilts/sdk/tools/linux/lib64')
    def run(command,label):
        p=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
        path=folder/(label+'.txt');check(not path.exists(),'Duplicate verification log');path.write_text(p.stdout)
        check(p.returncode==0,'Readonly command failed: '+label+'; '+p.stdout[-1000:]);return p.stdout
    try:
        print('PHASE=verify_frozen_component_semantics',flush=True)
        prep_path=args.output/'preparation.json';result_path=args.output/'image-result.json'
        prep_sha,result_sha=sha(prep_path),sha(result_path);prep,result=read_json(prep_path),read_json(result_path)
        check(result['preparation_sha256']==prep_sha,'Preparation/image receipt mismatch')
        check(Path(prep['work'])==args.work and Path(prep['output'])==args.output,'Preparation belongs to another workspace')
        check(sha(args.work/'integration.json')==prep['integration_sha256'],'Prepared integration receipt changed')
        paths,hashes,receipts=inputs_check(prep,result)
        raw=ordinary(result['raw']);packed=ordinary(result['image'])
        check(raw==args.work/NAME and packed==args.output/(NAME+'.gz') and raw.stat().st_size==RAW_BYTES,
              'Foreign output paths/length')
        check(packed.stat().st_size==result['bytes'] and sha(packed)==result['sha256'],'Delivered gzip identity')
        print('PHASE=complete_gzip_sparse_expansion_and_raw_byte_comparison',flush=True)
        with gzip.open(packed,'rb') as reader,raw.open('rb') as compare:
            actual=stream(reader,folder,'actual',compare=compare,complete=True)
        check(actual['sha256']==result['raw_sha256'],'Entire expanded raw digest mismatch')
        check(all(result['ranges'][name]=={'offset':offset,'bytes':length,'sha256':actual['ranges'][name]}
                  for name,(offset,length) in RANGES.items()),'Complete range receipt mismatch')
        check(set(result['ranges'])==set(RANGES),'Missing/extra reported range')
        check(actual['ranges']['prefix']==prep['prefix_sha256'] and actual['ranges']['system']==prep['system']['sha256']
              and actual['ranges']['vendor']==prep['vendor']['sha256'],'Prepared/actual partition mismatch')
        gpt=verify_gpt(actual['head'],actual['tail'])
        print('PHASE=verify_exact_parent_and_extract_independent_ranges',flush=True)
        with ordinary(BASE).open('rb') as reader:parent=stream(reader,folder,'parent')
        check(parent['sha256']==BASE_SHA and parent['ranges']==PARENT_SHA,'Fixed accepted Test7 parent changed')
        check(actual['ranges']['userdata']==PARENT_SHA['userdata'] and actual['ranges']['backup_gpt']==PARENT_SHA['backup_gpt'],
              'Userdata/backup GPT changed')
        check(gpt==verify_gpt(parent['head'],parent['tail']),'GPT layout changed')
        print('PHASE=independent_actual_prefix_parsers_and_36_model_routes',flush=True)
        actual_prefix=(folder/'actual.prefix.raw').read_bytes()
        prefix=verify_prefix((folder/'parent.prefix.raw').read_bytes(),actual_prefix,paths,receipts,folder)
        handoff=bind_handoff_proof(args.output,result,actual_prefix)
        print('PHASE=independent_complete_system_and_vendor_payload_metadata',flush=True)
        filesystems={name:verify_filesystem(name,folder,paths,run) for name in ('system','vendor')}
        check(sha(prep_path)==prep_sha and sha(result_path)==result_sha,'Producer receipts changed during verification')
        check(sha(args.output/'final-handoff.json')==handoff['sha256'],'Final handoff proof changed during verification')
        check(all(sha(name)==value for name,value in read_json(args.output/'final-handoff.json')['controls'].items()),
              'Final machine proof controls changed during verification')
        check(sha(packed)==result['sha256'],'Delivered gzip changed during verification')
        inputs_check(prep,result)
        report.update(passed=True,image=str(packed),image_sha256=result['sha256'],raw_sha256=actual['sha256'],
          raw_bytes=actual['bytes'],expanded_raw=str(folder/'expanded.raw'),raw_equals_entire_gzip_stream=True,
          ranges=actual['ranges'],parent_raw_sha256=parent['sha256'],GPT=gpt,prefix=prefix,filesystems=filesystems,
          component_hashes=hashes,component_artifacts_bound_to_test_receipts=True,
          preparation_sha256=prep_sha,image_result_sha256=result_sha,
          Navigation18_framework_dual_ABI_ART_byte_exact_parent=True,
          final_handoff=handoff,
          elapsed_seconds=time.monotonic()-started)
        write_json(destination,report);print('TWELVE_MODEL_INDEPENDENT_PASS',flush=True)
    except BaseException as exc:
        report.update(error=repr(exc),elapsed_seconds=time.monotonic()-started)
        write_json(folder/'failed-attempt.json',report);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args())
