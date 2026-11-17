"""Check public 0.0.3 version inputs and public tooling without an Android build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    constrained()
    started = time.monotonic()
    result_path = args.output / 'source-check.json'
    if result_path.exists():
        raise ValueError('Preserve existing source validation')
    directory = args.work / 'public-source-check'
    directory.mkdir(parents=True, exist_ok=False)
    manifest = REPO / 'build-support/public/source-manifest.json'
    initial = sha(manifest)
    commands = []

    def run(argv, name):
        ran = subprocess.run(list(map(str, argv)), cwd=REPO, capture_output=True, text=True,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        log = directory / (name + '.log')
        log.write_text(ran.stdout + ran.stderr)
        commands.append({'name': name, 'returncode': ran.returncode, 'log_sha256': sha(log)})
        if ran.returncode:
            raise ValueError(name + ' failed: ' + (ran.stdout + ran.stderr)[-2000:])
        return ran.stdout

    run([sys.executable, '-B', REPO / 'tools/public_build/test_public_build.py'], 'public-tools')
    output = run([sys.executable, '-B', REPO / 'tools/public_build/validate_manifest.py',
                  '--output', directory / 'manifest.json'], 'manifest')
    validation = json.loads(output)
    overlay = REPO / 'build-support/public/overlay/device/roc/roc_os_release_candidate/release_properties.mk'
    makefile = directory / 'Makefile'
    makefile.write_text('PRODUCT_SYSTEM_DEFAULT_PROPERTIES := ro.roc.os.version=old ro.debuggable=1\n'
                        'BUILD_DISPLAY_ID := old\ninclude ' + str(overlay) + '\nall:\n'
                        '\t@echo "$(BUILD_DISPLAY_ID) $(PRODUCT_SYSTEM_DEFAULT_PROPERTIES)"\n')
    effective = run(['/usr/bin/make', '-s', '-f', makefile], 'version-properties').split()
    if effective[0] != 'ROC_OS_ARM64_ver0.0.3' or effective.count('ro.roc.os.version=0.0.3') != 1:
        raise ValueError('Effective version properties differ')
    if 'ro.roc.os.version=old' in effective or 'ro.debuggable=1' in effective or 'ro.debuggable=0' not in effective:
        raise ValueError('Property precedence differs')
    if sha(manifest) != initial:
        raise ValueError('Source manifest changed during checks')
    result = {'schema': 'roc.h700.release003.source-check.v1', 'passed': True,
              'version': '0.0.3', 'source_manifest_sha256': initial, 'public_tool_tests': 11,
              'manifest_validation': validation, 'effective_display_id': effective[0],
              'effective_version': '0.0.3', 'commands': commands,
              'Android_full_rebuild_performed': False, 'device_accessed': False,
              'elapsed_seconds': time.monotonic()-started}
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'source_manifest_sha256': initial,
                      'public_tool_tests': 11, 'elapsed_seconds': result['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
