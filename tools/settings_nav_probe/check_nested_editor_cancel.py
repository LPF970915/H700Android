"""Test legacy input-style dialogs and empty dictionary editors without saving."""
import argparse
import hashlib
import json
import time
from audit import Audit, OUT, adb, descendants
from explore import Explorer, fingerprint
from followup import top, enter_supplement
from files import focus
from graph import graph


def require_graph(value):
    if value['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Incomplete direction graph')
    return value['status']


def style_values(root):
    value={}
    for ident in ('subtype_locale_spinner','keyboard_layout_set_spinner'):
        node=next(n for n in descendants(root) if n.get('id','').endswith('/'+ident))
        value[ident]=' / '.join(n.get('text') for n in descendants(node) if n.get('text'))
    return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('nested-editor-cancel-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh tag required')
    result={'status':'RUNNING','dictionary_words_typed':False,'styles_saved':False}
    a=Audit()
    try:
        _,root,_,state=a.snap('nested-style-current-root')
        labels={n.get('text') for n in descendants(root) if n.get('visible')}
        if state['package']!='com.android.inputmethod.latin' or not {'偏好设置','外观和布局'}.issubset(labels):
            raise RuntimeError('Expected audited AOSP keyboard root as continuation')
        top(a);a.seek('外观和布局',actionable=True);a.key('a')
        a.seek('自定义输入样式',actionable=True);a.key('a')
        _,root,_,result['style_list_before']=a.snap('nested-style-list-before',True)
        before=fingerprint(root,result['style_list_before'])
        a.seek('德语 (QWERTY)',actionable=True);a.key('a')
        _,root,_,result['style_dialog']=a.snap('nested-style-editor',True)
        result['german_restored_values']=style_values(root)
        if ('德语' not in result['german_restored_values']['subtype_locale_spinner']
                or result['german_restored_values']['keyboard_layout_set_spinner']!='QWERTY'):
            raise RuntimeError('Existing German style was not restored by value')
        value=graph(a,['输入法深层编辑',args.tag,'现有样式编辑'],180)
        result['style_graph']=require_graph(value)
        signatures=[state.get('focus_signature') or '' for state in value['nodes'].values()]
        for ident in ('subtype_locale_spinner','keyboard_layout_set_spinner','android:id/button1','android:id/button2','android:id/button3'):
            if not any(ident in signature for signature in signatures):raise RuntimeError('Style control not reached: '+ident)
        result['style_spinners']=[]
        for ident in ('subtype_locale_spinner','keyboard_layout_set_spinner'):
            focus(a,ident,expected_package='com.android.inputmethod.latin');a.key('a')
            e=Explorer(a,args.tag+'-style-'+ident)
            e.visit(['输入法深层编辑',args.tag,'现有样式',ident],True)
            if e.pages[0]['status']!='BIDIRECTIONAL_SCAN_DONE':raise RuntimeError('Style dropdown scan incomplete')
            result['style_spinners'].append(e.output.name)
            a.key('b')
        focus(a,'button3',expected_package='com.android.inputmethod.latin');a.key('a')
        _,root,_,result['style_cancel']=a.snap('nested-style-a-cancel',True)
        if fingerprint(root,result['style_cancel'])!=before:raise RuntimeError('Style cancel did not restore exact list')
        a.seek('法语 (QWERTZ)',actionable=True);a.key('a')
        _,root,_,result['french_dialog']=a.snap('nested-style-french-existing',True)
        result['french_restored_values']=style_values(root)
        if ('法语' not in result['french_restored_values']['subtype_locale_spinner']
                or result['french_restored_values']['keyboard_layout_set_spinner']!='QWERTZ'):
            raise RuntimeError('Existing French style was not restored by value')
        focus(a,'button3',expected_package='com.android.inputmethod.latin');a.key('a')
        _,root,_,result['french_cancel']=a.snap('nested-style-french-a-cancel',True)
        if fingerprint(root,result['french_cancel'])!=before:raise RuntimeError('French cancel did not restore exact list')
        # Hash the provider output on-device; dictionary contents are never logged.
        query='content query --uri content://user_dictionary/words --projection _id:word:shortcut:locale'
        def dictionary_hash():
            raw=adb(query)
            if 'Error while accessing provider' in raw or 'Exception' in raw:raise RuntimeError('Dictionary provider read failed')
            return hashlib.sha256(raw.encode()).hexdigest()
        result['dictionary_hash_before']=dictionary_hash()
        result['dictionaries']=[]
        for locale in ('所有语言','中文 (中国,#Hans)','英语 (美国)'):
            enter_supplement(a,{'setup_action':'android.settings.INPUT_METHOD_SETTINGS',
                               'path':['系统','语言和输入法','个人字典',locale]})
            _,root,_,entry=a.snap('nested-dictionary-empty-entry',True)
            dictionary_list_fingerprint=fingerprint(root,entry)
            # The audited dictionaries are empty. Never open/edit a user's word.
            if any(n.get('id')=='android:id/text1' and n.get('text') for n in descendants(root)):
                raise RuntimeError('Dictionary has existing entries; preserve user words')
            focus(a,'添加',expected_package='com.android.settings');a.key('a')
            item={'locale':locale,'entry':a.snap('nested-dictionary-add-empty',True)[3]}
            _,initial_root,_,_=a.snap('nested-dictionary-empty-baseline')
            initial_fields={n.get('id'):n.get('text') for n in descendants(initial_root) if n.get('editable') and n.get('visible')}
            if len(initial_fields)!=2:raise RuntimeError('Expected two new dictionary editors')
            for ident in ('user_dictionary_add_word_text','user_dictionary_add_shortcut'):
                focus(a,ident,expected_package='com.android.settings')
                for _ in range(6):
                    data,_,_,_=a.snap('nested-dictionary-before-keyboard')
                    if any(w.get('type')==2 for w in data['windows']):break
                    time.sleep(.2)
                if not any(w.get('type')==2 for w in data['windows']):a.key('a')
                for _ in range(10):
                    data,_,_,keyboard=a.snap('nested-dictionary-keyboard',True)
                    if any(w.get('type')==2 for w in data['windows']):break
                    time.sleep(.2)
                else:raise RuntimeError('Dictionary field did not open keyboard')
                a.key('b')
            _,root,_,_=a.snap('nested-dictionary-before-empty-cancel')
            fields=[n for n in descendants(root) if n.get('editable') and n.get('visible')]
            if len(fields)!=2:raise RuntimeError('Expected two empty dictionary editors')
            # The provider writes on fragment pause. Confirm no typed content.
            if {n.get('id'):n.get('text') for n in fields}!=initial_fields:
                raise RuntimeError('Unexpected dictionary content; do not leave editor')
            value=graph(a,['输入法深层编辑',args.tag,locale,'空白字典编辑'],180)
            item['form_graph']=require_graph(value)
            signatures=[state.get('focus_signature') or '' for state in value['nodes'].values()]
            for ident in ('user_dictionary_add_word_text','user_dictionary_add_shortcut'):
                if not any(ident in signature for signature in signatures):raise RuntimeError('Dictionary field not reached: '+ident)
            a.key('b');_,root,_,item['cancel']=a.snap('nested-dictionary-empty-cancel',True)
            if fingerprint(root,item['cancel'])!=dictionary_list_fingerprint:
                raise RuntimeError('Dictionary editor did not return to its list')
            result['dictionaries'].append(item)
        result['dictionary_hash_after']=dictionary_hash()
        if result['dictionary_hash_before']!=result['dictionary_hash_after']:raise RuntimeError('Dictionary provider changed')
        result['status']='PASS_STYLE_DIALOG_DROPDOWNS_A_CANCEL_EMPTY_DICTIONARY_KEYBOARDS_NO_SAVE'
        print(result['status'],flush=True)
    except Exception as error:
        result.update(status='ERROR',error=repr(error));raise
    finally:
        a.close();output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
