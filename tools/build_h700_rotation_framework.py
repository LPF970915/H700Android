"""Reassemble the exact delivered services DEX; no full AOSP graph regeneration."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time
import zipfile

REPO = Path(__file__).resolve().parents[1]
BASE_SHA = '7015b60d93e1b516378cf91b691cc628305ba37ec7cc872013babf5e8159bff5'
APKTOOL_SHA = '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4'

def main():
    cg = Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split('::')[-1].lstrip('/')
    quota, period = (cg / 'cpu.max').read_text().split()
    assert quota != 'max' and int(quota) <= int(period)
    assert int((cg / 'memory.max').read_text()) <= 6442450944
    assert os.sched_getaffinity(0) <= {0, 1} and os.getpriority(os.PRIO_PROCESS, 0) == 19
    native = Path('/home/lpf/h700-android10/android')
    out = REPO / 'out/force-landscape-20261029'
    base = out / 'services.before.jar'
    apktool = Path('/home/lpf/h700-at4k-20261028/apktool-2.9.3.jar')
    assert hashlib.sha256(base.read_bytes()).hexdigest() == BASE_SHA
    assert hashlib.sha256(apktool.read_bytes()).hexdigest() == APKTOOL_SHA
    work = Path('/home/lpf/h700-rotation-20261029') / ('framework-' + time.strftime('%Y%m%d-%H%M%S'))
    work.mkdir(parents=True)
    jdk = native / 'prebuilts/jdk/jdk9/linux-x86/bin'
    def run(*args):
        print('RUN', *map(str, args[:4]), flush=True)
        subprocess.run(list(map(str, args)), check=True)
    run(jdk / 'javac', '-J-Xmx512m', '-cp', apktool, '-d', work, REPO / 'tools/rotation/FrameworkDexTool.java')
    java = ['taskset', '-c', '0', jdk / 'java', '-Xmx2g', '-cp', str(work) + ':' + str(apktool), 'FrameworkDexTool']
    found = subprocess.check_output(list(map(str, java + ['find', base, 'Lcom/android/server/wm/ActivityRecord;'])), text=True)
    entries = [s.split('=', 1)[1] for s in found.splitlines() if s.startswith('CLASS_ENTRY=')]
    assert len(entries) == 1, entries
    dex_entry = entries[0]
    run(*java, 'disassemble', base, dex_entry, work / 'original')
    spec = importlib.util.spec_from_file_location('rotation_patch', REPO / 'tools/rotation/patch_framework.py')
    patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)
    target = Path('com/android/server/wm/ActivityRecord.smali')
    original = (work / 'original' / target).read_text()
    original_methods = patcher.methods(original)
    patched = patcher.patch(original)
    shutil.copytree(work / 'original', work / 'modified')
    (work / 'modified' / target).write_text(patched)
    run(*java, 'assemble', work / 'modified', work / 'classes.dex')
    candidate = out / 'services.force-landscape.jar'
    with zipfile.ZipFile(base) as incoming, zipfile.ZipFile(candidate, 'w') as result:
        for info in incoming.infolist():
            result.writestr(info, (work / 'classes.dex').read_bytes() if info.filename == dex_entry else incoming.read(info.filename))
    run(*java, 'disassemble', candidate, dex_entry, work / 'verify')
    compared = 0
    for before in (work / 'original').rglob('*.smali'):
        relative = before.relative_to(work / 'original')
        after = work / 'verify' / relative
        assert after.is_file(), relative
        if relative == target:
            rebuilt = patcher.methods(after.read_text())
            assert set(rebuilt) == set(original_methods) | {'h700ForceLandscape()Z'}
            for name, body in original_methods.items():
                if name not in patcher.INJECTIONS:
                    assert patcher.canonical(body) == patcher.canonical(rebuilt[name]), name
            for name in patcher.INJECTIONS:
                assert '->h700ForceLandscape()Z' in rebuilt[name]
        else:
            assert patcher.canonical(before.read_text()) == patcher.canonical(after.read_text()), relative
        compared += 1
    with zipfile.ZipFile(base) as a, zipfile.ZipFile(candidate) as b:
        assert a.namelist() == b.namelist()
        for name in a.namelist():
            if name != dex_entry: assert a.read(name) == b.read(name), name
    receipt = {'base_sha256': BASE_SHA, 'sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'bytes': candidate.stat().st_size, 'classes_compared': compared, 'dex_entry': dex_entry, 'changed_class': str(target),
        'changed_existing_methods': list(patcher.INJECTIONS), 'added_method': 'h700ForceLandscape()Z',
        'other_dex_and_zip_entries_unchanged': True, 'work': str(work)}
    (out / 'framework-build.private.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('FRAMEWORK_VERIFIED', json.dumps(receipt), flush=True)

if __name__ == '__main__': main()
