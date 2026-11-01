"""Scoped GSI services ports: rotation, controller IME, ROMS visibility and OEM state."""
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
sys.path.insert(0, str(REPO / 'tools/rotation'))
from patch_framework import patch as rotation_patch
from dex_port import DexPort, methods

constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
OUT = REPO / 'out/dualabi-parity-20261101'
WORK = ROOT / 'services-v3'
port = DexPort(REPO, WORK)
names = {
    'activity': 'com/android/server/wm/ActivityRecord',
    'ime': 'com/android/server/inputmethod/InputMethodManagerService',
    'oem': 'com/android/server/oemlock/OemLockService',
    'server': 'com/android/server/SystemServer',
    'storage': 'com/android/server/StorageManagerService',
}
old_fallback = 'com/android/server/oemlock/RgspUnsupportedOemLock'
current = port.load(ROOT / 'inputs-gsi/services.jar', list(names.values()), 'gsi')
previous = port.load(ROOT / 'inputs-arm32/services.jar', [names['ime'], names['oem'], old_fallback], 'arm32')
changed = {**current}
changed[names['activity']] = rotation_patch(current[names['activity']])
# The GSI retains parameter debug names absent from the original BSP JAR.
# Keep those headers before executable instructions instead of asking DEX
# assembly to move them across the new prologue.
activity = changed[names['activity']]
for signature, block in methods(activity).items():
    if '->h700ForceLandscape()Z' not in block:
        continue
    params = re.findall(r'(?m)^    \.param[^\n]*\n', block)
    if not params:
        continue
    assert '.end param' not in block
    normalized = re.sub(r'(?m)^    \.param[^\n]*\n', '', block)
    declaration = re.search(r'(?m)^    \.(?:registers|locals) \d+[^\n]*\n', normalized)
    normalized = normalized[:declaration.end()] + ''.join(params) + normalized[declaration.end():]
    activity = activity.replace(block, normalized, 1)
changed[names['activity']] = activity

def transplant(name, signature):
    original = methods(current[name])[signature]
    replacement = methods(previous[name])[signature]
    assert original.splitlines()[0] == replacement.splitlines()[0], (name, signature)
    changed[name] = changed[name].replace(original, replacement, 1)

transplant(names['ime'], 'onActionLocaleChanged()V')
transplant(names['oem'], 'getOemLock(Landroid/content/Context;)Lcom/android/server/oemlock/OemLock;')
changed[names['oem']] += '''
.method public static h700HasOemService()Z
    .locals 2
    sget-object v0, Landroid/os/Build;->DEVICE:Ljava/lang/String;
    const-string v1, "rgsp"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :h700_original_hal
    const/4 v0, 0x1
    return v0
    :h700_original_hal
    invoke-static {}, Lcom/android/server/oemlock/OemLockService;->isHalPresent()Z
    move-result v0
    return v0
.end method
'''
old_call = 'Lcom/android/server/oemlock/OemLockService;->isHalPresent()Z'
assert current[names['server']].count(old_call) == 1
changed[names['server']] = current[names['server']].replace(old_call,
    'Lcom/android/server/oemlock/OemLockService;->h700HasOemService()Z')

signature = 'onVolumeCreatedLocked(Landroid/os/storage/VolumeInfo;)V'
original = methods(current[names['storage']])[signature]
pattern = r'(invoke-virtual \{[^\n]+\}, Landroid/os/storage/DiskInfo;->isAdoptable\(\)Z\s+move-result (v\d+))'
matches = list(re.finditer(pattern, original))
assert len(matches) == 1, len(matches)
match = matches[0]
register = match[2]
assert ':h700_visible_volume' not in original
addition = f'''
    if-nez {register}, :h700_visible_volume
    invoke-static/range {{p1 .. p1}}, Lcom/android/server/StorageManagerService;->h700VisibleRoms(Landroid/os/storage/VolumeInfo;)Z
    move-result {register}
    :h700_visible_volume
'''
modified = original[:match.end()] + addition + original[match.end():]
changed[names['storage']] = current[names['storage']].replace(original, modified, 1)
changed[names['storage']] += '''
.method private static h700VisibleRoms(Landroid/os/storage/VolumeInfo;)Z
    .locals 3
    sget-object v0, Landroid/os/Build;->DEVICE:Ljava/lang/String;
    const-string v1, "rgsp"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :h700_not_roms
    iget-object v0, p0, Landroid/os/storage/VolumeInfo;->disk:Landroid/os/storage/DiskInfo;
    if-eqz v0, :h700_not_roms
    invoke-virtual {v0}, Landroid/os/storage/DiskInfo;->getId()Ljava/lang/String;
    move-result-object v0
    const-string v1, "disk:179,0"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :h700_not_roms
    iget-object v0, p0, Landroid/os/storage/VolumeInfo;->id:Ljava/lang/String;
    const-string v1, "public:179,8"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    return v0
    :h700_not_roms
    const/4 v0, 0x0
    return v0
.end method
'''
receipt = port.emit(ROOT / 'inputs-gsi/services.jar', 'gsi', changed,
                    {old_fallback: previous[old_fallback]}, WORK / 'services.parity.jar')
receipt.update({'runtime_accepted': False, 'full_source_framework_rebuild': False,
                'roms_native_vold_port_still_required': True,
                'ime_method_from_pinned_arm32': True, 'oem_fallback_reports_unsupported': True})
(OUT / 'services-v3.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('SERVICES_SCOPED_PORT_CANDIDATE_COMPLETE', flush=True)
