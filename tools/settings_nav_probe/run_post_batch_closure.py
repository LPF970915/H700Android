"""Run remaining guarded deep-dialog tests and one final controller Restart."""
import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from audit import OUT


def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True);p.add_argument('--navigation-version',type=int,required=True)
    p.add_argument('--completed-running-detail',type=Path)
    p.add_argument('--resume-closure',type=Path)
    p.add_argument('--information-resume-receipt',type=Path)
    p.add_argument('--stage-delta-review',type=Path)
    p.add_argument('--native-framework',action='store_true')
    p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:p.error('--execute required; includes a controller-confirmed Restart')
    batch=json.loads(args.batch.read_text(encoding='utf8'))
    if batch['status']!='COMMANDS_COMPLETED_EVIDENCE_REVIEW_REQUIRED':
        raise RuntimeError('The preceding navigation batch is incomplete')
    tag='native'+str(args.navigation_version)+'-closure-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    folder=OUT/tag;folder.mkdir();output=folder/'closure.json'
    steps=[('running-service-detail',['check_running_service_detail.py','--tag',tag]),
           ('app-action-rows',['check_app_action_rows.py','--tag',tag]),
           ('toolbar-menu-gaps',['followup.py',str(OUT/'notouch-toolbar-menu-plan-20261027.json')]),
           ('remaining-information-menus',['check_remaining_information_menus.py','--tag',tag]),
           ('ringtone-add',['check_ringtone_add_cancel.py','--tag',tag]),
           ('credential-confirmation',['check_controller_locks.py','--tag',tag,'--confirmation-pages']),
           ('final-reboot',['check_final_reboot.py','--execute','--stage',str(args.stage),'--tag',tag,
                            '--navigation-version',str(args.navigation_version)])]
    result={'status':'RUNNING','preceding_batch':str(args.batch),'stage':str(args.stage),'steps':[],
            'navigation_version':args.navigation_version,
            'components_manifest_sha256':hashlib.sha256((args.stage/'components.json').read_bytes()).hexdigest()}
    if args.native_framework:
        result['native_framework_resources']=True
        for name,command in steps:
            if name=='final-reboot':command.append('--native-framework')
    if args.information_resume_receipt:
        for name, command in steps:
            if name=='remaining-information-menus':
                command.extend(['--resume-receipt',str(args.information_resume_receipt),'--stage',str(args.stage)])
    if args.completed_running_detail:
        receipt=json.loads(args.completed_running_detail.read_text(encoding='utf8'))
        components=json.loads((args.stage/'components.json').read_text())
        if (receipt.get('status')!='PASS_ACTUAL_A_RUNNING_APP_DETAILS_BUTTON_FOCUS_B_NO_STOP'
                or receipt.get('navigation_apk_sha256')!=components['system:/system/app/RGSPNavigation/RGSPNavigation.apk']
                or len(receipt.get('additional_immediate_a_trials',[]))<2):
            raise RuntimeError('Completed repeated service-detail proof does not match this stage')
        steps=[step for step in steps if step[0]!='running-service-detail']
        result['completed_running_detail']=str(args.completed_running_detail)
    if args.resume_closure:
        previous=json.loads(args.resume_closure.read_text(encoding='utf8'))
        if (previous['status']!='STOPPED_AT_ERROR'
                or previous.get('navigation_version')!=args.navigation_version):
            raise RuntimeError('Closure continuation must match the same immutable stage')
        if previous.get('components_manifest_sha256')!=result['components_manifest_sha256']:
            if not args.stage_delta_review:raise RuntimeError('Stage changed without exact compatibility review')
            delta=json.loads(args.stage_delta_review.read_text(encoding='utf8'))
            if (delta.get('status')!='PASS_ONLY_NO_TOUCH_VENDOR_POLICY_OLD_COMPONENTS_AND_SYSTEM_IMAGE_IDENTICAL'
                    or delta.get('old_components_manifest_sha256')!=previous.get('components_manifest_sha256')
                    or delta.get('new_components_manifest_sha256')!=result['components_manifest_sha256']
                    or delta.get('changed_old_components') or delta.get('removed_old_components')
                    or not delta.get('system_raw_identical')
                    or Path(delta['old_stage']).resolve()!=Path(previous['stage']).resolve()
                    or Path(delta['new_stage']).resolve()!=args.stage.resolve()):
                raise RuntimeError('Stage compatibility proof does not match this continuation')
            result['stage_delta_review']={'file':str(args.stage_delta_review),
                'sha256':hashlib.sha256(args.stage_delta_review.read_bytes()).hexdigest(),
                'scope':'Unchanged APK/library evidence retained; no-touch native toolbar and fresh input regressions required separately.'}
        inherited=previous.get('reused_steps',{}).get('steps',[])
        completed={item['name']:item for item in inherited+previous['steps']
                   if item['status']=='COMMAND_COMPLETED' and item.get('returncode')==0}
        steps=[step for step in steps if step[0] not in completed]
        result['reused_steps']={'source':str(args.resume_closure),
                                'sha256':hashlib.sha256(args.resume_closure.read_bytes()).hexdigest(),
                                'steps':list(completed.values())}
    def save():output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    save()
    for name,command in steps:
        item={'name':name,'status':'RUNNING','started':datetime.datetime.now().isoformat()};result['steps'].append(item);save()
        print('POST_BATCH_STEP',name,flush=True)
        with (folder/(name+'.log')).open('w',encoding='utf8') as log:
            done=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name(command[0]))]+command[1:],stdout=log,stderr=subprocess.STDOUT)
        item.update(status='COMMAND_COMPLETED' if done.returncode==0 else 'ERROR',returncode=done.returncode,ended=datetime.datetime.now().isoformat());save()
        if done.returncode:
            result['status']='STOPPED_AT_ERROR';save();raise RuntimeError('Post-batch stopped at '+name)
    result['status']='COMMANDS_COMPLETED_COVERAGE_RECONCILIATION_REQUIRED';save();print('POST_BATCH_RECEIPT',output,flush=True)


if __name__=='__main__':main()
