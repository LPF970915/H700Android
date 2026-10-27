"""Check rule-type chooser navigation and cancellation without creating a rule."""
import json
from audit import Audit, OUT, adb
from followup import enter
from graph import graph


def main():
    a=Audit();result={}
    try:
        result['policy_before']=adb('settings get global zen_mode; settings get global zen_mode_config_etag')
        enter(a,['声音','勿扰模式','时间安排']);a.seek('添加更多',actionable=True)
        result['before']=a.snap('dnd-add-v15-before')[3]
        a.key('a');result['entry']=a.snap('dnd-add-v15-entry',True)[3]
        if result['entry']['window_id']==result['before']['window_id']:
            raise RuntimeError('Rule-type chooser did not open a dialog')
        scan=graph(a,['设置','声音','勿扰模式','时间安排','添加更多'],100)
        result['graph_status']=scan['status']
        result['focuses']=sorted({s.get('focus') or '' for s in scan['nodes'].values()})
        a.key('b');result['return']=a.snap('dnd-add-v15-return',True)[3]
        if result['return']['window_id']!=result['before']['window_id']:
            raise RuntimeError('B did not return to the schedule page')
        result['policy_after']=adb('settings get global zen_mode; settings get global zen_mode_config_etag')
        if result['policy_after']!=result['policy_before']:raise RuntimeError('Zen policy changed during focus/cancel test')
        result['status']='RULE_CHOOSER_DIRECTIONS_AND_CANCEL_VERIFIED_POLICY_UNCHANGED'
        print(result['status'],flush=True)
    except Exception as error:result['error']=repr(error);raise
    finally:
        a.close();(OUT/'dnd-add-v15.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
