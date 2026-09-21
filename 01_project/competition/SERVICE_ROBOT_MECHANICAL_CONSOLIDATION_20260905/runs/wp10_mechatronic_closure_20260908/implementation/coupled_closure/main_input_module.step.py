from pathlib import Path
import importlib.util
from build123d import Compound
path=Path(__file__).with_name('mechanical_parts.py')
spec=importlib.util.spec_from_file_location('closure_mechanical_parts',path)
parts=importlib.util.module_from_spec(spec);spec.loader.exec_module(parts)
def gen_step():
    return Compound(label='WP10_MAIN_INPUT_MODULE_CANDIDATE_PARTIAL_POPULATION_NO_HOST_INSTALL',children=parts.main_parts())
