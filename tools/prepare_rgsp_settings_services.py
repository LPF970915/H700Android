#!/usr/bin/env python3
"""Publish the real RGSP settings services, preserving existing framework changes."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SERVER = 'frameworks/base/services/java/com/android/server/SystemServer.java'
OEM = 'frameworks/base/services/core/java/com/android/server/oemlock/OemLockService.java'
PATCHES = {
    SERVER: ('145862222c97519ca89c2011fa4b904a491cddbd0fa2c52549efbc97440c5be6',
             'if (hasPdb || OemLockService.isHalPresent()) {',
             'if (hasPdb || OemLockService.isHalPresent()\n'
             '                    || "rgsp".equals(android.os.Build.DEVICE)) {'),
    OEM: ('a08efffd146163450ad68cdb3370dd367f9da645db8bdb52d1da501e64035a61',
          '        } else {\n            Slog.i(TAG, "Using persistent data block based lock");',
          '        } else if ("rgsp".equals(android.os.Build.DEVICE)\n'
          '                && SystemProperties.get("ro.frp.pst").isEmpty()) {\n'
          '            Slog.i(TAG, "RGSP has no OEM unlock backend; publishing unsupported state");\n'
          '            return new RgspUnsupportedOemLock();\n'
          '        } else {\n            Slog.i(TAG, "Using persistent data block based lock");'),
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    changes = []
    for rel, (before, old, new) in PATCHES.items():
        path = args.source / rel
        data = path.read_bytes()
        text = data.decode()
        if new in text:
            if sha(text.replace(new, old, 1).encode()) != before:
                raise SystemExit('Unrecognized framework edits: ' + rel)
        elif sha(data) != before or text.count(old) != 1:
            raise SystemExit('Unrecognized framework source: ' + rel)
        else:
            changes.append((path, text.replace(old, new, 1).encode()))
    device = Path('device/roc/rgsp')
    for name in ['h700_rgsp.mk', 'configs/android.hardware.usb.host.xml', 'rgsp-wifi-adb-session.sh']:
        local = ROOT/'android/h700-android10'/device/name
        target = args.source/device/name
        data = local.read_bytes().replace(b'\r\n', b'\n')
        if target.exists() and target.read_bytes() != data:
            result = subprocess.run(['git', '-C', str(ROOT), 'show',
                        f'HEAD:android/h700-android10/{device.as_posix()}/{name}'],capture_output=True)
            baseline = result.stdout.replace(b'\r\n', b'\n') if result.returncode==0 else None
            previous=data.replace(b'\n# Explicit guarded Wi-Fi debugging, started from UART only.\nPRODUCT_COPY_FILES += \\\n    device/roc/rgsp/rgsp-wifi-adb-session.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-wifi-adb-session.sh\n', b'')
            if target.read_bytes().replace(b'\r\n', b'\n') not in (baseline,previous):
                raise SystemExit('Unrecognized device edits: ' + name)
        changes.append((target, data))
    source = ROOT/'android/h700-android10'/device/'framework/RgspUnsupportedOemLock.java'
    target = args.source/'frameworks/base/services/core/java/com/android/server/oemlock/RgspUnsupportedOemLock.java'
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise SystemExit('Unrecognized OEM backend edits')
    changes.append((target, source.read_bytes()))
    for path, data in changes:
        if path.exists() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(sha(data), path)

if __name__ == '__main__':
    main()
