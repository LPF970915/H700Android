"""Prove information-only preference rows are readable, traversable, and inert on A."""
import argparse
import json
import re
from audit import Audit, OUT, adb
from followup import enter, top


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',type=int,default=15)
    args=parser.parse_args()
    a=Audit();result={'version':args.version}
    try:
        enter(a,['关于手机']);top(a)
        walk=a.walk('about-information-v'+str(args.version),90)
        labels={state['focus'] for state in walk['path']}
        required={'IP 地址','WLAN MAC 地址','蓝牙地址','已开机时间'}
        if not required<=labels:raise RuntimeError('Unreachable information rows: '+str(required-labels))
        result['focuses']=[state['focus'] for state in walk['path']]
        top(a);a.seek('IP 地址')
        _,_,focus,result['before']=a.snap('information-v14-before',True)
        if focus.get('clickable'):raise RuntimeError('Expected an actual read-only row')
        service=adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        count=re.search(r'actionCount=(\d+)',service)[1]
        a.key('a');result['after']=a.snap('information-v14-after')[3]
        service=adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        if re.search(r'actionCount=(\d+)',service)[1]!=count:raise RuntimeError('A attempted an action on an information row')
        if result['after']['focus_signature']!=result['before']['focus_signature']:
            raise RuntimeError('A changed the read-only target')
        a.key('d');result['down']=a.snap('information-v14-down')[3]
        if result['down']['focus']=='IP 地址':raise RuntimeError('Information row is a focus trap')
        result['status']='INFORMATION_ROWS_REACHABLE_A_INERT_AND_DIRECTION_EXIT_VERIFIED'
        print(result['status'],flush=True)
    except Exception as error:result['error']=repr(error);raise
    finally:
        a.close();(OUT/('information-rows-v'+str(args.version)+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
