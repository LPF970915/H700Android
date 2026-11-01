"""Seal one retry-state fix into a new stage, preserving the audited parent."""
import json
from pathlib import Path
import subprocess
import sys
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
import package_h700_dualabi_prototype as proto
base.constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'sealed-stage-v1'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
lockfile = OUT / 'final-stage-v2.json'
record = json.loads(lockfile.read_text())
source = ROOT / 'final-stage-v2/system.candidate.raw'
assert base.sha(source) == record['system']['sha256']
system = WORK / 'system.candidate.raw'
subprocess.run(['cp', '--sparse=always', source, system], check=True)
installer = ROOT / 'payload64-v1/h700-preinstall.sh'
assert base.sha(installer) == json.loads((OUT / 'payload64-v1.json').read_text())['installer_sha256']
data = installer.read_text()
old = '[ ! -f "$state/complete" ] || exit 0'
new = '[ ! -f "$state/complete" ] || { setprop sys.h700.preinstall complete; exit 0; }'
assert (data.count(old) == 1 and new not in data) or (old not in data and data.count(new) == 1)
candidate = WORK / 'h700-preinstall.sh'
candidate.write_text(data.replace(old, new), newline='\n')
subprocess.run(['bash', '-n', candidate], check=True)
# Exercise the completed-install retry branch in a host-only sandbox. Commands
# beyond the branch must not run, even though the boot-local property is lost.
test = WORK / 'retry-host-test.sh'
test.write_text('set -eu\nsetprop() { test "$1" = sys.h700.preinstall && test "$2" = complete; echo restored; }\n'
                'state=' + base.q(WORK / 'state') + '\n' + new + '\necho unexpected\n')
(WORK / 'state').mkdir()
(WORK / 'state/complete').touch()
assert subprocess.check_output(['bash', test], text=True).strip() == 'restored'
proto.WORK = WORK
modified = proto.modify(system, {'/system/bin/h700-preinstall.sh':
    (candidate, '0100755', 'u:object_r:shell_exec:s0')}, 'u:object_r:system_file:s0')
record['modified_files']['system'].update(modified)
record['system']['sha256'] = base.sha(system)
record['parent_final_stage_sha256'] = base.sha(lockfile)
record['completed_preinstall_retry_property_host_test_passed'] = True
record['first_boot_interruption_recovery_physically_tested'] = False
(OUT / 'sealed-stage-v1.json').write_text(json.dumps(record, indent=2) + '\n')
print('SEALED_PARITY_STAGE_AND_RETRY_BRANCH_PASS', flush=True)
