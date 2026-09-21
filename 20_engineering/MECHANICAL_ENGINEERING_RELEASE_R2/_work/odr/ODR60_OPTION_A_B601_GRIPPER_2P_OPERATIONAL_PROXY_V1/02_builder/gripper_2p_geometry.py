"""Source-bound B601 gripper geometry and deterministic artifact helpers.

This module deliberately separates three authorities:

* accepted URDF: link frames, masses, joint axes and numeric travel limits;
* R1/neutral STEP: nominal design BRep geometry;
* M01 system authority: not granted by this local package.

All OpenCascade geometry is expressed in millimetres.  URDF translations and
joint travel enter in metres and are converted exactly once at the OCP boundary.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import (
    STEPControl_AsIs,
    STEPControl_Reader,
    STEPControl_Writer,
)
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Trsf
from scipy.optimize import linear_sum_assignment


PACKAGE = Path(__file__).resolve().parents[1]
CONTRACT_DIR = PACKAGE / "00_contract"
CAD_ASSETS = PACKAGE / "01_cad"
RUNTIME_ASSETS = PACKAGE / "02_runtime"
RESULTS = PACKAGE / "05_results"

CONTRACT_PATH = CONTRACT_DIR / "GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "URDF_FRAME_AND_STATE_LEDGER_V1.json"

ACCEPTED_URDF_REL = Path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
NEUTRAL_STEP_REL = Path(
    "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
    "vendor_reference_linklocal/B50_REF_gripper_detail_LINKLOCAL.step"
)
V5_RECEIPT_REL = Path(
    "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/"
    "13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"
)
ASSIGNMENT_REL = Path(
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
    "08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
)
R1_PALM_STEP_REL = Path(
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
    "01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step"
)
R1_VALIDATION_REL = Path(
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
    "04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"
)
R1_LEFT_STL_REL = Path(
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
    "01_native_cad/gripper_r1/B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl"
)
R1_RIGHT_STL_REL = Path(
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
    "01_native_cad/gripper_r1/B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl"
)
M5_FRAME_DECISION_REL = Path(
    "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
    "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json"
)
M5_SURFACE_DIR_REL = Path(
    "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
    "01_geometry_authority/assets/b601_link_local_surfaces"
)

OBJECTS: dict[str, dict[str, Any]] = {
    "gripper_link": {
        "object_id": "A::gripper_link",
        "frame": "gripper_link",
        "source_group": "gripper_link",
        "step_name": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1.step",
        "runtime_stem": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_M_V1",
        "receipt_name": "B601_GRIPPER_LINK_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "m5_surface": "B601_GRIPPER_R1_PALM_GRIPPER_LINK_LOCAL_M.ply",
        "expected_solid_count": 12,
    },
    "gripper_left": {
        "object_id": "A::gripper_left",
        "frame": "gripper_left",
        "source_group": "gripper_left",
        "step_name": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1.step",
        "runtime_stem": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_M_V1",
        "receipt_name": "B601_GRIPPER_LEFT_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "joint": "gripper_joint1",
        "m5_surface": "B601_GRIPPER_R1_LEFT_FINGER_GRIPPER_LINK_LOCAL_M.ply",
        "expected_solid_count": 24,
    },
    "gripper_right": {
        "object_id": "A::gripper_right",
        "frame": "gripper_right",
        "source_group": "gripper_right",
        "step_name": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1.step",
        "runtime_stem": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_M_V1",
        "receipt_name": "B601_GRIPPER_RIGHT_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "joint": "gripper_joint2",
        "m5_surface": "B601_GRIPPER_R1_RIGHT_FINGER_GRIPPER_LINK_LOCAL_M.ply",
        "expected_solid_count": 24,
    },
}

LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = 0.10
VERTEX_ROUND_DECIMALS_M = 12
STEP_NUMERIC_DERATE_MM = 1.0e-6
STEP_BBOX_REOPEN_TOLERANCE_MM = 2.0e-4
STEP_VOLUME_REL_TOLERANCE = 2.0e-8
Q_MIN_M = 0.0
Q_MAX_M = 0.0715


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def strict_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    require(path.is_file(), f"required JSON missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def byte_record(path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def _walk_pin_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        for child in value.values():
            yield from _walk_pin_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_pin_records(child)


def source_pin(lock: dict[str, Any], relative: Path) -> dict[str, Any]:
    key = relative.as_posix()
    matches = [row for row in _walk_pin_records(lock) if str(row["path"]).replace("\\", "/") == key]
    require(len(matches) == 1, f"source lock must contain exactly one pin for {key}; got {len(matches)}")
    return matches[0]


def verify_source_pin(lock: dict[str, Any], relative: Path) -> dict[str, Any]:
    pin = source_pin(lock, relative)
    path = workspace_root() / relative
    require(path.is_file(), f"pinned source missing: {relative.as_posix()}")
    require(path.stat().st_size == int(pin["bytes"]), f"pinned source byte drift: {relative.as_posix()}")
    require(sha256_path(path) == str(pin["sha256"]), f"pinned source hash drift: {relative.as_posix()}")
    return pin


def verify_all_source_pins(lock: dict[str, Any]) -> int:
    records = list(_walk_pin_records(lock))
    require(records, "source lock contains no file pins")
    root = workspace_root()
    seen: set[str] = set()
    for row in records:
        relative = str(row["path"]).replace("\\", "/")
        require(relative not in seen, f"duplicate source pin path: {relative}")
        seen.add(relative)
        path = Path(relative)
        full = path if path.is_absolute() else root / path
        require(full.is_file(), f"pinned file missing: {relative}")
        require(full.stat().st_size == int(row["bytes"]), f"pinned file byte drift: {relative}")
        require(sha256_path(full) == str(row["sha256"]), f"pinned file hash drift: {relative}")
    return len(records)


def read_step(path: Path):
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path}")
    transferred = int(reader.TransferRoots())
    require(transferred >= 1, f"STEP transferred no roots: {path}")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP transferred a null shape: {path}")
    return shape


def bbox_mm(shape) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def solids(shape) -> list[Any]:
    result: list[Any] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        result.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    return result


def solid_rows(shape) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for solid in solids(shape):
        face_explorer = TopExp_Explorer(solid, TopAbs_FACE)
        face_count = 0
        while face_explorer.More():
            face_count += 1
            face_explorer.Next()
        shell_explorer = TopExp_Explorer(solid, TopAbs_SHELL)
        shell_count = 0
        shells_closed = True
        while shell_explorer.More():
            shell_count += 1
            shells_closed &= bool(BRep_Tool.IsClosed_s(shell_explorer.Current()))
            shell_explorer.Next()
        rows.append(
            {
                "shape": solid,
                "bbox_mm": bbox_mm(solid),
                "volume_mm3": volume_mm3(solid),
                "brep_valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
                "face_count": face_count,
                "shell_count": shell_count,
                "all_shells_closed": bool(shell_count > 0 and shells_closed),
            }
        )
    return rows


def make_compound(children: Iterable[Any]):
    shapes = list(children)
    require(shapes, "cannot create an empty gripper compound")
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def rpy_matrix(rpy_rad: Iterable[float]) -> np.ndarray:
    roll, pitch, yaw = (float(value) for value in rpy_rad)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.asarray(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )


def homogeneous(rotation: np.ndarray, translation_mm: np.ndarray) -> np.ndarray:
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = rotation
    result[:3, 3] = translation_mm
    return result


def parse_urdf_contract() -> dict[str, Any]:
    path = workspace_root() / ACCEPTED_URDF_REL
    root = ElementTree.parse(path).getroot()
    links = {node.attrib["name"]: node for node in root.findall("link")}
    joints = {node.attrib["name"]: node for node in root.findall("joint")}
    required_links = {"gripper_link", "gripper_left", "gripper_right"}
    require(required_links.issubset(links), "accepted URDF is missing one or more gripper links")
    result: dict[str, Any] = {"links": {}, "joints": {}}
    for name in sorted(required_links):
        mass_node = links[name].find("./inertial/mass")
        require(mass_node is not None, f"accepted URDF link has no mass: {name}")
        result["links"][name] = {"mass_kg": float(mass_node.attrib["value"])}
    for name, child in (("gripper_joint1", "gripper_left"), ("gripper_joint2", "gripper_right")):
        joint = joints.get(name)
        require(joint is not None, f"accepted URDF joint missing: {name}")
        require(joint.attrib.get("type") == "prismatic", f"joint is not prismatic: {name}")
        require(joint.find("parent").attrib["link"] == "gripper_link", f"joint parent drift: {name}")
        require(joint.find("child").attrib["link"] == child, f"joint child drift: {name}")
        origin = joint.find("origin")
        axis_node = joint.find("axis")
        limit = joint.find("limit")
        require(origin is not None and axis_node is not None and limit is not None, f"joint fields missing: {name}")
        xyz_m = np.fromstring(origin.attrib["xyz"], sep=" ", dtype=np.float64)
        rpy_rad = np.fromstring(origin.attrib["rpy"], sep=" ", dtype=np.float64)
        axis_joint = np.fromstring(axis_node.attrib["xyz"], sep=" ", dtype=np.float64)
        require(xyz_m.shape == rpy_rad.shape == axis_joint.shape == (3,), f"joint vector shape drift: {name}")
        lower_m = float(limit.attrib["lower"])
        upper_m = float(limit.attrib["upper"])
        require(lower_m == Q_MIN_M and upper_m == Q_MAX_M, f"joint travel limit drift: {name}")
        require(np.array_equal(axis_joint, np.asarray([1.0, 0.0, 0.0])), f"joint axis drift: {name}")
        rotation = rpy_matrix(rpy_rad)
        parent_from_child_mm = homogeneous(rotation, xyz_m * 1000.0)
        result["joints"][name] = {
            "parent": "gripper_link",
            "child": child,
            "origin_xyz_m": xyz_m.tolist(),
            "origin_rpy_rad": rpy_rad.tolist(),
            "axis_joint": axis_joint.tolist(),
            "axis_parent": (rotation @ axis_joint).tolist(),
            "lower_m": lower_m,
            "upper_m": upper_m,
            "T_parent_from_child_q0_mm": parent_from_child_mm.tolist(),
            "T_child_from_parent_q0_mm": np.linalg.inv(parent_from_child_mm).tolist(),
        }
    left_axis = np.asarray(result["joints"]["gripper_joint1"]["axis_parent"])
    right_axis = np.asarray(result["joints"]["gripper_joint2"]["axis_parent"])
    require(left_axis[1] < -0.999999 and right_axis[1] > 0.999999, "opposed 2P parent-frame axis signs are not preserved")
    return result


def trsf_from_matrix(matrix: np.ndarray) -> gp_Trsf:
    value = np.asarray(matrix, dtype=np.float64)
    require(value.shape == (4, 4), "OCP transform matrix must be 4x4")
    require(np.all(np.isfinite(value)), "OCP transform contains a non-finite value")
    require(np.max(np.abs(value[3] - np.asarray([0.0, 0.0, 0.0, 1.0]))) <= 1.0e-14, "invalid homogeneous row")
    transform = gp_Trsf()
    transform.SetValues(*(float(value[row, column]) for row in range(3) for column in range(4)))
    return transform


def transform_shape(shape, matrix: np.ndarray):
    operation = BRepBuilderAPI_Transform(shape, trsf_from_matrix(matrix), True)
    operation.Build()
    require(operation.IsDone(), "OpenCascade rigid transform failed")
    result = operation.Shape()
    require(not result.IsNull(), "OpenCascade rigid transform returned a null shape")
    return result


def _center_size(box: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.mean(box, axis=0), box[1] - box[0]


def reconstruct_neutral_groups() -> dict[str, Any]:
    root = workspace_root()
    model = read_step(root / NEUTRAL_STEP_REL)
    imported = solid_rows(model)
    receipt = strict_json(root / V5_RECEIPT_REL)
    evidence = list(receipt["source_open"]["evidence"])
    require(len(imported) == len(evidence) == 57, "neutral/V5 evidence must contain exactly 57 solids")
    costs: list[list[float]] = []
    residuals: list[list[dict[str, float]]] = []
    for source in imported:
        source_center, source_size = _center_size(source["bbox_mm"])
        source_volume = float(source["volume_mm3"])
        cost_row: list[float] = []
        residual_row: list[dict[str, float]] = []
        for target in evidence:
            target_box = np.asarray(target["bbox_mm"], dtype=np.float64).reshape(2, 3)
            target_center, target_size = _center_size(target_box)
            center_delta = float(np.linalg.norm(source_center - target_center))
            size_delta = float(np.linalg.norm(source_size - target_size))
            target_volume = float(target["volume_mm3"])
            relative_volume = abs(source_volume - target_volume) / target_volume
            cost_row.append(center_delta + 0.25 * size_delta + 10.0 * abs(math.log(max(source_volume, 1.0e-12) / target_volume)))
            residual_row.append(
                {
                    "center_delta_mm": center_delta,
                    "size_delta_mm": size_delta,
                    "volume_relative": relative_volume,
                }
            )
        costs.append(cost_row)
        residuals.append(residual_row)
    source_indices, target_indices = linear_sum_assignment(costs)
    bound: dict[str, Any] = {}
    binding_rows: list[dict[str, Any]] = []
    for source_index, target_index in zip(source_indices, target_indices, strict=True):
        target = evidence[int(target_index)]
        name = str(target["mapped_source_name"])
        residual = residuals[int(source_index)][int(target_index)]
        require(residual["center_delta_mm"] <= 1.0, f"neutral center binding failed: {name}")
        require(residual["size_delta_mm"] <= 1.0, f"neutral size binding failed: {name}")
        require(residual["volume_relative"] <= 0.05, f"neutral volume binding failed: {name}")
        bound[name] = imported[int(source_index)]["shape"]
        binding_rows.append(
            {
                "source_name": name,
                "neutral_import_index": int(source_index),
                **residual,
            }
        )
    require(len(bound) == 57, "neutral/V5 binding is not one-to-one")

    grouped_names: dict[str, list[str]] = {name: [] for name in OBJECTS}
    with (root / ASSIGNMENT_REL).open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            name = str(row["solid"])
            if name.endswith("057"):
                continue
            group = str(row["assigned_body"])
            require(group in grouped_names, f"unexpected gripper assignment group: {group}")
            grouped_names[group].append(name)
    require(sorted(len(values) for values in grouped_names.values()) == [9, 24, 24], "frozen gripper group counts drifted")
    for group, names in grouped_names.items():
        require(len(names) == len(set(names)), f"duplicate source name in gripper group: {group}")
        require(all(name in bound for name in names), f"unbound solid in gripper group: {group}")
    return {
        "bound": bound,
        "grouped_names": {key: sorted(values) for key, values in grouped_names.items()},
        "binding_rows": sorted(binding_rows, key=lambda row: row["source_name"]),
    }


def canonicalize_step_bytes(data: bytes) -> bytes:
    text = data.decode("latin-1")
    pattern = re.compile(r"(FILE_NAME\([^,]+,')([^']+)(')")
    text, count = pattern.subn(r"\g<1>2000-01-01T00:00:00\g<3>", text, count=1)
    require(count == 1, "STEP header timestamp could not be canonicalized")
    return text.replace("\r\n", "\n").encode("latin-1")


def write_step_bytes(shape) -> bytes:
    with tempfile.TemporaryDirectory(prefix="b601_gripper_step_") as directory:
        path = Path(directory) / "candidate.step"
        writer = STEPControl_Writer()
        require(writer.Transfer(shape, STEPControl_AsIs) == IFSelect_RetDone, "STEP transfer failed")
        require(writer.Write(str(path)) == IFSelect_RetDone, "STEP write failed")
        return canonicalize_step_bytes(path.read_bytes())


def _transform_node(point, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def extract_triangles_m(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, int]:
    triangles: list[np.ndarray] = []
    solid_ids: list[int] = []
    missing_faces = 0
    for solid_id, row in enumerate(rows):
        mesher = BRepMesh_IncrementalMesh(
            row["shape"], LINEAR_DEFLECTION_MM, False, ANGULAR_DEFLECTION_RAD, False
        )
        mesher.Perform()
        require(mesher.IsDone(), f"OpenCascade meshing failed for solid {solid_id}")
        explorer = TopExp_Explorer(row["shape"], TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face_s(explorer.Current())
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            if triangulation is None or triangulation.NbTriangles() <= 0:
                missing_faces += 1
                explorer.Next()
                continue
            nodes = np.asarray(
                [_transform_node(triangulation.Node(index), location) for index in range(1, triangulation.NbNodes() + 1)],
                dtype=np.float64,
            ) * 1.0e-3
            reverse = face.Orientation() == TopAbs_REVERSED
            for index in range(1, triangulation.NbTriangles() + 1):
                node_a, node_b, node_c = triangulation.Triangle(index).Get()
                indices = [node_a - 1, node_b - 1, node_c - 1]
                if reverse:
                    indices[1], indices[2] = indices[2], indices[1]
                triangles.append(nodes[indices])
                solid_ids.append(solid_id)
            explorer.Next()
    require(missing_faces == 0, f"{missing_faces} positive-area faces have no triangulation")
    require(triangles, "no runtime triangles were produced")
    return np.asarray(triangles, dtype=np.float64), np.asarray(solid_ids, dtype=np.uint16), missing_faces


def signed_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    triangles = vertices[faces]
    return float(
        np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6.0
    )


def canonicalize_mesh(
    triangles_m: np.ndarray, solid_ids: np.ndarray, solid_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    flat = np.round(triangles_m.reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    cross = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    degenerate = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
        | (np.linalg.norm(cross, axis=1) <= 1.0e-16)
    )
    removed = int(np.count_nonzero(degenerate))
    if removed:
        faces = faces[~degenerate]
        solid_ids = solid_ids[~degenerate]
    flipped: list[int] = []
    duplicate_count = 0
    for solid_id in range(solid_count):
        selection = np.flatnonzero(solid_ids == solid_id)
        require(bool(len(selection)), f"runtime solid {solid_id} emitted no triangles")
        volume = signed_volume_m3(vertices, faces[selection])
        require(math.isfinite(volume) and abs(volume) > 1.0e-18, f"runtime solid {solid_id} has zero/nonfinite volume")
        if volume < 0.0:
            faces[selection, 1], faces[selection, 2] = faces[selection, 2].copy(), faces[selection, 1].copy()
            flipped.append(solid_id)
        keys = np.sort(faces[selection], axis=1)
        keys = keys[np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))]
        duplicate_count += int(np.count_nonzero(np.all(keys[1:] == keys[:-1], axis=1)))
    require(duplicate_count == 0, f"within-solid duplicate runtime triangles: {duplicate_count}")
    minimum_position = np.argmin(faces, axis=1)
    rotated = np.empty_like(faces)
    for position in range(3):
        selection = minimum_position == position
        rotated[selection] = faces[selection][:, [position, (position + 1) % 3, (position + 2) % 3]]
    faces = rotated
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], solid_ids))
    return (
        vertices.astype("<f8"),
        faces[order].astype("<u4"),
        solid_ids[order].astype("<u2"),
        {
            "removed_zero_area_triangle_count": removed,
            "within_solid_duplicate_triangle_count": duplicate_count,
            "outward_winding_flipped_solid_ids": flipped,
        },
    )


def manifold_metrics(faces: np.ndarray, solid_ids: np.ndarray, solid_count: int) -> dict[str, Any]:
    boundary = 0
    nonmanifold = 0
    orientation_mismatch = 0
    for solid_id in range(solid_count):
        local = faces[solid_ids == solid_id].astype(np.int64)
        directed = np.concatenate((local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0)
        undirected = np.sort(directed, axis=1)
        unique_edges, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
        boundary += int(np.count_nonzero(counts == 1))
        nonmanifold += int(np.count_nonzero(counts > 2))
        forward = np.bincount(
            inverse,
            weights=(directed[:, 0] < directed[:, 1]).astype(np.int8),
            minlength=len(unique_edges),
        )
        orientation_mismatch += int(np.count_nonzero(forward != counts - forward))
    require(boundary == 0, f"runtime boundary edge count is {boundary}")
    require(nonmanifold == 0, f"runtime nonmanifold edge count is {nonmanifold}")
    require(orientation_mismatch == 0, f"runtime orientation mismatch edge count is {orientation_mismatch}")
    return {
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_mismatch_edge_count": orientation_mismatch,
        "per_solid_closed": True,
        "per_solid_consistently_oriented": True,
    }


def npy_bytes(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(stream, np.asarray(array), allow_pickle=False)
    return stream.getvalue()


def deterministic_npz(arrays: dict[str, np.ndarray]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, npy_bytes(arrays[name]))
    return stream.getvalue()


def binary_stl(vertices_m: np.ndarray, faces: np.ndarray, frame: str) -> bytes:
    header = f"B601 GRIPPER 2P OPERATIONAL CANDIDATE V1; UNITS=M; FRAME={frame}".encode("ascii")
    output = io.BytesIO()
    output.write(header[:80].ljust(80, b"\0"))
    output.write(struct.pack("<I", int(len(faces))))
    triangles = vertices_m[faces].astype(np.float64)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    norms = np.linalg.norm(normals, axis=1)
    require(bool(np.all(norms > 0.0)), "runtime STL contains a degenerate triangle")
    normals /= norms[:, None]
    for normal, triangle in zip(normals.astype("<f4"), triangles.astype("<f4"), strict=True):
        output.write(struct.pack("<12fH", *(normal.tolist() + triangle.reshape(-1).tolist()), 0))
    return output.getvalue()


def binary_ply(vertices_m: np.ndarray, faces: np.ndarray, frame: str) -> bytes:
    """Return a deterministic little-endian binary PLY in owning-link metres."""

    require(int(faces.max()) < len(vertices_m), "runtime PLY face index overflow")
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment B601_GRIPPER_2P_OPERATIONAL_PROXY_V1\n"
        "comment units=m\n"
        f"comment frame={frame}\n"
        f"element vertex {len(vertices_m)}\n"
        "property double x\n"
        "property double y\n"
        "property double z\n"
        f"element face {len(faces)}\n"
        "property list uchar uint vertex_indices\n"
        "end_header\n"
    ).encode("ascii")
    output = io.BytesIO()
    output.write(header)
    output.write(np.asarray(vertices_m, dtype="<f8").tobytes(order="C"))
    for face in np.asarray(faces, dtype="<u4"):
        output.write(struct.pack("<BIII", 3, int(face[0]), int(face[1]), int(face[2])))
    return output.getvalue()


def validate_numeric_joint_state(state: dict[str, Any]) -> tuple[float, float]:
    require(set(state) == {"gripper_joint1_m", "gripper_joint2_m"}, "numeric 2P state requires exactly two metre-valued joints")
    values: list[float] = []
    for name in ("gripper_joint1_m", "gripper_joint2_m"):
        value = state[name]
        require(not isinstance(value, bool) and isinstance(value, (int, float)), f"joint state is not numeric: {name}")
        numeric = float(value)
        require(math.isfinite(numeric), f"joint state is non-finite: {name}")
        require(Q_MIN_M <= numeric <= Q_MAX_M, f"joint state is outside accepted URDF limits: {name}")
        values.append(numeric)
    return values[0], values[1]


def validate_runtime_metadata(metadata: dict[str, Any], object_name: str) -> None:
    spec = OBJECTS[object_name]
    require(metadata.get("units") == "m", "runtime geometry units must be m")
    require(metadata.get("frame") == spec["frame"], "runtime geometry frame mismatch")
    require(metadata.get("object_id") == spec["object_id"], "runtime geometry object id mismatch")
    require(metadata.get("transform_application_count") == 1, "finger frame transform must be applied exactly once")


def apply_transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(points, dtype=np.float64)
    return values @ matrix[:3, :3].T + matrix[:3, 3]
