"""Read-only symbol screen against the actual GSI boot jars and ported services."""
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained, dump
from dex_port import DexPort
constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
OUT = REPO / 'out/dualabi-parity-20261101'
WORK = ROOT / 'api-audit-v3'
port = DexPort(REPO, WORK)
image = Path('/home/lpf/h700-dualabi-test1-20261031/system.candidate.raw')
dependencies = [ROOT / 'inputs-gsi/framework.jar', ROOT / 'services-v3/services.parity.jar']
for name in ('core-oj', 'core-libart', 'apache-xml', 'bouncycastle', 'conscrypt', 'okhttp',
             'ext', 'telephony-common', 'ims-common', 'voip-common', 'android.hidl.base-V1.0-java',
             'android.test.base', 'updatable-media'):
    target = WORK / (name + '.jar')
    found = []
    for directory in ('/system/framework', '/system/apex/com.android.runtime.release/javalib',
                      '/system/apex/com.android.conscrypt.release/javalib',
                      '/system/apex/com.android.conscrypt/javalib', '/system/apex/com.android.media/javalib'):
        inside = directory + '/' + name + '.jar'
        stat = port.run('debugfs', '-R', 'stat ' + inside, image)
        if 'Type: regular' in stat:
            found.append(inside)
    if not found:
        print('API_OPTIONAL_BOOT_JAR_NOT_FOUND', name, flush=True)
        continue
    dump(image, found[0], target)
    dependencies.append(target)
apps = [ROOT / 'settings-api-v1/Settings.apk', ROOT / 'systemui-v6/SystemUI.apk']
command = ['taskset', '-c', '0', port.jdk / 'java', '-Xmx2g', '-cp',
           str(WORK) + ':' + str(port.apktool), 'FrameworkApiAudit',
           ':'.join(map(str, dependencies)), *apps]
print('API_LINKAGE_SCREEN_START', flush=True)
result = port.run(*command)
(OUT / 'api-audit-v3.txt').write_text(result)
print(result[-24000:], flush=True)
(OUT / 'api-audit-v3.json').write_text(json.dumps({
    'dependencies': [p.name for p in dependencies], 'output': result,
    'runtime_accepted': False, 'access_flags_jni_and_reflection_not_validated': True,
}, indent=2) + '\n')
if __import__('re').search(r'UNRESOLVED=[1-9]', result):
    raise ValueError('Unresolved GSI API remains')
print('FINAL_CHANGED_COMPONENT_API_SCREEN_PASS', flush=True)
