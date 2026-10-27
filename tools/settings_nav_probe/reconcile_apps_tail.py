"""Create a new continuation cache without altering the original interrupted scan."""
import copy
import hashlib
import json
from audit import OUT


def main():
    source=OUT/'exploration-9cd8901a44.json'
    closure=OUT/'apps-list-tail-closure-native34-20261027.json'
    target=OUT/'apps-tail-reviewed-completed-reuse-20261027.json'
    if target.exists():raise ValueError('Continuation cache already exists')
    original=json.loads(source.read_text(encoding='utf8'))
    tail=json.loads(closure.read_text(encoding='utf8'))
    if tail['status']!='PASS_ORIGINAL_21_APP_SCAN_OVERFLOW_RESET_A_CANCEL_SYSTEM_LIST_BOTH_DIRECTIONS_FILTER_RESTORED':
        raise RuntimeError('Actual overflow/cancel/list/filter closure is incomplete')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if tail['source_sha256']!=sha(source):raise RuntimeError('Original interrupted scan changed')
    extra_file=OUT/tail['overflow_scan'];extra=json.loads(extra_file.read_text(encoding='utf8'))
    path=['设置','应用和通知','查看全部 21 个应用']
    parent=copy.deepcopy(next(p for p in original['pages'] if p['path']==path))
    branches=[b for b in parent['branches'] if b['label']!='更多选项']
    if not branches or any(b.get('result')!='ENTERED_AND_SCANNED' for b in branches):
        raise RuntimeError('Original app-detail branches were not all completed')
    if not parent.get('toolbar_sweep') or len(parent.get('held_boundary_checks',[]))!=2:
        raise RuntimeError('Original list did not reach both directional boundaries')
    popup=next(p for p in extra['pages'] if p['path']==path+['更多选项'])
    if popup['status']!='BIDIRECTIONAL_SCAN_DONE' or not popup.get('popup_reentries'):
        raise RuntimeError('Natural overflow dismissal/reentry was not proven')
    for b in parent['branches']:
        if b['label']=='更多选项':b.update(result='ENTERED_AND_SCANNED',entry=popup['entry'])
    proof={'original_scan':source.name,'original_sha256':sha(source),
        'tail_closure':closure.name,'tail_sha256':sha(closure),
        'overflow_scan':extra_file.name,'overflow_sha256':sha(extra_file),
        'scope':'Original completed app branches and both list directions; actual overflow child cancellation/reentry and system-list filter restored in the supplementary hardware-node test.'}
    parent.update(status='BIDIRECTIONAL_SCAN_DONE',end=tail['system_hidden_restore'],completion_provenance=proof)
    pages=[p for p in original['pages'] if p['path']!=path and not p['path'][:len(path)+1]==path+['更多选项']
           and p['status'] in ('BIDIRECTIONAL_SCAN_DONE','DUPLICATE_TEMPLATE','EXTERNAL_APP_ENTRY')]
    pages.append(parent)
    pages.extend(p for p in extra['pages'] if p['path']!=path)
    target.write_text(json.dumps({'pages':pages,'completion_provenance':proof},ensure_ascii=False,indent=2),encoding='utf8')
    print('REVIEWED_CONTINUATION_CACHE',target,flush=True)


if __name__=='__main__':main()
