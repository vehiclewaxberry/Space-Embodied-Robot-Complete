# -*- coding: utf-8 -*-
"""Build the M4 competition-scope mechanical digital prototype.

This builder intentionally produces a geometry/dynamics integration prototype,
not manufacturing or flight hardware.  It embeds all active source shapes in a
single FCStd, uses App::Link for installed instances, and keeps every component
whose spacecraft transform is unresolved in a hidden HOLD library.

Run with FreeCADCmd.  Length units are millimetres throughout this file.
No FEA is performed.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Part


HERE = Path(__file__).resolve().parent
M4_ROOT = HERE.parent
PROJECT_ROOT = M4_ROOT.parents[1]
M3_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DETAILED_DESIGN_V1"
M3_TERMINAL_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
V5R_ROOT = PROJECT_ROOT / "20_engineering" / "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
CAD_ROOT = PROJECT_ROOT / "20_engineering" / "cad"

OUTPUT_FCSTD = HERE / "SEI_DIGITAL_PROTOTYPE_V1.FCStd"
OUTPUT_STEP = HERE / "SEI_DIGITAL_PROTOTYPE_V1.step"
BUILD_RECEIPT = HERE / "DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json"
GEOMETRY_AUDIT = HERE / "DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1.json"
SOURCE_PINS = HERE / "DIGITAL_PROTOTYPE_SOURCE_HASH_PINS_V1.json"

MODEL_SPECS = CAD_ROOT / "spacecraft_layout" / "model_specs_v0.json"
FRAME_TREE = PROJECT_ROOT / "20_engineering" / "config" / "geometry" / "frame_tree_v1.yaml"
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
HDRM_SKELETON_STEP = (
    V5R_ROOT
    / "06_pack_and_go"
    / "V5R_NEUTRAL_OPERATIONAL_PACKAGE"
    / "addenda"
    / "v4_delta"
    / "hdrm"
    / "V4_ARM_HDRM_60MM_FLANGE_SKELETON.step"
)
TARGET_SAT_STEP = CAD_ROOT / "spacecraft_layout" / "target_satellite_v0" / "target_satellite_v0.step"
TARGET_DEBRIS_STEP = CAD_ROOT / "spacecraft_layout" / "target_debris_v0" / "target_debris_v0.step"

MEMORY_THRESHOLD_GIB = 6.0
OWNER_OVERRIDE_SOURCE = (
    "C:/Users/stude/.codex/attachments/038d9781-5921-4858-9fea-c070890a71b8/pasted-text.txt"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            "owner_override_used": True,
            "measurement_status": "UNAVAILABLE_FAIL_CLOSED",
        }
    gib = float(1024**3)
    available = stat.ullAvailPhys / gib
    total = stat.ullTotalPhys / gib
    passed = available >= MEMORY_THRESHOLD_GIB
    return {
        "available_physical_gib": round(available, 6),
        "total_physical_gib": round(total, 6),
        "threshold_gib": MEMORY_THRESHOLD_GIB,
        "memory_gate_passed": passed,
        "owner_override_used": not passed,
        "owner_override_source": OWNER_OVERRIDE_SOURCE if not passed else None,
        "measurement_status": "MEASURED_AT_BUILD_START",
        "execution_controls": [
            "SINGLE_FREECAD_PROCESS",
            "NO_VENDOR_252MB_STEP_IMPORT",
            "LIGHTWEIGHT_KINEMATIC_WITNESS_AND_PARAMETERIZED_BREP_ONLY",
            "NO_FEA",
        ],
    }


def mat_identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
        for i in range(4)
    ]


def transform_xyz_rpy_mm(xyz_m, rpy) -> list[list[float]]:
    roll, pitch, yaw = [float(value) for value in rpy]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    # URDF fixed-axis RPY: Rz(yaw) * Ry(pitch) * Rx(roll).
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


def matrix_to_placement(matrix: list[list[float]]) -> App.Placement:
    fc = App.Matrix()
    fc.A11, fc.A12, fc.A13, fc.A14 = matrix[0]
    fc.A21, fc.A22, fc.A23, fc.A24 = matrix[1]
    fc.A31, fc.A32, fc.A33, fc.A34 = matrix[2]
    fc.A41, fc.A42, fc.A43, fc.A44 = matrix[3]
    return App.Placement(fc)


def clean_matrix(matrix: list[list[float]]) -> list[list[float]]:
    return [[round(value, 12) for value in row] for row in matrix]


def arm_base_matrix(translation=(208.0, 0.0, 0.0)) -> list[list[float]]:
    # Frozen V5R physical arm-base map: Ry(+90 deg) * Rz(+25.000014 deg).
    # This is deliberately distinct from the M dynamics origin at x=185.25 mm.
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
        float(lx),
        float(ly),
        float(lz),
        App.Vector(float(cx) - float(lx) / 2.0, float(cy) - float(ly) / 2.0, float(cz) - float(lz) / 2.0),
    )


def centered_cylinder(radius, length, axis, cx, cy, cz):
    radius, length = float(radius), float(length)
    center = App.Vector(float(cx), float(cy), float(cz))
    if axis == "x":
        return Part.makeCylinder(radius, length, center - App.Vector(length / 2.0, 0.0, 0.0), App.Vector(1, 0, 0))
    if axis == "z":
        return Part.makeCylinder(radius, length, center - App.Vector(0.0, 0.0, length / 2.0), App.Vector(0, 0, 1))
    raise RuntimeError(f"unsupported cylinder axis: {axis}")


def load_model_spec(key: str) -> dict:
    data = json.loads(MODEL_SPECS.read_text(encoding="utf-8"))
    for record in data:
        if record.get("key") == key:
            return record["spec"]
    raise RuntimeError(f"{key} missing from model_specs_v0.json")


def load_servicer_spec() -> dict:
    return load_model_spec("servicer_12U_v0")


def build_model_spec_shape(key: str, composition: str = "FUSED"):
    """Reconstruct exact millimetre primitives from the geometry SSOT.

    A source can request an exact primitive compound instead of a boolean union.
    This is required for the debris model because its marker bracket is tangent
    to the cylindrical shell.  The OCCT boolean on that non-manifold line
    contact produced a valid-looking but dimensionally corrupt solid; retaining
    the exact six primitives is the conservative, auditable representation.
    """
    spec = load_model_spec(key)
    shapes = []
    for primitive in spec["primitives"]:
        dims = primitive["dims_mm"]
        center = primitive["center_offset_mm"]
        if primitive["shape"] == "box":
            shape = centered_box(
                dims["length_x"], dims["width_y"], dims["height_z"], *center
            )
        elif primitive["shape"] == "cylinder":
            shape = centered_cylinder(
                dims["radius"], dims["cyl_length"], dims["axis"], *center
            )
        else:
            raise RuntimeError(f"unsupported primitive type in {key}: {primitive['shape']}")
        shapes.append(shape)
    if not shapes:
        raise RuntimeError(f"no primitives in {key}")
    if composition == "EXACT_PRIMITIVE_COMPOUND":
        return Part.makeCompound(shapes)
    if composition != "FUSED":
        raise RuntimeError(f"unsupported composition for {key}: {composition}")
    fused = shapes[0]
    for shape in shapes[1:]:
        fused = fused.fuse(shape)
    return fused.removeSplitter()


def build_servicer_shapes(spec: dict) -> dict:
    bus_shapes = []
    panels = {}
    sensor = None
    for primitive in spec["primitives"]:
        role = primitive["role"]
        dims = primitive["dims_mm"]
        center = primitive["center_offset_mm"]
        if primitive["shape"] == "box":
            shape = centered_box(
                dims["length_x"], dims["width_y"], dims["height_z"], *center
            )
        elif primitive["shape"] == "cylinder":
            shape = centered_cylinder(
                dims["radius"], dims["cyl_length"], dims["axis"], *center
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


def build_arm_core_q0():
    """Load the lightweight q0 frame/axis witness, never a physical arm B-rep."""
    doc = App.newDocument("M4_B601_Q0_WITNESS_IMPORT")
    try:
        Part.insert(str(B601_Q0_WITNESS), doc.Name)
        doc.recompute()
        shapes = [
            obj.Shape.copy()
            for obj in doc.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
        ]
        if not shapes:
            raise RuntimeError(f"no solid witness geometry in {B601_Q0_WITNESS}")
        component_metrics = {
            obj.Name: shape_metrics(obj.Shape)
            for obj in doc.Objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0
        }
        return Part.makeCompound(shapes), component_metrics
    finally:
        App.closeDocument(doc.Name)


def shape_metrics(shape) -> dict:
    box = shape.BoundBox
    return {
        "shape_type": shape.ShapeType,
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
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


def add_string(obj, name, value, group="M4_Traceability"):
    obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def add_string_list(obj, name, values, group="M4_Traceability"):
    obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, [str(value) for value in values])


def set_visibility(obj, visible: bool) -> None:
    """Set GUI visibility when a view provider exists; FreeCADCmd may omit it."""
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


def classify_pair(name_a: str, name_b: str, common_volume_mm3: float, distance_mm: float) -> str:
    pair = frozenset((name_a, name_b))
    if "INST_B601_ARM_CORE_Q0" in pair:
        return "KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY_NOT_INTERFERENCE_GEOMETRY"
    if pair == frozenset(("INST_BUS_12U_CORE", "INST_SENSOR_PACKAGE_PLACEHOLDER")):
        return "INTENTIONAL_MOUNT_EMBEDMENT_IN_ORIGINAL_FUSED_PRIMITIVE_SPEC"
    if common_volume_mm3 > 1.0e-6:
        return "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
    if distance_mm <= 1.0e-7:
        return "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME"
    return "SEPARATED_CLEAR_GAP_GEOMETRY_ONLY"


def main() -> None:
    memory = memory_snapshot()
    required_sources = [MODEL_SPECS, FRAME_TREE, V5R_FRAME_TREE, URDF, B601_Q0_WITNESS, M3R_STEP, M3R_PHYSICAL_STACK, GRIPPER_R1_STEP, HDRM_SKELETON_STEP, TARGET_SAT_STEP, TARGET_DEBRIS_STEP]
    missing = [str(path) for path in required_sources if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing required source(s): {missing}")

    source_records = [
        {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "status": "HASH_BOUND_AT_M4_BUILD",
        }
        for path in required_sources
    ]

    q0 = parse_q0_chain()
    spec = load_servicer_spec()
    split = build_servicer_shapes(spec)
    arm_core, arm_component_metrics = build_arm_core_q0()

    doc = App.newDocument("SEI_DIGITAL_PROTOTYPE_V1")
    top = doc.addObject("App::Part", "SEI_DIGITAL_PROTOTYPE_V1")
    top.Label = "SEI_DIGITAL_PROTOTYPE_V1"
    add_string(top, "LifecycleStatus", "M4_DIGITAL_PROTOTYPE_WORKING_RELEASE")
    add_string(top, "ReleaseScope", "COMPETITION_DIGITAL_PROTOTYPE_ONLY")
    add_string(top, "LengthUnit", "mm")
    add_string(top, "DefaultConfiguration", "DEPLOYED_NOMINAL__ARM_TASK_READY")
    add_string(top, "FormalFEA", "NOT_PERFORMED_NOT_AUTHORIZED")
    add_string_list(
        top,
        "ExplicitNonClaims",
        [
            "NOT_MANUFACTURING_RELEASED",
            "NOT_FLIGHT_OR_LAUNCH_QUALIFIED",
            "NOT_VENDOR_OR_OEM_GEOMETRY_FOR_B601_CARRIERS",
            "NOT_CONTACT_OR_CONTINUOUS_COLLISION_VALIDATED",
            "NOT_SYSTEM_MASS_OR_INERTIA_AUTHORITY",
            "M_DYNAMICS_FRAME_AND_PHYSICAL_ARM_BASE_FRAME_ARE_NOT_ALIASES",
        ],
    )

    source_library = doc.addObject("App::Part", "SOURCE_GEOMETRY_LIBRARY")
    source_library.Label = "SOURCE_GEOMETRY_LIBRARY__EMBEDDED_ACTIVE_COPIES"
    installed_group = doc.addObject("App::Part", "INSTALLED_COMPONENT_LINKS")
    installed_group.Label = "INSTALLED_COMPONENT_LINKS__DEFAULT_CONFIGURATION"
    unresolved_group = doc.addObject("App::Part", "UNRESOLVED_COMPONENT_SLOTS")
    unresolved_group.Label = "UNRESOLVED_COMPONENT_SLOTS__HOLD"
    scenario_group = doc.addObject("App::Part", "SCENARIO_ASSET_LIBRARY")
    scenario_group.Label = "SCENARIO_ASSET_LIBRARY__NOT_INSTALLED"
    for group in (source_library, installed_group, unresolved_group, scenario_group):
        top.addObject(group)

    src_bus = add_source(
        doc,
        source_library,
        "SRC_BUS_12U_CORE",
        "SRC_BUS_12U_CORE__V0_ANALYTIC_RECONSTRUCTION",
        split["bus"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::servicer_12U_v0.primitives",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVES",
        "WORKING_PROTOTYPE_GEOMETRY",
        ["12U_DIMENSION_VERIFICATION_HOLD", "INTERNAL_STRUCTURE_NOT_MODELLED"],
    )
    src_panel_l = add_source(
        doc,
        source_library,
        "SRC_SOLAR_ARRAY_LEFT",
        "SRC_SOLAR_ARRAY_LEFT__DEPLOYED_PLATE_PROXY",
        split["panel_left"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::solar_panel_left",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVE",
        "DEPLOYED_GEOMETRY_PROXY",
        ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD"],
    )
    src_panel_r = add_source(
        doc,
        source_library,
        "SRC_SOLAR_ARRAY_RIGHT",
        "SRC_SOLAR_ARRAY_RIGHT__DEPLOYED_PLATE_PROXY",
        split["panel_right"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::solar_panel_right",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVE",
        "DEPLOYED_GEOMETRY_PROXY",
        ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD"],
    )
    src_sensor = add_source(
        doc,
        source_library,
        "SRC_SENSOR_PACKAGE",
        "SRC_SENSOR_PACKAGE__CAMERA_CLASS_PLACEHOLDER",
        split["sensor"],
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::camera_payload",
        "SOURCE_BOUND_ANALYTIC_PRIMITIVE",
        "PLACEHOLDER_ONLY",
        ["CAMERA_PART_NUMBER_HOLD", "OPTICAL_CALIBRATION_HOLD", "MASS_INERTIA_HOLD"],
    )
    src_arm = add_source(
        doc,
        source_library,
        "SRC_B601_ARM_CORE_Q0",
        "SRC_B601_ARM_CORE_Q0__FRAME_AXIS_WITNESS",
        arm_core,
        B601_Q0_WITNESS.relative_to(PROJECT_ROOT).as_posix(),
        "KINEMATIC_FRAME_AND_AXIS_WITNESS",
        "FRAME_TREE_WITNESS_NOT_ARM_ENVELOPE_NOT_VENDOR_BREP",
        ["B601_PHYSICAL_GEOMETRY_HOLD", "PHYSICAL_FITUP_HOLD", "CONTINUOUS_COLLISION_HOLD"],
    )
    m3r_shape = load_shape_from_step(doc, M3R_STEP)
    src_m3r = add_source(
        doc,
        source_library,
        "SRC_M3R_INTERFACE_ASSEMBLY",
        "SRC_M3R_INTERFACE_ASSEMBLY__WORKING_BREP",
        m3r_shape,
        M3R_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "M3_PARAMETERIZED_WORKING_BREP",
        "WORKING_DETAILED_DESIGN_NOT_RELEASED",
        ["B601_PHYSICAL_FITUP_HOLD", "LOAD_BRIDGE_FITUP_HOLD", "TOLERANCE_AND_FASTENER_HOLD"],
    )
    gripper_shape = load_shape_from_step(doc, GRIPPER_R1_STEP)
    src_gripper = add_source(
        doc,
        source_library,
        "SRC_GRIPPER_R1_PALM",
        "SRC_GRIPPER_R1_PALM__CORRECTED_NEUTRAL_BREP",
        gripper_shape,
        GRIPPER_R1_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "VERIFIED_NEUTRAL_DERIVATIVE_BREP",
        "PALM_ONLY_INTEGRATION_OVERLAY",
        ["FINGER_BREP_SEPARATION_HOLD", "CONTACT_LOAD_HOLD", "MANUFACTURING_CLEARANCE_HOLD"],
    )
    hdrm_shape = load_shape_from_step(doc, HDRM_SKELETON_STEP)
    src_hdrm = add_source(
        doc,
        source_library,
        "SRC_ARM_HDRM_SKELETON",
        "SRC_ARM_HDRM_SKELETON__NON_PHYSICAL",
        hdrm_shape,
        HDRM_SKELETON_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "NON_PHYSICAL_HOLD_SKELETON_ONLY",
        "UNRESOLVED_NOT_INSTALLED",
        ["HDRM_GLOBAL_TRANSFORM_HOLD", "HDRM_PRODUCT_AND_TEST_HOLD", "FLIGHT_HDRM_HOLD"],
    )
    target_sat_shape = build_model_spec_shape("target_satellite_v0", "FUSED")
    src_target_sat = add_source(
        doc,
        scenario_group,
        "SRC_TARGET_SATELLITE_22KG",
        "SRC_TARGET_SATELLITE_22KG__SCENARIO_PROXY",
        target_sat_shape,
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::target_satellite_v0.primitives",
        "SCENARIO_PROXY_SOURCE_BOUND_ANALYTIC_PRIMITIVES_MM",
        "NOT_INSTALLED_TARGET_ASSET",
        ["RELATIVE_POSE_HOLD", "CONTACT_INTERFACE_HOLD"],
    )
    target_debris_shape = build_model_spec_shape(
        "target_debris_v0", "EXACT_PRIMITIVE_COMPOUND"
    )
    src_target_debris = add_source(
        doc,
        scenario_group,
        "SRC_TARGET_DEBRIS_150KG",
        "SRC_TARGET_DEBRIS_150KG__SCENARIO_PROXY",
        target_debris_shape,
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::target_debris_v0.primitives",
        "SCENARIO_PROXY_SOURCE_BOUND_EXACT_PRIMITIVE_COMPOUND_MM",
        "NOT_INSTALLED_TARGET_ASSET",
        [
            "RELATIVE_POSE_HOLD",
            "CONTACT_INTERFACE_HOLD",
            "BOOLEAN_UNION_HOLD_TANGENT_MARKER_BRACKET",
        ],
    )

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

    installed_links = []
    for name, source, matrix, status in installed_specs:
        link = add_link(
            doc,
            installed_group,
            name,
            name,
            source,
            matrix,
            status,
            "DEFAULT_DEPLOYED_NOMINAL_ARM_TASK_READY_DIGITAL_PROTOTYPE",
            ["NO_SYSTEM_INTERFERENCE_RELEASE", "NO_MASS_FROM_BREP"],
            True,
        )
        installed_links.append(link)

    add_slot(
        doc,
        unresolved_group,
        "SLOT_SPACECRAFT_LOAD_BRIDGE__UNRESOLVED",
        M3R_PHYSICAL_STACK.relative_to(PROJECT_ROOT).as_posix(),
        "BUS_OUTER_FACE_X_185_25_TO_M3R_MIN_X_APPROX_196_LOAD_PATH_NULL",
        "The M3R working B-rep is correctly placed from its x=208 mm physical installation face, but the bus proxy ends at x=185.25 mm and no authorized load-bridge/mating structure spans the geometric gap.",
        [
            "SPACECRAFT_LOAD_BRIDGE_GEOMETRY_HOLD",
            "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD",
            "MATING_FASTENER_AND_TOLERANCE_HOLD",
        ],
    )
    add_slot(
        doc,
        unresolved_group,
        "SLOT_SENSOR_PACKAGE__UNRESOLVED",
        MODEL_SPECS.relative_to(PROJECT_ROOT).as_posix() + "::camera_payload",
        "CANDIDATE_T_S_SENSOR_REJECTED_BY_NARROW_PHASE",
        "The source-bound camera placeholder at [190.25,0,80] mm penetrates the installed M3R working B-rep; no replacement pose is authorized.",
        ["SENSOR_PACKAGE_SELECTION_HOLD", "M3R_SENSOR_INTERFERENCE_HOLD", "OPTICAL_CALIBRATION_HOLD"],
    )
    add_slot(
        doc,
        unresolved_group,
        "SLOT_ARM_HDRM__UNRESOLVED",
        HDRM_SKELETON_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "GLOBAL_TRANSFORM_NULL",
        "Controlling authority keeps flange global transform and clocking on hard hold.",
        ["HDRM_GLOBAL_TRANSFORM_HOLD", "HDRM_FUNCTIONAL_TEST_HOLD"],
    )
    add_slot(
        doc,
        unresolved_group,
        "SLOT_TARGET_INTERFACE__UNRESOLVED",
        "20_engineering/config/geometry/capture_interface_v1.yaml",
        "T_S_TARGET_NULL",
        "Target is a scenario asset, not an installed spacecraft component; no relative capture pose is frozen.",
        ["TARGET_RELATIVE_POSE_HOLD", "CONTACT_GEOMETRY_HOLD"],
    )
    add_slot(
        doc,
        unresolved_group,
        "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED",
        GRIPPER_R1_STEP.relative_to(PROJECT_ROOT).as_posix(),
        "PALM_BOUND_FINGERS_NOT_AVAILABLE_AS_VALID_BREP",
        "R1 source closes the palm rail-slot geometry only; complete separated finger B-reps are not released.",
        ["FINGER_BREP_SEPARATION_HOLD", "PREGRASP_CONTACT_HOLD"],
    )

    config = doc.addObject("App::FeaturePython", "CONFIGURATION_REGISTER")
    config.Label = "CONFIGURATION_REGISTER__NINE_REQUIRED_STATES"
    add_string(config, "ActiveGeometryConfiguration", "DEPLOYED_NOMINAL__ARM_TASK_READY")
    add_string_list(
        config,
        "RequiredConfigurations",
        [
            "DEPLOYED_NOMINAL",
            "LEFT_PANEL_FAIL",
            "RIGHT_PANEL_FAIL",
            "BOTH_PANEL_FAIL",
            "ARM_STOWED_ONORBIT",
            "ARM_TASK_READY",
            "PREGRASP",
            "TARGET_CAPTURE_22KG",
            "TARGET_CAPTURE_150KG",
        ],
    )
    add_string_list(
        config,
        "GeometryState",
        [
            "DEPLOYED_NOMINAL=ACTIVE_GEOMETRY",
            "LEFT_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN",
            "RIGHT_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN",
            "BOTH_PANEL_FAIL=HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN",
            "ARM_STOWED_ONORBIT=SOURCE_WITNESS_EXISTS_NOT_EMBEDDED_AS_ACTIVE_CONFIG",
            "ARM_TASK_READY=ACTIVE_Q0_GEOMETRY",
            "PREGRASP=PALM_ONLY_FINGER_BREP_HOLD",
            "TARGET_CAPTURE_22KG=TARGET_SOURCE_EMBEDDED_RELATIVE_POSE_HOLD",
            "TARGET_CAPTURE_150KG=TARGET_SOURCE_EMBEDDED_RELATIVE_POSE_HOLD",
        ],
    )
    top.addObject(config)

    set_visibility(source_library, False)
    set_visibility(scenario_group, False)
    set_visibility(unresolved_group, False)
    set_visibility(installed_group, True)
    doc.recompute()

    # Installed source geometry is composed explicitly for deterministic export.
    installed_shapes = [transformed_shape(source, matrix) for _, source, matrix, _ in installed_specs]
    installed_shape_map = {
        name: shape for (name, _, _, _), shape in zip(installed_specs, installed_shapes)
    }
    pairwise_narrow_phase = []
    installed_names = list(installed_shape_map)
    for index, name_a in enumerate(installed_names):
        for name_b in installed_names[index + 1 :]:
            shape_a = installed_shape_map[name_a]
            shape_b = installed_shape_map[name_b]
            distance = float(shape_a.distToShape(shape_b)[0])
            common_volume = float(shape_a.common(shape_b).Volume)
            pairwise_narrow_phase.append(
                {
                    "component_a": name_a,
                    "component_b": name_b,
                    "minimum_distance_mm": round(distance, 9),
                    "common_volume_mm3": round(common_volume, 9),
                    "classification": classify_pair(name_a, name_b, common_volume, distance),
                    "acceptance_scope": "DEFAULT_CONFIGURATION_GEOMETRY_ONLY_NOT_CONTINUOUS_SWEEP",
                }
            )
    export_compound = Part.makeCompound(installed_shapes)
    export_obj = doc.addObject("Part::Feature", "STEP_EXPORT_AGGREGATE")
    export_obj.Label = "STEP_EXPORT_AGGREGATE__DEFAULT_CONFIGURATION_ONLY"
    export_obj.Shape = export_compound
    add_string(export_obj, "LifecycleStatus", "DERIVED_EXPORT_OBJECT")
    add_string(
        export_obj,
        "Composition",
        f"{len(installed_specs)}_INSTALLED_LINKS_DEFAULT_CONFIGURATION",
    )
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

    # Cold reopen validates that all App::Link targets are internal and readable.
    reopened = App.openDocument(str(OUTPUT_FCSTD))
    try:
        links = [obj for obj in reopened.Objects if obj.TypeId == "App::Link"]
        internal_links = [
            obj
            for obj in links
            if obj.LinkedObject is not None and obj.LinkedObject.Document is reopened
        ]
        source_shapes = [
            obj
            for obj in reopened.Objects
            if obj.Name.startswith("SRC_") and hasattr(obj, "Shape") and not obj.Shape.isNull()
        ]
        fcstd_reopen = {
            "object_count": len(reopened.Objects),
            "app_part_count": sum(obj.TypeId == "App::Part" for obj in reopened.Objects),
            "app_link_count": len(links),
            "all_links_internal": len(internal_links) == len(links),
            "source_shape_count": len(source_shapes),
            "all_source_shapes_valid": all(obj.Shape.isValid() for obj in source_shapes),
            "installed_link_names": [obj.Name for obj in links if obj.Name.startswith("INST_")],
        }
    finally:
        App.closeDocument(reopened.Name)

    step_doc = App.newDocument("M4_STEP_REOPEN")
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

    source_geometry_metrics = {
        "bus_12U_core": shape_metrics(split["bus"]),
        "solar_array_left": shape_metrics(split["panel_left"]),
        "solar_array_right": shape_metrics(split["panel_right"]),
        "sensor_package_placeholder": shape_metrics(split["sensor"]),
        "B601_arm_q0_frame_axis_witness": shape_metrics(arm_core),
        "M3R_interface_assembly": shape_metrics(m3r_shape),
        "gripper_R1_palm": shape_metrics(gripper_shape),
        "ARM_HDRM_hidden_skeleton": shape_metrics(hdrm_shape),
        "target_satellite_22kg_hidden_proxy": shape_metrics(target_sat_shape),
        "target_debris_150kg_hidden_proxy": shape_metrics(target_debris_shape),
    }
    geometry_checks = {
        "M3R_volume_matches_M3_receipt": abs(m3r_shape.Volume - 289750.832561) <= 1.0e-6,
        "gripper_R1_volume_matches_reopen_receipt_with_import_tolerance": abs(gripper_shape.Volume - 45088.72293792546) <= 1.0e-2,
        "left_panel_bbox_matches_source_primitive": source_geometry_metrics["solar_array_left"]["bounding_box_mm"] == [-170.25, 113.15, -3.0, 56.75, 313.15, 3.0],
        "right_panel_bbox_matches_source_primitive": source_geometry_metrics["solar_array_right"]["bounding_box_mm"] == [-170.25, -313.15, -3.0, 56.75, -113.15, 3.0],
        "target_satellite_unit_reconciled_bbox_matches_json": source_geometry_metrics["target_satellite_22kg_hidden_proxy"]["bounding_box_mm"] == [-170.0, -313.0, -113.0, 290.0, 313.0, 313.0],
        "target_debris_unit_reconciled_bbox_matches_json": source_geometry_metrics["target_debris_150kg_hidden_proxy"]["bounding_box_mm"] == [-660.0, -660.0, -1500.0, 660.0, 660.0, 1000.0],
        "target_debris_exact_primitive_compound_has_six_solids": source_geometry_metrics["target_debris_150kg_hidden_proxy"]["solids"] == 6,
        "bus_M3R_no_positive_common_volume": next(
            row["common_volume_mm3"] <= 1.0e-6
            for row in pairwise_narrow_phase
            if frozenset((row["component_a"], row["component_b"]))
            == frozenset(("INST_BUS_12U_CORE", "INST_M3R_INTERFACE_ASSEMBLY"))
        ),
        "no_unclassified_positive_overlap": not any(
            row["classification"] == "UNRESOLVED_POSITIVE_OVERLAP_HOLD"
            for row in pairwise_narrow_phase
        ),
        "step_reopen_valid": step_reopen["valid"],
        "fcstd_all_links_internal": fcstd_reopen["all_links_internal"],
        "fcstd_all_source_shapes_valid": fcstd_reopen["all_source_shapes_valid"],
    }

    pin_payload = {
        "schema": "M4_DIGITAL_PROTOTYPE_SOURCE_HASH_PINS_V1",
        "generated_utc": utc_now(),
        "records": source_records,
        "status": "PASS_ALL_SOURCES_PRESENT_AND_HASH_BOUND_AT_BUILD",
    }
    SOURCE_PINS.write_text(json.dumps(pin_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    audit_payload = {
        "schema": "M4_DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1",
        "generated_utc": utc_now(),
        "lifecycle_status": "COMPETITION_DIGITAL_PROTOTYPE_NOT_FLIGHT_NOT_MANUFACTURING",
        "composition": {
            "active_default_configuration": "DEPLOYED_NOMINAL__ARM_TASK_READY",
            "installed_component_count": len(installed_specs),
            "installed_components": [name for name, _, _, _ in installed_specs],
            "hidden_source_only": ["SRC_ARM_HDRM_SKELETON", "SRC_TARGET_SATELLITE_22KG", "SRC_TARGET_DEBRIS_150KG"],
            "explicit_overlap_semantics": "The B601 object is a frame/axis witness, not an arm envelope; any witness overlay is excluded from physical-interference interpretation. Aggregate B-rep volume is not a mass result.",
            "excluded_from_step": ["ARM_HDRM", "TARGET_SATELLITE_22KG", "TARGET_DEBRIS_150KG", "UNRESOLVED_SLOTS"],
        },
        "source_geometry": source_geometry_metrics,
        "arm_frame_axis_witness_components_q0": arm_component_metrics,
        "transforms": {
            "T_S_M_DYNAMICS": [
                [0.0, 0.0, 1.0, 185.25],
                [0.0, 1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "T_S_B601_ARM_BASE": clean_matrix(t_arm),
            "T_S_M3R_LOCAL": clean_matrix(t_m3r),
            "T_S_LINK6_Q0_FOR_GRIPPER_R1_PALM": clean_matrix(t_link6_global),
            "T_S_HDRM": None,
            "T_S_TARGET_22KG": None,
            "T_S_TARGET_150KG": None,
        },
        "placement_rulings": {
            "M3R": "Placed at the x=208.0 mm physical installation plane with +25.000014 deg clocking, not naively at the x=185.25 mm legacy M-frame/flange outer face. This preserves the physical stack and avoids silent legacy-flange replacement overlap.",
            "M_vs_arm_base_frame_semantics": "The physical-stack authority defines M_FRAME_DYNAMICS_ORIGIN at x=185.25 mm, while the frozen V5R SYSTEM_FRAME_TREE places the physical B601 arm_base_frame at x=208.0 mm. M4 preserves both transforms as distinct frames and holds any downstream aliasing until the upstream naming conflict is adjudicated.",
            "spacecraft_load_bridge": "The bus proxy terminates at x=185.25 mm while the installed M3R B-rep begins near x=196 mm. The missing mating/load-bridge structure is an explicit unresolved slot; mechanical connection and load-path continuity are not claimed.",
            "target_proxy_unit_reconciliation": "Legacy target STEP files declare mm while carrying metre-valued coordinates. M4 therefore reconstructs hidden target proxies from the controlling model_specs_v0.json millimetre primitives and retains the STEP files as hash-bound sibling evidence only.",
            "target_debris_boolean_ruling": "The exact six source primitives are retained as a hidden compound. Their tangent marker bracket makes a single boolean union non-manifold; an OCCT trial expanded the bounding box incorrectly, so no fused-solid or contact-ready claim is made.",
        },
        "pairwise_narrow_phase_default_configuration": pairwise_narrow_phase,
        "checks": geometry_checks,
        "fcstd_cold_reopen": fcstd_reopen,
        "step_cold_reopen": step_reopen,
        "system_interference_verdict": "NOT_EVALUATED_NO_CONTINUOUS_OR_CONFIGURATION_COMPLETE_MODEL",
        "structural_load_path_verdict": "HOLD_SPACECRAFT_TO_M3R_LOAD_BRIDGE_GEOMETRY_ABSENT",
        "formal_fea_performed": False,
        "verdict": "PASS_DIGITAL_PROTOTYPE_GEOMETRY_WITH_EXPLICIT_RELEASE_HOLDS" if all(geometry_checks.values()) else "HOLD_GEOMETRY_VALIDATION_FAILURE",
    }
    GEOMETRY_AUDIT.write_text(json.dumps(audit_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    outputs = [OUTPUT_FCSTD, OUTPUT_STEP, SOURCE_PINS, GEOMETRY_AUDIT]
    build_payload = {
        "schema": "M4_DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1",
        "generated_utc": utc_now(),
        "builder": "FreeCADCmd / OpenCascade",
        "memory_gate": memory,
        "source_count": len(source_records),
        "source_pin_file": SOURCE_PINS.name,
        "architecture": "EMBEDDED_PART_FEATURE_SOURCE_LIBRARY_PLUS_INTERNAL_APP_LINK_INSTANCES",
        "external_file_references_in_master": False,
        "default_configuration": "DEPLOYED_NOMINAL__ARM_TASK_READY",
        "installed_component_count": len(installed_specs),
        "unresolved_component_slots": [
            "SLOT_SPACECRAFT_LOAD_BRIDGE__UNRESOLVED",
            "SLOT_SENSOR_PACKAGE__UNRESOLVED",
            "SLOT_ARM_HDRM__UNRESOLVED",
            "SLOT_TARGET_INTERFACE__UNRESOLVED",
            "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED",
        ],
        "fcstd_cold_reopen": fcstd_reopen,
        "step_cold_reopen": step_reopen,
        "all_geometry_checks_pass": all(geometry_checks.values()),
        "formal_fea_performed": False,
        "outputs": [
            {
                "path": path.relative_to(M4_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in outputs
        ],
        "explicit_holds": [
            "HDRM_GLOBAL_TRANSFORM_AND_FUNCTIONAL_TEST_HOLD",
            "SPACECRAFT_TO_M3R_LOAD_BRIDGE_AND_LOAD_PATH_CONTINUITY_HOLD",
            "M_DYNAMICS_VS_PHYSICAL_ARM_BASE_FRAME_ALIAS_RECONCILIATION_HOLD",
            "TARGET_RELATIVE_CAPTURE_POSE_AND_CONTACT_GEOMETRY_HOLD",
            "TARGET_DEBRIS_TANGENT_MARKER_BRACKET_BOOLEAN_UNION_HOLD",
            "GRIPPER_R1_SEPARATED_FINGER_BREP_AND_CONTACT_HOLD",
            "SOLAR_ARRAY_STOWED_GEOMETRY_AND_HINGE_KINEMATICS_HOLD",
            "SYSTEM_CONTINUOUS_COLLISION_AND_INTERFERENCE_HOLD",
            "MASS_INERTIA_MATERIAL_TOLERANCE_AND_LOADS_HOLD",
            "MANUFACTURING_FLIGHT_LAUNCH_QUALIFICATION_HOLD",
        ],
        "verdict": "M4_MASTER_DIGITAL_PROTOTYPE_BUILD_PASS_WITH_RELEASE_HOLDS" if all(geometry_checks.values()) else "M4_MASTER_DIGITAL_PROTOTYPE_BUILD_HOLD",
    }
    BUILD_RECEIPT.write_text(json.dumps(build_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": build_payload["verdict"], "fcstd": str(OUTPUT_FCSTD), "step": str(OUTPUT_STEP), "memory_gate": memory}, ensure_ascii=False))


main()
