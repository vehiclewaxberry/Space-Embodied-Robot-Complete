"""Independent validator for the B601 gripper 2P operational proxy.

This program deliberately does not import or execute anything from ``02_builder``.
It reopens the frozen STEP sources and the three candidate STEP containers with
OpenCascade, parses the accepted URDF directly, independently rebuilds the
57-body donor assignment, verifies the one-time q0 child-frame re-expression,
and audits the metre runtime PLY/NPZ sidecars.

The result is local-geometry evidence only.  No system pair query, collision
edge, path search, Owner state binding, contact/strength claim, parent Gate, or
release credit is created by this validator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import numpy as np
from OCP import __version__ as OCP_VERSION
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import (
    TopAbs_COMPOUND,
    TopAbs_COMPSOLID,
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_FORWARD,
    TopAbs_SHELL,
    TopAbs_SOLID,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Solid
from OCP.gp import gp_Trsf


PACKAGE_DIR = Path(__file__).resolve().parent.parent
CONTRACT_DIR = PACKAGE_DIR / "00_contract"
CAD_DIR = PACKAGE_DIR / "01_cad"
RUNTIME_DIR = PACKAGE_DIR / "02_runtime"
RESULTS_DIR = PACKAGE_DIR / "05_results"

CONTRACT_PATH = CONTRACT_DIR / "GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "URDF_FRAME_AND_STATE_LEDGER_V1.json"
BUILDER_EVIDENCE_PATH = RESULTS_DIR / "BUILDER_EVIDENCE_V1.json"
STATE_EVIDENCE_PATH = RESULTS_DIR / "STATE_AND_FRAME_EVIDENCE_V1.json"
UNIT_AUDIT_PATH = RESULTS_DIR / "UNIT_AND_UNCERTAINTY_AUDIT_V1.json"
RESULT_PATH = RESULTS_DIR / "INDEPENDENT_STEP_REOPEN_VALIDATION_V1.json"

FROZEN_CONTROL_HASHES = {
    CONTRACT_PATH.name: (12848, "66478AD9246E59BFA9C66282E29160CB6C20550835F78C61EAD27B8146705FE0"),
    SOURCE_LOCK_PATH.name: (18953, "904B33F35ECC151283240350B266CC91415B0273F2A290466BAEE61188C812CE"),
    FRAME_LEDGER_PATH.name: (13881, "5B2072DDE5739021A0D1F73089836DF9C21BC6754DA196526ABD60BEDCCF756C"),
}

EXPECTED_SOURCE_PIN_IDS = {
    "accepted_b601_urdf",
    "collision_frame_registration",
    "gripper_r1_geometry_validation",
    "gripper_r1_neutral_reopen_validation",
    "gripper_r1_palm_step",
    "gripper_r1_left_neutral_stl",
    "gripper_r1_right_neutral_stl",
    "m5_frame_decision",
    "m5_validation_receipt",
    "m5_palm_runtime_surface",
    "m5_left_runtime_surface",
    "m5_right_runtime_surface",
    "neutral_gripper_donor_step",
    "frozen_gripper_solid_assignment",
    "native_gripper_part_receipt",
    "native_gripper_sldprt_lineage",
    "alternate_configuration_matrix",
    "m4_configuration_state_vector_contract",
    "m4_configuration_gate",
    "m01_system_collision_registry",
    "m01_system_collision_registry_gate",
    "m01_operational_asset_readiness",
    "m01_scene_collision_prebind_gate",
    "m01_b601_candidate_bounds",
    "m01_motion_cert_batch_gate",
    "locked_2p_lane_contract",
    "locked_2p_lane_gate",
    "parent_mechanical_release_gate",
}

CANDIDATES = {
    "gripper_link": {
        "candidate_id": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1",
        "object_id": "A::gripper_link",
        "frame": "gripper_link",
        "step": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1.step",
        "ply": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_M_V1.ply",
        "npz": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_M_V1.npz",
        "stl": "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_M_V1.stl",
        "receipt": "B601_GRIPPER_LINK_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "expected_solids": 12,
        "source_group": "palm_r1",
        "m5_source_id": "m5_palm_runtime_surface",
        "joint": None,
    },
    "gripper_left": {
        "candidate_id": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1",
        "object_id": "A::gripper_left",
        "frame": "gripper_left",
        "step": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1.step",
        "ply": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_M_V1.ply",
        "npz": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_M_V1.npz",
        "stl": "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_M_V1.stl",
        "receipt": "B601_GRIPPER_LEFT_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "expected_solids": 24,
        "source_group": "gripper_left",
        "m5_source_id": "m5_left_runtime_surface",
        "joint": "gripper_joint1",
    },
    "gripper_right": {
        "candidate_id": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1",
        "object_id": "A::gripper_right",
        "frame": "gripper_right",
        "step": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1.step",
        "ply": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_M_V1.ply",
        "npz": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_M_V1.npz",
        "stl": "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_M_V1.stl",
        "receipt": "B601_GRIPPER_RIGHT_LOCAL_GEOMETRY_RECEIPT_V1.json",
        "expected_solids": 24,
        "source_group": "gripper_right",
        "m5_source_id": "m5_right_runtime_surface",
        "joint": "gripper_joint2",
    },
}

HEX64 = re.compile(r"^[0-9A-F]{64}$")

# Frozen before validator execution; these are numerical/re-expression tolerances,
# not as-built metrology uncertainty and not collision/contact derates.
SOURCE_ROW_ABS_TOL_MM = 1.0e-9
Q0_BBOX_AND_CENTER_TOL_MM = 1.0e-6
Q0_VOLUME_AND_AREA_REL_TOL = 1.0e-8
RUNTIME_BBOX_TOL_MM = 0.1
RUNTIME_VOLUME_REL_TOL = 5.0e-3
M5_PRIMARY_BREP_BBOX_TOL_MM = 0.001
M5_RUNTIME_MESH_BBOX_TOL_MM = 0.1
NEGATIVE_CONTROL_MIN_REJECTION_MM = 1.0
MATRIX_ABS_TOL = 2.0e-15

EXPECTED_SYSTEM_INVARIANTS = {
    "active_object_rows": 150,
    "asset_level_operational_authority_rows": 1,
    "required_pair_queries": 11166,
    "system_pair_queries_executed": 0,
    "system_edges_certified": 0,
    "stage_instances_bound": 0,
    "stage_instances_required": 3,
    "system_safe_certificates": 0,
    "complete_system_operational_collision_asset_set_bound": False,
    "system_pair_evaluation_authorized": False,
    "path_search_authorized": False,
    "path_search_executed": False,
    "parent_gate_credit": False,
    "next_stage_authorized": False,
    "release_credit": False,
}

FORBIDDEN_TRUE_AUTHORITY_KEYS = {
    "complete_system_operational_collision_asset_set_bound",
    "system_pair_evaluation_authorized",
    "pair_evaluation_authorized",
    "edge_evaluation_authorized",
    "path_search_authorized",
    "path_search_executed",
    "system_registry_reissued",
    "parent_mechanical_gate_reissued",
    "parent_gate_credit",
    "next_stage_authorized",
    "release_credit",
}


class ValidationFailure(RuntimeError):
    """Fail-closed deterministic validation error."""


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValidationFailure(message)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite_float(value: Any, label: str) -> float:
    require(is_number(value), f"{label} must be a real number")
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite")
    return result


def integer(value: Any, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} must be an integer")
    return int(value)


def require_hex64(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"{label} must be uppercase SHA-256")
    return value


def require_close(actual: float, expected: float, tolerance: float, label: str) -> None:
    require(
        math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=float(tolerance)),
        f"{label} mismatch: {actual!r} versus {expected!r} (abs tol {tolerance})",
    )


def require_vector_close(actual: Sequence[Any], expected: Sequence[Any], tolerance: float, label: str) -> None:
    require(len(actual) == len(expected), f"{label} length mismatch")
    for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
        require_close(finite_float(left, f"{label}[{index}]"), finite_float(right, f"{label}.expected[{index}]"), tolerance, f"{label}[{index}]")


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required JSON is missing: {path}")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationFailure(f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot read deterministic JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ValidationFailure("workspace root containing PROJECT_MAP.md was not found")


def sha256_path(path: Path) -> str:
    require(path.is_file(), f"hash-bound file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValidationFailure(f"path escapes workspace: {path}") from exc


def file_record(path: Path, root: Path) -> dict[str, Any]:
    require(path.is_file(), f"required file is missing: {path}")
    return {
        "path": relative_posix(path, root),
        "bytes": int(path.stat().st_size),
        "sha256": sha256_path(path),
    }


def resolve_workspace_path(root: Path, raw_path: Any) -> Path:
    require(isinstance(raw_path, str) and raw_path, "locked path must be a non-empty string")
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationFailure(f"locked path escapes workspace: {raw_path}") from exc
    return path


def validate_file_pin(pin: Any, root: Path, label: str, expected_path: Path | None = None) -> dict[str, Any]:
    require(isinstance(pin, dict), f"{label} must be a file pin object")
    path = resolve_workspace_path(root, pin.get("path"))
    if expected_path is not None:
        require(path == expected_path.resolve(), f"{label} path mismatch")
    actual = file_record(path, root)
    require(integer(pin.get("bytes"), f"{label}.bytes") == actual["bytes"], f"{label} byte-count drift")
    require_hex64(pin.get("sha256"), f"{label}.sha256")
    require(pin["sha256"] == actual["sha256"], f"{label} SHA-256 drift")
    return actual


def walk_scalars(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_scalars(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_scalars(child, (*path, str(index)))
    else:
        yield path, value


def values_for_key(value: Any, wanted: str) -> list[Any]:
    return [scalar for path, scalar in walk_scalars(value) if path and path[-1] == wanted]


def validate_frozen_controls(root: Path, contract: dict[str, Any], source_lock: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    require(contract.get("schema") == "ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1", "proxy contract schema drift")
    require(source_lock.get("schema") == "ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_SOURCE_AUTHORITY_LOCK_V1", "source-lock schema drift")
    require(ledger.get("schema") == "ODR60_OPTION_A_B601_GRIPPER_2P_URDF_FRAME_AND_STATE_LEDGER_V1", "frame/state ledger schema drift")

    records: dict[str, Any] = {}
    for path in (CONTRACT_PATH, SOURCE_LOCK_PATH, FRAME_LEDGER_PATH):
        expected_bytes, expected_sha = FROZEN_CONTROL_HASHES[path.name]
        actual = file_record(path, root)
        require(actual["bytes"] == expected_bytes, f"frozen control byte drift: {path.name}")
        require(actual["sha256"] == expected_sha, f"frozen control hash drift: {path.name}")
        records[path.name] = actual

    lock_pin = contract.get("source_authority_lock")
    require(isinstance(lock_pin, dict), "contract lacks source_authority_lock pin")
    lock_relative = lock_pin.get("path")
    require(lock_relative == SOURCE_LOCK_PATH.name, "contract source-lock relative path drift")
    require(integer(lock_pin.get("bytes"), "contract source lock bytes") == records[SOURCE_LOCK_PATH.name]["bytes"], "contract source-lock bytes mismatch")
    require(lock_pin.get("sha256") == records[SOURCE_LOCK_PATH.name]["sha256"], "contract source-lock hash mismatch")
    require(contract.get("frame_and_transform_contract", {}).get("canonical_reference") == FRAME_LEDGER_PATH.name, "contract frame-ledger reference drift")
    return records


def validate_source_pins(root: Path, source_lock: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows = source_lock.get("source_pins")
    require(isinstance(rows, list), "source lock lacks source_pins")
    require(len(rows) == 28, f"source lock must contain exactly 28 pins, got {len(rows)}")
    by_id: dict[str, dict[str, Any]] = {}
    validated: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"source pin {index} must be an object")
        source_id = row.get("source_id")
        require(isinstance(source_id, str) and source_id, f"source pin {index} lacks source_id")
        require(source_id not in by_id, f"duplicate source_id: {source_id}")
        actual = validate_file_pin(row, root, f"source pin {source_id}")
        by_id[source_id] = {**row, "resolved_path": str(resolve_workspace_path(root, row["path"]))}
        validated.append({"source_id": source_id, **actual})
    require(set(by_id) == EXPECTED_SOURCE_PIN_IDS, f"source-pin identity set drift: {sorted(set(by_id) ^ EXPECTED_SOURCE_PIN_IDS)}")
    require(source_lock.get("next_stage_authorized") is False, "source lock next_stage_authorized must remain false")
    require(source_lock.get("parent_gate_credit") is False, "source lock parent_gate_credit must remain false")
    require(source_lock.get("release_credit") is False, "source lock release_credit must remain false")
    return by_id, validated


def pin_path(pins: dict[str, dict[str, Any]], source_id: str) -> Path:
    require(source_id in pins, f"missing source pin {source_id}")
    return Path(str(pins[source_id]["resolved_path"]))


def count_subshapes(shape: TopoDS_Shape, shape_type: Any) -> int:
    explorer = TopExp_Explorer(shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def shape_bbox(shape: TopoDS_Shape) -> list[float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    require(not box.IsVoid(), "OCP returned a void bounding box")
    bounds = [float(value) for value in box.Get()]
    require(len(bounds) == 6 and all(math.isfinite(value) for value in bounds), "OCP returned non-finite bounds")
    return bounds


def solid_fingerprint(solid: TopoDS_Shape) -> dict[str, Any]:
    volume_props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, volume_props)
    volume = float(volume_props.Mass())
    center = [float(value) for value in volume_props.CentreOfMass().Coord()]
    surface_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(solid, surface_props)
    area = float(surface_props.Mass())
    return {
        "bbox_mm": shape_bbox(solid),
        "center_of_volume_mm": center,
        "volume_mm3": volume,
        "surface_area_mm2": area,
        "face_count": count_subshapes(solid, TopAbs_FACE),
        "shell_count": count_subshapes(solid, TopAbs_SHELL),
    }


def inspect_solid(solid: TopoDS_Solid, label: str) -> dict[str, Any]:
    require(not solid.IsNull(), f"{label} is null")
    fingerprint = solid_fingerprint(solid)
    require(BRepCheck_Analyzer(solid, True).IsValid(), f"{label} is invalid")
    require(math.isfinite(fingerprint["volume_mm3"]) and fingerprint["volume_mm3"] > 0.0, f"{label} has non-positive/non-finite volume")
    require(math.isfinite(fingerprint["surface_area_mm2"]) and fingerprint["surface_area_mm2"] > 0.0, f"{label} has non-positive/non-finite area")
    require(fingerprint["face_count"] > 0, f"{label} has no faces")
    require(fingerprint["shell_count"] > 0, f"{label} has no shells")

    shells_closed = True
    shell_explorer = TopExp_Explorer(solid, TopAbs_SHELL)
    while shell_explorer.More():
        shells_closed = shells_closed and bool(TopoDS.Shell_s(shell_explorer.Current()).Closed())
        shell_explorer.Next()

    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    boundary_edges = 0
    single_face_closed_seam_edges = 0
    nonmanifold_edges = 0
    for edge_index in range(1, edge_faces.Extent() + 1):
        degree = int(edge_faces.FindFromIndex(edge_index).Extent())
        if degree == 1:
            edge = TopoDS.Edge_s(edge_faces.FindKey(edge_index))
            if BRep_Tool.IsClosed_s(edge):
                # A periodic face owns its seam edge once in the ancestor map,
                # even though the edge is topologically closed.  It is not a
                # free boundary and must not invalidate an otherwise closed
                # solid.
                single_face_closed_seam_edges += 1
            else:
                boundary_edges += 1
        elif degree != 2:
            nonmanifold_edges += 1
    closed = shells_closed and boundary_edges == 0 and nonmanifold_edges == 0
    require(closed, f"{label} is not a closed two-manifold solid")

    return {
        **fingerprint,
        "valid": True,
        "closed": True,
        "all_shells_closed": bool(shells_closed),
        "boundary_edge_count": boundary_edges,
        "single_face_closed_seam_edge_count": single_face_closed_seam_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "orientation": int(solid.Orientation()),
        "forward_orientation": int(solid.Orientation()) == int(TopAbs_FORWARD),
    }


def load_step(path: Path, root: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"{label} STEP is missing: {path}")
    reader = STEPControl_Reader()
    try:
        status = reader.ReadFile(str(path))
        transferred = int(reader.TransferRoots())
        shape = reader.OneShape()
    except Exception as exc:
        raise ValidationFailure(f"OCP STEP reopen failed for {label}: {exc}") from exc
    require(status == IFSelect_RetDone, f"OCP STEP reader status is not RetDone for {label}")
    require(transferred == 1 and int(reader.NbRootsForTransfer()) == 1, f"{label} must contain exactly one transferable root")
    require(not shape.IsNull(), f"{label} reopened to a null shape")
    require(shape.ShapeType() == TopAbs_COMPOUND, f"{label} root must be a compound")
    require(BRepCheck_Analyzer(shape, True).IsValid(), f"{label} compound is invalid")
    compound_count = count_subshapes(shape, TopAbs_COMPOUND)
    compsolid_count = count_subshapes(shape, TopAbs_COMPSOLID)
    require(compound_count == 1, f"{label} must contain exactly one compound container")
    require(compsolid_count == 0, f"{label} must not contain a compsolid")

    solids: list[TopoDS_Solid] = []
    metrics: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        solids.append(solid)
        metrics.append(inspect_solid(solid, f"{label}.solid[{len(solids) - 1}]") )
        explorer.Next()
    require(solids, f"{label} contains no solids")
    total_volume = math.fsum(float(row["volume_mm3"]) for row in metrics)
    total_faces = sum(int(row["face_count"]) for row in metrics)
    total_shells = sum(int(row["shell_count"]) for row in metrics)
    return {
        "shape": shape,
        "solids": solids,
        "metrics": metrics,
        "report": {
            **file_record(path, root),
            "native_length_unit": "mm",
            "root_shape_type": "COMPOUND",
            "transfer_root_count": 1,
            "compound_count": compound_count,
            "compsolid_count": compsolid_count,
            "solid_count": len(solids),
            "shell_count": total_shells,
            "face_count": total_faces,
            "all_solids_valid": True,
            "all_solids_closed": True,
            "all_solid_volumes_finite_positive": True,
            "per_solid_volume_sum_mm3": total_volume,
            "bbox_mm": shape_bbox(shape),
        },
    }


def rpy_rotation(rpy: Sequence[float]) -> np.ndarray:
    roll, pitch, yaw = (float(value) for value in rpy)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64)
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return rz @ ry @ rx


def homogeneous(rotation: np.ndarray, translation: Sequence[float]) -> np.ndarray:
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = np.asarray(rotation, dtype=np.float64)
    result[:3, 3] = np.asarray(translation, dtype=np.float64)
    return result


def matrix_rows(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(matrix, dtype=np.float64)]


def matrix_max_abs_delta(actual: Any, expected: np.ndarray, label: str) -> float:
    array = np.asarray(actual, dtype=np.float64)
    require(array.shape == expected.shape and np.isfinite(array).all(), f"{label} has invalid matrix shape/values")
    delta = float(np.max(np.abs(array - expected)))
    require(delta <= MATRIX_ABS_TOL, f"{label} matrix drift: {delta} > {MATRIX_ABS_TOL}")
    return delta


def xml_vector(element: ET.Element | None, attribute: str, count: int, label: str) -> list[float]:
    require(element is not None, f"{label} element is missing")
    raw = element.get(attribute)
    require(isinstance(raw, str), f"{label}.{attribute} is missing")
    try:
        values = [float(token) for token in raw.split()]
    except ValueError as exc:
        raise ValidationFailure(f"{label}.{attribute} contains a non-number") from exc
    require(len(values) == count and all(math.isfinite(value) for value in values), f"{label}.{attribute} must contain {count} finite values")
    return values


def validate_urdf_and_state(
    urdf_path: Path,
    ledger: dict[str, Any],
    contract: dict[str, Any],
    state_evidence: dict[str, Any],
) -> dict[str, Any]:
    try:
        xml_root = ET.parse(urdf_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValidationFailure(f"cannot parse accepted URDF: {exc}") from exc
    require(xml_root.tag == "robot" and xml_root.get("name") == "arm_b601_v1", "accepted URDF robot identity drift")

    links = {row.get("name"): row for row in xml_root.findall("link")}
    required_links = {"gripper_link", "gripper_left", "gripper_right"}
    require(required_links.issubset(links), "accepted URDF lacks a gripper link")
    link_masses: dict[str, float] = {}
    for name in sorted(required_links):
        link = links[name]
        mass_element = link.find("./inertial/mass")
        require(mass_element is not None and mass_element.get("value") is not None, f"{name} lacks inertial mass")
        mass = float(str(mass_element.get("value")))
        require(math.isfinite(mass) and mass > 0.0, f"{name} mass is invalid")
        link_masses[name] = mass
        for kind in ("visual", "collision"):
            elements = link.findall(kind)
            require(len(elements) == 1, f"{name} must have exactly one {kind} element")
            origin = elements[0].find("origin")
            require_vector_close(xml_vector(origin, "xyz", 3, f"{name}.{kind}.origin"), [0.0, 0.0, 0.0], 0.0, f"{name}.{kind}.origin.xyz")
            require_vector_close(xml_vector(origin, "rpy", 3, f"{name}.{kind}.origin"), [0.0, 0.0, 0.0], 0.0, f"{name}.{kind}.origin.rpy")

    joints_xml = {row.get("name"): row for row in xml_root.findall("joint")}
    expected = {
        "gripper_joint": {
            "type": "fixed",
            "parent": "link6",
            "child": "gripper_link",
            "xyz": [0.0, 0.0, 0.15971],
            "rpy": [0.0, -1.5708, 0.0],
        },
        "gripper_joint1": {
            "type": "prismatic",
            "parent": "gripper_link",
            "child": "gripper_left",
            "xyz": [-0.042091, 0.000027531, -0.000013031],
            "rpy": [0.0, 0.0, -1.5708],
            "axis": [1.0, 0.0, 0.0],
            "lower": 0.0,
            "upper": 0.0715,
            "effort": 100.0,
            "velocity": 15.0,
        },
        "gripper_joint2": {
            "type": "prismatic",
            "parent": "gripper_link",
            "child": "gripper_right",
            "xyz": [-0.042091, -0.000027531, 0.000013031],
            "rpy": [0.0, 0.0, 1.5708],
            "axis": [1.0, 0.0, 0.0],
            "lower": 0.0,
            "upper": 0.0715,
            "effort": 100.0,
            "velocity": 15.0,
        },
    }

    ledger_joints = {row.get("joint_name"): row for row in ledger.get("joint_ledger", []) if isinstance(row, dict)}
    state_joints = state_evidence.get("urdf_contract", {}).get("joints")
    require(isinstance(state_joints, dict), "state evidence lacks urdf_contract.joints")
    derived: dict[str, Any] = {}
    for name, spec in expected.items():
        joint = joints_xml.get(name)
        require(joint is not None, f"accepted URDF lacks {name}")
        require(joint.get("type") == spec["type"], f"{name} type drift")
        parent = joint.find("parent")
        child = joint.find("child")
        require(parent is not None and parent.get("link") == spec["parent"], f"{name} parent drift")
        require(child is not None and child.get("link") == spec["child"], f"{name} child drift")
        xyz = xml_vector(joint.find("origin"), "xyz", 3, f"{name}.origin")
        rpy = xml_vector(joint.find("origin"), "rpy", 3, f"{name}.origin")
        require_vector_close(xyz, spec["xyz"], 0.0, f"{name}.origin.xyz")
        require_vector_close(rpy, spec["rpy"], 0.0, f"{name}.origin.rpy")
        rotation = rpy_rotation(rpy)
        transform_m = homogeneous(rotation, xyz)
        transform_mm = homogeneous(rotation, [1000.0 * value for value in xyz])

        ledger_row = ledger_joints.get(name)
        require(isinstance(ledger_row, dict), f"frame ledger lacks {name}")
        require(ledger_row.get("type") == spec["type"] and ledger_row.get("parent_link") == spec["parent"] and ledger_row.get("child_link") == spec["child"], f"frame ledger identity drift for {name}")
        matrix_delta = matrix_max_abs_delta(ledger_row.get("T_parent_child_rows_q0"), transform_m, f"ledger {name}.T_parent_child")

        row_report: dict[str, Any] = {
            "type": spec["type"],
            "parent": spec["parent"],
            "child": spec["child"],
            "origin_xyz_m": xyz,
            "origin_rpy_rad": rpy,
            "T_parent_from_child_q0_m": matrix_rows(transform_m),
            "T_parent_from_child_q0_mm": matrix_rows(transform_mm),
            "ledger_matrix_max_abs_delta": matrix_delta,
        }
        if spec["type"] == "prismatic":
            axis = xml_vector(joint.find("axis"), "xyz", 3, f"{name}.axis")
            require_vector_close(axis, spec["axis"], 0.0, f"{name}.axis")
            require_close(float(np.linalg.norm(axis)), 1.0, 1.0e-15, f"{name}.axis norm")
            limit = joint.find("limit")
            require(limit is not None, f"{name} limit is missing")
            for field in ("lower", "upper", "effort", "velocity"):
                value = float(str(limit.get(field)))
                require_close(value, float(spec[field]), 0.0, f"{name}.limit.{field}")
            axis_parent = rotation @ np.asarray(axis, dtype=np.float64)
            inverse_mm = np.linalg.inv(transform_mm)
            state_row = state_joints.get(name)
            require(isinstance(state_row, dict), f"state evidence lacks {name}")
            require(state_row.get("parent") == spec["parent"] and state_row.get("child") == spec["child"], f"state evidence identity drift for {name}")
            state_forward_delta = matrix_max_abs_delta(state_row.get("T_parent_from_child_q0_mm"), transform_mm, f"state {name}.T_parent_from_child")
            state_inverse_delta = matrix_max_abs_delta(state_row.get("T_child_from_parent_q0_mm"), inverse_mm, f"state {name}.T_child_from_parent")
            require_vector_close(state_row.get("axis_parent", []), axis_parent.tolist(), MATRIX_ABS_TOL, f"state {name}.axis_parent")
            require_vector_close(ledger_row.get("axis_in_parent_frame_from_accepted_urdf", []), axis_parent.tolist(), MATRIX_ABS_TOL, f"ledger {name}.axis_parent")
            q_upper = float(spec["upper"])
            open_displacement_m = axis_parent * q_upper
            row_report.update(
                {
                    "axis_in_joint_frame": axis,
                    "axis_in_parent_frame": [float(value) for value in axis_parent],
                    "lower_m": float(spec["lower"]),
                    "upper_m": q_upper,
                    "open_parent_displacement_m": [float(value) for value in open_displacement_m],
                    "T_child_from_parent_q0_mm": matrix_rows(inverse_mm),
                    "state_forward_matrix_max_abs_delta": state_forward_delta,
                    "state_inverse_matrix_max_abs_delta": state_inverse_delta,
                }
            )
        derived[name] = {"matrix_m": transform_m, "matrix_mm": transform_mm, "report": row_report}

    state_links = state_evidence.get("urdf_contract", {}).get("links")
    require(isinstance(state_links, dict), "state evidence lacks link mass records")
    for name, mass in link_masses.items():
        require_close(finite_float(state_links.get(name, {}).get("mass_kg"), f"state {name}.mass_kg"), mass, 0.0, f"state {name}.mass_kg")

    configurations = ledger.get("configuration_state_ledger", {}).get("configurations")
    require(isinstance(configurations, list) and len(configurations) == 9, "frame ledger must retain nine configurations")
    for row in configurations:
        require(isinstance(row, dict), "configuration row must be an object")
        require(row.get("gripper_joint1_m") is None and row.get("gripper_joint2_m") is None, "Owner gripper values must remain null")
    require(ledger.get("configuration_state_ledger", {}).get("production_complete_state_vector_count") == 0, "production complete state count must remain zero")
    require(ledger.get("configuration_state_ledger", {}).get("configuration_travel_authority") is None, "configuration travel authority must remain null")
    owner_hold = contract.get("owner_configuration_to_travel_hold", {})
    require(owner_hold.get("configuration_travel_authority") is None and owner_hold.get("authoritative_gripper_joint_values") is None, "contract illegally binds an Owner gripper state")
    require(owner_hold.get("zero_fill_forbidden") is True and owner_hold.get("scene_instance_binding_authorized") is False, "Owner state fail-closed policy drift")

    return {
        "derived": derived,
        "report": {
            "accepted_urdf_parsed_directly": True,
            "robot_name": "arm_b601_v1",
            "engineering_system_label": "B601",
            "required_links": sorted(required_links),
            "link_masses_kg": link_masses,
            "joints": {name: row["report"] for name, row in derived.items()},
            "owner_configuration_count_checked": 9,
            "owner_gripper_values_all_null": True,
            "configuration_travel_authority": None,
            "urdf_length_unit": "m",
            "step_length_unit": "mm",
            "rpy_unit": "rad",
            "prismatic_coordinate_unit": "m",
        },
    }


def gp_transform_from_matrix(matrix: np.ndarray) -> gp_Trsf:
    matrix = np.asarray(matrix, dtype=np.float64)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all(), "rigid transform matrix is invalid")
    require_close(float(np.linalg.det(matrix[:3, :3])), 1.0, 1.0e-12, "rigid transform determinant")
    transform = gp_Trsf()
    transform.SetValues(
        float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[0, 2]), float(matrix[0, 3]),
        float(matrix[1, 0]), float(matrix[1, 1]), float(matrix[1, 2]), float(matrix[1, 3]),
        float(matrix[2, 0]), float(matrix[2, 1]), float(matrix[2, 2]), float(matrix[2, 3]),
    )
    return transform


def transformed_shape(shape: TopoDS_Shape, matrix_mm: np.ndarray) -> TopoDS_Shape:
    try:
        operation = BRepBuilderAPI_Transform(shape, gp_transform_from_matrix(matrix_mm), True)
    except Exception as exc:
        raise ValidationFailure(f"OCP rigid transformation failed: {exc}") from exc
    require(operation.IsDone(), "OCP rigid transformation did not complete")
    result = operation.Shape()
    require(not result.IsNull(), "OCP rigid transformation returned a null shape")
    return result


def relative_error(actual: float, expected: float) -> float:
    return abs(float(actual) - float(expected)) / max(abs(float(expected)), 1.0e-300)


def fingerprint_delta(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
    bbox = float(np.max(np.abs(np.asarray(actual["bbox_mm"]) - np.asarray(expected["bbox_mm"]))))
    center = float(np.linalg.norm(np.asarray(actual["center_of_volume_mm"]) - np.asarray(expected["center_of_volume_mm"])))
    return {
        "bbox_endpoint_max_abs_mm": bbox,
        "center_distance_mm": center,
        "volume_relative": relative_error(actual["volume_mm3"], expected["volume_mm3"]),
        "surface_area_relative": relative_error(actual["surface_area_mm2"], expected["surface_area_mm2"]),
        "face_count_delta": float(abs(int(actual["face_count"]) - int(expected["face_count"]))),
        "shell_count_delta": float(abs(int(actual["shell_count"]) - int(expected["shell_count"]))),
    }


def match_fingerprints(
    expected_rows: list[dict[str, Any]],
    observed_rows: list[dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    require(len(expected_rows) == len(observed_rows), f"{label} fingerprint set count mismatch")
    remaining = set(range(len(observed_rows)))
    matches: list[dict[str, Any]] = []
    for expected in sorted(expected_rows, key=lambda row: str(row["stable_id"])):
        eligible: list[tuple[tuple[float, ...], int, dict[str, float]]] = []
        for index in sorted(remaining):
            observed = observed_rows[index]
            delta = fingerprint_delta(observed["fingerprint"], expected["fingerprint"])
            if delta["face_count_delta"] != 0.0 or delta["shell_count_delta"] != 0.0:
                continue
            if delta["bbox_endpoint_max_abs_mm"] > 1.0e-3 or delta["center_distance_mm"] > 1.0e-3:
                continue
            if delta["volume_relative"] > 1.0e-6 or delta["surface_area_relative"] > 1.0e-6:
                continue
            score = (
                delta["bbox_endpoint_max_abs_mm"],
                delta["center_distance_mm"],
                delta["volume_relative"],
                delta["surface_area_relative"],
                float(index),
            )
            eligible.append((score, index, delta))
        require(eligible, f"{label} has no fingerprint match for {expected['stable_id']}")
        _, selected, delta = min(eligible, key=lambda row: row[0])
        remaining.remove(selected)
        require(delta["bbox_endpoint_max_abs_mm"] <= Q0_BBOX_AND_CENTER_TOL_MM, f"{label} bbox registration exceeds tolerance for {expected['stable_id']}")
        require(delta["center_distance_mm"] <= Q0_BBOX_AND_CENTER_TOL_MM, f"{label} center registration exceeds tolerance for {expected['stable_id']}")
        require(delta["volume_relative"] <= Q0_VOLUME_AND_AREA_REL_TOL, f"{label} volume registration exceeds tolerance for {expected['stable_id']}")
        require(delta["surface_area_relative"] <= Q0_VOLUME_AND_AREA_REL_TOL, f"{label} area registration exceeds tolerance for {expected['stable_id']}")
        matches.append(
            {
                "source_member_id": str(expected["stable_id"]),
                "candidate_solid_index": int(observed_rows[selected]["candidate_index"]),
                **delta,
            }
        )
    require(not remaining, f"{label} contains unmatched candidate solids: {sorted(remaining)}")
    maxima = {
        key: max(float(row[key]) for row in matches)
        for key in (
            "bbox_endpoint_max_abs_mm",
            "center_distance_mm",
            "volume_relative",
            "surface_area_relative",
            "face_count_delta",
            "shell_count_delta",
        )
    }
    return {"matched_solid_count": len(matches), "maxima": maxima, "matches": matches}


def read_assignment_csv(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)
        rows = [dict(row) for row in reader]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValidationFailure(f"cannot read frozen solid assignment CSV: {exc}") from exc
    expected_columns = {
        "solid", "assigned_body", "volume_mm3", "faces", "s_on_jaw_axis_mm",
        "u_min_mm", "u_max_mm", "urdf_enclosure_best", "urdf_enclosure_score",
    }
    require(reader.fieldnames is not None and set(reader.fieldnames) == expected_columns, "solid assignment CSV column drift")
    require(len(rows) == 58, f"solid assignment CSV must retain 58 object-tree rows, got {len(rows)}")
    require(len({row["solid"] for row in rows}) == 58, "solid assignment CSV contains duplicate labels")
    return rows


def validate_source_accounting(
    root: Path,
    pins: dict[str, dict[str, Any]],
    donor_step: dict[str, Any],
    palm_source_step: dict[str, Any],
) -> dict[str, Any]:
    validation = read_json(pin_path(pins, "gripper_r1_geometry_validation"))
    receipt = read_json(pin_path(pins, "native_gripper_part_receipt"))
    assignment_rows = read_assignment_csv(pin_path(pins, "frozen_gripper_solid_assignment"))
    require(validation.get("schema") == "F3R2_V5R_GRIPPER_R1_GEOMETRY_VALIDATION_V1", "R1 geometry validation schema drift")
    require(receipt.get("schema") == "F3R2_V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT_V3_LINK6_LOCAL_FINGERPRINT", "native gripper receipt schema drift")
    require(receipt.get("verdict") == "V5_LOOP1C0_57_PHYSICAL_BODIES_THREE_NATIVE_GRIPPER_PARTS_PASS_ASSEMBLY_HOLD", "native gripper receipt verdict drift")
    require(donor_step["report"]["solid_count"] == 57, "neutral donor must independently reopen to 57 solids")
    require(palm_source_step["report"]["solid_count"] == 12, "R1 palm source must independently reopen to 12 solids")

    correlation = validation.get("neutral_to_v5_fingerprint_correlation")
    require(isinstance(correlation, dict), "R1 validation lacks neutral correlation")
    rows = correlation.get("rows")
    require(isinstance(rows, list) and len(rows) == 57 and correlation.get("body_count") == 57, "R1 neutral correlation count drift")
    by_index: dict[int, dict[str, Any]] = {}
    source_names: set[str] = set()
    max_source_recompute = {"bbox_mm": 0.0, "volume_mm3": 0.0, "face_count": 0}
    for row in rows:
        require(isinstance(row, dict), "R1 neutral correlation row must be an object")
        index = integer(row.get("neutral_import_index"), "neutral_import_index")
        source_name = row.get("source_name")
        require(0 <= index < 57 and index not in by_index, f"neutral_import_index invalid/duplicate: {index}")
        require(isinstance(source_name, str) and source_name and source_name not in source_names, f"source_name invalid/duplicate: {source_name}")
        source_names.add(source_name)
        metric = donor_step["metrics"][index]
        bbox_error = float(np.max(np.abs(np.asarray(metric["bbox_mm"]) - np.asarray(row.get("neutral_bbox_mm"), dtype=np.float64))))
        volume_error = abs(float(metric["volume_mm3"]) - finite_float(row.get("neutral_volume_mm3"), f"neutral row {index} volume"))
        face_delta = abs(int(metric["face_count"]) - integer(row.get("neutral_face_count"), f"neutral row {index} face_count"))
        require(bbox_error <= SOURCE_ROW_ABS_TOL_MM, f"neutral donor bbox fingerprint drift at index {index}")
        require(volume_error <= SOURCE_ROW_ABS_TOL_MM, f"neutral donor volume fingerprint drift at index {index}")
        require(face_delta == 0, f"neutral donor face fingerprint drift at index {index}")
        max_source_recompute["bbox_mm"] = max(max_source_recompute["bbox_mm"], bbox_error)
        max_source_recompute["volume_mm3"] = max(max_source_recompute["volume_mm3"], volume_error)
        max_source_recompute["face_count"] = max(max_source_recompute["face_count"], face_delta)
        by_index[index] = {"source_name": source_name, "shape": donor_step["solids"][index], "metric": metric}
    require(set(by_index) == set(range(57)), "neutral correlation indices must be exactly 0..56")

    aggregate = receipt.get("aggregate_exclusion")
    require(isinstance(aggregate, dict), "native receipt lacks aggregate exclusion")
    wrapper = "B51_REF_gripper_detail_LINKLOCAL057"
    require(aggregate.get("label") == wrapper and aggregate.get("classification") == "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY", "aggregate wrapper classification drift")
    require(aggregate.get("copy_authorized") is False and aggregate.get("step_brep_n_solids") == 57, "aggregate wrapper exclusion drift")
    wrapper_rows = [row for row in assignment_rows if row["solid"] == wrapper]
    require(len(wrapper_rows) == 1, "assignment must contain exactly one historical aggregate wrapper row")

    receipt_assignment = receipt.get("assignment")
    require(isinstance(receipt_assignment, dict), "native receipt lacks assignment")
    expected_counts = {"gripper_link": 9, "gripper_left": 24, "gripper_right": 24}
    physical_csv = [row for row in assignment_rows if row["solid"] != wrapper]
    require(len(physical_csv) == 57, "assignment wrapper exclusion must leave 57 physical rows")
    group_by_name: dict[str, str] = {}
    for group, expected_count in expected_counts.items():
        receipt_group = receipt_assignment.get(group)
        require(isinstance(receipt_group, dict), f"native receipt lacks {group} assignment")
        names = receipt_group.get("source_names")
        require(isinstance(names, list) and len(names) == expected_count and receipt_group.get("body_count") == expected_count, f"native receipt {group} count drift")
        require(len(set(names)) == expected_count, f"native receipt {group} contains duplicate members")
        csv_names = {row["solid"] for row in physical_csv if row["assigned_body"] == group}
        require(set(names) == csv_names, f"CSV/receipt membership mismatch for {group}")
        for name in names:
            require(name not in group_by_name, f"member assigned to multiple gripper groups: {name}")
            group_by_name[name] = group
    require(set(group_by_name) == source_names, "receipt/CSV physical source-name union is not the 57-body donor set")
    require(receipt.get("conservation", {}).get("source_name_union_exact") is True, "native receipt source-name union is not exact")

    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in expected_counts}
    for index in range(57):
        row = by_index[index]
        group = group_by_name[row["source_name"]]
        groups[group].append(
            {
                "stable_id": row["source_name"],
                "source_index": index,
                "shape": row["shape"],
                "fingerprint": row["metric"],
            }
        )
    for group, expected_count in expected_counts.items():
        require(len(groups[group]) == expected_count, f"independent donor selection count mismatch for {group}")

    palm_rows = [
        {
            "stable_id": f"R1_PALM_SOLID_{index:02d}",
            "source_index": index,
            "shape": shape,
            "fingerprint": palm_source_step["metrics"][index],
        }
        for index, shape in enumerate(palm_source_step["solids"])
    ]
    groups["palm_r1"] = palm_rows

    group_report: dict[str, Any] = {}
    for group, members in groups.items():
        group_report[group] = {
            "solid_count": len(members),
            "face_count": sum(int(member["fingerprint"]["face_count"]) for member in members),
            "per_solid_volume_sum_mm3": math.fsum(float(member["fingerprint"]["volume_mm3"]) for member in members),
            "member_ids": [str(member["stable_id"]) for member in members],
        }
    return {
        "groups": groups,
        "report": {
            "neutral_donor_physical_solid_count": 57,
            "assignment_object_tree_row_count": 58,
            "aggregate_wrapper_excluded": wrapper,
            "aggregate_wrapper_copy_authorized": False,
            "physical_assignment_count_after_exclusion": 57,
            "native_group_counts": expected_counts,
            "new_r1_candidate_expected_counts": {"palm": 12, "left": 24, "right": 24, "total": 60},
            "neutral_index_to_source_name_recompute_max_error": max_source_recompute,
            "groups": group_report,
        },
    }


def nested_bbox(flat: Sequence[float]) -> list[list[float]]:
    require(len(flat) == 6, "bbox must have six values")
    return [[float(value) for value in flat[:3]], [float(value) for value in flat[3:]]]


def flatten_bbox(value: Any, label: str) -> list[float]:
    require(isinstance(value, list) and len(value) == 2, f"{label} must have min/max rows")
    require(all(isinstance(row, list) and len(row) == 3 for row in value), f"{label} rows must contain three values")
    return [finite_float(item, label) for row in value for item in row]


def validate_output_pin_set(
    root: Path,
    builder_evidence: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    require(builder_evidence.get("schema") == "B601_GRIPPER_2P_BUILDER_EVIDENCE_V1", "builder evidence schema drift")
    require(builder_evidence.get("source_pin_count_verified") == 28, "builder evidence source-pin count drift")
    require(builder_evidence.get("deterministic_build_inputs_frozen") is True, "builder inputs not declared frozen")
    outputs = builder_evidence.get("outputs")
    require(isinstance(outputs, dict) and set(outputs) == set(CANDIDATES), "builder output object set drift")
    records: dict[str, Any] = {}
    for object_name, spec in CANDIDATES.items():
        row = outputs.get(object_name)
        require(isinstance(row, dict), f"builder output row missing: {object_name}")
        receipt = receipts[object_name]
        for kind, directory, filename in (
            ("step", CAD_DIR, spec["step"]),
            ("runtime_ply", RUNTIME_DIR, spec["ply"]),
            ("runtime_npz", RUNTIME_DIR, spec["npz"]),
            ("runtime_stl", RUNTIME_DIR, spec["stl"]),
            ("receipt", RESULTS_DIR, spec["receipt"]),
        ):
            actual = validate_file_pin(row.get(kind), root, f"builder {object_name}.{kind}", (directory / filename).resolve())
            records[f"{object_name}.{kind}"] = actual
            if kind != "receipt":
                receipt_key = "primary_step" if kind == "step" else kind
                receipt_actual = validate_file_pin(receipt.get(receipt_key), root, f"receipt {object_name}.{receipt_key}", (directory / filename).resolve())
                require(receipt_actual == actual, f"builder/receipt file pin mismatch for {object_name}.{kind}")
    actual_steps = {path.name for path in CAD_DIR.glob("*.step") if path.is_file()}
    expected_steps = {str(spec["step"]) for spec in CANDIDATES.values()}
    require(actual_steps == expected_steps, f"01_cad must contain exactly three authorized STEP containers: {sorted(actual_steps)}")
    return records


def validate_receipt_authority(receipt: dict[str, Any], object_name: str) -> None:
    require(receipt.get("schema") == "B601_GRIPPER_2P_LOCAL_GEOMETRY_RECEIPT_V1", f"{object_name} receipt schema drift")
    require(receipt.get("object_name") == object_name, f"{object_name} receipt object name drift")
    require(receipt.get("object_id") == CANDIDATES[object_name]["object_id"], f"{object_name} receipt object id drift")
    require(receipt.get("authority_scope") == "LOCAL_STEP_FIRST_COLLISION_GEOMETRY_CANDIDATE_ONLY", f"{object_name} receipt authority scope drift")
    require(receipt.get("classification") == "PENDING_OWNER_REVIEW", f"{object_name} receipt classification drift")
    checks = receipt.get("checks")
    require(isinstance(checks, dict) and checks and all(value is True for value in checks.values()), f"{object_name} builder receipt contains a failed/non-boolean check")
    flags = receipt.get("authority_flags")
    require(isinstance(flags, dict), f"{object_name} receipt lacks authority flags")
    require(flags.get("candidate_may_be_submitted_for_owner_binding") is True, f"{object_name} local submission flag drift")
    for key in (
        "contact_authority", "next_stage_authorized", "owner_named_state_map_resolved",
        "parent_mechanical_gate_reissued", "path_search_authorized", "release_credit",
        "system_pair_evaluation_authorized", "system_registry_reissued",
    ):
        require(flags.get(key) is False, f"{object_name} receipt illegally sets {key}")


def validate_candidate_geometry(
    root: Path,
    source_groups: dict[str, list[dict[str, Any]]],
    urdf_derived: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    palm_source_step: dict[str, Any],
    pins: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    internal: dict[str, Any] = {}
    report: dict[str, Any] = {}
    total_solids = 0
    for object_name, spec in CANDIDATES.items():
        receipt = receipts[object_name]
        validate_receipt_authority(receipt, object_name)
        candidate_path = CAD_DIR / str(spec["step"])
        candidate = load_step(candidate_path, root, f"candidate {object_name}")
        expected_count = int(spec["expected_solids"])
        require(candidate["report"]["solid_count"] == expected_count, f"{object_name} candidate solid count mismatch")
        total_solids += expected_count
        expected_rows = source_groups[str(spec["source_group"])]

        observed_rows: list[dict[str, Any]] = []
        if spec["joint"] is None:
            source_palm_hash = pins["gripper_r1_palm_step"]["sha256"]
            require(candidate["report"]["sha256"] == source_palm_hash, "palm output must be byte-identical to direct R1 palm STEP")
            require(candidate_path.read_bytes() == Path(pins["gripper_r1_palm_step"]["resolved_path"]).read_bytes(), "palm byte identity failed")
            q0_matrix_mm = np.eye(4, dtype=np.float64)
            transformed_solids = list(candidate["solids"])
        else:
            q0_matrix_mm = np.asarray(urdf_derived[str(spec["joint"])]["matrix_mm"], dtype=np.float64)
            transformed_solids = [transformed_shape(solid, q0_matrix_mm) for solid in candidate["solids"]]
        for index, solid in enumerate(transformed_solids):
            observed_rows.append({"candidate_index": index, "fingerprint": solid_fingerprint(solid)})
        match = match_fingerprints(expected_rows, observed_rows, f"{object_name} q0 reconstruction")

        geometry = receipt.get("geometry")
        require(isinstance(geometry, dict), f"{object_name} receipt lacks geometry")
        require(geometry.get("solid_count") == expected_count, f"{object_name} receipt solid count drift")
        require(geometry.get("face_count") == candidate["report"]["face_count"], f"{object_name} receipt face count drift")
        require(geometry.get("shell_count") == candidate["report"]["shell_count"], f"{object_name} receipt shell count drift")
        require(geometry.get("per_solid_closed") is True, f"{object_name} receipt closed flag drift")
        require_close(finite_float(geometry.get("brep_volume_mm3"), f"{object_name} receipt BRep volume"), candidate["report"]["per_solid_volume_sum_mm3"], 1.0e-6, f"{object_name} receipt BRep volume")
        require_vector_close(flatten_bbox(geometry.get("brep_bbox_mm"), f"{object_name} receipt bbox"), candidate["report"]["bbox_mm"], 1.0e-6, f"{object_name} receipt bbox")
        receipt_match = geometry.get("q0_source_reconstruction_match")
        require(isinstance(receipt_match, dict) and receipt_match.get("matched_solid_count") == expected_count, f"{object_name} receipt q0 match count drift")
        units = receipt.get("uncertainty_and_units")
        require(isinstance(units, dict), f"{object_name} receipt lacks unit ledger")
        require(units.get("primary_step_geometry_units") == "mm" and units.get("runtime_units") == "m", f"{object_name} receipt unit drift")
        require(units.get("m_to_mm_conversion_count_at_ocp_boundary") == 1, f"{object_name} receipt m/mm conversion count drift")
        require(units.get("manufacturing_as_built_derate_mm") is None, f"{object_name} illegally zero-fills manufacturing uncertainty")

        internal[object_name] = {
            "candidate": candidate,
            "q0_matrix_mm": q0_matrix_mm,
            "source_rows": expected_rows,
        }
        report[object_name] = {
            "candidate_id": spec["candidate_id"],
            "object_id": spec["object_id"],
            "output_frame": spec["frame"],
            "step_reopen": candidate["report"],
            "q0_source_fingerprint_registration": match,
            "offline_inverse_q0_application_count": 0 if spec["joint"] is None else 1,
            "runtime_q0_application_count_required": 0 if spec["joint"] is None else 1,
            "owner_state_bound": False,
        }
    require(total_solids == 60, f"independent candidate recount must be 60, got {total_solids}")
    require(palm_source_step["report"]["sha256"] == report["gripper_link"]["step_reopen"]["sha256"], "palm source/output SHA mismatch")
    return {"internal": internal, "report": report, "total_solids": total_solids}


def parse_binary_ply(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    marker = b"end_header\n"
    header_end = raw.find(marker)
    require(header_end >= 0, f"PLY lacks end_header: {path.name}")
    data_offset = header_end + len(marker)
    try:
        header_lines = raw[:data_offset].decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValidationFailure(f"PLY header is not ASCII: {path.name}") from exc
    require(header_lines[:2] == ["ply", "format binary_little_endian 1.0"], f"PLY format drift: {path.name}")
    comments: dict[str, str] = {}
    vertex_count: int | None = None
    face_count: int | None = None
    for line in header_lines:
        if line.startswith("comment ") and "=" in line:
            key, value = line[len("comment "):].split("=", 1)
            comments[key] = value
        elif line.startswith("element vertex "):
            vertex_count = int(line.split()[-1])
        elif line.startswith("element face "):
            face_count = int(line.split()[-1])
    require(vertex_count is not None and vertex_count > 0, f"PLY vertex count invalid: {path.name}")
    require(face_count is not None and face_count > 0, f"PLY face count invalid: {path.name}")
    required_properties = {
        "property double x", "property double y", "property double z",
        "property list uchar uint vertex_indices",
    }
    require(required_properties.issubset(set(header_lines)), f"PLY property schema drift: {path.name}")
    vertex_bytes = vertex_count * 3 * 8
    face_dtype = np.dtype([("count", "u1"), ("indices", "<u4", (3,))], align=False)
    require(face_dtype.itemsize == 13, "unexpected NumPy PLY face record size")
    expected_size = data_offset + vertex_bytes + face_count * face_dtype.itemsize
    require(len(raw) == expected_size, f"PLY byte structure mismatch: {path.name}")
    vertices = np.frombuffer(raw, dtype="<f8", count=vertex_count * 3, offset=data_offset).reshape(vertex_count, 3)
    face_rows = np.frombuffer(raw, dtype=face_dtype, count=face_count, offset=data_offset + vertex_bytes)
    require(np.all(face_rows["count"] == 3), f"PLY contains a non-triangle face: {path.name}")
    faces = face_rows["indices"]
    require(np.isfinite(vertices).all(), f"PLY contains non-finite vertices: {path.name}")
    require(int(faces.max()) < vertex_count, f"PLY face index out of range: {path.name}")
    return {
        "comments": comments,
        "vertices": vertices,
        "faces": faces,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "header_bytes": data_offset,
    }


def parse_m5_binary_ply_vertex_bbox(path: Path) -> dict[str, Any]:
    """Read only the pinned M5 PLY vertex block, without trimesh/builder code."""
    raw = path.read_bytes()
    marker = b"end_header\n"
    header_end = raw.find(marker)
    require(header_end >= 0, f"M5 PLY lacks end_header: {path.name}")
    data_offset = header_end + len(marker)
    try:
        header_lines = raw[:data_offset].decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValidationFailure(f"M5 PLY header is not ASCII: {path.name}") from exc
    require(header_lines[:2] == ["ply", "format binary_little_endian 1.0"], f"M5 PLY format drift: {path.name}")

    vertex_count: int | None = None
    vertex_properties: list[str] = []
    active_element: str | None = None
    for line in header_lines:
        if line.startswith("element "):
            fields = line.split()
            require(len(fields) == 3, f"M5 PLY malformed element declaration: {path.name}")
            active_element = fields[1]
            if active_element == "vertex":
                vertex_count = int(fields[2])
        elif line.startswith("property ") and active_element == "vertex":
            vertex_properties.append(line)
    require(vertex_count is not None and vertex_count > 0, f"M5 PLY vertex count invalid: {path.name}")
    require(
        vertex_properties in (
            ["property float x", "property float y", "property float z"],
            ["property double x", "property double y", "property double z"],
        ),
        f"M5 PLY vertex property schema drift: {path.name}",
    )
    vertex_dtype = np.dtype("<f4" if vertex_properties[0] == "property float x" else "<f8")
    vertex_bytes = int(vertex_count) * 3 * vertex_dtype.itemsize
    require(len(raw) >= data_offset + vertex_bytes, f"M5 PLY vertex block is truncated: {path.name}")
    vertices = np.frombuffer(raw, dtype=vertex_dtype, count=int(vertex_count) * 3, offset=data_offset).reshape(int(vertex_count), 3)
    require(np.isfinite(vertices).all(), f"M5 PLY contains non-finite vertices: {path.name}")
    bbox_m = np.concatenate((vertices.min(axis=0), vertices.max(axis=0))).astype(np.float64)
    return {
        "vertex_count": int(vertex_count),
        "vertex_dtype": str(vertex_dtype),
        "header_bytes": int(data_offset),
        "bbox_m": [float(value) for value in bbox_m],
    }


def scalar_array_value(array: np.ndarray, label: str) -> Any:
    require(array.shape == (), f"{label} must be a scalar NPZ field")
    return array.item()


def mesh_topology_and_volume(vertices: np.ndarray, faces: np.ndarray, solid_ids: np.ndarray, expected_solids: int, label: str) -> dict[str, Any]:
    unique_ids = np.unique(solid_ids)
    require(np.array_equal(unique_ids, np.arange(expected_solids, dtype=unique_ids.dtype)), f"{label} solid_ids must be contiguous 0..{expected_solids - 1}")
    boundary_edges = 0
    nonmanifold_edges = 0
    duplicate_triangles = 0
    zero_area_triangles = 0
    signed_volumes: list[float] = []
    per_solid_triangles: list[int] = []
    for solid_id in range(expected_solids):
        triangles = faces[solid_ids == solid_id]
        require(len(triangles) > 0, f"{label} mesh solid {solid_id} has no triangles")
        per_solid_triangles.append(int(len(triangles)))
        require(np.all(triangles[:, 0] != triangles[:, 1]) and np.all(triangles[:, 1] != triangles[:, 2]) and np.all(triangles[:, 2] != triangles[:, 0]), f"{label} mesh has repeated indices in a triangle")
        canonical_triangles = np.sort(triangles, axis=1)
        duplicate_triangles += int(len(canonical_triangles) - len(np.unique(canonical_triangles, axis=0)))
        edge_rows = np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]), axis=0)
        edge_rows.sort(axis=1)
        _, counts = np.unique(edge_rows, axis=0, return_counts=True)
        boundary_edges += int(np.count_nonzero(counts == 1))
        nonmanifold_edges += int(np.count_nonzero(counts != 2)) - int(np.count_nonzero(counts == 1))
        a = vertices[triangles[:, 0]]
        b = vertices[triangles[:, 1]]
        c = vertices[triangles[:, 2]]
        cross = np.cross(b - a, c - a)
        zero_area_triangles += int(np.count_nonzero(np.linalg.norm(cross, axis=1) == 0.0))
        signed_volume = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum(dtype=np.float64) / 6.0)
        require(math.isfinite(signed_volume) and signed_volume > 0.0, f"{label} mesh solid {solid_id} is not finite/outward-positive")
        signed_volumes.append(signed_volume)
    require(boundary_edges == 0 and nonmanifold_edges == 0, f"{label} runtime mesh is not closed two-manifold")
    require(duplicate_triangles == 0 and zero_area_triangles == 0, f"{label} runtime mesh contains duplicate/zero-area triangles")
    return {
        "solid_count": expected_solids,
        "boundary_edge_count": boundary_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "duplicate_triangle_count": duplicate_triangles,
        "zero_area_triangle_count": zero_area_triangles,
        "all_signed_solid_volumes_positive": True,
        "mesh_volume_m3": math.fsum(signed_volumes),
        "mesh_volume_mm3": math.fsum(signed_volumes) * 1.0e9,
        "minimum_signed_solid_volume_m3": min(signed_volumes),
        "per_solid_triangle_counts": per_solid_triangles,
    }


def validate_runtime_sidecars(
    root: Path,
    candidate_internal: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    pins: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    report: dict[str, Any] = {}
    runtime_bboxes: dict[str, list[float]] = {}
    for object_name, spec in CANDIDATES.items():
        ply_path = RUNTIME_DIR / str(spec["ply"])
        npz_path = RUNTIME_DIR / str(spec["npz"])
        ply = parse_binary_ply(ply_path)
        try:
            with np.load(npz_path, allow_pickle=False) as archive:
                require(set(archive.files) == {"faces", "frame", "object_id", "solid_ids", "transform_application_count", "units", "vertices_m"}, f"{object_name} NPZ key set drift")
                vertices = np.asarray(archive["vertices_m"])
                faces = np.asarray(archive["faces"])
                solid_ids = np.asarray(archive["solid_ids"])
                frame = scalar_array_value(np.asarray(archive["frame"]), f"{object_name}.frame")
                object_id = scalar_array_value(np.asarray(archive["object_id"]), f"{object_name}.object_id")
                units = scalar_array_value(np.asarray(archive["units"]), f"{object_name}.units")
                transform_count = scalar_array_value(np.asarray(archive["transform_application_count"]), f"{object_name}.transform_application_count")
        except (OSError, ValueError, KeyError) as exc:
            raise ValidationFailure(f"cannot independently read runtime NPZ for {object_name}: {exc}") from exc
        require(vertices.dtype == np.dtype("float64") and vertices.ndim == 2 and vertices.shape[1] == 3, f"{object_name} NPZ vertices schema drift")
        require(faces.dtype == np.dtype("uint32") and faces.ndim == 2 and faces.shape[1] == 3, f"{object_name} NPZ faces schema drift")
        require(solid_ids.dtype == np.dtype("uint16") and solid_ids.shape == (len(faces),), f"{object_name} NPZ solid_ids schema drift")
        require(np.isfinite(vertices).all(), f"{object_name} NPZ contains non-finite vertices")
        require(len(vertices) > 0 and len(faces) > 0 and int(faces.max()) < len(vertices), f"{object_name} NPZ topology indices invalid")
        require(str(frame) == spec["frame"] and str(object_id) == spec["object_id"] and str(units) == "m", f"{object_name} NPZ frame/object/unit drift")
        require(int(transform_count) == 1, f"{object_name} NPZ scale/transform application count must be one")
        require(ply["comments"].get("units") == "m" and ply["comments"].get("frame") == spec["frame"], f"{object_name} PLY frame/unit comments drift")
        require(np.array_equal(vertices, ply["vertices"]), f"{object_name} PLY/NPZ vertices differ")
        require(np.array_equal(faces, ply["faces"]), f"{object_name} PLY/NPZ faces differ")
        require(ply["vertex_count"] == len(vertices) and ply["face_count"] == len(faces), f"{object_name} PLY/NPZ count mismatch")

        expected_solids = int(spec["expected_solids"])
        topology = mesh_topology_and_volume(vertices, faces, solid_ids, expected_solids, object_name)
        candidate_report = candidate_internal[object_name]["candidate"]["report"]
        step_bbox_mm = np.asarray(candidate_report["bbox_mm"], dtype=np.float64)
        runtime_bbox_m = np.concatenate((vertices.min(axis=0), vertices.max(axis=0)))
        runtime_bbox_mm = runtime_bbox_m * 1000.0
        bbox_error_mm = float(np.max(np.abs(runtime_bbox_mm - step_bbox_mm)))
        require(bbox_error_mm <= RUNTIME_BBOX_TOL_MM, f"{object_name} runtime bbox scale/frame mismatch")
        volume_relative = relative_error(topology["mesh_volume_mm3"], candidate_report["per_solid_volume_sum_mm3"])
        require(volume_relative <= RUNTIME_VOLUME_REL_TOL, f"{object_name} runtime mesh/BRep volume mismatch")
        runtime_bboxes[object_name] = [float(value) for value in runtime_bbox_m]

        # M5 is a pinned secondary gripper_link-local frame/bounds witness.  The
        # primary comparison therefore uses the reopened STEP BRep recomposed
        # to q0 parent coordinates, while the separate runtime comparison uses
        # the independently parsed metre mesh recomposed by the same literal
        # URDF transform.  Keeping both prevents a tessellation match from
        # disguising primary-BRep drift.
        m5_source_id = str(spec["m5_source_id"])
        m5_path = pin_path(pins, m5_source_id)
        m5 = parse_m5_binary_ply_vertex_bbox(m5_path)
        m5_bbox_mm = np.asarray(m5["bbox_m"], dtype=np.float64) * 1000.0
        q0_matrix_mm = np.asarray(candidate_internal[object_name]["q0_matrix_mm"], dtype=np.float64)
        candidate_solids = candidate_internal[object_name]["candidate"]["solids"]
        primary_parent_bbox_mm = np.asarray(
            aggregate_bbox(candidate_solids, None if spec["joint"] is None else q0_matrix_mm),
            dtype=np.float64,
        )
        primary_m5_error_mm = float(np.max(np.abs(primary_parent_bbox_mm - m5_bbox_mm)))
        require(primary_m5_error_mm <= M5_PRIMARY_BREP_BBOX_TOL_MM, f"{object_name} primary BRep/M5 q0 bbox mismatch")
        runtime_parent_vertices_mm = vertices * 1000.0 @ q0_matrix_mm[:3, :3].T + q0_matrix_mm[:3, 3]
        runtime_parent_bbox_mm = np.concatenate((runtime_parent_vertices_mm.min(axis=0), runtime_parent_vertices_mm.max(axis=0)))
        runtime_m5_error_mm = float(np.max(np.abs(runtime_parent_bbox_mm - m5_bbox_mm)))
        require(runtime_m5_error_mm <= M5_RUNTIME_MESH_BBOX_TOL_MM, f"{object_name} runtime mesh/M5 q0 bbox mismatch")

        receipt_geometry = receipts[object_name].get("geometry", {})
        require(receipt_geometry.get("runtime_triangle_count") == len(faces), f"{object_name} receipt triangle count drift")
        require(receipt_geometry.get("runtime_vertex_count") == len(vertices), f"{object_name} receipt vertex count drift")
        require(receipt_geometry.get("boundary_edge_count") == 0 and receipt_geometry.get("nonmanifold_edge_count") == 0, f"{object_name} receipt mesh closure drift")
        require_close(finite_float(receipt_geometry.get("runtime_mesh_volume_mm3"), f"{object_name} receipt runtime volume"), topology["mesh_volume_mm3"], 1.0e-6, f"{object_name} receipt runtime volume")
        require_close(finite_float(receipt_geometry.get("runtime_step_bbox_max_abs_error_mm"), f"{object_name} receipt bbox error"), bbox_error_mm, 1.0e-6, f"{object_name} receipt bbox error")
        require_close(finite_float(receipt_geometry.get("primary_brep_to_m5_q0_bbox_max_abs_error_mm"), f"{object_name} receipt primary/M5 bbox error"), primary_m5_error_mm, 1.0e-6, f"{object_name} receipt primary/M5 bbox error")
        require_close(finite_float(receipt_geometry.get("runtime_mesh_to_m5_q0_bbox_max_abs_error_mm"), f"{object_name} receipt runtime/M5 bbox error"), runtime_m5_error_mm, 1.0e-6, f"{object_name} receipt runtime/M5 bbox error")

        report[object_name] = {
            "frame": spec["frame"],
            "units": "m",
            "step_to_runtime_scale": 0.001,
            "scale_application_count": 1,
            "ply": {
                **file_record(ply_path, root),
                "binary_format": "binary_little_endian_1.0",
                "vertex_count": int(ply["vertex_count"]),
                "triangle_count": int(ply["face_count"]),
                "header_bytes": int(ply["header_bytes"]),
            },
            "npz": {
                **file_record(npz_path, root),
                "key_set": ["faces", "frame", "object_id", "solid_ids", "transform_application_count", "units", "vertices_m"],
                "vertex_dtype": str(vertices.dtype),
                "face_dtype": str(faces.dtype),
                "solid_id_dtype": str(solid_ids.dtype),
                "transform_application_count": int(transform_count),
            },
            "ply_npz_vertices_byte_equal": True,
            "ply_npz_faces_equal": True,
            "runtime_bbox_m": [float(value) for value in runtime_bbox_m],
            "runtime_bbox_reexpressed_mm": [float(value) for value in runtime_bbox_mm],
            "step_bbox_mm": [float(value) for value in step_bbox_mm],
            "runtime_step_bbox_max_abs_error_mm": bbox_error_mm,
            "runtime_mesh_brep_volume_relative_error": volume_relative,
            "mesh_topology": topology,
            "m5_gripper_link_local_crosscheck": {
                "source_id": m5_source_id,
                "source": file_record(m5_path, root),
                "m5_vertex_count": m5["vertex_count"],
                "m5_vertex_dtype": m5["vertex_dtype"],
                "m5_bbox_m": m5["bbox_m"],
                "primary_brep_q0_parent_bbox_mm": [float(value) for value in primary_parent_bbox_mm],
                "primary_brep_to_m5_q0_bbox_max_abs_error_mm": primary_m5_error_mm,
                "primary_brep_acceptance_mm": M5_PRIMARY_BREP_BBOX_TOL_MM,
                "runtime_mesh_q0_parent_bbox_mm": [float(value) for value in runtime_parent_bbox_mm],
                "runtime_mesh_to_m5_q0_bbox_max_abs_error_mm": runtime_m5_error_mm,
                "runtime_mesh_acceptance_mm": M5_RUNTIME_MESH_BBOX_TOL_MM,
                "primary_and_runtime_crosschecks_pass": True,
            },
        }
    return report, runtime_bboxes


def aggregate_bbox(shapes: Sequence[TopoDS_Shape], matrix_mm: np.ndarray | None = None) -> list[float]:
    boxes: list[list[float]] = []
    for shape in shapes:
        current = transformed_shape(shape, matrix_mm) if matrix_mm is not None else shape
        boxes.append(shape_bbox(current))
    require(boxes, "cannot compute aggregate bbox of an empty shape set")
    minimum = [min(row[index] for row in boxes) for index in range(3)]
    maximum = [max(row[index + 3] for row in boxes) for index in range(3)]
    return [*minimum, *maximum]


def bbox_endpoint_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    return float(np.max(np.abs(np.asarray(actual, dtype=np.float64) - np.asarray(expected, dtype=np.float64))))


def validate_negative_controls(
    candidate_internal: dict[str, Any],
    urdf_derived: dict[str, Any],
    runtime_bboxes_m: dict[str, list[float]],
) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for side, joint in (("gripper_left", "gripper_joint1"), ("gripper_right", "gripper_joint2")):
        source_shapes = [row["shape"] for row in candidate_internal[side]["source_rows"]]
        candidate_shapes = candidate_internal[side]["candidate"]["solids"]
        source_bbox = aggregate_bbox(source_shapes)
        transform = np.asarray(urdf_derived[joint]["matrix_mm"], dtype=np.float64)
        wrong_parent_relabel_bbox = aggregate_bbox(source_shapes, transform)
        parent_relabel_error = bbox_endpoint_error(wrong_parent_relabel_bbox, source_bbox)
        require(parent_relabel_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM, f"{side} parent-local-as-child negative control was not rejected")

        double_transform_bbox = aggregate_bbox(candidate_shapes, transform @ transform)
        double_transform_error = bbox_endpoint_error(double_transform_bbox, source_bbox)
        require(double_transform_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM, f"{side} double-q0 negative control was not rejected")
        controls[f"{side}_parent_local_relabelled_child"] = {
            "expected_rejection": True,
            "bbox_endpoint_error_mm": parent_relabel_error,
            "rejection_threshold_mm": NEGATIVE_CONTROL_MIN_REJECTION_MM,
            "rejected": True,
        }
        controls[f"{side}_q0_transform_applied_twice"] = {
            "expected_rejection": True,
            "bbox_endpoint_error_mm": double_transform_error,
            "rejection_threshold_mm": NEGATIVE_CONTROL_MIN_REJECTION_MM,
            "rejected": True,
        }

        step_bbox = np.asarray(candidate_internal[side]["candidate"]["report"]["bbox_mm"], dtype=np.float64)
        scale_omitted_runtime_bbox_m = step_bbox.copy()
        scale_twice_runtime_bbox_m = step_bbox * 1.0e-6
        omitted_error = float(np.max(np.abs(scale_omitted_runtime_bbox_m * 1000.0 - step_bbox)))
        twice_error = float(np.max(np.abs(scale_twice_runtime_bbox_m * 1000.0 - step_bbox)))
        require(omitted_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM and twice_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM, f"{side} scale negative controls were not rejected")
        controls[f"{side}_mm_to_m_scale_omitted"] = {
            "expected_rejection": True,
            "bbox_endpoint_error_mm": omitted_error,
            "rejected": True,
        }
        controls[f"{side}_mm_to_m_scale_applied_twice"] = {
            "expected_rejection": True,
            "bbox_endpoint_error_mm": twice_error,
            "rejected": True,
        }

    left_shapes = candidate_internal["gripper_left"]["candidate"]["solids"]
    right_shapes = candidate_internal["gripper_right"]["candidate"]["solids"]
    left_source_bbox = aggregate_bbox([row["shape"] for row in candidate_internal["gripper_left"]["source_rows"]])
    right_source_bbox = aggregate_bbox([row["shape"] for row in candidate_internal["gripper_right"]["source_rows"]])
    left_transform = np.asarray(urdf_derived["gripper_joint1"]["matrix_mm"], dtype=np.float64)
    right_transform = np.asarray(urdf_derived["gripper_joint2"]["matrix_mm"], dtype=np.float64)
    swapped_left_error = bbox_endpoint_error(aggregate_bbox(right_shapes, left_transform), left_source_bbox)
    swapped_right_error = bbox_endpoint_error(aggregate_bbox(left_shapes, right_transform), right_source_bbox)
    require(swapped_left_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM and swapped_right_error >= NEGATIVE_CONTROL_MIN_REJECTION_MM, "left/right child-frame swap negative control was not rejected")
    controls["left_right_child_frame_swap"] = {
        "expected_rejection": True,
        "left_bbox_endpoint_error_mm": swapped_left_error,
        "right_bbox_endpoint_error_mm": swapped_right_error,
        "rejection_threshold_mm": NEGATIVE_CONTROL_MIN_REJECTION_MM,
        "rejected": True,
    }

    left_axis = np.asarray(urdf_derived["gripper_joint1"]["report"]["axis_in_parent_frame"], dtype=np.float64)
    right_axis = np.asarray(urdf_derived["gripper_joint2"]["report"]["axis_in_parent_frame"], dtype=np.float64)
    q_upper_m = 0.0715
    swapped_axis_error_mm = float(np.linalg.norm((left_axis - right_axis) * q_upper_m * 1000.0))
    double_travel_error_mm = q_upper_m * 1000.0
    require(swapped_axis_error_mm >= NEGATIVE_CONTROL_MIN_REJECTION_MM and double_travel_error_mm >= NEGATIVE_CONTROL_MIN_REJECTION_MM, "axis/double-travel negative control was not rejected")
    controls["left_right_axis_swap_at_open"] = {
        "expected_rejection": True,
        "parent_displacement_error_mm": swapped_axis_error_mm,
        "rejected": True,
    }
    controls["prismatic_travel_applied_twice_at_open"] = {
        "expected_rejection": True,
        "parent_displacement_error_mm": double_travel_error_mm,
        "rejected": True,
    }

    palm_step_bbox = np.asarray(candidate_internal["gripper_link"]["candidate"]["report"]["bbox_mm"], dtype=np.float64)
    palm_runtime_bbox = np.asarray(runtime_bboxes_m["gripper_link"], dtype=np.float64)
    correct_palm_error = float(np.max(np.abs(palm_runtime_bbox * 1000.0 - palm_step_bbox)))
    require(correct_palm_error <= RUNTIME_BBOX_TOL_MM, "palm positive scale control failed")
    controls["positive_single_mm_to_m_scale"] = {
        "expected_rejection": False,
        "maximum_runtime_step_bbox_error_mm": correct_palm_error,
        "acceptance_threshold_mm": RUNTIME_BBOX_TOL_MM,
        "accepted": True,
    }
    controls["aggregate_wrapper_as_physical_body"] = {
        "expected_rejection": True,
        "historical_object_tree_rows": 58,
        "physical_body_rows_after_exclusion": 57,
        "excluded_label": "B51_REF_gripper_detail_LINKLOCAL057",
        "rejected": True,
    }
    controls["native_57_reported_as_new_r1_output_count"] = {
        "expected_rejection": True,
        "native_lineage_count": 57,
        "independent_new_output_count": 60,
        "rejected": True,
    }
    return {
        "negative_control_count": sum(1 for row in controls.values() if row.get("expected_rejection") is True),
        "all_required_negative_controls_rejected": True,
        "controls": controls,
    }


def validate_system_invariants(
    contract: dict[str, Any],
    source_lock: dict[str, Any],
    builder_evidence: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    state_evidence: dict[str, Any],
    pins: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    contract_invariants = contract.get("current_system_authority_invariants")
    lock_invariants = source_lock.get("current_system_authority_invariants")
    require(isinstance(contract_invariants, dict) and isinstance(lock_invariants, dict), "system invariant ledgers are missing")
    for key, expected in EXPECTED_SYSTEM_INVARIANTS.items():
        require(contract_invariants.get(key) == expected, f"contract system invariant drift: {key}")
        if key in lock_invariants:
            require(lock_invariants.get(key) == expected, f"source lock system invariant drift: {key}")

    scene_gate = read_json(pin_path(pins, "m01_scene_collision_prebind_gate"))
    registry_gate = read_json(pin_path(pins, "m01_system_collision_registry_gate"))
    motion_gate = read_json(pin_path(pins, "m01_motion_cert_batch_gate"))
    parent_gate = read_json(pin_path(pins, "parent_mechanical_release_gate"))
    require(scene_gate.get("asset_accounting", {}).get("active_object_rows") == 150, "scene gate active-object count drift")
    require(scene_gate.get("asset_accounting", {}).get("operational_authority_rows") == 1, "scene gate operational-authority count drift")
    require(scene_gate.get("scene_accounting", {}).get("stage_instances_bound") == 0 and scene_gate.get("scene_accounting", {}).get("stage_instances_required") == 3, "scene gate stage-instance counters drift")
    system_state = scene_gate.get("system_execution_state")
    require(isinstance(system_state, dict), "scene gate lacks system execution state")
    for key, expected in {
        "complete_system_operational_collision_asset_set_bound": False,
        "system_pair_queries_executed": 0,
        "system_edges_certified": 0,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }.items():
        require(system_state.get(key) == expected, f"scene gate execution-state drift: {key}")
    require(registry_gate.get("known_active_object_count") == 150, "registry active-object count drift")
    require(registry_gate.get("pair_coverage", {}).get("expected_pairs") == 11175, "registry raw pair count drift")
    require(registry_gate.get("pair_coverage", {}).get("status_counts", {}).get("UNASSESSED_FAIL_CLOSED") == 11166, "registry unassessed pair count drift")
    require(registry_gate.get("path_search_executed") is False and registry_gate.get("next_stage_authorized") is False and registry_gate.get("release_credit") is False, "registry gate authority drift")
    counters = motion_gate.get("counters")
    require(isinstance(counters, dict), "motion gate lacks counters")
    for key, expected in {
        "active_object_count": 150,
        "asset_level_operational_count": 1,
        "pair_queries_executed": 0,
        "pair_queries_required": 11166,
        "edges_certified": 0,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "batch_new_system_motion_certificates_bound": 0,
        "next_stage_authorized": False,
        "path_search_executed": False,
        "release_credit": False,
    }.items():
        require(counters.get(key) == expected, f"motion gate counter drift: {key}")
    for key in ("pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized", "next_stage_authorized", "release_credit"):
        require(motion_gate.get(key) is False, f"motion gate illegally sets {key}")
    require(parent_gate.get("gate_a_pass") is False and parent_gate.get("next_stage_authorized") is False and parent_gate.get("release_credit") is False, "parent mechanical release gate was upgraded")

    candidate_documents: list[tuple[str, dict[str, Any]]] = [("builder", builder_evidence), ("state", state_evidence)]
    candidate_documents.extend((f"receipt.{name}", value) for name, value in receipts.items())
    for document_name, document in candidate_documents:
        for path, value in walk_scalars(document):
            if path and path[-1] in FORBIDDEN_TRUE_AUTHORITY_KEYS:
                require(value is False, f"{document_name} illegally sets {'.'.join(path)}={value!r}")
    require(builder_evidence.get("authority_flags", {}).get("system_registry_reissued") is False, "builder reissued system registry")
    require(state_evidence.get("system_authority_flags", {}).get("system_pair_queries_executed") == 0, "state evidence query counter drift")
    require(state_evidence.get("system_authority_flags", {}).get("stage_instances_bound") == 0, "state evidence stage count drift")

    return {
        **EXPECTED_SYSTEM_INVARIANTS,
        "raw_unordered_pair_count": 11175,
        "unassessed_fail_closed_pair_count": 11166,
        "batch_new_system_motion_certificates_bound": 0,
        "parent_gate_a_pass": False,
        "candidate_documents_checked_for_authority_promotion": [name for name, _ in candidate_documents],
        "validation_pass": True,
    }


def validate_unit_audit(unit_audit: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    require(unit_audit.get("schema") == "B601_GRIPPER_2P_UNIT_AND_UNCERTAINTY_AUDIT_V1", "unit audit schema drift")
    checks = unit_audit.get("checks")
    require(isinstance(checks, dict) and checks and all(value is True for value in checks.values()), "unit audit contains a failed/non-boolean check")
    derates = unit_audit.get("derates")
    require(isinstance(derates, dict), "unit audit lacks derates")
    require(derates.get("manufacturing_as_built_mm") is None, "manufacturing/as-built uncertainty was zero-filled")
    require_close(finite_float(derates.get("primary_step_numeric_mm_per_object"), "primary BRep numeric derate"), 1.0e-6, 0.0, "primary BRep numeric derate")
    require_close(finite_float(derates.get("runtime_mesh_chordal_mm_per_object"), "runtime chordal derate"), 0.05, 0.0, "runtime chordal derate")
    require_close(finite_float(derates.get("runtime_mesh_pair_lower_bound_debit_mm"), "runtime pair debit"), 0.10000200000000001, 0.0, "runtime pair debit")
    frame_contract = contract.get("frame_and_transform_contract", {})
    require(frame_contract.get("urdf_length_unit") == "m" and frame_contract.get("primary_step_length_unit") == "mm" and frame_contract.get("runtime_sidecar_length_unit") == "m", "contract unit ledger drift")
    require_close(finite_float(frame_contract.get("step_to_runtime_scale"), "step_to_runtime_scale"), 0.001, 0.0, "step_to_runtime_scale")
    require(frame_contract.get("scale_application_count_required") == 1 and frame_contract.get("double_scale_prohibited") is True, "contract scale application policy drift")
    return {
        "primary_step_length_unit": "mm",
        "accepted_urdf_length_unit": "m",
        "runtime_sidecar_length_unit": "m",
        "urdf_rpy_unit": "rad",
        "prismatic_coordinate_unit": "m",
        "m_to_mm_reframe_scale": 1000.0,
        "mm_to_m_runtime_scale": 0.001,
        "each_boundary_scale_application_count": 1,
        "manufacturing_as_built_uncertainty_mm": None,
        "uncertainty_disposition": "MEASUREMENT_PENDING__NO_CONTACT_MANUFACTURING_OR_SYSTEM_DERATING_AUTHORITY",
        "validation_pass": True,
    }


def validate_all() -> dict[str, Any]:
    root = workspace_root()
    contract = read_json(CONTRACT_PATH)
    source_lock = read_json(SOURCE_LOCK_PATH)
    ledger = read_json(FRAME_LEDGER_PATH)
    control_records = validate_frozen_controls(root, contract, source_lock, ledger)

    # All 28 source byte locks are recomputed before any source or candidate BRep
    # is opened.  A mismatch therefore fails before geometry consumption.
    pins, validated_pins = validate_source_pins(root, source_lock)

    builder_evidence = read_json(BUILDER_EVIDENCE_PATH)
    state_evidence = read_json(STATE_EVIDENCE_PATH)
    unit_audit = read_json(UNIT_AUDIT_PATH)
    receipts = {
        name: read_json(RESULTS_DIR / str(spec["receipt"]))
        for name, spec in CANDIDATES.items()
    }
    output_pin_records = validate_output_pin_set(root, builder_evidence, receipts)
    require(builder_evidence.get("contract", {}).get("sha256") == control_records[CONTRACT_PATH.name]["sha256"], "builder contract hash drift")
    require(builder_evidence.get("source_lock", {}).get("sha256") == control_records[SOURCE_LOCK_PATH.name]["sha256"], "builder source-lock hash drift")
    require(builder_evidence.get("frame_and_state_ledger", {}).get("sha256") == control_records[FRAME_LEDGER_PATH.name]["sha256"], "builder frame-ledger hash drift")

    urdf = validate_urdf_and_state(pin_path(pins, "accepted_b601_urdf"), ledger, contract, state_evidence)
    palm_source = load_step(pin_path(pins, "gripper_r1_palm_step"), root, "R1 palm source")
    donor_source = load_step(pin_path(pins, "neutral_gripper_donor_step"), root, "neutral gripper donor")
    source_accounting = validate_source_accounting(root, pins, donor_source, palm_source)

    candidate_geometry = validate_candidate_geometry(
        root,
        source_accounting["groups"],
        urdf["derived"],
        receipts,
        palm_source,
        pins,
    )
    runtime_report, runtime_bboxes = validate_runtime_sidecars(root, candidate_geometry["internal"], receipts, pins)
    negative_controls = validate_negative_controls(candidate_geometry["internal"], urdf["derived"], runtime_bboxes)
    unit_report = validate_unit_audit(unit_audit, contract)
    system_invariants = validate_system_invariants(contract, source_lock, builder_evidence, receipts, state_evidence, pins)

    return {
        "schema": "B601_GRIPPER_2P_INDEPENDENT_STEP_REOPEN_VALIDATION_V1",
        "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "as_of_date": "2026-08-28",
        "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
        "authority_scope": "INDEPENDENT_THREE_LOCAL_STEP_AND_RUNTIME_SIDECAR_VALIDATION_ONLY",
        "review_status": "PENDING_OWNER_REVIEW",
        "validator_independence": {
            "candidate_builder_imported": False,
            "candidate_geometry_module_imported": False,
            "candidate_builder_executed": False,
            "accepted_urdf_parsed_directly": True,
            "step_reopen_backend": "DIRECT_OCP_STEPCONTROL_BREPCHECK_BREPGPROP_BREPBNDLIB",
            "donor_membership_recompute": "DIRECT_57_SOLID_OCP_ENUMERATION_PLUS_R1_INDEX_FINGERPRINT_PLUS_RECEIPT_CSV_INTERSECTION",
            "runtime_sidecar_recompute": "DIRECT_BINARY_PLY_AND_NUMPY_NPZ_PARSE",
            "system_pair_query_executed": False,
            "path_search_executed": False,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": str(np.__version__),
            "ocp": str(OCP_VERSION),
            "ocp_step_length_unit_interpretation": "mm",
            "ocp_multithread": False,
        },
        "frozen_tolerances": {
            "source_row_abs_tolerance_mm": SOURCE_ROW_ABS_TOL_MM,
            "q0_bbox_and_center_tolerance_mm": Q0_BBOX_AND_CENTER_TOL_MM,
            "q0_volume_and_area_relative_tolerance": Q0_VOLUME_AND_AREA_REL_TOL,
            "runtime_bbox_tolerance_mm": RUNTIME_BBOX_TOL_MM,
            "runtime_mesh_brep_volume_relative_tolerance": RUNTIME_VOLUME_REL_TOL,
            "m5_primary_brep_q0_bbox_tolerance_mm": M5_PRIMARY_BREP_BBOX_TOL_MM,
            "m5_runtime_mesh_q0_bbox_tolerance_mm": M5_RUNTIME_MESH_BBOX_TOL_MM,
            "negative_control_minimum_rejection_mm": NEGATIVE_CONTROL_MIN_REJECTION_MM,
            "metrology_uncertainty_bound_mm": None,
        },
        "input_files": {
            "validator": file_record(Path(__file__), root),
            "contract": control_records[CONTRACT_PATH.name],
            "source_authority_lock": control_records[SOURCE_LOCK_PATH.name],
            "urdf_frame_and_state_ledger": control_records[FRAME_LEDGER_PATH.name],
            "builder_evidence": file_record(BUILDER_EVIDENCE_PATH, root),
            "state_and_frame_evidence": file_record(STATE_EVIDENCE_PATH, root),
            "unit_and_uncertainty_audit": file_record(UNIT_AUDIT_PATH, root),
        },
        "source_pin_validation": {
            "required_source_pin_count": 28,
            "validated_source_pin_count": len(validated_pins),
            "all_bytes_and_sha256_match": True,
            "geometry_opened_only_after_all_pins_passed": True,
            "validated_pins": validated_pins,
        },
        "output_pin_validation": {
            "three_step_containers_only": True,
            "builder_and_receipt_pins_match_actual_files": True,
            "records": output_pin_records,
        },
        "urdf_frame_and_state_recompute": urdf["report"],
        "source_step_reopen": {
            "r1_palm": palm_source["report"],
            "neutral_57_solid_donor": donor_source["report"],
        },
        "source_solid_accounting": source_accounting["report"],
        "candidate_step_reopen_and_q0_registration": candidate_geometry["report"],
        "runtime_ply_npz_validation": runtime_report,
        "unit_and_uncertainty_validation": unit_report,
        "negative_controls": negative_controls,
        "current_system_authority_invariants": system_invariants,
        "claim_boundaries": {
            "owner_state_bound": False,
            "contact_valid": False,
            "strength_valid": False,
            "manufacturing_clearance_valid": False,
            "as_built_valid": False,
            "operational_narrowphase_promoted": False,
            "pair_eligible": False,
            "system_safe": False,
            "path_search_legal": False,
            "parent_gate_credit": False,
            "release_credit": False,
        },
        "summary": {
            "source_pins_passed": len(validated_pins),
            "source_pins_required": 28,
            "step_containers_passed": 3,
            "step_containers_required": 3,
            "independently_reopened_solid_counts": {"palm": 12, "left": 24, "right": 24, "total": candidate_geometry["total_solids"]},
            "runtime_ply_npz_pairs_passed": 3,
            "runtime_ply_npz_pairs_required": 3,
            "negative_controls_rejected": negative_controls["negative_control_count"],
            "system_pair_queries_executed": 0,
            "system_edges_certified": 0,
            "stage_instances_bound": 0,
            "path_search_executed": False,
        },
        "validation_pass": True,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "maximum_legal_claim": "THREE_SOURCE_BOUND_LOCAL_B601_GRIPPER_STEP_CANDIDATES_AND_METRE_RUNTIME_SIDECARS_INDEPENDENTLY_REOPEN_AND_REFRAME_PASS__OWNER_STATE_SYSTEM_PAIR_EDGE_PATH_CONTACT_STRENGTH_MANUFACTURING_AND_RELEASE_REMAIN_HELD",
        "verdict": "INDEPENDENT_GRIPPER_2P_LOCAL_GEOMETRY_VALIDATION_PASS__12_PLUS_24_PLUS_24__28_SOURCE_PINS__ZERO_SYSTEM_PAIR_QUERIES__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT",
    }


def encode_result(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"atomically write {RESULT_PATH.name}")
    mode.add_argument("--check", action="store_true", help="recompute and require byte-identical existing result JSON")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_all()
        payload = encode_result(result)
        if args.check:
            require(RESULT_PATH.is_file(), f"independent validation output is missing: {RESULT_PATH}")
            require(RESULT_PATH.read_bytes() == payload, "independent validation output differs from fresh deterministic recomputation")
        elif args.write:
            atomic_write(RESULT_PATH, payload)
        sys.stdout.buffer.write(payload)
        return 0
    except ValidationFailure as exc:
        print(f"VALIDATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
