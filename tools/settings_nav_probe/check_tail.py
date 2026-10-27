"""Recheck real list boundaries without activating any selected leaf control."""
import argparse
import json
from audit import Audit, OUT, adb
from followup import enter, top


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',type=int,default=12)
    args=parser.parse_args()
    a=Audit();result={}
    try:
        enter(a,['显示']);top(a)
        try:a.seek('色温调节',90)
        except RuntimeError:
            top(a);a.seek('高级');a.key('a');a.seek('色温调节',90)
        _,root,focus,state=a.snap('display-tail-preflight')
        # A read-only section heading can share the slider's caption. Verify
        # RangeInfo instead of treating the first matching label as the slider.
        for _ in range(10):
            if state['focus']=='色温调节' and focus and focus.get('range'):break
            a.key('d');_,root,focus,state=a.snap('display-tail-find-range')
        else:raise RuntimeError('Actual color-temperature slider was not reached')
        _,root,focus,state=a.snap('display-v12-tail-before',True)
        if state['navigation_version']!=args.version:raise RuntimeError('Unexpected native navigation version')
        baseline=focus.get('range');result['display']={'before':state,'down':[]}
        for _ in range(5):
            a.key('d');_,_,focus,state=a.snap('display-v12-tail-down')
            result['display']['down'].append(state)
            if state['focus']!='色温调节' or focus.get('range')!=baseline:
                raise RuntimeError('Bottom slider escaped or changed: '+str(state))
        a.key('u');up=a.snap('display-v12-tail-up')[3]
        if up['focus']=='色温调节':raise RuntimeError('Slider cannot be exited upward')
        result['display']['up']=up
        result['display']['status']='BOTTOM_STABLE_UP_EXIT_VERIFIED'
        enter(a,['存储','内部共享存储空间']);top(a)
        walk=a.walk('storage-v12',90)
        if any('android:id/progress' in key for key in walk['visited']):
            raise RuntimeError('Decorative progress bar still selected')
        if walk['path'][-1]['focus']!='系统':raise RuntimeError('Storage tail not reached')
        result['storage']={'status':'VERTICAL_BOTTOM_VERIFIED','steps':len(walk['path']),
                           'focuses':[state['focus'] for state in walk['path']]}
        # Check the opposite direction after reaching the actual end.
        for _ in range(3):a.key('u')
        up=a.snap('storage-v12-up')[3]
        if up['focus']=='系统':raise RuntimeError('Storage cannot be exited upward')
        result['storage']['up']=up
        result['status']='BOTH_LIST_BOUNDARIES_VERIFIED'
        print(result['status'],flush=True)
    finally:
        a.close();(OUT/('tail-check-v'+str(args.version)+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
