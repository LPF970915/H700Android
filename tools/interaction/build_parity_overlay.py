"""Build the final ARM32 framework resource overlay against the actual GSI IDs."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'framework-overlay-v3'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
java = native / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace')[-5000:] + p.stderr.decode(errors='replace')[-5000:])
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

framework = ROOT / 'inputs-gsi/framework-res.apk'
listing = run(sdk / 'bin/aapt', 'dump', 'resources', framework)
resources = set(re.findall(r'spec resource 0x[0-9a-f]+ android:([^: ]+):', listing))
public_attributes = set(re.findall(r'spec resource 0x[0-9a-f]+ android:attr/([^: ]+): flags=0x40000000', listing))
source = REPO / 'android/h700-android10/device/roc/rgsp/overlay/frameworks/base/core/res/res'
shutil.copytree(source, WORK / 'res')
config = WORK / 'res/values/config.xml'
tree = ET.parse(config)
skipped = []
retained = []
for node in list(tree.getroot()):
    name = node.tag + '/' + node.attrib['name']
    if name not in resources:
        tree.getroot().remove(node)
        skipped.append(name)
    else:
        retained.append(name)
tree.write(config, encoding='utf-8', xml_declaration=True)
for file in (WORK / 'res/layout').glob('*.xml'):
    assert 'layout/' + file.stem in resources
    tree = ET.parse(file)
    android_ns = 'http://schemas.android.com/apk/res/android'
    private_ns = 'http://schemas.android.com/apk/prv/res/android'
    for node in tree.iter():
        for key, value in list(node.attrib.items()):
            # The source overlays originally compiled inside package android.
            # A separate RRO must explicitly address those framework symbols.
            value = re.sub(r'@([a-zA-Z_]+)/(\w+)', r'@*android:\1/\2', value)
            value = re.sub(r'\?attr/(\w+)', r'?android:attr/\1', value)
            if key.startswith('{' + android_ns + '}'):
                attr = key.split('}', 1)[1]
                if attr not in public_attributes:
                    assert 'attr/' + attr in resources or '^attr-private/' + attr in resources, attr
                    del node.attrib[key]
                    key = '{' + private_ns + '}' + attr
            node.attrib[key] = value
    tree.write(file, encoding='utf-8', xml_declaration=True)
manifest = WORK / 'AndroidManifest.xml'
manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.roc.h700.framework.overlay" android:versionCode="1" android:versionName="1.0-parity">
    <uses-sdk android:minSdkVersion="29" android:targetSdkVersion="29" />
    <overlay android:targetPackage="android" android:isStatic="true" android:priority="999" />
    <application android:hasCode="false" android:label="H700 controller framework resources" />
</manifest>
''')
unsigned = WORK / 'overlay-unsigned.apk'
run(sdk / 'bin/aapt', 'package', '-f', '--auto-add-overlay', '-M', manifest,
    '-S', WORK / 'res', '-I', framework, '-F', unsigned)
aligned = WORK / 'overlay-aligned.apk'
target = WORK / 'H700FrameworkOverlay.apk'
run(sdk / 'bin/zipalign', '-f', '4', unsigned, aligned)
run(java, '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'sign',
    '--key', native / 'build/make/target/product/security/platform.pk8',
    '--cert', native / 'build/make/target/product/security/platform.x509.pem',
    '--min-sdk-version', '29', '--out', target, aligned)
run(java, '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--min-sdk-version', '29', target)
receipt = {'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
           'overrides': retained, 'absent_gsi_configuration_names_skipped': skipped,
           'resolver_layouts': sorted(p.stem for p in (WORK / 'res/layout').glob('*.xml')),
           'runtime_accepted': False, 'requires_coherent_new_system_signing': True}
(OUT / 'framework-overlay-v3.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('FRAMEWORK_RESOURCE_OVERLAY_CANDIDATE_COMPLETE', json.dumps(receipt), flush=True)
