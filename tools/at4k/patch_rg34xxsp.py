"""Menu text, guarded scrolling and wallpaper sync for the pinned shipped AT4K."""
import hashlib
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

BASE_SHA = 'b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d'
MENU_METHODS = {'A', 'H', 'a', 'c', 'e', 'i', 'j', 'l', 'm'}

def patch(decoded: Path, apk: Path):
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == BASE_SHA, 'Expected frozen delivered APK'
    path = decoded / 'smali/R3/J7.smali'
    text = path.read_text()
    changed = {}
    def edit(match):
        name, body = match[1], match[2]
        if name in MENU_METHODS:
            count = body.count('LB3/a;->E(I)J')
            assert count, name
            changed[name] = count
            body = body.replace('LB3/a;->E(I)J', 'Lcom/overdevs/at4k/RgspLayout;->menuSp(I)J')
            body = body.replace('LK/L0;->b(', 'Lcom/overdevs/at4k/RgspLayout;->menuText(')
        return match[0].replace(match[2], body, 1)
    text = re.sub(r'(?ms)^\.method [^\n]* (\w+)\([^\n]*\n(.*?)^\.end method', edit, text)
    assert set(changed) == MENU_METHODS, changed
    path.write_text(text)
    path = decoded / 'smali/a/a.smali'
    text = path.read_text()
    def menu_row(match):
        body = match[0]
        assert body.count('LB3/a;->E(I)J') == 3
        body = body.replace('LB3/a;->E(I)J', 'Lcom/overdevs/at4k/RgspLayout;->menuSp(I)J')
        before = '''    invoke-static {v0, v8}, Landroidx/compose/ui/input/key/a;->a(LZ/o;Lo4/c;)LZ/o;

    move-result-object v0'''
        assert body.count(before) == 1
        return body.replace(before, before + '''

    move-object/from16 v1, p5

    invoke-static {v0, v1}, Lcom/overdevs/at4k/RgspLayout;->menuClick(LZ/o;Lo4/a;)LZ/o;

    move-result-object v0''')
    text, count = re.subn(r'(?ms)^\.method [^\n]* y\(Ljava/lang/String;ZZZLe0/p;Lo4/a;Lo4/a;Lo4/a;Lo4/a;Lo4/c;LN/p;II\)V\n.*?^\.end method', menu_row, text)
    assert count == 1
    dialog_methods = {'h', 'i', 'n', 'o', 'r', 's', 'y'}
    def dialog_text(match):
        if match[1] not in dialog_methods: return match[0]
        body = match[0].replace('LK/L0;->b(', 'Lcom/overdevs/at4k/RgspLayout;->menuText(')
        if match[1] in {'h', 'i'}:
            body = body.replace('Landroidx/compose/foundation/layout/d;->n(LZ/o;F)',
                                'Lcom/overdevs/at4k/RgspLayout;->tableCell(LZ/o;F)')
        if match[1] == 'h':
            body = body.replace('Landroidx/compose/foundation/layout/d;->g(LZ/o;F)',
                                'Lcom/overdevs/at4k/RgspLayout;->tableSpace(LZ/o;F)')
        return body
    text = re.sub(r'(?ms)^\.method [^\n]* (\w+)\([^\n]*\n(.*?)^\.end method', dialog_text, text)
    path.write_text(text)
    for relative in ['R3/P.smali', 'R3/S.smali', 'R3/T.smali']:
        button_path = decoded / 'smali' / relative
        button_text = button_path.read_text()
        assert 'LK/L0;->b(' in button_text
        button_path.write_text(button_text.replace('LK/L0;->b(', 'Lcom/overdevs/at4k/RgspLayout;->menuText('))
    shutil.copyfile(Path(__file__).with_name('RgspLayout.smali'), decoded / 'smali/com/overdevs/at4k/RgspLayout.smali')
    path = decoded / 'smali/com/overdevs/at4k/MainActivity.smali'
    text = path.read_text()
    before = '    invoke-super {p0}, Landroid/app/Activity;->onResume()V'
    assert text.count(before) == 1
    path.write_text(text.replace(before, before + '\n\n    invoke-static {p0}, Lcom/overdevs/at4k/RgspWallpaper;->install(Landroid/content/Context;)V'))
    path = decoded / 'AndroidManifest.xml'
    ns = 'http://schemas.android.com/apk/res/android'
    ET.register_namespace('android', ns)
    tree = ET.parse(path)
    manifest = tree.getroot()
    permission = 'android.permission.SET_WALLPAPER'
    assert not any(n.get('{' + ns + '}name') == permission for n in manifest.findall('uses-permission'))
    manifest.insert(1, ET.Element('uses-permission', {'{' + ns + '}name': permission}))
    tree.write(path, encoding='utf-8', xml_declaration=True)
    print('Patched menu text calls:', changed, flush=True)
