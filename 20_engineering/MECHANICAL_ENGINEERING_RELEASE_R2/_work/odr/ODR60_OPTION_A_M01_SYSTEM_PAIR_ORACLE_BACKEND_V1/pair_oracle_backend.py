"""Fail-closed, synthetic-only OCP BRep pair-oracle backend.

This module implements a *single-pair* realization of the frozen current M01
row semantics.  The admission boundary intentionally accepts only the two
``FIXTURE::`` BRep assets located in this package.  It therefore proves the
software and numeric semantics without loading any current 150-object asset or
creating system pair, edge, path, parent-Gate, or release credit.

Length units are explicit:

* serialized BRep coordinates: millimetres;
* S-frame pose translations at the API: metres;
* OCP transforms, distances, derates, witnesses and margins: millimetres.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any, Mapping, Sequence

from OCP import __version__ as OCP_VERSION
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepTools import BRepTools
from OCP.Precision import Precision
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape
from OCP.gp import gp_Trsf


PACKAGE = Path(__file__).resolve().parent
FIXTURE_ROOT = (PACKAGE / "fixtures").resolve()
PAIR_CONTRACT_SHA256 = "D8B9CEE66BBD1793732F08F8E52C070B91CC5A6FCAAE56820E09E3C13BC81417"
BACKEND_ID = "OCP_BREP_DISTANCE_PAIR_ORACLE_V1"
BACKEND_VERSION = str(OCP_VERSION)
BACKEND_NUMERIC_DERATE_MM = float(Precision.Approximation_s())
HEX64 = re.compile(r"^[0-9A-F]{64}$")
Q_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
RESULT_SCHEMA = "M01_SYSTEM_PAIR_ORACLE_RESULT_V1"

GEOMETRIC_FIELDS = {
    "backend_id",
    "backend_version",
    "backend_configuration_sha256",
    "backend_determinism_receipt_sha256",
    "geometry_a_pose_S_row_major_binary64",
    "geometry_b_pose_S_row_major_binary64",
    "raw_backend_separation_mm",
    "object_a_hausdorff_derate_mm",
    "object_b_hausdorff_derate_mm",
    "backend_numeric_derate_mm",
    "certified_separation_lower_bound_mm",
    "certified_separation_upper_bound_mm",
    "certified_upper_bound_evidence_sha256",
    "authorized_pair_min_mm",
    "required_clearance_mm",
    "certified_margin_lower_bound_mm",
    "certified_margin_upper_bound_mm",
    "intersection_or_contact_certified",
    "unsafe_witness_authority_sha256",
    "witness_point_a_S_mm",
    "witness_point_b_S_mm",
    "witness_feature_a",
    "witness_feature_b",
    "comparison_set_size",
    "finite",
    "complete",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON; NaN and infinity are forbidden."""
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def sha256_path(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def q_bytes_sha256(values: Sequence[float]) -> str:
    if len(values) != 6:
        raise ValueError("q must contain exactly six binary64 values")
    payload = b"".join(struct.pack("<d", float(value)) for value in values)
    return hashlib.sha256(payload).hexdigest().upper()


def canonical_pair_id(object_id_a: str, object_id_b: str) -> str:
    if not isinstance(object_id_a, str) or not isinstance(object_id_b, str):
        raise ValueError("object IDs must be strings")
    if not object_id_a or not object_id_b or object_id_a == object_id_b:
        raise ValueError("pair requires two distinct non-empty object IDs")
    first, second = sorted((object_id_a, object_id_b))
    return f"{first}||{second}"


def _synthetic_payloads() -> dict[str, Any]:
    exception_pairs = ["FIXTURE::ADJ_A||FIXTURE::ADJ_B"]
    return {
        "scene_state": "SYNTHETIC_FIXTURE_SCENE_V1",
        "registry": {
            "schema": "SYNTHETIC_PAIR_ORACLE_FIXTURE_REGISTRY_V1",
            "object_ids": [
                "FIXTURE::ADJ_A",
                "FIXTURE::ADJ_B",
                "FIXTURE::BOX_A",
                "FIXTURE::BOX_B",
            ],
        },
        "exception_set": {
            "schema": "SYNTHETIC_EXACT_ADJACENT_SET_V1",
            "pair_ids": exception_pairs,
            "wildcard": False,
        },
        "clearance_policy": {
            "schema": "SYNTHETIC_PAIR_CLEARANCE_POLICY_V1",
            "pair_id": "FIXTURE::BOX_A||FIXTURE::BOX_B",
            "authorized_pair_min_mm": 5.0,
            "required_clearance_mm": 5.0,
            "caller_override": False,
        },
        "motion_a": {"schema": "SYNTHETIC_FIXED_POSE_MOTION_V1", "object_id": "FIXTURE::BOX_A"},
        "motion_b": {"schema": "SYNTHETIC_FIXED_POSE_MOTION_V1", "object_id": "FIXTURE::BOX_B"},
        "mount": {"schema": "SYNTHETIC_IDENTITY_MOUNT_V1", "pose_frame": "S"},
        "backend_configuration": {
            "schema": "OCP_BREP_DISTANCE_PAIR_ORACLE_CONFIGURATION_V1",
            "backend_id": BACKEND_ID,
            "backend_version": BACKEND_VERSION,
            "brep_native_length_unit": "mm",
            "pose_translation_unit": "m",
            "distance_output_unit": "mm",
            "backend_numeric_derate_mm": BACKEND_NUMERIC_DERATE_MM,
            "fixture_only": True,
        },
        "backend_determinism": {
            "schema": "SYNTHETIC_BACKEND_DETERMINISM_BINDING_V1",
            "algorithm": "BRepExtrema_DistShapeShape",
            "ocp_version": BACKEND_VERSION,
        },
        "exception_rule": {
            "schema": "SYNTHETIC_EXACT_ADJACENT_RULE_V1",
            "rule_id": "SYNTHETIC_EXACT_ADJACENT_V1",
            "pair_ids": exception_pairs,
        },
    }


def synthetic_binding_hashes() -> dict[str, str]:
    """Return the only hashes accepted by the synthetic admission boundary."""
    payloads = _synthetic_payloads()
    return {
        "scene_state_sha256": canonical_sha256(payloads["scene_state"]),
        "registry_sha256": canonical_sha256(payloads["registry"]),
        "allowed_collision_exact_pair_set_sha256": canonical_sha256(payloads["exception_set"]),
        "clearance_policy_sha256": canonical_sha256(payloads["clearance_policy"]),
        "object_a_motion_binding_sha256": canonical_sha256(payloads["motion_a"]),
        "object_b_motion_binding_sha256": canonical_sha256(payloads["motion_b"]),
        "mount_binding_sha256": canonical_sha256(payloads["mount"]),
        "backend_configuration_sha256": canonical_sha256(payloads["backend_configuration"]),
        "backend_determinism_receipt_sha256": canonical_sha256(payloads["backend_determinism"]),
        "exception_rule_sha256": canonical_sha256(payloads["exception_rule"]),
    }


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _safe_echo(request: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = request.get(key, default)
    if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
        return value
    return default


def _common_result(request: Mapping[str, Any], status: str, reasons: Sequence[str]) -> dict[str, Any]:
    object_a = _safe_echo(request, "object_id_a", "UNBOUND::A")
    object_b = _safe_echo(request, "object_id_b", "UNBOUND::B")
    try:
        pair_id = canonical_pair_id(str(object_a), str(object_b))
        canonical_ids: list[str] | None = pair_id.split("||")
    except ValueError:
        pair_id = str(_safe_echo(request, "pair_id", "UNBOUND_PAIR"))
        canonical_ids = None

    binding_keys = (
        "pair_id",
        "q_bytes_sha256",
        "scene_state_sha256",
        "registry_sha256",
        "pair_oracle_contract_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
        "object_a_geometry_asset_sha256",
        "object_b_geometry_asset_sha256",
        "object_a_motion_binding_sha256",
        "object_b_motion_binding_sha256",
        "mount_binding_sha256",
        "backend_configuration_sha256",
        "geometry_a_pose_S_row_major_binary64",
        "geometry_b_pose_S_row_major_binary64",
    )
    binding = {key: _safe_echo(request, key) for key in binding_keys}
    try:
        input_hash = canonical_sha256(binding)
    except (TypeError, ValueError):
        input_hash = "0" * 64
    return {
        "schema": RESULT_SCHEMA,
        "row_kind": _safe_echo(request, "row_kind", "MALFORMED"),
        "request_id": _safe_echo(request, "request_id", "MALFORMED_REQUEST"),
        "pair_id": pair_id,
        "canonical_object_ids": canonical_ids,
        "q_bytes_sha256": _safe_echo(request, "q_bytes_sha256"),
        "scene_state_sha256": _safe_echo(request, "scene_state_sha256"),
        "input_binding_sha256": input_hash,
        "pair_oracle_contract_sha256": _safe_echo(request, "pair_oracle_contract_sha256"),
        "allowed_collision_exact_pair_set_sha256": _safe_echo(
            request, "allowed_collision_exact_pair_set_sha256"
        ),
        "clearance_policy_sha256": _safe_echo(request, "clearance_policy_sha256"),
        "status": status,
        "reason_codes": list(reasons),
    }


def _finish(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result)
    payload.pop("evidence_sha256", None)
    result["evidence_sha256"] = canonical_sha256(payload)
    return result


def _fail(request: Mapping[str, Any], *reasons: str) -> dict[str, Any]:
    return _finish(_common_result(request, "FAIL", reasons or ("MALFORMED_REQUEST",)))


def _empty_geometric_result(
    request: Mapping[str, Any], status: str, reasons: Sequence[str]
) -> dict[str, Any]:
    result = _common_result(request, status, reasons)
    result.update(
        {
            "backend_id": _safe_echo(request, "backend_id", BACKEND_ID),
            "backend_version": BACKEND_VERSION,
            "backend_configuration_sha256": _safe_echo(request, "backend_configuration_sha256"),
            "backend_determinism_receipt_sha256": _safe_echo(
                request, "backend_determinism_receipt_sha256"
            ),
            "geometry_a_pose_S_row_major_binary64": _safe_echo(
                request, "geometry_a_pose_S_row_major_binary64"
            ),
            "geometry_b_pose_S_row_major_binary64": _safe_echo(
                request, "geometry_b_pose_S_row_major_binary64"
            ),
            "raw_backend_separation_mm": None,
            "object_a_hausdorff_derate_mm": _safe_echo(
                request, "object_a_hausdorff_derate_mm"
            ),
            "object_b_hausdorff_derate_mm": _safe_echo(
                request, "object_b_hausdorff_derate_mm"
            ),
            "backend_numeric_derate_mm": _safe_echo(request, "backend_numeric_derate_mm"),
            "certified_separation_lower_bound_mm": None,
            "certified_separation_upper_bound_mm": None,
            "certified_upper_bound_evidence_sha256": None,
            "authorized_pair_min_mm": _safe_echo(request, "authorized_pair_min_mm"),
            "required_clearance_mm": _safe_echo(request, "required_clearance_mm"),
            "certified_margin_lower_bound_mm": None,
            "certified_margin_upper_bound_mm": None,
            "intersection_or_contact_certified": False,
            "unsafe_witness_authority_sha256": None,
            "witness_point_a_S_mm": None,
            "witness_point_b_S_mm": None,
            "witness_feature_a": None,
            "witness_feature_b": None,
            "comparison_set_size": None,
            "finite": False,
            "complete": False,
        }
    )
    return _finish(result)


def _validate_common(request: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return (malformed FAIL reasons, binding UNKNOWN reasons)."""
    malformed: list[str] = []
    unbound: list[str] = []
    required = (
        "schema",
        "row_kind",
        "request_id",
        "pair_id",
        "object_id_a",
        "object_id_b",
        "q_order",
        "q_rad_binary64",
        "q_bytes_sha256",
        "scene_state",
        "scene_state_sha256",
        "registry_sha256",
        "pair_oracle_contract_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
    )
    malformed.extend(f"MISSING_FIELD::{key}" for key in required if key not in request)
    if request.get("schema") != "M01_SYSTEM_PAIR_ORACLE_REQUEST_V1":
        malformed.append("REQUEST_SCHEMA_INVALID")
    if request.get("row_kind") not in {"GEOMETRIC_RESULT", "EXCEPTION_RESULT"}:
        malformed.append("ROW_KIND_INVALID")
    if request.get("q_order") != Q_ORDER:
        malformed.append("Q_ORDER_INVALID")
    q = request.get("q_rad_binary64")
    if not isinstance(q, list) or len(q) != 6 or not all(_finite_number(x) for x in q):
        malformed.append("Q_VECTOR_INVALID")
    else:
        try:
            expected_q_hash = q_bytes_sha256([float(x) for x in q])
        except (OverflowError, ValueError):
            malformed.append("Q_VECTOR_INVALID")
        else:
            if request.get("q_bytes_sha256") != expected_q_hash:
                unbound.append("Q_BYTES_SHA256_MISMATCH")

    try:
        expected_pair = canonical_pair_id(
            str(request.get("object_id_a", "")), str(request.get("object_id_b", ""))
        )
    except ValueError:
        malformed.append("OBJECT_OR_PAIR_ID_INVALID")
    else:
        if request.get("pair_id") != expected_pair:
            malformed.append("PAIR_ID_NOT_CANONICAL")

    for field in (
        "q_bytes_sha256",
        "scene_state_sha256",
        "registry_sha256",
        "pair_oracle_contract_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
    ):
        if not _hex64(request.get(field)):
            malformed.append(f"{field.upper()}_INVALID")

    bindings = synthetic_binding_hashes()
    expected = {
        "scene_state_sha256": bindings["scene_state_sha256"],
        "registry_sha256": bindings["registry_sha256"],
        "allowed_collision_exact_pair_set_sha256": bindings[
            "allowed_collision_exact_pair_set_sha256"
        ],
        "clearance_policy_sha256": bindings["clearance_policy_sha256"],
        "pair_oracle_contract_sha256": PAIR_CONTRACT_SHA256,
    }
    for field, value in expected.items():
        if _hex64(request.get(field)) and request.get(field) != value:
            unbound.append(f"{field.upper()}_MISMATCH")
    if request.get("scene_state") != _synthetic_payloads()["scene_state"]:
        unbound.append("SCENE_STATE_PAYLOAD_MISMATCH")
    if request.get("fixture_only") is not True:
        unbound.append("PRODUCTION_ADMISSION_NOT_BOUND")
    return sorted(set(malformed)), sorted(set(unbound))


def _validate_pose(pose: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(pose, list) or len(pose) != 16 or not all(_finite_number(x) for x in pose):
        return [f"{label}_POSE_INVALID"]
    values = [float(x) for x in pose]
    if any(abs(values[12 + index] - expected) > 1.0e-15 for index, expected in enumerate((0, 0, 0, 1))):
        errors.append(f"{label}_POSE_LAST_ROW_INVALID")
    rotation = [[values[4 * row + col] for col in range(3)] for row in range(3)]
    for row in range(3):
        for col in range(3):
            dot = sum(rotation[k][row] * rotation[k][col] for k in range(3))
            expected = 1.0 if row == col else 0.0
            if abs(dot - expected) > 1.0e-12:
                errors.append(f"{label}_POSE_ROTATION_NOT_ORTHONORMAL")
                break
    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )
    if abs(determinant - 1.0) > 1.0e-12:
        errors.append(f"{label}_POSE_DETERMINANT_INVALID")
    return sorted(set(errors))


def _pose_to_trsf(pose: Sequence[float]) -> gp_Trsf:
    values = [float(value) for value in pose]
    transform = gp_Trsf()
    # OCP shapes are millimetres; the only length conversion is m -> mm here.
    transform.SetValues(
        values[0], values[1], values[2], 1000.0 * values[3],
        values[4], values[5], values[6], 1000.0 * values[7],
        values[8], values[9], values[10], 1000.0 * values[11],
    )
    return transform


def _count_solids(shape: TopoDS_Shape) -> int:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _load_fixture_shape(path_value: Any, expected_sha256: str) -> tuple[TopoDS_Shape | None, str | None]:
    if not isinstance(path_value, str) or not path_value:
        return None, "GEOMETRY_PATH_MISSING"
    path = Path(path_value).resolve()
    try:
        path.relative_to(FIXTURE_ROOT)
    except ValueError:
        return None, "NON_FIXTURE_GEOMETRY_FORBIDDEN"
    if not path.is_file():
        return None, "GEOMETRY_FILE_MISSING"
    try:
        actual_sha = sha256_path(path)
    except OSError:
        return None, "GEOMETRY_HASH_READ_FAILURE"
    if actual_sha != expected_sha256:
        return None, "GEOMETRY_ASSET_SHA256_MISMATCH"
    shape = TopoDS_Shape()
    builder = BRep_Builder()
    try:
        loaded = BRepTools.Read_s(shape, str(path), builder)
    except Exception:
        return None, "BREP_BACKEND_READ_FAILURE"
    if not bool(loaded) or shape.IsNull():
        return None, "BREP_BACKEND_READ_FAILURE"
    try:
        valid = bool(BRepCheck_Analyzer(shape, True).IsValid())
    except Exception:
        return None, "BREP_VALIDATION_FAILURE"
    if not valid or _count_solids(shape) <= 0:
        return None, "EMPTY_OR_INVALID_CLOSED_SOLID_SET"
    return shape, None


def _support_name(value: Any) -> str:
    name = getattr(value, "name", None)
    return str(name if name is not None else value)


def _validate_geometric_request(request: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    malformed: list[str] = []
    unbound: list[str] = []
    required = (
        "object_a_geometry_path",
        "object_b_geometry_path",
        "object_a_geometry_asset_sha256",
        "object_b_geometry_asset_sha256",
        "object_a_motion_binding_sha256",
        "object_b_motion_binding_sha256",
        "mount_binding_sha256",
        "authorized_pair_min_mm",
        "required_clearance_mm",
        "object_a_hausdorff_derate_mm",
        "object_b_hausdorff_derate_mm",
        "backend_numeric_derate_mm",
        "backend_id",
        "backend_version",
        "backend_configuration_sha256",
        "backend_determinism_receipt_sha256",
        "geometry_a_pose_S_row_major_binary64",
        "geometry_b_pose_S_row_major_binary64",
        "pose_frame",
        "pose_translation_unit",
        "brep_native_length_unit",
        "distance_output_unit",
        "joint_unit",
    )
    malformed.extend(f"MISSING_FIELD::{key}" for key in required if key not in request)
    for field in (
        "object_a_geometry_asset_sha256",
        "object_b_geometry_asset_sha256",
        "object_a_motion_binding_sha256",
        "object_b_motion_binding_sha256",
        "mount_binding_sha256",
        "backend_configuration_sha256",
        "backend_determinism_receipt_sha256",
    ):
        if not _hex64(request.get(field)):
            malformed.append(f"{field.upper()}_INVALID")
    if request.get("pose_frame") != "S":
        malformed.append("POSE_FRAME_NOT_S")
    if request.get("pose_translation_unit") != "m":
        malformed.append("POSE_TRANSLATION_UNIT_NOT_M")
    if request.get("brep_native_length_unit") != "mm":
        malformed.append("BREP_NATIVE_UNIT_NOT_MM")
    if request.get("distance_output_unit") != "mm":
        malformed.append("DISTANCE_OUTPUT_UNIT_NOT_MM")
    if request.get("joint_unit") != "rad":
        malformed.append("JOINT_UNIT_NOT_RAD")
    malformed.extend(_validate_pose(request.get("geometry_a_pose_S_row_major_binary64"), "A"))
    malformed.extend(_validate_pose(request.get("geometry_b_pose_S_row_major_binary64"), "B"))

    authorized = request.get("authorized_pair_min_mm")
    required_clearance = request.get("required_clearance_mm")
    if not _finite_number(authorized) or float(authorized) < 0.0:
        malformed.append("AUTHORIZED_PAIR_MIN_INVALID")
    if not _finite_number(required_clearance) or float(required_clearance) < 0.0:
        malformed.append("REQUIRED_CLEARANCE_INVALID")
    if _finite_number(authorized) and _finite_number(required_clearance):
        if float(required_clearance) < float(authorized):
            malformed.append("REQUIRED_CLEARANCE_BELOW_AUTHORIZED_MIN")
        if float(authorized).hex() != float(5.0).hex() or float(required_clearance).hex() != float(5.0).hex():
            unbound.append("SYNTHETIC_CLEARANCE_POLICY_VALUE_MISMATCH")
    for field in (
        "object_a_hausdorff_derate_mm",
        "object_b_hausdorff_derate_mm",
        "backend_numeric_derate_mm",
    ):
        value = request.get(field)
        if not _finite_number(value) or float(value) < 0.0:
            malformed.append(f"{field.upper()}_INVALID")
    if _finite_number(request.get("object_a_hausdorff_derate_mm")) and float(
        request["object_a_hausdorff_derate_mm"]
    ).hex() != 0.0.hex():
        unbound.append("FIXTURE_A_HAUSDORFF_DERATE_MISMATCH")
    if _finite_number(request.get("object_b_hausdorff_derate_mm")) and float(
        request["object_b_hausdorff_derate_mm"]
    ).hex() != 0.0.hex():
        unbound.append("FIXTURE_B_HAUSDORFF_DERATE_MISMATCH")
    if _finite_number(request.get("backend_numeric_derate_mm")) and float(
        request["backend_numeric_derate_mm"]
    ).hex() != BACKEND_NUMERIC_DERATE_MM.hex():
        unbound.append("BACKEND_NUMERIC_DERATE_MISMATCH")

    bindings = synthetic_binding_hashes()
    expected = {
        "object_a_motion_binding_sha256": bindings["object_a_motion_binding_sha256"],
        "object_b_motion_binding_sha256": bindings["object_b_motion_binding_sha256"],
        "mount_binding_sha256": bindings["mount_binding_sha256"],
        "backend_configuration_sha256": bindings["backend_configuration_sha256"],
        "backend_determinism_receipt_sha256": bindings[
            "backend_determinism_receipt_sha256"
        ],
    }
    for field, value in expected.items():
        if _hex64(request.get(field)) and request.get(field) != value:
            unbound.append(f"{field.upper()}_MISMATCH")
    if request.get("backend_id") != BACKEND_ID:
        unbound.append("BACKEND_ID_MISMATCH")
    if request.get("backend_version") != BACKEND_VERSION:
        unbound.append("BACKEND_VERSION_MISMATCH")
    if request.get("object_id_a") != "FIXTURE::BOX_A" or request.get("object_id_b") != "FIXTURE::BOX_B":
        unbound.append("NON_FIXTURE_OBJECT_ID_FORBIDDEN")
    return sorted(set(malformed)), sorted(set(unbound))


def _evaluate_exception(request: Mapping[str, Any]) -> dict[str, Any]:
    malformed, unbound = _validate_common(request)
    for field in ("exception_rule_id", "exception_rule_sha256", "exception_exact_pair_ids"):
        if field not in request:
            malformed.append(f"MISSING_FIELD::{field}")
    if any(field in request for field in GEOMETRIC_FIELDS):
        malformed.append("GEOMETRIC_FIELD_FORBIDDEN_ON_EXCEPTION_ROW")
    pair_list = request.get("exception_exact_pair_ids")
    if not isinstance(pair_list, list) or not pair_list or not all(isinstance(x, str) for x in pair_list):
        malformed.append("EXCEPTION_EXACT_PAIR_SET_INVALID")
        pair_list = []
    if any("*" in pair for pair in pair_list):
        malformed.append("WILDCARD_EXCEPTION_FORBIDDEN")
    expected_pair_list = _synthetic_payloads()["exception_set"]["pair_ids"]
    if pair_list != expected_pair_list:
        malformed.append("EXCEPTION_EXACT_PAIR_SET_MISMATCH")
    if request.get("pair_id") not in pair_list:
        malformed.append("ILLEGAL_EXCEPTION_PAIR")
    bindings = synthetic_binding_hashes()
    if request.get("exception_rule_id") != "SYNTHETIC_EXACT_ADJACENT_V1":
        malformed.append("EXCEPTION_RULE_ID_INVALID")
    if request.get("exception_rule_sha256") != bindings["exception_rule_sha256"]:
        unbound.append("EXCEPTION_RULE_SHA256_MISMATCH")
    if malformed:
        return _fail(request, *sorted(set(malformed)))
    if unbound:
        return _finish(_common_result(request, "UNKNOWN", sorted(set(unbound))))
    result = _common_result(request, "EXEMPT_ADJACENT", ["EXACT_EXCEPTION_SET_MEMBERSHIP_CERTIFIED"])
    result.update(
        {
            "exception_rule_id": request["exception_rule_id"],
            "exception_rule_sha256": request["exception_rule_sha256"],
            "exception_pair_set_membership_proof_sha256": canonical_sha256(
                {
                    "pair_id": request["pair_id"],
                    "exact_pair_ids": pair_list,
                    "allowed_collision_exact_pair_set_sha256": request[
                        "allowed_collision_exact_pair_set_sha256"
                    ],
                }
            ),
        }
    )
    return _finish(result)


def _evaluate_geometric(request: Mapping[str, Any]) -> dict[str, Any]:
    malformed, unbound = _validate_common(request)
    malformed_geometric, unbound_geometric = _validate_geometric_request(request)
    malformed.extend(malformed_geometric)
    unbound.extend(unbound_geometric)
    exception_pairs = request.get("exception_exact_pair_ids")
    expected_exception_pairs = _synthetic_payloads()["exception_set"]["pair_ids"]
    if exception_pairs != expected_exception_pairs:
        malformed.append("EXCEPTION_EXACT_PAIR_SET_MISMATCH")
    if request.get("pair_id") in expected_exception_pairs:
        malformed.append("EXCEPTION_PAIR_CANNOT_USE_GEOMETRIC_ROW")
    if malformed:
        return _fail(request, *sorted(set(malformed)))
    if unbound:
        return _empty_geometric_result(request, "UNKNOWN", sorted(set(unbound)))

    expected_sha_a = str(request["object_a_geometry_asset_sha256"])
    expected_sha_b = str(request["object_b_geometry_asset_sha256"])
    shape_a, error_a = _load_fixture_shape(request["object_a_geometry_path"], expected_sha_a)
    shape_b, error_b = _load_fixture_shape(request["object_b_geometry_path"], expected_sha_b)
    errors = [reason for reason in (error_a, error_b) if reason is not None]
    if errors or shape_a is None or shape_b is None:
        return _empty_geometric_result(request, "UNKNOWN", sorted(set(errors or ["GEOMETRY_LOAD_FAILED"])))

    try:
        moved_a = BRepBuilderAPI_Transform(
            shape_a, _pose_to_trsf(request["geometry_a_pose_S_row_major_binary64"]), True
        ).Shape()
        moved_b = BRepBuilderAPI_Transform(
            shape_b, _pose_to_trsf(request["geometry_b_pose_S_row_major_binary64"]), True
        ).Shape()
        oracle = BRepExtrema_DistShapeShape(moved_a, moved_b)
        oracle.Perform()
        if not oracle.IsDone():
            return _empty_geometric_result(request, "UNKNOWN", ["BACKEND_NOT_DONE"])
        comparison_count = int(oracle.NbSolution())
        if comparison_count <= 0:
            return _empty_geometric_result(request, "UNKNOWN", ["EMPTY_COMPARISON_SET"])
        backend_value = float(oracle.Value())
        if not math.isfinite(backend_value) or backend_value < 0.0:
            return _empty_geometric_result(request, "UNKNOWN", ["NONFINITE_OR_NEGATIVE_BACKEND_VALUE"])
        solutions: list[tuple[tuple[float, float, float], tuple[float, float, float], str, str]] = []
        for index in range(1, comparison_count + 1):
            point_a = oracle.PointOnShape1(index)
            point_b = oracle.PointOnShape2(index)
            pa = (float(point_a.X()), float(point_a.Y()), float(point_a.Z()))
            pb = (float(point_b.X()), float(point_b.Y()), float(point_b.Z()))
            if not all(math.isfinite(value) for value in (*pa, *pb)):
                continue
            solutions.append(
                (pa, pb, _support_name(oracle.SupportTypeShape1(index)), _support_name(oracle.SupportTypeShape2(index)))
            )
        if not solutions:
            return _empty_geometric_result(request, "UNKNOWN", ["EMPTY_FINITE_WITNESS_SET"])
        pa, pb, feature_a, feature_b = min(solutions)
        witnessed_distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(pa, pb)))
        if not math.isfinite(witnessed_distance):
            return _empty_geometric_result(request, "UNKNOWN", ["NONFINITE_WITNESS_DISTANCE"])
        if abs(witnessed_distance - backend_value) > max(BACKEND_NUMERIC_DERATE_MM, 1.0e-12):
            return _empty_geometric_result(request, "UNKNOWN", ["BACKEND_WITNESS_DISTANCE_MISMATCH"])
        intersection = bool(oracle.InnerSolution()) or backend_value == 0.0
    except Exception:
        return _empty_geometric_result(request, "UNKNOWN", ["BACKEND_EXCEPTION"])

    raw = float(witnessed_distance)
    debit_a = float(request["object_a_hausdorff_derate_mm"])
    debit_b = float(request["object_b_hausdorff_derate_mm"])
    debit_backend = float(request["backend_numeric_derate_mm"])
    lower = ((raw - debit_a) - debit_b) - debit_backend
    upper = 0.0 if intersection else raw
    required_clearance = float(request["required_clearance_mm"])
    lower_margin = lower - required_clearance
    upper_margin = upper - required_clearance
    upper_evidence_payload = {
        "pair_id": request["pair_id"],
        "input_binding_sha256": _common_result(request, "UNKNOWN", [])["input_binding_sha256"],
        "backend_configuration_sha256": request["backend_configuration_sha256"],
        "witness_point_a_S_mm": list(pa),
        "witness_point_b_S_mm": list(pb),
        "witnessed_distance_mm": upper,
        "intersection_or_contact_certified": intersection,
    }
    upper_evidence = canonical_sha256(upper_evidence_payload)
    if lower_margin > 0.0:
        status = "SAFE"
        reasons = ["STRICT_POSITIVE_CERTIFIED_LOWER_MARGIN"]
    elif upper_margin <= 0.0:
        status = "UNSAFE"
        reasons = [
            "CERTIFIED_CONTACT_WITNESS" if intersection else "CERTIFIED_NONPOSITIVE_UPPER_MARGIN"
        ]
    else:
        status = "UNKNOWN"
        reasons = ["THRESHOLD_INTERVAL_AMBIGUITY__LOWER_NOT_POSITIVE_UPPER_NOT_NONPOSITIVE"]

    result = _common_result(request, status, reasons)
    result.update(
        {
            "backend_id": BACKEND_ID,
            "backend_version": BACKEND_VERSION,
            "backend_configuration_sha256": request["backend_configuration_sha256"],
            "backend_determinism_receipt_sha256": request[
                "backend_determinism_receipt_sha256"
            ],
            "geometry_a_pose_S_row_major_binary64": list(
                request["geometry_a_pose_S_row_major_binary64"]
            ),
            "geometry_b_pose_S_row_major_binary64": list(
                request["geometry_b_pose_S_row_major_binary64"]
            ),
            "raw_backend_separation_mm": raw,
            "object_a_hausdorff_derate_mm": debit_a,
            "object_b_hausdorff_derate_mm": debit_b,
            "backend_numeric_derate_mm": debit_backend,
            "certified_separation_lower_bound_mm": lower,
            "certified_separation_upper_bound_mm": upper,
            "certified_upper_bound_evidence_sha256": upper_evidence,
            "authorized_pair_min_mm": float(request["authorized_pair_min_mm"]),
            "required_clearance_mm": required_clearance,
            "certified_margin_lower_bound_mm": lower_margin,
            "certified_margin_upper_bound_mm": upper_margin,
            "intersection_or_contact_certified": intersection,
            "unsafe_witness_authority_sha256": upper_evidence if status == "UNSAFE" else None,
            "witness_point_a_S_mm": list(pa),
            "witness_point_b_S_mm": list(pb),
            "witness_feature_a": feature_a,
            "witness_feature_b": feature_b,
            "comparison_set_size": comparison_count,
            "finite": True,
            "complete": True,
        }
    )
    return _finish(result)


def evaluate_pair(request: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one hash-bound synthetic row without raising backend errors.

    The public function deliberately takes one mapping so deterministic builders
    cannot smuggle un-hashed geometry or authority objects through side channels.
    """
    if not isinstance(request, Mapping):
        return _fail({}, "REQUEST_NOT_MAPPING")
    row_kind = request.get("row_kind")
    if row_kind == "EXCEPTION_RESULT":
        return _evaluate_exception(request)
    if row_kind == "GEOMETRIC_RESULT":
        return _evaluate_geometric(request)
    return _fail(request, "ROW_KIND_INVALID")


__all__ = [
    "BACKEND_ID",
    "BACKEND_NUMERIC_DERATE_MM",
    "BACKEND_VERSION",
    "PAIR_CONTRACT_SHA256",
    "canonical_json_bytes",
    "canonical_pair_id",
    "canonical_sha256",
    "evaluate_pair",
    "q_bytes_sha256",
    "sha256_path",
    "synthetic_binding_hashes",
]
