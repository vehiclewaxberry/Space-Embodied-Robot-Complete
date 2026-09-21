"""Corrected R2 generator for the Master Skeleton V2 STEP witness.

R1 is intentionally retained as a failed semantic audit artifact: its visual
+Y witness used the wrong Euler-rotation sign.  R2 imports the shared geometry
and replaces only the coordinate-triad construction.  This remains neutral
construction geometry with no physical or native-mate credit.
"""

import importlib.util
from math import cos, radians, sin
from pathlib import Path

from build123d import Align, Compound, Cylinder, Location


_R1_PATH = Path(__file__).with_name("B51R1_MASTER_SKELETON_V2_STEP_WITNESS.py")
_SPEC = importlib.util.spec_from_file_location("b51r1_master_skeleton_r1", _R1_PATH)
_R1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_R1)


def triad(x, name, angle_x_deg=0.0):
    """Build a right-handed +X/+Y/+Z visual triad clocked about +X."""
    a = radians(angle_x_deg)
    y_dir = (0.0, cos(a), sin(a))
    z_dir = (0.0, -sin(a), cos(a))

    x_axis = _R1.rod_x(
        _R1.TRIAD_LENGTH,
        0.0,
        0.0,
        _R1.TRIAD_R,
        f"{name}_X",
        x + _R1.TRIAD_LENGTH / 2.0,
    )
    y_axis = Cylinder(
        _R1.TRIAD_R,
        _R1.TRIAD_LENGTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    ).moved(Location((x, 0.0, 0.0), (angle_x_deg - 90.0, 0.0, 0.0)))
    y_axis = _R1.label(y_axis, f"{name}_Y")

    z_axis = Cylinder(
        _R1.TRIAD_R,
        _R1.TRIAD_LENGTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    ).moved(Location((x, 0.0, 0.0), (angle_x_deg, 0.0, 0.0)))
    z_axis = _R1.label(z_axis, f"{name}_Z")

    result = _R1.label(Compound(children=[x_axis, y_axis, z_axis]), name)
    result.metadata = {
        "x_axis": (1.0, 0.0, 0.0),
        "y_axis": y_dir,
        "z_axis": z_dir,
    }
    return result


_R1.triad = triad


def gen_step():
    result = _R1.gen_step()
    result.label = "B51R1_MASTER_SKELETON_V2_STEP_WITNESS_R2_DATUM_ONLY"
    return result

