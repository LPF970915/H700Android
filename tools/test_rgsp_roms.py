#!/usr/bin/env python3
"""ROMS boot ownership, patch ordering, and host-executed policy tests."""
import fnmatch
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_rgsp_compact_image import ROOT, prepare_init


class RomsTests(unittest.TestCase):
    def baseline(self):
        return """#!/bin/sh
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
ROMS_DEV=/dev/block/mmcblk0p8
mount -t vfat -o rw "$ROMS_DEV" /single-card-roms ||
    fail "unable to mount ROMS"
mount -t ext4 -o ro "$SYSTEM_DEV" /android-root ||
    fail "unable to mount system"
mount -o move /single-card-roms /android-root/rgsp-persist ||
    fail "unable to move persistent ROMS storage"
echo '[rgsp-single-card] Android root ready; switching root' >> "$LOG"
"""

    def test_vold_boot_preserves_all_android_mounts(self):
        text = prepare_init(self.baseline(), True)
        hook = '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"'
        self.assertEqual(text.count(hook), 1)
        self.assertLess(text.index(hook), text.index("mount -t ext4"))
        for dev in ("SYSTEM_DEV", "VENDOR_DEV", "DATA_DEV"):
            self.assertIn(f'"${dev}"', text)
        self.assertNotIn("mount -t vfat", text)
        self.assertNotIn("mount -o move /single-card-roms", text)
        self.assertGreater(text.index('touch "$LOG"'),
                           text.index('fail "unable to mount Android data"'))
        self.assertIn('exec </dev/ttyS0 >/dev/ttyS0 2>&1', text)
        subprocess.run(["sh", "-n"], input=text, text=True, check=True)

    def test_legacy_boot_still_supported(self):
        old = self.baseline()
        # Actual v5d has this hook; the source-only template predates injection.
        old = old.replace('mount -t vfat',
                          '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"\n'
                          'mount -t vfat', 1)
        text = prepare_init(old)
        self.assertIn("mount -t vfat", text)
        self.assertIn("mount -o move /single-card-roms", text)

    def test_duplicate_hook_refused(self):
        hook = '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"\n'
        with self.assertRaises(ValueError):
            prepare_init(hook * 2 + self.baseline(), True)

    def test_fstab_matches_only_boot_disk(self):
        fstab = (ROOT/"android/h700-android10/device/roc/rgsp/fstab.sun50iw9p1").read_text()
        line, = [s for s in fstab.splitlines() if "voldmanaged=" in s]
        pattern = line.split()[0]
        disk = "/devices/platform/soc/sdc0/mmc_host/mmc0/mmc0:0001/block/mmcblk0"
        self.assertTrue(fnmatch.fnmatchcase(disk, pattern))
        self.assertFalse(fnmatch.fnmatchcase(disk+"/mmcblk0p8", pattern))
        self.assertFalse(fnmatch.fnmatchcase(disk.replace("mmcblk0", "mmcblk1"), pattern))
        self.assertNotIn("encryptable", line)
        self.assertNotIn("noemulatedsd", line)

    def test_patch_guards_precede_destructive_work(self):
        patch = (ROOT/"tools/rgsp-vold-roms.patch").read_text()
        self.assertIn("table != Table::kGpt || i != 8", patch)
        self.assertIn("minor(device) <= 8", patch)
        self.assertIn("whole-device fallback is forbidden", patch)
        self.assertIn('Trim(start) == "54960128"', patch)
        for signature, operation in [
            ("status_t Disk::partitionPublic()", "int res;"),
            ("status_t Disk::partitionMixed(int8_t ratio)", "int res;"),
            ("status_t PublicVolume::doFormat", "bool useVfat"),
            ("status_t PublicVolume::doMount()", "readMetadata();"),
        ]:
            body = patch[patch.index(signature):]
            guard = "return -EBUSY;" if "doMount" in signature else "return -EPERM;"
            self.assertLess(body.index(guard), body.index(operation))

    def test_public_visibility_does_not_enable_adoption(self):
        patch = (ROOT/"tools/rgsp-roms-visible.patch").read_text()
        self.assertIn('"rgsp".equals(SystemProperties.get("ro.product.device"))', patch)
        self.assertIn('"disk:179,0".equals(vol.disk.getId())', patch)
        self.assertIn('"public:179,8".equals(vol.id)', patch)
        self.assertIn("vol.disk.isAdoptable() || rgspRoms", patch)
        self.assertIn("VolumeInfo.MOUNT_FLAG_VISIBLE", patch)
        self.assertNotIn("FLAG_ADOPTABLE", patch)

    def test_provider_default_preserves_explicit_tuning(self):
        script = (ROOT/"android/h700-android10/device/roc/rgsp/rgsp-roms-handoff.sh").read_text()
        self.assertIn('[ "$(getprop ro.product.device)" = rgsp ]', script)
        self.assertIn('if [ "$(device_config get activity_manager max_cached_processes)" = null ]; then',
                      script)
        self.assertIn("device_config put activity_manager max_cached_processes 8", script)
        self.assertNotIn("umount -l", script)
        self.assertNotIn("umount -f", script)

    def test_live_source_policy_cpp(self):
        # Compile the exact helper bodies from the patch with host stubs.
        patch = (ROOT/"tools/rgsp-vold-roms.patch").read_text()
        additions = "\n".join(s[1:] for s in patch.splitlines()
                              if s.startswith("+") and not s.startswith("+++"))
        start = additions.index("static bool isRgspBootCard")
        end = additions.index("\n    const bool protectedBootCard", start)
        disk_helpers = additions[start:end]
        start = additions.index("static bool isRgspBootPartition")
        end = additions.index("\n    if (isRgspBootPartition", start)
        volume_helpers = additions[start:end]
        prelude = r'''
#include <cassert>
#include <string>
#include <sstream>
#include <map>
#include <sys/sysmacros.h>
#include <sys/types.h>
std::string product = "rgsp";
std::map<std::string, std::string> files;
namespace android { namespace base {
std::string GetProperty(const std::string&, const std::string&) { return product; }
bool ReadFileToString(const std::string& path, std::string* out) {
    auto it = files.find(path);
    if (it == files.end()) return false;
    *out = it->second; return true;
}
std::string Trim(std::string s) {
    auto end = s.find_last_not_of(" \n\r\t");
    return end == std::string::npos ? "" : s.substr(0, end + 1);
}
}}
using android::base::ReadFileToString;
'''
        checks = r'''
int main() {
    assert(isRgspBootCard(makedev(179, 0)));
    assert(!isRgspBootCard(makedev(179, 8)));
    assert(!isRgspBootCard(makedev(179, 16)));
    for (int i = 0; i <= 8; ++i) assert(isRgspBootPartition(makedev(179, i)));
    assert(!isRgspBootPartition(makedev(179, 16)));
    product = "other";
    assert(!isRgspBootCard(makedev(179, 0)));
    assert(!isRgspBootPartition(makedev(179, 8)));
    product = "rgsp";
    assert(!hasRgspRomsGeometry());
    files["/sys/class/block/mmcblk0p8/start"] = "54960128\n";
    files["/sys/class/block/mmcblk0p8/dev"] = "179:8\n";
    files["/sys/class/block/mmcblk0p8/uevent"] = "PARTN=8\nPARTNAME=ROMS\n";
    assert(hasRgspRomsGeometry());
    files["/sys/class/block/mmcblk0p8/start"] = "123\n";
    assert(!hasRgspRomsGeometry());
    assert(rgspRomsAlreadyMounted()); // Missing mountinfo fails closed.
    files["/proc/self/mountinfo"] = "25 1 179:7 / /data rw - ext4 /dev/mmcblk0p7 rw\n";
    assert(!rgspRomsAlreadyMounted());
    files["/proc/self/mountinfo"] += "26 1 179:8 / /rgsp-persist rw - vfat /dev/alias rw\n";
    assert(rgspRomsAlreadyMounted());
}
'''
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp)/"policy.cpp"
            src.write_text(prelude + disk_helpers + volume_helpers + checks)
            binary = Path(temp)/"policy"
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror",
                            str(src), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
