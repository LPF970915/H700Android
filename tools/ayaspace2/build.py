"""Pinned local Android10 adaptation. Requires original APK and private trial key."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
sys.path.insert(0, str(REPO / 'tools/interaction'))
from package_h700_v6a import constrained
from dex_port import DexPort
from manifest import patch

constrained()
REVISION = 9
root = Path('/home/lpf/h700-ayaspace2-20261101')
work = next(root / ('build-v%d' % i) for i in range(1, 100) if not (root / ('build-v%d' % i)).exists())
port = DexPort(REPO, work)
out = REPO / 'out/ayaspace2-20261101'
source = Path('/mnt/d/Downloads/Ayaspace2/pocketmuseum-0.3.3-release.apk')
assert hashlib.sha256(source.read_bytes()).hexdigest() == '205cbf8b87d3b696b3c3873dbaa0ad47fbe0e57acce8ca208961a7aea476df38'
smali = work / 'smali'
shutil.copytree(root / 'inspect-v1/smali', smali)
edits = {}
compat = 'Lcom/roc/h700/ayaspace/Compat;'

def update(name, transform):
    p = smali / (name + '.smali')
    before = p.read_text()
    after = transform(before)
    assert after != before, name
    p.write_text(after)
    edits[name] = {'before_sha256': hashlib.sha256(before.encode()).hexdigest(),
                   'after_sha256': hashlib.sha256(after.encode()).hexdigest()}

def body(text, signature, code, locals=2):
    pattern = r'^\.method [^\n]* ' + re.escape(signature) + r'\n.*?^\.end method'
    matches = list(re.finditer(pattern, text, re.M|re.S))
    assert len(matches) == 1, signature
    original = matches[0][0]
    annotations = re.findall(r'    \.annotation .*?    \.end annotation\n', original, re.S)
    result = original.splitlines()[0] + '\n    .locals ' + str(locals) + '\n' + ''.join(annotations) + '\n' + code + '\n.end method'
    return text.replace(original, result, 1)

# Storage checks must reflect real runtime grants, never return a hardcoded true.
storage_call = 'Landroid/os/Environment;->isExternalStorageManager()Z'
storage_sites = 0
for p in smali.rglob('*.smali'):
    text = p.read_text()
    if storage_call in text:
        storage_sites += text.count(storage_call)
        update(str(p.relative_to(smali))[:-6], lambda s: s.replace(storage_call, compat+'->storageAllowed()Z'))

update('com/godot/game/GodotApp', lambda s: body(s, 'onCreate(Landroid/os/Bundle;)V', f'''    invoke-static {{p0}}, {compat}->init(Landroid/content/Context;)V
    invoke-static {{p0}}, {compat}->appearance(Landroid/app/Activity;)V
    invoke-super {{p0, p1}}, Lorg/godotengine/godot/GodotActivity;->onCreate(Landroid/os/Bundle;)V
    return-void''', 0))

def bridge(s):
    start = s.index('    invoke-virtual {p1}, Landroid/app/Activity;->getSplashScreen()')
    end = s.index('    iget-object v1, p0, Lcom/pocketmuseum/bridge/BridgePlugin;->w:', start)
    s = s[:start] + '''    const/4 v2, 0x1
    iput-boolean v2, v1, Lg/P0;->c:Z

''' + s[end:]
    s=body(s, 'open_storage_permission()V', f'''    invoke-virtual {{p0}}, Lorg/godotengine/godot/plugin/GodotPlugin;->getActivity()Landroid/app/Activity;
    move-result-object v0
    if-eqz v0, :done
    invoke-static {{v0}}, {compat}->requestStorage(Landroid/app/Activity;)V
    :done
    return-void''', 1)
    declaration='.method public final device_supported()Z\n    .registers 2'
    assert s.count(declaration)==1
    at=s.index('    invoke-virtual {p0}',s.index(declaration))
    return s[:at]+f'''    invoke-static {{}}, {compat}->isH700()Z
    move-result v0
    if-eqz v0, :h700_original_device_check
    const/4 v0, 0x1
    return v0
    :h700_original_device_check
'''+s[at:]
update('com/pocketmuseum/bridge/BridgePlugin', bridge)
update('g/P0', lambda s: body(s, 'a()V', '''    const/4 v0, 0x1
    iput-boolean v0, p0, Lg/P0;->c:Z
    return-void''', 1))

for name in ('g/c0', 'org/godotengine/godot/io/directory/FilesystemDirectoryAccess'):
    update(name, lambda s: re.sub(r'invoke-virtual \{([vp]\d+)\}, Landroid/os/storage/StorageVolume;->getDirectory\(\)Ljava/io/File;',
         lambda m: 'invoke-static {'+m[1]+'}, '+compat+'->volumeDirectory(Landroid/os/storage/StorageVolume;)Ljava/io/File;', s))

def vibrator(s):
    a = s.index('    const-class v0, Landroid/os/VibratorManager;')
    b = s.index('    sget-object v0, Li/g;', a)
    return s[:a] + '''    const-string v0, "vibrator"
    invoke-virtual {p1, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object p1
    check-cast p1, Landroid/os/Vibrator;

''' + s[b:]
update('i/h', vibrator)
update('com/pocketmuseum/emu/EmuActivity', lambda s: s.replace('''    invoke-interface {p0}, Landroid/view/WindowManager;->getCurrentWindowMetrics()Landroid/view/WindowMetrics;

    move-result-object p0

    invoke-virtual {p0}, Landroid/view/WindowMetrics;->getBounds()Landroid/graphics/Rect;''',
    f'    invoke-static {{p0}}, {compat}->screenBounds(Landroid/view/WindowManager;)Landroid/graphics/Rect;'))
update('androidx/core/view/WindowCompat', lambda s: body(s, 'setDecorFitsSystemWindows(Landroid/view/Window;Z)V', f'''    invoke-static {{p0, p1}}, {compat}->decorFits(Landroid/view/Window;Z)V
    return-void''', 0))
update('androidx/activity/EdgeToEdge', lambda s: body(s, 'enable(Lcom/godot/game/GodotApp;)V', f'''    invoke-static {{p0}}, {compat}->appearance(Landroid/app/Activity;)V
    return-void''', 0))

def godot(s):
    s = body(s, 'enableImmersiveMode(ZZ)V', f'''    iget-object v0, p0, Lorg/godotengine/godot/Godot;->useImmersive:Ljava/util/concurrent/atomic/AtomicBoolean;
    invoke-virtual {{v0, p1}}, Ljava/util/concurrent/atomic/AtomicBoolean;->set(Z)V
    invoke-virtual {{p0}}, Lorg/godotengine/godot/Godot;->getActivity()Landroid/app/Activity;
    move-result-object v0
    if-eqz v0, :done
    invoke-virtual {{v0}}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-static {{v0, p1}}, {compat}->immersive(Landroid/view/Window;Z)V
    :done
    return-void''', 1)
    return body(s, 'enableEdgeToEdge(ZZ)V', f'''    iget-object v0, p0, Lorg/godotengine/godot/Godot;->isEdgeToEdge:Ljava/util/concurrent/atomic/AtomicBoolean;
    invoke-virtual {{v0, p1}}, Ljava/util/concurrent/atomic/AtomicBoolean;->set(Z)V
    invoke-virtual {{p0}}, Lorg/godotengine/godot/Godot;->getActivity()Landroid/app/Activity;
    move-result-object v0
    if-eqz v0, :done
    invoke-virtual {{v0}}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    xor-int/lit8 v1, p1, 0x1
    invoke-static {{v0, v1}}, {compat}->decorFits(Landroid/view/Window;Z)V
    :done
    return-void''', 2)
update('org/godotengine/godot/Godot', godot)

# Android10 PiP retains aspect/source rect; Android12 automatic entry is absent.
def pip(s):
    start=s.index('    invoke-virtual {v1, v2}, Landroid/app/PictureInPictureParams$Builder;->setSeamlessResizeEnabled')
    end=s.index('    const/16 p1, 0x21', start)
    return s[:start]+s[end:]
update('org/godotengine/godot/GodotActivity', pip)
# Optional updater: API29 always uses the platform's user confirmation policy.
update('g/o', lambda s: re.sub(r'^    invoke-virtual \{v5, v1\}, Landroid/content/pm/PackageInstaller\$SessionParams;->setRequireUserAction\(I\)V\n', '', s, flags=re.M))

def insets(s):
    s = body(s, '<init>(Landroid/view/Window;)V', '''    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Landroidx/core/view/WindowInsetsCompat$Builder;->mImpl:Ljava/lang/Object;
    return-void''', 0)
    for signature, code in {
        'hide()V': f'    const/4 v1, 0x1\n    invoke-static {{v0, v1}}, {compat}->immersive(Landroid/view/Window;Z)V',
        'show(I)V': f'    invoke-static {{v0, p1}}, {compat}->show(Landroid/view/Window;I)V',
        'setSystemBarsBehavior()V': f'    const/4 v1, 0x1\n    invoke-static {{v0, v1}}, {compat}->immersive(Landroid/view/Window;Z)V',
        'setAppearanceLightStatusBars(Z)V': f'    const/4 v1, 0x1\n    invoke-static {{v0, p1, v1}}, {compat}->lightBar(Landroid/view/Window;ZZ)V',
        'setAppearanceLightNavigationBars(Z)V': f'    const/4 v1, 0x0\n    invoke-static {{v0, p1, v1}}, {compat}->lightBar(Landroid/view/Window;ZZ)V',
    }.items():
        s=body(s,signature,'''    iget-object v0, p0, Landroidx/core/view/WindowInsetsCompat$Builder;->mImpl:Ljava/lang/Object;
    check-cast v0, Landroid/view/Window;
'''+code+'\n    return-void',2)
    return s
update('androidx/core/view/WindowInsetsCompat$Builder', insets)
update('androidx/core/view/ViewCompat', lambda s: body(s,
    'setWindowInsetsAnimationCallback(Landroid/view/View;Lorg/godotengine/godot/Godot$onInitRenderView$2;)V',
    f'    invoke-static {{p0}}, {compat}->observeKeyboard(Landroid/view/View;)V\n    return-void', 0))

def legacy_insets(s):
    s=s.replace('    sget-object v0, Landroid/view/WindowInsets;->CONSUMED:Landroid/view/WindowInsets;',
                f'    invoke-static {{}}, {compat}->emptyInsets()Landroid/view/WindowInsets;\n    move-result-object v0')
    return body(s,'getInsets(I)Landroidx/core/graphics/Insets;', '''    invoke-super {p0, p1}, Landroidx/core/view/WindowInsetsCompat$Impl29;->getInsets(I)Landroidx/core/graphics/Insets;
    move-result-object v0
    return-object v0''',1)
update('androidx/core/view/WindowInsetsCompat$Impl30',legacy_insets)

update('g/e',lambda s: re.sub(r'invoke-virtual \{([^}]+)\}, Landroid/database/sqlite/SQLiteDatabase;->execSQL\(Ljava/lang/String;\[Ljava/lang/Object;\)V',
    lambda m: 'invoke-static {'+m[1]+'}, '+compat+'->execSql(Landroid/database/sqlite/SQLiteDatabase;Ljava/lang/String;[Ljava/lang/Object;)V',s))

def dispatch_frontend(s):
    assert 'dispatchKeyEvent(Landroid/view/KeyEvent;)Z' not in s
    return s+f'''
.method public dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    .locals 1
    invoke-static {{p1}}, {compat}->remapGodot(Landroid/view/KeyEvent;)Landroid/view/KeyEvent;
    move-result-object p1
    invoke-super {{p0, p1}}, Lorg/godotengine/godot/GodotActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    move-result v0
    return v0
.end method
'''
update('com/godot/game/GodotApp',dispatch_frontend)

def dispatch_play(s):
    match=re.search(r'^\.method public dispatchKeyEvent\(Landroid/view/KeyEvent;\)Z\n    \.registers \d+\n',s,re.M)
    assert match
    return s[:match.end()]+f'''    invoke-static {{p1}}, {compat}->remapPlay(Landroid/view/KeyEvent;)Landroid/view/KeyEvent;
    move-result-object p1
'''+s[match.end():]
update('com/pocketmuseum/emu/EmuActivity',dispatch_play)

native=Path('/home/lpf/h700-android10/android')
sdk=native/'prebuilts/sdk/tools/linux'
android=native/'prebuilts/sdk/29/public/android.jar'
classes=work/'classes';classes.mkdir()
port.run(port.jdk/'javac','-J-Xmx512m','-source','8','-target','8','-bootclasspath',android,'-d',classes,REPO/'tools/ayaspace2/Compat.java')
helper=work/'helper';helper.mkdir()
port.run('taskset','-c','0',port.jdk/'java','-Xmx1g','-cp',sdk/'lib/d8.jar','com.android.tools.r8.D8','--min-api','29','--lib',android,'--output',helper,*classes.rglob('*.class'))
with zipfile.ZipFile(work/'helper.jar','w') as archive:
    archive.write(helper/'classes.dex','classes.dex')
port.run(*port.java,'disassemble',work/'helper.jar','classes.dex',work/'helper-smali')
shutil.copytree(work/'helper-smali',smali,dirs_exist_ok=True)
port.run(*port.java,'assemble',smali,work/'classes.dex')
unsigned=work/'unsigned.apk'
with zipfile.ZipFile(source) as original, zipfile.ZipFile(unsigned,'w') as result:
    manifest, manifest_edits=patch(original.read('AndroidManifest.xml'),REVISION)
    for info in original.infolist():
        name=info.filename;upper=name.upper()
        if upper.startswith('META-INF/') and (upper.endswith(('.SF','.RSA','.DSA','.EC')) or upper=='META-INF/MANIFEST.MF'):continue
        data=manifest if name=='AndroidManifest.xml' else (work/'classes.dex').read_bytes() if name=='classes.dex' else original.read(info)
        result.writestr(info,data)
aligned=work/'aligned.apk'
port.run(sdk/'bin/zipalign','-p','4',unsigned,aligned)
private=REPO/'LOCAL_PRESERVE_H700_BASELINE_20261028/ayaspace2-20261101';private.mkdir(exist_ok=True)
key=private/'trial.keystore';password=private/'trial-password.private.txt'
if not key.exists():
    password.write_text(secrets.token_hex(24)+'\n');os.chmod(password,0o600)
    port.run(port.jdk/'keytool','-genkeypair','-keystore',key,'-alias','ayaspace-trial','-storepass:file',password,'-keypass:file',password,'-dname','CN=H700 Local Compatibility Trial','-keyalg','RSA','-keysize','2048','-validity','3650')
output=out/('PocketMuseum_0.3.3_H700_Android10_r%d.apk' % REVISION)
assert not output.exists()
signed=work/'signed.apk'
port.run(port.jdk/'java','-Xmx1g','-jar',sdk/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','ayaspace-trial','--ks-pass','file:'+str(password),'--out',signed,aligned)
verified=port.run(port.jdk/'java','-Xmx1g','-jar',sdk/'lib/apksigner.jar','verify','--print-certs',signed)
shutil.copyfile(signed,output)
(out/('signature-r%d.txt' % REVISION)).write_text(verified)
# Every native library/asset/resource must remain identical to the supplied APK.
with zipfile.ZipFile(source) as a, zipfile.ZipFile(output) as b:
    preserved=[n for n in a.namelist() if n not in ('AndroidManifest.xml','classes.dex') and not n.upper().startswith('META-INF/')]
    assert all(hashlib.sha256(a.read(n)).digest()==hashlib.sha256(b.read(n)).digest() for n in preserved)
receipt={'output':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'manifest_edits':manifest_edits,'storage_call_sites':storage_sites,'edited_classes':edits,'unchanged_asset_native_resource_entries':len(preserved),'runtime_accepted':False}
(out/('build-r%d.json' % REVISION)).write_text(json.dumps(receipt,indent=2)+'\n')
print('AYASPACE_ANDROID10_BUILT',output.name,receipt['sha256'],flush=True)
