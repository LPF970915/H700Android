#!/usr/bin/env python3
"""Guarded Windows/USB controller for the fixed data-side window prototype.

Read-only plan by default. --execute deploys once, runs bounded GPU work and
saves private evidence. Never writes system/vendor or starts an ARM64 Zygote.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time

repo = Path(__file__).resolve().parents[1]
out = repo / 'out/dualabi-prototype-20261030'
delivery_out = out
bundle = out / 'window-bundle'
base = '/data/local/tmp/h700-dualabi-prototype-20261030'
parser = argparse.ArgumentParser()
parser.add_argument('--execute', action='store_true')
parser.add_argument('--reuse-for-capture', action='store_true',
                    help='Repeat only a previously successful render with the verified file capture path')
args = parser.parse_args()
if not args.execute:
    print('Plan: verify saved USB identity/profile and bundle; deploy to ' + base +
          '; guarded private mount namespace; 30s window; screenshot and invariants.')
    raise SystemExit(0)
if os.name != 'nt': raise RuntimeError('Use the guarded Windows USB transport')
if args.reuse_for_capture:
    previous = json.loads((out / 'window-run.private.json').read_text())
    if previous['rc'] or not all(s in previous['stdout'] for s in ['WINDOW_SWAP_OK','WINDOW_CLEANUP_OK']):
        raise RuntimeError('Previous render was not successful; do not repeat blindly')
    if json.loads((out / 'window-before.private.json').read_text()) != json.loads((out / 'window-after.private.json').read_text()):
        raise RuntimeError('Previous baseline changed')
    from PIL import Image
    with Image.open(out / 'desktop-control.private.png') as control:
        control.verify()
    out = out / 'window-file-capture'
    out.mkdir()  # Preserve the first attempt and refuse repeated overwrites.
adb = str(Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/platform-tools/adb.exe')
serial = json.loads((repo / 'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text())['serial']
if subprocess.check_output([adb, '-d', 'get-serialno'], timeout=10).decode().strip() != serial:
    raise RuntimeError('USB device mismatch')
def shell(command, timeout=20):
    p = subprocess.run([adb, '-s', serial, 'shell', command], capture_output=True, timeout=timeout)
    return {'rc': p.returncode, 'stdout': p.stdout.decode('utf-8','replace').replace('\r',''),
            'stderr': p.stderr.decode('utf-8','replace').replace('\r','')}
for command, expected in [('getprop ro.serialno', serial), ('getprop ro.product.device', 'rgsp'),
        ('getprop persist.vendor.rgsp.input_profile', 'rg34xxsp'), ('id -u', '0')]:
    result = shell(command)
    if result['rc'] or result['stdout'].strip() != expected: raise RuntimeError('Device guard failed')
power = shell('dumpsys power')
if power['rc'] or 'mWakefulness=Awake' not in power['stdout'] or 'Display Power: state=ON' not in power['stdout']:
    raise RuntimeError('Device must be awake with its lid open for window acceptance')
lock = json.loads((bundle / 'bundle-lock.json').read_text())
for name, digest in lock['payload_sha256'].items():
    file = bundle / name
    if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Bundle hash mismatch: ' + name)
invariant = ('cat /proc/sys/kernel/random/boot_id; pidof surfaceflinger system_server; '
    'sha256sum /system/framework/services.jar /system/app/RGSPNavigation/RGSPNavigation.apk '
    '/vendor/lib/egl/libGLES_mali.so; cat /proc/mounts')
before = shell(invariant)
if before['rc']: raise RuntimeError('Cannot capture baseline')
record = out / 'window-before.private.json'
if record.exists(): raise RuntimeError('A window attempt already exists; preserve and inspect it')
record.write_text(json.dumps(before, indent=2))
if args.reuse_for_capture:
    result = shell('cd ' + base + ' && sha256sum ' + ' '.join(shlex.quote(n) for n in lock['payload_sha256']), timeout=30)
    actual = dict((line.split(None,1)[1], line.split(None,1)[0]) for line in result['stdout'].splitlines())
    if result['rc'] or actual != lock['payload_sha256']: raise RuntimeError('Remote payload changed')
else:
    if shell('test ! -e ' + base)['rc']: raise RuntimeError('Remote stage exists; do not overwrite')
    if shell('mkdir ' + base)['rc']: raise RuntimeError('Remote mkdir failed')
    for name in ['rootfs', 'mount64', 'namespace-run.sh']:
        p = subprocess.run([adb, '-s', serial, 'push', str(bundle / name), base + '/'], capture_output=True, timeout=180)
        (out / ('push-' + name + '.private.txt')).write_bytes(p.stdout + p.stderr)
        if p.returncode: raise RuntimeError('Deployment failed')
if shell('chmod 0755 ' + base + '/mount64 ' + base + '/rootfs/system/bin/linker64 ' +
         base + '/rootfs/system/bin/h700_window_probe64')['rc']:
    raise RuntimeError('Remote executable permissions failed')
namespace = shell('readlink /proc/self/ns/mnt')['stdout'].strip()
if not re.fullmatch(r'mnt:\[\d+\]', namespace): raise RuntimeError('Invalid namespace')
namespace_arg = shlex.quote(namespace)
guards = [shell(base + '/mount64 ' + namespace_arg)]
for extra in [' /proc /system/forbidden', ' /proc ' + base + '/rootfs/../escape',
              ' /dev/block/mmcblk0 ' + base + '/rootfs/proc']:
    guards.append(shell('unshare -m ' + base + '/mount64 ' + namespace_arg + extra))
(out / 'window-mount-guards.private.json').write_text(json.dumps(guards, indent=2))
if [r['rc'] for r in guards] != [4,5,6,7]: raise RuntimeError('Mount guards failed')
print('USB_AND_MOUNT_GUARDS_PASS', flush=True)
command = 'timeout -s KILL 45 unshare -m sh ' + base + '/namespace-run.sh ' + namespace_arg
process = subprocess.Popen([adb, '-s', serial, 'shell', command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
ready = threading.Event()
output = []
def observe():
    for line in iter(process.stdout.readline, b''):
        output.append(line)
        if b'WINDOW_SWAP_OK' in line: ready.set()
reader = threading.Thread(target=observe, daemon=True)
reader.start()
try:
    # Wait for the actual first swap, rather than racing the cold loader.
    displayed = ready.wait(timeout=35)
    print('WINDOW_READY_FOR_OBSERVATION' if displayed else 'WINDOW_NOT_READY', flush=True)
    layers = shell('dumpsys SurfaceFlinger --list', timeout=5)
    (out / 'window-layers.private.json').write_text(json.dumps(layers, indent=2))
    remote_shot = base + '/window-file-capture.png'
    capture = shell('screencap -p ' + remote_shot, timeout=15)
    (out / 'capture.private.json').write_text(json.dumps(capture, indent=2))
    shot_file = out / 'window.private.png'
    pull = subprocess.run([adb, '-s', serial, 'pull', remote_shot, str(shot_file)], capture_output=True, timeout=20)
    shot_bytes = shot_file.read_bytes() if capture['rc'] == 0 and pull.returncode == 0 else b''
    process.wait(timeout=50)
    reader.join(timeout=5)
    if reader.is_alive(): raise RuntimeError('Evidence reader did not finish')
    run = {'rc': process.returncode, 'stdout': b''.join(output).decode('utf-8','replace'),
           'stderr': '(merged into stdout)'}
    (out / 'window-run.private.json').write_text(json.dumps(run, indent=2))
finally:
    if process.poll() is None:
        process.kill(); process.wait(timeout=10); reader.join(timeout=5)
    after = shell(invariant)
    (out / 'window-after.private.json').write_text(json.dumps(after, indent=2))
if after != before: raise RuntimeError('Baseline changed; stop and inspect')
text = run['stdout']
if run['rc'] or not all(s in text for s in ['WINDOW_PROBE_BITS=64', 'WINDOW_SWAP_OK', 'WINDOW_CLEANUP_OK']):
    raise RuntimeError('Window probe did not pass; inspect private evidence')
if layers['rc'] or 'H700-DualABI-WindowProbe' not in layers['stdout']:
    raise RuntimeError('Window layer not observed')
remaining = shell('dumpsys SurfaceFlinger --list')
for _ in range(10):
    if remaining['rc'] or 'H700-DualABI-WindowProbe' not in remaining['stdout']: break
    time.sleep(0.2)  # Observation only: allow asynchronous Binder/layer teardown.
    remaining = shell('dumpsys SurfaceFlinger --list')
if remaining['rc'] or 'H700-DualABI-WindowProbe' in remaining['stdout']:
    raise RuntimeError('Window layer cleanup not confirmed')
from PIL import Image
image = Image.open(io.BytesIO(shot_bytes)).convert('RGB')
samples = [image.getpixel((x,y)) for x,y in [(64,64),(128,96),(240,160)]]
if not all(r < 20 and g > 235 and b < 20 for r,g,b in samples):
    raise RuntimeError('Swap passed but screenshot does not confirm visible green window')
(delivery_out / 'window.pass.json').write_text(json.dumps({
    'elf_bits': 64, 'swap': True, 'composed_green_window': True,
    'layer_removed': True, 'baseline_unchanged': True, 'physical_observation': 'pending',
    'bundle_lock_sha256': hashlib.sha256((bundle / 'bundle-lock.json').read_bytes()).hexdigest(),
    'evidence_subdir': out.relative_to(delivery_out).as_posix(),
}, indent=2) + '\n')
print('ELF64_WINDOW_SWAP_SCREENSHOT_AND_BASELINE_PASS')
