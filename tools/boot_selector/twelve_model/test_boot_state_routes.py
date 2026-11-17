"""Exercise actual host/AArch64 boot-state helpers against ordinary fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

from models import ALL_MODEL_IDS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-output',type=Path,required=True)
    parser.add_argument('--environment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists();args.output.mkdir(parents=True)
    seed=args.environment.read_bytes();assert len(seed)==128*1024
    cases=[]
    for name,runner in [('host',[str(args.native_output/'boot-state-host')]),
                        ('aarch64',['/usr/bin/qemu-aarch64',str(args.native_output/'boot-state-aarch64')])]:
        target=args.output/(name+'.fixture')
        with target.open('xb') as stream:
            stream.write(seed);stream.truncate(16*1024*1024)
        def call(action,*extra):
            return subprocess.check_output([*runner,'--fixture',str(target),action,*extra],text=True)
        for model in ALL_MODEL_IDS:
            call('save',model)
            status=call('status');assert status==f'saved={model}\nnext=\nnext_start=\n'
            once=ALL_MODEL_IDS[(ALL_MODEL_IDS.index(model)+1)%len(ALL_MODEL_IDS)]
            call('once',once)
            status=call('status');assert status==f'saved={model}\nnext={once}\nnext_start=1\n'
            call('clear-next')
            status=call('status');assert status==f'saved={model}\nnext=\nnext_start=\n'
            cases.append({'architecture':name,'saved':model,'once':once,'passed':True})
        with target.open('rb') as stream:
            stream.seek(len(seed));assert not any(stream.read())
    result={'passed':True,'cases':len(cases),'rows':cases,'ordinary_fixture_only':True,
            'actual_host_and_aarch64_helpers':True,'no_device_card_io':True,
            'environment_seed_sha256':hashlib.sha256(seed).hexdigest()}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
