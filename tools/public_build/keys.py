#!/usr/bin/env python3
"""Generate a new builder-owned identity once, outside all source trees."""
from pathlib import Path
import argparse
import os
import sys
from common import REPO, run, sha, write_json
from prepare import ROLES


def create(output):
    output = Path(output).resolve()
    if output.is_relative_to(REPO) or output.exists():
        raise ValueError('Choose a new private directory outside the repository')
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    certs = {}
    for role in ROLES:
        temporary = output / (role + '.temporary.pem')
        cert = output / (role + '.x509.pem')
        key = output / (role + '.pk8')
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-nodes', '-days', '10950',
             '-sha256', '-subj', '/CN=ROC Community ' + role + '/O=Independent Android Build',
             '-addext', 'basicConstraints=critical,CA:FALSE', '-addext', 'keyUsage=critical,digitalSignature',
             '-keyout', temporary, '-out', cert])
        run(['openssl', 'pkcs8', '-topk8', '-inform', 'PEM', '-outform', 'DER', '-nocrypt',
             '-in', temporary, '-out', key])
        temporary.unlink()
        key.chmod(0o600)
        certs[role] = {'certificate_file_sha256': sha(cert)}
    write_json(output / 'public-certificates.json', certs)
    print('CREATED five builder-owned roles; retain a secure backup outside Git')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    try:
        create(args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)
