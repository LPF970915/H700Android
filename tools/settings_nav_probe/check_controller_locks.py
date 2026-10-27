"""Check hidden pattern entry, PIN/password input and cancellation without setting a credential."""
import argparse,json,time
from audit import Audit,OUT,adb,descendants,label
from followup import enter,top
from files import focus
from graph import graph

PKG='com.android.settings'
def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',default='native-20261025')
 p.add_argument('--confirmation-pages',action='store_true',help='Advance first draft only; never type or confirm the second credential')
 args=p.parse_args()
 if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
 receipt=OUT/('controller-locks-'+args.tag+'.json')
 if receipt.exists():raise ValueError('New evidence tag required')
 a=Audit();r={'status':'RUNNING','credential_saved':False}
 try:
  r['trust_before']=adb('dumpsys trust')
  enter(a,['安全','屏幕锁定']);top(a)
  walk=a.walk('controller-lock-picker',40);r['picker_walk']=walk
  labels={x['focus'] for x in walk['path']}
  if any('图案' in x for x in labels):raise RuntimeError('Pattern lock entry remains')
  if not any('PIN' in x for x in labels) or '密码' not in labels:raise RuntimeError('PIN/password entry missing')
  r['editors']=[]
  for key in ('lock_pin','lock_password'):
   focus(a,key,expected_package=PKG);a.key('a')
   data,root,_,state=a.snap('controller-'+key+'-entry',True)
   if any(n.get('id')=='com.android.settings:id/lock_pin' for n in descendants(root)):raise RuntimeError('Lock picker did not open editor')
   item={'kind':key,'entry':state}
   fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
   if len(fields)!=1:raise RuntimeError('Expected one uncommitted credential editor')
   if not any(w.get('type')==2 for w in data['windows']):
    focus(a,fields[0]['id'].split('/')[-1],expected_package=PKG);a.key('a')
   data,root,_,item['keyboard']=a.snap('controller-'+key+'-keyboard',True)
   if not any(w.get('type')==2 and w.get('root',{}).get('package')=='com.android.inputmethod.leanback' for w in data['windows']):raise RuntimeError('TV IME absent')
   # All A presses are consumed by the verified open IME, never a Next button.
   if key=='lock_pin':
    # The stock TV layout has its digit row above the initial letter focus.
    # Use a non-sequential four-digit fixture; it is never submitted.
    for k in ['u','a','r','r','a','r','r','a','l','l','l','l','l','a']:a.key(k)
   else:
    a.key('d')
    for _ in range(4):a.key('a')
   item['typed']=a.snap('controller-'+key+'-typed',True)[3]
   a.key('b');data,root,_,item['hidden']=a.snap('controller-'+key+'-hidden',True)
   if any(w.get('type')==2 for w in data['windows']):raise RuntimeError('B did not hide credential IME')
   item['valid_input_next_enabled']=any(n.get('visible') and n.get('enabled') and n.get('clickable') and label(n)=='下一步' for n in descendants(root))
   if not item['valid_input_next_enabled']:raise RuntimeError('Typed credential did not enable Next; no valid input proved')
   item['focus_graph']=graph(a,['锁定方式',key,'未提交输入',args.tag],160)['status']
   if item['focus_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Credential control graph incomplete')
   if args.confirmation_pages:
    # ChooseLockPassword.handleNext only moves Introduction -> NeedToConfirm
    # on this first draft. Saving requires a matching second entry and another
    # confirmation; this test leaves that second entry empty throughout.
    focus(a,'下一步',expected_package=PKG)
    data,_,_,_=a.snap('controller-before-first-next')
    if any(w.get('type')==2 for w in data['windows']):
     a.key('b');focus(a,'下一步',expected_package=PKG)
    a.key('a');data,root,_,item['confirmation_entry']=a.snap('controller-'+key+'-confirmation',True)
    if not any(n.get('visible') and str(n.get('text','')).startswith('重新输入') for n in descendants(root)):
     raise RuntimeError('First Next did not open the expected uncommitted confirmation page')
    item['confirmation_keyboard_shown']=any(w.get('type')==2 for w in data['windows'])
    if item['confirmation_keyboard_shown']:a.key('b')
    item['confirmation_graph']=graph(a,['锁定方式',key,'空确认页面不保存',args.tag],160)['status']
    if item['confirmation_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Credential confirmation graph incomplete')
    _,root,_,_=a.snap('controller-empty-confirmation-save-disabled')
    if any(n.get('visible') and n.get('enabled') and n.get('clickable') and label(n) in ('确定','确认','完成') for n in descendants(root)):
     raise RuntimeError('Unexpected enabled credential-save action on empty confirmation; no A injected')
   a.key('b')
   for _ in range(8):
    _,root,_,item['cancelled']=a.snap('controller-'+key+'-cancelled',True)
    if any(n.get('id')=='com.android.settings:id/lock_pin' for n in descendants(root)):break
    time.sleep(.2)
   else:raise RuntimeError('B did not cancel uncommitted credential editor')
   r['editors'].append(item)
  r['trust_after']=adb('dumpsys trust')
  r['status']=('PASS_PIN_PASSWORD_FIRST_NEXT_EMPTY_CONFIRMATION_GRAPH_CANCEL_NO_SAVE' if args.confirmation_pages
               else 'PASS_PATTERN_HIDDEN_PIN_PASSWORD_INPUT_FOCUS_AND_CANCEL');print(r['status'],flush=True)
 except Exception as e:r.update(status='ERROR',error=repr(e));raise
 finally:a.close();receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
