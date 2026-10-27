"""Use the verified physical power-node timing, not a synthetic LONG_PRESS flag."""
import hashlib
from pathlib import Path

REMOTE = '/data/local/tmp/nav-power-held-1s-20261027.sh'


def open_power_menu(a):
    source = Path(__file__).with_name('nav-power-hold.sh')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    a.command('test "$(sha256sum ' + REMOTE + ' | cut -d \' \' -f 1)" = ' + digest)
    return a.command('sh ' + REMOTE)
