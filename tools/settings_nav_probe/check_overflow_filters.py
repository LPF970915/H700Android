"""Activate harmless display filters twice and verify the original label returns."""
import argparse
import hashlib
import json
from pathlib import Path
from audit import Audit, OUT, adb, descendants
from followup import enter
from files import focus


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True)
    parser.add_argument('--resume-receipt',type=Path);parser.add_argument('--stage',type=Path)
    args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('overflow-filters-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    result={'status':'RUNNING','items':[]};a=Audit()
    query='settings get secure location_mode; settings get global low_power'
    try:
        result['before']=adb(query)
        if args.resume_receipt:
            if not args.stage:raise ValueError('Pinned stage required')
            old=json.loads(args.resume_receipt.read_text(encoding='utf8'))
            if old['status']!='ERROR' or old['before']!=result['before'] or len(old['items'])!=2:
                raise RuntimeError('Continuation baseline mismatch')
            if any(x['status']!='PASS_ACTUAL_A_FILTER_AND_REVERSE_ORIGINAL_LABEL_RESTORED' for x in old['items']):
                raise RuntimeError('Cannot reuse incomplete filter restores')
            components=json.loads((args.stage/'components.json').read_text())
            for key,package in [('system:/system/product/priv-app/Settings/Settings.apk','com.android.settings'),('system:/system/app/RGSPNavigation/RGSPNavigation.apk','com.roc.rgsp.navtrial')]:
                active=adb('pm path '+package).strip().removeprefix('package:')
                if adb('sha256sum '+active).split()[0]!=components[key]:raise RuntimeError('Continuation component changed')
            if adb('sha256sum /system/framework/framework-res.apk').split()[0]!=components['system:/system/framework/framework-res.apk']:
                raise RuntimeError('Framework resources changed')
            result['items']=old['items'];result['continuation']={'file':str(args.resume_receipt),'sha256':hashlib.sha256(args.resume_receipt.read_bytes()).hexdigest(),'scope':'Completed filter A/reverse proofs retained; failed printer draft safely canceled and input test rerun.'}
            data,_,_,current=a.snap('printer-draft-continuation-scene')
            failed=old.get('printer_valid_input',{}).get('entry',{})
            if current['window_id']==failed.get('window_id') and current['package']=='com.android.bips' and current['window']=='根据 IP 地址添加打印机':
                if any(w.get('type')==2 for w in data['windows']):a.key('b')
                a.key('b');result['failed_draft_cancel']=a.snap('printer-draft-failed-cancel',True)[3]
                if result['failed_draft_cancel']['window_id']==current['window_id']:raise RuntimeError('Retained draft did not cancel')
        else:
            for path, choices in [
                (['位置信息','查看全部','更多选项'],('显示系统程序','隐藏系统程序')),
                (['电池','更多选项','电池用量','更多选项'],('显示完整的设备用电量','显示应用的耗电情况'))]:
                enter(a,path)
                data,root,_,state=a.snap('overflow-filter-initial',True)
                if state['package']!='com.android.settings' or state['window']!='弹出式窗口':raise RuntimeError('Expected overflow popup')
                present=[text for text in choices if any(n.get('visible') and n.get('text')==text for n in descendants(root))]
                if len(present)!=1:raise RuntimeError('Ambiguous display filter')
                initial=present[0];reverse=next(x for x in choices if x!=initial)
                item={'path':path,'initial_label':initial,'actions':[]};result['items'].append(item)
                for name in [initial,reverse]:
                    before=focus(a,name,expected_package='com.android.settings')
                    if before['focus']!=name:raise RuntimeError('Exact filter not focused')
                    a.key('a');after=a.snap('overflow-filter-applied',True)[3]
                    if after['package']!='com.android.settings' or after['window']=='弹出式窗口':raise RuntimeError('Filter A did not apply')
                    item['actions'].append({'label':name,'actual_a_focus':before,'applied':after})
                    focus(a,'更多选项',expected_package='com.android.settings');a.key('a')
                item['restored_popup']=a.snap('overflow-filter-restored',True)[3]
                item['restored_label_focus']=focus(a,initial,expected_package='com.android.settings')
                if item['restored_label_focus']['focus']!=initial:raise RuntimeError('Filter label not restored')
                a.key('b');item['b_return']=a.snap('overflow-filter-final-cancel',True)[3]
                if item['b_return']['window']=='弹出式窗口':raise RuntimeError('Filter popup did not close')
                item['status']='PASS_ACTUAL_A_FILTER_AND_REVERSE_ORIGINAL_LABEL_RESTORED'
        # An empty hostname disables Add by design. Exercise a valid draft with
        # the same physical TV-keyboard path, then focus Add without submitting.
        path=['已连接的设备','连接偏好设置','打印','默认打印服务','更多选项','添加打印机','根据 IP 地址添加打印机']
        # Its complete Settings/HAT entry was already proven by the overflow
        # child-menu receipt. Launch that same parent as setup for the extra
        # input-state test; only the IP row and editor are interaction evidence.
        setup_command='am start -n com.android.bips/.ui.AddPrintersActivity'
        a.command(setup_command)
        setup_state=a.snap('printer-draft-parent-setup')[3]
        if setup_state['package']!='com.android.bips' or setup_state['window']!='添加打印机':
            raise RuntimeError('Expected previously audited add-printer parent')
        focus(a,'根据 IP 地址添加打印机',expected_package='com.android.bips');a.key('a')
        data,root,_,entry=a.snap('printer-draft-entry',True)
        draft={'entry':entry,'positive_add_clicked':False,'typed_observations':[],
               'setup_command':setup_command,'setup_parent':setup_state,
               'scope':'Full controller parent entry retained in overflow-child receipt; this extra test checks valid-input/Add-focus/Cancel only.'}
        result['printer_valid_input']=draft
        for _ in range(3):
            if not any(w.get('type')==2 and (w.get('root') or {}).get('package')=='com.android.inputmethod.leanback' for w in data['windows']):
                raise RuntimeError('TV keyboard not shown for uncommitted printer hostname')
            a.key('d');a.key('a')
            data,root,_,state=a.snap('printer-draft-tv-character',True);draft['typed_observations'].append(state)
            enabled=any(n.get('visible') and n.get('enabled') and n.get('id')=='android:id/button1' for n in descendants(root))
            if enabled:break
        else:raise RuntimeError('Controller draft did not enable Add')
        a.key('b');data,root,_,draft['keyboard_hidden']=a.snap('printer-draft-ime-hidden',True)
        if any(w.get('type')==2 for w in data['windows']):raise RuntimeError('Printer IME did not hide')
        # Native EditText consumes left/right while moving its cursor. Once at
        # the edge, Right moves to Cancel and then Add. These direction keys do
        # not change the draft; the generic bounded lookup skips them in editors.
        draft['native_right_route']=[]
        for _ in range(12):
            _,root,node,state=a.snap('printer-draft-native-right-route')
            draft['native_right_route'].append(state)
            if node and node.get('id')=='android:id/button1' and node.get('enabled'):
                draft['enabled_add_focus']=state;break
            a.key('r')
        else:raise RuntimeError('Enabled Add not reached through native cursor/right route')
        if 'android:id/button1' not in (draft['enabled_add_focus']['focus_signature'] or ''):
            raise RuntimeError('Enabled printer Add not focused')
        draft['cancel_focus']=focus(a,'取消',expected_package='com.android.bips');a.key('a')
        draft['cancel_return']=a.snap('printer-draft-cancelled',True)[3]
        if draft['cancel_return']['package']!='com.android.bips' or draft['cancel_return']['window_id']==entry['window_id']:
            raise RuntimeError('Printer draft Cancel did not close')
        draft['status']='PASS_TV_TYPED_VALID_HOSTNAME_ENABLED_ADD_FOCUS_A_CANCEL_NO_ADD'
        result['after']=adb(query)
        if result['before']!=result['after']:raise RuntimeError('Location/power setting changed')
        result['status']='PASS_LOCATION_BATTERY_OVERFLOW_FILTER_A_REVERSE_NO_PERSISTENT_CHANGE'
    except Exception as error:result.update(status='ERROR',error=repr(error));raise
    finally:a.close();output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['status'],flush=True)


if __name__=='__main__':main()
