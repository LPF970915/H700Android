"""Enter a real Settings search query through TV keys and activate a result."""
import argparse
import json
import time
from audit import Audit, OUT, descendants
from explore import Explorer
from followup import top
from files import focus
from ime_keys import type_ascii

PKG = 'com.android.settings.intelligence'


def focus_clear(a):
    # With the keyboard hidden, our Settings scope owns navigation. A single
    # Right from the query editor reaches its actual clear button, not a caret.
    focus(a, 'search_src_text', expected_package=PKG)
    a.key('r')
    _, _, node, state = a.snap('settings-search-clear-target', True)
    if not node or node.get('id') != 'android:id/search_close_btn':
        raise RuntimeError('Right from query did not reach the clear button')
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('settings-search-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'query': 'wlan'}
    try:
        Explorer(a).goto_root()
        top(a)
        focus(a, 'search_action_bar', expected_package='com.android.settings')
        a.key('a')
        data, root, node, result['entry'] = a.snap('settings-search-entry', True)
        if result['entry']['package'] != PKG:
            raise RuntimeError('Native Settings search did not open')
        def query(root):
            fields = [n for n in descendants(root) if n.get('id') == 'android:id/search_src_text']
            if len(fields) != 1:
                raise RuntimeError('Search query editor ambiguous')
            value = fields[0].get('text', '')
            # Android's AX text substitutes the hint while this empty editor
            # has no visible clear button. This fixture types only "wlan".
            has_clear = any(n.get('visible') and n.get('id') == 'android:id/search_close_btn'
                            for n in descendants(root))
            return '' if value == '搜索…' and not has_clear else value
        if query(root):
            if any(w.get('type') == 2 for w in data['windows']):
                a.key('b')
            focus_clear(a)
            a.key('a')
            data, root, _, result['stale_query_cleared'] = a.snap('settings-search-clear-prior-query', True)
            if query(root):
                raise RuntimeError('Prior search query could not be cleared with A')
        if not any(w.get('type') == 2 for w in data['windows']):
            focus(a, 'search_src_text', expected_package=PKG)
            # SearchView may show its IME asynchronously on native focus. Do
            # not let an unnecessary second A type the initially selected key.
            deadline = time.monotonic() + 2
            while True:
                data, root, _, result['editor_focused'] = a.snap('settings-search-editor-focus-settle')
                if any(w.get('type') == 2 for w in data['windows']):
                    break
                if time.monotonic() >= deadline:
                    a.key('a')
                    data, root, _, result['editor_opened'] = a.snap('settings-search-editor-opened')
                    break
                time.sleep(.2)
        if query(root):
            raise RuntimeError('Search editor is not empty before owned fixture input')
        a.key('d')
        result['typed'] = type_ascii(a, 'wlan', query, 'settings-search')
        a.key('b')
        deadline = time.monotonic() + 20
        while True:
            data, root, _, result['results'] = a.snap('settings-search-results', True)
            if any(n.get('visible') and n.get('text') == 'WLAN' for n in descendants(root)):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('No actual WLAN search result appeared')
            time.sleep(.4)
        if any(w.get('type') == 2 for w in data['windows']):
            raise RuntimeError('B failed to hide the search keyboard')
        focus(a, 'WLAN', expected_package=PKG)
        _, _, node, result['result_target'] = a.snap('settings-search-wlan-target', True)
        if not node or not node.get('clickable') or node.get('editable'):
            raise RuntimeError('WLAN result is not a real clickable row')
        a.key('a')
        result['opened'] = a.snap('settings-search-result-opened', True)[3]
        if result['opened']['package'] != 'com.android.settings' or result['opened']['window'] != 'WLAN':
            raise RuntimeError('Search result A did not open WLAN')
        a.key('b')
        data, _, _, result['returned'] = a.snap('settings-search-result-return', True)
        if result['returned']['package'] != PKG:
            raise RuntimeError('B did not return to the actual search results')
        if any(w.get('type') == 2 for w in data['windows']):
            a.key('b')
        focus_clear(a)
        a.key('a')
        data, root, _, result['cleared'] = a.snap('settings-search-cleared', True)
        if query(root):
            raise RuntimeError('Clear A did not empty the search query')
        if any(w.get('type') == 2 for w in data['windows']):
            a.key('b')
            data, _, _, result['clear_keyboard_hidden'] = a.snap('settings-search-clear-keyboard-hidden', True)
            if any(w.get('type') == 2 for w in data['windows']):
                raise RuntimeError('B did not hide the clear-query keyboard')
        a.key('b')
        result['cancelled'] = a.snap('settings-search-cancelled', True)[3]
        if result['cancelled']['package'] != 'com.android.settings':
            raise RuntimeError('B did not return to Settings')
        result['status'] = 'PASS_TV_TYPED_WLAN_RESULT_A_B_CLEAR_AND_RETURN'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
