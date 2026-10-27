"""Run remaining controller-only regressions sequentially, stopping at any error."""
import argparse
import datetime
import json
import os
import hashlib
import subprocess
import sys
from pathlib import Path
from audit import OUT, ROOT, adb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completed-keyboard-receipt',type=Path)
    parser.add_argument('--completed-nested-receipt',type=Path)
    parser.add_argument('--apps-reuse-scan',type=Path)
    parser.add_argument('--settings-sha',help='Current reviewed Settings hash for compatible completed-body reuse')
    parser.add_argument('--resume-batch',type=Path,help='Reuse only command-completed steps from this preserved batch journal')
    parser.add_argument('--supplement-plan',type=Path,help='Reviewed remaining supplemental items, preserving the original plan')
    parser.add_argument('--navigation-version',type=int,default=34)
    parser.add_argument('--navigation-delta-review',type=Path)
    parser.add_argument('--framework-delta-review',type=Path)
    parser.add_argument('--regressions-only',action='store_true',help='Fresh Files/search/locale/WLAN-password/power checks; never reuse completed commands')
    args=parser.parse_args()
    tag='native'+str(args.navigation_version)+'-final-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    folder=OUT/tag
    folder.mkdir()
    reserve=ROOT/'out/flicker-investigation-20261026/startup-buffer-reserve'
    receipts=sorted(reserve.glob('live-two-boot-v2-*.json'),key=lambda p:p.stat().st_mtime)
    if not receipts or json.loads(receipts[-1].read_text(encoding='utf8'))['status']!='PASS_TWO_KERNEL_REBOOTS_RESERVE_ACTIVE_ZERO_GPU_IMPORT_ERRORS':
        raise RuntimeError('Production graphics candidate has not passed its two-boot gate')
    supplement=json.loads((args.supplement_plan or OUT/'native33-supplement-plan-20261026.json').read_text(encoding='utf8'))
    supplement=[item for item in supplement if 'Android 键盘 (AOSP)' not in item['path']]
    plan=folder/'supplement-plan.json'
    plan.write_text(json.dumps(supplement,ensure_ascii=False,indent=2),encoding='utf8')
    steps=[
        ('keyboard', ['explore.py','--tag',tag,'--path','系统','语言和输入法','虚拟键盘','Android 键盘 (AOSP)',
                      '--reuse-scan',str(OUT/'native33-system-developer-completed-reuse-20261026.json'),
                      '--reuse-completed','--reuse-settings-sha','df0a981784b3523e9267624b8b1a2dd22e721d3fa03c4acdbce1df574e0dae3b']),
        ('apps',['explore.py','--tag',tag,'--category','应用和通知']),
        ('app-list-search',['check_app_list_search.py','--tag',tag]),
        ('display',['explore.py','--tag',tag,'--category','显示']),
        ('keyboard-parent',['explore.py','--tag',tag,'--path','系统','语言和输入法','虚拟键盘',
                            '--reuse-scan',str(OUT/'exploration-24abf121ee.json'),
                            '--reuse-completed','--reuse-settings-sha',args.settings_sha or 'c5bb61836da4e3884dc3dbfe7afa30c6c385d0a1142e089aca0400cfc23830c3']),
        ('supplement',['followup.py',str(plan)]),
        ('conditional-network',['check_conditional_network_forms.py','--tag',tag]),
        ('files-apk',['check_file_apk_cancel.py','--tag',tag]),
        ('search',['check_settings_search.py','--tag',tag]),
        ('locale',['check_locale_confirm.py','--tag',tag]),
        ('wifi-password',['check_wifi_password.py','--tag',tag]),
        ('power-menu',['check_power_menu.py','--tag',tag]),
    ]
    if args.regressions_only:
        if args.resume_batch:raise ValueError('Fresh regressions cannot reuse a prior batch')
        steps=[step for step in steps if step[0] in ('files-apk','search','locale','wifi-password','power-menu')]
    if args.completed_keyboard_receipt:
        keyboard=json.loads(args.completed_keyboard_receipt.read_text(encoding='utf8'))
        if keyboard.get('status')!='PASS_LEGACY_KEYBOARD_ROOT_AND_SAFE_CHILDREN_RESCANNED':
            raise RuntimeError('Keyboard continuation was not completed')
        steps=[('nested-editors',['check_nested_editor_cancel.py','--tag',tag])]+steps[1:]
    if args.completed_nested_receipt:
        nested=json.loads(args.completed_nested_receipt.read_text(encoding='utf8'))
        if not args.completed_keyboard_receipt or nested.get('status')!='PASS_STYLE_DIALOG_DROPDOWNS_A_CANCEL_EMPTY_DICTIONARY_KEYBOARDS_NO_SAVE':
            raise RuntimeError('Completed keyboard/nested editor receipts required')
        steps=[step for step in steps if step[0]!='nested-editors']
    if args.apps_reuse_scan:
        if not args.settings_sha:raise ValueError('Current reviewed Settings SHA required for reuse')
        for name,command in steps:
            if name=='apps':command.extend(['--reuse-scan',str(args.apps_reuse_scan),'--reuse-completed',
                                             '--reuse-settings-sha',args.settings_sha])
    result={'status':'RUNNING','tag':tag,'reserve_receipt':str(receipts[-1]),'steps':[],
            'control_transport':os.environ.get('NAV_CONTROL_TRANSPORT','uart'),
            'navigation_version':args.navigation_version}
    if args.regressions_only:result['scope']='FRESH_FILES_AND_MAIN_INPUT_REGRESSIONS_NO_COMMAND_REUSE'
    if args.resume_batch:
        previous=json.loads(args.resume_batch.read_text(encoding='utf8'))
        if previous['status'] not in ('STOPPED_AT_ERROR','COMMANDS_COMPLETED_EVIDENCE_REVIEW_REQUIRED') or not args.settings_sha:
            raise ValueError('A preserved stopped/completed journal and pinned Settings SHA are required')
        path=adb('pm path com.android.settings').strip().removeprefix('package:')
        if adb('sha256sum '+path).split()[0]!=args.settings_sha:raise RuntimeError('Settings changed before batch continuation')
        if args.navigation_version!=previous.get('navigation_version',34):
            if not args.navigation_delta_review:raise RuntimeError('Navigation version changed without a reviewed source delta')
            delta=json.loads(args.navigation_delta_review.read_text(encoding='utf8'))
            if delta.get('status')!='PASS_ONLY_STATS_ROW_IDENTITY_LIFECYCLE_DUMP_AND_VERSION' or not delta.get('inverse_exact_match') or not delta.get('other_behavior_unchanged'):
                raise RuntimeError('Unreviewed navigation change; prior command steps cannot be reused')
            result['navigation_delta_review']={'file':str(args.navigation_delta_review),
                'sha256':hashlib.sha256(args.navigation_delta_review.read_bytes()).hexdigest()}
        navigation=adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        if 'navigationVersion='+str(args.navigation_version)+' mode=' not in navigation:
            raise RuntimeError('Expected navigation helper is not active before continuation')
        inherited=previous.get('reused_command_steps',{}).get('steps',[])
        completed_by_name={item['name']:item for item in inherited+previous['steps']
            if item['status']=='COMMAND_COMPLETED' and item.get('returncode')==0}
        completed=list(completed_by_name.values())
        done={item['name'] for item in completed}
        steps=[step for step in steps if step[0] not in done]
        result['reused_command_steps']={'source':str(args.resume_batch),
            'source_sha256':hashlib.sha256(args.resume_batch.read_bytes()).hexdigest(),'steps':completed,
            'inherited_journal':previous.get('reused_command_steps'),
            'scope':'Original immutable logs and completed receipts retained; failed/unfinished commands are never reused'}
        if args.framework_delta_review:
            delta=json.loads(args.framework_delta_review.read_text(encoding='utf8'))
            if delta.get('status')!='PASS_ONLY_ALREADY_UNLINKED_BINDER_RESET_GUARD':
                raise RuntimeError('Unreviewed framework lifecycle change')
            result['framework_delta_review']={'file':str(args.framework_delta_review),
                'sha256':hashlib.sha256(args.framework_delta_review.read_bytes()).hexdigest()}
    if args.completed_keyboard_receipt:result['keyboard_continuation']=str(args.completed_keyboard_receipt)
    if args.completed_nested_receipt:result['nested_editors']=str(args.completed_nested_receipt)
    target=folder/'batch.json'
    def save():target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    save()
    for name,args in steps:
        item={'name':name,'status':'RUNNING','started':datetime.datetime.now().isoformat(),'args':args}
        result['steps'].append(item);save()
        print('FINAL_BATCH_STEP',name,flush=True)
        with (folder/(name+'.log')).open('w',encoding='utf8') as log:
            completed=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name(args[0]))]+args[1:],
                                     stdout=log,stderr=subprocess.STDOUT)
        item.update(status='COMMAND_COMPLETED' if completed.returncode==0 else 'ERROR',returncode=completed.returncode,
                    ended=datetime.datetime.now().isoformat())
        save()
        if completed.returncode:
            result['status']='STOPPED_AT_ERROR';save()
            raise RuntimeError('Controller batch stopped: '+name+'; evidence '+str(folder))
    result['status']='COMMANDS_COMPLETED_EVIDENCE_REVIEW_REQUIRED';save()
    print('FINAL_BATCH_RECEIPT',target,flush=True)


if __name__=='__main__':main()
