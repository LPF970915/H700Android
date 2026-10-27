"""Navigate the actual Leanback keyboard selector with HAT; never touch or set text."""
from audit import descendants


def type_ascii(a, text, read_editor, tag):
    if not text.isascii() or not text.isalnum():
        raise ValueError('Only owned alphanumeric fixture text is supported')
    evidence = []
    for char in text:
        seen = set()
        for step in range(70):
            data, root, _, state = a.snap(tag + '-key-' + char)
            keyboard = [w['root'] for w in data['windows'] if w.get('type') == 2
                        and w.get('root', {}).get('package') == 'com.android.inputmethod.leanback']
            if len(keyboard) != 1:
                raise RuntimeError('Actual TV keyboard is not open')
            nodes = list(descendants(keyboard[0]))
            selectors = [n for n in nodes if n.get('visible') and n.get('id', '').endswith('/key_selector')]
            targets = [n for n in nodes if n.get('visible') and n.get('desc') == char]
            if len(selectors) != 1 or len(targets) != 1:
                raise RuntimeError('TV selector/fixture key ambiguous: ' + char)
            sb = selectors[0]['bounds']
            tb = targets[0]['bounds']
            sx, sy = (sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2
            tx, ty = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
            if tb[0] <= sx <= tb[2] and tb[1] <= sy <= tb[3]:
                before = read_editor(root)
                a.key('a')
                _, after_root, _, after = a.snap(tag + '-typed-' + char)
                if read_editor(after_root) != before + char:
                    raise RuntimeError('Actual key A did not append the requested fixture character')
                evidence.append({'character': char, 'target': state, 'applied': after})
                break
            dx, dy = tx - sx, ty - sy
            direction = ('r' if dx > 0 else 'l') if abs(dx) > abs(dy) else ('d' if dy > 0 else 'u')
            edge = (tuple(sb), direction)
            if edge in seen:
                raise RuntimeError('TV keyboard direction repeated before fixture key: ' + char)
            seen.add(edge)
            a.key(direction)
        else:
            raise RuntimeError('TV keyboard fixture key not reached: ' + char)
    return evidence
