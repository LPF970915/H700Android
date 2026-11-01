"""Inspect the pinned user-supplied APK offline inside the low-pressure wrapper."""
import hashlib
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
sys.path.insert(0, str(REPO / 'tools/interaction'))
from package_h700_v6a import constrained
from dex_port import DexPort

constrained()
source = Path('/mnt/d/Downloads/Ayaspace2/pocketmuseum-0.3.3-release.apk')
assert hashlib.sha256(source.read_bytes()).hexdigest() == '205cbf8b87d3b696b3c3873dbaa0ad47fbe0e57acce8ca208961a7aea476df38'
work = Path('/home/lpf/h700-ayaspace2-20261101/inspect-v1')
work.parent.mkdir(exist_ok=True)
port = DexPort(REPO, work)
port.run(*port.java, 'disassemble', source, 'classes.dex', work / 'smali')
dependencies = [Path('/home/lpf/h700-dualabi-parity-20261101/inputs-gsi/framework.jar')]
dependencies.extend(Path('/home/lpf/h700-dualabi-parity-20261101/api-audit-v3').glob('*.jar'))
result = port.run('taskset', '-c', '0', port.jdk / 'java', '-Xmx2g', '-cp',
                  str(work) + ':' + str(port.apktool), 'FrameworkApiAudit',
                  ':'.join(map(str, dependencies)), source)
(REPO / 'out/ayaspace2-20261101/api29-audit-original.txt').write_text(result)
print(result, flush=True)
