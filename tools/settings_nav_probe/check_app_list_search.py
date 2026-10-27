"""Exercise the native installed-app search with HAT/A and the TV keyboard."""
import argparse
import json
import time
from audit import Audit, OUT, adb, descendants
from files import focus
from followup import top
from ime_keys import type_ascii

PKG='com.android.settings'


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('app-list-search-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    result={'status':'RUNNING','query':'rgsp'};a=Audit()
    try:
        a.command("am start -n 'com.android.settings/.Settings$AppAndNotificationDashboardActivity'")
        top(a);a.seek('查看全部',actionable=True);a.key('a');top(a)
        result['search_button']=focus(a,'search_app_list_menu',expected_package=PKG);a.key('a')
        data,root,_,result['search_entry']=a.snap('app-list-search-entry',True)
        fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
        if len(fields)!=1:raise RuntimeError('Installed-app query editor ambiguous')
        editor_id=fields[0]['id'];initial=fields[0].get('text','')
        def query(current):
            value=next(n.get('text','') for n in descendants(current) if n.get('id')==editor_id)
            return '' if value==initial else value
        # A newly expanded SearchView starts empty. Do not replace existing text.
        if any(n.get('visible') and n.get('id','').endswith('/search_close_btn') for n in descendants(root)):
            result['initial_close_visible']=True
        for _ in range(8):
            if any(w.get('type')==2 for w in data['windows']):break
            time.sleep(.2);data,root,_,_=a.snap('app-list-search-ime-settle')
        else:
            focus(a,editor_id.split('/')[-1],expected_package=PKG);a.key('a')
        a.key('d');result['typed']=type_ascii(a,'rgsp',query,'app-list-search')
        a.key('b');data,root,_,result['filtered']=a.snap('app-list-search-filtered',True)
        if any(w.get('type')==2 for w in data['windows']):raise RuntimeError('TV keyboard did not close')
        result['filtered_titles']=[n.get('text') for n in descendants(root)
            if n.get('visible') and n.get('id')=='android:id/title' and n.get('text')]
        if 'RGSP D-pad Navigation' not in result['filtered_titles']:raise RuntimeError('Actual typed app filter has no expected result')
        result['result_focus']=focus(a,'RGSP D-pad Navigation',expected_package=PKG);a.key('a')
        _,opened_root,_,result['opened']=a.snap('app-list-search-result-opened',True)
        if result['opened']['window']!='应用信息' or not any(
                n.get('id','').endswith('/entity_header_title') and n.get('text')=='RGSP D-pad Navigation'
                for n in descendants(opened_root)):raise RuntimeError('App result did not open expected details')
        a.key('b');data,root,_,result['returned']=a.snap('app-list-search-result-return',True)
        if result['returned']['window_id']!=result['search_entry']['window_id']:
            raise RuntimeError('B did not return to original app list')
        # This native fragment destroys/recreates its options menu when opening
        # app details. A collapsed SearchView on B is a valid parent return.
        if not any(n.get('visible') and n.get('id')==editor_id for n in descendants(root)):
            result['native_return_collapsed_search']=True
            top(a);focus(a,'search_app_list_menu',expected_package=PKG);a.key('a')
            for _ in range(8):
                data,root,_,_=a.snap('app-list-search-reopen-ime')
                if any(w.get('type')==2 for w in data['windows']):break
                time.sleep(.2)
            else:raise RuntimeError('Reopened app query did not expose TV IME')
            a.key('d');result['clear_fixture']=type_ascii(a,'r',query,'app-list-search-clear-fixture');a.key('b')
        focus(a,'search_close_btn',expected_package=PKG);a.key('a')
        data,root,_,result['cleared']=a.snap('app-list-search-cleared',True)
        if query(root):raise RuntimeError('Search clear A did not empty query')
        if any(w.get('type')==2 for w in data['windows']):a.key('b')
        a.key('b');result['collapsed']=a.snap('app-list-search-collapsed',True)[3]
        if result['collapsed']['package']!=PKG:raise RuntimeError('App search cancellation left Settings')
        result['status']='PASS_APP_LIST_TV_TYPED_FILTER_RESULT_A_B_CLEAR_COLLAPSE'
    except Exception as error:result.update(status='ERROR',error=repr(error));raise
    finally:a.close();output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['status'],flush=True)


if __name__=='__main__':main()
