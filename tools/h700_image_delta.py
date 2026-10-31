"""Bounded block deltas for regular prototype image files, no device access."""
import hashlib
from pathlib import Path

def block_delta(parent, candidate, directory, maximum=1024**2):
    directory=Path(directory);directory.mkdir()
    if parent.stat().st_size!=candidate.stat().st_size:raise ValueError('Partition size changed')
    result=[];offset=0;pending=None
    def flush():
        nonlocal pending
        if pending is None:return
        at,old,new=pending;i=len(result)
        left=f'{i:03d}.old.bin';right=f'{i:03d}.new.bin'
        (directory/left).write_bytes(old);(directory/right).write_bytes(new)
        result.append({'offset':at,'bytes':len(old),'old_sha256':hashlib.sha256(old).hexdigest(),
                       'new_sha256':hashlib.sha256(new).hexdigest(),'old_file':left,'new_file':right})
        pending=None
    with parent.open('rb') as a,candidate.open('rb') as b:
        while left:=a.read(4*1024**2):
            right=b.read(len(left))
            if len(left)!=len(right):raise ValueError('Short candidate')
            if left!=right:
                for i in range(0,len(left),4096):
                    x,y=left[i:i+4096],right[i:i+4096]
                    if x==y:continue
                    at=offset+i
                    if pending and pending[0]+len(pending[1])==at and len(pending[1])<65536:
                        pending=(pending[0],pending[1]+x,pending[2]+y)
                    else:flush();pending=(at,x,y)
            offset+=len(left)
        flush()
    if not result or sum(r['bytes'] for r in result)>maximum:raise ValueError('Unexpected delta extent')
    # Reconstruct the candidate stream using only the parent and published
    # ranges. This detects incomplete or incorrectly coalesced manifests.
    digest=hashlib.sha256();at=0
    with parent.open('rb') as source:
        for r in result:
            left=r['offset']-at
            while left:
                data=source.read(min(left,8*1024**2));digest.update(data);left-=len(data);at+=len(data)
            old=source.read(r['bytes'])
            if hashlib.sha256(old).hexdigest()!=r['old_sha256']:raise ValueError('Parent delta mismatch')
            digest.update((directory/r['new_file']).read_bytes());at+=r['bytes']
        while data:=source.read(8*1024**2):digest.update(data)
    with candidate.open('rb') as f:expected=hashlib.file_digest(f,'sha256').hexdigest()
    if digest.hexdigest()!=expected:raise ValueError('Delta reconstruction mismatch')
    return result
