#!/usr/bin/env python3
"""Apply the verified Fix67 deployment repairs to local preflight image copies.

This is a bring-up package, not a clean-data or standalone-TF2 qualification.
Only regular image files below the workspace out directory may be mounted.
"""

import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def update_rc(path, transform):
    original = path.read_text()
    updated = transform(original)
    path.write_text(updated)


def install(source, target, mode=0o644):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    os.chmod(target, mode)
    os.chown(target, 0, 0)


def props(path, values):
    lines = path.read_text().splitlines()
    lines = [line for line in lines if line.split("=", 1)[0] not in values]
    path.write_text("\n".join(lines + [f"{k}={v}" for k, v in values.items()]) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / "out") or output == root / "out":
        raise ValueError("Output must be a new directory inside workspace out")
    if output.exists():
        raise ValueError("Refusing to overwrite an existing deployment package")
    preflight = root / "out/h700-android10-preflight"
    payload = root / "out/h700-android10-b2"
    source_manifest = json.loads((preflight / "DEPLOYMENT_MANIFEST.json").read_text(encoding="utf-8-sig"))
    for name in ("system.raw.img", "vendor.raw.img"):
        entry = source_manifest["artifacts"][name]
        if (preflight / name).stat().st_size != entry["bytes"] or sha(preflight / name) != entry["sha256"]:
            raise ValueError(f"Preflight hash mismatch: {name}")
    for line in (root / "docs/baselines/fix67-payload.sha256").read_text().splitlines():
        expected, name = line.split()
        if sha(payload / name) != expected:
            raise ValueError(f"Fix67 payload hash mismatch: {name}")
    output.mkdir()
    for name in ("system.raw.img", "vendor.raw.img"):
        run("cp", "--sparse=always", "--", str(preflight / name), str(output / name))
    checks = []
    for name in ("system.raw.img", "vendor.raw.img"):
        run("e2fsck", "-fn", str(output / name))
    with tempfile.TemporaryDirectory(prefix="rgsp-wifi-images-") as temp:
        s, v = Path(temp) / "system", Path(temp) / "vendor"
        s.mkdir()
        v.mkdir()
        mounted = []
        try:
            for image, mountpoint in (("system.raw.img", s), ("vendor.raw.img", v)):
                run("mount", "-t", "ext4", "-o", "loop,rw", str(output / image), str(mountpoint))
                mounted.append(mountpoint)
            for name in ("servicemanager.rc", "hwservicemanager.rc"):
                update_rc(s / "system/etc/init" / name, lambda text:
                          re.sub(r"(?m)^[ \t]*console[ \t]*\n", "", text))
            sf = s / "system/etc/init/surfaceflinger.rc"
            def fix_sf(text):
                text = re.sub(r"(?m)^service surfaceflinger .*$",
                              "service surfaceflinger /system/bin/surfaceflinger", text)
                text = re.sub(r"(?m)^[ \t]*(?:console|capabilities SYS_NICE|seclabel u:r:surfaceflinger:s0)[ \t]*\n", "", text)
                text = re.sub(r"(?m)^[ \t]*setenv LD_PRELOAD .*librgsp_mali_ioctl_trace\.so[ \t]*\n", "", text)
                return text.replace("service surfaceflinger /system/bin/surfaceflinger\n",
                                    "service surfaceflinger /system/bin/surfaceflinger\n    capabilities SYS_NICE\n")
            update_rc(sf, fix_sf)
            props(s / "system/build.prop", {
                "ro.product.platform": "tablet", "debug.hwui.renderer": "opengl",
                "debug.hwui.use_buffer_age": "false", "debug.hwui.use_partial_updates": "false",
                "persist.display.policy": "single",
                "persist.disp.device_config": "/vendor/etc/dispconfigs/h700-rgsp-lcd.json",
            })
            update_rc(s / "init.rc", lambda text:
                      re.sub(r"(?m)^[ \t]*start console[ \t]*\n", "", text))
            update_rc(s / "system/etc/init/displayservice.rc", lambda text:
                      re.sub(r"(?m)^[ \t]*start displayservice[ \t]*\n", "", text))
            install(payload / "rgsp_fix63_graphics.rc", s / "system/etc/init/rgsp_fix63_graphics.rc")
            install(payload / "rgsp-graphics-diag.sh", s / "system/etc/rgsp-graphics-diag.sh", 0o755)
            install(payload / "rgsp-logcat-bounded.sh", s / "system/bin/rgsp-fix47-logcat.sh", 0o755)
            (s / "system/etc/init/rgsp_fix47_logcat.rc").write_text(
                "service rgsp_fix47_logcat /system/bin/sh /system/bin/rgsp-fix47-logcat.sh\n"
                "    class core\n    user root\n    group root log\n    seclabel u:r:init:s0\n")
            feature = s / "system/etc/permissions/android.software.app_widgets.xml"
            feature.write_text('<permissions><feature name="android.software.app_widgets" /></permissions>\n')
            for source, target, expected in (
                ("mali_kbase.h700.r20p0.ko.xz", s / "system/lib/modules/mali_kbase.ko",
                 "987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9"),
                ("libGLES_mali.arm32.r20p0.so.xz", v / "lib/egl/libGLES_mali.so",
                 "05dc81f866b7ab947d20f283f25dcd96ca2f56ffd48e637b68778c1a994a6925"),
            ):
                target.parent.mkdir(parents=True, exist_ok=True)
                with lzma.open(payload / source, "rb") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.chmod(target, 0o644)
                if sha(target) != expected:
                    raise ValueError(f"Expanded payload mismatch: {source}")
            install(payload / "hwcomposer.cupid.fix64.so", v / "lib/hw/hwcomposer.cupid.so")
            install(payload / "libdisplayconfig.fix63.so", v / "lib/libdisplayconfig.so")
            display = {"DisplayEngineVersion": 2, "DisplayNumber": 2}
            for index, interface in enumerate(("LCD", "HDMI")):
                display[f"Display{index}"] = {
                    "InterfaceType": interface, "DisplayEnginePortId": index,
                    "OverrideFramebufferSize": 1, "FramebufferWidth": 720,
                    "FramebufferHeight": 480, "DpiX": 160, "DpiY": 160,
                    "HotplugSupported": index, "AfbcSupported": 0,
                    "HardwareRotateSupported": 0, "BandwidthLimited": 338800,
                    "DefaultOutputMode": 0,
                }
            disp_dir = v / "etc/dispconfigs"
            disp_dir.mkdir(parents=True, exist_ok=True)
            (disp_dir / "config.json").write_text(json.dumps({"DeviceConfig": "h700-rgsp-lcd.json"}, indent=2) + "\n")
            (disp_dir / "h700-rgsp-lcd.json").write_text(json.dumps(display, indent=2) + "\n")
            props(v / "build.prop", {"persist.vendor.hwc.software_vsync": "true"})
            wifi_rc = (v / "etc/init/init.rgsp.rc").read_text()
            if "insmod /vendor/modules/8821cs.ko" not in wifi_rc:
                raise ValueError("Wi-Fi module loading missing")
            check_paths = [
                (s, "system/lib/modules/mali_kbase.ko"),
                (s, "system/etc/init/rgsp_fix63_graphics.rc"),
                (s, "system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl"),
                (v, "lib/egl/libGLES_mali.so"), (v, "lib/hw/hwcomposer.cupid.so"),
                (v, "modules/8821cs.ko"), (v, "firmware/rtlbt/rtl8821c_config"),
                (v, "firmware/rtlbt/rtl8821c_fw"), (v, "etc/init/init.rgsp.rc"),
            ]
            for mountpoint, rel in check_paths:
                checks.append({"partition": mountpoint.name, "path": rel, "sha256": sha(mountpoint / rel)})
            if "setprop vold.decrypt trigger_restart_framework" not in (s / "system/etc/init/rgsp_fix63_graphics.rc").read_text():
                raise ValueError("Framework trigger missing")
            for rel in ("dev", "proc", "sys", "apex", "vendor", "data", "rgsp-persist"):
                if not (s / rel).is_dir():
                    raise ValueError(f"Handoff mount point missing: {rel}")
        finally:
            for mountpoint in reversed(mounted):
                run("umount", str(mountpoint))
    for name in ("system.raw.img", "vendor.raw.img"):
        result = subprocess.run(["e2fsck", "-fn", str(output / name)], capture_output=True, text=True)
        (output / f"{name}.fsck.txt").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise ValueError(f"Final ext4 check failed: {name}")
    shutil.copyfile(preflight / "AT4K-launcher.apk", output / "AT4K-launcher.apk")
    shutil.copyfile(payload / "ramdisk-a10-handoff-fix67.gz", output / "ramdisk-a10-handoff-fix67.gz")
    (output / "CONTENT_CHECKS.json").write_text(json.dumps(checks, indent=2) + "\n")
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "baseline": "fresh preflight plus verified Fix67 offline deployment repairs",
        "writes_performed": False,
        "boot_requirement": "Existing protected Fix67 handoff; TF1 boot is NOT written by this package",
        "data_requirement": "Preserve existing RGSP Android data; blank-data boot not qualified",
        "artifacts": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)}
                      for p in sorted(output.iterdir()) if p.is_file()},
        "parent_artifacts": source_manifest["artifacts"],
    }
    (output / "DEPLOYMENT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"DEPLOYMENT_READY={output}", flush=True)


if __name__ == "__main__":
    main()
