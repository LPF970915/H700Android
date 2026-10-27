"""Discover safe Settings submenus through controller HAT/A/B, never accessibility clicks."""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from audit import Audit, OUT, adb, descendants, label, signature, viewport

CATALOG=json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
APP_LABELS=set(json.loads((OUT/'app-labels.json').read_text(encoding='utf-8'))) if (OUT/'app-labels.json').exists() else set()
DIALOG_MENUS={'选择调试应用','选择模拟位置信息应用'}
SAFE_MENUS={
 '开发者选项','内存','正在运行的服务','桌面备份密码','WLAN','WLAN 偏好设置',
 '已保存的网络','WLAN 流量用量','连接偏好设置','与新设备配对','蓝牙',
 '权限管理器','应用权限','加密与凭据','屏幕锁定','PIN码','图案','密码',
 '字体大小','显示大小','屏幕超时','亮度','壁纸','媒体音量','默认应用',
 '特殊应用权限','应用信息','查看所有应用','所有应用','存储和缓存','存储空间和缓存',
 '打开支持的链接','通知','权限','其他权限','电池用量','应用流量使用情况',
 '版本','型号和硬件','Android 版本','设备名称','状态','法律信息','更多选项',
 '添加网络','添加 VPN','添加帐号','重置选项','重置 WLAN、移动数据网络和蓝牙设置',
 '重置应用偏好设置','清除所有数据（恢复出厂设置）',
 '投射','通过蓝牙收到的文件','默认打印服务',
 '私人 DNS','锁定屏幕消息','内部共享存储空间','ROMS',
 '语言和输入法','日期和时间','语言','虚拟键盘','实体键盘','屏幕键盘','文字转语音输出',
 '搜索设置',
}
NO_ACTIVATE={
 '向上导航','开启','关闭','使用 WLAN / 开启','使用 WLAN / 关闭',
 '打开','停用','启用','强行停止','卸载','清除存储空间','清除缓存','忘记',
 '无','滑动','清除所有数据','重置设置','恢复出厂设置','重置应用',
 '连接','保存','确定','完成','下一步','开始','停止','删除','移除',
}
HAZARD=re.compile(r'加密|生成|捕获|提交|录制|恢复默认|清除.*授权|撤消|撤销|立即|格式化|弹出|重新启动|重启|强制|卸载|停用|清除缓存|删除')


def new_ui_crash(before,after):
    previous=set(before.splitlines())
    added='\n'.join(line for line in after.splitlines() if line not in previous)
    return bool(after!=before and re.search(
        r'Process: (?:com\.android\.(?:settings(?:\.intelligence)?|permissioncontroller|packageinstaller|systemui|documentsui|inputmethod\.latin)|com\.google\.android\.permissioncontroller)(?:,|\s)',added))


def new_ui_service_fault(before,after):
    previous=set(before.splitlines())
    added='\n'.join(line for line in after.splitlines() if line not in previous)
    return bool(after!=before and re.search(
        r'am_(?:wtf|crash|anr)\s*:.*(?:com\.android\.(?:settings(?:\.intelligence)?|permissioncontroller|packageinstaller|systemui|documentsui|inputmethod\.latin)|com\.google\.android\.permissioncontroller)(?:,|\s|\])',added))


SERVICE_FAULT_QUERY="logcat -d -b events -v threadtime am_wtf:I am_crash:I am_anr:I '*:S'"

def dialog(root):
    return any(n.get('id','').endswith(('/alertTitle','/buttonPanel')) for n in descendants(root))

def page_key(root,state):
    titles=[]
    for n in descendants(root):
        if n.get('visible') and n.get('id','').endswith(('/alertTitle','/decor_title')):
            titles.append(n.get('text',''))
    return (state['package'],state['window'],state.get('window_id'),tuple(titles))

def fingerprint(root,state):
    # The controller also exposes clickable rows whose native focusable flag is
    # false. Legacy PreferenceActivity fragments can retain both title and
    # window ID, so omitting those rows makes different pages look identical.
    rows=[label(n) for n in descendants(root) if n.get('visible') and n.get('clickable')]
    # Window IDs protect live transitions, but are not part of template dedup.
    headers=tuple(n.get('text','') for n in descendants(root)
        if n.get('visible') and n.get('id','').endswith('/entity_header_title'))
    key=page_key(root,state)
    return (key[0],key[1],key[3],headers,tuple(rows[:8]))


def same_window_parent_return(before,current,parent_labels,child_labels):
    """Accept a scrolled parent only with a parent-specific actionable row."""
    if current==before:return True
    if current[:4]!=before[:4]:return False
    common={'向上导航','搜索设置','更多选项'}
    distinct=set(parent_labels)-set(child_labels)-common
    rows=set(current[-1])-common
    return bool(rows & distinct) and rows.issubset(set(parent_labels))

def toggle(n):
    return any(x.get('checkable') or 'Switch' in x.get('class','') for x in descendants(n))


def notification_channel_menu(n,state):
    # NotificationSettingsBase builds MasterSwitchPreference: the body opens
    # ChannelNotificationSettings; only its separate widget_frame toggles it.
    if state['package']!='com.android.settings' or state['window'] not in ('通知','应用通知'):
        return False
    children=list(descendants(n))
    return (n.get('clickable') and any(x.get('visible') and x.get('id','').endswith('/two_target_divider') for x in children)
            and any(x.get('id')=='com.android.settings:id/switchWidget' for x in children)
            and any(x.get('id')=='android:id/widget_frame' and x.get('clickable') for x in children))

def in_toolbar(root,target):
    if not target: return False
    def walk(node,inside=False):
        inside=inside or 'Toolbar' in node.get('class','') or node.get('id','').endswith(('/action_bar','/toolbar'))
        if (node.get('bounds')==target.get('bounds') and node.get('id')==target.get('id')
                and node.get('class')==target.get('class')): return inside
        return any(walk(child,inside) for child in node.get('children',[]))
    return walk(root)

def classify(n,root,state,in_dialog):
    title=label(n)
    if in_dialog or not n.get('enabled') or n.get('editable'): return 'focus-only'
    if n.get('range'): return 'focus-only-range'
    if any(x.get('range') and not x.get('class','').endswith('ProgressBar')
            for x in descendants(n)): return 'focus-only-range-container'
    if not n.get('clickable'): return 'information-focus'
    # These exact toolbar actions only open UI. Keep every other Button guarded.
    if title=='更多选项': return 'menu'
    if title=='搜索设置' and state['package']=='com.android.settings' and in_toolbar(root,n):
        # Every toolbar delegates to the same SearchMenuController. The full
        # query/result/clear/Back flow has a dedicated controller-only test;
        # this inventory still requires each toolbar button to be focused.
        return 'focus-only-search-template-tested-separately'
    if n.get('id','').endswith('/vpn_create'): return 'dialog'
    if title=='添加语言' and n.get('id')=='com.android.settings:id/add_language': return 'menu'
    if re.fullmatch(r'com\.android\.settings:id/app[123]_view',n.get('id','')) and any(
            x.get('id')=='com.android.settings:id/app_title' and x.get('text') for x in descendants(n)): return 'menu'
    if re.match(r'查看全部\s*\d+\s*个应用',title) or re.match(r'查看过去.*所有应用',title): return 'menu'
    if n.get('class','').endswith('Button'): return 'focus-only-action'
    # These runtime-created preferences are absent from the XML catalog.
    # Native controllers only open a chooser/help dialog on click.
    if title in ('指针速度','默认拼写检查工具','键盘快捷键帮助程序'):
        return 'dialog'
    if (state['package']=='com.android.settings' and state['window']=='个人字典'
            and title in ('所有语言','中文 (中国,#Hans)','英语 (美国)')
            and n.get('class')=='android.widget.LinearLayout'):
        return 'menu'
    if title=='加密与凭据': return 'menu'
    if HAZARD.search(title): return 'focus-only-action'
    if title in ('WLAN','蓝牙'): return 'menu'
    if notification_channel_menu(n,state):return 'menu'
    if toggle(n): return 'focus-only'
    if title in NO_ACTIVATE: return 'focus-only'
    if title=='高级' and state['package']=='com.android.settings': return 'expand'
    if title in DIALOG_MENUS or n.get('class')=='android.widget.Spinner': return 'dialog'
    if re.match(r'查看过去.*所有应用',title): return 'menu'
    if state['window']=='应用信息' and not any(x.get('id','').endswith('/entity_header_title') for x in descendants(root)):
        if n.get('clickable') and n.get('class')=='android.widget.LinearLayout': return 'menu'
    if title in APP_LABELS and any(x.get('id')=='android:id/icon' for x in descendants(n)): return 'menu'
    if 'permissioncontroller' in state['package'] and n.get('class')=='android.widget.LinearLayout':
        if any(x.get('id','').endswith(('/title','/permission_title')) for x in descendants(n)): return 'menu'
    if state['package']=='com.android.settings' and state['window']=='存储' and title in (
            '照片和视频','音乐和音频','游戏','电影和电视应用','影视应用','其他应用','文件','系统'):
        return 'dialog' if title=='系统' else 'menu'
    if title in SAFE_MENUS: return 'menu'
    if HAZARD.search(title): return 'focus-only-action'
    if re.match(r'查看全部\s*\d+\s*个应用',title): return 'menu'
    records=CATALOG.get(title,[])
    if any('FooterPreference' in r['type'] for r in records): return 'information-focus'
    if any('DialogPreference' in r['type'] or 'ListPreference' in r['type'] or 'DropDownPreference' in r['type'] or
           'RingtonePreference' in r['type'] for r in records): return 'dialog'
    if any(r['type'].endswith('PreferenceScreen') for r in records): return 'menu'
    if any(r.get('fragment') for r in records): return 'menu'
    return 'unclassified'

class Explorer:
    def __init__(self,audit,run_id='root',reuse=None):
        self.a=audit
        self.pages=[]; self.seen=set()
        self.max_pages=400
        self.output=OUT/('exploration-'+hashlib.sha1(run_id.encode()).hexdigest()[:10]+'.json')
        self.reuse=reuse or {}
        self.crash_baseline=adb('logcat -d -b crash -v threadtime')
        self.service_fault_baseline=adb(SERVICE_FAULT_QUERY)

    def save(self):
        self.output.write_text(json.dumps({'pages':self.pages},ensure_ascii=False,indent=2),encoding='utf-8')

    def goto_root(self):
        self.a.key('home')
        _,root,_,state=self.a.snap('go-home')
        if state['package']!='com.overdevs.at4k':
            self.a.key('wake'); self.a.key('a'); self.a.key('home')
        for k in ['u']*8+['l']*3+['r','a']: self.a.key(k)
        _,root,_,state=self.a.snap('settings-root',True)
        if not any(n.get('id','').endswith('/search_action_bar') for n in descendants(root)):
            raise RuntimeError('Settings homepage was not reached: '+str(state))

    def visit(self,path,forced_dialog=False,depth=0,*,resume=None):
        if depth>12 or len(self.pages)>=self.max_pages: raise RuntimeError('Traversal bound reached')
        tag=hashlib.sha1('/'.join(path).encode()).hexdigest()[:12]
        data,root,focus,state=self.a.snap(tag+'-entry',True)
        origin=page_key(root,state)
        cached=self.reuse.get(tuple(path))
        if cached and fingerprint(root,state)==cached['fingerprint']:
            # Preserve the original version/evidence; only entry and return are
            # tested again. Caller explicitly pins the unchanged Settings APK.
            record=copy.deepcopy(cached['page'])
            record['reused_scan']={k:v for k,v in cached.items() if k not in ('page','fingerprint')}
            record['reused_scan']['live_reentry']=state
            self.pages.append(record);self.save()
            print('REUSED_UNCHANGED_PAGE '+('/'.join(path)),flush=True)
            return
        if resume:
            old=resume['page']
            installed=adb('pm path com.android.settings').strip().removeprefix('package:')
            if adb('sha256sum '+installed).split()[0]!=resume['settings_apk_sha256']:
                raise ValueError('Settings changed before walk continuation')
            if (old['path']!=path or old['status']!='RUNNING' or old['dialog']
                    or page_key(root,state)!=page_key({},old['entry'])
                    or resume['direction'] not in ('d','u')):
                raise ValueError('Continuation does not match the current unfinished list')
            record=copy.deepcopy(old)
            record.setdefault('continuations',[]).append({k:v for k,v in resume.items() if k!='page'} | {'live_entry':state})
        else:
            record={'path':path,'entry':state,'controls':{},'visible_controls':{},'branches':[],
                    'dialog':forced_dialog or dialog(root),'status':'RUNNING'}
        self.pages.append(record); self.save()
        print('PAGE '+str(len(self.pages))+' '+('/'.join(path))+' '+state['window'],flush=True)
        if state['package'] not in ('com.android.settings','com.android.permissioncontroller',
            'com.google.android.permissioncontroller','com.android.systemui','android',
            'com.android.inputmethod.latin','com.android.documentsui','com.android.wallpaperpicker',
            'com.android.wallpaper','com.android.printspooler','com.android.providers.media',
            'com.android.bluetooth','com.android.bips'):
            record['status']='EXTERNAL_APP_ENTRY'; self.save(); return
        fp=fingerprint(root,state)
        if fp in self.seen:
            record['status']='DUPLICATE_TEMPLATE'; self.save(); return
        self.seen.add(fp)
        # Hide an automatically shown IME before testing the form's button navigation.
        if any(w.get('type')==2 for w in data['windows']):
            record['ime_shown']=True
            self.a.key('b')
            _,root,focus,state=self.a.snap(tag+'-hide-ime')
        # Empty lists and toolbar-only pages can require a horizontal first move.
        if not focus:
            record['initial_direction_checks']=[]
            for key in ('u','d','l','r'):
                self.a.key(key)
                _,root,focus,state=self.a.snap(tag+'-initial-'+key)
                record['initial_direction_checks'].append(state)
                if focus: break
        # Include the toolbar/up control, then descend through every reachable row.
        repeated=0; previous=None
        for _ in range(0 if resume else 400):
            self.a.key('u')
            _,root,focus,state=self.a.snap(tag+'-up')
            now=(state['focus_signature'],viewport(root))
            if now==previous: repeated+=1
            else: repeated=0
            previous=now
            if repeated>=1: break
        repeated=0; previous=None
        processed=set(record['controls']) if resume else set()
        if resume:
            completed={b['label'] for b in record['branches']
                       if b.get('result') in ('ENTERED_AND_SCANNED','NO_TRANSITION')}
            # STOP_AUDIT can fire after saving a focused menu but before A, or
            # while its child is still being scanned. Such a branch is pending.
            processed -= {sig for sig,c in record['controls'].items()
                          if c['action'] in ('menu','dialog') and c['label'] not in completed}
        walk_direction=resume['direction'] if resume else 'd'
        held_boundaries=set()
        for step in range(1000):
            data,root,focus,state=self.a.snap(tag+'-step')
            if walk_direction=='r' and not in_toolbar(root,focus): break
            if page_key(root,state)!=origin:
                record['status']='UNEXPECTED_PAGE_CHANGE'; record['unexpected']=state; self.save()
                raise RuntimeError('Unexpected page change: '+str(state))
            for n in descendants(root):
                if n.get('visible') and (n.get('focusable') or n.get('clickable')):
                    record['visible_controls'][signature(n)]={
                        'label':label(n),'enabled':n.get('enabled'),'focusable':n.get('focusable'),
                        'clickable':n.get('clickable'),'class':n.get('class')}
            sig=state['focus_signature']
            if sig:
                record['controls'][sig]={'label':state['focus'],'evidence':state['file'],
                                        'range':focus.get('range'),'action':classify(focus,root,state,record['dialog'])}
            # Dialog action buttons often sit side by side. Check both directions
            # without activating choices or altering a SeekBar value.
            if (record['dialog'] and sig and sig not in processed
                    and focus.get('class')!='android.widget.CheckedTextView'
                    and not any(n.get('range') for n in descendants(focus))):
                record.setdefault('horizontal_checks',[])
                for direction,reverse in [('l','r'),('r','l')]:
                    self.a.key(direction)
                    _,side,side_focus,side_state=self.a.snap(tag+'-side-'+direction)
                    record['horizontal_checks'].append(side_state)
                    side_sig=side_state['focus_signature']
                    if side_sig and side_sig!=sig:
                        record['controls'][side_sig]={'label':side_state['focus'],'evidence':side_state['file'],
                            'range':side_focus.get('range'),'action':'focus-only'}
                        self.a.key(reverse)
                        _,_,_,returned=self.a.snap(tag+'-side-return')
                        if returned['focus_signature']!=sig:
                            # Android focus edges need not be reciprocal (for example
                            # a dialog's list and action buttons). Preserve evidence;
                            # the reverse vertical pass will cover the new position.
                            record.setdefault('nonreciprocal_horizontal',[]).append(returned)
                            self.save(); break
            print(json.dumps({'path':'/'.join(path),'step':step,'focus':state['focus']},ensure_ascii=False),flush=True)
            if sig and sig not in processed and focus.get('clickable'):
                processed.add(sig)
                action=classify(focus,root,state,record['dialog'])
                if action in ('menu','dialog','expand'):
                    parent_activity=adb('dumpsys activity activities | grep mResumedActivity')
                    parent_pid=(adb('pidof '+state['package']+' || true').strip()
                                if state['package'] in ('com.android.settings','com.android.permissioncontroller') else None)
                    before_fp=fingerprint(root,state)
                    self.a.key('a')
                    _,child,_,child_state=self.a.snap(tag+'-opened',True)
                    # A fragment transaction need not create a new window, and
                    # its first accessibility snapshot can still be the parent.
                    for settle in range(3):
                        if fingerprint(child,child_state)!=before_fp: break
                        if action=='expand': break
                        time.sleep(.2)
                        _,child,_,child_state=self.a.snap(tag+'-opened-settle')
                    branch={'label':state['focus'],'kind':action,'entry':child_state}
                    record['branches'].append(branch); self.save()
                    if action=='expand':
                        previous=None; repeated=0; continue
                    child_activity=adb('dumpsys activity activities | grep mResumedActivity')
                    crash=adb('logcat -d -b crash -v threadtime')
                    service_fault=adb(SERVICE_FAULT_QUERY)
                    current_pid=(adb('pidof '+state['package']+' || true').strip() if parent_pid else None)
                    java_fault=new_ui_crash(self.crash_baseline,crash)
                    service_failure=new_ui_service_fault(self.service_fault_baseline,service_fault)
                    pid_changed=bool(parent_pid and current_pid!=parent_pid)
                    if java_fault or service_failure or pid_changed:
                        crash_file=self.output.with_suffix('.native-crash.log')
                        crash_file.write_text(crash+'\nSERVICE_FAULT_EVENTS\n'+service_fault,encoding='utf8')
                        branch['result']='NATIVE_UI_FAILURE';record['status']='NATIVE_UI_FAILURE'
                        branch['failure_evidence']={'new_java_crash':java_fault,
                            'new_service_fault':service_failure,'process_changed':pid_changed}
                        branch['parent_pid_before']=parent_pid;branch['parent_pid_after']=current_pid
                        record['crash_log']=crash_file.name;self.save()
                        raise RuntimeError('Native UI crashed while opening '+str(path+[state['focus']]))
                    self.crash_baseline=crash
                    self.service_fault_baseline=service_fault
                    if (fingerprint(child,child_state)==before_fp and child_activity==parent_activity
                            and child_state.get('window_id')==state.get('window_id')):
                        branch['result']='NO_TRANSITION'; self.save()
                    else:
                        if child_state['package']=='com.overdevs.at4k':
                            branch['result']='EXITED_SETTINGS'; record['status']='CHILD_EXITED_SETTINGS'; self.save()
                            raise RuntimeError('Settings exited on '+str(path+[state['focus']]))
                        child_index=len(self.pages)
                        self.visit(path+[state['focus']],action=='dialog',depth+1)
                        branch['result']='ENTERED_AND_SCANNED'
                        same_window_child=page_key(child,child_state)==origin
                        parent_labels={c['label'] for c in record['controls'].values()} | {c['label'] for c in record['visible_controls'].values()} | set(before_fp[-1])
                        child_labels={c['label'] for c in self.pages[child_index]['controls'].values()} | set(fingerprint(child,child_state)[-1])
                        popup_owner=next((p for p in self.pages if p['path']==path[:-1]),None) if state['window']=='弹出式窗口' and path[-1]=='更多选项' else None
                        def returned_to_parent(current_root,current_state):
                            if same_window_child:
                                return same_window_parent_return(before_fp,fingerprint(current_root,current_state),parent_labels,child_labels)
                            return (page_key(current_root,current_state)==origin or
                                (current_state['package']==state['package']
                                 and current_state.get('window_id')==record['entry'].get('window_id')
                                 and fingerprint(current_root,current_state)[-1]==before_fp[-1]))
                        for back in range(4):
                            self.a.key('b')
                            # Observe asynchronous Activity finishes before another B;
                            # otherwise a second press can overshoot the actual parent.
                            for settle in range(10):
                                _,root,focus,current=self.a.snap(tag+'-return')
                                if returned_to_parent(root,current): break
                                if (popup_owner and page_key(root,current)==page_key({},popup_owner['entry'])):
                                    # Selecting an overflow item dismisses its popup.
                                    # Canceling its dialog returns to the owner, so
                                    # reopen the real overflow with HAT/A for the
                                    # remaining reverse scan; never press B again.
                                    owner_state=current
                                    for route in range(90):
                                        if current['focus']=='更多选项' and focus and focus.get('clickable'):break
                                        self.a.key('r' if in_toolbar(root,focus) else 'u')
                                        _,root,focus,current=self.a.snap(tag+'-popup-owner-route')
                                        if page_key(root,current)!=page_key({},popup_owner['entry']):
                                            raise RuntimeError('Popup owner routing changed page')
                                    else:raise RuntimeError('Overflow anchor not reached after child cancel')
                                    self.a.key('a');_,root,focus,current=self.a.snap(tag+'-popup-reopened',True)
                                    if fingerprint(root,current)!=before_fp:
                                        raise RuntimeError('Reopened overflow is not the original menu')
                                    origin=page_key(root,current)
                                    record.setdefault('popup_reentries',[]).append({'owner':owner_state,'popup':current,
                                        'scope':'Actual HAT/A reopens an overflow naturally dismissed by its child action'})
                                    self.save();break
                                time.sleep(.3)
                            if returned_to_parent(root,current): break
                        else:
                            record['status']='RETURN_FAILED'; self.save()
                            raise RuntimeError('Could not return to '+str(path))
                        previous=None; repeated=0
            boundary=(sig,viewport(root))
            if boundary==previous: repeated+=1
            else: repeated=0
            if repeated>=2:
                # A held HAT produces ordinary controller key repeats. Some BSP
                # lists scroll past disabled rows only after repeated key-downs.
                held_key=(walk_direction,boundary)
                if (walk_direction!='r' and held_key not in held_boundaries
                        and any(n.get('scrollable') for n in descendants(root))
                        and not any(n.get('range') for n in descendants(root))):
                    # Some native lists wrap after held repeats. One bounded
                    # held check per actual boundary avoids endless full-list
                    # cycles while still testing disabled-row scroll behavior.
                    held_boundaries.add(held_key)
                    self.a.hold(walk_direction)
                    _,held_root,_,held_state=self.a.snap(tag+'-held-boundary')
                    record.setdefault('held_boundary_checks',[]).append(held_state)
                    if (held_state['focus_signature'],viewport(held_root))!=boundary:
                        previous=None; repeated=0; continue
                if walk_direction=='d':
                    walk_direction='u'; previous=None; repeated=0
                    self.a.key('u'); continue
                if walk_direction=='u' and in_toolbar(root,focus):
                    # Vertical scans miss Search/overflow beside Up. Sweep only
                    # inside the real toolbar, never across a slider or editor.
                    for _ in range(12):
                        old=state['focus_signature']; self.a.key('l')
                        _,root,focus,state=self.a.snap(tag+'-toolbar-left')
                        if not in_toolbar(root,focus):
                            raise RuntimeError('Toolbar Left escaped its container')
                        if state['focus_signature']==old: break
                    walk_direction='r'; previous=None; repeated=0
                    record['toolbar_sweep']=True
                    continue
                break
            previous=boundary
            self.save(); self.a.key(walk_direction)
        else:
            record['status']='VERTICAL_WALK_LIMIT'; self.save()
            raise RuntimeError('Vertical walk limit: '+str(path))
        record['status']='BIDIRECTIONAL_SCAN_DONE'
        record['end']=self.a.snap(tag+'-end',True)[3]
        self.save()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--category')
    parser.add_argument('--categories',nargs='+')
    parser.add_argument('--path',nargs='+',help='A complete D-pad path below Settings')
    parser.add_argument('--tag',help='Fresh evidence namespace; preserves earlier scan receipts')
    parser.add_argument('--reuse-scan',type=Path)
    parser.add_argument('--reuse-path',nargs='+',help='Exact previously completed page, including 设置')
    parser.add_argument('--reuse-completed',action='store_true',help='Reuse every completed page only when its live fingerprint matches')
    parser.add_argument('--reuse-settings-sha',help='Require this reviewed Settings APK before reuse')
    args=parser.parse_args()
    if args.tag and not args.tag.replace('-','').isalnum():raise ValueError('Invalid fresh tag')
    a=Audit()
    bluetooth_before=None
    try:
        a.snap('audit-session-entry')  # Also verifies ADB/UART device identity.
        reuse={}
        if args.reuse_scan or args.reuse_path or args.reuse_settings_sha or args.reuse_completed:
            if not (args.reuse_scan and args.reuse_settings_sha and bool(args.reuse_path)!=bool(args.reuse_completed)):
                raise ValueError('Reuse requires a scan, pinned Settings hash, and either one path or completed pages')
            installed=adb('pm path com.android.settings').strip().removeprefix('package:')
            if adb('sha256sum '+installed).split()[0]!=args.reuse_settings_sha:raise ValueError('Settings changed since the reviewed scan')
            saved=json.loads(args.reuse_scan.read_text(encoding='utf-8'))
            selected=[p for p in saved['pages'] if p['status']=='BIDIRECTIONAL_SCAN_DONE'] if args.reuse_completed else [next(p for p in saved['pages'] if p['path']==args.reuse_path)]
            for page in selected:
                if page['status']!='BIDIRECTIONAL_SCAN_DONE':raise ValueError('Incomplete pages cannot be reused')
                raw=json.loads((OUT/page['entry']['file']).read_text(encoding='utf-8'))
                old_root=next(w['root'] for w in raw['windows'] if w.get('id')==page['entry'].get('window_id') and w.get('root'))
                reuse[tuple(page['path'])]={'page':page,'fingerprint':fingerprint(old_root,page['entry']),
                    'source':str(args.reuse_scan),'source_sha256':hashlib.sha256(args.reuse_scan.read_bytes()).hexdigest(),
                    'settings_apk_sha256':args.reuse_settings_sha,'scope':'Original content scan reused; live entry/return retested'}
        bluetooth_before=adb('settings get global bluetooth_on').strip()
        for category in (args.categories or [args.category]):
            run_id='/'.join(args.path) if args.path else category or 'root'
            if args.tag:run_id+='@'+args.tag
            explorer=Explorer(a,run_id,reuse=reuse)
            if args.tag and explorer.output.exists():raise ValueError('Fresh scan tag required')
            try:
                explorer.goto_root()
                path=['设置']
                for component in (args.path or ([category] if category else [])):
                    previous=None; repeated=0
                    for _ in range(200):
                        _,root,_,state=a.snap('path-top')
                        boundary=(state['focus_signature'],viewport(root))
                        if boundary==previous: repeated+=1
                        else: repeated=0
                        previous=boundary
                        if repeated>=2: break
                        a.key('u')
                    a.seek(component,actionable=True); a.key('a'); path.append(component)
                explorer.visit(path)
            except Exception as error:
                print('CATEGORY_ERROR '+str(category)+' '+repr(error),flush=True)
                with (OUT/'category-errors.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps({'category':category,'error':repr(error)},ensure_ascii=False)+'\n')
                # Stop on any unresolved transition or transport failure. A new
                # category must never conceal an uncertain current page.
                raise
    finally:
        try:
            # Opening Android's pairing screen can implicitly enable Bluetooth.
            # Restore the known initially-off state; this is cleanup, not a key-test pass.
            if bluetooth_before=='0':
                try: bluetooth_after=adb('settings get global bluetooth_on').strip()
                except (subprocess.SubprocessError,TimeoutError): bluetooth_after=None
                if bluetooth_after!='0':
                    cleanup=a.command('svc bluetooth disable')
                    with (OUT/'audit-cleanup.jsonl').open('a',encoding='utf-8') as f:
                        f.write(json.dumps({'setting':'bluetooth_on','before':bluetooth_before,
                            'observed':bluetooth_after,'cleanup_uart':cleanup,
                            'restored':adb('settings get global bluetooth_on').strip()},ensure_ascii=False)+'\n')
        finally: a.close()

if __name__=='__main__': main()
