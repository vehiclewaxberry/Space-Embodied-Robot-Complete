from pathlib import Path
import importlib.util
from build123d import Compound
path=Path(__file__).with_name('mechanical_parts.py')
spec=importlib.util.spec_from_file_location('closure_mechanical_parts',path)
parts=importlib.util.module_from_spec(spec);spec.loader.exec_module(parts)
def gen_step():
    return Compound(label='C_POD_PROJECT_INTERFACE_KIT_NO_OEM_MATING_OR_PRESSURE_DESIGN',children=parts.propulsion_parts())
