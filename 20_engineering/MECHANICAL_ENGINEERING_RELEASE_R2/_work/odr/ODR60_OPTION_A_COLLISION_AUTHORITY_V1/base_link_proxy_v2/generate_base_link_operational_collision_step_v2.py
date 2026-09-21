"""STEP-first generator for the B601 base_link operational collision proxy V2.

The source STEP is immutable.  Sixty-six source solids are retained exactly
apart from the frozen WP11 link-frame translation.  The two DM-J4340P solids
and the thin base plate that cannot produce a complete auditable mesh are
replaced by tolerance-aware, strictly containing AABBs.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from OCP.BRep import BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.Bnd import Bnd_Box
from OCP.Font import Font_FontMgr
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TCollection import TCollection_AsciiString
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec


# build123d 0.11.1 scans every user font on first import on Windows.  The host
# has one non-font file with a font extension, so establish the canary alias
# before importing build123d.  No text geometry is used by this generator.
_font_manager = Font_FontMgr.GetInstance_s()
_font_manager.AddFontAlias(
    TCollection_AsciiString("singleline"), TCollection_AsciiString("Arial")
)

from build123d import Color, Compound, Solid  # noqa: E402


MODEL_NAME = "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2"
SOURCE_STEP_REL = Path(
    "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
    "vendor_reference_linklocal/B50_REF_base_link_LINKLOCAL.step"
)
SOURCE_STEP_SHA256 = "A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5"
SOURCE_STEP_BYTES = 25_111_906

D_BASE_LINK_MM = (-0.05732750272995675, -0.03253727084589079, 0.05006764302725364)
REPLACED_TRAVERSAL_INDICES = (58, 59, 68)
EXPECTED_SOURCE_SOLID_COUNT = 69
EXPECTED_RETAINED_SOLID_COUNT = 66

EXPECTED_MOTOR_TOL_AABB_MM = (
    (-28.415038038579, -28.522004415829, 20.854345909634),
    (28.585038038580, 28.478012831305, 77.359619319645),
)
EXPECTED_PLATE_TOL_AABB_MM = (
    (-45.915000100000, -46.022000099999, 75.604999899980),
    (46.085000100000, 45.978000100000, 82.555000100030),
)
AABB_BOUND_CONTRACT_TOLERANCE_MM = 2.0e-6


def _workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_step(path: Path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    root_count = int(reader.TransferRoots())
    shape = reader.OneShape()
    if root_count != 1 or shape.IsNull():
        raise RuntimeError(
            f"STEP transfer invalid: roots={root_count}, null={shape.IsNull()}"
        )
    return shape


def _solids(shape) -> list:
    result = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        result.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    return result


def _volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return float(properties.Mass())


def _compound(shapes: list):
    builder = BRep_Builder()
    result = TopoDS_Compound()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape)
    return result


def _tol_aabb(shapes: list) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    bounds = Bnd_Box()
    for shape in shapes:
        BRepBndLib.AddOptimal_s(shape, bounds, False, True)
    values = tuple(float(value) for value in bounds.Get())
    return values[:3], values[3:]


def _assert_bounds(
    actual: tuple[tuple[float, float, float], tuple[float, float, float]],
    expected: tuple[tuple[float, float, float], tuple[float, float, float]],
    label: str,
) -> None:
    maximum_error = max(
        abs(actual[row][axis] - expected[row][axis])
        for row in range(2)
        for axis in range(3)
    )
    if maximum_error > AABB_BOUND_CONTRACT_TOLERANCE_MM:
        raise RuntimeError(
            f"{label} tolerance-aware AABB contract drifted by {maximum_error:.9g} mm"
        )


def _translated(shape):
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(*D_BASE_LINK_MM))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def _box_from_bounds(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
):
    lower, upper = bounds
    final_lower = tuple(lower[i] + D_BASE_LINK_MM[i] for i in range(3))
    final_upper = tuple(upper[i] + D_BASE_LINK_MM[i] for i in range(3))
    if not all(final_upper[i] > final_lower[i] for i in range(3)):
        raise RuntimeError(f"invalid box bounds: {bounds}")
    return BRepPrimAPI_MakeBox(gp_Pnt(*final_lower), gp_Pnt(*final_upper)).Solid()


def _label(shape, label: str, color: Color, material: str):
    wrapped = Solid.cast(shape)
    wrapped.label = label
    wrapped.color = color
    wrapped.material = material
    return wrapped


def gen_step():
    workspace = _workspace_root()
    source_path = workspace / SOURCE_STEP_REL
    if source_path.stat().st_size != SOURCE_STEP_BYTES:
        raise RuntimeError("pinned B50 source byte count changed")
    if _sha256(source_path) != SOURCE_STEP_SHA256:
        raise RuntimeError("pinned B50 source SHA-256 changed")

    source = _read_step(source_path)
    solids = _solids(source)
    if len(solids) != EXPECTED_SOURCE_SOLID_COUNT:
        raise RuntimeError(f"expected 69 source solids, found {len(solids)}")

    retained = []
    for index, solid in enumerate(solids):
        if index in REPLACED_TRAVERSAL_INDICES:
            continue
        if not BRepCheck_Analyzer(solid, True).IsValid():
            raise RuntimeError(f"retained source solid {index} is not BRep-valid")
        volume = _volume_mm3(solid)
        if not math.isfinite(volume) or volume <= 0.0:
            raise RuntimeError(f"retained source solid {index} has invalid volume")
        retained.append((index, _translated(solid)))
    if len(retained) != EXPECTED_RETAINED_SOLID_COUNT:
        raise RuntimeError(f"expected 66 retained solids, found {len(retained)}")

    motor_bounds = _tol_aabb([solids[58], solids[59]])
    plate_bounds = _tol_aabb([solids[68]])
    _assert_bounds(motor_bounds, EXPECTED_MOTOR_TOL_AABB_MM, "motor")
    _assert_bounds(plate_bounds, EXPECTED_PLATE_TOL_AABB_MM, "plate")

    exact_color = Color(0.66, 0.69, 0.73, 1.0)
    proxy_color = Color(0.94, 0.58, 0.12, 0.70)
    exact_material = (
        "PINNED_B50_BREP_EXACT_EXCEPT_FROZEN_D_BASE_LINK_TRANSLATION;"
        "COLLISION_ONLY_NO_MASS_AUTHORITY"
    )
    proxy_material = (
        "TOLERANCE_AWARE_STRICT_CONSERVATIVE_AABB;"
        "SUBSTITUTED_NONTRIANGULATING_SOURCE_REGION;"
        "COLLISION_ONLY_NOT_HARDWARE_SHAPE_OR_MASS_AUTHORITY"
    )

    children = [
        _label(
            shape,
            f"B50_EXACT_RETAINED_TRAVERSAL_{index:02d}",
            exact_color,
            exact_material,
        )
        for index, shape in retained
    ]
    children.extend(
        [
            _label(
                _box_from_bounds(motor_bounds),
                "DM_J4340P_TRAVERSAL_58_59_STRICT_CONSERVATIVE_AABB",
                proxy_color,
                proxy_material,
            ),
            _label(
                _box_from_bounds(plate_bounds),
                "BASE_PLATE_TRAVERSAL_68_STRICT_CONSERVATIVE_AABB",
                proxy_color,
                proxy_material,
            ),
        ]
    )

    result = Compound(children=children, label=MODEL_NAME)
    result.material = (
        "B601_BASE_LINK_OPERATIONAL_COLLISION_ONLY;UNITS_MM;FRAME_BASE_LINK;"
        "RAW_URDF_BASE_LINK_STL_FORBIDDEN;NO_PATH_SEARCH_AUTHORITY"
    )
    return result


if __name__ == "__main__":
    model = gen_step()
    print(
        {
            "label": model.label,
            "child_count": len(model.children),
            "solid_count": len(model.solids()),
        }
    )
