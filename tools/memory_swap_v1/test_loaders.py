"""Run the existing 45 loader cases against the actual composed helper."""
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[1] / 'tools/input_profiles/stick_sampling_v2/test_loaders.py'


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('sampling_v2_loader_tests', ORIGINAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.main()
