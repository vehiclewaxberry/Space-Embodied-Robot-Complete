"""Fail-closed, independently reproducible validation of the M5 release package.

This validator does not create mechanical, collision, mass, contact, load,
structural, flight, manufacturing, or RL authority.  It verifies integrity and
the deliberately bounded diagnostic claims already made by M5.  In particular,
the 6 GiB memory gate remains failed: the recorded Owner Override authorizes
only the lightweight route and is never converted into a MEMORY_GATE_PASS.

Exit status is 0 only when every validation check passes.  A receipt is written
atomically even when one or more checks fail.  Unknown physical values must
remain null/HOLD; no zero filling is performed here.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


M5 = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[3]
RECEIPT = M5 / "08_validation/M5_VALIDATION_RECEIPT_V1.json"

URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
POSE_REL = "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_INITIAL_POSE.yaml"
SCENE_REL = "20_engineering/config/visualization/scene_manifest_v1.yaml"
MODEL_REL = "30_simulation/sim_05_free_floating_arm/b601_model.py"
TARGET_SATELLITE_REL = "20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.stl"
TARGET_DEBRIS_REL = "20_engineering/cad/spacecraft_layout/target_debris_v0/target_debris_v0.stl"

FRAME_REL = "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json"
CONFIG_REL = "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"
BROAD_REL = "02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json"
LOAD_REL = "03_load_authority/M5_LOAD_AUTHORITY_MIGRATION_V1.yaml"
LOAD_CSV_REL = "03_load_authority/M5_LOAD_CASE_MIGRATION_REGISTER_V1.csv"
JOINT_REL = "04_joint_load_model/M5_ANALYTIC_JOINT_LOAD_MODEL_V1.yaml"
JOINT_CSV_REL = "04_joint_load_model/M5_FASTENER_GROUP_INFLUENCE_MATRIX_V1.csv"
CONTACT_REL = "05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml"
CONTACT_PLAN_REL = "05_contact_identification/CONTACT_IDENTIFICATION_TEST_PLAN_V1.yaml"
STRUCTURAL_REL = "06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json"
INTERFACE_REL = "07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml"
PHASE_REL = "00_authority/M5_PHASE_AUTHORITY_AND_BOUNDARY.yaml"
INPUT_MANIFEST_REL = "00_authority/M5_FROZEN_INPUT_MANIFEST_V1.json"
GATE_REL = "12_release/M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1.json"
OUTPUT_MANIFEST_REL = "12_release/M5_OUTPUT_MANIFEST_V1.json"

Q1_REL = "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/02_wp1_loads"
SOURCE_LOAD_CASES_REL = f"{Q1_REL}/LOAD_CASE_MATRIX.csv"
SOURCE_LOAD_COMBOS_REL = f"{Q1_REL}/LOAD_COMBINATION_MATRIX.csv"
SOURCE_LOAD_GAPS_REL = f"{Q1_REL}/LOAD_SOURCE_GAP_REGISTER.csv"
SOURCE_BOUNDARY_REL = f"{Q1_REL}/BOUNDARY_CONDITION_AUTHORITY.json"

# Exact static inputs consumed by build_m5_closure.py.  Per-configuration arm
# and gripper mesh inputs are added from the frame decision below, then the
# resulting set is compared exactly with the frozen manifest.
EXPECTED_FROZEN_STATIC_REL = [
    URDF_REL,
    POSE_REL,
    SCENE_REL,
    "20_engineering/config/geometry/target_models_v1.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/ENV_MESH_DEPLOYED.json",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/ENV_MESH_STOWED.json",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/99_tools/fc_export_env_mesh.py",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
    "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json",
    "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json",
    "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_A_INTERFACE_RING_REVB.stl",
    "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.stl",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/06_pack_and_go/V5R_NEUTRAL_OPERATIONAL_PACKAGE/interface/CONFIGURATION_MATRIX.csv",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/07_structural_model/STRUCTURAL_ANALYSIS_ENTRY_GATE.json",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json",
    SOURCE_LOAD_CASES_REL,
    SOURCE_LOAD_COMBOS_REL,
    SOURCE_LOAD_GAPS_REL,
    SOURCE_BOUNDARY_REL,
    MODEL_REL,
    TARGET_SATELLITE_REL,
    TARGET_DEBRIS_REL,
]

EXPECTED_CONFIG_NAMES = {
    "C01": "DEPLOYED_NOMINAL",
    "C02": "LEFT_PANEL_FAIL",
    "C03": "RIGHT_PANEL_FAIL",
    "C04": "BOTH_PANEL_FAIL",
    "C05": "ARM_STOWED_ONORBIT",
    "C06": "ARM_TASK_READY",
    "C07": "PREGRASP",
    "C08": "CAPTURE",
    "C09": "POST_CAPTURE",
}
ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]
FRAME_COMPONENTS = ARM_LINKS + ["legacy_gripper_detail"]


try:
    import numpy as np
    import trimesh
    import yaml
    from scipy.spatial import cKDTree

    SCIENCE_IMPORT_ERROR: str | None = None
except Exception as import_exc:  # pragma: no cover - exercised only on deficient host
    np = None  # type: ignore[assignment]
    trimesh = None  # type: ignore[assignment]
    yaml = None  # type: ignore[assignment]
    cKDTree = None  # type: ignore[assignment]
    SCIENCE_IMPORT_ERROR = f"{type(import_exc).__name__}: {import_exc}"


class ValidationDataError(RuntimeError):
    """Raised for malformed or unsafe controlled data."""


class Scope:
    """Accumulate all failures in one independently meaningful check."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.details: dict[str, Any] = {}

    def expect(self, condition: Any, message: str) -> None:
        if not bool(condition):
            self.errors.append(message)

    def equal(self, actual: Any, expected: Any, label: str) -> None:
        if actual != expected:
            self.errors.append(f"{label}: expected {expected!r}, got {actual!r}")

    def finite(self, value: Any, label: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            self.errors.append(f"{label}: expected a finite number, got {value!r}")


class Recorder:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def run(self, check_id: str, title: str, function: Callable[[], Scope]) -> None:
        try:
            scope = function()
            self.checks.append(
                {
                    "id": check_id,
                    "title": title,
                    "passed": not scope.errors,
                    "errors": scope.errors,
                    "details": clean(scope.details),
                }
            )
        except Exception as exc:  # receipt must survive malformed/missing inputs
            self.checks.append(
                {
                    "id": check_id,
                    "title": title,
                    "passed": False,
                    "errors": [f"unhandled {type(exc).__name__}: {exc}"],
                    "details": {"traceback_tail": traceback.format_exc().splitlines()[-8:]},
                }
            )


def now_local() -> str:
    return datetime.now().astimezone().isoformat()


def clean(value: Any) -> Any:
    if np is not None and isinstance(value, np.ndarray):
        return clean(value.tolist())
    if np is not None and isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float):
        return 0.0 if abs(value) < 5.0e-15 else value
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationDataError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> Any:
    raise ValidationDataError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_json_pairs,
        parse_constant=reject_json_constant,
    )


def read_yaml(path: Path) -> Any:
    if yaml is None:
        raise ValidationDataError(f"PyYAML unavailable: {SCIENCE_IMPORT_ERROR}")

    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise ValidationDataError(f"unhashable YAML mapping key in {path}") from exc
            if duplicate:
                raise ValidationDataError(f"duplicate YAML key in {path}: {key!r}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping,
    )
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def read_csv_strict(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        raw = list(csv.reader(stream))
    if not raw:
        raise ValidationDataError(f"empty CSV: {path}")
    header = raw[0]
    if not header or any(not item for item in header):
        raise ValidationDataError(f"blank CSV header field: {path}")
    if len(set(item.casefold() for item in header)) != len(header):
        raise ValidationDataError(f"duplicate CSV header: {path}")
    rows: list[dict[str, str]] = []
    for line_number, values in enumerate(raw[1:], start=2):
        # RFC 4180 files in the inherited qualification set contain harmless
        # trailing blank records.  They are not data rows and DictReader (used
        # by the M5 builder) ignores them, so do the same while retaining exact
        # width checks for every non-blank record.
        if not values or all(not item.strip() for item in values):
            continue
        if len(values) != len(header):
            raise ValidationDataError(
                f"CSV width mismatch at {path}:{line_number}: {len(values)} != {len(header)}"
            )
        rows.append(dict(zip(header, values, strict=True)))
    return header, rows


def assert_finite_tree(value: Any, location: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationDataError(f"non-finite value at {location}")
    if isinstance(value, dict):
        for key, item in value.items():
            assert_finite_tree(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_finite_tree(item, f"{location}[{index}]")


def safe_resolve(relative: str, root: Path) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValidationDataError(f"invalid empty/non-string path: {relative!r}")
    candidate_rel = Path(relative)
    if candidate_rel.is_absolute() or candidate_rel.drive:
        raise ValidationDataError(f"absolute or drive-qualified path forbidden: {relative!r}")
    root_resolved = root.resolve()
    candidate = (root_resolved / candidate_rel).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValidationDataError(f"path escapes controlled root: {relative!r}") from exc
    return candidate


def workspace_file(relative: str) -> Path:
    return safe_resolve(relative.replace("\\", "/"), WORKSPACE)


def m5_file(relative: str) -> Path:
    return safe_resolve(relative.replace("\\", "/"), M5)


def verify_reference(scope: Scope, reference: Any, root: Path, label: str) -> Path | None:
    if not isinstance(reference, dict):
        scope.errors.append(f"{label}: reference is not a mapping")
        return None
    relative = reference.get("path")
    expected_hash = reference.get("sha256")
    try:
        path = safe_resolve(relative, root)
    except Exception as exc:
        scope.errors.append(f"{label}: {exc}")
        return None
    if not path.is_file():
        scope.errors.append(f"{label}: file missing: {relative}")
        return None
    actual_hash = sha256(path)
    if not isinstance(expected_hash, str) or actual_hash != expected_hash.upper():
        scope.errors.append(
            f"{label}: SHA-256 mismatch for {relative}: expected {expected_hash!r}, got {actual_hash}"
        )
    return path


def science_required() -> None:
    if SCIENCE_IMPORT_ERROR is not None:
        raise ValidationDataError(f"scientific runtime unavailable: {SCIENCE_IMPORT_ERROR}")


def rpy_matrix(rpy: list[float]) -> Any:
    science_required()
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    return rz @ ry @ rx


def axis_angle_matrix(axis: Any, angle: float) -> Any:
    science_required()
    vector = np.asarray(axis, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValidationDataError("zero rotation axis")
    x, y, z = vector / norm
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)


def parse_vector(text: str | None, count: int, default: list[float]) -> list[float]:
    if text is None:
        return list(default)
    values = [float(item) for item in text.split()]
    if len(values) != count or not all(math.isfinite(item) for item in values):
        raise ValidationDataError(f"invalid vector {text!r}; expected {count} finite values")
    return values


def parse_urdf(path: Path) -> dict[str, Any]:
    science_required()
    root = ET.parse(path).getroot()
    if root.tag != "robot":
        raise ValidationDataError("URDF root is not <robot>")
    links = {node.attrib["name"] for node in root.findall("link")}
    joints: dict[str, Any] = {}
    children: set[str] = set()
    for node in root.findall("joint"):
        name = node.attrib.get("name")
        joint_type = node.attrib.get("type")
        parent_node = node.find("parent")
        child_node = node.find("child")
        if not name or parent_node is None or child_node is None:
            raise ValidationDataError("URDF joint missing name/parent/child")
        parent = parent_node.attrib.get("link")
        child = child_node.attrib.get("link")
        if parent not in links or child not in links or child in children:
            raise ValidationDataError(f"invalid or multiply-parented URDF joint {name}")
        children.add(child)
        origin_node = node.find("origin")
        xyz = parse_vector(origin_node.attrib.get("xyz") if origin_node is not None else None, 3, [0.0] * 3)
        rpy = parse_vector(origin_node.attrib.get("rpy") if origin_node is not None else None, 3, [0.0] * 3)
        origin = np.eye(4)
        origin[:3, :3] = rpy_matrix(rpy)
        origin[:3, 3] = xyz
        axis_node = node.find("axis")
        axis = parse_vector(axis_node.attrib.get("xyz") if axis_node is not None else None, 3, [1.0, 0.0, 0.0])
        limit_node = node.find("limit")
        lower = float(limit_node.attrib["lower"]) if limit_node is not None and "lower" in limit_node.attrib else None
        upper = float(limit_node.attrib["upper"]) if limit_node is not None and "upper" in limit_node.attrib else None
        joints[name] = {
            "type": joint_type,
            "parent": parent,
            "child": child,
            "origin": origin,
            "origin_xyz": xyz,
            "origin_rpy": rpy,
            "axis": np.asarray(axis, dtype=float),
            "lower": lower,
            "upper": upper,
        }
    roots = sorted(links - children)
    if roots != ["base_link"]:
        raise ValidationDataError(f"unexpected URDF roots: {roots}")
    return {"links": links, "joints": joints, "root": "base_link"}


def urdf_fk(model: dict[str, Any], q_by_joint: dict[str, float], base_transform: Any) -> dict[str, Any]:
    science_required()
    transforms: dict[str, Any] = {model["root"]: np.asarray(base_transform, dtype=float)}
    pending = set(model["joints"])
    while pending:
        progressed = False
        for name in list(pending):
            joint = model["joints"][name]
            if joint["parent"] not in transforms:
                continue
            motion = np.eye(4)
            coordinate = float(q_by_joint.get(name, 0.0))
            if joint["type"] in {"revolute", "continuous"}:
                motion[:3, :3] = axis_angle_matrix(joint["axis"], coordinate)
            elif joint["type"] == "prismatic":
                norm = float(np.linalg.norm(joint["axis"]))
                if norm <= 0.0:
                    raise ValidationDataError(f"zero prismatic axis: {name}")
                motion[:3, 3] = joint["axis"] / norm * coordinate
            elif joint["type"] != "fixed":
                raise ValidationDataError(f"unsupported URDF joint type: {joint['type']}")
            transforms[joint["child"]] = transforms[joint["parent"]] @ joint["origin"] @ motion
            pending.remove(name)
            progressed = True
        if not progressed:
            raise ValidationDataError(f"URDF graph is disconnected or cyclic: {sorted(pending)}")
    return transforms


def transform_mm(matrix_m: Any) -> Any:
    result = np.asarray(matrix_m, dtype=float).copy()
    result[:3, 3] *= 1000.0
    return result


def load_mesh(path: Path) -> Any:
    science_required()
    loaded = trimesh.load(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        meshes = [item for item in loaded.geometry.values() if isinstance(item, trimesh.Trimesh)]
        if not meshes:
            raise ValidationDataError(f"mesh scene has no triangle geometry: {path}")
        loaded = trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.vertices) == 0:
        raise ValidationDataError(f"not a non-empty triangle mesh: {path}")
    if not np.all(np.isfinite(loaded.vertices)):
        raise ValidationDataError(f"non-finite mesh vertices: {path}")
    return loaded


def nearest_metrics(source: Any, target: Any) -> dict[str, float | int]:
    query = np.asarray(source, dtype=float)
    target_array = np.asarray(target, dtype=float)
    if len(query) == 0 or len(target_array) == 0:
        raise ValidationDataError("nearest-neighbour comparison received empty vertices")
    # Query every released/source vertex.  Chunking bounds temporary memory but
    # deliberately does not subsample: `maximum_mm` is an actual vertex-set
    # maximum, not a sampled witness mislabeled as a maximum.
    tree = cKDTree(target_array)
    distance_blocks = []
    for start in range(0, len(query), 50_000):
        distances, _ = tree.query(query[start : start + 50_000], k=1)
        distance_blocks.append(np.asarray(distances, dtype=float))
    all_distances = np.concatenate(distance_blocks)
    return {
        "sample_count": int(len(query)),
        "maximum_mm": float(np.max(all_distances)),
        "p99_mm": float(np.quantile(all_distances, 0.99)),
        "median_mm": float(np.median(all_distances)),
    }


def parse_scene_q(path: Path) -> list[float]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"q_rad:\s*\[([^\]]+)\]", text, flags=re.DOTALL)
    if match is None:
        raise ValidationDataError("scene q_rad candidate not found")
    values = [float(item.strip()) for item in match.group(1).split(",")]
    if len(values) != 6 or not all(math.isfinite(item) for item in values):
        raise ValidationDataError("scene q_rad is not six finite values")
    return values


def write_receipt_atomic(payload: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f".{RECEIPT.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, RECEIPT)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    recorder = Recorder()
    docs: dict[str, Any] = {}
    csv_docs: dict[str, tuple[list[str], list[dict[str, str]]]] = {}

    def check_runtime() -> Scope:
        scope = Scope()
        scope.expect(SCIENCE_IMPORT_ERROR is None, f"scientific runtime import failure: {SCIENCE_IMPORT_ERROR}")
        if SCIENCE_IMPORT_ERROR is None:
            scope.details = {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "trimesh": trimesh.__version__,
                "pyyaml": yaml.__version__,
            }
        return scope

    recorder.run("M5-V-001", "validator runtime dependencies", check_runtime)

    core_specs: dict[str, tuple[str, str, str]] = {
        "input_manifest": (INPUT_MANIFEST_REL, "json", "M5_FROZEN_INPUT_MANIFEST_V1"),
        "phase": (PHASE_REL, "yaml", "M5_PHASE_AUTHORITY_AND_BOUNDARY_V1"),
        "frame": (FRAME_REL, "json", "M5_B601_CAD_MESH_FRAME_DECISION_V1"),
        "config": (CONFIG_REL, "yaml", "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1"),
        "broad": (BROAD_REL, "json", "M5_BROADPHASE_COLLISION_AUDIT_V1"),
        "load": (LOAD_REL, "yaml", "M5_LOAD_AUTHORITY_MIGRATION_V1"),
        "joint": (JOINT_REL, "yaml", "M5_ANALYTIC_JOINT_LOAD_MODEL_V1"),
        "contact": (CONTACT_REL, "yaml", "M5_CONTACT_MODEL_PARAMETER_CONTRACT_V1"),
        "contact_plan": (CONTACT_PLAN_REL, "yaml", "M5_CONTACT_IDENTIFICATION_TEST_PLAN_V1"),
        "structural": (STRUCTURAL_REL, "json", "M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1"),
        "interface": (INTERFACE_REL, "yaml", "MECH_DYNAMICS_INTERFACE_V3"),
        "gate": (GATE_REL, "json", "M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1"),
        "output_manifest": (OUTPUT_MANIFEST_REL, "json", "M5_OUTPUT_MANIFEST_V1"),
    }

    def check_structured_documents() -> Scope:
        scope = Scope()
        for name, (relative, kind, schema) in core_specs.items():
            path = m5_file(relative)
            if not path.is_file():
                scope.errors.append(f"missing required M5 document: {relative}")
                continue
            try:
                value = read_json(path) if kind == "json" else read_yaml(path)
                assert_finite_tree(value, name)
                if not isinstance(value, dict):
                    raise ValidationDataError("root is not a mapping")
                if value.get("schema") != schema:
                    raise ValidationDataError(f"schema expected {schema!r}, got {value.get('schema')!r}")
                docs[name] = value
            except Exception as exc:
                scope.errors.append(f"{relative}: {type(exc).__name__}: {exc}")
        csv_specs = {
            "load_csv": LOAD_CSV_REL,
            "joint_csv": JOINT_CSV_REL,
        }
        for name, relative in csv_specs.items():
            try:
                csv_docs[name] = read_csv_strict(m5_file(relative))
            except Exception as exc:
                scope.errors.append(f"{relative}: {type(exc).__name__}: {exc}")
        scope.details = {
            "parsed_structured_documents": sorted(docs),
            "parsed_csv_documents": sorted(csv_docs),
        }
        return scope

    recorder.run("M5-V-002", "strict structured-document parsing", check_structured_documents)

    def required_doc(name: str) -> dict[str, Any]:
        value = docs.get(name)
        if not isinstance(value, dict):
            raise ValidationDataError(f"required parsed document unavailable: {name}")
        return value

    def check_input_manifest() -> Scope:
        scope = Scope()
        manifest = required_doc("input_manifest")
        records = manifest.get("records")
        if not isinstance(records, list):
            raise ValidationDataError("input manifest records is not a list")
        scope.equal(
            set(manifest),
            {"schema", "generated_local", "record_count", "records", "status"},
            "input manifest exact fields",
        )
        seen: set[str] = set()
        verified_bytes = 0
        for index, record in enumerate(records):
            label = f"input record {index}"
            if not isinstance(record, dict):
                scope.errors.append(f"{label}: not a mapping")
                continue
            relative = record.get("path")
            try:
                path = workspace_file(relative)
            except Exception as exc:
                scope.errors.append(f"{label}: {exc}")
                continue
            key = relative.replace("\\", "/").casefold()
            if key in seen:
                scope.errors.append(f"{label}: duplicate case-insensitive path {relative!r}")
            seen.add(key)
            if not path.is_file():
                scope.errors.append(f"{label}: missing {relative}")
                continue
            size = path.stat().st_size
            verified_bytes += size
            if record.get("bytes") != size:
                scope.errors.append(f"{label}: byte count mismatch for {relative}")
            actual_hash = sha256(path)
            if str(record.get("sha256", "")).upper() != actual_hash:
                scope.errors.append(f"{label}: SHA-256 mismatch for {relative}")
        scope.equal(manifest.get("record_count"), len(records), "input manifest record_count")
        scope.equal(manifest.get("status"), "PASS_ALL_INPUTS_PRESENT_AND_HASH_BOUND", "input manifest status")
        scope.details = {"record_count": len(records), "verified_total_bytes": verified_bytes}
        return scope

    recorder.run("M5-V-003", "frozen input manifest hashes", check_input_manifest)

    def check_critical_source_coverage() -> Scope:
        scope = Scope()
        manifest = required_doc("input_manifest")
        records = manifest.get("records", [])
        declared = {
            str(record.get("path", "")).replace("\\", "/").casefold(): record
            for record in records
            if isinstance(record, dict)
        }
        critical = list(EXPECTED_FROZEN_STATIC_REL)
        frame = required_doc("frame")
        for component in frame.get("components", {}).values():
            if isinstance(component, dict):
                for key in ("deployed_source", "stowed_source"):
                    reference = component.get(key)
                    if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                        critical.append(reference["path"])
        gripper = frame.get("active_gripper_r1", {})
        for role in ("palm", "left_finger", "right_finger"):
            reference = gripper.get(role, {}).get("source") if isinstance(gripper, dict) else None
            if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                critical.append(reference["path"])
        motion = gripper.get("motion_contract", {}) if isinstance(gripper, dict) else {}
        for witness in motion.get("conflicting_non_authoritative_travel_witnesses_m", {}).values():
            if isinstance(witness, dict):
                reference = witness.get("source")
                if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                    critical.append(reference["path"])
        unique_critical = sorted(set(item.replace("\\", "/") for item in critical), key=str.casefold)
        missing: list[dict[str, Any]] = []
        for relative in unique_critical:
            key = relative.casefold()
            if key not in declared:
                path = workspace_file(relative)
                missing.append(
                    {
                        "path": relative,
                        "exists": path.is_file(),
                        "bytes": path.stat().st_size if path.is_file() else None,
                        "actual_sha256": sha256(path) if path.is_file() else None,
                    }
                )
        expected_keys = {item.casefold() for item in unique_critical}
        extra_declared = sorted(
            str(record.get("path", "")).replace("\\", "/")
            for key, record in declared.items()
            if key not in expected_keys
        )
        scope.expect(not missing, f"build dependencies absent from frozen input manifest: {[item['path'] for item in missing]}")
        scope.expect(not extra_declared, f"frozen input manifest contains undeclared-by-builder dependencies: {extra_declared}")
        scope.equal(len(records), len(unique_critical), "exact frozen dependency count")
        scope.details = {
            "expected_dependency_count": len(unique_critical),
            "missing_from_manifest": missing,
            "extra_in_manifest": extra_declared,
            "coverage_complete": not missing and not extra_declared,
        }
        return scope

    recorder.run("M5-V-004", "critical source-dependency coverage", check_critical_source_coverage)

    def check_output_manifest() -> Scope:
        scope = Scope()
        manifest = required_doc("output_manifest")
        records = manifest.get("records")
        if not isinstance(records, list):
            raise ValidationDataError("output manifest records is not a list")
        scope.equal(
            set(manifest),
            {
                "schema",
                "generated_local",
                "file_count",
                "total_bytes",
                "records",
                "exclusion_policy",
                "host_or_interpreter_cache_files_present",
                "status",
            },
            "output manifest exact fields",
        )
        scope.equal(
            manifest.get("host_or_interpreter_cache_files_present"),
            False,
            "output manifest host/interpreter cache flag",
        )
        seen: set[str] = set()
        total = 0
        mismatches: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            label = f"output record {index}"
            if not isinstance(record, dict):
                scope.errors.append(f"{label}: not a mapping")
                continue
            relative = record.get("path")
            try:
                path = m5_file(relative)
            except Exception as exc:
                scope.errors.append(f"{label}: {exc}")
                continue
            key = relative.replace("\\", "/").casefold()
            if key in seen:
                scope.errors.append(f"{label}: duplicate case-insensitive path {relative!r}")
            seen.add(key)
            if not path.is_file():
                scope.errors.append(f"{label}: missing {relative}")
                continue
            size = path.stat().st_size
            total += size
            if record.get("bytes") != size:
                scope.errors.append(f"{label}: byte count mismatch for {relative}")
            actual_hash = sha256(path)
            if str(record.get("sha256", "")).upper() != actual_hash:
                scope.errors.append(f"{label}: SHA-256 mismatch for {relative}")
            if record.get("bytes") != size or str(record.get("sha256", "")).upper() != actual_hash:
                mismatches.append(
                    {
                        "path": relative,
                        "declared_bytes": record.get("bytes"),
                        "actual_bytes": size,
                        "declared_sha256": record.get("sha256"),
                        "actual_sha256": actual_hash,
                    }
                )
        scope.equal(manifest.get("file_count"), len(records), "output manifest file_count")
        scope.equal(manifest.get("total_bytes"), total, "output manifest total_bytes")
        scope.equal(manifest.get("status"), "PASS_OUTPUTS_HASH_BOUND", "output manifest status")
        scope.details = {
            "file_count": len(records),
            "verified_total_bytes": total,
            "mismatched_records": mismatches,
        }
        return scope

    recorder.run("M5-V-005", "M5 output manifest hashes", check_output_manifest)

    def check_output_coverage() -> Scope:
        scope = Scope()
        manifest = required_doc("output_manifest")
        declared = {
            str(record.get("path", "")).replace("\\", "/").casefold()
            for record in manifest.get("records", [])
            if isinstance(record, dict)
        }
        expected_exclusion_policy = [
            "12_release/M5_OUTPUT_MANIFEST_V1.json",
            "08_validation/M5_VALIDATION_RECEIPT_V1.json",
        ]
        scope.equal(manifest.get("exclusion_policy"), expected_exclusion_policy, "output manifest exclusion policy")

        def excluded_by_manifest_policy(relative: str) -> bool:
            return (
                relative.casefold() == OUTPUT_MANIFEST_REL.casefold()
                or relative.casefold() == "08_validation/m5_validation_receipt_v1.json"
            )

        def permitted_live_exclusion(relative: str) -> bool:
            normalized = relative.replace("\\", "/").casefold()
            return (
                normalized == OUTPUT_MANIFEST_REL.casefold()
                or normalized == "08_validation/m5_validation_receipt_v1.json"
            )

        actual = {
            path.relative_to(M5).as_posix().casefold()
            for path in M5.rglob("*")
            if path.is_file()
        }
        allowed_unmanifested = {relative for relative in actual if permitted_live_exclusion(relative)}
        unexpected = sorted(actual - declared - allowed_unmanifested)
        missing = sorted(declared - actual)
        wrongly_manifested_exclusions = sorted(relative for relative in declared if excluded_by_manifest_policy(relative))
        scope.expect(not unexpected, f"unmanifested M5 files outside the closed exclusion allowance: {unexpected}")
        scope.expect(not missing, f"manifested M5 files absent from package: {missing}")
        scope.expect(not wrongly_manifested_exclusions, f"files forbidden by exclusion policy are manifested: {wrongly_manifested_exclusions}")
        scope.expect("99_tools/validate_m5_release.py" in declared, "validator script is not hash-bound by the M5 output manifest")
        scope.details = {
            "declared_file_count": len(declared),
            "live_file_count": len(actual),
            "allowed_unmanifested": sorted(allowed_unmanifested),
            "unexpected_unmanifested": unexpected,
            "wrongly_manifested_exclusions": wrongly_manifested_exclusions,
        }
        return scope

    recorder.run("M5-V-006", "closed output-file coverage", check_output_coverage)

    shared_kinematics: dict[str, Any] = {}

    def get_kinematics() -> tuple[dict[str, Any], dict[str, Any], Any]:
        if shared_kinematics:
            return shared_kinematics["model"], shared_kinematics["pose"], shared_kinematics["mount"]
        model = parse_urdf(workspace_file(URDF_REL))
        pose = read_yaml(workspace_file(POSE_REL))
        mount = np.asarray(pose["mount"]["transform_mm_rows"], dtype=float)
        if mount.shape != (4, 4) or not np.all(np.isfinite(mount)):
            raise ValidationDataError("mount transform is not finite 4x4")
        mount = mount.copy()
        mount[:3, 3] /= 1000.0
        shared_kinematics.update({"model": model, "pose": pose, "mount": mount})
        return model, pose, mount

    def check_frame_localization() -> Scope:
        scope = Scope()
        science_required()
        frame = required_doc("frame")
        model, pose, mount = get_kinematics()
        q_zero = {f"joint{index}": 0.0 for index in range(1, 7)}
        stow_values = pose["poses"]["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"]
        q_stow = {f"joint{index}": float(stow_values[index - 1]) for index in range(1, 7)}
        fk_zero = urdf_fk(model, q_zero, mount)
        fk_stow = urdf_fk(model, q_stow, mount)

        components = frame.get("components")
        if not isinstance(components, dict):
            raise ValidationDataError("frame components is not a mapping")
        scope.equal(set(components), set(FRAME_COMPONENTS), "frame component names")
        scope.equal(frame.get("registration_component_count"), 8, "frame registration_component_count")
        scope.equal(
            frame.get("decision"),
            "SOURCE_LINKLOCAL_NAMED_STLS_ARE_ASSEMBLY_COORDINATE_MESHES_AND_MUST_BE_INVERSE_Q0_LOCALIZED",
            "frame decision",
        )
        scope.equal(frame.get("numerical_acceptance_mm"), 0.1, "frame numerical acceptance (mm)")
        scope.equal(frame.get("source_tessellation_linear_deflection_mm"), 0.5, "source tessellation deflection (mm)")
        scope.equal(frame.get("physical_clearance_or_metrology_claim"), False, "physical clearance/metrology authority")

        residual_table: list[dict[str, Any]] = []
        for name in FRAME_COMPONENTS:
            item = components.get(name)
            if not isinstance(item, dict):
                scope.errors.append(f"frame component missing/malformed: {name}")
                continue
            carrier = str(item.get("carrier_frame", ""))
            if carrier not in fk_zero or carrier not in fk_stow:
                scope.errors.append(f"{name}: invalid carrier frame {carrier!r}")
                continue
            deployed_path = verify_reference(scope, item.get("deployed_source"), WORKSPACE, f"{name} deployed")
            stowed_path = verify_reference(scope, item.get("stowed_source"), WORKSPACE, f"{name} stowed")
            if deployed_path is None or stowed_path is None:
                continue
            deployed = load_mesh(deployed_path)
            stowed = load_mesh(stowed_path)
            t0_mm = transform_mm(fk_zero[carrier])
            ts_mm = transform_mm(fk_stow[carrier])
            expected_local_mm = trimesh.transform_points(deployed.vertices, np.linalg.inv(t0_mm))

            row: dict[str, Any] = {"component": name, "carrier_frame": carrier}
            recorded_transform = item.get("T_link_from_assembly_at_q0_rows")
            if name != "legacy_gripper_detail":
                try:
                    recorded = np.asarray(recorded_transform, dtype=float)
                    transform_residual = float(np.max(np.abs(recorded - np.linalg.inv(t0_mm))))
                except Exception:
                    transform_residual = float("inf")
                row["inverse_q0_transform_max_abs_residual"] = transform_residual
                scope.expect(transform_residual <= 1.0e-9, f"{name}: recorded inverse-q0 transform mismatch {transform_residual}")

                local_path = verify_reference(scope, item.get("local_surface"), WORKSPACE, f"{name} local surface")
                broad_path = verify_reference(scope, item.get("conservative_broadphase_box"), WORKSPACE, f"{name} broadphase box")
                if local_path is None or broad_path is None:
                    del deployed, stowed, expected_local_mm
                    gc.collect()
                    continue
                local = load_mesh(local_path)
                broad = load_mesh(broad_path)
                local_mm = np.asarray(local.vertices, dtype=float) * 1000.0
                localized_forward = nearest_metrics(local_mm, expected_local_mm)
                localized_reverse = nearest_metrics(expected_local_mm, local_mm)
                reconstructed_stow_mm = trimesh.transform_points(local_mm, ts_mm)
                forward = nearest_metrics(reconstructed_stow_mm, stowed.vertices)
                reverse = nearest_metrics(stowed.vertices, reconstructed_stow_mm)
                bbox_residual = float(
                    np.max(
                        np.abs(
                            np.vstack([reconstructed_stow_mm.min(axis=0), reconstructed_stow_mm.max(axis=0)])
                            - stowed.bounds
                        )
                    )
                )
                box_contains = bool(
                    np.all(local.vertices >= broad.bounds[0] - 5.0e-8)
                    and np.all(local.vertices <= broad.bounds[1] + 5.0e-8)
                )
                max_registration = max(float(forward["maximum_mm"]), float(reverse["maximum_mm"]))
                max_localization = max(
                    float(localized_forward["maximum_mm"]), float(localized_reverse["maximum_mm"])
                )
                row.update(
                    {
                        "released_localization_forward_maximum_mm": localized_forward["maximum_mm"],
                        "released_localization_reverse_maximum_mm": localized_reverse["maximum_mm"],
                        "released_q0_to_stow_forward_maximum_mm": forward["maximum_mm"],
                        "released_q0_to_stow_forward_p99_mm": forward["p99_mm"],
                        "released_q0_to_stow_reverse_maximum_mm": reverse["maximum_mm"],
                        "released_q0_to_stow_reverse_p99_mm": reverse["p99_mm"],
                        "released_q0_to_stow_bbox_endpoint_max_abs_residual_mm": bbox_residual,
                        "broadphase_box_contains_released_vertices": box_contains,
                    }
                )
                scope.expect(max_localization <= 0.1, f"{name}: released local PLY does not match inverse-q0 source ({max_localization:.9g} mm)")
                scope.expect(max_registration <= 0.1, f"{name}: released PLY stow registration exceeds 0.1 mm ({max_registration:.9g} mm)")
                scope.expect(box_contains, f"{name}: conservative broadphase box does not contain released PLY")
                scope.equal(item.get("local_surface", {}).get("units"), "m", f"{name} local units")
                scope.equal(item.get("conservative_broadphase_box", {}).get("units"), "m", f"{name} box units")
                scope.equal(item.get("conservative_broadphase_box", {}).get("contains_source_vertices"), True, f"{name} recorded box containment")
                del local, broad, local_mm
            else:
                reconstructed_stow_mm = trimesh.transform_points(expected_local_mm, ts_mm)
                forward = nearest_metrics(reconstructed_stow_mm, stowed.vertices)
                reverse = nearest_metrics(stowed.vertices, reconstructed_stow_mm)
                bbox_residual = float(
                    np.max(
                        np.abs(
                            np.vstack([reconstructed_stow_mm.min(axis=0), reconstructed_stow_mm.max(axis=0)])
                            - stowed.bounds
                        )
                    )
                )
                max_registration = max(float(forward["maximum_mm"]), float(reverse["maximum_mm"]))
                row.update(
                    {
                        "q0_to_stow_forward_maximum_mm": forward["maximum_mm"],
                        "q0_to_stow_forward_p99_mm": forward["p99_mm"],
                        "q0_to_stow_reverse_maximum_mm": reverse["maximum_mm"],
                        "q0_to_stow_reverse_p99_mm": reverse["p99_mm"],
                        "q0_to_stow_bbox_endpoint_max_abs_residual_mm": bbox_residual,
                    }
                )
                scope.expect(max_registration <= 0.1, f"{name}: stow registration exceeds 0.1 mm ({max_registration:.9g} mm)")
                scope.equal(
                    item.get("disposition"),
                    "SUPERSEDED_FOR_ACTIVE_GRIPPER_GEOMETRY_BY_R1_SEPARATED_PALM_AND_FINGERS",
                    "legacy gripper disposition",
                )

            recorded_registration = item.get("independent_q0_to_stow_registration", {})
            scope.equal(recorded_registration.get("pass"), True, f"{name} recorded registration pass")
            scope.equal(recorded_registration.get("numerical_acceptance_mm"), 0.1, f"{name} recorded acceptance")
            residual_table.append(row)
            del deployed, stowed, expected_local_mm, reconstructed_stow_mm
            gc.collect()

        scope.equal(frame.get("all_components_below_0p1mm"), True, "frame aggregate pass")
        scope.equal(frame.get("status"), "PASS_SOURCE_BOUND_LINK_LOCALIZATION_FOR_DIGITAL_GEOMETRY", "frame status")
        scope.details = {
            "units": {"source_and_residual": "mm", "released_surfaces": "m"},
            "numerical_acceptance_mm": 0.1,
            "physical_clearance_or_metrology_claim": False,
            "component_residuals": residual_table,
        }
        return scope

    recorder.run("M5-V-010", "independent B601 frame localization residuals", check_frame_localization)

    def check_gripper_binding() -> Scope:
        scope = Scope()
        science_required()
        frame = required_doc("frame")
        model, _pose, mount = get_kinematics()
        joints = model["joints"]
        fixed = joints.get("gripper_joint")
        if not isinstance(fixed, dict):
            raise ValidationDataError("accepted URDF has no gripper_joint")
        scope.equal(fixed.get("type"), "fixed", "gripper_joint type")
        scope.equal(fixed.get("parent"), "link6", "gripper_joint parent")
        scope.equal(fixed.get("child"), "gripper_link", "gripper_joint child")
        origin_xyz = np.asarray(fixed.get("origin_xyz"), dtype=float)
        origin_rpy = np.asarray(fixed.get("origin_rpy"), dtype=float)
        scope.expect(np.allclose(origin_xyz, [0.0, 0.0, 0.15971], rtol=0.0, atol=1.0e-12), f"gripper_joint xyz mismatch: {origin_xyz.tolist()}")
        scope.expect(np.allclose(origin_rpy, [0.0, -1.5708, 0.0], rtol=0.0, atol=1.0e-12), f"gripper_joint rpy mismatch: {origin_rpy.tolist()}")

        active = frame.get("active_gripper_r1")
        if not isinstance(active, dict):
            raise ValidationDataError("active_gripper_r1 missing")
        source_vertices: list[Any] = []
        asset_hashes: dict[str, dict[str, Any]] = {}
        for role in ("palm", "left_finger", "right_finger"):
            record = active.get(role)
            if not isinstance(record, dict):
                scope.errors.append(f"active gripper role missing: {role}")
                continue
            scope.equal(record.get("frame"), "gripper_link", f"{role} frame")
            source_path = verify_reference(scope, record.get("source"), WORKSPACE, f"{role} source")
            local_path = verify_reference(scope, record.get("local_surface"), WORKSPACE, f"{role} local surface")
            broad_path = verify_reference(scope, record.get("broadphase_box"), WORKSPACE, f"{role} broadphase")
            scope.equal(record.get("source", {}).get("source_units"), "mm", f"{role} source units")
            scope.equal(record.get("local_surface", {}).get("units"), "m", f"{role} local units")
            scope.equal(record.get("broadphase_box", {}).get("units"), "m", f"{role} broadphase units")
            source_array = None
            if source_path is not None:
                mesh = load_mesh(source_path)
                source_array = np.asarray(mesh.vertices, dtype=float)
                source_vertices.append(source_array)
                del mesh
            if local_path is not None and broad_path is not None:
                local = load_mesh(local_path)
                broad = load_mesh(broad_path)
                scope.expect(
                    bool(np.all(local.vertices >= broad.bounds[0] - 5.0e-8) and np.all(local.vertices <= broad.bounds[1] + 5.0e-8)),
                    f"{role}: broadphase box does not contain released gripper surface",
                )
                local_forward = None
                local_reverse = None
                if source_array is None:
                    scope.errors.append(f"{role}: source geometry unavailable for released-local verification")
                else:
                    local_vertices_mm = np.asarray(local.vertices, dtype=float) * 1000.0
                    local_forward = nearest_metrics(local_vertices_mm, source_array)
                    local_reverse = nearest_metrics(source_array, local_vertices_mm)
                    maximum_local_error = max(
                        float(local_forward["maximum_mm"]),
                        float(local_reverse["maximum_mm"]),
                    )
                    scope.expect(
                        maximum_local_error <= 0.001,
                        f"{role}: released gripper PLY differs from source STL/1000 by {maximum_local_error:.9g} mm",
                    )
                    recorded_bounds = np.asarray(
                        record.get("local_surface", {}).get("bounds_gripper_link_m"),
                        dtype=float,
                    )
                    bounds_error_m = (
                        float(np.max(np.abs(recorded_bounds - local.bounds)))
                        if recorded_bounds.shape == (2, 3)
                        else math.inf
                    )
                    scope.expect(bounds_error_m <= 5.0e-8, f"{role}: recorded local bounds residual {bounds_error_m} m")
                asset_hashes[role] = {
                    "source_sha256": sha256(source_path) if source_path is not None else "",
                    "local_surface_sha256": sha256(local_path),
                    "broadphase_sha256": sha256(broad_path),
                    "source_to_released_local_maximum_mm": local_reverse["maximum_mm"] if local_reverse else None,
                    "released_local_to_source_maximum_mm": local_forward["maximum_mm"] if local_forward else None,
                }
                del local, broad

        motion = active.get("motion_contract")
        if not isinstance(motion, dict):
            raise ValidationDataError("gripper motion_contract missing")
        registration = motion.get("frame_registration")
        if not isinstance(registration, dict):
            raise ValidationDataError("gripper frame_registration missing")
        scope.equal(motion.get("neutral_source_semantics"), "CLOSED_TRAVEL_ZERO", "gripper neutral semantics")
        scope.equal(motion.get("source_receipt_frame_label"), "LINK6_LOCAL", "source receipt frame label")
        scope.equal(motion.get("corrected_frame_binding"), "gripper_link", "corrected gripper frame binding")
        scope.equal(registration.get("accepted_binding"), "gripper_link", "accepted gripper binding")
        scope.equal(registration.get("gripper_link_registration_pass"), True, "gripper_link registration pass")
        scope.equal(registration.get("direct_link6_binding_rejected"), True, "direct link6 binding rejection")
        scope.expect("HOLD" in str(registration.get("source_label_conflict_status", "")), "source frame-label conflict is not explicitly HOLD")
        scope.equal(motion.get("configuration_travel_authority"), None, "configuration-to-travel authority")
        scope.expect("HOLD" in str(motion.get("travel_conflict_disposition", "")), "travel sequence conflict is not HOLD")
        scope.equal(motion.get("contact_and_strength_status"), "HOLD", "gripper contact/strength status")
        scope.expect("HOLD" in str(motion.get("manufacturing_clearance_status", "")), "manufacturing clearance is not HOLD")
        scope.equal(motion.get("manufacturing_additional_clearance_m"), None, "manufacturing additional clearance")

        witnesses = motion.get("conflicting_non_authoritative_travel_witnesses_m", {})
        r1_witness = witnesses.get("R1_geometry_witness", {}) if isinstance(witnesses, dict) else {}
        alt_witness = witnesses.get("alternate_equal_increment_witness", {}) if isinstance(witnesses, dict) else {}
        scope.equal(r1_witness.get("values_m"), [0.0, 0.03575, 0.055, 0.0715], "R1 travel witness")
        scope.equal(alt_witness.get("values_m"), [0.0, 0.023833, 0.047667, 0.0715], "alternate travel witness")
        scope.expect("HOLD" in str(alt_witness.get("source_status", "")), "alternate witness status is not HOLD")
        r1_witness_path = verify_reference(scope, r1_witness.get("source"), WORKSPACE, "R1 travel witness source")
        alt_witness_path = verify_reference(scope, alt_witness.get("source"), WORKSPACE, "alternate travel witness source")
        if r1_witness_path is not None:
            r1_source = read_json(r1_witness_path)
            source_poses = r1_source.get("continuous_stroke_acceptance", {}).get("poses", {})
            scope.equal(set(source_poses), {"CLOSED", "PARTIAL", "PREGRASP", "OPEN"}, "R1 source travel pose names")
            try:
                r1_values_from_source_m = [
                    float(source_poses[name]["travel_mm"]) / 1000.0
                    for name in ("CLOSED", "PARTIAL", "PREGRASP", "OPEN")
                ]
                scope.expect(
                    np.allclose(r1_values_from_source_m, r1_witness.get("values_m"), rtol=0.0, atol=1.0e-12),
                    "R1 witness values do not match parsed geometry-validation source",
                )
            except Exception as exc:
                scope.errors.append(f"R1 travel source parse failed: {exc}")
        if alt_witness_path is not None:
            _alt_header, alt_rows = read_csv_strict(alt_witness_path)
            gripper_rows = [row for row in alt_rows if row.get("configuration_class") == "GRIPPER"]
            expected_names = ["GRIPPER_CLOSED", "GRIPPER_PARTIAL", "GRIPPER_PREGRASP", "GRIPPER_OPEN"]
            scope.equal([row.get("configuration") for row in gripper_rows], expected_names, "alternate source gripper rows")
            parsed_alt_values: list[float] = []
            for row in gripper_rows:
                match = re.fullmatch(r"left/right prismatic=([0-9]+(?:\.[0-9]+)?) m", row.get("unique_geometry_summary", ""))
                if match is None:
                    scope.errors.append(f"alternate source travel unparsable: {row.get('unique_geometry_summary')!r}")
                    continue
                parsed_alt_values.append(float(match.group(1)))
                scope.equal(row.get("independent_activation"), "SEMANTIC_STATE_ONLY", f"{row.get('configuration')} semantic authority")
                scope.expect("HOLD" in row.get("native_rebuild", ""), f"{row.get('configuration')}: native rebuild is not HOLD")
            scope.expect(
                np.allclose(parsed_alt_values, alt_witness.get("values_m"), rtol=0.0, atol=1.0e-12),
                "alternate witness values do not match parsed CONFIGURATION_MATRIX source",
            )

        q_zero = {f"joint{index}": 0.0 for index in range(1, 7)}
        fk_zero = urdf_fk(model, q_zero, mount)
        legacy = load_mesh(
            workspace_file(
                "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_DEPLOYED/B51_REF_gripper_detail_LINKLOCAL.stl"
            )
        )
        if len(source_vertices) != 3:
            raise ValidationDataError("could not load all three R1 gripper source meshes")
        aggregate = np.vstack(source_vertices)
        r1_bounds = np.vstack([aggregate.min(axis=0), aggregate.max(axis=0)])
        t_s_link6 = fk_zero["link6"]
        t_s_gripper = t_s_link6 @ fixed["origin"]
        legacy_gripper = trimesh.transform_points(legacy.vertices, np.linalg.inv(transform_mm(t_s_gripper)))
        legacy_link6 = trimesh.transform_points(legacy.vertices, np.linalg.inv(transform_mm(t_s_link6)))
        gripper_error = float(
            np.max(np.abs(np.vstack([legacy_gripper.min(axis=0), legacy_gripper.max(axis=0)]) - r1_bounds))
        )
        link6_error = float(
            np.max(np.abs(np.vstack([legacy_link6.min(axis=0), legacy_link6.max(axis=0)]) - r1_bounds))
        )
        scope.expect(gripper_error <= 0.001, f"independent gripper_link bbox registration exceeds 0.001 mm: {gripper_error}")
        scope.expect(link6_error > 100.0, f"direct link6 rejection witness is not decisive (>100 mm): {link6_error}")
        scope.expect(abs(float(registration.get("gripper_link_bbox_endpoint_max_abs_error_mm", math.inf)) - gripper_error) <= 1.0e-9, "recorded gripper_link registration error differs from independent result")
        scope.expect(abs(float(registration.get("direct_link6_bbox_endpoint_max_abs_error_mm", -math.inf)) - link6_error) <= 1.0e-9, "recorded direct-link6 error differs from independent result")

        mapped_axes: dict[str, Any] = {}
        for joint_name, expected in (("gripper_joint1", [0.0, -1.0, 0.0]), ("gripper_joint2", [0.0, 1.0, 0.0])):
            joint = joints.get(joint_name)
            if not isinstance(joint, dict):
                scope.errors.append(f"accepted URDF missing {joint_name}")
                continue
            scope.equal(joint.get("type"), "prismatic", f"{joint_name} type")
            scope.equal(joint.get("parent"), "gripper_link", f"{joint_name} parent")
            scope.expect(abs(float(joint.get("lower")) - 0.0) <= 1.0e-12, f"{joint_name} lower travel is not 0 m")
            scope.expect(abs(float(joint.get("upper")) - 0.0715) <= 1.0e-12, f"{joint_name} upper travel is not 0.0715 m")
            mapped = joint["origin"][:3, :3] @ joint["axis"]
            mapped_axes[joint_name] = mapped.tolist()
            scope.expect(np.allclose(mapped, expected, rtol=0.0, atol=5.0e-6), f"{joint_name} mapped gripper-frame axis mismatch: {mapped.tolist()}")
        scope.expect(np.allclose(motion.get("axis_in_gripper_link"), [0.0, 1.0, 0.0], rtol=0.0, atol=1.0e-12), "motion contract axis is not gripper-link +Y")
        scope.equal(motion.get("left_translation_m"), [0.0, -0.0715], "left finger translation range")
        scope.equal(motion.get("right_translation_m"), [0.0, 0.0715], "right finger translation range")

        scope.details = {
            "accepted_binding": "gripper_link",
            "independent_gripper_link_bbox_error_mm": gripper_error,
            "independent_direct_link6_bbox_error_mm": link6_error,
            "finger_axes_in_gripper_link": mapped_axes,
            "asset_hashes": asset_hashes,
            "travel_authority": None,
            "travel_conflict_status": motion.get("travel_conflict_disposition"),
        }
        return scope

    recorder.run("M5-V-011", "accepted gripper binding and finger semantics", check_gripper_binding)

    def check_configurations() -> Scope:
        scope = Scope()
        science_required()
        config = required_doc("config")
        model, pose, _mount = get_kinematics()
        records = config.get("records")
        if not isinstance(records, list):
            raise ValidationDataError("configuration records is not a list")
        expected_ids = list(EXPECTED_CONFIG_NAMES)
        ids = [record.get("configuration_id") for record in records if isinstance(record, dict)]
        scope.equal(config.get("configuration_count"), 9, "configuration_count")
        scope.equal(config.get("required_ids"), expected_ids, "required configuration IDs")
        scope.equal(ids, expected_ids, "configuration record order/IDs")

        q_home = pose["poses"]["Q_DEPLOYED_HOME"]["q_rad"]
        q_stow = pose["poses"]["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"]
        q_ready = pose["poses"]["Q_SERVICE_READY"]["q_rad"]
        q_scene = parse_scene_q(workspace_file(SCENE_REL))
        q_expected = {
            "C01": q_home,
            "C02": q_home,
            "C03": q_home,
            "C04": q_home,
            "C05": q_stow,
            "C06": q_ready,
            "C07": q_scene,
            "C08": q_scene,
            "C09": q_scene,
        }
        joint_names = [f"joint{index}" for index in range(1, 7)]
        snapshot_rows: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                scope.errors.append("configuration record is not a mapping")
                continue
            cid = record.get("configuration_id")
            if cid not in EXPECTED_CONFIG_NAMES:
                continue
            scope.equal(record.get("name"), EXPECTED_CONFIG_NAMES[cid], f"{cid} name")
            q = np.asarray(record.get("q_rad"), dtype=float)
            scope.expect(q.shape == (6,) and np.all(np.isfinite(q)), f"{cid}: q_rad is not six finite radians")
            if q.shape == (6,):
                scope.expect(np.allclose(q, q_expected[cid], rtol=0.0, atol=1.0e-12), f"{cid}: q_rad differs from controlled source")
                limits_valid = True
                for index, joint_name in enumerate(joint_names):
                    joint = model["joints"][joint_name]
                    limits_valid &= float(joint["lower"]) - 1.0e-12 <= q[index] <= float(joint["upper"]) + 1.0e-12
                scope.expect(limits_valid, f"{cid}: q_rad violates accepted URDF limits")
                scope.equal(record.get("joint_limits_valid"), limits_valid, f"{cid} recorded joint-limit validity")
            scope.equal(record.get("diagnostic_only"), True, f"{cid} diagnostic_only")
            scope.equal(record.get("contact_enabled"), False, f"{cid} contact_enabled")
            scope.equal(record.get("mass_properties_authority"), False, f"{cid} mass authority")
            scope.equal(record.get("finger_travel_configuration_authority"), False, f"{cid} finger travel authority")
            scope.equal(record.get("required_capture_gripper_travel_m"), None, f"{cid} required capture travel")
            scope.equal(record.get("released_mass_kg"), None, f"{cid} released mass")
            scope.equal(record.get("released_cg_S_m"), None, f"{cid} released CG")
            scope.equal(record.get("released_inertia_S_kg_m2"), None, f"{cid} released inertia")
            broad = record.get("broadphase", {})
            scope.equal(broad.get("verified_system_collision_clear"), False, f"{cid} collision release")
            scope.equal(broad.get("nonadjacent_pair_count"), 15, f"{cid} nonadjacent pair count")
            scope.expect("NO_NARROW_PHASE_OR_SYSTEM_RELEASE" in str(broad.get("claim_limit", "")), f"{cid}: broadphase claim limit missing")
            scope.expect("HOLD" in str(record.get("status", "")), f"{cid}: status does not preserve HOLD")
            if cid in {"C07", "C08", "C09"}:
                scope.equal(record.get("display_gripper_travel_m"), 0.055, f"{cid} display-only travel witness")
                scope.expect("NOT_CXX_AUTHORITY" in str(record.get("display_gripper_travel_source", "")), f"{cid}: display travel source is not explicitly non-authoritative")
            else:
                scope.equal(record.get("display_gripper_travel_m"), None, f"{cid} display gripper travel")

            snapshot = record.get("snapshot")
            snapshot_path = verify_reference(scope, snapshot, WORKSPACE, f"{cid} snapshot")
            if snapshot_path is not None:
                scene = trimesh.load_scene(snapshot_path, process=False)
                geometry_count = len(scene.geometry)
                bounds = np.asarray(scene.bounds, dtype=float)
                scope.expect(geometry_count > 0, f"{cid}: GLB has no geometry")
                scope.expect(bounds.shape == (2, 3) and np.all(np.isfinite(bounds)), f"{cid}: GLB bounds invalid")
                recorded_bounds = np.asarray(record.get("bbox_S_m"), dtype=float)
                bbox_error = float(np.max(np.abs(bounds - recorded_bounds))) if recorded_bounds.shape == (2, 3) else math.inf
                scope.expect(bbox_error <= 2.0e-6, f"{cid}: GLB bounds differ from contract by {bbox_error} m")
                snapshot_rows.append(
                    {
                        "configuration_id": cid,
                        "path": snapshot.get("path") if isinstance(snapshot, dict) else None,
                        "sha256": sha256(snapshot_path),
                        "geometry_count": geometry_count,
                        "bbox_max_abs_residual_m": bbox_error,
                    }
                )
                del scene
                gc.collect()
        for key in ("released_mass_count", "released_cg_count", "released_inertia_count", "verified_system_collision_count", "contact_enabled_count"):
            scope.equal(config.get(key), 0, key)
        scope.equal(
            config.get("status"),
            "PASS_EXACT_NINE_DIAGNOSTIC_GEOMETRY_SNAPSHOTS_WITH_ALL_PHYSICAL_RELEASE_FIELDS_HOLD",
            "configuration contract status",
        )
        scope.details = {"configuration_ids": ids, "diagnostic_snapshot_count": len(snapshot_rows), "snapshots": snapshot_rows}
        return scope

    recorder.run("M5-V-020", "exact nine diagnostic configurations and snapshots", check_configurations)

    def check_collision_and_authority() -> Scope:
        scope = Scope()
        broad = required_doc("broad")
        config = required_doc("config")
        interface = required_doc("interface")
        gate = required_doc("gate")
        contact = required_doc("contact")
        structural = required_doc("structural")
        expected_ids = list(EXPECTED_CONFIG_NAMES)
        results = broad.get("configuration_results")
        if not isinstance(results, dict):
            raise ValidationDataError("broadphase configuration_results missing")
        scope.equal(list(results), expected_ids, "broadphase configuration IDs")
        allowed_results = {"CONSERVATIVE_CLEAR", "POSSIBLE_OR_TOUCHING_HOLD"}
        config_by_id = {
            row.get("configuration_id"): row
            for row in config.get("records", [])
            if isinstance(row, dict)
        }
        expected_pair_rows = {
            (ARM_LINKS[left_index], ARM_LINKS[right_index])
            for left_index in range(len(ARM_LINKS))
            for right_index in range(left_index + 2, len(ARM_LINKS))
        }
        pair_counts: dict[str, Any] = {}
        for cid in expected_ids:
            result = results.get(cid, {})
            pairs = result.get("pairs", []) if isinstance(result, dict) else []
            pair_keys = {
                (str(pair.get("a")), str(pair.get("b")))
                for pair in pairs
                if isinstance(pair, dict)
            }
            scope.equal(len(pairs), 15, f"{cid} broadphase pair rows")
            scope.equal(len(pair_keys), 15, f"{cid} unique broadphase pairs")
            scope.equal(pair_keys, expected_pair_rows, f"{cid} exact nonadjacent link-pair set")
            scope.expect(all(pair.get("result") in allowed_results for pair in pairs if isinstance(pair, dict)), f"{cid}: invalid broadphase result token")
            clear_count = sum(pair.get("result") == "CONSERVATIVE_CLEAR" for pair in pairs if isinstance(pair, dict))
            hold_count = sum(pair.get("result") == "POSSIBLE_OR_TOUCHING_HOLD" for pair in pairs if isinstance(pair, dict))
            contract_broad = config_by_id.get(cid, {}).get("broadphase", {})
            scope.equal(contract_broad.get("conservative_clear_count"), clear_count, f"{cid} clear count")
            scope.equal(contract_broad.get("possible_or_touching_hold_count"), hold_count, f"{cid} ambiguous count")
            scope.equal(contract_broad.get("target_possible_overlap"), result.get("target_possible_overlap"), f"{cid} target overlap witness")
            pair_counts[cid] = {"clear": clear_count, "ambiguous_hold": hold_count}
        scope.equal(broad.get("method"), "CONSERVATIVE_LINK_AABB_ONLY", "broadphase method")
        scope.equal(broad.get("narrow_phase_available"), False, "narrow-phase availability")
        scope.equal(broad.get("system_collision_release"), False, "system collision release")
        scope.expect("HOLD" in str(broad.get("status", "")), "broadphase aggregate status does not preserve HOLD")

        geometry_caps = interface.get("geometry_capabilities", {})
        load_caps = interface.get("loads_capabilities", {})
        runtime = interface.get("runtime_gates", {})
        scope.equal(geometry_caps.get("narrow_phase_verified"), False, "interface narrow-phase authority")
        scope.equal(geometry_caps.get("contact_geometry_authorized"), False, "interface contact geometry authority")
        scope.equal(load_caps.get("contact_force_time_history"), False, "interface contact force history")
        scope.equal(load_caps.get("physical_load_authority"), False, "interface physical load authority")
        scope.equal(runtime.get("physical_contact"), "HOLD", "interface physical contact gate")
        scope.equal(runtime.get("structural_analysis"), "HOLD", "interface structural gate")
        scope.equal(runtime.get("physics_gated_RL"), "HOLD", "interface RL gate")
        scope.equal(interface.get("zero_fill_forbidden"), True, "interface zero-fill rule")
        scope.equal(contact.get("physical_contact_kernel_authorized"), False, "physical contact kernel authority")
        scope.equal(structural.get("formal_fea_authorized"), False, "formal FEA authority")
        scope.equal(gate.get("verified_system_collision_configuration_count"), 0, "released collision configuration count")
        scope.equal(gate.get("physical_contact_parameters_ready"), False, "released contact readiness")
        scope.equal(gate.get("structural_analysis_ready"), False, "released structural readiness")
        scope.equal(gate.get("physics_gated_contact_rl_ready"), False, "released RL readiness")
        scope.details = {
            "pair_counts": pair_counts,
            "authority": {
                "system_collision": False,
                "configuration_mass_properties": False,
                "physical_contact": False,
                "structural": False,
                "physics_gated_RL": False,
            },
        }
        return scope

    recorder.run("M5-V-021", "collision, mass, contact, and RL authority remains false", check_collision_and_authority)

    def check_load_migration() -> Scope:
        scope = Scope()
        load = required_doc("load")
        if "load_csv" not in csv_docs:
            raise ValidationDataError("parsed M5 load migration CSV unavailable")
        _header, migrated_rows = csv_docs["load_csv"]
        _source_header, source_rows = read_csv_strict(workspace_file(SOURCE_LOAD_CASES_REL))
        _combo_header, combo_rows = read_csv_strict(workspace_file(SOURCE_LOAD_COMBOS_REL))
        _gap_header, gap_rows = read_csv_strict(workspace_file(SOURCE_LOAD_GAPS_REL))
        source_by_id = {row["case_id"]: row for row in source_rows}
        migrated_by_id = {row["case_id"]: row for row in migrated_rows}
        scope.equal(len(source_by_id), len(source_rows), "unique source load case count")
        scope.equal(len(migrated_by_id), len(migrated_rows), "unique migrated load case count")
        scope.equal(set(migrated_by_id), set(source_by_id), "migrated/source case IDs")
        for case_id, source in source_by_id.items():
            row = migrated_by_id.get(case_id)
            if row is None:
                continue
            for field in ("load_family", "coordinate_frame", "claim_limit"):
                scope.equal(row.get(field), source.get(field), f"{case_id} preserved {field}")
            scope.equal(row.get("source_status"), source.get("status"), f"{case_id} preserved source status")
            if case_id == "LC-010":
                scope.equal(row.get("m5_disposition"), "REJECTED_AS_NUMERICAL_LOAD_INPUT", "LC-010 disposition")
                scope.expect("VIOLATES_ACCEPTED_UPPER_LIMIT_ZERO" in row.get("m5_status", ""), "LC-010 invalid +60 deg status missing")
            elif case_id in {"LC-013", "LC-014"}:
                scope.equal(row.get("m5_disposition"), "SUPERSEDED_FOR_REPRODUCIBILITY_BY_SIM15_DIAGNOSTIC_ENVELOPE", f"{case_id} disposition")
                scope.equal(row.get("m5_status"), "DIAGNOSTIC_IMPULSE_ONLY_CONTACT_FORCE_HOLD", f"{case_id} status")
            elif case_id == "LC-021":
                scope.equal(row.get("m5_disposition"), "ADMITTED_TO_M5_ANALYTIC_JOINT_SENSITIVITY_ONLY", "LC-021 disposition")
                scope.equal(row.get("m5_status"), "AUTHORIZED_ANALYTIC_GEOMETRY_CHARACTERIZATION_NO_FEA", "LC-021 scope")
            else:
                scope.equal(row.get("m5_disposition"), "RETAINED_HOLD_NO_NEW_PHYSICAL_AUTHORITY", f"{case_id} disposition")
                scope.equal(row.get("m5_status"), source.get("status"), f"{case_id} retained status")
            if case_id != "LC-021":
                scope.expect("FORMAL_FEA" not in row.get("m5_status", "") and "FLIGHT_MOS" not in row.get("m5_status", ""), f"{case_id}: prohibited physical authority promotion")

        counts = load.get("source_counts", {})
        scope.equal(counts.get("load_cases"), len(source_rows), "source load case count")
        scope.equal(counts.get("combinations"), len(combo_rows), "source load combination count")
        scope.equal(counts.get("gaps"), len(gap_rows), "source load gap count")
        old = load.get("old_boundary_ruling", {})
        replacement = load.get("replacement_boundary_contract", {})
        invalid = load.get("invalid_trajectory_ruling", {})
        gap = load.get("gap_closure", {})
        scope.equal(old.get("boundary_id"), "BC-M3R-001", "old boundary ID")
        scope.equal(old.get("parent_frame"), "M_FRAME", "old boundary frame")
        scope.equal(old.get("disposition"), "REJECTED_FOR_PHYSICAL_LOAD_APPLICATION", "old boundary disposition")
        for field in ("T_M_DYNAMICS_FROM_SPACECRAFT_LOAD_BRIDGE_MATING_DATUM", "stiffness_6x6", "fastener_preload_N", "friction_coefficient"):
            scope.equal(replacement.get(field), None, f"replacement boundary {field}")
        scope.expect("HOLD" in str(replacement.get("status", "")), "replacement boundary status is not HOLD")
        scope.equal(replacement.get("formal_fea_use"), "PROHIBITED", "replacement boundary FEA use")
        scope.equal(invalid.get("source_case"), "LC-010", "invalid trajectory case")
        scope.equal(invalid.get("source_joint2_command_deg"), 60.0, "invalid joint2 command (deg)")
        scope.equal(invalid.get("accepted_joint2_limits_deg"), [-179.908748, 0.0], "accepted joint2 limits (deg)")
        scope.equal(invalid.get("disposition"), "REJECTED_AS_LOAD_INPUT", "invalid trajectory ruling")
        scope.equal(gap.get("LG-019_capture_impulse_reproducibility"), "PENDING_SIM15_HASH_BOUND_RERUN", "LG-019 state")
        scope.equal(gap.get("remaining_open_gap_count"), len(gap_rows), "remaining load gaps")
        scope.equal(gap.get("physical_load_authority_gap_count"), len(gap_rows), "physical authority gaps")
        scope.equal(load.get("formal_loads_authorized"), False, "formal loads authority")
        scope.expect("HOLD" in str(load.get("status", "")), "load migration aggregate status does not preserve physical HOLD")
        scope.details = {
            "load_case_count": len(source_rows),
            "load_combination_count": len(combo_rows),
            "load_gap_count": len(gap_rows),
            "formal_loads_authorized": False,
            "replacement_boundary_physical_fields": None,
        }
        return scope

    recorder.run("M5-V-030", "load-authority migration and invalid trajectory ruling", check_load_migration)

    def check_joint_model() -> Scope:
        scope = Scope()
        science_required()
        joint = required_doc("joint")
        if "joint_csv" not in csv_docs:
            raise ValidationDataError("parsed influence-matrix CSV unavailable")
        header, rows = csv_docs["joint_csv"]
        expected_header = ["pattern", "fastener_index", "y_m", "z_m", "response", "Fx", "Fy", "Fz", "Mx_per_m", "My_per_m", "Mz_per_m"]
        scope.equal(header, expected_header, "influence CSV header")
        scope.equal(joint.get("units"), {"force": "N", "moment": "N*m", "coordinate": "m", "influence_moment_terms": "1/m"}, "joint model units")
        patterns = joint.get("patterns")
        if not isinstance(patterns, dict):
            raise ValidationDataError("joint patterns missing")
        scope.equal(set(patterns), {"B601_TO_STAGE_A_4XM4_64MM", "STAGE_A_TO_B_8XM5_R62P5MM", "STAGE_B_TO_SPACECRAFT_4XM6_140MM"}, "joint pattern names")
        expected_csv: dict[tuple[str, int, str], list[float]] = {}
        maximum_matrix_error = 0.0
        for name, pattern in patterns.items():
            coordinates = np.asarray(pattern.get("coordinates_yz_m"), dtype=float)
            matrices = np.asarray(pattern.get("influence_matrices"), dtype=float)
            n = len(coordinates)
            scope.expect(coordinates.shape == (n, 2) and n > 0 and np.all(np.isfinite(coordinates)), f"{name}: coordinates invalid")
            scope.expect(matrices.shape == (n, 3, 6) and np.all(np.isfinite(matrices)), f"{name}: influence matrix dimensions invalid")
            if coordinates.shape != (n, 2) or matrices.shape != (n, 3, 6):
                continue
            sum_y2 = float(np.sum(coordinates[:, 0] ** 2))
            sum_z2 = float(np.sum(coordinates[:, 1] ** 2))
            sum_r2 = sum_y2 + sum_z2
            scope.expect(sum_y2 > 0.0 and sum_z2 > 0.0 and sum_r2 > 0.0, f"{name}: singular fastener pattern")
            scope.expect(abs(float(pattern.get("sum_y2_m2")) - sum_y2) <= 1.0e-14, f"{name}: sum_y2 mismatch")
            scope.expect(abs(float(pattern.get("sum_z2_m2")) - sum_z2) <= 1.0e-14, f"{name}: sum_z2 mismatch")
            scope.expect(abs(float(pattern.get("sum_r2_m2")) - sum_r2) <= 1.0e-14, f"{name}: sum_r2 mismatch")
            scope.equal(pattern.get("fastener_count"), n, f"{name} fastener count")
            for index, (y_value, z_value) in enumerate(coordinates, start=1):
                expected = np.array(
                    [
                        [1.0 / n, 0.0, 0.0, 0.0, z_value / sum_z2, -y_value / sum_y2],
                        [0.0, 1.0 / n, 0.0, -z_value / sum_r2, 0.0, 0.0],
                        [0.0, 0.0, 1.0 / n, y_value / sum_r2, 0.0, 0.0],
                    ]
                )
                error = float(np.max(np.abs(matrices[index - 1] - expected)))
                maximum_matrix_error = max(maximum_matrix_error, error)
                scope.expect(error <= 1.0e-12, f"{name} fastener {index}: influence formula residual {error}")
                for response_index, response in enumerate(("N_axial", "Qy", "Qz")):
                    expected_csv[(name, index, response)] = [float(y_value), float(z_value)] + expected[response_index].tolist()
        scope.equal(len(rows), len(expected_csv), "influence CSV row count")
        seen_keys: set[tuple[str, int, str]] = set()
        for row in rows:
            try:
                key = (row["pattern"], int(row["fastener_index"]), row["response"])
                values = [float(row[field]) for field in ("y_m", "z_m", "Fx", "Fy", "Fz", "Mx_per_m", "My_per_m", "Mz_per_m")]
            except Exception as exc:
                scope.errors.append(f"invalid influence CSV row {row!r}: {exc}")
                continue
            if key in seen_keys:
                scope.errors.append(f"duplicate influence CSV key: {key}")
            seen_keys.add(key)
            expected = expected_csv.get(key)
            scope.expect(expected is not None, f"unexpected influence CSV key: {key}")
            if expected is not None:
                scope.expect(np.allclose(values, expected, rtol=0.0, atol=1.0e-12), f"influence CSV values mismatch: {key}")
        uncertainty = joint.get("uncertainty", {})
        for field in ("coordinate_standard_uncertainty_m", "distribution", "degrees_of_freedom"):
            scope.equal(uncertainty.get(field), None, f"joint uncertainty {field}")
        scope.expect("HOLD" in str(uncertainty.get("status", "")), "joint coordinate uncertainty is not HOLD")
        scope.equal(joint.get("allowed_use"), "GEOMETRIC_WRENCH_DISTRIBUTION_SENSITIVITY_AND_SOFTWARE_VERIFICATION", "joint allowed use")
        prohibited = set(joint.get("prohibited_uses", []))
        scope.expect({"FASTENER_STRENGTH", "PRELOAD_MARGIN", "SLIP_OR_SEPARATION", "PLATE_STRESS", "FLIGHT_MOS"} <= prohibited, "joint prohibited-use set incomplete")
        scope.expect("HOLD" in str(joint.get("status", "")), "joint model status does not preserve strength HOLD")
        scope.details = {
            "pattern_count": len(patterns),
            "influence_csv_row_count": len(rows),
            "maximum_formula_residual": maximum_matrix_error,
            "strength_authority": False,
        }
        return scope

    recorder.run("M5-V-031", "analytic joint-load influence model", check_joint_model)

    def check_contact_contract() -> Scope:
        scope = Scope()
        contact = required_doc("contact")
        plan = required_doc("contact_plan")
        scope.equal(contact.get("units_policy"), "SI_AT_API_BOUNDARY_AND_EXPLICIT_CONVERSION_FROM_SOURCE_MM", "contact units policy")
        scope.equal(contact.get("zero_fill_forbidden"), True, "contact zero-fill rule")
        scope.equal(
            set(contact),
            {
                "schema",
                "units_policy",
                "zero_fill_forbidden",
                "normal_contact",
                "tangential_contact",
                "gripper_actuator",
                "contact_geometry",
                "structural_mapping",
                "computed_contact_force_N",
                "computed_contact_pressure_Pa",
                "physical_contact_kernel_authorized",
                "status",
            },
            "contact contract exact root fields",
        )
        family_units = {
            "normal_contact": {
                "normal_stiffness_N_per_m": "N/m",
                "normal_damping_N_s_per_m": "N*s/m",
                "exponent": "1",
                "coefficient_of_restitution": "1",
                "regularization_velocity_mps": "m/s",
            },
            "tangential_contact": {
                "static_friction": "1",
                "kinetic_friction": "1",
                "tangential_stiffness_N_per_m": "N/m",
                "tangential_damping_N_s_per_m": "N*s/m",
                "stick_slip_transition_velocity_mps": "m/s",
            },
        }
        parameter_fields = {
            "estimate",
            "unit",
            "standard_uncertainty",
            "distribution",
            "degrees_of_freedom",
            "correlation_group",
            "source",
            "status",
        }
        for family, expected_units in family_units.items():
            entries = contact.get(family)
            if not isinstance(entries, dict):
                scope.errors.append(f"{family}: missing mapping")
                continue
            expected_keys = set(expected_units)
            if family == "normal_contact":
                expected_keys.add("model_family")
                scope.equal(entries.get("model_family"), None, "normal_contact.model_family")
            scope.equal(set(entries), expected_keys, f"{family} exact parameter names")
            for name, expected_unit in expected_units.items():
                parameter = entries.get(name)
                if not isinstance(parameter, dict):
                    scope.errors.append(f"{family}.{name}: malformed parameter")
                    continue
                scope.equal(set(parameter), parameter_fields, f"{family}.{name} exact fields")
                for key in ("estimate", "standard_uncertainty", "distribution", "degrees_of_freedom", "correlation_group", "source"):
                    scope.equal(parameter.get(key), None, f"{family}.{name}.{key}")
                scope.expect("HOLD" in str(parameter.get("status", "")), f"{family}.{name}: status is not HOLD")
                scope.equal(parameter.get("unit"), expected_unit, f"{family}.{name}.unit")
        actuator_units = {
            "stroke_m": "m",
            "first_contact_closing_velocity_mps": "m/s",
            "continuous_force_N": "N",
            "peak_force_N": "N",
            "power_off_holding_force_N": "N",
            "control_latency_s": "s",
        }
        actuator = contact.get("gripper_actuator")
        if not isinstance(actuator, dict):
            scope.errors.append("gripper_actuator: missing mapping")
            actuator = {}
        scope.equal(set(actuator), set(actuator_units), "gripper actuator exact parameter names")
        for name, expected_unit in actuator_units.items():
            parameter = actuator.get(name)
            if not isinstance(parameter, dict):
                scope.errors.append(f"gripper_actuator.{name}: malformed parameter")
                continue
            scope.equal(set(parameter), parameter_fields, f"gripper_actuator.{name} exact fields")
            scope.equal(parameter.get("unit"), expected_unit, f"gripper_actuator.{name}.unit")
            if name == "stroke_m":
                scope.equal(parameter.get("estimate"), 0.0715, "gripper stroke estimate (m)")
                scope.equal(
                    str(parameter.get("source", "")).replace("\\", "/"),
                    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
                    "gripper stroke source",
                )
                scope.expect("HOLD" in str(parameter.get("status", "")), "gripper stroke uncertainty is not HOLD")
            else:
                scope.equal(parameter.get("estimate"), None, f"gripper_actuator.{name}.estimate")
                scope.equal(parameter.get("source"), None, f"gripper_actuator.{name}.source")
                scope.expect("HOLD" in str(parameter.get("status", "")), f"gripper_actuator.{name}: status is not HOLD")
            for key in ("standard_uncertainty", "distribution", "degrees_of_freedom", "correlation_group"):
                scope.equal(parameter.get(key), None, f"gripper_actuator.{name}.{key}")
        geometry = contact.get("contact_geometry")
        if not isinstance(geometry, dict):
            scope.errors.append("contact_geometry: missing mapping")
            geometry = {}
        scope.equal(
            set(geometry),
            {
                "left_contact_frame_T_gripper_link",
                "right_contact_frame_T_gripper_link",
                "target_surface_normal",
                "effective_area_m2",
                "initial_gap_m",
            },
            "contact geometry exact fields",
        )
        for key in ("left_contact_frame_T_gripper_link", "right_contact_frame_T_gripper_link", "target_surface_normal"):
            scope.equal(geometry.get(key), None, f"contact geometry {key}")
        for key, expected_unit in (("effective_area_m2", "m^2"), ("initial_gap_m", "m")):
            parameter = geometry.get(key, {})
            scope.equal(set(parameter) if isinstance(parameter, dict) else set(), parameter_fields, f"contact geometry {key} exact fields")
            scope.equal(parameter.get("estimate"), None, f"contact geometry {key} estimate")
            scope.equal(parameter.get("unit"), expected_unit, f"contact geometry {key} unit")
            for uncertainty_key in ("standard_uncertainty", "distribution", "degrees_of_freedom", "correlation_group", "source"):
                scope.equal(parameter.get(uncertainty_key), None, f"contact geometry {key} {uncertainty_key}")
            scope.expect("HOLD" in str(parameter.get("status", "")), f"contact geometry {key} status")
        structural_mapping = contact.get("structural_mapping")
        if not isinstance(structural_mapping, dict):
            scope.errors.append("structural_mapping: missing mapping")
            structural_mapping = {}
        scope.equal(
            set(structural_mapping),
            {"T_wrist_from_contact", "T_arm_base_from_wrist", "T_m3r_from_arm_base", "T_load_bridge_from_m3r", "status"},
            "contact structural mapping exact fields",
        )
        scope.equal(structural_mapping.get("T_wrist_from_contact"), None, "contact-to-wrist transform")
        scope.equal(structural_mapping.get("T_arm_base_from_wrist"), "AVAILABLE_AS_FUNCTION_OF_Q_FROM_ACCEPTED_URDF", "wrist-to-arm-base scope")
        scope.equal(structural_mapping.get("T_m3r_from_arm_base"), "DIGITAL_GEOMETRY_ONLY", "arm-base-to-M3R scope")
        scope.equal(structural_mapping.get("T_load_bridge_from_m3r"), None, "M3R-to-load-bridge transform")
        scope.expect("HOLD" in str(structural_mapping.get("status", "")), "contact structural mapping is not HOLD")
        scope.equal(contact.get("computed_contact_force_N"), None, "computed contact force")
        scope.equal(contact.get("computed_contact_pressure_Pa"), None, "computed contact pressure")
        scope.equal(contact.get("physical_contact_kernel_authorized"), False, "physical contact kernel")
        scope.expect("HOLD" in str(contact.get("status", "")), "contact contract aggregate status is not HOLD")

        tests = plan.get("tests")
        if not isinstance(tests, list):
            raise ValidationDataError("contact test plan tests missing")
        scope.equal([test.get("id") for test in tests if isinstance(test, dict)], ["CT-01", "CT-02", "CT-03", "CT-04", "CT-05"], "contact test IDs")
        for test in tests:
            if isinstance(test, dict):
                scope.expect("HOLD" in str(test.get("status", "")), f"{test.get('id')}: test status is not HOLD")
                scope.expect(bool(test.get("raw_channels")), f"{test.get('id')}: raw channels missing")
                scope.expect(bool(test.get("outputs")), f"{test.get('id')}: outputs missing")
        analysis = plan.get("analysis", {})
        scope.equal(set(plan), {"schema", "status", "metrology_rule", "tests", "analysis"}, "contact test-plan exact root fields")
        scope.equal(set(analysis), {"gum_linearized", "monte_carlo", "correlations", "acceptance_thresholds"}, "contact analysis exact fields")
        scope.equal(analysis.get("gum_linearized"), "REQUIRED", "GUM requirement")
        scope.equal(analysis.get("monte_carlo"), "REQUIRED_FOR_NONLINEAR_OR_GT20_PERCENT_RELATIVE_UNCERTAINTY", "Monte Carlo requirement")
        scope.equal(analysis.get("correlations"), "MUST_BE_PRESERVED", "correlation requirement")
        scope.equal(analysis.get("acceptance_thresholds"), None, "contact acceptance thresholds")
        scope.expect("HOLD" in str(plan.get("status", "")), "contact test plan aggregate status is not HOLD")
        scope.details = {
            "test_count": len(tests),
            "physical_contact_kernel_authorized": False,
            "computed_contact_force_N": None,
            "computed_contact_pressure_Pa": None,
            "unknown_physical_parameters_zero_filled": False,
        }
        return scope

    recorder.run("M5-V-040", "contact identification and metrology hold contract", check_contact_contract)

    def check_structural_and_fea() -> Scope:
        scope = Scope()
        structural = required_doc("structural")
        phase = required_doc("phase")
        gate = required_doc("gate")
        scope.equal(structural.get("gate_status"), "HOLD", "structural gate status")
        scope.equal(structural.get("pass_token"), "STRUCTURAL_ANALYSIS_READY", "structural pass token name")
        scope.equal(structural.get("pass_token_issued"), False, "structural pass token issued")
        scope.equal(structural.get("formal_fea_authorized"), False, "formal FEA authorized")
        scope.equal(structural.get("formal_fea_run_count"), 0, "structural formal FEA count")
        subgates = structural.get("mandatory_subgates")
        if not isinstance(subgates, dict) or not subgates:
            scope.errors.append("mandatory structural subgates missing")
        else:
            scope.equal(
                set(subgates),
                {
                    "controlled_structural_geometry",
                    "load_cases_and_factors",
                    "boundary_conditions",
                    "contact_and_fastener_definition",
                    "material_allowables",
                    "configuration_mass_properties",
                    "mesh_convergence_and_quality_plan",
                    "acceptance_criteria",
                },
                "exact mandatory structural subgates",
            )
            for name, status in subgates.items():
                scope.expect(str(status).startswith(("HOLD", "PENDING")), f"structural subgate {name} is not HOLD/PENDING: {status!r}")
        scope.equal(phase.get("formal_fea_run_count"), 0, "phase formal FEA count")
        scope.equal(gate.get("formal_fea_run_count"), 0, "release formal FEA count")
        scope.equal(gate.get("structural_analysis_ready"), False, "release structural readiness")
        forbidden_suffixes = {".inp", ".odb", ".cae", ".fil", ".sta", ".msg", ".sim", ".prt", ".res", ".lck"}
        solver_artifacts = sorted(
            path.relative_to(M5).as_posix()
            for path in M5.rglob("*")
            if path.is_file() and path.suffix.casefold() in forbidden_suffixes
        )
        scope.expect(not solver_artifacts, f"formal solver artifacts found inside M5: {solver_artifacts}")
        scope.details = {
            "formal_fea_authorized": False,
            "formal_fea_run_count": 0,
            "formal_solver_artifacts": solver_artifacts,
            "mandatory_subgate_count": len(subgates) if isinstance(subgates, dict) else 0,
        }
        return scope

    recorder.run("M5-V-041", "structural entry gate and formal FEA zero", check_structural_and_fea)

    def check_interface_hashes() -> Scope:
        scope = Scope()
        interface = required_doc("interface")
        artifacts = interface.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValidationDataError("interface artifacts missing")
        package_prefix = M5.relative_to(WORKSPACE).as_posix()
        expected_artifacts = {
            "accepted_b601_urdf": URDF_REL,
            "frozen_input_manifest": f"{package_prefix}/{INPUT_MANIFEST_REL}",
            "mesh_frame_decision": f"{package_prefix}/{FRAME_REL}",
            "configuration_contract": f"{package_prefix}/{CONFIG_REL}",
            "broadphase_audit": f"{package_prefix}/{BROAD_REL}",
            "load_authority_migration": f"{package_prefix}/{LOAD_REL}",
            "joint_load_model": f"{package_prefix}/{JOINT_REL}",
            "contact_parameter_contract": f"{package_prefix}/{CONTACT_REL}",
            "structural_entry_gate": f"{package_prefix}/{STRUCTURAL_REL}",
            "sim14_fixture": "30_simulation/sim_14_m4_digital_prototype_grasping/config/SIM14_DIAGNOSTIC_FIXTURE_V1.json",
            "m4_mass_properties": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
            "target_models": "20_engineering/config/geometry/target_models_v1.yaml",
            "solar_r2b_static_oracle": "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json",
        }
        scope.equal(set(artifacts), set(expected_artifacts), "interface artifact names")
        verified: dict[str, str] = {}
        for name, reference in artifacts.items():
            if not isinstance(reference, dict):
                scope.errors.append(f"interface artifact {name}: malformed reference")
                continue
            scope.equal(reference.get("required"), True, f"interface artifact {name} required")
            scope.equal(
                str(reference.get("path", "")).replace("\\", "/"),
                expected_artifacts.get(name),
                f"interface artifact {name} canonical path",
            )
            path = verify_reference(scope, reference, WORKSPACE, f"interface artifact {name}")
            if path is not None:
                verified[name] = sha256(path)
        scope.equal(interface.get("configuration_ids"), list(EXPECTED_CONFIG_NAMES), "interface configuration IDs")
        scope.equal(interface.get("scope"), "M5_SOURCE_BOUND_GEOMETRY_AND_DIAGNOSTIC_IMPULSE_HANDOFF", "interface scope")
        scope.equal(interface.get("required_acknowledgement"), "I_ACKNOWLEDGE_M5_VALUES_ARE_DIAGNOSTIC_NOT_PHYSICAL_CONTACT_OR_FLIGHT_AUTHORITY", "interface acknowledgement")
        scope.equal(interface.get("zero_fill_forbidden"), True, "interface zero-fill rule")
        scope.details = {"verified_artifact_count": len(verified), "artifact_hashes": verified}
        return scope

    recorder.run("M5-V-050", "simulation handoff nested artifact hashes", check_interface_hashes)

    def check_memory_override() -> Scope:
        scope = Scope()
        phase = required_doc("phase")
        gate = required_doc("gate")
        memory = phase.get("memory_execution")
        if not isinstance(memory, dict):
            raise ValidationDataError("phase memory_execution missing")
        scope.equal(memory.get("legacy_threshold_GiB"), 6.0, "legacy memory threshold (GiB)")
        scope.equal(memory.get("memory_gate_passed"), False, "phase memory gate")
        scope.equal(memory.get("memory_gate_status"), "OWNER_OVERRIDE_LOW_MEMORY", "phase memory gate status")
        scope.equal(memory.get("owner_override_used"), True, "phase owner override")
        scope.equal(memory.get("execution_route"), "LIGHTWEIGHT_NEUTRAL_GEOMETRY_AND_ANALYTIC_LOADS", "phase execution route")
        scope.expect("not re-labelled PASS" in str(memory.get("note", "")), "memory note does not explicitly prohibit relabelling PASS")
        for key in ("available_physical_memory_GiB", "total_physical_memory_GiB"):
            value = memory.get(key)
            if value is not None:
                scope.finite(value, f"memory {key}")
                scope.expect(float(value) >= 0.0, f"memory {key} is negative")
        available = memory.get("available_physical_memory_GiB")
        total = memory.get("total_physical_memory_GiB")
        if isinstance(available, (int, float)) and isinstance(total, (int, float)):
            scope.expect(float(available) <= float(total), "available physical memory exceeds total")
        scope.equal(gate.get("memory_gate_passed"), False, "release memory gate")
        scope.equal(gate.get("memory_gate_status"), "OWNER_OVERRIDE_LOW_MEMORY", "release memory gate status")
        scope.equal(gate.get("owner_override_used"), True, "release owner override")
        scope.expect("MEMORY_GATE_PASS" in set(gate.get("prohibited_claims", [])), "release prohibited claims omit MEMORY_GATE_PASS")
        scope.details = {
            "legacy_threshold_GiB": 6.0,
            "sampled_available_physical_memory_GiB": available,
            "sampled_total_physical_memory_GiB": total,
            "memory_gate_passed": False,
            "owner_override_used": True,
            "override_scope": memory.get("execution_route"),
        }
        return scope

    recorder.run("M5-V-060", "6 GiB memory gate and Owner Override truth", check_memory_override)

    def check_release_gate() -> Scope:
        scope = Scope()
        gate = required_doc("gate")
        frame = required_doc("frame")
        config = required_doc("config")
        load = required_doc("load")
        joint = required_doc("joint")
        structural = required_doc("structural")
        scope.equal(gate.get("b601_mesh_frame_localization_pass"), frame.get("all_components_below_0p1mm"), "gate/frame localization consistency")
        scope.equal(gate.get("true_link_local_surface_count"), 7, "gate arm surface count")
        scope.equal(gate.get("gripper_r1_separated_surface_count"), 3, "gate gripper surface count")
        scope.equal(gate.get("diagnostic_configuration_snapshot_count"), config.get("configuration_count"), "gate configuration count")
        counts = load.get("source_counts", {})
        scope.equal(gate.get("load_case_migration_count"), counts.get("load_cases"), "gate load case count")
        scope.equal(gate.get("load_combination_count"), counts.get("combinations"), "gate combination count")
        scope.equal(gate.get("load_gap_count"), counts.get("gaps"), "gate load gap count")
        scope.equal(gate.get("diagnostic_reproducibility_gap_closed_count"), 0, "gate reproducibility gap closure count")
        scope.equal(gate.get("joint_pattern_count"), len(joint.get("patterns", {})), "gate joint pattern count")
        scope.equal(gate.get("formal_fea_run_count"), structural.get("formal_fea_run_count"), "gate/structural FEA count")
        scope.equal(gate.get("next_stage_authorized"), True, "bounded next-stage authorization")
        scope.equal(gate.get("next_stage_scope"), "SIM15_HASH_BOUND_DIAGNOSTIC_CAPTURE_IMPULSE_AND_JOINT_LOAD_SOFTWARE_ONLY", "bounded next-stage scope")
        expected_prohibitions = {
            "MEMORY_GATE_PASS",
            "SYSTEM_COLLISION_PASS",
            "CONTACT_FORCE_PASS",
            "STRUCTURAL_ANALYSIS_READY",
            "FLIGHT_OR_MANUFACTURING_RELEASE",
            "RL_POLICY_READY",
        }
        scope.expect(expected_prohibitions <= set(gate.get("prohibited_claims", [])), "release prohibited claims incomplete")
        evidence = gate.get("critical_evidence")
        if not isinstance(evidence, dict):
            raise ValidationDataError("release critical_evidence missing")
        package_prefix = M5.relative_to(WORKSPACE).as_posix()
        expected_evidence = {
            "mesh_frame_decision": f"{package_prefix}/{FRAME_REL}",
            "configuration_contract": f"{package_prefix}/{CONFIG_REL}",
            "interface": f"{package_prefix}/{INTERFACE_REL}",
            "contact_contract": f"{package_prefix}/{CONTACT_REL}",
            "structural_gate": f"{package_prefix}/{STRUCTURAL_REL}",
        }
        scope.equal(set(evidence), set(expected_evidence), "release critical evidence names")
        for name, reference in evidence.items():
            if isinstance(reference, dict):
                scope.equal(
                    str(reference.get("path", "")).replace("\\", "/"),
                    expected_evidence.get(name),
                    f"release critical evidence {name} canonical path",
                )
            verify_reference(scope, reference, WORKSPACE, f"release critical evidence {name}")
        scope.equal(
            gate.get("status"),
            "M5_SCOPED_GEOMETRY_AND_LOADS_CLOSURE_PASS_WITH_PHYSICAL_CONTACT_STRUCTURAL_AND_FLIGHT_HOLDS",
            "release gate scoped status",
        )
        scope.details = {
            "bounded_next_stage": gate.get("next_stage_scope"),
            "prohibited_claims": gate.get("prohibited_claims"),
            "physical_release_authority": False,
        }
        return scope

    recorder.run("M5-V-070", "release-gate consistency and bounded next stage", check_release_gate)

    failed = [check for check in recorder.checks if not check["passed"]]
    passed_by_id = {check["id"]: bool(check["passed"]) for check in recorder.checks}
    memory_gate_fact = False if passed_by_id.get("M5-V-060", False) else None
    collision_fact = False if passed_by_id.get("M5-V-021", False) else None
    mass_fact = False if passed_by_id.get("M5-V-020", False) and passed_by_id.get("M5-V-021", False) else None
    contact_fact = False if passed_by_id.get("M5-V-021", False) and passed_by_id.get("M5-V-040", False) else None
    formal_loads_fact = False if passed_by_id.get("M5-V-030", False) and passed_by_id.get("M5-V-021", False) else None
    structural_fact = False if passed_by_id.get("M5-V-041", False) and passed_by_id.get("M5-V-021", False) else None
    formal_fea_count_fact = 0 if passed_by_id.get("M5-V-041", False) else None
    flight_manufacturing_fact = False if passed_by_id.get("M5-V-070", False) else None
    rl_fact = False if passed_by_id.get("M5-V-021", False) else None
    validator_hash = sha256(Path(__file__).resolve())
    receipt = {
        "schema": "M5_VALIDATION_RECEIPT_V1",
        "validated_local": now_local(),
        "validator": {
            "path": Path(__file__).resolve().relative_to(WORKSPACE.resolve()).as_posix(),
            "sha256": validator_hash,
            "execution": "independent fail-closed validation; builder was not imported or modified",
        },
        "package_root": M5.relative_to(WORKSPACE).as_posix(),
        "status": "PASS_SCOPED_M5_VALIDATION_EXPECTED_HOLDS_PRESERVED" if not failed else "FAIL_M5_INTEGRITY_OR_SCOPE",
        "check_count": len(recorder.checks),
        "pass_count": len(recorder.checks) - len(failed),
        "fail_count": len(failed),
        "failed_check_ids": [check["id"] for check in failed],
        "checks": recorder.checks,
        "release_authority": {
            "integrity_and_scoped_diagnostic_validation_passed": not failed,
            "memory_gate_passed": memory_gate_fact,
            "system_collision_authorized": collision_fact,
            "configuration_mass_properties_authorized": mass_fact,
            "physical_contact_authorized": contact_fact,
            "formal_loads_authorized": formal_loads_fact,
            "structural_analysis_authorized": structural_fact,
            "formal_fea_run_count": formal_fea_count_fact,
            "formal_fea_verification_status": "VERIFIED_ZERO" if formal_fea_count_fact == 0 else "UNVERIFIED",
            "flight_or_manufacturing_release_authorized": flight_manufacturing_fact,
            "physics_gated_RL_authorized": rl_fact,
        },
        "claim_limit": "Validation confirms only integrity and the explicitly bounded M5 diagnostic scope. Numerical mesh residual acceptance is not physical clearance/metrology authority. Owner Override is not MEMORY_GATE_PASS. Unknown physical quantities remain null/HOLD.",
    }
    write_receipt_atomic(receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": RECEIPT.relative_to(WORKSPACE).as_posix(),
                "receipt_sha256": sha256(RECEIPT),
                "check_count": receipt["check_count"],
                "pass_count": receipt["pass_count"],
                "fail_count": receipt["fail_count"],
                "failed_check_ids": receipt["failed_check_ids"],
                "formal_fea_run_count": formal_fea_count_fact,
                "formal_fea_verification_status": "VERIFIED_ZERO" if formal_fea_count_fact == 0 else "UNVERIFIED",
                "memory_gate_passed": memory_gate_fact,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
