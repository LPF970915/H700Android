"""Build the navigation/AT4K adaptation inside the existing low-pressure scope."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

REPO = Path(__file__).resolve().parents[1]

def run(*args, **kwargs):
    print('RUN', Path(str(args[0])).name, *[str(x) for x in args[1:3]], flush=True)
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)

def jar_classes(classes, jar):
    with zipfile.ZipFile(jar, 'w') as output:
        for path in sorted(classes.rglob('*.class')):
            output.write(path, path.relative_to(classes).as_posix())

def prepared_zip(source, output, additions):
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(output, 'w') as target:
        for info in incoming.infolist():
            if info.filename.startswith('META-INF/') or info.filename in additions:
                continue
            if info.filename.endswith('.dex') or (info.filename.startswith('lib/') and info.filename.endswith('.so')):
                info.compress_type = zipfile.ZIP_STORED
            target.writestr(info, incoming.read(info.filename))
        for name, path in additions.items():
            target.write(path, name, compress_type=zipfile.ZIP_STORED)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--input-only', action='store_true')
    parser.add_argument('--navigation-only', action='store_true')
    args = parser.parse_args()
    cg = Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split('::')[-1].lstrip('/')
    assert int((cg / 'memory.max').read_text()) <= 6442450944
    quota, period = (cg / 'cpu.max').read_text().split()
    assert quota != 'max' and int(quota) <= int(period)
    assert os.sched_getaffinity(0) <= {0, 1} and os.getpriority(os.PRIO_PROCESS, 0) == 19
    native = args.source.resolve(strict=True)
    sdk = native / 'prebuilts/sdk/tools/linux'
    jdk = native / 'prebuilts/jdk/jdk9/linux-x86'
    android = native / 'prebuilts/sdk/29/public/android.jar'
    work = Path('/home/lpf/h700-at4k-20261028')
    work.mkdir(exist_ok=True)
    delivery = REPO / 'out/rg34xxsp-dev-20261028'
    os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')
    java, javac = jdk / 'bin/java', jdk / 'bin/javac'
    key = native / 'build/make/target/product/security/platform.pk8'
    cert = key.with_name('platform.x509.pem')
    def compile_java(sources, stem):
        classes = work / (stem + '-classes')
        classes.mkdir(exist_ok=True)
        bootclasspath = str(android) + ':' + str(sdk / 'bin/core-lambda-stubs.jar')
        run(javac, '-J-Xmx1g', '-source', '8', '-target', '8', '-bootclasspath', bootclasspath,
            '-g:none', '-d', classes, *sources)
        jar = work / (stem + '.jar')
        jar_classes(classes, jar)
        dex = work / (stem + '-dex')
        dex.mkdir(exist_ok=True)
        run(java, '-Xmx2g', '-cp', sdk / 'lib/d8.jar', 'com.android.tools.r8.D8',
            '--min-api', '29', '--lib', android, '--output', dex, jar)
        return dex / 'classes.dex'
    def sign(source, stem):
        aligned = work / (stem + '-aligned.apk')
        run(sdk / 'bin/zipalign', '-f', '-p', '4', source, aligned)
        target = delivery / (stem + '.apk')
        run(java, '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'sign', '--key', key,
            '--cert', cert, '--min-sdk-version', '29', '--out', target, aligned)
        run(java, '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--verbose',
            '--print-certs', '--max-sdk-version', '29', target)
        return target
    if args.input_only:
        run('arm-linux-gnueabihf-gcc', '-std=c11', '-D_DEFAULT_SOURCE', '-O2', '-static',
            '-Wall', '-Wextra', '-Werror', REPO / 'android/h700-android10/device/roc/rgsp/input/h700_sticks.c',
            '-o', delivery / 'h700-sticks')
        for stem, source in [('nav-probe', 'tools/settings_nav_probe/Dump.java'),
                             ('stick-motion', 'tools/input_probe/StickMotion.java')]:
            dex = compile_java([REPO / source], stem)
            with zipfile.ZipFile(delivery / (stem + '.jar'), 'w') as target:
                target.write(dex, 'classes.dex')
        probe_resources = work / 'input-probe-resources.apk'
        run(sdk / 'bin/aapt', 'package', '-f', '-M', REPO / 'tools/input_probe/AndroidManifest.xml',
            '-I', android, '-F', probe_resources)
        dex = compile_java([REPO / 'tools/input_probe/PointerProbe.java'], 'input-probe')
        prepared = work / 'input-probe-prepared.apk'
        prepared_zip(probe_resources, prepared, {'classes.dex': dex})
        sign(prepared, 'H700InputProbe')
        return
    nav = REPO / 'android/h700-android10/device/roc/rgsp/RGSPNavigation'
    gen = work / 'nav-gen'; gen.mkdir(exist_ok=True)
    resource_apk = work / 'nav-resources.apk'
    run(sdk / 'bin/aapt', 'package', '-f', '-M', nav / 'AndroidManifest.xml', '-S', nav / 'res',
        '-I', android, '-J', gen, '-F', resource_apk)
    dex = compile_java([*sorted((nav / 'src').rglob('*.java')), *sorted(gen.rglob('*.java'))], 'navigation')
    prepared = work / 'nav-prepared.apk'
    prepared_zip(resource_apk, prepared, {'classes.dex': dex})
    outputs = [sign(prepared, 'RGSPNavigation-rg34xxsp')]
    if args.navigation_only:
        receipt_path = delivery / 'apps-build.json'
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        receipt[outputs[0].name] = {'bytes': outputs[0].stat().st_size,
            'sha256': hashlib.sha256(outputs[0].read_bytes()).hexdigest()}
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2), flush=True)
        return
    spec = importlib.util.spec_from_file_location('patch_rg34xxsp', REPO / 'tools/at4k/patch_rg34xxsp.py')
    patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)
    def historical_input(path, git_path, digest):
        if not path.exists():
            path.write_bytes(subprocess.check_output(['git', '-C', str(REPO), 'show',
                'baseline/h700-v5i-usb-network-20261028:' + git_path]))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, path
        return path
    base = historical_input(work / 'AT4K-frozen-base.apk',
        'android/h700-android10/device/roc/rgsp/prebuilt/AT4K/AT4K.apk', patcher.BASE_SHA)
    apktool = historical_input(work / 'apktool-2.9.3.jar', 'tools/apktool/apktool.jar',
        '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4')
    decoded = work / 'decoded'
    # Each rebuild recreates only this fixed temporary decoded tree from the pinned input.
    run(java, '-Xmx2g', '-jar', apktool, 'd', '-f', base, '-o', decoded)
    patcher.patch(decoded, base)
    helper = compile_java([REPO / 'tools/at4k/RgspWallpaper.java'], 'wallpaper-helper')
    unsigned = work / 'AT4K-unsigned.apk'
    run(java, '-Xmx2g', '-jar', apktool, 'b', decoded, '-o', unsigned)
    prepared = work / 'AT4K-prepared.apk'
    prepared_zip(unsigned, prepared, {'classes2.dex': helper})
    outputs.append(sign(prepared, 'AT4K-rg34xxsp'))
    receipt = {path.name: {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in outputs}
    (delivery / 'apps-build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)

if __name__ == '__main__':
    main()
