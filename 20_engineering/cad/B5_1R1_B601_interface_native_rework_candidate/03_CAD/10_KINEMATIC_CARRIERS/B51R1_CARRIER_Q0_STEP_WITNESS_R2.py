"""API-corrected R2 generator for the accepted-URDF carrier q0 witness.

R1 is retained as a failed build audit artifact.  Its kinematic validation
passed, but four visual-marker calls supplied translation tuples where this
installed build123d release requires Location objects.  R2 installs only that
compatibility adapter and delegates all authority/hash/kinematic logic to R1.
"""

import importlib.util
from pathlib import Path

from build123d import Location, Shape


_ORIGINAL_MOVED = Shape.moved


def _moved_with_translation_tuple(self, loc):
    if isinstance(loc, tuple):
        loc = Location(loc)
    return _ORIGINAL_MOVED(self, loc)


Shape.moved = _moved_with_translation_tuple

_R1_PATH = Path(__file__).with_name("B51R1_CARRIER_Q0_STEP_WITNESS.py")
_SPEC = importlib.util.spec_from_file_location("b51r1_carrier_q0_r1", _R1_PATH)
_R1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_R1)


def gen_step():
    result = _R1.gen_step()
    result.label = "B51R1_CARRIER_Q0_STEP_WITNESS_R2_10_LINKS_6R_1FIXED_2P_DATUM_ONLY"
    return result

