"""Read-only, planar bearing-face measurements on already placed STEP shapes.

Importing this module does not import a CAD kernel, cadgen, or a generator.
Call ``contact_area`` explicitly with build123d shapes or TopoDS_Shapes already
read from the actual STEP files and placed in world coordinates, in millimetres.
The caller owns STEP provenance, placement, pair names and acceptance thresholds.

For a side with axis_world=(0, sign_y, 0), the current nominal planes are:
  outer washer -> clip: 109.15; clip -> web: 103.15;
  web -> inner washer: 101.15; inner washer -> nut: 100.65;
  screw head -> outer washer: 109.65.
These offsets are examples for the frozen stack, not inferred acceptance limits.

The plane equation is dot(normalize(axis_world), world_point_mm)=plane_offset_mm.
No faces are projected, translated, enlarged, meshed or substituted by disks.
Area comes from BRepAlgoAPI_Common of the actual trimmed planar faces, including
holes and chamfers. A zero solid intersection volume is never used as evidence
of contact. Common uses no added fuzzy tolerance; native OCCT shape tolerances
still apply and are reported. Plane-selection tolerance is not a fit tolerance.

MEASURED is a measurement status, not engineering PASS. The caller must also
check solid interpenetration, coverage, intended load path and its own thresholds.
Exceptions, absent faces and ambiguous overlapping selected faces fail closed.
There is deliberately no automatic STEP load, job, CLI run or output-file write.
"""

from __future__ import annotations

import math
from typing import Any, Sequence


class ContactMeasurementError(RuntimeError):
    """The requested face-area measurement could not be established reliably."""


def _request(axis_world: Sequence[float], plane_offset_mm: float, tol_mm: float):
    axis = tuple(float(v) for v in axis_world)
    if len(axis) != 3 or not all(math.isfinite(v) for v in axis):
        raise ValueError("axis_world must contain three finite numbers")
    length = math.hypot(*axis)
    if not math.isfinite(length) or length == 0:
        raise ValueError("axis_world must have finite, nonzero length")
    offset, tol = float(plane_offset_mm), float(tol_mm)
    if not math.isfinite(offset) or not math.isfinite(tol) or tol <= 0:
        raise ValueError("plane offset must be finite and tol_mm positive")
    return tuple(v / length for v in axis), offset, tol


def _kernel():
    # Lazy by design: an import/static audit of this file cannot start CAD work.
    from OCP.Bnd import Bnd_Box
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.TopTools import TopTools_ListOfShape

    return locals()


def _faces(shape, k):
    explorer = k["TopExp_Explorer"](shape, k["TopAbs_FACE"])
    result = []
    while explorer.More():
        face = k["TopoDS"].Face_s(explorer.Current())
        if not any(face.IsSame(previous) for previous in result):
            result.append(face)
        explorer.Next()
    return result


def _area(shape, k):
    props = k["GProp_GProps"]()
    k["BRepGProp"].SurfaceProperties_s(shape, props)
    area = float(props.Mass())
    if not math.isfinite(area) or area < 0:
        raise ContactMeasurementError(f"Invalid surface-area result: {area!r}")
    return area


def _bbox(shape, k):
    box = k["Bnd_Box"]()
    box.SetGap(0.0)
    k["BRepBndLib"].AddOptimal_s(shape, box, False, False)
    if box.IsVoid():
        return None
    coordinates = tuple(float(v) for v in box.Get())
    if not all(math.isfinite(v) for v in coordinates):
        raise ContactMeasurementError("Non-finite BRep bounding box")
    return {"min_mm": list(coordinates[:3]), "max_mm": list(coordinates[3:])}


def _merge_bbox(boxes):
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        return None
    return {
        "min_mm": [min(box["min_mm"][i] for box in boxes) for i in range(3)],
        "max_mm": [max(box["max_mm"][i] for box in boxes) for i in range(3)],
    }


def _common(face_a, face_b, k):
    arguments, tools = k["TopTools_ListOfShape"](), k["TopTools_ListOfShape"]()
    arguments.Append(face_a)
    tools.Append(face_b)
    operation = k["BRepAlgoAPI_Common"]()
    operation.SetArguments(arguments)
    operation.SetTools(tools)
    operation.SetNonDestructive(True)
    operation.SetRunParallel(False)
    operation.SetFuzzyValue(0.0)
    operation.Build()
    if not operation.IsDone():
        raise ContactMeasurementError("Face Common IsDone is false")
    for name in ("HasErrors", "HasWarnings"):
        method = getattr(operation, name, None)
        if callable(method) and method():
            raise ContactMeasurementError(f"Face Common reports {name}")
    common = operation.Shape()
    if common.IsNull():
        raise ContactMeasurementError("Face Common returned a null shape")
    faces = _faces(common, k)
    if faces and not k["BRepCheck_Analyzer"](common).IsValid():
        raise ContactMeasurementError("Face Common returned invalid topology")
    return {
        "area_mm2": sum(_area(face, k) for face in faces),
        "face_count": len(faces),
        "bbox_mm": _merge_bbox([_bbox(face, k) for face in faces]),
    }


def _select(shape, axis, offset, tol, k):
    wrapped = getattr(shape, "wrapped", shape)
    if wrapped is None or wrapped.IsNull():
        raise ContactMeasurementError("Input shape is null")
    if not k["BRepCheck_Analyzer"](wrapped).IsValid():
        raise ContactMeasurementError("Input shape has invalid topology")
    selected, selected_info = [], []
    all_faces = _faces(wrapped, k)
    # This is an angular tolerance (sine), independent of the millimetre tolerance.
    normal_cross_tolerance = 1e-10
    for face_index, face in enumerate(all_faces, 1):
        surface = k["BRepAdaptor_Surface"](face, True)
        if surface.GetType() != k["GeomAbs_Plane"]:
            continue
        plane = surface.Plane()
        point = tuple(float(v) for v in plane.Location().Coord())
        normal = tuple(float(v) for v in plane.Axis().Direction().Coord())
        cross = (
            normal[1] * axis[2] - normal[2] * axis[1],
            normal[2] * axis[0] - normal[0] * axis[2],
            normal[0] * axis[1] - normal[1] * axis[0],
        )
        actual_offset = sum(a * p for a, p in zip(axis, point))
        if math.hypot(*cross) > normal_cross_tolerance or abs(actual_offset - offset) > tol:
            continue
        orientation = face.Orientation()
        if orientation == k["TopAbs_REVERSED"]:
            normal = tuple(-v for v in normal)
        elif orientation != k["TopAbs_FORWARD"]:
            raise ContactMeasurementError("Selected face has no unambiguous external orientation")
        selected.append(face)
        selected_info.append({
            "face_index_1based": face_index,
            "area_mm2": _area(face, k),
            "bbox_mm": _bbox(face, k),
            "normal_world": list(normal),
            "normal_dot_axis": sum(n * a for n, a in zip(normal, axis)),
            "actual_plane_offset_mm": actual_offset,
            "plane_selection_residual_mm": actual_offset - offset,
            "occt_face_tolerance_mm": float(k["BRep_Tool"].Tolerance_s(face)),
        })
    # Summing pairwise intersections is sound only if each side has no duplicated
    # overlapping planar area. Refuse ambiguity instead of silently double-counting.
    for i, face_a in enumerate(selected):
        for j in range(i + 1, len(selected)):
            if _common(face_a, selected[j], k)["area_mm2"] > tol * tol:
                raise ContactMeasurementError(
                    f"Selected faces {i + 1}, {j + 1} overlap within one input; sum is ambiguous"
                )
    return selected, {
        "input_face_count": len(all_faces),
        "selected_face_count": len(selected),
        "selected_faces_area_mm2": sum(item["area_mm2"] for item in selected_info),
        "selected_bbox_mm": _merge_bbox([item["bbox_mm"] for item in selected_info]),
        "faces": selected_info,
    }


def contact_area(
    a: Any,
    b: Any,
    axis_world: Sequence[float],
    plane_offset_mm: float,
    tol_mm: float = 1e-5,
) -> dict:
    """Measure real, oppositely oriented planar contact, returning JSON-safe data.

    ``a`` and ``b`` are world-placed build123d/TopoDS shapes, not filenames. On
    missing faces or measurement errors, ``contact_area_mm2`` remains None (never
    a fabricated zero). A completed Common with no overlapping area returns 0.0.
    Non-opposed positive-area face intersections are reported but are not credited
    as contact. No value here substitutes for a root-defined bearing-area threshold.
    """
    result = {
        "schema": "PLANAR_BEARING_CONTACT_AREA_V1",
        "status": "INCOMPLETE",
        "contact_area_mm2": None,
        "contact_bbox_mm": None,
        "contact_face_count": None,
        "method": "OCCT actual trimmed planar face Common; SurfaceProperties",
        "normal_cross_tolerance": 1e-10,
        "boolean_fuzzy_value_mm": 0.0,
        "projection_or_geometry_substitution": False,
        "engineering_acceptance_evaluated": False,
        "pairs": [],
    }
    try:
        axis, offset, tol = _request(axis_world, plane_offset_mm, tol_mm)
        result.update(axis_world_unit=list(axis), plane_offset_mm=offset, selection_tol_mm=tol)
        k = _kernel()
        faces_a, result["a"] = _select(a, axis, offset, tol, k)
        faces_b, result["b"] = _select(b, axis, offset, tol, k)
        if not faces_a or not faces_b:
            result.update(status="INCOMPLETE_NO_SELECTED_FACES", reason="Requested plane lacks faces on one or both inputs")
            return result
        non_opposed = []
        for i, face_a in enumerate(faces_a):
            for j, face_b in enumerate(faces_b):
                info_a, info_b = result["a"]["faces"][i], result["b"]["faces"][j]
                pair = _common(face_a, face_b, k)
                normal_dot = sum(x * y for x, y in zip(info_a["normal_world"], info_b["normal_world"]))
                pair.update(
                    a_face_index_1based=info_a["face_index_1based"],
                    b_face_index_1based=info_b["face_index_1based"],
                    oriented_normal_dot=normal_dot,
                    opposed_normals=normal_dot < 0.0,
                    plane_offset_difference_mm=info_b["actual_plane_offset_mm"] - info_a["actual_plane_offset_mm"],
                )
                result["pairs"].append(pair)
                if pair["area_mm2"] > tol * tol and not pair["opposed_normals"]:
                    non_opposed.append([pair["a_face_index_1based"], pair["b_face_index_1based"]])
        if non_opposed:
            result.update(status="INCOMPLETE_NON_OPPOSED_FACES", non_opposed_face_pairs=non_opposed)
            return result
        credited = [pair for pair in result["pairs"] if pair["opposed_normals"]]
        result.update(
            status="MEASURED",
            contact_area_mm2=sum(pair["area_mm2"] for pair in credited),
            contact_face_count=sum(pair["face_count"] for pair in credited),
            contact_bbox_mm=_merge_bbox([pair["bbox_mm"] for pair in credited]),
        )
    except Exception as exc:
        result.update(status="MEASUREMENT_EXCEPTION", exception_type=type(exc).__name__, exception_message=str(exc))
    return result


if __name__ == "__main__":
    raise SystemExit("Function library only; explicitly call contact_area on actual, world-placed STEP shapes.")
