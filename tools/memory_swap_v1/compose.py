"""Compose the reviewed swap prefix with the unchanged sampling-v2 input helper."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PARENT = REPO / 'tools/input_profiles/stick_sampling_v2/h700_optional_axes.sh'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = HERE / 'h700_optional_axes.sh'
    previous = PARENT.read_bytes()
    assert previous.startswith(b'#!/bin/sh\n')
    assert b"expected_module_sha256='5a017572b601ac8ae70216852cce3763428d5fa5793c4767812c8caf7b2d0deb'" in previous
    prefix = (HERE / 'swap_prefix.sh').read_bytes()
    result = b'#!/bin/sh\n' + prefix + previous[len(b'#!/bin/sh\n'):]
    assert result.endswith(previous[len(b'#!/bin/sh\n'):])
    assert result.count(b'expected_module_sha256=') == 1
    assert result.index(b'h700_swap_setup "$@"') < result.index(b'if [ "$sticks" = 0 ]; then')
    if target.exists():
        assert not (REPO / 'out/memory-swap-20261117/helper-tests-v1').exists(), 'Frozen tests already started'
    target.write_bytes(result)
    out = {'schema': 'roc.h700.swap-helper-composition.v1', 'passed': True,
           'parent_helper_path': str(PARENT), 'parent_helper_sha256': sha(PARENT),
           'prefix_path': str(HERE / 'swap_prefix.sh'), 'prefix_sha256': sha(HERE / 'swap_prefix.sh'),
           'helper_path': str(target), 'helper_sha256': sha(target),
           'axes_logic_byte_exact_suffix': True, 'swap_before_any_model_gate': True}
    (HERE / 'composition.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
