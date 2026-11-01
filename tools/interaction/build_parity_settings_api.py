"""Adapt three unmodified BSP FaceManager calls to the actual GSI API29 signatures."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from dex_port import DexPort, methods
constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
OUT = REPO / 'out/dualabi-parity-20261101'
WORK = ROOT / 'settings-api-v1'
port = DexPort(REPO, WORK)
source = ROOT / 'rebased-apps-v2/Settings.apk'
assert hashlib.sha256(source.read_bytes()).hexdigest() == json.loads(
    (OUT / 'rebased-apps-v2.json').read_text())['apps']['Settings']['sha256']
expected = {'enroll(I[BLandroid/os/CancellationSignal;Landroid/hardware/face/FaceManager$EnrollmentCallback;[I)V',
            'getFeature(IILandroid/hardware/face/FaceManager$GetFeatureCallback;)V',
            'setFeature(IIZ[BLandroid/hardware/face/FaceManager$SetFeatureCallback;)V'}
assert set(json.loads((OUT / 'gsi-face-signatures.json').read_text())) == expected
prefix = 'com/android/settings/biometrics/face/'
sidecar = prefix + 'FaceEnrollSidecar'
attention = prefix + 'FaceSettingsAttentionPreferenceController'
context_owner = 'com/android/settingslib/core/AbstractPreferenceController'
original = port.load(source, [sidecar, attention, context_owner], 'settings')
assert re.search(r'^\.field protected[^\n]*mContext:Landroid/content/Context;', original[context_owner], re.M)
changed = {}

def replace_call(text, old, new, locals_count):
    occurrences = []
    for signature, block in methods(text).items():
        if old in block:
            occurrences.append((signature, block))
    assert len(occurrences) == 1
    signature, block = occurrences[0]
    declaration = re.search(r'(?m)^    \.(?:registers|locals) \d+[^\n]*', block)
    assert declaration
    # baksmali uses p-register notation; added local slots do not move the
    # symbolic parameters or any original local register.
    modified = block[:declaration.start()] + '    .locals ' + str(locals_count) + block[declaration.end():]
    assert modified.count(old) == 1
    modified = modified.replace(old, new, 1)
    return text.replace(block, modified, 1)

old = 'invoke-virtual {v0, v1, v2, v3, v4}, Landroid/hardware/face/FaceManager;->enroll([BLandroid/os/CancellationSignal;Landroid/hardware/face/FaceManager$EnrollmentCallback;[I)V'
new = '''move-object v5, v4
    move-object v4, v3
    move-object v3, v2
    move-object v2, v1
    iget v1, p0, Lcom/android/settings/biometrics/BiometricEnrollSidecar;->mUserId:I
    const/16 v6, -0x2710
    if-ne v1, v6, :h700_face_user_ready
    invoke-static {}, Landroid/os/UserHandle;->myUserId()I
    move-result v1
    :h700_face_user_ready
    invoke-virtual/range {v0 .. v5}, Landroid/hardware/face/FaceManager;->enroll(I[BLandroid/os/CancellationSignal;Landroid/hardware/face/FaceManager$EnrollmentCallback;[I)V'''
changed[sidecar] = replace_call(original[sidecar], old, new, 7)
old = 'invoke-virtual {v0, v1, v2}, Landroid/hardware/face/FaceManager;->getFeature(ILandroid/hardware/face/FaceManager$GetFeatureCallback;)V'
new = '''iget-object v3, p0, Lcom/android/settingslib/core/AbstractPreferenceController;->mContext:Landroid/content/Context;
    invoke-virtual {v3}, Landroid/content/Context;->getUserId()I
    move-result v3
    invoke-virtual {v0, v3, v1, v2}, Landroid/hardware/face/FaceManager;->getFeature(IILandroid/hardware/face/FaceManager$GetFeatureCallback;)V'''
text = replace_call(original[attention], old, new, 4)
old = 'invoke-virtual {v0, v3, p1, v1, v2}, Landroid/hardware/face/FaceManager;->setFeature(IZ[BLandroid/hardware/face/FaceManager$SetFeatureCallback;)V'
new = '''move-object v5, v2
    move-object v4, v1
    move v2, v3
    move v3, p1
    iget-object v1, p0, Lcom/android/settingslib/core/AbstractPreferenceController;->mContext:Landroid/content/Context;
    invoke-virtual {v1}, Landroid/content/Context;->getUserId()I
    move-result v1
    invoke-virtual/range {v0 .. v5}, Landroid/hardware/face/FaceManager;->setFeature(IIZ[BLandroid/hardware/face/FaceManager$SetFeatureCallback;)V
    const/4 v3, 0x1'''
changed[attention] = replace_call(text, old, new, 6)
unsigned = WORK / 'Settings-unsigned.apk'
receipt = port.emit(source, 'settings', changed, {}, unsigned)
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
aligned = WORK / 'Settings-aligned.apk'
target = WORK / 'Settings.apk'
port.run(sdk / 'bin/zipalign', '-f', '-p', '4', unsigned, aligned)
port.run(port.jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'sign',
         '--key', native / 'build/make/target/product/security/platform.pk8',
         '--cert', native / 'build/make/target/product/security/platform.x509.pem',
         '--min-sdk-version', '29', '--out', target, aligned)
port.run(port.jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--min-sdk-version', '29', target)
receipt.update({'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'added_user_ids': 'Enrollment target user with USER_NULL fallback; preference Context user',
                'new_facial_hardware_support_claimed': False, 'runtime_accepted': False})
(OUT / 'settings-api-v1.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('SETTINGS_GSI_FACE_API_COMPATIBILITY_CANDIDATE_COMPLETE', flush=True)
