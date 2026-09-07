#!/usr/bin/env python3
"""Read-only build inventory: component presence is never a runtime pass."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from prepare_rgsp_wifi_deployment import sha


PARTITIONS = ("system", "vendor", "product", "system/product", "system_ext", "system/system_ext")


def package_paths(product, name):
    aliases = {"Launcher3": ("Launcher3", "Launcher3QuickStep"),
               "WebView": ("WebView", "webview")}
    paths = set()
    for partition in PARTITIONS:
        for directory in ("app", "priv-app"):
            for module in aliases.get(name, (name,)):
                paths.update(p.resolve() for p in
                             (product / partition / directory / module).glob("*.apk"))
    return sorted(paths)


def audit(product):
    manifest = product / "vendor/etc/vintf/manifest.xml"
    hals = sorted({hal.findtext("name") for hal in ET.parse(manifest).getroot().findall("hal")})
    features = set()
    for partition in PARTITIONS:
        for path in (product / partition / "etc/permissions").glob("*.xml"):
            for node in ET.parse(path).getroot().findall("feature"):
                features.add(node.attrib["name"])
    policy = product / "vendor/etc/audio_policy_configuration.xml"
    audio = ET.parse(policy).getroot()
    includes = [n.attrib["href"] for n in audio.iter("{http://www.w3.org/2001/XInclude}include")]
    devices = sorted(n.attrib.get("tagName", "") for n in audio.iter("devicePort"))
    mixer = product / "vendor/etc/audio_mixer_paths.xml"
    controls = sorted({n.attrib["name"] for n in ET.parse(mixer).getroot().iter("ctl")})
    packages = {}
    for name in ("DocumentsUI", "PackageInstaller", "PermissionController", "Settings",
                 "LeanbackIME", "LatinIME", "Launcher3", "WebView"):
        paths = package_paths(product, name)
        packages[name] = [{"path": str(p.relative_to(product)), "sha256": sha(p)} for p in paths]
    vendor_hw = product / "vendor/lib/hw"
    report = {
        "device_writes": False, "runtime_verified": False,
        "manifest": {"path": str(manifest), "sha256": sha(manifest), "hals": hals},
        "features": sorted(features), "packages": packages,
        "audio": {"policy_sha256": sha(policy), "mixer_sha256": sha(mixer),
                  "device_ports": devices, "mixer_controls": controls,
                  "missing_includes": [name for name in includes if not (policy.parent / name).is_file()],
                  "qualification": "Donor routes; RGSP playback, volume and headphones not verified"},
        "unavailable_hidl_providers": [
            name for name in ("android.hardware.bluetooth", "android.hardware.light",
                              "android.hardware.power", "android.hardware.vibrator")
            if name not in hals],
        "legacy_hal_files": sorted(p.name for p in vendor_hw.glob("*.so")),
        "gates": [
            "Wi-Fi: authentication, DHCP, DNS, HTTPS and saved-network recovery",
            "Storage: blank-data boot, emulated storage and TF2 ROM partition exposure",
            "APK UI: DocumentsUI -> PackageInstaller -> permission confirmation -> AT4K",
            "Audio: card/device and mixer matching before changing donor control values",
            "Health: compare AXP2202 sysfs values with framework battery/charging reports",
            "Lights/power: panel brightness and safe suspend/resume need a real RGSP backend",
            "Bluetooth: UART, rfkill, firmware loading, HAL and pairing remain unqualified",
        ],
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite an existing report")
    report = audit(args.product.resolve(strict=True))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"SERVICE_AUDIT={args.output}")
    print("RUNTIME_VERIFIED=false")
    print("MISSING_AUDIO_INCLUDES=" + str(len(report["audio"]["missing_includes"])))
    print("UNAVAILABLE_HIDL=" + ",".join(report["unavailable_hidl_providers"]))


if __name__ == "__main__":
    main()
