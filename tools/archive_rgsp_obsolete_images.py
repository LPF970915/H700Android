#!/usr/bin/env python3
"""Losslessly archive three historical expanded images; never delete sources."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "out/tf2-fix72-deploy-20260907-current-v2/data.before.img",
    "out/tf2-fix72-deploy-20260907-current-v2/data.journal-review.img",
    "out/tf2-data-backup-20260909-2359/offline-journal-trial/data.journal-replayed.img",
)
SIZE = 17179869184


def digest(stream):
    result, size = hashlib.sha256(), 0
    while chunk := stream.read(4 * 1024 * 1024):
        size += len(chunk)
        result.update(chunk)
    return size, result.hexdigest()


def main():
    for relative in FILES:
        source = ROOT / relative
        before = source.lstat()
        if (source.resolve() != source or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1 or before.st_size != SIZE):
            raise ValueError("Unsafe historical image path or size")
        target = source.with_name(source.name + ".archived-20260910.gz")
        receipt = target.with_name(target.name + ".json")
        print("ARCHIVING=" + str(source), flush=True)
        h = hashlib.sha256()
        total = 0
        with source.open("rb") as src, target.open("xb") as dst:
            with gzip.GzipFile(filename="", fileobj=dst, mode="wb", compresslevel=1, mtime=0) as zipped:
                while chunk := src.read(4 * 1024 * 1024):
                    h.update(chunk)
                    total += len(chunk)
                    zipped.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        after = source.stat()
        if total != SIZE or (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            raise ValueError("Source changed during archive")
        with gzip.open(target, "rb") as stream:
            if digest(stream) != (SIZE, h.hexdigest()):
                raise ValueError("Full decompressed archive verification failed")
        with target.open("rb") as stream:
            archive_bytes, archive_sha = digest(stream)
        with receipt.open("x") as stream:
            json.dump({"status": "FULL_ARCHIVE_VERIFIED_SOURCE_RETAINED",
                       "source": relative, "raw_bytes": SIZE, "raw_sha256": h.hexdigest(),
                       "archive_bytes": archive_bytes, "archive_sha256": archive_sha},
                      stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        print("ARCHIVE_VERIFIED=" + str(target), flush=True)


if __name__ == "__main__":
    main()
