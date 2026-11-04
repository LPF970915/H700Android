"""Derive source64-only modules from immutable BSP inputs; no device access."""
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET


def block(text, kind, name):
    start = next(m.start() for m in re.finditer(kind + r'\s*\{', text)
                 if re.match(r'\s*name:\s*"' + re.escape(name) + '"', text[m.end():]))
    depth = 0
    for i in range(text.index('{', start), len(text)):
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return text[start:i+1]
    raise ValueError(name)


def generate(repo, native, dest):
    nav = dest / 'Navigation'
    shutil.copytree(native / 'device/roc/rgsp/RGSPNavigation', nav, dirs_exist_ok=True)
    p = nav / 'Android.bp'
    p.write_text(p.read_text().replace('name: "RGSPNavigation"', 'name: "ROCNavigation"'))
    p = nav / 'AndroidManifest.xml'
    s = p.read_text().replace('android:versionCode="8" android:versionName="1.5-menu-shade"',
                            'android:versionCode="16" android:versionName="2.2-source64-select-fallback"')
    assert 'android:versionCode="16"' in s
    p.write_text(s)
    p = nav / 'src/com/roc/rgsp/navtrial/NavigationService.java'
    s = p.read_text()
    old = 'if(!"settings".equals(mode) || !target.isEnabled() || range==null'
    assert s.count(old) == 1
    s = s.replace(old, 'boolean shadeRange = "shade".equals(mode) &&\n'
                  '                "com.android.systemui:id/slider".equals(target.getViewIdResourceName());\n'
                  '        if((!"settings".equals(mode) && !shadeRange) || !target.isEnabled() || range==null')
    old = 'float step=range.getType()==AccessibilityNodeInfo.RangeInfo.RANGE_TYPE_INT ? 1 : (range.getMax()-range.getMin())/20f;'
    assert s.count(old) == 1
    s = s.replace(old, 'float step=shadeRange ? Math.max(1f, (range.getMax()-range.getMin())/20f)\n'
                  '                : range.getType()==AccessibilityNodeInfo.RangeInfo.RANGE_TYPE_INT ? 1 : (range.getMax()-range.getMin())/20f;')
    # The source SystemUI already owns A/power focus; do not add GSI proxies.
    assert 'nativeSystemUi()' not in s and 'PrototypeUnlock' not in s
    old = 'if((key==KeyEvent.KEYCODE_MENU || key==KeyEvent.KEYCODE_BUTTON_SELECT)'
    assert s.count(old) == 1
    s = s.replace(old, 'if((key==KeyEvent.KEYCODE_MENU && event.getScanCode()!=310)')
    old = '''        @Override public boolean dispatchKeyEvent(KeyEvent event) {
            if (mouse != null && mouse.onKey(event)) return true;
            int code = event.getKeyCode();'''
    assert s.count(old) == 1
    s = s.replace(old, '''        @Override public boolean dispatchKeyEvent(KeyEvent event) {
            int code = event.getKeyCode();''')
    old = '''                    || code == KeyEvent.KEYCODE_ESCAPE) {
                if (event.getAction() == KeyEvent.ACTION_UP'''
    assert s.count(old) == 1
    s = s.replace(old, '''                    || code == KeyEvent.KEYCODE_ESCAPE) {
                if (mouse != null && mouse.onKey(event)) return true;
                if (event.getAction() == KeyEvent.ACTION_UP''')
    old = 'if(!hasFocus) {stopRepeat();held.clear();armedIdentity=null;armedKey=0;}'
    assert s.count(old) == 1
    s = s.replace(old, 'if(!hasFocus) {stopRepeat();held.clear();menu.clear();armedIdentity=null;armedKey=0; if(mouse!=null) mouse.windowFocusLost();}')
    p.write_text(s)
    p = nav / 'src/com/roc/rgsp/navtrial/MouseHotkey.java'
    s = p.read_text().replace('return fallback && scan == 310 && key == 82 ? SELECT : key;',
                             'return scan == 310 && key == 82 ? SELECT : key;')
    s = s.replace('    void clear() {', '    String debugState() { return "held="+held+" presses="+presses.size(); }\n\n    void clear() {')
    p.write_text(s)
    p = nav / 'src/com/roc/rgsp/navtrial/MouseController.java'
    s = p.read_text()
    s = s.replace('    boolean isActive() { return active; }', '''    boolean isActive() { return active; }

    void windowFocusLost() {
        // Releases may be cancelled when the Settings overlay loses focus.
        // Never carry those held keys into the next standalone Select hold.
        // Active gestures intentionally release focus to deliver a touch.
        if (!active) { hotkey.clear(); cancelSelectToggle(); }
    }''')
    s = s.replace('event.isCanceled(), event.getEventTime());', '''event.isCanceled(), event.getEventTime());
        if (event.getScanCode()==310) android.util.Log.i("ROCSelect",
            "key="+key+" action="+event.getAction()+" flags="+event.getFlags()
            +" canonical="+triggerKey+" result="+hotkey.lastResult+" "+hotkey.debugState());''')
    p.write_text(s)

    # The source framework's legacy ROMS visibility rule cannot expose TF2.
    services = dest / 'Services'
    core = services / 'Core'
    for original, target in [(native / 'frameworks/base/services/core/java', core / 'java'),
                             (native / 'frameworks/base/services/java', services / 'java')]:
        shutil.copytree(original, target, dirs_exist_ok=True)
    p = core / 'java/com/android/server/StorageManagerService.java'
    s = p.read_text()
    anchor = 'final boolean rgspRoms = "rgsp".equals(SystemProperties.get("ro.product.device"))'
    assert s.count(anchor) == 1
    s = s.replace(anchor, 'final boolean rocUnified = "unified-v1".equals(SystemProperties.get("ro.roc.storage.layout"));\n'
                  '            final boolean rocTf2 = rocUnified && vol.disk.isSd() && vol.disk.sysPath != null\n'
                  '                    && vol.disk.sysPath.contains("/sdc2/mmc_host/");\n'
                  '            final boolean rgspRoms = !rocUnified && "rgsp".equals(SystemProperties.get("ro.product.device"))')
    s = s.replace('if (vol.disk.isAdoptable() || rgspRoms)', 'if (vol.disk.isAdoptable() || rgspRoms || rocTf2)')
    p.write_text(s)
    bp = (native / 'frameworks/base/services/core/Android.bp').read_text()
    bp = bp[:bp.index('prebuilt_etc {')]
    # Includes :module genrule references, not only quoted module names.
    bp = bp.replace('services.core', 'services.rocsource.core')
    assert 'services.core' not in bp
    (core / 'Android.bp').write_text(bp)
    bp = block((native / 'frameworks/base/services/Android.bp').read_text(), 'java_library', 'services')
    bp = bp.replace('name: "services"', 'name: "services.rocsource"').replace('"services.core"', '"services.rocsource.core"')
    (services / 'Android.bp').write_text(bp+'\n')
    shutil.copyfile(native / 'frameworks/base/services/art-profile', services / 'art-profile')

    # The original Wi-Fi jar has a required-install edge to services.jar.
    # Reuse its unchanged Java/AIDL sources with only private module edges.
    wifi = dest / 'Wifi'
    wifi.mkdir()
    original = native / 'frameworks/opt/net/wifi/service'
    s = (original / 'Android.mk').read_text()
    s = s.replace('LOCAL_PATH := $(call my-dir)', 'LOCAL_PATH := frameworks/opt/net/wifi/service')
    s = re.sub(r'(?m)^(\s*)services(\s*\\?)$', r'\1services.rocsource\2', s)
    s = s.replace('LOCAL_MODULE := wifi-service', 'LOCAL_MODULE := wifi-service.rocsource')
    s = s.replace('LOCAL_INIT_RC := wifi-events.rc', '# Init is copied by the private product under a unique name.')
    (wifi / 'Android.mk').write_text(s)
    shutil.copyfile(original / 'wifi-events.rc', wifi / 'roc-wifi-events.rc')

    light = dest / 'Light'
    shutil.copytree(repo / 'android/h700-android10/device/roc/rgsp/H700Light', light, dirs_exist_ok=True)
    p = light / 'Backlight.cpp'
    s = p.read_text()
    old = 'unsigned long args[4] = {0, brightness(argb), 0, 0};'
    assert s.count(old) == 1
    s = s.replace(old, '''// The retained RG34XXSP display stack reads back 200 at ioctl value
    // 255, while 248/250/254 remain exact. Keep the logical endpoint
    // monotonic using the highest validated driver value; true off stays 0.
    // This is a private product compatibility rule, not a kernel fix.
    const unsigned int requested = brightness(argb);
    const unsigned int driver = requested == 255 ? 254 : requested;
    unsigned long args[4] = {0, driver, 0, 0};''')
    p.write_text(s)
    p = light / 'Android.bp'
    s = p.read_text().replace('name: "android.hardware.light@2.0-service.h700",',
                            'name: "android.hardware.light@2.0-service.rocsource",')
    s = s.replace('    vintf_fragments: ["h700-light.xml"],\n', '')
    s = s.replace('init_rc: ["h700-light.rc"]', 'init_rc: ["roc-light.rc"]')
    p.write_text(s)
    (light / 'roc-light.rc').write_text((light / 'h700-light.rc').read_text().replace(
        '/vendor/bin/hw/android.hardware.light@2.0-service.h700',
        '/vendor/bin/hw/android.hardware.light@2.0-service.rocsource'))
    from sys import path
    path.insert(0, str(repo / 'tools/interaction'))
    from omx_manifest import BLOCK
    s = (native / 'device/roc/rgsp/manifest.xml').read_text()
    assert not any(h.findtext('name') == 'android.hardware.media.omx' for h in ET.fromstring(s).findall('hal'))
    # This is an unmerged board fragment; the sepolicy section is added later.
    s = s.replace('</manifest>', BLOCK.decode() + '</manifest>')
    hal = ET.tostring(ET.fromstring((light / 'h700-light.xml').read_bytes()).find('hal'), encoding='unicode')
    # The running supplicant registers 1.2; omitting its declaration makes the
    # framework fall back to 1.0 listInterfaces instead of 1.1 addInterface.
    supplicant = '''<hal format="hidl"><name>android.hardware.wifi.supplicant</name>
<transport>hwbinder</transport><version>1.2</version><interface><name>ISupplicant</name>
<instance>default</instance></interface><fqname>@1.2::ISupplicant/default</fqname></hal>'''
    thermal = '<hal format="hidl"><name>android.hardware.thermal</name><transport>hwbinder</transport><version>2.0</version><interface><name>IThermal</name><instance>default</instance></interface></hal>'
    (dest / 'manifest.xml').write_text(s.replace('</manifest>', hal + '\n' + supplicant + '\n' + thermal + '\n</manifest>'))

    # Private vold library/binary; the AIDL protocol and old modules stay intact.
    vold = dest / 'Vold'
    for p in (native / 'system/vold').rglob('*'):
        if p.is_file() and p.suffix in ['.cpp', '.h']:
            t = vold / p.relative_to(native / 'system/vold')
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, t)
    bp = (native / 'system/vold/Android.bp').read_text()
    lib = block(bp, 'cc_library_static', 'libvold').replace('name: "libvold"', 'name: "libvold.rocsource"')
    binary = block(bp, 'cc_binary', 'vold').replace('name: "vold",', 'name: "vold.rocsource",')
    binary = binary.replace('static_libs: ["libvold"]', 'static_libs: ["libvold.rocsource"]')
    binary = binary.replace('"vold.rc"', '"vold.rocsource.rc"').replace('"wait_for_keymaster.rc"', '"roc-wait-for-keymaster.rc"')
    (vold / 'Android.bp').write_text(lib + '\n\n' + binary + '\n')
    for old, new in [('vold.rc', 'vold.rocsource.rc'), ('wait_for_keymaster.rc', 'roc-wait-for-keymaster.rc')]:
        shutil.copyfile(native / 'system/vold' / old, vold / new)
    p = vold / 'vold.rocsource.rc'
    p.write_text(p.read_text().replace('service vold /system/bin/vold', 'service vold /system/bin/vold.rocsource'))
    shutil.copyfile(repo / 'tools/source64/storage/RocStoragePolicy.h', vold / 'RocStoragePolicy.h')
    (vold / 'RocStorage.h').write_text('''#pragma once
#include "RocStoragePolicy.h"
#include <android-base/properties.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/sysmacros.h>
#include <string>
inline bool rocUnified() {
    return android::base::GetProperty("ro.roc.storage.layout", "") == "unified-v1";
}
inline bool rocProtectedMmc(dev_t device) {
    if (!rocUnified() || major(device) != 179) return false;
    char resolved[PATH_MAX];
    std::string sys = "/sys/dev/block/" + std::to_string(major(device)) + ":" + std::to_string(minor(device));
    return !realpath(sys.c_str(), resolved) || !rocTf2Path(resolved);
}
''')
    for file, function in [('model/Disk.cpp', 'isRgspBootCard'), ('model/PublicVolume.cpp', 'isRgspBootPartition')]:
        p = vold / file
        s = p.read_text().replace('#include <fcntl.h>', '#include "../RocStorage.h"\n#include <fcntl.h>', 1)
        old = re.search(r'static bool ' + function + r'\(dev_t device\) \{.*?\n\}', s, re.S)
        assert old
        s = s[:old.start()] + 'static bool ' + function + '(dev_t device) {\n    if (rocUnified()) return rocProtectedMmc(device);\n' + old[0].split('{', 1)[1] + s[old.end():]
        if file == 'model/Disk.cpp':
            s = s.replace('status_t Disk::readPartitions() {', 'status_t Disk::readPartitions() {\n'
                          '    if (rocUnified() && rocProtectedMmc(mDevice)) return -EPERM;', 1)
        p.write_text(s)
    p = vold / 'VolumeManager.cpp'
    s = p.read_text().replace('#include "VolumeManager.h"', '#include "VolumeManager.h"\n#include "RocStorage.h"', 1)
    anchor = 'case NetlinkEvent::Action::kAdd: {'
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor + '\n            if (rocUnified() && major == 179 && !rocTf2Path(eventPath)) {\n'
                  '                LOG(ERROR) << "ROC OS refuses boot-card/unknown MMC as external storage";\n'
                  '                break;\n            }')
    p.write_text(s)

    resize = dest / 'Resize'
    resize.mkdir(exist_ok=True)
    for p in (native / 'external/e2fsprogs/resize').iterdir():
        if p.suffix in ['.c', '.h']:
            shutil.copyfile(p, resize / p.name)
    shutil.copyfile(native / 'external/e2fsprogs/version.h', resize / 'version.h')
    p = resize / 'main.c'
    p.write_text(p.read_text().replace('#include "../version.h"', '#include "version.h"'))
    s = (native / 'external/e2fsprogs/resize/Android.bp').read_text()
    s = s.replace('name: "resize2fs",', 'name: "roc-resize2fs-static",\n    static_executable: true,')
    s = s.replace('    system_shared_libs: ["libc", "libdl"],\n', '')
    s = s.replace('    host_supported: true,\n', '').replace('    shared_libs:', '    static_libs:')
    (resize / 'Android.bp').write_text(s)

    from sys import path
    path.insert(0, str(repo / 'tools/source64/storage'))
    from layout import c_identity
    storage = dest / 'Storage'
    storage.mkdir(exist_ok=True)
    shutil.copyfile(repo / 'tools/source64/storage/grow_gpt.c', storage / 'grow_gpt.c')
    (storage / 'identity.h').write_text(c_identity())
    (storage / 'Android.bp').write_text('''cc_binary {
    name: "roc-grow-userdata-gpt",
    srcs: ["grow_gpt.c"],
    static_executable: true,
    compile_multilib: "64",
    cflags: ["-Wall", "-Wextra", "-Werror"],
}
''')


def boot_contract(repo, root, output):
    """Write loose boot files/metadata only, never a boot or whole-card image."""
    import hashlib
    import json
    import sys
    sys.path.insert(0, str(repo / 'tools'))
    from prepare_h700_dualabi_handoff import ramdisk_init
    from layout import derive, DATA_FS_UUID
    prefix = Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
    locked = json.loads((repo / 'docs/baselines/rg34xxsp-arm64-defaults-test2a-20261101/image-lock.json').read_text())
    expected = next(x for x in locked['ranges'] if x['name'] == 'prefix')['sha256']
    with prefix.open('rb') as f:
        assert hashlib.file_digest(f, 'sha256').hexdigest() == expected
    old = ramdisk_init(prefix)
    assert hashlib.sha256(old).hexdigest() == '3b8c6c1458d28c9a664900f92a92b111b91da2afbf69ad1e606cb9f47c5db053'
    s = old.decode()
    vars_start = s.index('SYSTEM_DEV=/dev/mmcblk0p5')
    vars_end = s.index('LOG=/dev/console', vars_start)
    s = s[:vars_start] + s[vars_end:]
    start = s.index('tries=0')
    end = s.index('/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"')
    replacement = '''tries=0
TF1=
while [ "$tries" -lt 30 ]; do
    TF1=
    for sys in /sys/class/block/mmcblk[0-9] /sys/class/block/mmcblk[0-9][0-9]; do
        [ -e "$sys" ] || continue
        case "$(readlink -f "$sys")" in
            */sdc0/mmc_host/*/block/mmcblk*)
                [ -z "$TF1" ] || fail "ambiguous TF1 controller"
                TF1=/dev/${sys##*/}
                ;;
        esac
    done
    if [ -n "$TF1" ] && [ -b "${TF1}p5" ] && [ -b "${TF1}p6" ] && [ -b "${TF1}p7" ]; then break; fi
    tries=$((tries+1)); sleep 1
done
[ -n "$TF1" ] && [ -b "${TF1}p5" ] && [ -b "${TF1}p6" ] && [ -b "${TF1}p7" ] || fail "TF1 is unavailable"
SYSTEM_DEV=${TF1}p5
VENDOR_DEV=${TF1}p6
DATA_DEV=${TF1}p7
/bin/sh /grow/grow-userdata.sh "$TF1" || fail "userdata capacity preparation failed"'''
    s = s[:start] + replacement + s[end+len('/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"'):]
    start = s.index('for spec in \\\n')
    end = s.index('\ndone', start) + len('\ndone')
    s = s[:start] + '''mkdir -p /dev/block/by-name
for spec in "system:$SYSTEM_DEV" "vendor:$VENDOR_DEV" "userdata:$DATA_DEV"; do
    name=${spec%%:*}
    device=${spec#*:}
    ln -snf "$device" "/dev/block/by-name/$name"
done''' + s[end:]
    s = s.replace('v5f ROMS vold ramdisk running', 'ROC OS unified userdata ramdisk')
    s = s.replace('ROMS delegated to Android vold', 'TF1 internal userdata; TF2 removable')
    assert 'p8' not in s and '/grow/auto-grow.sh' not in s and 'ROMS_DEV' not in s
    folder = root / 'round2-boot-contract'
    folder.mkdir(exist_ok=True)
    # Version by content hash: prior drafts remain untouched.
    ident = hashlib.sha256(s.encode()).hexdigest()[:12]
    boot = folder / ident
    boot.mkdir(exist_ok=True)
    (boot / 'init').write_text(s)
    shutil.copyfile(repo / 'tools/source64/storage/grow_userdata.sh', boot / 'grow-userdata.sh')
    with prefix.open('rb') as f:
        primary, backup = derive(f.read(2048))
    (boot / 'primary-gpt.template').write_bytes(primary)
    (boot / 'backup-gpt.template').write_bytes(backup)
    record = {'work': str(boot), 'prefix_sha256': expected, 'init_sha256': hashlib.sha256(s.encode()).hexdigest(),
              'userdata_fs_uuid': str(DATA_FS_UUID), 'no_p8': True, 'compact_table_slots': 8, 'used_partitions': 7,
              'static_ramdisk_tools_required': ['roc-grow-userdata-gpt', 'e2fsck_static', 'roc-resize2fs-static'],
              'boot_image_created': False, 'whole_card_image_created': False, 'device_boot_accepted': False}
    (output / 'boot-contract.json').write_text(json.dumps(record, indent=2)+'\n')
    return record
