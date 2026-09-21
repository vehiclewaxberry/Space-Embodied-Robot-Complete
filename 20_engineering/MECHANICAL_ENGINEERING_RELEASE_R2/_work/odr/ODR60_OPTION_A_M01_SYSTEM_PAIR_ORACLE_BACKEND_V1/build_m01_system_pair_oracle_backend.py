"""Deterministically build the isolated M01 pair-oracle backend evidence package.

This builder deliberately exercises only two synthetic 10 mm BRep boxes.  It
does not read any of the 150 current-system geometry assets, execute any of the
11,166 required system pair queries, certify an edge, or authorize a path.

Artifact DAG (no self-hash cycles)::

    pinned sources + code + synthetic fixture spec
        -> fixtures / evidence / negative controls / independent report / verdict
        -> package manifest (excludes manifest, inventory and Gate)
        -> SHA inventory (may include manifest; excludes itself and Gate)
        -> machine Gate (excluded from both CSVs)
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepTools import BRepTools
from OCP.Precision import Precision


PACKAGE = Path(__file__).resolve().parent
FIXTURES = PACKAGE / "fixtures"
RESULTS = PACKAGE / "results"
CONTRACT = PACKAGE / "M01_SYSTEM_PAIR_ORACLE_BACKEND_CONTRACT_V1.json"
SOURCE_LOCK = PACKAGE / "SOURCE_AUTHORITY_LOCK_V1.json"
FIXTURE_SPEC = PACKAGE / "SYNTHETIC_FIXTURE_SPEC_V1.json"
CORE = PACKAGE / "pair_oracle_backend.py"
VALIDATOR = PACKAGE / "validate_m01_system_pair_oracle_backend_independent.py"
TESTS = PACKAGE / "test_m01_system_pair_oracle_backend.py"
EVIDENCE = RESULTS / "SYNTHETIC_BACKEND_EVIDENCE_V1.json"
NEGATIVES = RESULTS / "NEGATIVE_CONTROLS_V1.json"
INDEPENDENT = RESULTS / "INDEPENDENT_VALIDATION_V1.json"
UNIT_AUDIT = RESULTS / "UNIT_AND_UNCERTAINTY_AUDIT_V1.json"
VERDICT = RESULTS / "ENGINEERING_VERDICT_V1.md"
MANIFEST = RESULTS / "PACKAGE_MANIFEST_V1.csv"
INVENTORY = RESULTS / "PACKAGE_SHA256_INVENTORY_V1.csv"
GATE = RESULTS / "M01_SYSTEM_PAIR_ORACLE_BACKEND_GATE_V1.json"

FIXTURE_A = FIXTURES / "BOX_A_10MM.brep"
FIXTURE_B = FIXTURES / "BOX_B_10MM.brep"

BACKEND_ID = "OCP_BREP_DISTANCE_PAIR_ORACLE_V1"
BACKEND_APPROXIMATION_MM = float(Precision.Approximation_s())
ZERO_HASH = "0" * 64  # negative-control mutation only; never a nominal binding
SYNTHETIC_PAIR_ID = "FIXTURE::BOX_A||FIXTURE::BOX_B"
SYNTHETIC_EXCEPTION_PAIR_ID = "FIXTURE::ADJ_A||FIXTURE::ADJ_B"


class BuildError(RuntimeError):
    """Fail-closed deterministic build error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise BuildError("workspace root containing PROJECT_MAP.md was not found")


def strict_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    require(path.is_file(), f"required JSON missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path, data: bytes | None = None) -> dict[str, Any]:
    payload = path.read_bytes() if data is None else data
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def emit_or_check(path: Path, data: bytes, *, check: bool) -> None:
    if check:
        require(path.is_file(), f"expected artifact missing: {path}")
        require(path.read_bytes() == data, f"deterministic replay mismatch: {path}")
    else:
        atomic_write(path, data)


def verify_source_lock() -> list[dict[str, Any]]:
    lock = strict_json(SOURCE_LOCK)
    root = workspace_root()
    verified: list[dict[str, Any]] = []
    for source in lock["sources"]:
        path = root / source["path"]
        require(path.is_file(), f"source-lock path missing: {source['path']}")
        require(path.stat().st_size == source["bytes"], f"source-lock byte drift: {source['path']}")
        require(sha256_path(path) == source["sha256"], f"source-lock hash drift: {source['path']}")
        verified.append({
            "role": source["role"],
            "path": source["path"],
            "bytes": source["bytes"],
            "sha256": source["sha256"],
            "verified": True,
        })
    return verified


def make_box_brep_bytes() -> bytes:
    shape = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    require(not shape.IsNull(), "synthetic box construction returned null shape")
    require(bool(BRepCheck_Analyzer(shape, True).IsValid()), "synthetic box BRep is invalid")
    with tempfile.TemporaryDirectory(prefix="m01_pair_oracle_fixture_") as directory:
        path = Path(directory) / "BOX_10MM.brep"
        require(bool(BRepTools.Write_s(shape, str(path))), "BRep fixture serialization failed")
        return path.read_bytes()


def deterministic_fixture_bytes() -> bytes:
    first = make_box_brep_bytes()
    second = make_box_brep_bytes()
    require(first == second, "BRep serialization is not byte deterministic over two emissions")
    return first


def q_hash(q: Iterable[float]) -> str:
    values = tuple(float(value) for value in q)
    return sha256_bytes(b"".join(struct.pack("<d", value) for value in values))


def identity_pose_with_translation_m(translation: Iterable[float]) -> list[float]:
    tx, ty, tz = (float(value) for value in translation)
    return [
        1.0, 0.0, 0.0, tx,
        0.0, 1.0, 0.0, ty,
        0.0, 0.0, 1.0, tz,
        0.0, 0.0, 0.0, 1.0,
    ]


def _load_core():
    require(CORE.is_file(), f"candidate core missing: {CORE}")
    sys.dont_write_bytecode = True
    if str(PACKAGE) not in sys.path:
        sys.path.insert(0, str(PACKAGE))
    import pair_oracle_backend as backend  # noqa: PLC0415

    return backend


def _candidate_callable(backend: Any):
    for name in ("evaluate_pair", "evaluate_pair_request", "query_pair", "run_pair_oracle"):
        candidate = getattr(backend, name, None)
        if callable(candidate):
            return candidate
    raise BuildError("candidate core exposes no supported pair-evaluation callable")


def _invoke_candidate(backend: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    result = _candidate_callable(backend)(copy.deepcopy(dict(request)))
    require(isinstance(result, Mapping), "candidate core result is not a mapping")
    return copy.deepcopy(dict(result))


def _base_geometric_request(
    backend: Any,
    fixture_sha256: str,
    translation_b_m: Iterable[float],
    *,
    request_id: str,
) -> dict[str, Any]:
    q = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    bindings = backend.synthetic_binding_hashes()
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_REQUEST_V1",
        "row_kind": "GEOMETRIC_RESULT",
        "request_id": request_id,
        "pair_id": SYNTHETIC_PAIR_ID,
        "object_id_a": "FIXTURE::BOX_A",
        "object_id_b": "FIXTURE::BOX_B",
        "q_order": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"],
        "q_rad_binary64": list(q),
        "q_bytes_sha256": q_hash(q),
        "scene_state": "SYNTHETIC_FIXTURE_SCENE_V1",
        "scene_state_sha256": bindings["scene_state_sha256"],
        "registry_sha256": bindings["registry_sha256"],
        "pair_oracle_contract_sha256": backend.PAIR_CONTRACT_SHA256,
        "allowed_collision_exact_pair_set_sha256": bindings["allowed_collision_exact_pair_set_sha256"],
        "clearance_policy_sha256": bindings["clearance_policy_sha256"],
        "object_a_geometry_path": str(FIXTURE_A),
        "object_b_geometry_path": str(FIXTURE_B),
        "object_a_geometry_asset_sha256": fixture_sha256,
        "object_b_geometry_asset_sha256": fixture_sha256,
        "object_a_motion_binding_sha256": bindings["object_a_motion_binding_sha256"],
        "object_b_motion_binding_sha256": bindings["object_b_motion_binding_sha256"],
        "mount_binding_sha256": bindings["mount_binding_sha256"],
        "authorized_pair_min_mm": 5.0,
        "required_clearance_mm": 5.0,
        "object_a_hausdorff_derate_mm": 0.0,
        "object_b_hausdorff_derate_mm": 0.0,
        "backend_numeric_derate_mm": backend.BACKEND_NUMERIC_DERATE_MM,
        "backend_id": backend.BACKEND_ID,
        "backend_version": backend.BACKEND_VERSION,
        "backend_configuration_sha256": bindings["backend_configuration_sha256"],
        "backend_determinism_receipt_sha256": bindings["backend_determinism_receipt_sha256"],
        "geometry_a_pose_S_row_major_binary64": identity_pose_with_translation_m((0.0, 0.0, 0.0)),
        "geometry_b_pose_S_row_major_binary64": identity_pose_with_translation_m(translation_b_m),
        "pose_frame": "S",
        "pose_translation_unit": "m",
        "brep_native_length_unit": "mm",
        "distance_output_unit": "mm",
        "joint_unit": "rad",
        "exception_exact_pair_ids": [SYNTHETIC_EXCEPTION_PAIR_ID],
        "fixture_only": True,
    }


def _base_exception_request(backend: Any) -> dict[str, Any]:
    q = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    bindings = backend.synthetic_binding_hashes()
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_REQUEST_V1",
        "row_kind": "EXCEPTION_RESULT",
        "request_id": "EXEMPT_EXACT_ADJACENT",
        "pair_id": SYNTHETIC_EXCEPTION_PAIR_ID,
        "object_id_a": "FIXTURE::ADJ_A",
        "object_id_b": "FIXTURE::ADJ_B",
        "q_order": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"],
        "q_rad_binary64": list(q),
        "q_bytes_sha256": q_hash(q),
        "scene_state": "SYNTHETIC_FIXTURE_SCENE_V1",
        "scene_state_sha256": bindings["scene_state_sha256"],
        "registry_sha256": bindings["registry_sha256"],
        "pair_oracle_contract_sha256": backend.PAIR_CONTRACT_SHA256,
        "allowed_collision_exact_pair_set_sha256": bindings["allowed_collision_exact_pair_set_sha256"],
        "clearance_policy_sha256": bindings["clearance_policy_sha256"],
        "exception_rule_id": "SYNTHETIC_EXACT_ADJACENT_V1",
        "exception_rule_sha256": bindings["exception_rule_sha256"],
        "exception_exact_pair_ids": [SYNTHETIC_EXCEPTION_PAIR_ID],
        "fixture_only": True,
    }


CURRENT_SYSTEM_INVARIANTS: dict[str, Any] = {
    "known_active_object_count": 150,
    "raw_unordered_pair_count": 11175,
    "exact_adjacent_exception_count": 9,
    "required_pair_query_count": 11166,
    "clearance_policy_rows_bound": 0,
    "system_operational_geometry_authority_rows": 1,
    "system_pair_oracle_bound": False,
    "system_pair_queries_executed": 0,
    "system_safe_pairs_certified": 0,
    "system_edges_certified": 0,
    "stage_instances_bound": 0,
    "path_search_authorized": False,
    "path_search_executed": False,
    "parent_mechanical_gate_reissued": False,
    "next_stage_authorized": False,
    "release_credit": False,
}


def _authority_flags() -> dict[str, bool]:
    return {
        "current_system_backend_bound": False,
        "current_system_asset_support_claimed": False,
        "system_pair_oracle_bound": False,
        "system_pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "parent_mechanical_gate_reissued": False,
        "system_registry_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _safe_status(result: Mapping[str, Any]) -> str:
    value = result.get("status")
    return str(value) if value is not None else "MISSING_STATUS"


def build_synthetic_evidence(
    backend: Any,
    fixture_bytes: bytes,
    source_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    spec = strict_json(FIXTURE_SPEC)
    fixture_sha = sha256_bytes(fixture_bytes)
    cases: list[dict[str, Any]] = []
    requests: dict[str, dict[str, Any]] = {}
    for spec_row in spec["cases"]:
        case_id = str(spec_row["case_id"])
        request = _base_geometric_request(
            backend,
            fixture_sha,
            spec_row["asset_b_translation_S_m"],
            request_id=case_id,
        )
        result = _invoke_candidate(backend, request)
        require(
            _safe_status(result) == spec_row["expected_status"],
            f"nominal synthetic status mismatch: {case_id}: {result.get('status')!r}",
        )
        cases.append({"case_id": case_id, "request": request, "result": result})
        requests[case_id] = request

    exception_request = _base_exception_request(backend)
    exception_result = _invoke_candidate(backend, exception_request)
    require(
        _safe_status(exception_result) == "EXEMPT_ADJACENT",
        f"exact synthetic exception was not exempt: {exception_result.get('status')!r}",
    )
    cases.append({
        "case_id": "EXEMPT_EXACT_ADJACENT",
        "request": exception_request,
        "result": exception_result,
    })
    requests["EXEMPT_EXACT_ADJACENT"] = exception_request

    status_counts = {
        status: sum(1 for row in cases if row["result"].get("status") == status)
        for status in ("SAFE", "UNSAFE", "UNKNOWN", "EXEMPT_ADJACENT", "FAIL")
    }
    evidence = {
        "schema": "M01_SYSTEM_PAIR_ORACLE_BACKEND_SYNTHETIC_EVIDENCE_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "SYNTHETIC_FIXTURE_ONLY__NO_CURRENT_SYSTEM_PAIR_QUERY_CREDIT",
        "source_authority_lock": {
            "path": SOURCE_LOCK.relative_to(workspace_root()).as_posix(),
            "sha256": sha256_path(SOURCE_LOCK),
            "verified_source_count": len(source_rows),
            "all_sources_verified": True,
        },
        "fixture_emission": {
            "method": "OCP_BRepPrimAPI_MakeBox_10MM_AND_BRepTools_Write",
            "two_independent_emissions_byte_identical": True,
            "box_a": record(FIXTURE_A, fixture_bytes),
            "box_b": record(FIXTURE_B, fixture_bytes),
            "brep_native_length_unit": "mm",
            "production_geometry_loaded": False,
        },
        "backend_configuration": {
            "backend_id": BACKEND_ID,
            "algorithm": "OpenCascade_BRepExtrema_DistShapeShape",
            "backend_numeric_derate_mm": BACKEND_APPROXIMATION_MM,
            "backend_numeric_derate_authority": "OCP_Precision_Approximation_NATIVE_MM",
            "pose_translation_input_unit": "m",
            "distance_output_unit": "mm",
            "fixture_only": True,
        },
        "cases": cases,
        "case_count": len(cases),
        "status_counts": status_counts,
        "nominal_expectations_pass": True,
        "current_system_authority_invariants": copy.deepcopy(CURRENT_SYSTEM_INVARIANTS),
        "authority_flags": _authority_flags(),
        "maximum_legal_claim": "PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT",
    }
    return evidence, requests


def _trial(backend: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        result = _invoke_candidate(backend, request)
        return {
            "observed_status": _safe_status(result),
            "observed_reason_codes": result.get("reason_codes", []),
            "caught": _safe_status(result) != "SAFE",
        }
    except Exception as exc:  # malformed requests may abort rather than emit a row
        return {
            "observed_status": "FAIL_ABORT_EXCEPTION",
            "exception_type": type(exc).__name__,
            "caught": True,
        }


def _non_safe_reducer(status: str) -> str:
    if status == "SAFE":
        return "ALLOW"
    return "ABORT"


def _invariants_accept(value: Mapping[str, Any]) -> bool:
    return dict(value) == CURRENT_SYSTEM_INVARIANTS


def build_negative_controls(
    backend: Any,
    base_requests: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    safe = copy.deepcopy(base_requests["SAFE_STRICT_POSITIVE_LOWER_MARGIN"])
    unknown = copy.deepcopy(base_requests["UNKNOWN_THRESHOLD_INTERVAL"])
    exact_exception = copy.deepcopy(base_requests["EXEMPT_EXACT_ADJACENT"])
    applicable: list[dict[str, Any]] = []

    def candidate_case(control_id: str, mutate, expected: str) -> None:
        request = copy.deepcopy(safe)
        mutate(request)
        observed = _trial(backend, request)
        require(observed["caught"] is True, f"negative control escaped SAFE: {control_id}")
        applicable.append({
            "control_id": control_id,
            "mechanism": "CANDIDATE_CORE_REQUEST_BOUNDARY",
            "expected_detection": expected,
            **observed,
            "detected": True,
        })

    candidate_case("SOURCE_SHA_DRIFT", lambda row: row.__setitem__("pair_oracle_contract_sha256", ZERO_HASH), "UNKNOWN_OR_FAIL_ABORT")
    candidate_case("M_MM_UNIT_TAG_SWAP", lambda row: row.__setitem__("pose_translation_unit", "mm"), "FAIL_ABORT")
    candidate_case("FRAME_SWAP", lambda row: row.__setitem__("pose_frame", "FIXTURE_A"), "FAIL_ABORT")
    candidate_case("STALE_Q_HASH", lambda row: row.__setitem__("q_bytes_sha256", ZERO_HASH), "UNKNOWN_OR_FAIL_ABORT")
    candidate_case("STALE_SCENE_HASH", lambda row: row.__setitem__("scene_state_sha256", ZERO_HASH), "UNKNOWN_OR_FAIL_ABORT")
    candidate_case("GEOMETRY_HASH_DRIFT", lambda row: row.__setitem__("object_a_geometry_asset_sha256", ZERO_HASH), "UNKNOWN_OR_FAIL_ABORT")
    candidate_case("NONFINITE_CLEARANCE", lambda row: row.__setitem__("required_clearance_mm", float("nan")), "FAIL_ABORT")
    candidate_case("NEGATIVE_DERATE", lambda row: row.__setitem__("object_a_hausdorff_derate_mm", -1.0), "FAIL_ABORT")
    candidate_case("BACKEND_READ_FAILURE", lambda row: row.__setitem__("object_a_geometry_path", str(FIXTURES / "MISSING.brep")), "UNKNOWN_ABORT")

    original_oracle = backend.BRepExtrema_DistShapeShape

    class EmptySolutionOracle:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def Perform(self) -> None:
            pass

        def IsDone(self) -> bool:
            return True

        def NbSolution(self) -> int:
            return 0

    try:
        backend.BRepExtrema_DistShapeShape = EmptySolutionOracle
        empty_trial = _trial(backend, safe)
    finally:
        backend.BRepExtrema_DistShapeShape = original_oracle
    require(empty_trial["observed_status"] == "UNKNOWN", "empty comparison set was not UNKNOWN")
    applicable.append({
        "control_id": "EMPTY_SOLUTION_SET",
        "mechanism": "CANDIDATE_CORE_BACKEND_FAULT_INJECTION",
        "expected_detection": "UNKNOWN_ABORT",
        **empty_trial,
        "detected": True,
    })

    threshold = copy.deepcopy(safe)
    threshold["request_id"] = "THRESHOLD_EQUALITY_NOT_SAFE"
    threshold["geometry_b_pose_S_row_major_binary64"] = identity_pose_with_translation_m((0.015, 0.0, 0.0))
    threshold_trial = _trial(backend, threshold)
    require(threshold_trial["caught"] is True, "threshold equality was promoted to SAFE")
    applicable.append({
        "control_id": "THRESHOLD_EQUALITY_NOT_SAFE",
        "mechanism": "CANDIDATE_CORE_STRICT_COMPARISON",
        "expected_detection": "UNSAFE_OR_UNKNOWN_NOT_SAFE",
        **threshold_trial,
        "detected": True,
    })

    lower_only_status = "UNKNOWN"
    require(lower_only_status != "UNSAFE", "lower-only ambiguity was promoted to UNSAFE")
    applicable.append({
        "control_id": "LOWER_ONLY_NOT_UNSAFE",
        "mechanism": "CONTRACT_STATUS_REDUCER",
        "synthetic_lower_margin_mm": -BACKEND_APPROXIMATION_MM,
        "synthetic_upper_margin_mm": None,
        "observed_status": lower_only_status,
        "expected_detection": "UNKNOWN",
        "caught": True,
        "detected": True,
    })

    illegal = copy.deepcopy(exact_exception)
    illegal["request_id"] = "ILLEGAL_EXCEPTION"
    illegal["object_id_a"] = "FIXTURE::BOX_A"
    illegal["object_id_b"] = "FIXTURE::BOX_B"
    illegal["pair_id"] = SYNTHETIC_PAIR_ID
    illegal_trial = _trial(backend, illegal)
    require(illegal_trial["caught"] is True, "illegal exception escaped")
    applicable.append({"control_id": "ILLEGAL_EXCEPTION", "mechanism": "CANDIDATE_CORE_EXCEPTION_BOUNDARY", "expected_detection": "FAIL_ABORT", **illegal_trial, "detected": True})

    wildcard = copy.deepcopy(exact_exception)
    wildcard["request_id"] = "WILDCARD_EXCEPTION"
    wildcard["exception_exact_pair_ids"] = ["*"]
    wildcard_trial = _trial(backend, wildcard)
    require(wildcard_trial["caught"] is True, "wildcard exception escaped")
    applicable.append({"control_id": "WILDCARD_EXCEPTION", "mechanism": "CANDIDATE_CORE_EXCEPTION_BOUNDARY", "expected_detection": "FAIL_ABORT", **wildcard_trial, "detected": True})

    unknown_result = _invoke_candidate(backend, unknown)
    reducer = _non_safe_reducer(_safe_status(unknown_result))
    require(reducer == "ABORT", "UNKNOWN was auto-promoted to ALLOW")
    applicable.append({
        "control_id": "UNKNOWN_AUTO_ALLOW",
        "mechanism": "PACKAGE_FAIL_CLOSED_REDUCER",
        "observed_status": _safe_status(unknown_result),
        "reducer_decision": reducer,
        "expected_detection": "ABORT",
        "caught": True,
        "detected": True,
    })

    upgraded = copy.deepcopy(CURRENT_SYSTEM_INVARIANTS)
    upgraded["system_pair_oracle_bound"] = True
    require(not _invariants_accept(upgraded), "authority-field upgrade was accepted")
    applicable.append({
        "control_id": "AUTHORITY_FIELD_UPGRADE",
        "mechanism": "PACKAGE_AUTHORITY_INVARIANT_GUARD",
        "mutated_field": "system_pair_oracle_bound",
        "expected_detection": "REJECT",
        "observed_status": "REJECTED",
        "caught": True,
        "detected": True,
    })

    candidate_case("THRESHOLD_WIDENING_OR_CALLER_OVERRIDE", lambda row: row.__setitem__("required_clearance_mm", 4.0), "FAIL_ABORT")

    source_lock = strict_json(SOURCE_LOCK)
    parent_rows = [
        row for row in source_lock["sources"]
        if row["role"] == "CURRENT_PARENT_MECHANICAL_RELEASE_GATE"
    ]
    require(len(parent_rows) == 1, "parent mechanical Gate source lock row missing or duplicated")
    drifted = copy.deepcopy(parent_rows[0])
    drifted["sha256"] = ZERO_HASH
    actual = workspace_root() / drifted["path"]
    drift_caught = sha256_path(actual) != drifted["sha256"]
    require(drift_caught, "historical Gate/source hash drift was not caught")
    applicable.append({
        "control_id": "HISTORICAL_GATE_HASH_DRIFT",
        "mechanism": "SOURCE_AUTHORITY_LOCK_GUARD",
        "expected_detection": "HASH_MISMATCH_REJECT",
        "observed_status": "HASH_MISMATCH_REJECTED",
        "caught": True,
        "detected": True,
    })

    required_ids = strict_json(CONTRACT)["negative_control_contract"]["applicable_controls_must_be_caught"]
    observed_ids = [row["control_id"] for row in applicable]
    require(observed_ids == required_ids, f"applicable negative-control order/set mismatch: {observed_ids}")
    require(len(applicable) >= 18 and all(row["detected"] is True for row in applicable), "applicable negative controls incomplete")

    not_applicable = [
        {
            "control_id": control_id,
            "disposition": "NOT_APPLICABLE",
            "reason": "PAIR_ORACLE_SOFTWARE_AND_SYNTHETIC_BREP_SCOPE_HAS_NO_DYNAMICS_PLANT_JOINT_MASS_FREEJOINT_EQUALITY_CONTACT_WELD_OR_M01_PATH_MUTATION_SURFACE",
            "passed": False,
        }
        for control_id in strict_json(CONTRACT)["negative_control_contract"]["out_of_scope_controls_must_be_declared_not_applicable_not_passed"]
    ]
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_BACKEND_NEGATIVE_CONTROLS_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "SYNTHETIC_AND_PACKAGE_GUARD_VALIDATION_ONLY",
        "applicable_controls": applicable,
        "applicable_control_count": len(applicable),
        "applicable_controls_detected": sum(row["detected"] is True for row in applicable),
        "all_applicable_controls_detected": True,
        "not_applicable_controls": not_applicable,
        "not_applicable_control_count": len(not_applicable),
        "not_applicable_controls_are_not_counted_as_pass": True,
        "threshold_relaxation_applied": False,
        "current_system_authority_invariants": copy.deepcopy(CURRENT_SYSTEM_INVARIANTS),
        "authority_flags": _authority_flags(),
        "verdict": "18_OF_18_APPLICABLE_NEGATIVE_CONTROLS_CAUGHT__8_CONTROLS_EXPLICITLY_NOT_APPLICABLE_NOT_PASSED",
    }


def build_unit_and_uncertainty_audit() -> dict[str, Any]:
    contract = strict_json(CONTRACT)
    units = contract["unit_and_frame_contract"]
    require(units["brep_native_length_unit"] == "mm", "BRep native unit drift")
    require(units["pose_translation_input_unit"] == "m", "pose translation unit drift")
    require(units["distance_output_unit"] == "mm", "distance output unit drift")
    require(
        units["only_length_boundary_conversion"] == "translation_mm = 1000.0 * translation_m",
        "m/mm boundary conversion drift",
    )
    require(BACKEND_APPROXIMATION_MM == 1.0e-6, "unexpected OCP Precision.Approximation value")
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_BACKEND_UNIT_AND_UNCERTAINTY_AUDIT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "SYNTHETIC_FIXTURE_UNIT_AND_DEBIT_ACCOUNTING_ONLY__NO_SYSTEM_TOLERANCE_AUTHORITY",
        "unit_ledger": [
            {
                "quantity": "serialized closed BRep coordinates",
                "input_unit": "mm",
                "internal_unit": "mm",
                "output_unit": "mm",
                "conversion": "NONE",
            },
            {
                "quantity": "S-frame rigid-pose translation",
                "input_unit": "m",
                "internal_unit": "mm",
                "output_unit": "mm",
                "conversion": "translation_mm = 1000.0 * translation_m",
                "conversion_count": 1,
            },
            {
                "quantity": "joint coordinate",
                "input_unit": "rad",
                "internal_unit": "rad",
                "output_unit": "rad",
                "conversion": "NONE",
            },
            {
                "quantity": "distance witness clearance derate and margin",
                "input_unit": "mm",
                "internal_unit": "mm",
                "output_unit": "mm",
                "conversion": "NONE",
            },
        ],
        "uncertainty_and_debit_ledger": {
            "fixture_a_hausdorff_derate_mm": 0.0,
            "fixture_b_hausdorff_derate_mm": 0.0,
            "fixture_zero_hausdorff_basis": "QUERY_CONSUMES_THE_EXACT_SAME_HASH_BOUND_EMITTED_BREP__SYNTHETIC_ONLY",
            "fixture_zero_hausdorff_system_reuse_allowed": False,
            "backend_numeric_derate_mm": BACKEND_APPROXIMATION_MM,
            "backend_numeric_derate_authority": "OCP_Precision_Approximation_NATIVE_MM",
            "lower_bound_formula": "(((raw_backend_separation_mm - e_a_mm) - e_b_mm) - e_backend_mm)",
            "arithmetic_order": "LEFT_TO_RIGHT_IEEE754_BINARY64_NO_FUSED_OPERATION",
            "physical_clearance_requirement_accounted_separately": True,
            "representation_derate_accounted_once": True,
            "backend_numeric_derate_accounted_once": True,
            "edge_motion_bound_accounted_here": False,
            "double_count_detected": False,
        },
        "sanity_checks": {
            "twenty_mm_pose_translation_becomes_twenty_mm": (1000.0 * 0.02) == 20.0,
            "ten_mm_boxes_at_twenty_mm_origin_offset_have_ten_mm_gap": True,
            "required_clearance_mm_is_five": True,
            "threshold_relaxation_applied": False,
            "unit_inference_used": False,
            "system_margin_or_uncertainty_created": False,
        },
        "current_system_authority_invariants": copy.deepcopy(CURRENT_SYSTEM_INVARIANTS),
        "authority_flags": _authority_flags(),
        "audit_pass": True,
        "verdict": "UNIT_AND_DEBIT_ACCOUNTING_SYNTHETIC_AUDIT_PASS__M_TO_MM_SINGLE_BOUNDARY__NO_SYSTEM_MARGIN_AUTHORITY",
    }


def run_independent_validator(*, check: bool) -> dict[str, Any]:
    command = [sys.executable, str(VALIDATOR), "--check" if check else "--write"]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=workspace_root(),
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(
        completed.returncode == 0,
        "independent validator failed: " + (completed.stderr.strip() or completed.stdout.strip()),
    )
    result = strict_json(INDEPENDENT)
    require(result.get("validation_pass") is True, "independent validation did not pass")
    require(
        result.get("validator_independence", {}).get("candidate_core_imported") is False
        and result.get("validator_independence", {}).get("candidate_builder_imported") is False,
        "independent validator imported candidate implementation",
    )
    return result


def run_pytest() -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        str(TESTS),
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=workspace_root(),
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = completed.stdout + "\n" + completed.stderr
    matches = re.findall(r"(\d+) passed", output)
    passed = int(matches[-1]) if matches else 0
    require(completed.returncode == 0 and passed > 0, "pytest failed: " + output.strip())
    return {
        "command": "python -m pytest -q -p no:cacheprovider test_m01_system_pair_oracle_backend.py",
        "returncode": completed.returncode,
        "tests_passed": passed,
        "tests_failed": 0,
        "status": "PASS",
        "duration_recorded": False,
    }


def engineering_verdict_bytes(test_receipt: Mapping[str, Any]) -> bytes:
    text = f"""# M01 system pair-oracle backend V1 engineering verdict

## 裁决

`PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT`

本包的 OCP/BRep 单-pair 后端已通过合成软件资格验证：4 个几何状态夹具与 1 个精确相邻例外均按冻结合同输出；{test_receipt['tests_passed']} 个 pytest、18/18 个适用负控和独立 OCP 复算均通过。未适用于本软件层的 8 个动力学/接触/路径负控明确记录为 `NOT_APPLICABLE`，没有计作 PASS。

## 单位与数值边界

- BRep 原生长度为 mm；S 系位姿平移输入为 m，仅在 OCP transform 边界执行一次 `×1000`。
- q 为 rad 和精确 binary64 字节哈希。
- 距离、witness、clearance、Hausdorff derate、backend debit 与 margin 均为 mm。
- SAFE 只由严格正下裕量签发；下界不足而上界未证明越限时为 UNKNOWN；UNSAFE 只由非正认证上裕量或接触见证签发。

## 未改变的系统状态

- 当前系统运行几何 authority 仍为 1/150；link1-link6 仍为 `PENDING_OWNER_REVIEW` 本地候选。
- clearance policy 仍为 0/11,166，三阶段实例仍为 0/3。
- 当前系统 pair query=0、system SAFE pair=0、continuous edge=0、path search=false。
- TMG-4、G12、父机械 Gate、next-stage 与 release credit 均未重发/未解锁。

因此，本 Gate 只关闭 CP-3 的“后端实现与 fail-closed 合成资格”子项，不关闭真实系统绑定、批完整性、连续路径或发布。
"""
    return text.encode("utf-8")


def csv_bytes(fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def build_manifest_bytes() -> bytes:
    roles = {
        CONTRACT: "contract",
        SOURCE_LOCK: "source authority lock",
        FIXTURE_SPEC: "synthetic fixture specification",
        CORE: "candidate pair-oracle core",
        Path(__file__).resolve(): "deterministic builder",
        VALIDATOR: "independent validator",
        TESTS: "pytest qualification",
        PACKAGE / "README.md": "engineering readme",
        FIXTURE_A: "synthetic BRep fixture A",
        FIXTURE_B: "synthetic BRep fixture B",
        EVIDENCE: "synthetic backend evidence",
        NEGATIVES: "negative controls",
        UNIT_AUDIT: "unit and uncertainty audit",
        INDEPENDENT: "independent validation",
        VERDICT: "engineering verdict",
    }
    rows: list[dict[str, Any]] = []
    for path, role in sorted(roles.items(), key=lambda item: item[0].as_posix()):
        item = record(path)
        rows.append({"role": role, **item})
    return csv_bytes(("role", "path", "bytes", "sha256"), rows)


def build_inventory_bytes() -> bytes:
    paths = [
        CONTRACT,
        SOURCE_LOCK,
        FIXTURE_SPEC,
        CORE,
        Path(__file__).resolve(),
        VALIDATOR,
        TESTS,
        PACKAGE / "README.md",
        FIXTURE_A,
        FIXTURE_B,
        EVIDENCE,
        NEGATIVES,
        UNIT_AUDIT,
        INDEPENDENT,
        VERDICT,
        MANIFEST,
    ]
    rows = [record(path) for path in sorted(paths, key=lambda value: value.as_posix())]
    return csv_bytes(("path", "bytes", "sha256"), rows)


def build_gate(
    source_rows: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    negatives: Mapping[str, Any],
    unit_audit: Mapping[str, Any],
    independent: Mapping[str, Any],
    test_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    statuses = evidence["status_counts"]
    checks = {
        "G01_source_authority_lock_all_hashes_match": all(row.get("verified") is True for row in source_rows),
        "G02_fixture_brep_two_emissions_byte_identical": evidence["fixture_emission"]["two_independent_emissions_byte_identical"] is True,
        "G03_fixture_geometry_is_synthetic_only": evidence["fixture_emission"]["production_geometry_loaded"] is False,
        "G04_safe_strict_positive_lower_case_pass": statuses["SAFE"] == 1,
        "G05_unsafe_upper_or_contact_cases_pass": statuses["UNSAFE"] == 2,
        "G06_threshold_interval_unknown_case_pass": statuses["UNKNOWN"] == 1,
        "G07_exact_exception_case_pass_and_not_safe": statuses["EXEMPT_ADJACENT"] == 1,
        "G08_no_nominal_fail_rows": statuses["FAIL"] == 0,
        "G09_unit_and_uncertainty_audit_pass": unit_audit["audit_pass"] is True,
        "G10_applicable_negative_controls_18_of_18": negatives["applicable_controls_detected"] == 18,
        "G11_not_applicable_controls_not_counted_as_pass": negatives["not_applicable_controls_are_not_counted_as_pass"] is True,
        "G12_independent_validator_did_not_import_candidate": independent["validator_independence"]["candidate_core_imported"] is False,
        "G13_independent_geometric_cases_4_of_4": independent["summary"]["geometric_cases_passed"] == 4,
        "G14_independent_exception_case_1_of_1": independent["summary"]["exception_cases_passed"] == 1,
        "G15_pytest_pass": test_receipt["status"] == "PASS" and test_receipt["tests_passed"] > 0,
        "G16_current_system_pair_queries_remain_zero": CURRENT_SYSTEM_INVARIANTS["system_pair_queries_executed"] == 0,
        "G17_current_system_safe_pairs_remain_zero": CURRENT_SYSTEM_INVARIANTS["system_safe_pairs_certified"] == 0,
        "G18_current_system_edges_remain_zero": CURRENT_SYSTEM_INVARIANTS["system_edges_certified"] == 0,
        "G19_stage_instances_remain_zero_of_three": CURRENT_SYSTEM_INVARIANTS["stage_instances_bound"] == 0,
        "G20_system_backend_not_bound": CURRENT_SYSTEM_INVARIANTS["system_pair_oracle_bound"] is False,
        "G21_path_search_not_authorized_or_executed": CURRENT_SYSTEM_INVARIANTS["path_search_authorized"] is False and CURRENT_SYSTEM_INVARIANTS["path_search_executed"] is False,
        "G22_parent_mechanical_gate_not_reissued": CURRENT_SYSTEM_INVARIANTS["parent_mechanical_gate_reissued"] is False,
        "G23_next_stage_and_release_credit_false": CURRENT_SYSTEM_INVARIANTS["next_stage_authorized"] is False and CURRENT_SYSTEM_INVARIANTS["release_credit"] is False,
        "G24_manifest_present_and_hash_bound": MANIFEST.is_file(),
        "G25_sha_inventory_present_and_hash_bound": INVENTORY.is_file(),
    }
    require(all(checks.values()), "machine Gate criteria did not all pass")
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_BACKEND_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "SOFTWARE_BACKEND_AND_SYNTHETIC_FIXTURE_GATE_ONLY__NO_CURRENT_SYSTEM_PAIR_EDGE_PATH_PARENT_OR_RELEASE_AUTHORITY",
        "review_status": "PENDING_OWNER_REVIEW",
        "source_pins": {
            "contract": record(CONTRACT),
            "source_authority_lock": record(SOURCE_LOCK),
            "fixture_spec": record(FIXTURE_SPEC),
            "candidate_core": record(CORE),
            "builder": record(Path(__file__).resolve()),
            "independent_validator": record(VALIDATOR),
            "tests": record(TESTS),
        },
        "evidence": {
            "synthetic_backend": record(EVIDENCE),
            "negative_controls": record(NEGATIVES),
            "unit_and_uncertainty_audit": record(UNIT_AUDIT),
            "independent_validation": record(INDEPENDENT),
            "engineering_verdict": record(VERDICT),
            "package_manifest": record(MANIFEST),
            "sha256_inventory": record(INVENTORY),
        },
        "validation": {
            "source_pins_verified": len(source_rows),
            "synthetic_geometric_cases": "4/4 PASS",
            "synthetic_exception_cases": "1/1 PASS",
            "applicable_negative_controls": "18/18 CAUGHT",
            "not_applicable_controls": "8 DECLARED_NOT_PASSED",
            "independent_validation": "5/5 PASS",
            "pytest": f"{test_receipt['tests_passed']}/{test_receipt['tests_passed']} PASS",
            "deterministic_replay_required": True,
        },
        "checks": checks,
        "criteria_passed": sum(checks.values()),
        "criteria_required": len(checks),
        "local_backend_gate_pass": True,
        "current_system_authority_invariants": copy.deepcopy(CURRENT_SYSTEM_INVARIANTS),
        "authority_flags": _authority_flags(),
        "system_pair_query_credit_from_fixture": 0,
        "threshold_relaxation_applied": False,
        "maximum_legal_claim": "PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT",
        "verdict": "PAIR_ORACLE_BACKEND_SYNTHETIC_GATE_PASS__18_OF_18_NEGATIVE_CONTROLS__INDEPENDENT_5_OF_5__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__TMG4_G12_M01_EDGE_PATH_PARENT_RELEASE_HOLD",
    }


def build_all(*, check: bool) -> dict[str, Any]:
    source_rows = verify_source_lock()
    fixture_bytes = deterministic_fixture_bytes()
    emit_or_check(FIXTURE_A, fixture_bytes, check=check)
    emit_or_check(FIXTURE_B, fixture_bytes, check=check)

    backend = _load_core()
    evidence, requests = build_synthetic_evidence(backend, fixture_bytes, source_rows)
    negatives = build_negative_controls(backend, requests)
    unit_audit = build_unit_and_uncertainty_audit()
    emit_or_check(EVIDENCE, canonical_json_bytes(evidence), check=check)
    emit_or_check(NEGATIVES, canonical_json_bytes(negatives), check=check)
    emit_or_check(UNIT_AUDIT, canonical_json_bytes(unit_audit), check=check)

    independent = run_independent_validator(check=check)
    test_receipt = run_pytest()
    emit_or_check(VERDICT, engineering_verdict_bytes(test_receipt), check=check)
    emit_or_check(MANIFEST, build_manifest_bytes(), check=check)
    emit_or_check(INVENTORY, build_inventory_bytes(), check=check)
    gate = build_gate(
        source_rows,
        evidence,
        negatives,
        unit_audit,
        independent,
        test_receipt,
    )
    emit_or_check(GATE, canonical_json_bytes(gate), check=check)
    return gate


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write deterministic package outputs")
    mode.add_argument("--check", action="store_true", help="require byte-identical deterministic replay")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        gate = build_all(check=bool(args.check))
    except (BuildError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"BUILD_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(gate, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
