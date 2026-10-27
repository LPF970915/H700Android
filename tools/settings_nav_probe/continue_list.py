"""Continue a stopped, unchanged Settings list without replaying confirmations."""
import argparse
import hashlib
import json
from pathlib import Path
from audit import Audit
from explore import Explorer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--path', nargs='+', required=True)
    parser.add_argument('--settings-sha', required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    raw = args.source.read_bytes()
    page = next(p for p in json.loads(raw)['pages'] if p['path'] == args.path)
    if page['status'] != 'RUNNING' or page['dialog']:
        raise ValueError('Only an unfinished non-dialog list can continue')
    audit = Audit()
    try:
        explorer = Explorer(audit, 'continued-' + args.tag)
        if explorer.output.exists():
            raise ValueError('Fresh continuation tag required')
        explorer.visit(args.path, resume={
            'page': page, 'direction': 'd', 'source': args.source.name,
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'settings_apk_sha256': args.settings_sha,
            'scope': 'Original forward prefix retained; continue forward to bottom, then reverse to top',
        })
        print('CONTINUED_SCAN ' + str(explorer.output), flush=True)
    finally:
        audit.close()


if __name__ == '__main__':
    main()
