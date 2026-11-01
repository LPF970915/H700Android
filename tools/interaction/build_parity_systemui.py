"""Port only the two reviewed controller patches into the pinned GSI SystemUI."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
sys.path.insert(0, str(REPO / 'tools/rotation'))
from patch_framework import methods, canonical
from dex_port import equivalent_class

constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'systemui-v6'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
jdk = native / 'prebuilts/jdk/jdk9/linux-x86/bin'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')
apktool = Path('/home/lpf/h700-at4k-20261028/apktool-2.9.3.jar')
assert hashlib.sha256(apktool.read_bytes()).hexdigest() == '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4'

def run(*args):
    print('RUN', *map(str, args[:3]), flush=True)
    p = subprocess.run(list(map(str, args)), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace')[-6000:] + p.stderr.decode(errors='replace')[-6000:])
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

def apk_canonical(text):
    # A DEX encoded_array may omit trailing default null static references.
    # Retain every non-default initializer and all instance field declarations.
    text = re.sub(r'(?m)^(\.field [^\n]*\bstatic\b[^\n]*:[L\[][^\n]*) = null$', r'\1', text)
    return canonical(text)

def signing_entry(name):
    upper = name.upper()
    if not upper.startswith('META-INF/'):
        return False
    leaf = upper.rsplit('/', 1)[-1]
    return leaf == 'MANIFEST.MF' or leaf.startswith('SIG-') or leaf.endswith(('.SF', '.RSA', '.DSA', '.EC'))

run(jdk / 'javac', '-J-Xmx512m', '-cp', apktool, '-d', WORK,
    REPO / 'tools/rotation/FrameworkDexTool.java', REPO / 'tools/interaction/FrameworkApiAudit.java')
java = ['taskset', '-c', '0', jdk / 'java', '-Xmx2g', '-cp', str(WORK) + ':' + str(apktool), 'FrameworkDexTool']
source = ROOT / 'inputs-gsi/SystemUI.apk'
comparison = json.loads((OUT / 'component-comparison.json').read_text())['components']
assert hashlib.sha256(source.read_bytes()).hexdigest() == comparison['SystemUI']['gsi']['sha256']
targets = ['com/android/systemui/globalactions/GlobalActionsDialog$ActionsDialog',
           'com/android/systemui/statusbar/phone/StatusBarWindowView']
entries = {}
for name in targets + ['com/android/systemui/statusbar/phone/StatusBar']:
    found = run(*java, 'find', source, 'L' + name + ';')
    candidates = re.findall(r'CLASS_ENTRY=(.+)', found)
    assert len(candidates) == 1, (name, found)
    entries[name] = candidates[0]
for entry in set(entries.values()):
    run(*java, 'disassemble', source, entry, WORK / ('original-' + entry))
    shutil.copytree(WORK / ('original-' + entry), WORK / ('modified-' + entry))
statusbar = (WORK / ('original-' + entries['com/android/systemui/statusbar/phone/StatusBar']) /
             'com/android/systemui/statusbar/phone/StatusBar.smali').read_text()
for signature in ('onSpacePressed()Z', 'isKeyguardShowing()Z', 'isBouncerShowing()Z'):
    assert signature in methods(statusbar), signature

def start_hook(text, signature, instructions):
    block = methods(text)[signature]
    declaration = re.search(r'(?m)^    \.(registers|locals) (\d+)\s*$', block)
    assert declaration is not None
    # Existing methods have locals available; reject instead of silently
    # moving raw parameter registers when the upstream method shape changes.
    assert int(declaration[2]) >= (1 if declaration[1] == 'locals' else 3)
    changed = block[:declaration.end()] + '\n' + instructions + block[declaration.end():]
    return text.replace(block, changed, 1)

name = targets[0]
path = WORK / ('modified-' + entries[name]) / (name + '.smali')
text = path.read_text()
superclass = re.search(r'^\.super (\S+)', text, re.M)[1]
for signature, event, helper in [('dispatchKeyEvent(Landroid/view/KeyEvent;)Z', 'KeyEvent', 'key'),
                                  ('dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z', 'MotionEvent', 'motion')]:
    hook = f'''    invoke-static {{p0, p1}}, Lcom/roc/h700/parity/SystemUiKeys;->{helper}(Landroid/app/Dialog;Landroid/view/{event};)Z
    move-result v0
    if-eqz v0, :h700_original_{helper}
    const/4 v0, 0x1
    return v0
    :h700_original_{helper}
'''
    if signature in methods(text):
        text = start_hook(text, signature, hook)
    else:
        text += f'''
.method public {signature}
    .locals 1
{hook}
    invoke-super {{p0, p1}}, {superclass}->{signature}
    move-result v0
    return v0
.end method
'''
block = methods(text)['onStart()V']
assert block.count('    return-void') == 1
text = text.replace(block, block.replace('    return-void',
    '    invoke-static {p0}, Lcom/roc/h700/parity/SystemUiKeys;->start(Landroid/app/Dialog;)V\n    return-void'), 1)
path.write_text(text)

name = targets[1]
path = WORK / ('modified-' + entries[name]) / (name + '.smali')
text = path.read_text()
assert '.field private mService:Lcom/android/systemui/statusbar/phone/StatusBar;' in text or re.search(
    r'^\.field .*mService:Lcom/android/systemui/statusbar/phone/StatusBar;', text, re.M)
hook = '''    invoke-static {p1}, Lcom/roc/h700/parity/SystemUiKeys;->physicalA(Landroid/view/KeyEvent;)Z
    move-result v0
    if-eqz v0, :h700_unlock_original
    iget-object v0, p0, Lcom/android/systemui/statusbar/phone/StatusBarWindowView;->mService:Lcom/android/systemui/statusbar/phone/StatusBar;
    invoke-virtual {v0}, Lcom/android/systemui/statusbar/phone/StatusBar;->isKeyguardShowing()Z
    move-result v0
    if-eqz v0, :h700_unlock_original
    iget-object v0, p0, Lcom/android/systemui/statusbar/phone/StatusBarWindowView;->mService:Lcom/android/systemui/statusbar/phone/StatusBar;
    invoke-virtual {v0}, Lcom/android/systemui/statusbar/phone/StatusBar;->isBouncerShowing()Z
    move-result v0
    if-nez v0, :h700_unlock_original
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getAction()I
    move-result v0
    const/4 v1, 0x1
    if-ne v0, v1, :h700_unlock_consumed
    invoke-virtual {p1}, Landroid/view/KeyEvent;->isCanceled()Z
    move-result v0
    if-nez v0, :h700_unlock_consumed
    iget-object v0, p0, Lcom/android/systemui/statusbar/phone/StatusBarWindowView;->mService:Lcom/android/systemui/statusbar/phone/StatusBar;
    invoke-virtual {v0}, Lcom/android/systemui/statusbar/phone/StatusBar;->onSpacePressed()Z
    :h700_unlock_consumed
    const/4 v0, 0x1
    return v0
    :h700_unlock_original
'''
block = methods(text)['dispatchKeyEvent(Landroid/view/KeyEvent;)Z']
declaration = re.search(r'(?m)^    \.(registers|locals) (\d+)\s*$', block)
assert int(declaration[2]) >= (2 if declaration[1] == 'locals' else 4)
text = start_hook(text, 'dispatchKeyEvent(Landroid/view/KeyEvent;)Z', hook)
path.write_text(text)

classes = WORK / 'helper-classes'
classes.mkdir()
android = native / 'prebuilts/sdk/29/public/android.jar'
run(jdk / 'javac', '-J-Xmx512m', '-source', '8', '-target', '8', '-bootclasspath',
    str(android) + ':' + str(sdk / 'bin/core-lambda-stubs.jar'), '-d', classes,
    REPO / 'tools/interaction/SystemUiKeys.java')
helperjar = WORK / 'helper.jar'
with zipfile.ZipFile(helperjar, 'w') as z:
    for p in classes.rglob('*.class'):
        z.write(p, p.relative_to(classes).as_posix())
dex = WORK / 'helper-dex'
dex.mkdir()
run(jdk / 'java', '-Xmx1g', '-cp', sdk / 'lib/d8.jar', 'com.android.tools.r8.D8',
    '--min-api', '29', '--lib', android, '--output', dex, helperjar)
with zipfile.ZipFile(WORK / 'helper-dex.jar', 'w') as z:
    z.write(dex / 'classes.dex', 'classes.dex')
run(*java, 'disassemble', WORK / 'helper-dex.jar', 'classes.dex', WORK / 'helper-smali')
extra = WORK / 'extra-smali'
shutil.copytree(WORK / 'helper-smali', extra)
for name in targets:
    path = WORK / ('modified-' + entries[name]) / (name + '.smali')
    to = extra / (name + '.smali')
    to.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, to)
    path.unlink()  # Only this new derived tree; original directories are retained.
newdex = {}
for entry in set(entries[n] for n in targets):
    output = WORK / entry
    run(*java, 'assemble', WORK / ('modified-' + entry), output)
    verification_jar = WORK / ('verify-' + entry + '.jar')
    with zipfile.ZipFile(verification_jar, 'w') as z:
        z.write(output, entry)
    run(*java, 'disassemble', verification_jar, entry, WORK / ('verify-' + entry))
    for before in (WORK / ('original-' + entry)).rglob('*.smali'):
        relative = before.relative_to(WORK / ('original-' + entry))
        if relative.as_posix().removesuffix('.smali') in targets:
            continue
        assert apk_canonical(before.read_text()) == apk_canonical((WORK / ('verify-' + entry) / relative).read_text()), relative
    newdex[entry] = output
with zipfile.ZipFile(source) as z:
    indices = [1 if n == 'classes.dex' else int(re.search(r'classes(\d+)\.dex', n)[1])
               for n in z.namelist() if re.fullmatch(r'classes\d*\.dex', n)]
extraentry = 'classes' + str(max(indices) + 1) + '.dex'
run(*java, 'assemble', extra, WORK / extraentry)
with zipfile.ZipFile(WORK / 'extra-verify.jar', 'w') as z:
    z.write(WORK / extraentry, extraentry)
run(*java, 'disassemble', WORK / 'extra-verify.jar', extraentry, WORK / 'extra-verify')
assert {p.relative_to(extra) for p in extra.rglob('*.smali')} == {
    p.relative_to(WORK / 'extra-verify') for p in (WORK / 'extra-verify').rglob('*.smali')}
for expected in extra.rglob('*.smali'):
    assert equivalent_class(expected.read_text(),
        (WORK / 'extra-verify' / expected.relative_to(extra)).read_text()), expected
newdex[extraentry] = WORK / extraentry
unsigned = WORK / 'SystemUI-unsigned.apk'
with zipfile.ZipFile(source) as a, zipfile.ZipFile(unsigned, 'w') as b:
    for info in a.infolist():
        if not signing_entry(info.filename):
            b.writestr(info, newdex[info.filename].read_bytes() if info.filename in newdex else a.read(info.filename))
    b.write(WORK / extraentry, extraentry)
with zipfile.ZipFile(source) as a, zipfile.ZipFile(unsigned) as b:
    for name in a.namelist():
        if not signing_entry(name) and not name.endswith('.dex'):
            assert a.read(name) == b.read(name), name
aligned = WORK / 'SystemUI-aligned.apk'
target = WORK / 'SystemUI.apk'
run(sdk / 'bin/zipalign', '-f', '-p', '4', unsigned, aligned)
run(jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'sign',
    '--key', native / 'build/make/target/product/security/platform.pk8',
    '--cert', native / 'build/make/target/product/security/platform.x509.pem',
    '--min-sdk-version', '29', '--out', target, aligned)
run(jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--min-sdk-version', '29', target)
receipt = {'base_sha256': comparison['SystemUI']['gsi']['sha256'], 'bytes': target.stat().st_size,
           'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'modified_classes': targets,
           'all_other_classes_canonically_verified': True, 'all_non_dex_resources_unchanged': True,
           'native_systemui_window_input_port': True, 'runtime_accepted': False,
           'requires_coherent_new_system_signing': True}
(OUT / 'systemui-v6.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('SYSTEMUI_SCOPED_PORT_CANDIDATE_COMPLETE', flush=True)
