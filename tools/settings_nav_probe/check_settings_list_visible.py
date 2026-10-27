"""Check full selected-row visibility in a real Settings choice list; cancel."""
import argparse
import hashlib
import json
from pathlib import Path
from audit import Audit, OUT, adb, descendants
from followup import enter, top
from files import focus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--resume-receipt', type=Path)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('settings-list-visible-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'selection_submitted': False, 'walk': []}
    query = 'settings get global window_animation_scale'
    try:
        result['value_before'] = adb(query).strip()
        if args.resume_receipt:
            raw=args.resume_receipt.read_bytes()
            old=json.loads(raw)
            _, root, _, state=a.snap('list-visible-resume-guard',True)
            if (old.get('status')!='ERROR' or 'Selected choice remains clipped' not in old.get('error','')
                    or state['window_id']!=old['entry']['window_id']
                    or state['package']!='com.android.settings'
                    or result['value_before']!=old['value_before']
                    or not any(n.get('text')=='窗口动画缩放' and n.get('id','').endswith('/alertTitle')
                               for n in descendants(root))):
                raise RuntimeError('Owned unchanged animation popup does not match the continuation')
            result['continuation']={'source':str(args.resume_receipt),
                                    'sha256':hashlib.sha256(raw).hexdigest()}
        else:
            enter(a, ['系统', '开发者选项', '窗口动画缩放'])
        _, root, _, result['entry'] = a.snap('list-visible-entry', True)
        rows = [n for n in descendants(root) if n.get('visible')
                and n.get('class') == 'android.widget.CheckedTextView']
        expected_height = max(n['bounds'][3] - n['bounds'][1] for n in rows)
        result['native_row_height'] = expected_height
        if expected_height < 40:
            raise RuntimeError('No fully visible native list row for comparison')
        top(a)
        labels = set()
        for direction in ('d', 'u'):
            previous = None
            repeats = 0
            for _ in range(60):
                _, root, node, state = a.snap('list-visible-' + direction)
                if state['navigation_version'] != args.version:
                    raise RuntimeError('Unexpected navigation implementation')
                result['walk'].append(state)
                if node and node.get('class') == 'android.widget.CheckedTextView':
                    labels.add(node.get('text'))
                    height = state['focus_bounds'][3] - state['focus_bounds'][1]
                    edge=node.get('text') in ('关闭动画','动画缩放 10x')
                    # Native ListView can clip 8 px of its boundary row's blank
                    # padding. Screenshot review confirms its text/radio remain
                    # intact. Interior rows still require their full height.
                    minimum=expected_height*.75 if edge else expected_height-2
                    if height < minimum:
                        raise RuntimeError('Selected choice remains clipped: ' + repr(state))
                    if height < expected_height-2:
                        result.setdefault('boundary_padding_reviews',[]).append(
                            a.snap('list-visible-boundary-padding-'+direction,True)[3])
                boundary = (state['focus_signature'], tuple(state['focus_bounds'] or []))
                repeats = repeats + 1 if boundary == previous else 0
                if repeats >= 2:
                    break
                previous = boundary
                a.key(direction)
            else:
                raise RuntimeError('Choice list boundary not reached')
        result['choices'] = sorted(labels)
        expected = {'关闭动画', '动画缩放 0.5x', '动画缩放 1x', '动画缩放 1.5x',
                    '动画缩放 2x', '动画缩放 5x', '动画缩放 10x'}
        if labels != expected:
            raise RuntimeError('Choice coverage differs: ' + repr(labels))
        focus(a, '取消', expected_package='com.android.settings')
        a.key('a')
        result['cancel'] = a.snap('list-visible-canceled', True)[3]
        if result['cancel']['window'] != '开发者选项':
            raise RuntimeError('Cancel did not return to Developer settings')
        result['value_after'] = adb(query).strip()
        if result['value_after'] != result['value_before']:
            raise RuntimeError('Animation setting changed despite cancellation')
        result['status'] = 'PASS_ALL_SEVEN_CHOICE_CONTENTS_VISIBLE_INTERIOR_ROWS_FULL_CANCEL_UNCHANGED'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
