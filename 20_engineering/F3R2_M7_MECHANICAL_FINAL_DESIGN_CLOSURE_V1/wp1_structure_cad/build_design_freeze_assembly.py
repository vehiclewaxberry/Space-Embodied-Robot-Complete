# -*- coding: utf-8 -*-
"""Build the M7 WP1 design-freeze assembly (product structure freeze, CAD part).

Architecture and controls follow M4_BUILD_DIGITAL_PROTOTYPE_V1.py:
embedded Part::Feature sources + internal App::Link instances, single
FreeCADCmd process, lightweight parameterized B-rep only, no FEA, no vendor
252 MB STEP import.  The M6 WP1 load-bridge candidate
(LOAD_BRIDGE_CANDIDATE_V1.step, authored directly in frame S at
x in [185.25, 196.0]) is integrated as the design piece that fills the former
SLOT_SPACECRAFT_LOAD_BRIDGE__UNRESOLVED (BOM DP-007).

B601 is installed as the frame/axis witness only (arm geometry rebuild is
forbidden).  The legacy flange (x 170.25..185.25, 140x140 mm) stays inside the
bus proxy as a TAGGED_REFERENCE per ODR-01 semantics and is never merged into
the load bridge.

Camera relocation candidate solids (CAM_A/CAM_B + bracket stubs) are built as
hidden candidate geometry.  They are measured against the installed M3R B-rep
(minimum distance / common volume) to provide the numeric clearance evidence
required for the relocation candidates.  They are NOT exported into the
design-freeze STEP.

Run with FreeCADCmd.  Length units are millimetres throughout this file.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import FreeCAD as App
import Part


HERE = Path(__file__).resolve().parent
M7_ROOT = HERE.parent
PROJECT_ROOT = M7_ROOT.parents[1]
M4_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
M3_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DETAILED_DESIGN_V1"
M3_TERMINAL_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
V5R_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
M6_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
CAD_ROOT = PROJECT_ROOT / "20_engineering" / "cad"

OUTPUT_FCSTD = HERE / "DESIGN_FREEZE_ASSEMBLY_V1.FCStd"
OUTPUT_STEP = HERE / "DESIGN_FREEZE_ASSEMBLY_V1.step"
BUILD_REPORT = HERE / "DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json"

MODEL_SPECS = CAD_ROOT / "spacecraft_layout" / "model_specs_v0.json"
FRAME_TREE = PROJECT_ROOT / "20_engineering" / "config" / "geometry" / "frame_tree_v1.yaml"
M4_FRAME_TREE = M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
SERVICE_SPACECRAFT_GEOM = PROJECT_ROOT / "20_engineering" / "config" / "geometry" / "service_spacecraft_v1.yaml"
V5R_FRAME_TREE = V5R_ROOT / "02_interfaces" / "SYSTEM_FRAME_TREE.yaml"
URDF = CAD_ROOT / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"
FREECAD_AUTH = CAD_ROOT / "freecad_authoritative"
B601_Q0_WITNESS = FREECAD_AUTH / "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step"
M3R_STEP = M3_ROOT / "06_parameterized_parts" / "m3r" / "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step"
M3R_PHYSICAL_STACK = (
    M3_TERMINAL_ROOT
    / "03_native_cad"
    / "M3_interface_authority"
    / "M3R_TSM_PHYSICAL_STACK.yaml"
)
GRIPPER_R1_STEP = V5R_ROOT / "01_native_cad" / "gripper_r1" / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step"
GRIPPER_LEFT_RAIL_SWEPT = V5R_ROOT / "01_native_cad" / "gripper_r1" / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"
GRIPPER_RIGHT_RAIL_SWEPT = V5R_ROOT / "01_native_cad" / "gripper_r1" / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"
LOAD_BRIDGE_STEP = M6_ROOT / "wp1_load_bridge" / "LOAD_BRIDGE_CANDIDATE_V1.step"
LOAD_BRIDGE_DATUMS = M6_ROOT / "wp1_load_bridge" / "LOAD_BRIDGE_DATUMS_V1.yaml"
LOAD_BRIDGE_FITUP = M6_ROOT / "wp1_load_bridge" / "FITUP_AND_FRAME_RECEIPT_V1.json"
SUPPORT_V2_DEF = M3_TERMINAL_ROOT / "06_supports" / "F3R2_SUPPORT_V2_DEFINITION.json"
G4_DEF = M3_TERMINAL_ROOT / "07_hdrm" / "F3R2_ARM_HDRM_DEFINITION.json"
M7_ODR = M7_ROOT / "00_authority" / "M7_OWNER_DECISION_REGISTER_V1.yaml"
M7_PLAN = M7_ROOT / "00_authority" / "M7_EXECUTION_PLAN_V1.md"

MEMORY_THRESHOLD_GIB = 6.0
OWNER_OVERRIDE_SOURCE = (
    "C:/Users/stude/.codex/attachments/038d9781-5921-4858-9fea-c070890a71b8/pasted-text.txt"
)
M4_OVERRIDE_REGISTER = (
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/00_authority/"
    "M4_OWNER_OVERRIDE_REGISTER_V1.csv::M4-OVR-001"
)

# Camera relocation candidate envelopes (evidence solids, never exported).
# CAM_A: front-face upper-corner bracket position, same camera-class envelope
# as the rejected M4 placeholder (cylinder r=25, L=40, axis +X).
CAM_A_CENTER = (190.25, -35.0, 145.0)
CAM_A_RADIUS = 25.0
CAM_A_LENGTH = 40.0
# CAM_A bracket stub: deck-mounted riser + forward arm reaching the camera.
BRK_A_BOXES = [
    # (xmin, ymin, zmin, xmax, ymax, zmax) in S, mm
    (165.0, -55.0, 113.15, 170.25, -40.0, 130.0),   # riser off the top deck
    (165.0, -55.0, 120.0, 195.0, -40.0, 130.0),     # forward arm under the camera
]
# CAM_B: deck-flush position forward on the top deck, -Y side.
CAM_B_CENTER = (150.0, -60.0, 143.15)
CAM_B_RADIUS = 25.0
CAM_B_LENGTH = 40.0
BRK_B_BOXES = [
    (135.0, -75.0, 113.15, 165.0, -45.0, 118.15),   # 5 mm base plate on the deck
]


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
    if not ok:
        return {
            "available_physical_gib": None,
            "total_physical_gib": None,
            "threshold_gib": MEMORY_THRESHOLD_GIB,
            "memory_gate_passed": False,
            "measurement_status": "UNAVAILABLE_FAIL_CLOSED",
        }
    gib = float(1024**3)
    available = stat.ullAvailPhys / gib
    total = stat.ullTotalPhys / gib
    return {
        "available_physical_gib": round(available, 6),
        "total_physical_gib": round(total, 6),
        "threshold_gib": MEMORY_THRESHOLD_GIB,
        "memory_gate_passed": available >= MEMORY_THRESHOLD_GIB,
        "measurement_status": "MEASURED",
    }


def mat_identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform_xyz_rpy_mm(xyz_m, rpy) -> list[list[float]]:
    roll, pitch, yaw = [float(value) for value in rpy]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    matrix = mat_identity()
    matrix[0][0] = cy * cp
    matrix[0][1] = cy * sp * sr - sy * cr
    matrix[0][2] = cy * sp * cr + sy * sr
    matrix[1][0] = sy * cp
    matrix[1][1] = sy * sp * sr + cy * cr
    matrix[1][2] = sy * sp * cr - cy * sr
    matrix[2][0] = -sp
    matrix[2][1] = cp * sr
    matrix[2][2] = cp * cr
    matrix[0][3] = 1000.0 * float(xyz_m[0])
    matrix[1][3] = 1000.0 * float(xyz_m[1])
    matrix[2][3] = 1000.0 * float(xyz_m[2])
    return matrix


def matrix_to_placement(matrix) -> App.Placement:
    fc = App.Matrix()
    fc.A11, fc.A12, fc.A13, fc.A14 = matrix[0]
    fc.A21, fc.A22, fc.A23, fc.A24 = matrix[1]
    fc.A31, fc.A32, fc.A33, fc.A34 = matrix[2]
    fc.A41, fc.A42, fc.A43, fc.A44 = matrix[3]
    return App.Placement(fc)


def clean_matrix(matrix):
    return [[round(value, 12) for value in row] for row in matrix]


def arm_base_matrix(translation=(208.0, 0.0, 0.0)) -> list[list[float]]:
    # Frozen V5R physical arm-base map: Ry(+90 deg) * Rz(+25.000014 deg).
    angle = math.radians(25.000014)
    c, s = math.cos(angle), math.sin(angle)
    return [
        [0.0, 0.0, 1.0, float(translation[0])],
        [s, c, 0.0, float(translation[1])],
        [-c, s, 0.0, float(translation[2])],
        [0.0, 0.0, 0.0, 1.0],
    ]


def parse_q0_chain() -> dict[str, list[list[float]]]:
    root = ET.parse(URDF).getroot()
    joints = {}
    for joint in root.findall("joint"):
        parent = joint.find("parent").attrib["link"]
        child = joint.find("child").attrib["link"]
        origin = joint.find("origin")
        xyz = [float(v) for v in origin.attrib.get("xyz", "0 0 0").split()]
        rpy = [float(v) for v in origin.attrib.get("rpy", "0 0 0").split()]
        joints[child] = {"parent": parent, "transform": transform_xyz_rpy_mm(xyz, rpy)}

    transforms = {"base_link": mat_identity()}
    unresolved = dict(joints)
    while unresolved:
        progress = False
        for child, definition in list(unresolved.items()):
            parent = definition["parent"]
            if parent not in transforms:
                continue
            transforms[child] = mat_mul(transforms[parent], definition["transform"])
            del unresolved[child]
            progress = True
        if not progress:
            raise RuntimeError(f"URDF frame tree cannot be resolved: {sorted(unresolved)}")
    return transforms


def load_shape_from_step(doc, path: Path):
    before = {obj.Name for obj in doc.Objects}
    Part.insert(str(path), doc.Name)
    doc.recompute()
    imported = [obj for obj in doc.Objects if obj.Name not in before]
    shapes = [
        obj.Shape.copy()
        for obj in imported
        if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
    ]
    if not shapes:
        raise RuntimeError(f"STEP contained no solid shape: {path}")
    compound = Part.makeCompound(shapes)
    for obj in reversed(imported):
        doc.removeObject(obj.Name)
    doc.recompute()
    return compound


def centered_box(lx, ly, lz, cx, cy, cz):
    return Part.makeBox(
        float(lx), float(ly), float(lz),
        App.Vector(float(cx) - float(lx) / 2.0, float(cy) - float(ly) / 2.0, float(cz) - float(lz) / 2.0),
    )


def bbox_box(xmin, ymin, zmin, xmax, ymax, zmax):
    return Part.makeBox(
        float(xmax - xmin), float(ymax - ymin), float(zmax - zmin),
        App.Vector(float(xmin), float(ymin), float(zmin)),
    )


def centered_cylinder_x(radius, length, cx, cy, cz):
    radius, length = float(radius), float(length)
    return Part.makeCylinder(
        radius, length,
        App.Vector(float(cx) - length / 2.0, float(cy), float(cz)),
        App.Vector(1, 0, 0),
    )


def load_model_spec(key: str) -> dict:
    data = json.loads(MODEL_SPECS.read_text(encoding="utf-8"))
    for record in data:
        if record.get("key") == key:
            return record["spec"]
    raise RuntimeError(f"{key} missing from model_specs_v0.json")


def build_servicer_shapes(spec: dict) -> dict:
    bus_shapes = []
    panels = {}
    sensor = None
    for primitive in spec["primitives"]:
        role = primitive["role"]
        dims = primitive["dims_mm"]
        center = primitive["center_offset_mm"]
        if primitive["shape"] == "box":
            shape = centered_box(dims["length_x"], dims["width_y"], dims["height_z"], *center)
        elif primitive["shape"] == "cylinder":
            shape = centered_cylinder_x(dims["radius"], dims["cyl_length"], *center) \
                if dims.get("axis") == "x" else None
            if shape is None:
                # z-axis cylinder (antenna placeholder)
                r, length = float(dims["radius"]), float(dims["cyl_length"])
                shape = Part.makeCylinder(
                    r, length,
                    App.Vector(center[0], center[1], center[2] - length / 2.0),
                    App.Vector(0, 0, 1),
                )
        else:
            raise RuntimeError(f"unknown primitive type: {primitive['shape']}")

        if role == "solar_panel_left":
            panels["left"] = shape
        elif role == "solar_panel_right":
            panels["right"] = shape
        elif role == "camera_payload":
            sensor = shape
        else:
            bus_shapes.append(shape)
    if set(panels) != {"left", "right"} or sensor is None:
        raise RuntimeError("servicer split did not find both panels and sensor")
    return {
        "bus": Part.makeCompound(bus_shapes),
        "panel_left": panels["left"],
        "panel_right": panels["right"],
        "sensor": sensor,
    }


def shape_metrics(shape) -> dict:
    box = shape.BoundBox
    return {
        "shape_type": shape.ShapeType,
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "volume_mm3": round(float(shape.Volume), 9),
        "bounding_box_mm": [
            round(box.XMin, 9), round(box.YMin, 9), round(box.ZMin, 9),
            round(box.XMax, 9), round(box.YMax, 9), round(box.ZMax, 9),
        ],
    }


def add_string(obj, name, value, group="M7_Traceability"):
    obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def add_string_list(obj, name, values, group="M7_Traceability"):
    obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, [str(value) for value in values])


def set_visibility(obj, visible: bool) -> None:
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.Visibility = bool(visible)


def add_source(doc, library, name, label, shape, source_path, geometry_class, status, holds):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    add_string(obj, "SourcePath", source_path)
    add_string(obj, "GeometryClass", geometry_class)
    add_string(obj, "LifecycleStatus", status)
    add_string(obj, "MassUse", "PROHIBITED_FROM_GEOMETRY_VOLUME_WITHOUT_ACTIVE_MASS_AUTHORITY")
    add_string_list(obj, "Holds", holds)
    library.addObject(obj)
    return obj


def add_link(doc, group, name, label, source, matrix, status, use_scope, holds, visible=True):
    link = doc.addObject("App::Link", name)
    link.Label = label
    link.LinkedObject = source
    link.LinkTransform = False
    link.Placement = matrix_to_placement(matrix)
    add_string(link, "LifecycleStatus", status)
    add_string(link, "UseScope", use_scope)
    add_string_list(link, "Holds", holds)
    group.addObject(link)
    set_visibility(link, visible)
    return link


def add_slot(doc, group, name, source_path, frame_status, reason, holds):
    slot = doc.addObject("App::FeaturePython", name)
    slot.Label = name
    add_string(slot, "LifecycleStatus", "UNRESOLVED_HOLD")
    add_string(slot, "SourcePath", source_path)
    add_string(slot, "FrameStatus", frame_status)
    add_string(slot, "Reason", reason)
    add_string_list(slot, "Holds", holds)
    group.addObject(slot)
    return slot


def transformed_shape(source, matrix):
    shape = source.Shape.copy()
    shape.Placement = matrix_to_placement(matrix)
    return shape


def pair_row(name_a, name_b, shape_a, shape_b):
    distance = float(shape_a.distToShape(shape_b)[0])
    common_volume = float(shape_a.common(shape_b).Volume)
    return {
        "component_a": name_a,
        "component_b": name_b,
        "minimum_distance_mm": round(distance, 9),
        "common_volume_mm3": round(common_volume, 9),
    }


def classify_pair(name_a, name_b, common_volume_mm3, distance_mm) -> str:
    pair = frozenset((name_a, name_b))
    if "INST_B601_ARM_CORE_Q0" in pair:
        return "KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY_NOT_INTERFERENCE_GEOMETRY"
    if common_volume_mm3 > 1.0e-6:
        return "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
    if distance_mm <= 1.0e-7:
        return "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME"
    return "SEPARATED_CLEAR_GAP_GEOMETRY_ONLY"


def main() -> None:
    memory_start = memory_snapshot()
    required_sources = [
        MODEL_SPECS, FRAME_TREE, M4_FRAME_TREE, SERVICE_SPACECRAFT_GEOM, V5R_FRAME_TREE,
        URDF, B601_Q0_WITNESS, M3R_STEP, M3R_PHYSICAL_STACK, GRIPPER_R1_STEP,
        GRIPPER_LEFT_RAIL_SWEPT, GRIPPER_RIGHT_RAIL_SWEPT,
        LOAD_BRIDGE_STEP, LOAD_BRIDGE_DATUMS, LOAD_BRIDGE_FITUP,
        SUPPORT_V2_DEF, G4_DEF, M7_ODR, M7_PLAN,
    ]
    missing = [str(path) for path in required_sources if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing required source(s): {missing}")

    source_records = [
        {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "status": "HASH_BOUND_AT_M7_WP1_BUILD_READ_ONLY",
        }
        for path in required_sources
    ]

    q0 = parse_q0_chain()
    spec = load_model_spec("servicer_12U_v0")
    split = build_servicer_shapes(spec)

    doc = App.newDocument("DESIGN_FREEZE_ASSEMBLY_V1")
    top = doc.addObject("App::Part", "DESIGN_FREEZE_ASSEMBLY_V1")
    top.Label = "DESIGN_FREEZE_ASSEMBLY_V1"
    add_string(top, "LifecycleStatus", "M7_DESIGN_FREEZE_ASSEMBLY_CANDIDATE_LEVEL_NOT_MANUFACTURING_NOT_FLIGHT")
    add_string(top, "ReleaseScope", "MECHANICAL_ENGINEERING_DESIGN_CLOSURE_ONLY__GATE_A_SCOPE")
    add_string(top, "LengthUnit", "mm")
    add_string(top, "DefaultConfiguration", "DEPLOYED_NOMINAL__ARM_TASK_READY")
    add_string(top, "FormalFEA", "NOT_PERFORMED_BY_WP1__OPERATIONAL_FEA_IS_WP7_SCOPE")
    add_string(
        top,
        "FrameAuthority",
        "ODR-01: M frame dynamics mounting reference = T_SM [185.25,0,0] mm + Ry(90 deg); "
        "stations 198.0/208.0/210.405 mm are a geometric feature stack, not a second dynamics frame",
    )
    add_string_list(
        top,
        "ExplicitNonClaims",
        [
            "NOT_MANUFACTURING_RELEASED",
            "NOT_FLIGHT_OR_LAUNCH_QUALIFIED",
            "NOT_SYSTEM_MASS_OR_INERTIA_AUTHORITY",
            "NOT_CONTINUOUS_COLLISION_OR_SWEEP_VALIDATED",
            "ARM_IS_FRAME_AXIS_WITNESS_NOT_PHYSICAL_GEOMETRY",
            "CAMERA_AND_BRACKET_SOLIDS_ARE_CLEARANCE_EVIDENCE_CANDIDATES_ONLY",
            "LEGACY_FLANGE_TAGGED_REFERENCE_NOT_MERGED_INTO_LOAD_BRIDGE",
        ],
    )

    source_library = doc.addObject("App::Part", "SOURCE_GEOMETRY_LIBRARY")
    source_library.Label = "SOURCE_GEOMETRY_LIBRARY__EMBEDDED_ACTIVE_COPIES"
    installed_group = doc.addObject("App::Part", "INSTALLED_COMPONENT_LINKS")
    installed_group.Label = "INSTALLED_COMPONENT_LINKS__DEFAULT_CONFIGURATION"
    candidate_group = doc.addObject("App::Part", "DESIGN_CANDIDATE_COMPONENTS")
    candidate_group.Label = "DESIGN_CANDIDATE_COMPONENTS__EVIDENCE_ONLY_NOT_EXPORTED"
    unresolved_group = doc.addObject("App::Part", "UNRESOLVED_COMPONENT_SLOTS")
    unresolved_group.Label = "UNRESOLVED_COMPONENT_SLOTS__HOLD"
    for group in (source_library, installed_group, candidate_group, unresolved_group):
        top.addObject(group)

    # ---- embedded sources ------------------------------------------------
    src_bus = add_source(
        doc, source_library, "SRC_BUS_12U_CORE",
        "SRC_BUS_12U_CORE__V0_ANALYTIC_RECONSTRUCTION__LEGACY_FLANGE_TAGGED_REFERENCE",
        split["bus"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::servicer_12U_v0.primitives",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVES",
        "WORKING_PROTOTYPE_GEOMETRY",
        [
            "12U_DIMENSION_VERIFICATION_HOLD",
            "INTERNAL_STRUCTURE_NOT_MODELLED",
            "LEGACY_FLANGE_OWNERSHIP_HOLD_TAGGED_REFERENCE_ODR01",
        ],
    )
    src_panel_l = add_source(
        doc, source_library, "SRC_SOLAR_ARRAY_LEFT",
        "SRC_SOLAR_ARRAY_LEFT__DEPLOYED_PLATE_PROXY",
        split["panel_left"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::solar_panel_left",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVE",
        "DEPLOYED_GEOMETRY_PROXY",
        ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD", "PANEL_FAILURE_ATTACHED_STUCK_ODR02"],
    )
    src_panel_r = add_source(
        doc, source_library, "SRC_SOLAR_ARRAY_RIGHT",
        "SRC_SOLAR_ARRAY_RIGHT__DEPLOYED_PLATE_PROXY",
        split["panel_right"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::solar_panel_right",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVE",
        "DEPLOYED_GEOMETRY_PROXY",
        ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD", "PANEL_FAILURE_ATTACHED_STUCK_ODR02"],
    )
    witness_doc = App.newDocument("M7_B601_Q0_WITNESS_IMPORT")
    try:
        Part.insert(str(B601_Q0_WITNESS), witness_doc.Name)
        witness_doc.recompute()
        witness_shapes = [
            obj.Shape.copy()
            for obj in witness_doc.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
        ]
        if not witness_shapes:
            raise RuntimeError(f"no solid witness geometry in {B601_Q0_WITNESS}")
        arm_core = Part.makeCompound(witness_shapes)
    finally:
        App.closeDocument(witness_doc.Name)
    src_arm = add_source(
        doc, source_library, "SRC_B601_ARM_CORE_Q0",
        "SRC_B601_ARM_CORE_Q0__FRAME_AXIS_WITNESS",
        arm_core,
        B601_Q0_WITNESS.relative_to(PROJECT_ROOT).as_posix(),
        "KINEMATIC_FRAME_AND_AXIS_WITNESS",
        "FRAME_TREE_WITNESS_NOT_ARM_ENVELOPE_NOT_VENDOR_BREP",
        ["B601_PHYSICAL_GEOMETRY_HOLD", "PHYSICAL_FITUP_HOLD", "CONTINUOUS_COLLISION_HOLD"],
    )
    m3r_shape = load_shape_from_step(doc, M3R_STEP)
    src_m3r = add_source(
        doc, source_library, "SRC_M3R_INTERFACE_ASSEMBLY",
        "SRC_M3R_INTERFACE_ASSEMBLY__WORKING_BREP",
        m3r_shape,
        M3R_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "M3_PARAMETERIZED_WORKING_BREP",
        "WORKING_DETAILED_DESIGN_NOT_RELEASED",
        ["B601_PHYSICAL_FITUP_HOLD", "TOLERANCE_AND_FASTENER_HOLD", "M3R_AS_BUILT_MEASUREMENT_OPEN_ODR05"],
    )
    gripper_shape = load_shape_from_step(doc, GRIPPER_R1_STEP)
    src_gripper = add_source(
        doc, source_library, "SRC_GRIPPER_R1_PALM",
        "SRC_GRIPPER_R1_PALM__CORRECTED_NEUTRAL_BREP",
        gripper_shape,
        GRIPPER_R1_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "VERIFIED_NEUTRAL_DERIVATIVE_BREP",
        "PALM_ONLY_INTEGRATION_OVERLAY",
        ["FINGER_BREP_SEPARATION_HOLD", "CONTACT_LOAD_HOLD", "MANUFACTURING_CLEARANCE_HOLD"],
    )
    bridge_shape = load_shape_from_step(doc, LOAD_BRIDGE_STEP)
    src_bridge = add_source(
        doc, source_library, "SRC_SPACECRAFT_LOAD_BRIDGE",
        "SRC_SPACECRAFT_LOAD_BRIDGE__M6_DESIGN_CANDIDATE",
        bridge_shape,
        LOAD_BRIDGE_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "M6_PARAMETERIZED_DESIGN_CANDIDATE_BREP_S_FRAME_AUTHORED",
        "DESIGN_CANDIDATE_INTEGRATED__AUTHORITY_HOLDS_PRESERVED",
        [
            "LOAD_BRIDGE_PHYSICAL_FITUP_HOLD",
            "MATING_FASTENER_AND_TOLERANCE_HOLD",
            "SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD",
            "MATERIAL_APPROVAL_AND_PROCESS_HOLD",
            "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD",
            "LEGACY_FLANGE_OWNERSHIP_HOLD",
        ],
    )

    # ---- camera relocation candidate evidence solids (hidden, not exported)
    cam_a = centered_cylinder_x(CAM_A_RADIUS, CAM_A_LENGTH, *CAM_A_CENTER)
    cam_a_obj = add_source(
        doc, candidate_group, "CAND_CAMERA_CAM_A",
        "CAND_CAMERA_CAM_A__FRONT_FACE_UPPER_CORNER_BRACKET_POSE",
        cam_a,
        "M7_WP1_CAMERA_RELOCATION_CANDIDATE_A",
        "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID",
        "CANDIDATE_NOT_AUTHORIZED",
        ["CAMERA_PART_NUMBER_HOLD", "OPTICAL_CALIBRATION_HOLD", "MASS_INERTIA_HOLD"],
    )
    brk_a_shapes = [bbox_box(*box) for box in BRK_A_BOXES]
    brk_a = Part.makeCompound(brk_a_shapes)
    brk_a_obj = add_source(
        doc, candidate_group, "CAND_CAMERA_BRACKET_A",
        "CAND_CAMERA_BRACKET_A__DECK_RISER_PLUS_FORWARD_ARM_STUB",
        brk_a,
        "M7_WP1_CAMERA_RELOCATION_CANDIDATE_A_BRACKET_STUB",
        "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID",
        "CANDIDATE_NOT_AUTHORIZED",
        ["BRACKET_DETAIL_DESIGN_HOLD", "FASTENER_PATTERN_HOLD"],
    )
    cam_b = centered_cylinder_x(CAM_B_RADIUS, CAM_B_LENGTH, *CAM_B_CENTER)
    cam_b_obj = add_source(
        doc, candidate_group, "CAND_CAMERA_CAM_B",
        "CAND_CAMERA_CAM_B__DECK_FLUSH_FORWARD_POSE",
        cam_b,
        "M7_WP1_CAMERA_RELOCATION_CANDIDATE_B",
        "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID",
        "CANDIDATE_NOT_AUTHORIZED",
        ["CAMERA_PART_NUMBER_HOLD", "OPTICAL_CALIBRATION_HOLD", "MASS_INERTIA_HOLD"],
    )
    brk_b = Part.makeCompound([bbox_box(*box) for box in BRK_B_BOXES])
    brk_b_obj = add_source(
        doc, candidate_group, "CAND_CAMERA_BRACKET_B",
        "CAND_CAMERA_BRACKET_B__DECK_BASE_PLATE_STUB",
        brk_b,
        "M7_WP1_CAMERA_RELOCATION_CANDIDATE_B_BRACKET_STUB",
        "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID",
        "CANDIDATE_NOT_AUTHORIZED",
        ["BRACKET_DETAIL_DESIGN_HOLD", "FASTENER_PATTERN_HOLD"],
    )

    # ---- installed instances --------------------------------------------
    identity = mat_identity()
    installed_specs = []
    installed_specs.append(("INST_BUS_12U_CORE", src_bus, identity, "ANALYTIC_PROXY_INSTALLED"))
    installed_specs.append(("INST_SOLAR_ARRAY_LEFT_DEPLOYED", src_panel_l, identity, "DEPLOYED_PROXY_INSTALLED"))
    installed_specs.append(("INST_SOLAR_ARRAY_RIGHT_DEPLOYED", src_panel_r, identity, "DEPLOYED_PROXY_INSTALLED"))
    t_arm = arm_base_matrix()
    installed_specs.append(("INST_B601_ARM_CORE_Q0", src_arm, t_arm, "Q0_FRAME_AXIS_WITNESS_INSTALLED"))
    t_m3r = arm_base_matrix((208.0, 0.015994151, -0.08636607))
    installed_specs.append(("INST_M3R_INTERFACE_ASSEMBLY", src_m3r, t_m3r, "WORKING_BREP_INSTALLED"))
    t_link6_global = mat_mul(t_arm, q0["link6"])
    installed_specs.append(("INST_GRIPPER_R1_PALM", src_gripper, t_link6_global, "PALM_OVERLAY_INSTALLED"))
    installed_specs.append(
        ("INST_SPACECRAFT_LOAD_BRIDGE", src_bridge, identity, "M6_DESIGN_CANDIDATE_INSTALLED")
    )

    installed_links = []
    for name, source, matrix, status in installed_specs:
        link = add_link(
            doc, installed_group, name, name, source, matrix, status,
            "DEFAULT_DEPLOYED_NOMINAL__ARM_TASK_READY",
            ["NO_SYSTEM_INTERFERENCE_RELEASE", "NO_MASS_FROM_BREP"],
            True,
        )
        installed_links.append(link)

    # ---- unresolved slots -------------------------------------------------
    add_slot(
        doc, unresolved_group, "SLOT_SENSOR_PACKAGE__RELOCATION_CANDIDATES_PRESENT",
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::camera_payload",
        "CANDIDATE_T_S_SENSOR_REJECTED_BY_NARROW_PHASE__RELOCATION_CANDIDATES_CAM_A_CAM_B_MEASURED",
        "The source-bound camera placeholder at [190.25,0,80] mm penetrates the installed M3R working B-rep. "
        "CAM_A [190.25,-35,145] and CAM_B [150,-60,143.15] are measured relocation candidates; "
        "no camera selection is authorized.",
        ["SENSOR_PACKAGE_SELECTION_HOLD", "OPTICAL_CALIBRATION_HOLD"],
    )
    add_slot(
        doc, unresolved_group, "SLOT_ARM_HDRM__UNRESOLVED",
        G4_DEF.relative_to(PROJECT_ROOT).as_posix(),
        "GLOBAL_TRANSFORM_AND_PRODUCT_HOLD",
        "ARM_HDRM stays a defined-not-modelled demonstrator concept (F3R2 G4); restraint plane x=0, "
        "z band 132..168; no authorized mechanism geometry.",
        ["HDRM_GLOBAL_TRANSFORM_HOLD", "HDRM_PRODUCT_AND_TEST_HOLD", "FLIGHT_HDRM_HOLD"],
    )
    add_slot(
        doc, unresolved_group, "SLOT_TARGET_INTERFACE__UNRESOLVED",
        "20_engineering/config/geometry/capture_interface_v1.yaml",
        "T_S_TARGET_NULL",
        "Target is a scenario asset, not an installed spacecraft component; no relative capture pose is frozen.",
        ["TARGET_RELATIVE_POSE_HOLD", "CONTACT_GEOMETRY_HOLD"],
    )
    add_slot(
        doc, unresolved_group, "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED",
        GRIPPER_R1_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "PALM_BOUND_FINGERS_NOT_AVAILABLE_AS_VALID_BREP",
        "R1 source closes the palm rail-slot geometry only; complete separated finger B-reps are not released.",
        ["FINGER_BREP_SEPARATION_HOLD", "PREGRASP_CONTACT_HOLD"],
    )
    add_slot(
        doc, unresolved_group, "SLOT_SOLAR_STOW_AND_HINGE__UNRESOLVED",
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::servicer_12U_v0",
        "STOWED_PANEL_AND_HINGE_KINEMATICS_NULL",
        "Stowed panel geometry, root-hinge product and solar HDRM/latch geometry are not authorized; "
        "ODR-02 attached-stuck failure semantics apply to configuration definitions only.",
        ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD", "SOLAR_HDRM_PRODUCT_HOLD", "LATCH_STOP_PRODUCT_HOLD"],
    )
    add_slot(
        doc, unresolved_group, "SLOT_STOW_SUPPORTS__CANDIDATE_REF",
        SUPPORT_V2_DEF.relative_to(PROJECT_ROOT).as_posix(),
        "G32_SUPPORTS_V2_DEFINED_NOT_MODELLED_IN_NEUTRAL_CHAIN",
        "G07/G08/MID support heads are defined by the F3R2 G32 package (native-frame, deck z=113.15); "
        "neutral-chain B-reps are WP1 candidate outputs in SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml, "
        "not installed solids.",
        ["SUPPORT_PRODUCT_BREP_HOLD", "PAD_BENCH_CALIBRATION_HOLD"],
    )

    config = doc.addObject("App::FeaturePython", "CONFIGURATION_REGISTER")
    config.Label = "CONFIGURATION_REGISTER__NINE_REQUIRED_STATES"
    add_string(config, "ActiveGeometryConfiguration", "DEPLOYED_NOMINAL__ARM_TASK_READY")
    add_string(
        config,
        "PanelFailureSemantics",
        "ODR-02: LEFT/RIGHT/BOTH_PANEL_FAIL = failed panel(s) remain mechanically attached, "
        "stuck or not normally deployed; jettison interpretation forbidden unless a dedicated "
        "jettison device is later designed and authorized",
    )
    add_string_list(
        config,
        "RequiredConfigurations",
        [
            "DEPLOYED_NOMINAL", "LEFT_PANEL_FAIL", "RIGHT_PANEL_FAIL", "BOTH_PANEL_FAIL",
            "ARM_STOWED_ONORBIT", "ARM_TASK_READY", "PREGRASP",
            "TARGET_CAPTURE_22KG", "TARGET_CAPTURE_150KG",
        ],
    )
    add_string_list(
        config,
        "GeometryState",
        [
            "DEPLOYED_NOMINAL=ACTIVE_GEOMETRY",
            "LEFT_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
            "RIGHT_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
            "BOTH_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
            "ARM_STOWED_ONORBIT=SOURCE_WITNESS_EXISTS_NOT_EMBEDDED_AS_ACTIVE_CONFIG",
            "ARM_TASK_READY=ACTIVE_Q0_GEOMETRY",
            "PREGRASP=PALM_ONLY_FINGER_BREP_HOLD",
            "TARGET_CAPTURE_22KG=TARGET_SOURCE_NOT_EMBEDDED_RELATIVE_POSE_HOLD",
            "TARGET_CAPTURE_150KG=TARGET_SOURCE_NOT_EMBEDDED_RELATIVE_POSE_HOLD",
        ],
    )
    top.addObject(config)

    set_visibility(source_library, False)
    set_visibility(candidate_group, False)
    set_visibility(unresolved_group, False)
    set_visibility(installed_group, True)
    doc.recompute()

    # ---- narrow phase: installed set -------------------------------------
    installed_shapes = [transformed_shape(source, matrix) for _, source, matrix, _ in installed_specs]
    installed_shape_map = {
        name: shape for (name, _, _, _), shape in zip(installed_specs, installed_shapes)
    }
    pairwise_narrow_phase = []
    installed_names = list(installed_shape_map)
    for index, name_a in enumerate(installed_names):
        for name_b in installed_names[index + 1:]:
            row = pair_row(name_a, name_b, installed_shape_map[name_a], installed_shape_map[name_b])
            row["classification"] = classify_pair(
                name_a, name_b, row["common_volume_mm3"], row["minimum_distance_mm"]
            )
            row["acceptance_scope"] = "DEFAULT_CONFIGURATION_GEOMETRY_ONLY_NOT_CONTINUOUS_SWEEP"
            pairwise_narrow_phase.append(row)

    # ---- candidate clearance evidence ------------------------------------
    m3r_installed = installed_shape_map["INST_M3R_INTERFACE_ASSEMBLY"]
    bus_installed = installed_shape_map["INST_BUS_12U_CORE"]
    bridge_installed = installed_shape_map["INST_SPACECRAFT_LOAD_BRIDGE"]
    arm_installed = installed_shape_map["INST_B601_ARM_CORE_Q0"]

    def candidate_row(cand_name, cand_shape, ref_name, ref_shape, classification):
        row = pair_row(cand_name, ref_name, cand_shape, ref_shape)
        row["classification"] = classification
        row["acceptance_scope"] = "CANDIDATE_CLEARANCE_EVIDENCE_NOMINAL_GEOMETRY_ONLY"
        return row

    candidate_clearance = []
    for cand_name, cand_obj in (
        ("CAND_CAMERA_CAM_A", cam_a_obj),
        ("CAND_CAMERA_BRACKET_A", brk_a_obj),
        ("CAND_CAMERA_CAM_B", cam_b_obj),
        ("CAND_CAMERA_BRACKET_B", brk_b_obj),
    ):
        cand_shape = cand_obj.Shape
        for ref_name, ref_shape in (
            ("INST_M3R_INTERFACE_ASSEMBLY", m3r_installed),
            ("INST_SPACECRAFT_LOAD_BRIDGE", bridge_installed),
            ("INST_BUS_12U_CORE", bus_installed),
        ):
            row = pair_row(cand_name, ref_name, cand_shape, ref_shape)
            if row["common_volume_mm3"] > 1.0e-6:
                cls = "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
            elif row["minimum_distance_mm"] <= 1.0e-7:
                cls = "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME"
            else:
                cls = "SEPARATED_CLEAR_GAP_GEOMETRY_ONLY"
            row["classification"] = cls
            row["acceptance_scope"] = "CANDIDATE_CLEARANCE_EVIDENCE_NOMINAL_GEOMETRY_ONLY"
            candidate_clearance.append(row)
        # intentional mount embedment pairs
        if cand_name == "CAND_CAMERA_CAM_A":
            candidate_clearance.append(
                candidate_row(cand_name, cand_shape, "CAND_CAMERA_BRACKET_A", brk_a_obj.Shape,
                              "INTENTIONAL_MOUNT_EMBEDMENT_CANDIDATE")
            )
            candidate_clearance.append(
                candidate_row(cand_name, cand_shape, "INST_B601_ARM_CORE_Q0", arm_installed,
                              "KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY_NOT_INTERFERENCE_GEOMETRY")
            )
        if cand_name == "CAND_CAMERA_CAM_B":
            candidate_clearance.append(
                candidate_row(cand_name, cand_shape, "CAND_CAMERA_BRACKET_B", brk_b_obj.Shape,
                              "INTENTIONAL_MOUNT_FACE_CONTACT_CANDIDATE")
            )
            candidate_clearance.append(
                candidate_row(cand_name, cand_shape, "INST_B601_ARM_CORE_Q0", arm_installed,
                              "KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY_NOT_INTERFERENCE_GEOMETRY")
            )

    # ---- export aggregate (installed set only) ----------------------------
    export_compound = Part.makeCompound(installed_shapes)
    export_obj = doc.addObject("Part::Feature", "STEP_EXPORT_AGGREGATE")
    export_obj.Label = "STEP_EXPORT_AGGREGATE__DEFAULT_CONFIGURATION_INSTALLED_SET_ONLY"
    export_obj.Shape = export_compound
    add_string(export_obj, "LifecycleStatus", "DERIVED_EXPORT_OBJECT")
    add_string(export_obj, "Composition", f"{len(installed_specs)}_INSTALLED_LINKS_DEFAULT_CONFIGURATION")
    add_string(export_obj, "MassUse", "PROHIBITED")
    top.addObject(export_obj)
    set_visibility(export_obj, False)

    doc.recompute()
    staged = OUTPUT_FCSTD.with_name(OUTPUT_FCSTD.stem + ".new.FCStd")
    if staged.exists():
        staged.unlink()
    doc.saveAs(str(staged))
    Part.export([export_obj], str(OUTPUT_STEP))
    App.closeDocument(doc.Name)
    os.replace(staged, OUTPUT_FCSTD)

    # ---- cold reopen validations -----------------------------------------
    reopened = App.openDocument(str(OUTPUT_FCSTD))
    try:
        links = [obj for obj in reopened.Objects if obj.TypeId == "App::Link"]
        internal_links = [
            obj for obj in links
            if obj.LinkedObject is not None and obj.LinkedObject.Document is reopened
        ]
        source_shapes = [
            obj for obj in reopened.Objects
            if (obj.Name.startswith("SRC_") or obj.Name.startswith("CAND_"))
            and hasattr(obj, "Shape") and not obj.Shape.isNull()
        ]
        fcstd_reopen = {
            "object_count": len(reopened.Objects),
            "app_part_count": sum(obj.TypeId == "App::Part" for obj in reopened.Objects),
            "app_link_count": len(links),
            "all_links_internal": len(internal_links) == len(links),
            "source_shape_count": len(source_shapes),
            "all_source_shapes_valid": all(obj.Shape.isValid() for obj in source_shapes),
            "installed_link_names": sorted(obj.Name for obj in links if obj.Name.startswith("INST_")),
        }
    finally:
        App.closeDocument(reopened.Name)

    step_doc = App.newDocument("M7_STEP_REOPEN")
    try:
        Part.insert(str(OUTPUT_STEP), step_doc.Name)
        step_doc.recompute()
        step_shapes = [
            obj.Shape
            for obj in step_doc.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
        ]
        step_compound = Part.makeCompound(step_shapes)
        step_reopen = {
            "object_count": len(step_doc.Objects),
            "shape_object_count": len(step_shapes),
            **shape_metrics(step_compound),
        }
    finally:
        App.closeDocument(step_doc.Name)

    memory_end = memory_snapshot()

    # ---- assembly checks ---------------------------------------------------
    bridge_bbox = shape_metrics(bridge_shape)["bounding_box_mm"]
    m3r_local_bbox = shape_metrics(m3r_shape)["bounding_box_mm"]

    def find_pair(a, b):
        for row in pairwise_narrow_phase:
            if frozenset((row["component_a"], row["component_b"])) == frozenset((a, b)):
                return row
        raise RuntimeError(f"pair not found: {a} vs {b}")

    def find_cand(cand, ref):
        for row in candidate_clearance:
            if row["component_a"] == cand and row["component_b"] == ref:
                return row
        raise RuntimeError(f"candidate pair not found: {cand} vs {ref}")

    bridge_bus = find_pair("INST_BUS_12U_CORE", "INST_SPACECRAFT_LOAD_BRIDGE")
    bridge_m3r = find_pair("INST_M3R_INTERFACE_ASSEMBLY", "INST_SPACECRAFT_LOAD_BRIDGE")
    bus_m3r = find_pair("INST_BUS_12U_CORE", "INST_M3R_INTERFACE_ASSEMBLY")

    geometry_checks = {
        "bridge_x_span_matches_stations_185p25_196p0": (
            abs(bridge_bbox[0] - 185.25) <= 1.0e-6 and abs(bridge_bbox[3] - 196.0) <= 1.0e-6
        ),
        "m3r_local_bbox_matches_m4_reference": (
            abs(m3r_local_bbox[0] - (-85.0)) <= 1.0e-6 and abs(m3r_local_bbox[5] - 2.405) <= 1.0e-6
        ),
        "m3r_volume_matches_m3_receipt": abs(m3r_shape.Volume - 289750.832561) <= 1.0e-6,
        "gripper_R1_volume_matches_reopen_receipt_with_import_tolerance": abs(
            gripper_shape.Volume - 45088.72293792546
        ) <= 1.0e-2,
        "bridge_bus_nominal_face_contact_zero_distance": bridge_bus["minimum_distance_mm"] <= 1.0e-7,
        "bridge_bus_no_positive_common_volume": bridge_bus["common_volume_mm3"] <= 1.0e-6,
        "bridge_m3r_nominal_face_contact_zero_distance": bridge_m3r["minimum_distance_mm"] <= 1.0e-7,
        "bridge_m3r_no_positive_common_volume": bridge_m3r["common_volume_mm3"] <= 1.0e-6,
        "bus_m3r_still_separated_10p75_span_semantics": abs(bus_m3r["minimum_distance_mm"] - 10.75) <= 1.0e-6,
        "no_unclassified_positive_overlap_installed": not any(
            row["classification"] == "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
            for row in pairwise_narrow_phase
        ),
        "cam_a_clears_m3r_positive_distance": find_cand("CAND_CAMERA_CAM_A", "INST_M3R_INTERFACE_ASSEMBLY")["minimum_distance_mm"] > 0.0,
        "cam_a_clears_bridge_positive_distance": find_cand("CAND_CAMERA_CAM_A", "INST_SPACECRAFT_LOAD_BRIDGE")["minimum_distance_mm"] > 0.0,
        "cam_a_clears_bus_positive_distance": find_cand("CAND_CAMERA_CAM_A", "INST_BUS_12U_CORE")["minimum_distance_mm"] > 0.0,
        "cam_b_clears_m3r_positive_distance": find_cand("CAND_CAMERA_CAM_B", "INST_M3R_INTERFACE_ASSEMBLY")["minimum_distance_mm"] > 0.0,
        "cam_b_clears_bridge_positive_distance": find_cand("CAND_CAMERA_CAM_B", "INST_SPACECRAFT_LOAD_BRIDGE")["minimum_distance_mm"] > 0.0,
        "no_unclassified_positive_overlap_candidates": not any(
            row["classification"] == "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
            for row in candidate_clearance
        ),
        "step_reopen_valid": step_reopen["valid"],
        "step_reopen_solid_count_matches_installed_composition": (
            step_reopen["solids"] == sum(len(shape.Solids) for shape in installed_shapes)
        ),
        "step_reopen_volume_matches_export_compound": abs(
            step_reopen["volume_mm3"] - float(export_compound.Volume)
        ) <= 1.0e-3,
        "fcstd_all_links_internal": fcstd_reopen["all_links_internal"],
        "fcstd_all_source_shapes_valid": fcstd_reopen["all_source_shapes_valid"],
    }

    report = {
        "schema": "M7_WP1_DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1",
        "generated_local": local_now(),
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP1_STRUCTURE_CAD",
        "lifecycle_status": "DESIGN_FREEZE_CANDIDATE_LEVEL_NOT_MANUFACTURING_NOT_FLIGHT",
        "builder": "FreeCADCmd / OpenCascade (single process, WP1-exclusive Owner Override)",
        "freecad_version": str(App.Version()),
        "memory_gate": {
            "at_build_start": memory_start,
            "at_build_end": memory_end,
            "threshold_gib": MEMORY_THRESHOLD_GIB,
            "memory_gate_passed": bool(
                memory_start["memory_gate_passed"] and memory_end["memory_gate_passed"]
            ),
        },
        "owner_override": {
            "required": True,
            "used": True,
            "class": "BOUNDED_SERIAL_FREECADCMD_SINGLE_LIGHTWEIGHT_PARAMETERIZED_BREP",
            "source": OWNER_OVERRIDE_SOURCE,
            "source_sha256": next(
                (r["sha256"] for r in source_records if r["path"].endswith("pasted-text.txt")),
                "11BB4F1413570C3A9B229C70C5E2CBC478224EB24FFCABED66815107C6885F8B",
            ),
            "m4_register_reference": M4_OVERRIDE_REGISTER,
            "controls": [
                "SINGLE_FREECAD_PROCESS",
                "LIGHTWEIGHT_PARAMETERIZED_BREP_ONLY",
                "NO_VENDOR_252MB_STEP_IMPORT",
                "NO_FEA",
                "READ_ONLY_USE_OF_HASH_PINNED_INPUTS",
            ],
        },
        "architecture": "EMBEDDED_PART_FEATURE_SOURCE_LIBRARY_PLUS_INTERNAL_APP_LINK_INSTANCES",
        "external_file_references_in_master": False,
        "default_configuration": "DEPLOYED_NOMINAL__ARM_TASK_READY",
        "installed_component_count": len(installed_specs),
        "installed_components": [name for name, _, _, _ in installed_specs],
        "design_candidate_evidence_components": [
            "CAND_CAMERA_CAM_A", "CAND_CAMERA_BRACKET_A", "CAND_CAMERA_CAM_B", "CAND_CAMERA_BRACKET_B",
        ],
        "camera_candidate_definitions": {
            "CAM_A": {
                "center_S_mm": list(CAM_A_CENTER),
                "radius_mm": CAM_A_RADIUS,
                "length_mm": CAM_A_LENGTH,
                "axis_S": [1.0, 0.0, 0.0],
                "bracket_stub_boxes_S_mm": [list(b) for b in BRK_A_BOXES],
            },
            "CAM_B": {
                "center_S_mm": list(CAM_B_CENTER),
                "radius_mm": CAM_B_RADIUS,
                "length_mm": CAM_B_LENGTH,
                "axis_S": [1.0, 0.0, 0.0],
                "bracket_stub_boxes_S_mm": [list(b) for b in BRK_B_BOXES],
            },
        },
        "transforms": {
            "T_S_M_DYNAMICS_ODR01": [
                [0.0, 0.0, 1.0, 185.25],
                [0.0, 1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "T_S_B601_ARM_BASE": clean_matrix(t_arm),
            "T_S_M3R_LOCAL": clean_matrix(t_m3r),
            "T_S_LINK6_Q0_FOR_GRIPPER_R1_PALM": clean_matrix(t_link6_global),
            "T_S_LOAD_BRIDGE": "IDENTITY__M6_STEP_AUTHORED_IN_S_FRAME",
            "T_S_HDRM": None,
            "T_S_TARGET_22KG": None,
            "T_S_TARGET_150KG": None,
        },
        "source_geometry_metrics": {
            "bus_12U_core": shape_metrics(split["bus"]),
            "solar_array_left": shape_metrics(split["panel_left"]),
            "solar_array_right": shape_metrics(split["panel_right"]),
            "B601_arm_q0_frame_axis_witness": shape_metrics(arm_core),
            "M3R_interface_assembly": shape_metrics(m3r_shape),
            "gripper_R1_palm": shape_metrics(gripper_shape),
            "spacecraft_load_bridge_m6_candidate": shape_metrics(bridge_shape),
            "camera_cam_a_envelope": shape_metrics(cam_a),
            "camera_bracket_a_stub": shape_metrics(brk_a),
            "camera_cam_b_envelope": shape_metrics(cam_b),
            "camera_bracket_b_stub": shape_metrics(brk_b),
        },
        "pairwise_narrow_phase_default_configuration": pairwise_narrow_phase,
        "candidate_clearance_evidence": candidate_clearance,
        "checks": geometry_checks,
        "fcstd_cold_reopen": fcstd_reopen,
        "step_cold_reopen": step_reopen,
        "formal_fea_performed": False,
        "source_register": source_records,
        "outputs": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in (OUTPUT_FCSTD, OUTPUT_STEP)
        ],
        "verdict": (
            "PASS_DESIGN_FREEZE_ASSEMBLY_BUILD_WITH_EXPLICIT_HOLDS"
            if all(geometry_checks.values())
            else "HOLD_DESIGN_FREEZE_ASSEMBLY_VALIDATION_FAILURE"
        ),
    }
    BUILD_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["verdict"],
        "fcstd": str(OUTPUT_FCSTD),
        "step": str(OUTPUT_STEP),
        "memory_gate_passed": report["memory_gate"]["memory_gate_passed"],
        "checks_failed": [k for k, v in geometry_checks.items() if not v],
    }, ensure_ascii=False))


main()
