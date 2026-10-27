#!/usr/bin/env python3
"""Refresh the RGSP media volume cache before handling a mounted broadcast."""
import argparse
import hashlib
from pathlib import Path

REL='packages/providers/MediaProvider/src/com/android/providers/media/MediaProvider.java'
BEFORE='e840c3e0f867d3fdbf595e4a0cb0a7741243b478696cd2c9ca6c65b7833ed038'
OLD='''                    case Intent.ACTION_MEDIA_MOUNTED:
                        attachVolume(volumeName);'''
NEW='''                    case Intent.ACTION_MEDIA_MOUNTED:
                        // On RGSP the vold handoff can deliver this broadcast
                        // before the independent storage-listener cache update.
                        // Resolve the real current volumes before attaching;
                        // retain the existing unavailable-volume validation.
                        if ("rgsp".equals(android.os.Build.DEVICE)) {
                            updateVolumes();
                        }
                        attachVolume(volumeName);'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();path=a.source/REL
    data=path.read_bytes();text=data.decode()
    original=text.replace(NEW,OLD)
    if hashlib.sha256(original.encode()).hexdigest()!=BEFORE or original.count(OLD)!=1:
        raise SystemExit('Unrecognized MediaProvider edits; no source changed')
    patched=original.replace(OLD,NEW).encode()
    if data==patched:print('ALREADY_APPLIED')
    else:path.write_bytes(patched);print('RGSP_MEDIA_MOUNT_CACHE_REFRESH_APPLIED')


if __name__=='__main__':main()
