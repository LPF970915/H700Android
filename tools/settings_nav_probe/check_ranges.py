"""Check real font/density values after HAT adjustments, restoring on any failure."""
import json
import re
import time
from audit import Audit, OUT, adb
from followup import enter
from graph import graph


def check(a, title, query, rollback):
    baseline=adb(query).strip()
    enter(a,['显示',title])
    # The two-column layout places the minus button below the toolbar; Up
    # from that button reaches the range itself without changing its value.
    a.key('d'); a.key('u')
    _,_,focus,state=a.snap(title+'-range-entry',True)
    if not focus or not focus.get('range'): raise RuntimeError('Range was not selected: '+str(state))
    value=focus['range']
    direction='l' if value['current']>value['min'] else 'r'
    result={'title':title,'baseline':baseline,'entry':state,'navigation_version':state['navigation_version']}
    try:
        a.key(direction); time.sleep(2)
        result['changed_value']=adb(query).strip()
        _,_,focus,result['changed']=a.snap(title+'-range-changed',True)
        if result['changed_value']==baseline: raise RuntimeError('Backing value did not change')
        if not focus or not focus.get('range'): raise RuntimeError('Range focus was lost after change')
        a.key('r' if direction=='l' else 'l'); time.sleep(2)
        result['restored_value']=adb(query).strip()
        result['restored']=a.snap(title+'-range-restored',True)[3]
        if result['restored_value']!=baseline: raise RuntimeError('Backing value was not restored')
        result['graph_status']=graph(a,['设置','显示',title],100)['status']
        if adb(query).strip()!=baseline: raise RuntimeError('Graph changed backing value')
        result['status']='PROPERTY_CHANGE_AND_RESTORE_VERIFIED'
    except Exception as error:
        result['status']='FAILED'; result['error']=repr(error)
        try: current=adb(query).strip()
        except Exception as read_error:
            current=None; result['recovery_read_error']=repr(read_error)
        if current!=baseline:
            # Recovery is logged separately and never counts as a passing key test.
            a.command(rollback(baseline)); time.sleep(2)
            try: result['recovery_value']=adb(query).strip()
            except Exception as read_error: result['recovery_verify_error']=repr(read_error)
        raise
    finally:
        (OUT/('range-check-'+('font' if title=='字体大小' else 'density')+'.json')).write_text(
            json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


def restore_font(value):
    if not re.fullmatch(r'\d+(?:\.\d+)?',value): raise ValueError('Unexpected font baseline')
    return 'settings put system font_scale '+value


def restore_density(value):
    override=re.search(r'Override density: (\d+)',value)
    return 'wm density '+override[1] if override else 'wm density reset'


if __name__=='__main__':
    a=Audit()
    try:
        check(a,'字体大小','settings get system font_scale',restore_font)
        check(a,'显示大小','wm density',restore_density)
    finally: a.close()
