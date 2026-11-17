"""Compile a scoped ViewRoot source repair against retained real Android classes.

This is an isolated compile/link check. It does not replace framework.jar or
regenerate ART boot images, sign/install anything, or write the retained BSP.
Run only through tools/public_build/run-limited.sh.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys
import zipfile

from apply_joystick_guard import make_candidate, SOURCE_SHA256
from apply_dpad_guard import transform

REPO = Path(__file__).resolve().parents[2]
NATIVE = Path('/home/lpf/h700-android10/android')
OUT = Path('/home/lpf/roc-os-user-20261104/out/soong/.intermediates')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'framework_jar_built': False, 'ART_boot_images_built': False,
              'device_accessed': False, 'retained_sources_modified': False,
              'scope': 'full real ViewRoot source compile with retained Android classes', 'commands': []}
    try:
        original = NATIVE / 'frameworks/base/core/java/android/view/ViewRootImpl.java'
        before = original.read_bytes()
        assert digest(before) == SOURCE_SHA256
        joystick, manifest = make_candidate(before)
        snippet = Path(__file__).with_name('RocDpadKeyGuard.java.inc')
        combined = transform(joystick.decode('utf-8'), snippet.read_text(encoding='utf-8')).encode('utf-8')
        candidate = args.work / 'source/android/view/ViewRootImpl.java'
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(combined)
        patch = ''.join(difflib.unified_diff(before.decode().splitlines(True), combined.decode().splitlines(True),
            fromfile='a/frameworks/base/core/java/android/view/ViewRootImpl.java',
            tofile='b/frameworks/base/core/java/android/view/ViewRootImpl.java'))
        (args.work/'ViewRootImpl.patch').write_text(patch, encoding='utf-8')
        javac = NATIVE / 'prebuilts/jdk/jdk9/linux-x86/bin/javac'
        core = OUT / 'libcore/core-all/android_common/turbine-combined/core-all.jar'
        framework = OUT / 'frameworks/base/framework/android_common/combined/framework.jar'
        framework_jarjar = OUT / 'frameworks/base/framework/android_common/jarjar/framework.jar'
        inputs = [original, javac, core, framework, framework_jarjar, snippet,
                  Path(__file__), Path(__file__).with_name('apply_joystick_guard.py'),
                  Path(__file__).with_name('apply_dpad_guard.py'), Path(__file__).with_name('RocJoystickGuard.java.inc')]
        pins = {str(path): {'bytes': path.stat().st_size, 'sha256': sha(path)} for path in inputs}
        report.update({'input_sha256': pins, 'joystick_manifest': manifest,
                       'candidate_source_sha256': digest(combined), 'candidate_source': str(candidate),
                       'patch_sha256': sha(args.work/'ViewRootImpl.patch')})
        (args.work/'input-lock.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        classes = args.work/'classes'
        classes.mkdir()
        argv = [str(javac), '-J-Xmx2048m', '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                '-proc:none', '-g', '-bootclasspath', str(core), '-classpath', str(framework)+':'+str(framework_jarjar),
                '-d', str(classes), str(candidate)]
        run = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        (args.work/'compile.log').write_text(run.stdout, encoding='utf-8')
        report['commands'].append({'argv': argv, 'returncode': run.returncode, 'output': run.stdout})
        if run.returncode: raise RuntimeError('Real Android classpath compile failed; see compile.log')
        outputs = {path.relative_to(classes).as_posix(): sha(path) for path in sorted(classes.rglob('*.class'))}
        for required in ('ViewRootImpl.class', 'ViewRootImpl$RocJoystickGuard.class', 'ViewRootImpl$RocDpadKeyGuard.class'):
            assert 'android/view/'+required in outputs, required
        archive = args.work/'ViewRootImpl-compile-check.jar'
        with zipfile.ZipFile(archive, 'x') as z:
            for name in outputs: z.write(classes/name, name)
        assert before == original.read_bytes()
        assert all(sha(Path(name)) == item['sha256'] for name,item in pins.items())
        report.update({'passed': True, 'class_files': outputs, 'class_file_count': len(outputs),
                       'compile_check_jar_sha256': sha(archive), 'all_inputs_unchanged': True})
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (args.work/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'classes': report['class_file_count'], 'result': str(args.work/'result.json')}))


if __name__ == '__main__':
    main()
