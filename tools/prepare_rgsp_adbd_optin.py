#!/usr/bin/env python3
"""Keep RGSP TCP ADB opt-in when USB FunctionFS is unavailable."""
import argparse
import hashlib
from pathlib import Path

REL='system/core/adb/daemon/main.cpp'
BEFORE='dd9a46f3544775aff023200929c0f75fa3b1b5dcd07e3ba67be8ca2a0bd87920'
OLD='''    } else if (!is_usb) {
        // Listen on default port.'''
NEW='''    } else if (!is_usb
            && android::base::GetProperty("ro.product.device", "") != "rgsp") {
        // RGSP has no functioning USB FunctionFS endpoint. Require an explicit
        // TCP port there so UART can restore source restrictions before listen.
        // Other products retain the original default-port fallback.
        // Listen on default port.'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();path=a.source/REL
    data=path.read_bytes();text=data.decode();original=text.replace(NEW,OLD)
    if hashlib.sha256(original.encode()).hexdigest()!=BEFORE or original.count(OLD)!=1:
        raise SystemExit('Unrecognized adbd edits; no source changed')
    patched=original.replace(OLD,NEW).encode()
    if data==patched:print('ALREADY_APPLIED')
    else:path.write_bytes(patched);print('RGSP_ADBD_EXPLICIT_TCP_PORT_APPLIED')


if __name__=='__main__':main()
