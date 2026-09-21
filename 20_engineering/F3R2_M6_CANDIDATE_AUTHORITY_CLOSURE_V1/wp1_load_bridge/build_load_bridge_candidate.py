# -*- coding: utf-8 -*-
"""Build the M6 WP1 spacecraft-to-M3R load bridge CANDIDATE geometry.

This builder closes only the candidate layer of BOM item DP-007
(SPACECRAFT_LOAD_BRIDGE, HARD_HOLD in the M4 digital prototype BOM).  It
produces a lightweight parameterized B-rep that nominally spans the measured
10.75 mm minimum geometry gap between the 12U bus proxy +X face (x = 185.25
mm, also the legacy-flange outer face) and the M3R Stage B spacecraft-side
face (x = 196.0 mm, derived from the x = 208.0 mm physical installation face
minus the 12.0 mm Stage B base thickness).

The gap span is evidence of the missing load bridge, not an assembly pass.
Every output of this script is CANDIDATE class: candidate != authority,
diagnostic != released.  No measured, installed, manufacturing, flight, or
qualification claim is made.  No FEA is performed.  The legacy flange
(x 170.25-185.25 mm) has ambiguous ownership and is never merged into the
bridge geometry or mass.

Run with FreeCADCmd (single process, WP1-exclusive Owner Override):
    G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe build_load_bridge_candidate.py

Length units are millimetres throughout this file.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import FreeCAD as App
import Part


HERE = Path(__file__).resolve().parent
M6_ROOT = HERE.parent
PROJECT_ROOT = M6_ROOT.parents[1]
M4_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
M3_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DETAILED_DESIGN_V1"
M3_TERMINAL_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"

OUTPUT_FCSTD = HERE / "LOAD_BRIDGE_CANDIDATE_V1.FCStd"
OUTPUT_STEP = HERE / "LOAD_BRIDGE_CANDIDATE_V1.step"
BUILD_RUN = HERE / "LOAD_BRIDGE_BUILD_RUN_V1.json"

M3R_STEP = M3_ROOT / "06_parameterized_parts" / "m3r" / "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step"
M3R_PHYSICAL_STACK = (
    M3_TERMINAL_ROOT / "03_native_cad" / "M3_interface_authority" / "M3R_TSM_PHYSICAL_STACK.yaml"
)
M3R_ADAPTER_SSOT = (
    M3_TERMINAL_ROOT / "03_native_cad" / "M3_interface_authority" / "M3R_ADAPTER_INTERFACE_SSOT.yaml"
)
M3R_STAGE_B_TABLE = M3_ROOT / "06_parameterized_parts" / "m3r" / "M3R_STAGE_B_PARAMETER_TABLE.yaml"
M4_FRAME_TREE = M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
M4_MATERIAL_LIBRARY = M4_ROOT / "04_material_database" / "PROTOTYPE_MATERIAL_LIBRARY_V1.yaml"
MODEL_SPECS = PROJECT_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "model_specs_v0.json"
M6_BOUNDARY = M6_ROOT / "00_authority" / "M6_PHASE_AUTHORITY_AND_BOUNDARY.yaml"

MEMORY_THRESHOLD_GIB = 6.0
OWNER_OVERRIDE_SOURCE = (
    "C:/Users/stude/.codex/attachments/038d9781-5921-4858-9fea-c070890a71b8/pasted-text.txt"
)

# ---------------------------------------------------------------------------
# Parameter block.  Every value carries its provenance.  Classification
# vocabulary follows the M3R stage tables: FROZEN / DERIVED / CANDIDATE /
# UNKNOWN.  FROZEN here means frozen inside the upstream working loop only;
# nothing in this script promotes any value to release authority.
# ---------------------------------------------------------------------------
PARAMS = {
    # Axial station semantics (mm, S frame +X axis).
    "x_station_m_frame_mm": {
        "value": 185.25,
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::accepted_urdf_base_frame.station_x_mm",
        "note": "M_FRAME_DYNAMICS_ORIGIN, nonphysical; equals bus-proxy +X outer face and legacy-flange outer face",
    },
    "x_station_adapter_plate_external_face_mm": {
        "value": 198.0,
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::adapter_plate_external_face.station_x_mm",
        "note": "existing load-spreading plate external face; no M4 geometry entity",
    },
    "x_station_physical_installation_face_mm": {
        "value": 208.0,
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::central_boss_physical_installation_face.station_x_mm",
        "note": "M3R local z=0 plane placement station",
    },
    "x_station_fastener_end_plane_mm": {
        "value": 210.405,
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::b601_as_built_fastener_end_plane.station_x_mm",
    },
    "m3r_pattern_center_yz_mm": {
        "value": [0.015994151, -0.086366070],
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::b601_as_built_fastener_end_plane.pattern_center_yz_mm",
    },
    "m3r_clocking_about_x_deg": {
        "value": 25.000014,
        "classification": "FROZEN",
        "source": "M3R_TSM_PHYSICAL_STACK.yaml::b601_as_built_fastener_end_plane.pattern_clocking_about_x_deg",
    },
    # M3R Stage B interface facts (working-loop FROZEN / DERIVED, not released).
    "stage_b_base_thickness_mm": {
        "value": 12.0,
        "classification": "FROZEN",
        "source": "M3R_STAGE_B_PARAMETER_TABLE.yaml::B-003",
    },
    "stage_b_base_square_width_mm": {
        "value": 160.0,
        "classification": "FROZEN",
        "source": "M3R_STAGE_B_PARAMETER_TABLE.yaml::B-001",
    },
    "stage_b_base_corner_radius_mm": {
        "value": 4.0,
        "classification": "FROZEN",
        "source": "M3R_STAGE_B_PARAMETER_TABLE.yaml::B-002",
    },
    "stage_b_m6_clearance_hole_diameter_mm": {
        "value": 6.6,
        "classification": "FROZEN",
        "source": "M3R_STAGE_B_PARAMETER_TABLE.yaml::B-015",
    },
    "stage_b_m6_pattern_half_spacing_mm": {
        "value": 70.0,
        "classification": "FROZEN",
        "source": "M3R_STAGE_B_PARAMETER_TABLE.yaml::B-016 (centres at +/-70, +/-70)",
    },
    "stage_b_nominal_hole_edge_ligament_mm": {
        "value": 6.7,
        "classification": "DERIVED",
        "source": "M6_EXECUTION_PLAN_V1.md known engineering facts: 160/2 - 70 - 6.6/2",
        "note": "nominal geometry only, not a worst-case edge margin",
    },
    "stage_a_central_passage_diameter_mm": {
        "value": 40.0,
        "classification": "FROZEN",
        "source": "M3R_ADAPTER_INTERFACE_SSOT.yaml::stage_A_interface_ring.central_passage_diameter_mm "
        "and stage_B_load_spreading_adapter.stage_A_through_passage_diameter_mm",
    },
    # Load-bridge candidate design freedom (all CANDIDATE, digitally re-runnable).
    "bridge_x_span_mm": {
        "value": [185.25, 196.0],
        "classification": "CANDIDATE",
        "source": "DERIVED_FROM_STATIONS: bus face 185.25 to Stage B spacecraft-side face 208.0 - 12.0 = 196.0",
        "note": "spans the measured 10.75 mm minimum geometry gap; gap is evidence of the missing bridge, not an assembly pass",
    },
    "bridge_thickness_mm": {
        "value": 10.75,
        "classification": "CANDIDATE",
        "source": "DERIVED_FROM_STATIONS: 196.0 - 185.25",
    },
    "bridge_outline_square_width_mm": {
        "value": 160.0,
        "classification": "CANDIDATE",
        "source": "MATCHES Stage B base footprint (B-001) so hole-edge ligament equals Stage B nominal 6.7 mm",
    },
    "bridge_outline_corner_radius_mm": {
        "value": 4.0,
        "classification": "CANDIDATE",
        "source": "MATCHES Stage B corner radius (B-002)",
    },
    "bridge_outline_clocking": {
        "value": "PATTERN_ALIGNED_WITH_M3R_25P000014_DEG",
        "classification": "CANDIDATE",
        "source": "M3R clocking authority; outline rotates with the hole pattern",
    },
    "bridge_hole_diameter_mm": {
        "value": 6.6,
        "classification": "CANDIDATE",
        "source": "MATCHES Stage B M6 clearance diameter (B-015)",
    },
    "bridge_hole_count": {
        "value": 4,
        "classification": "CANDIDATE",
        "source": "MATCHES Stage B 4xM6 spacecraft primary pattern candidate",
    },
    "bridge_central_passage_diameter_mm": {
        "value": 40.0,
        "classification": "CANDIDATE",
        "source": "keeps the Stage A/B central 40 mm through channel open; void cannot create interference",
    },
    "material_candidate_id": {
        "value": "PMAT-AL6061-T6-SHEET-PLATE",
        "classification": "CANDIDATE",
        "source": "PROTOTYPE_MATERIAL_LIBRARY_V1.yaml::materials[material_id=PMAT-AL6061-T6-SHEET-PLATE]",
    },
    "material_density_estimate_kg_m3": {
        "value": 2700.0,
        "classification": "CANDIDATE",
        "source": "PROTOTYPE_MATERIAL_LIBRARY_V1.yaml PMAT-AL6061-T6-SHEET-PLATE density.estimate_kg_m3 "
        "(Kaiser Aluminum 6061 sheet/plate public PDF, retrieved 2026-08-21, not hash archived)",
        "note": "MATERIAL_DERIVED use only; candidate density is not a measurement",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def local_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def memory_snapshot() -> dict:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)))
    gib = float(1024**3)
    if not ok:
        return {
            "available_physical_gib": None,
            "total_physical_gib": None,
            "threshold_gib": MEMORY_THRESHOLD_GIB,
            "memory_gate_passed": False,
            "measurement_status": "UNAVAILABLE_FAIL_CLOSED",
        }
    return {
        "available_physical_gib": round(stat.ullAvailPhys / gib, 6),
        "total_physical_gib": round(stat.ullTotalPhys / gib, 6),
        "threshold_gib": MEMORY_THRESHOLD_GIB,
        "memory_gate_passed": (stat.ullAvailPhys / gib) >= MEMORY_THRESHOLD_GIB,
        "measurement_status": "MEASURED",
    }


def p(key: str):
    return PARAMS[key]["value"]


def t_s_m3r_local() -> list[list[float]]:
    """T_S_M3R_LOCAL from the M4 frame tree (rotation about +X_S by the
    as-built clocking, origin at the x=208.0 station with the as-built
    pattern-centre YZ offsets).  Recomputed from scalar authority and
    cross-checked against the frozen matrix digits below."""
    angle = math.radians(p("m3r_clocking_about_x_deg"))
    c, s = math.cos(angle), math.sin(angle)
    y0, z0 = p("m3r_pattern_center_yz_mm")
    x0 = p("x_station_physical_installation_face_mm")
    return [
        [0.0, 0.0, 1.0, x0],
        [s, c, 0.0, y0],
        [-c, s, 0.0, z0],
        [0.0, 0.0, 0.0, 1.0],
    ]


T_S_M3R_LOCAL_FRAME_TREE_ROWS = [
    [0.0, 0.0, 1.0, 208.0],
    [0.422618483193, 0.906307683772, 0.0, 0.015994151],
    [-0.906307683772, 0.422618483193, 0.0, -0.086366070],
    [0.0, 0.0, 0.0, 1.0],
]


def mat_vec(m: list[list[float]], v) -> list[float]:
    return [sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)]


def matrix_to_placement(matrix: list[list[float]]) -> App.Placement:
    fc = App.Matrix()
    fc.A11, fc.A12, fc.A13, fc.A14 = matrix[0]
    fc.A21, fc.A22, fc.A23, fc.A24 = matrix[1]
    fc.A31, fc.A32, fc.A33, fc.A34 = matrix[2]
    fc.A41, fc.A42, fc.A43, fc.A44 = matrix[3]
    return App.Placement(fc)


def rounded_square_wire(half: float, radius: float, z: float) -> Part.Wire:
    """CCW rounded square in the plane z=const, centred on the local origin."""
    a = half - radius
    zf = float(z)
    edges = []
    # right side, bottom-to-top
    edges.append(Part.makeLine(App.Vector(half, -a, zf), App.Vector(half, a, zf)))
    # top-right arc 0..90 deg about (a, a)
    edges.append(
        Part.ArcOfCircle(
            Part.Circle(App.Vector(a, a, zf), App.Vector(0, 0, 1), radius), 0.0, math.pi / 2.0
        ).toShape()
    )
    # top side, right-to-left
    edges.append(Part.makeLine(App.Vector(a, half, zf), App.Vector(-a, half, zf)))
    # top-left arc 90..180 deg about (-a, a)
    edges.append(
        Part.ArcOfCircle(
            Part.Circle(App.Vector(-a, a, zf), App.Vector(0, 0, 1), radius),
            math.pi / 2.0,
            math.pi,
        ).toShape()
    )
    # left side, top-to-bottom
    edges.append(Part.makeLine(App.Vector(-half, a, zf), App.Vector(-half, -a, zf)))
    # bottom-left arc 180..270 deg about (-a, -a)
    edges.append(
        Part.ArcOfCircle(
            Part.Circle(App.Vector(-a, -a, zf), App.Vector(0, 0, 1), radius),
            math.pi,
            3.0 * math.pi / 2.0,
        ).toShape()
    )
    # bottom side, left-to-right
    edges.append(Part.makeLine(App.Vector(-a, -half, zf), App.Vector(a, -half, zf)))
    # bottom-right arc 270..360 deg about (a, -a)
    edges.append(
        Part.ArcOfCircle(
            Part.Circle(App.Vector(a, -a, zf), App.Vector(0, 0, 1), radius),
            3.0 * math.pi / 2.0,
            2.0 * math.pi,
        ).toShape()
    )
    return Part.Wire(edges)


def build_bridge_shape_local() -> Part.Shape:
    """Bridge solid in LOAD_BRIDGE_LOCAL coordinates.

    LOAD_BRIDGE_LOCAL is coincident with M3R_LOCAL: same rotation about +X_S
    and the same as-built pattern-centre YZ offsets, so the bridge hole
    pattern is congruent with the Stage B 4xM6 pattern by construction.
    Local z = 0 maps to S x = 208.0; the bridge spans local z in
    [-22.75, -12.0] == S x in [185.25, 196.0].
    """
    x_lo, x_hi = p("bridge_x_span_mm")
    x_install = p("x_station_physical_installation_face_mm")
    z_lo = x_lo - x_install  # -22.75
    z_hi = x_hi - x_install  # -12.0
    thickness = z_hi - z_lo
    if abs(thickness - p("bridge_thickness_mm")) > 1e-12:
        raise RuntimeError("bridge thickness parameter inconsistent with x span")

    half = p("bridge_outline_square_width_mm") / 2.0
    radius = p("bridge_outline_corner_radius_mm")
    face = Part.Face(rounded_square_wire(half, radius, z_lo))
    solid = face.extrude(App.Vector(0, 0, thickness))

    cutters = []
    h = p("stage_b_m6_pattern_half_spacing_mm")
    r_hole = p("bridge_hole_diameter_mm") / 2.0
    for hx, hy in ((h, h), (h, -h), (-h, h), (-h, -h)):
        cutters.append(
            Part.makeCylinder(r_hole, thickness, App.Vector(hx, hy, z_lo), App.Vector(0, 0, 1))
        )
    r_center = p("bridge_central_passage_diameter_mm") / 2.0
    cutters.append(
        Part.makeCylinder(r_center, thickness, App.Vector(0.0, 0.0, z_lo), App.Vector(0, 0, 1))
    )
    solid = solid.cut(cutters)
    return solid.removeSplitter()


def analytic_profile_area_mm2() -> float:
    half = p("bridge_outline_square_width_mm") / 2.0
    radius = p("bridge_outline_corner_radius_mm")
    area = (2.0 * half) ** 2 - 4.0 * radius**2 * (1.0 - math.pi / 4.0)
    area -= p("bridge_hole_count") * math.pi * (p("bridge_hole_diameter_mm") / 2.0) ** 2
    area -= math.pi * (p("bridge_central_passage_diameter_mm") / 2.0) ** 2
    return area


def analytic_support_half_width_mm() -> float:
    """Support function of the rounded square along a unit direction, used for
    the rotated YZ bounding-box check (a + b == 1.328926166965... for the
    25.000014 deg clocking)."""
    half = p("bridge_outline_square_width_mm") / 2.0
    radius = p("bridge_outline_corner_radius_mm")
    angle = math.radians(p("m3r_clocking_about_x_deg"))
    s, c = abs(math.sin(angle)), abs(math.cos(angle))
    return (half - radius) * (s + c) + radius * math.hypot(s, c)


def shape_metrics(shape) -> dict:
    box = shape.BoundBox
    return {
        "shape_type": shape.ShapeType,
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "volume_mm3": round(float(shape.Volume), 9),
        "bounding_box_mm": [
            round(box.XMin, 9),
            round(box.YMin, 9),
            round(box.ZMin, 9),
            round(box.XMax, 9),
            round(box.YMax, 9),
            round(box.ZMax, 9),
        ],
    }


def cylindrical_face_audit(shape) -> list:
    """Audit cylindrical faces whose axis is parallel to the local z axis."""
    rows = []
    for face in shape.Faces:
        surface = face.Surface
        if surface.TypeId != "Part::GeomCylinder":
            continue
        axis = surface.Axis
        if abs(abs(axis.z) - 1.0) > 1e-9:
            continue
        center = surface.Center
        box = face.BoundBox
        rows.append(
            {
                "radius_mm": round(float(surface.Radius), 9),
                "axis": [round(float(axis.x), 9), round(float(axis.y), 9), round(float(axis.z), 9)],
                "center_xy_mm": [round(float(center.x), 9), round(float(center.y), 9)],
                "z_span_mm": [round(float(box.ZMin), 9), round(float(box.ZMax), 9)],
            }
        )
    rows.sort(key=lambda row: (row["radius_mm"], row["center_xy_mm"]))
    return rows


def load_shape_from_step(doc, path: Path):
    before = {obj.Name for obj in doc.Objects}
    Part.insert(str(path), doc.Name)
    doc.recompute()
    imported = [obj for obj in doc.Objects if obj.Name not in before]
    per_object = {}
    shapes = []
    for obj in imported:
        if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0:
            shapes.append(obj.Shape.copy())
            per_object[obj.Name] = {
                **shape_metrics(obj.Shape),
                "axial_cylindrical_faces_local": cylindrical_face_audit(obj.Shape),
            }
    if not shapes:
        raise RuntimeError(f"STEP contained no solid shape: {path}")
    compound = Part.makeCompound(shapes)
    for obj in reversed(imported):
        doc.removeObject(obj.Name)
    doc.recompute()
    return compound, per_object


def add_string(obj, name, value, group="M6_Traceability"):
    obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def add_string_list(obj, name, values, group="M6_Traceability"):
    obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, [str(value) for value in values])


def set_visibility(obj, visible: bool) -> None:
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.Visibility = bool(visible)


def main() -> None:
    memory_start = memory_snapshot()
    required_sources = [
        M3R_STEP,
        M3R_PHYSICAL_STACK,
        M3R_ADAPTER_SSOT,
        M3R_STAGE_B_TABLE,
        M4_FRAME_TREE,
        M4_MATERIAL_LIBRARY,
        MODEL_SPECS,
        M6_BOUNDARY,
        Path(OWNER_OVERRIDE_SOURCE),
    ]
    missing = [str(path) for path in required_sources if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing required source(s): {missing}")
    source_register = [
        {
            "path": path.relative_to(PROJECT_ROOT).as_posix()
            if path.is_relative_to(PROJECT_ROOT)
            else str(path).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "status": "HASH_BOUND_AT_WP1_BUILD_READ_ONLY",
        }
        for path in required_sources
    ]

    # Bus proxy +X face from the geometry SSOT JSON (read-only).
    specs = json.loads(MODEL_SPECS.read_text(encoding="utf-8"))
    servicer = next(rec["spec"] for rec in specs if rec.get("key") == "servicer_12U_v0")
    bus_primitives = [
        prim
        for prim in servicer["primitives"]
        if prim.get("role") not in ("solar_panel_left", "solar_panel_right", "camera_payload")
    ]
    bus_max_x_mm = None
    legacy_flange_extent_mm = None
    for prim in bus_primitives:
        dims = prim["dims_mm"]
        center = prim["center_offset_mm"]
        if prim["shape"] == "box":
            xmax = center[0] + dims["length_x"] / 2.0
            bus_max_x_mm = xmax if bus_max_x_mm is None else max(bus_max_x_mm, xmax)
            if prim.get("role") == "flange":
                legacy_flange_extent_mm = [center[0] - dims["length_x"] / 2.0, xmax]
    if bus_max_x_mm is None or legacy_flange_extent_mm is None:
        raise RuntimeError("servicer_12U_v0 bus primitives did not yield +X face and flange extent")

    t_bridge = t_s_m3r_local()
    frame_tree_residual = max(
        abs(t_bridge[i][j] - T_S_M3R_LOCAL_FRAME_TREE_ROWS[i][j])
        for i in range(4)
        for j in range(4)
    )

    # Build the candidate bridge solid in local coordinates, then place in S.
    bridge_local = build_bridge_shape_local()
    bridge_s = bridge_local.copy()
    bridge_s.Placement = matrix_to_placement(t_bridge)

    # Read-only M3R working B-rep, placed exactly as in M4 (T_S_M3R_LOCAL).
    import_doc = App.newDocument("WP1_M3R_READONLY_IMPORT")
    try:
        m3r_local, m3r_per_object = load_shape_from_step(import_doc, M3R_STEP)
    finally:
        App.closeDocument(import_doc.Name)
    m3r_s = m3r_local.copy()
    m3r_s.Placement = matrix_to_placement(t_bridge)

    # Nominal contact relations (default-configuration geometry only).
    distance_bridge_m3r = float(bridge_s.distToShape(m3r_s)[0])
    common_bridge_m3r_mm3 = float(bridge_s.common(m3r_s).Volume)

    # Hole positions in S (analytic transform of the four local centres at the
    # M3R mate plane local z=-12).
    h = p("stage_b_m6_pattern_half_spacing_mm")
    hole_local = [(h, h), (h, -h), (-h, h), (-h, -h)]
    z_mate_local = p("bridge_x_span_mm")[1] - p("x_station_physical_installation_face_mm")
    hole_s_positions = [
        mat_vec(t_bridge, (hx, hy, z_mate_local)) for hx, hy in hole_local
    ]
    hole_s_axes = [[round(t_bridge[i][2], 12) for i in range(3)] for _ in hole_local]

    # Measured bridge holes from the placed B-rep (S frame): cylindrical faces
    # of the M6 radius whose axis is parallel to +X_S.  The OCCT cylindrical
    # Surface.Center sits at one axial end of the face, so the axis position is
    # compared in the YZ plane and the through condition is proven by the face
    # bounding box spanning the full bridge thickness.
    measured_holes_s = []
    for face in bridge_s.Faces:
        surface = face.Surface
        if surface.TypeId != "Part::GeomCylinder":
            continue
        if abs(float(surface.Radius) - p("bridge_hole_diameter_mm") / 2.0) > 1e-6:
            continue
        center = surface.Center
        fbox = face.BoundBox
        measured_holes_s.append(
            {
                "center_S_mm": [
                    round(float(center.x), 9),
                    round(float(center.y), 9),
                    round(float(center.z), 9),
                ],
                "face_x_span_mm": [round(float(fbox.XMin), 9), round(float(fbox.XMax), 9)],
            }
        )
    measured_holes_s.sort(key=lambda row: (row["center_S_mm"][1], row["center_S_mm"][2]))
    analytic_holes_s = sorted(hole_s_positions, key=lambda row: (row[1], row[2]))
    hole_position_max_abs_dev_mm = None
    if len(measured_holes_s) == len(analytic_holes_s):
        hole_position_max_abs_dev_mm = max(
            abs(measured_holes_s[k]["center_S_mm"][i] - analytic_holes_s[k][i])
            for k in range(len(analytic_holes_s))
            for i in (1, 2)
        )
    holes_span_full_thickness = len(measured_holes_s) == 4 and all(
        abs(row["face_x_span_mm"][0] - p("bridge_x_span_mm")[0]) <= 1e-9
        and abs(row["face_x_span_mm"][1] - p("bridge_x_span_mm")[1]) <= 1e-9
        for row in measured_holes_s
    )

    bridge_metrics = shape_metrics(bridge_s)
    expected_support = analytic_support_half_width_mm()
    y0, z0 = p("m3r_pattern_center_yz_mm")
    analytic_volume_mm3 = analytic_profile_area_mm2() * p("bridge_thickness_mm")
    volume_rel_err = abs(bridge_metrics["volume_mm3"] - analytic_volume_mm3) / analytic_volume_mm3
    density_kg_m3 = p("material_density_estimate_kg_m3")
    material_derived_mass_kg = bridge_metrics["volume_mm3"] * 1.0e-9 * density_kg_m3

    ligament_mm = (
        p("bridge_outline_square_width_mm") / 2.0
        - p("stage_b_m6_pattern_half_spacing_mm")
        - p("bridge_hole_diameter_mm") / 2.0
    )

    checks = {
        "bridge_solid_valid": bridge_metrics["valid"] and bridge_metrics["solids"] == 1,
        "bridge_x_span_matches_stations": abs(bridge_metrics["bounding_box_mm"][0] - p("bridge_x_span_mm")[0]) <= 1e-9
        and abs(bridge_metrics["bounding_box_mm"][3] - p("bridge_x_span_mm")[1]) <= 1e-9,
        "bridge_span_equals_10p75_gap": abs(
            (bridge_metrics["bounding_box_mm"][3] - bridge_metrics["bounding_box_mm"][0])
            - p("bridge_thickness_mm")
        )
        <= 1e-9,
        "bridge_yz_bbox_matches_clocked_rounded_square": (
            abs(bridge_metrics["bounding_box_mm"][1] - (y0 - expected_support)) <= 1e-6
            and abs(bridge_metrics["bounding_box_mm"][4] - (y0 + expected_support)) <= 1e-6
            and abs(bridge_metrics["bounding_box_mm"][2] - (z0 - expected_support)) <= 1e-6
            and abs(bridge_metrics["bounding_box_mm"][5] - (z0 + expected_support)) <= 1e-6
        ),
        "bridge_volume_matches_analytic": volume_rel_err <= 1e-9,
        "four_m6_holes_present_through": len(measured_holes_s) == 4 and holes_span_full_thickness,
        "hole_positions_match_analytic_transform": hole_position_max_abs_dev_mm is not None
        and hole_position_max_abs_dev_mm <= 1e-9,
        "hole_axes_parallel_to_plus_x_s": all(
            abs(axis[0] - 1.0) <= 1e-12 and abs(axis[1]) <= 1e-12 and abs(axis[2]) <= 1e-12
            for axis in hole_s_axes
        ),
        "nominal_hole_edge_ligament_equals_6p7": abs(ligament_mm - 6.7) <= 1e-12,
        "m3r_volume_matches_m3_receipt": abs(float(m3r_local.Volume) - 289750.832561) <= 1.0e-6,
        "m3r_min_x_matches_196_station": abs(shape_metrics(m3r_s)["bounding_box_mm"][0] - 196.0) <= 1e-9,
        "bridge_m3r_nominal_face_contact_zero_distance": distance_bridge_m3r <= 1e-7,
        "bridge_m3r_no_positive_common_volume": common_bridge_m3r_mm3 <= 1e-6,
        "bus_proxy_plus_x_face_equals_185p25": abs(bus_max_x_mm - p("x_station_m_frame_mm")) <= 1e-9,
        "legacy_flange_extent_unchanged_reference": abs(legacy_flange_extent_mm[0] - 170.25) <= 1e-9
        and abs(legacy_flange_extent_mm[1] - 185.25) <= 1e-9,
        "bridge_does_not_enter_legacy_flange_x_interval": bridge_metrics["bounding_box_mm"][0]
        >= legacy_flange_extent_mm[1] - 1e-12,
        "t_s_m3r_local_matches_frame_tree_frozen_rows": frame_tree_residual <= 1e-9,
    }

    # ---- FCStd master (lightweight, embedded copies, no external refs) ----
    doc = App.newDocument("LOAD_BRIDGE_CANDIDATE_V1")
    top = doc.addObject("App::Part", "LOAD_BRIDGE_CANDIDATE_V1")
    top.Label = "LOAD_BRIDGE_CANDIDATE_V1"
    add_string(top, "LifecycleStatus", "M6_CANDIDATE_GEOMETRY_NOT_AUTHORITY_NOT_RELEASED")
    add_string(top, "LengthUnit", "mm")
    add_string(top, "FormalFEA", "NOT_PERFORMED_NOT_AUTHORIZED")
    add_string(top, "MassUse", "MATERIAL_DERIVED_CANDIDATE_ONLY_NOT_MEASURED_NOT_BUDGET")
    add_string_list(
        top,
        "ExplicitNonClaims",
        [
            "NOT_MANUFACTURING_RELEASED",
            "NOT_FLIGHT_OR_LAUNCH_QUALIFIED",
            "NOT_AN_ASSEMBLY_PASS_OR_FITUP_RESULT",
            "NOT_SYSTEM_MASS_OR_INERTIA_AUTHORITY",
            "LEGACY_FLANGE_X_170P25_TO_185P25_NOT_MERGED_OWNERSHIP_UNRESOLVED",
            "CANDIDATE_NOT_EQUAL_AUTHORITY",
        ],
    )

    bridge_obj = doc.addObject("Part::Feature", "LOAD_BRIDGE_PLATE_CANDIDATE")
    bridge_obj.Label = "LOAD_BRIDGE_PLATE_CANDIDATE__SPANS_X_185P25_TO_196P00"
    bridge_obj.Shape = bridge_s
    add_string(bridge_obj, "SourcePath", "wp1_load_bridge/build_load_bridge_candidate.py")
    add_string(bridge_obj, "GeometryClass", "CANDIDATE_PARAMETERIZED_BREP_MM")
    add_string(bridge_obj, "LifecycleStatus", "CANDIDATE_NOT_RELEASED")
    add_string(
        bridge_obj,
        "PlacementBasis",
        "T_S_LOAD_BRIDGE_LOCAL == T_S_M3R_LOCAL (DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml); local z in [-22.75, -12.0]",
    )
    add_string_list(
        bridge_obj,
        "Holds",
        [
            "LOAD_BRIDGE_PHYSICAL_FITUP_HOLD",
            "MATING_FASTENER_AND_TOLERANCE_HOLD",
            "M6_PATTERN_POSITION_TOLERANCE_HOLD",
            "SURFACE_SPECIFICATION_HOLD",
            "SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD",
            "MATERIAL_APPROVAL_AND_PROCESS_HOLD",
            "AUTHORIZED_LOADS_HOLD",
        ],
    )
    top.addObject(bridge_obj)

    ref_m3r = doc.addObject("Part::Feature", "REF_M3R_INTERFACE_ASSEMBLY_READONLY")
    ref_m3r.Label = "REF_M3R_INTERFACE_ASSEMBLY__READONLY_FITUP_REFERENCE"
    ref_m3r.Shape = m3r_s
    add_string(ref_m3r, "SourcePath", M3R_STEP.relative_to(PROJECT_ROOT).as_posix())
    add_string(ref_m3r, "GeometryClass", "READONLY_HASH_PINNED_FITUP_REFERENCE")
    add_string(ref_m3r, "LifecycleStatus", "WORKING_DETAILED_DESIGN_NOT_RELEASED")
    top.addObject(ref_m3r)
    set_visibility(ref_m3r, False)

    datum_obj = doc.addObject("App::FeaturePython", "DATUM_REGISTER")
    datum_obj.Label = "DATUM_REGISTER__CANDIDATE_TEXT_SUMMARY"
    add_string(datum_obj, "DatumBusFace", "PLANE_S_X_185P25__D_BRIDGE_BUS")
    add_string(datum_obj, "DatumM3RMate", "PLANE_S_X_196P00__D_BRIDGE_M3R_STAGE_B_BOTTOM")
    add_string(
        datum_obj,
        "HolePattern",
        "4x dia 6.6 through at local (+/-70, +/-70); clocked 25.000014 deg about +X_S; centre YZ (0.015994151, -0.086366070)",
    )
    add_string(datum_obj, "CentralPassage", "dia 40.0 through, aligned with Stage A/B central passage")
    add_string_list(
        datum_obj,
        "FitCandidates",
        [
            "BRIDGE_HOLE_6P6_H11_CANDIDATE_FIT",
            "M6_FASTENER_SHAFT_H9_CANDIDATE_FIT",
            "FACE_PAIR_FLATNESS_NULL_HOLD",
            "PATTERN_POSITION_TOLERANCE_NULL_HOLD",
        ],
    )
    top.addObject(datum_obj)

    doc.recompute()
    staged = OUTPUT_FCSTD.with_name(OUTPUT_FCSTD.stem + ".new.FCStd")
    if staged.exists():
        staged.unlink()
    doc.saveAs(str(staged))
    Part.export([bridge_obj], str(OUTPUT_STEP))
    App.closeDocument(doc.Name)
    os.replace(staged, OUTPUT_FCSTD)

    # Cold reopen of both artifacts (read-only validation).
    reopened = App.openDocument(str(OUTPUT_FCSTD))
    try:
        reopen_shapes = [
            obj
            for obj in reopened.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull()
        ]
        fcstd_reopen = {
            "object_count": len(reopened.Objects),
            "shape_object_count": len(reopen_shapes),
            "all_shapes_valid": all(obj.Shape.isValid() for obj in reopen_shapes),
            "object_names": sorted(obj.Name for obj in reopened.Objects),
        }
    finally:
        App.closeDocument(reopened.Name)
    checks["fcstd_cold_reopen_valid"] = fcstd_reopen["all_shapes_valid"]

    step_doc = App.newDocument("WP1_STEP_REOPEN")
    try:
        Part.insert(str(OUTPUT_STEP), step_doc.Name)
        step_doc.recompute()
        step_shapes = [
            obj.Shape
            for obj in step_doc.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
        ]
        step_compound = Part.makeCompound(step_shapes)
        step_metrics = shape_metrics(step_compound)
        step_reopen = {
            "object_count": len(step_doc.Objects),
            "shape_object_count": len(step_shapes),
            **step_metrics,
        }
    finally:
        App.closeDocument(step_doc.Name)
    checks["step_cold_reopen_valid"] = step_reopen["valid"] and step_reopen["solids"] == 1
    checks["step_reopen_volume_matches_build"] = (
        abs(step_reopen["volume_mm3"] - bridge_metrics["volume_mm3"]) <= 1e-6
    )
    checks["step_reopen_bbox_matches_build"] = step_reopen["bounding_box_mm"] == bridge_metrics[
        "bounding_box_mm"
    ]

    memory_end = memory_snapshot()
    verdict = (
        "PASS_CANDIDATE_BUILD_WITH_EXPLICIT_HOLDS"
        if all(checks.values())
        else "HOLD_CANDIDATE_BUILD_CHECK_FAILURE"
    )

    payload = {
        "schema": "LOAD_BRIDGE_BUILD_RUN_V1",
        "generated_local": local_now(),
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP1_LOAD_BRIDGE_CAD",
        "lifecycle_status": "CANDIDATE_GEOMETRY_ONLY_NOT_AUTHORITY_NOT_RELEASED",
        "builder": {
            "tool": "FreeCADCmd / OpenCascade",
            "freecad_version": ".".join(App.Version()[:3]) + "R" + App.Version()[3],
            "command": "G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe wp1_load_bridge/build_load_bridge_candidate.py",
            "execution_mode": "SINGLE_FREECAD_PROCESS_WP1_EXCLUSIVE",
        },
        "memory_gate": {
            "at_build_start": memory_start,
            "at_build_end": memory_end,
            "threshold_gib": MEMORY_THRESHOLD_GIB,
            "memory_gate_passed": memory_start["memory_gate_passed"]
            and memory_end["memory_gate_passed"],
        },
        "owner_override": {
            "required": not memory_start["memory_gate_passed"],
            "used": not memory_start["memory_gate_passed"],
            "class": "BOUNDED_SERIAL_FREECADCMD_SINGLE_LIGHTWEIGHT_PARAMETERIZED_BREP",
            "source": OWNER_OVERRIDE_SOURCE,
            "source_sha256": sha256(Path(OWNER_OVERRIDE_SOURCE)),
            "m4_register_reference": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/00_authority/M4_OWNER_OVERRIDE_REGISTER_V1.csv::M4-OVR-001",
            "controls": [
                "SINGLE_FREECAD_PROCESS",
                "LIGHTWEIGHT_PARAMETERIZED_BREP_ONLY",
                "NO_VENDOR_252MB_STEP_IMPORT",
                "NO_FEA",
                "READ_ONLY_USE_OF_HASH_PINNED_INPUTS",
            ],
        },
        "bom_item_closed_at_candidate_layer": {
            "item_id": "DP-007",
            "assembly_item": "spacecraft to M3R load bridge",
            "m4_status": "HARD_HOLD (absent, no authorized geometry)",
            "m6_candidate_status": "CANDIDATE_GEOMETRY_PRESENT_AUTHORITY_HOLD_PRESERVED",
        },
        "parameters": PARAMS,
        "frame": {
            "name": "LOAD_BRIDGE_LOCAL",
            "definition": "COINCIDENT_WITH_M3R_LOCAL",
            "T_S_LOAD_BRIDGE_LOCAL_rows": [[round(v, 12) for v in row] for row in t_bridge],
            "T_S_M3R_LOCAL_frame_tree_rows": T_S_M3R_LOCAL_FRAME_TREE_ROWS,
            "frame_tree_recompute_max_abs_residual": frame_tree_residual,
            "local_z_range_mm": [
                p("bridge_x_span_mm")[0] - p("x_station_physical_installation_face_mm"),
                p("bridge_x_span_mm")[1] - p("x_station_physical_installation_face_mm"),
            ],
        },
        "bus_reference": {
            "bus_proxy_plus_x_face_x_mm": bus_max_x_mm,
            "legacy_flange_x_extent_mm": legacy_flange_extent_mm,
            "legacy_flange_role": "SOURCE_PROXY_PRIMITIVE_ONLY_OWNERSHIP_UNRESOLVED_NOT_MERGED",
            "source": "model_specs_v0.json::servicer_12U_v0.primitives",
        },
        "bridge_geometry": {
            "metrics_S_frame": bridge_metrics,
            "analytic_volume_mm3": round(analytic_volume_mm3, 9),
            "volume_relative_error_vs_analytic": volume_rel_err,
            "nominal_hole_edge_ligament_mm": ligament_mm,
            "hole_centres_local_xy_mm": [list(row) for row in hole_local],
            "hole_centres_S_at_mate_plane_mm": [
                [round(v, 9) for v in row] for row in hole_s_positions
            ],
            "hole_axes_S": hole_s_axes,
            "measured_m6_hole_faces_S": measured_holes_s,
            "hole_position_max_abs_dev_mm": hole_position_max_abs_dev_mm,
        },
        "m3r_readonly_reference": {
            "metrics_local": shape_metrics(m3r_local),
            "metrics_S_frame": shape_metrics(m3r_s),
            "per_object_detail_local": m3r_per_object,
        },
        "nominal_contact_relations": {
            "bridge_vs_m3r": {
                "minimum_distance_mm": round(distance_bridge_m3r, 9),
                "common_volume_mm3": round(common_bridge_m3r_mm3, 9),
                "classification": "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME"
                if distance_bridge_m3r <= 1e-7 and common_bridge_m3r_mm3 <= 1e-6
                else "UNEXPECTED_GAP_OR_OVERLAP_HOLD",
                "acceptance_scope": "NOMINAL_DEFAULT_CONFIGURATION_GEOMETRY_ONLY_NOT_A_FITUP_RESULT",
            },
            "bridge_vs_bus_proxy_face": {
                "bus_face_x_mm": bus_max_x_mm,
                "bridge_min_x_mm": bridge_metrics["bounding_box_mm"][0],
                "classification": "PLANAR_ABUTMENT_NOMINAL_BY_CONSTRUCTION"
                if abs(bridge_metrics["bounding_box_mm"][0] - bus_max_x_mm) <= 1e-9
                else "UNEXPECTED_GAP_OR_OVERLAP_HOLD",
            },
        },
        "material_derived_mass_candidate": {
            "classification": "MATERIAL_DERIVED",
            "active": False,
            "measured": False,
            "installed": False,
            "volume_mm3": bridge_metrics["volume_mm3"],
            "density_estimate_kg_m3": density_kg_m3,
            "density_source": "PROTOTYPE_MATERIAL_LIBRARY_V1.yaml::PMAT-AL6061-T6-SHEET-PLATE",
            "mass_kg": round(material_derived_mass_kg, 9),
            "mass_g": round(material_derived_mass_kg * 1000.0, 6),
            "limitations": [
                "CANDIDATE_DENSITY_NOT_HARDWARE_MASS",
                "EXCLUDED_FROM_M3R_BUDGET_0P7619_KG (mating spacecraft structure per M3R_MASS_RULING.json)",
                "NEVER_OVERRIDES_L0_URDF_MASSES",
                "LEGACY_FLANGE_NOT_INCLUDED",
            ],
        },
        "checks": checks,
        "fcstd_cold_reopen": fcstd_reopen,
        "step_cold_reopen": step_reopen,
        "formal_fea_performed": False,
        "physical_fitup_performed": False,
        "source_register": source_register,
        "outputs": [
            {
                "path": path.relative_to(M6_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in (OUTPUT_FCSTD, OUTPUT_STEP)
        ],
        "verdict": verdict,
    }
    BUILD_RUN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": verdict,
                "fcstd": str(OUTPUT_FCSTD),
                "step": str(OUTPUT_STEP),
                "build_run": str(BUILD_RUN),
                "memory_gate": payload["memory_gate"],
            },
            ensure_ascii=False,
        )
    )


main()
