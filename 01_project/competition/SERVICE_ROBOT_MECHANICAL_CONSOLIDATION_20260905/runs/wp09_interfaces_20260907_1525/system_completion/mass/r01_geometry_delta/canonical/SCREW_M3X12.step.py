from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))
from mass_r01_geometry_delta import gen_step as _gen_step
def gen_step():
    return _gen_step('SCREW_M3X12')
