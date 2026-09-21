from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCES = CONTRACTS / "PHASE_B4G_R2_SOURCE_BINDINGS_V1.json"
DESIGN = CONTRACTS / "PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json"
SCHEDULE = CONTRACTS / "PHASE_B4G_R2_BLOCKED_SCHEDULE_V1.json"
NUMERICAL = CONTRACTS / "PHASE_B4G_R2_NUMERICAL_ACCEPTANCE_V1.json"
GOVERNANCE = CONTRACTS / "PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json"
TEST_RESULT = RESULTS / "SIM13_V4B4G_R2_TEST_RESULT_V1.json"
SNAPSHOT = EVIDENCE / "SIM13_V4B4G_R2_CONTRACT_SNAPSHOT_V1.json"
VALIDATION = RESULTS / "SIM13_V4B4G_R2_VALIDATION_V1.json"
MANIFEST = EVIDENCE / "SIM13_V4B4G_R2_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"

LOCAL_SOURCES = (
    "README.md",
    "pytest.ini",
    "run_phase_b4g_r2_contract.py",
    "validate_phase_b4g_r2_contract.py",
    "independent_audit_phase_b4g_r2_contract.py",
    "contracts/PHASE_B4G_R2_SOURCE_BINDINGS_V1.json",
    "contracts/PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json",
    "contracts/PHASE_B4G_R2_BLOCKED_SCHEDULE_V1.json",
    "contracts/PHASE_B4G_R2_NUMERICAL_ACCEPTANCE_V1.json",
    "contracts/PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json",
    "tests/conftest.py",
    "tests/test_design_and_schedule.py",
    "tests/test_numerical_contract.py",
    "tests/test_governance_and_independence.py",
)

LANES = (
    ("RK4_H_MS_0P25", "rk4", 0.00025, "0P25"),
    ("RK4_H_MS_0P125", "rk4", 0.000125, "0P125"),
    ("RK4_H_MS_0P0625", "rk4", 0.0000625, "0P0625"),
    ("MIDPOINT_H_MS_0P25", "midpoint", 0.00025, "0P25"),
    ("MIDPOINT_H_MS_0P125", "midpoint", 0.000125, "0P125"),
    ("MIDPOINT_H_MS_0P0625", "midpoint", 0.0000625, "0P0625"),
)

EXPECTED_GROUP_FIELD_MAP = {
    "/schema": "constant B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
    "/donor_acquisition_certificate_sha256": "raw /event_provenance/acquisition_certificate_sha256",
    "/acquisition_time_s": "payload /acquisition/acquisition_time_s",
    "/service/base_position_inertial_m": "payload /event/service/base_position_inertial_m",
    "/service/base_quaternion_body_to_inertial_wxyz": "payload /event/service/base_quaternion_body_to_inertial_wxyz",
    "/service/joint_coordinates_mixed": "payload /event/service/joint_coordinates_mixed",
    "/service/post_acquisition_eta_mixed": "payload /acquisition/z_plus_reduced[0:14]",
    "/target/position_inertial_m": "payload /event/target/position_inertial_m",
    "/target/quaternion_body_to_inertial_wxyz": "payload /event/target/quaternion_body_to_inertial_wxyz",
    "/target/post_acquisition_twist_inertial_mixed": "payload /acquisition/z_plus_reduced[14:20]",
}

EXPECTED_COMMON_CHANNELS = {
    "service_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_quaternion_body_to_inertial_wxyz": {"metric": "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1", "floor": 1e-12, "unit": "rad"},
    "R_joint_coordinates_rad": {"metric": "Linf", "floor": 1e-12, "unit": "rad"},
    "P_joint_coordinates_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_base_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "service_base_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "R_joint_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "P_joint_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "target_quaternion_body_to_inertial_wxyz": {"metric": "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1", "floor": 1e-12, "unit": "rad"},
    "target_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "total_linear_momentum_kg_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m/s"},
    "total_angular_momentum_kg_m2_s": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m^2/s"},
    "total_kinetic_energy_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
    "energy_minus_work_residual_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
}

EXPECTED_G04_FIELDS = [
    "W_act_initial_J", "sample_power_recomputed_W", "sample_power_reported_W", "sample_power_max_abs_error_W",
    "stage_power_recomputed_W", "stage_power_reported_W", "stage_power_max_abs_error_W", "cumulative_trapezoid_work_J",
    "cumulative_max_abs_error_J", "terminal_native_abs_error_J", "terminal_every_second_abs_error_J", "finite_removal_present",
    "active_terminal_W_act_J", "post_W_act_J", "post_actuator_work_reset_on_removal", "post_generalized_force_Q_14",
    "all_terms_finite", "scientific_predicate",
]


class ContractError(RuntimeError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise ContractError(f"non-object JSON: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def contains_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(contains_none(key) or contains_none(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_none(item) for item in value)
    return False


def evaluate_direct_order_triplet(
    errors_J: Any,
    *,
    floor_J: float,
    p_min: float,
    floor_scope: str,
) -> dict[str, Any]:
    invalid_order = "NOT_EVALUATED_INVALID_INPUT"
    def finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    if (
        not isinstance(errors_J, (list, tuple))
        or len(errors_J) != 3
        or not finite_number(floor_J)
        or floor_J <= 0.0
        or not finite_number(p_min)
        or p_min < 0.0
        or floor_scope not in {"FINE_AND_REFERENCE", "ALL_THREE"}
        or any(not finite_number(value) or value < 0.0 for value in errors_J)
    ):
        return {
            "passed": False,
            "category": "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA",
            "CF": {"passed": False, "order_status": invalid_order, "order_value": invalid_order},
            "FR": {"passed": False, "order_status": invalid_order, "order_value": invalid_order},
        }
    coarse, fine, reference = (float(value) for value in errors_J)
    relevant = (fine, reference) if floor_scope == "FINE_AND_REFERENCE" else (coarse, fine, reference)
    if all(value <= floor_J for value in relevant):
        sentinel = "NOT_EVALUATED_OVERALL_FLOOR_RESOLVED"
        return {
            "passed": True,
            "category": "OVERALL_FLOOR_RESOLVED",
            "CF": {"passed": True, "order_status": sentinel, "order_value": sentinel},
            "FR": {"passed": True, "order_status": sentinel, "order_value": sentinel},
        }

    def pair(left: float, right: float) -> dict[str, Any]:
        if left <= floor_J and right <= floor_J:
            status = "NOT_EVALUATED_PAIR_FLOOR_RESOLVED"
            return {"passed": True, "order_status": status, "order_value": status}
        if left <= floor_J and right > floor_J:
            status = "NOT_EVALUATED_REGRESSION_FROM_FLOOR"
            return {"passed": False, "order_status": status, "order_value": status}
        if left > floor_J and right == 0.0:
            status = "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT"
            return {"passed": True, "order_status": status, "order_value": status}
        if left > floor_J and 0.0 < right <= floor_J:
            status = "FINE_FLOOR_RESOLVED_POSITIVE_ORDER_LIMIT"
            return {"passed": True, "order_status": status, "order_value": status}
        order = math.log2(left) - math.log2(right)
        return {"passed": order >= p_min, "order_status": "FINITE_LOG2_ORDER", "order_value": order}

    cf = pair(coarse, fine)
    fr = pair(fine, reference)
    passed = bool(cf["passed"] and fr["passed"])
    return {"passed": passed, "category": "PAIRWISE_ORDER_PASS" if passed else "PAIRWISE_ORDER_FAIL", "CF": cf, "FR": fr}


def stable_quaternion_geodesic_rad(
    q1_wxyz: tuple[float, ...] | list[float],
    q2_wxyz: tuple[float, ...] | list[float],
    *,
    unit_norm_tolerance: float = 1e-12,
) -> dict[str, Any]:
    invalid = {"valid": False, "category": "INVALID_QUATERNION", "distance_rad": "NOT_EVALUATED_INVALID_QUATERNION"}
    def finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    if (
        not isinstance(q1_wxyz, (list, tuple))
        or not isinstance(q2_wxyz, (list, tuple))
        or len(q1_wxyz) != 4
        or len(q2_wxyz) != 4
        or not finite_number(unit_norm_tolerance)
        or unit_norm_tolerance < 0.0
        or any(not finite_number(value) for value in (*q1_wxyz, *q2_wxyz))
    ):
        return invalid
    norm1 = math.sqrt(sum(value * value for value in q1_wxyz))
    norm2 = math.sqrt(sum(value * value for value in q2_wxyz))
    if norm1 == 0.0 or norm2 == 0.0 or abs(norm1 - 1.0) > unit_norm_tolerance or abs(norm2 - 1.0) > unit_norm_tolerance:
        return invalid
    q1 = tuple(value / norm1 for value in q1_wxyz)
    q2 = tuple(value / norm2 for value in q2_wxyz)
    dot = sum(left * right for left, right in zip(q1, q2))
    sign = 1.0 if dot >= 0.0 else -1.0
    numerator = math.sqrt(sum((left - sign * right) ** 2 for left, right in zip(q1, q2)))
    denominator = math.sqrt(sum((left + sign * right) ** 2 for left, right in zip(q1, q2)))
    distance = 4.0 * math.atan2(numerator, denominator)
    if not math.isfinite(distance) or distance < 0.0 or distance > math.pi:
        return invalid
    return {"valid": True, "category": "VALID_QUATERNION_GEODESIC", "distance_rad": distance}


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def record(path: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": file_sha(path),
    }


def verify_sources(contract: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for declared in contract["sources"]:
        path = PROJECT_ROOT / declared["path"]
        exists = path.is_file() and not path.is_symlink()
        actual_bytes: int | str = path.stat().st_size if exists else "MISSING_FILE"
        actual_sha = file_sha(path) if exists else "MISSING_FILE"
        rows.append(
            {
                "id": declared["id"],
                "pass": bool(exists and actual_bytes == declared["bytes"] and actual_sha == declared["sha256"]),
                "declared_bytes": declared["bytes"],
                "actual_bytes": actual_bytes,
                "declared_sha256": declared["sha256"],
                "actual_sha256": actual_sha,
            }
        )
    return {"pass": all(row["pass"] for row in rows), "records": rows}


def verify_raw_inventory(contract: dict[str, Any]) -> dict[str, Any]:
    spec = contract["preserved_raw_inventory"]
    root = PROJECT_ROOT / spec["path"]
    files = sorted((path for path in root.iterdir() if path.is_file()), key=lambda path: path.name)
    if root.is_symlink() or any(path.is_symlink() for path in files):
        raise ContractError("linked raw evidence is forbidden")
    rows = [{"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha(path)} for path in files]
    actual = {
        "json_count": sum(path.suffix == ".json" for path in files),
        "npz_count": sum(path.suffix == ".npz" for path in files),
        "file_count": len(files),
        "canonical_sha256": canonical_hash(rows),
    }
    actual["pass"] = all(actual[key] == spec[key] for key in actual if key != "pass")
    return actual


def verify_parent_roots(sources: dict[str, Any]) -> dict[str, Any]:
    by_id = {row["id"]: row for row in sources["sources"]}
    terminal = load_json(PROJECT_ROOT / by_id["b4g_active_source_freeze_terminal"]["path"])
    gate_row = terminal["records"][0]
    gate_path = PROJECT_ROOT / gate_row["path"]
    gate = load_json(gate_path)
    manifest_row = gate["execution_source_manifest"]
    manifest_path = PROJECT_ROOT / manifest_row["path"]
    manifest = load_json(manifest_path)
    recursive_sources_pass = all(
        (PROJECT_ROOT / row["path"]).is_file()
        and (PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"]
        and file_sha(PROJECT_ROOT / row["path"]) == row["sha256"]
        for row in manifest["sources"]
    )
    r1_terminal = load_json(PROJECT_ROOT / by_id["b4g_r1_terminal"]["path"])
    r1_records_pass = all(
        (PROJECT_ROOT / row["path"]).is_file()
        and (PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"]
        and file_sha(PROJECT_ROOT / row["path"]) == row["sha256"]
        for row in r1_terminal["records"]
    )
    r1_gate = load_json(PROJECT_ROOT / by_id["b4g_r1_failure_closure_gate"]["path"])
    return {
        "b4g_source_freeze_pass": bool(
            terminal["self_excluded"] is True
            and terminal["acyclic"] is True
            and terminal["source_count"] == 52
            and file_sha(gate_path) == gate_row["sha256"]
            and file_sha(manifest_path) == manifest_row["sha256"]
            and canonical_hash(manifest["sources"]) == terminal["source_inventory_sha256"]
            and recursive_sources_pass
        ),
        "r1_terminal_pass": bool(
            r1_terminal["self_excluded"] is True
            and r1_terminal["acyclic"] is True
            and r1_records_pass
            and r1_gate["status"] == "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"
            and r1_gate["original_b4g_final_credit"] is False
            and r1_gate["b4g_scientific_gate_pass"] is False
        ),
    }


def verify_donor(sources: dict[str, Any]) -> dict[str, Any]:
    binding = sources["common_donor_payload_binding"]
    source = next(row for row in sources["sources"] if row["id"] == binding["source_id"])
    donor = load_json(PROJECT_ROOT / source["path"])
    payload = donor["event_provenance"]["acquisition_certificate_payload"]
    payload_bytes = canonical_bytes(payload)
    actual_hash = hashlib.sha256(payload_bytes).hexdigest().upper()
    declared_certificate = donor["event_provenance"]["acquisition_certificate_sha256"]
    event = payload["event"]
    acquisition = payload["acquisition"]
    reduced = acquisition["z_plus_reduced"]
    group_payload = {
        "schema": "B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
        "donor_acquisition_certificate_sha256": declared_certificate,
        "acquisition_time_s": acquisition["acquisition_time_s"],
        "service": {
            "base_position_inertial_m": event["service"]["base_position_inertial_m"],
            "base_quaternion_body_to_inertial_wxyz": event["service"]["base_quaternion_body_to_inertial_wxyz"],
            "joint_coordinates_mixed": event["service"]["joint_coordinates_mixed"],
            "post_acquisition_eta_mixed": reduced[:14],
        },
        "target": {
            "position_inertial_m": event["target"]["position_inertial_m"],
            "quaternion_body_to_inertial_wxyz": event["target"]["quaternion_body_to_inertial_wxyz"],
            "post_acquisition_twist_inertial_mixed": reduced[14:20],
        },
    }
    group_bytes = canonical_bytes(group_payload)
    group_hash = hashlib.sha256(group_bytes).hexdigest().upper()
    return {
        "pass": bool(
            binding["json_pointer"] == "/event_provenance/acquisition_certificate_payload"
            and len(payload_bytes) == binding["canonical_bytes"]
            and actual_hash == binding["canonical_sha256"]
            and declared_certificate == binding["declared_acquisition_certificate_sha256"] == actual_hash
            and group_payload["schema"] == binding["common_initial_state_group_schema"]
            and len(group_bytes) == binding["common_initial_state_group_canonical_bytes"]
            and group_hash == binding["common_initial_state_group_sha256"]
        ),
        "canonical_bytes": len(payload_bytes),
        "canonical_sha256": actual_hash,
        "declared_certificate_sha256": declared_certificate,
        "state_group_canonical_bytes": len(group_bytes),
        "state_group_sha256": group_hash,
    }


def project_acquisition_segment_identity(payload: dict[str, Any]) -> dict[str, Any]:
    invalid = {"status": "FAIL_IDENTITY_PROJECTION_SCHEMA", "canonical_bytes": "NOT_EVALUATED", "sha256": "NOT_EVALUATED"}
    try:
        case_id = payload["case_id"]
        if not isinstance(case_id, str) or payload["event"]["run_id"] != case_id or payload["acquisition"]["run_id"] != case_id:
            return invalid
        projected = json.loads(canonical_bytes(payload).decode("utf-8"), object_pairs_hook=_pairs)
        projected["case_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        projected["event"]["run_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        projected["acquisition"]["run_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        encoded = canonical_bytes(projected)
    except (KeyError, TypeError, ValueError, ContractError):
        return invalid
    return {"status": "PASS_IDENTITY_PROJECTION", "canonical_bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest().upper()}


def _alpha_token(alpha: float | int) -> str:
    return "0P5" if float(alpha) == 0.5 else str(int(alpha))


def _fresh_a1_id(lane_id: str, alpha: float | int, duration_ms: int) -> str:
    return f"FRESH__{lane_id}__A1__A_{_alpha_token(alpha)}__T_MS_{duration_ms}"


def expand_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane_id, method, step_s, _ in LANES:
        for sentinel in ("PRE", "POST"):
            rows.append(
                {
                    "case_id": f"FRESH__{lane_id}__A0__{sentinel}",
                    "execution_family": "FRESH",
                    "roles": ["A0_BOOKEND"],
                    "lane_id": lane_id,
                    "method": method,
                    "step_s": step_s,
                    "arm": "A0",
                    "sentinel": sentinel,
                    "alpha": "NOT_APPLICABLE_A0",
                    "command_duration_s": "NOT_APPLICABLE_A0",
                    "initial_state": "LANE_SPECIFIC_FRESH_B3",
                    "g12_credit": False,
                    "selector_input": False,
                }
            )
        for duration_ms in (5, 10, 20):
            roles = ["FRESH_ALPHA16_PROPAGATION"]
            if duration_ms == 10:
                roles.append("FRESH_ACQ_OBSERVATION")
            if step_s == 0.0000625:
                roles.append("G12_FRESH_REFERENCE")
            rows.append(
                {
                    "case_id": _fresh_a1_id(lane_id, 16, duration_ms),
                    "execution_family": "FRESH",
                    "roles": roles,
                    "lane_id": lane_id,
                    "method": method,
                    "step_s": step_s,
                    "arm": "A1",
                    "sentinel": "NOT_APPLICABLE_A1",
                    "alpha": 16.0,
                    "command_duration_s": duration_ms / 1000,
                    "initial_state": "LANE_SPECIFIC_FRESH_B3",
                    "g12_credit": step_s == 0.0000625,
                    "selector_input": step_s == 0.0000625,
                }
            )
        if step_s == 0.0000625:
            for alpha in (0.5, 1, 2, 4, 8):
                for duration_ms in (5, 10, 20):
                    rows.append(
                        {
                            "case_id": _fresh_a1_id(lane_id, alpha, duration_ms),
                            "execution_family": "FRESH",
                            "roles": ["G12_FRESH_REFERENCE"],
                            "lane_id": lane_id,
                            "method": method,
                            "step_s": step_s,
                            "arm": "A1",
                            "sentinel": "NOT_APPLICABLE_A1",
                            "alpha": float(alpha),
                            "command_duration_s": duration_ms / 1000,
                            "initial_state": "LANE_SPECIFIC_FRESH_B3",
                            "g12_credit": True,
                            "selector_input": True,
                        }
                    )
        for duration_ms in (5, 10, 20):
            rows.append(
                {
                    "case_id": f"COMMON_PROP__{lane_id}__A_16__T_MS_{duration_ms}",
                    "execution_family": "COMMON_PROP",
                    "roles": ["COMMON_PROPAGATION_DIAGNOSTIC"],
                    "lane_id": lane_id,
                    "method": method,
                    "step_s": step_s,
                    "arm": "A1",
                    "sentinel": "NOT_APPLICABLE_A1",
                    "alpha": 16.0,
                    "command_duration_s": duration_ms / 1000,
                    "initial_state": "COMMON_STATE_GROUP_396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444",
                    "g12_credit": False,
                    "selector_input": False,
                }
            )
    return sorted(rows, key=lambda row: row["case_id"])


def generate_schedule(seed: int) -> list[str]:
    def key(namespace: str, item: str) -> str:
        return hashlib.sha256(f"{seed}|{namespace}|{item}".encode("utf-8")).hexdigest()

    ordered: list[str] = []
    nonreference = sorted((lane for lane, _, step, _ in LANES if step != 0.0000625), key=lambda lane: key("NONREFERENCE_LANE_ORDER", lane))
    for lane in nonreference:
        ordered.append(f"FRESH__{lane}__A0__PRE")
        cases = [_fresh_a1_id(lane, 16, duration) for duration in (5, 10, 20)]
        ordered.extend(sorted(cases, key=lambda case: key(f"FRESH_LANE__{lane}", case)))
        ordered.append(f"FRESH__{lane}__A0__POST")

    references = tuple(lane for lane, _, step, _ in LANES if step == 0.0000625)
    pre = [f"FRESH__{lane}__A0__PRE" for lane in references]
    ordered.extend(sorted(pre, key=lambda case: key("REFERENCE_A0_PRE", case)))
    levels = [(alpha, duration) for alpha in (0.5, 1, 2, 4, 8, 16) for duration in (5, 10, 20)]
    levels.sort(key=lambda item: key("G12_LEVEL", f"{item[0]}|{item[1]}"))
    for alpha, duration in levels:
        pair = [_fresh_a1_id(lane, alpha, duration) for lane in references]
        namespace = f"G12_PAIR__{_alpha_token(alpha)}__{duration}"
        ordered.extend(sorted(pair, key=lambda case: key(namespace, case)))
    post = [f"FRESH__{lane}__A0__POST" for lane in references]
    ordered.extend(sorted(post, key=lambda case: key("REFERENCE_A0_POST", case)))

    durations = sorted((5, 10, 20), key=lambda duration: key("COMMON_DURATION", str(duration)))
    for duration in durations:
        cases = [f"COMMON_PROP__{lane}__A_16__T_MS_{duration}" for lane, _, _, _ in LANES]
        ordered.extend(sorted(cases, key=lambda case: key(f"COMMON_DURATION__{duration}", case)))
    return ordered


def validate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sources = load_json(SOURCES)
    design = load_json(DESIGN)
    schedule = load_json(SCHEDULE)
    numerical = load_json(NUMERICAL)
    governance = load_json(GOVERNANCE)
    test_result = load_json(TEST_RESULT)
    source_check = verify_sources(sources)
    raw_check = verify_raw_inventory(sources)
    parent_check = verify_parent_roots(sources)
    donor_check = verify_donor(sources)
    matrix = expand_matrix()
    generated_schedule = generate_schedule(schedule["seed"])
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any = "NO_ADDITIONAL_DETAIL") -> None:
        checks.append({"id": check_id, "pass": bool(condition), "detail": detail})

    check("R2V01", sources["schema"] == "SIM13_V4B4G_R2_SOURCE_BINDINGS_V1")
    check("R2V02", design["schema"] == "SIM13_V4B4G_R2_PREFLIGHT_DESIGN_V1")
    check("R2V03", schedule["schema"] == "SIM13_V4B4G_R2_BLOCKED_SCHEDULE_V1")
    check("R2V04", numerical["schema"] == "SIM13_V4B4G_R2_NUMERICAL_ACCEPTANCE_V1")
    check("R2V05", governance["schema"] == "SIM13_V4B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1")
    check("R2V06", source_check["pass"], source_check)
    check("R2V07", raw_check["pass"], raw_check)
    check("R2V08", parent_check == {"b4g_source_freeze_pass": True, "r1_terminal_pass": True}, parent_check)
    check("R2V09", donor_check["pass"], donor_check)

    lane_grid = design["lane_grid"]
    check(
        "R2V10",
        len(lane_grid) == 6
        and {row["method"] for row in lane_grid} == {"rk4", "midpoint"}
        and all([row["step_s"] for row in lane_grid if row["method"] == method] == [0.00025, 0.000125, 0.0000625] for method in ("rk4", "midpoint")),
    )
    acq = design["tracks"]["fresh_lane_acquisition_convergence"]
    floors = acq["registered_channels_and_floors"]
    identity_rule = acq["technical_repeat_identity_projection"]
    identity_acceptance = numerical["fresh_acquisition_technical_repeat_identity_rule"]
    raw_root = PROJECT_ROOT / sources["preserved_raw_inventory"]["path"]
    identity_projections = []
    for basename in identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["basenames"]:
        raw_case = load_json(raw_root / basename)
        identity_projections.append(project_acquisition_segment_identity(raw_case["event_provenance"]["acquisition_certificate_payload"]))
    quaternion_contract = design["quaternion_metric_contract"]
    q_sign = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0])
    q_pi = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0])
    q_norm_inside = stable_quaternion_geodesic_rad([1.0 + 5e-13, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    q_norm_outside = stable_quaternion_geodesic_rad([1.0 + 2e-12, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    check(
        "R2V11",
        acq["observation_count"] == 6
        and "6.25e-5_s" in acq["comparison_definitions"]["acquisition_time_rule"]
        and "0.60" in acq["comparison_definitions"]["native_channel_rule"]
        and len(floors) == 16
        and all(row["floor"] > 0 and row["unit"] and row["metric"] for row in floors.values())
        and acq["certificates"]["valid_and_unique_per_case_required"] is True
        and acq["certificates"]["certificate_hash_convergence_required"] is False
        and identity_rule["rule_id"] == identity_acceptance["rule_id"] == "B4G_R2_FRESH_ACQUISITION_SEGMENT_IDENTITY_V1"
        and identity_rule["allowed_different_json_pointers_exact"] == identity_acceptance["allowed_different_json_pointers_exact"] == ["/case_id", "/event/run_id", "/acquisition/run_id"]
        and identity_acceptance["all_unlisted_pointers_keys_lengths_types_and_values_exactly_equal_required"] is True
        and identity_acceptance["pseudoreplication_credit_for_5ms_or_20ms_repeat"] is False
        and all(item["status"] == "PASS_IDENTITY_PROJECTION" for item in identity_projections)
        and {item["canonical_bytes"] for item in identity_projections} == {identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["projected_canonical_bytes_each"]} == {31050}
        and {item["sha256"] for item in identity_projections} == {identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["projected_sha256_each"]} == {"29DFA8D35BBBA4E615B583B09EBB1B32144C0FE39B740898F1A0EB7ED838511C"}
        and quaternion_contract["rule_id"] == "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1"
        and quaternion_contract["formula"] == "d_rad=4*atan2(norm(q1-s*q2),norm(q1+s*q2))"
        and quaternion_contract["unit_norm_absolute_tolerance"] == 1e-12
        and q_sign == {"valid": True, "category": "VALID_QUATERNION_GEODESIC", "distance_rad": 0.0}
        and q_pi["valid"] is True
        and math.isclose(q_pi["distance_rad"], math.pi, rel_tol=0.0, abs_tol=1e-15)
        and q_norm_inside["valid"] is True
        and q_norm_outside["valid"] is False,
    )
    fresh = design["tracks"]["fresh_reference_g12_and_alpha16_propagation"]
    check(
        "R2V12",
        fresh["alpha16_refinement_domain"]["case_count"] == 18
        and fresh["g12_reference_domain"]["case_count"] == 36
        and fresh["a0_bookends"]["case_count"] == 12
        and fresh["fresh_unique_case_count"] == 60,
    )
    common = design["tracks"]["common_initial_state_propagation_convergence"]
    behavior = common["rehydrator_and_roundtrip_behavior_contract"]
    boundary = common["fixture_use_boundary"]
    check(
        "R2V13",
        common["domain"]["case_count"] == 18
        and common["common_initial_state_fixture"]["common_initial_state_group_canonical_bytes"] == donor_check["state_group_canonical_bytes"] == 1317
        and common["common_initial_state_fixture"]["common_initial_state_group_sha256"] == donor_check["state_group_sha256"] == "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"
        and common["common_initial_state_fixture"]["common_initial_state_group_field_map"] == EXPECTED_GROUP_FIELD_MAP
        and common["comparison_channels_and_floors"] == EXPECTED_COMMON_CHANNELS
        and sum(row["metric"] == quaternion_contract["rule_id"] for row in common["comparison_channels_and_floors"].values()) == 2
        and behavior["implementation_in_this_contract_package"] is False
        and behavior["roundtrip_verified_in_this_contract_package"] is False
        and "fresh deep copy" in behavior["per_case_object_isolation"]
        and "before and immediately after" in behavior["donor_immutability_check"]
        and boundary["numerical_propagation_isolation_only"] is True
        and all(value is False for key, value in boundary.items() if key != "numerical_propagation_isolation_only"),
    )
    matrix_hash = canonical_hash(matrix)
    fixed = design["fixed_matrix"]
    applicability = design["matrix_field_applicability"]
    matrix_applicability_ok = not contains_none(matrix)
    for row in matrix:
        if row["arm"] == "A0":
            matrix_applicability_ok &= (
                row["alpha"] == applicability["A0_alpha_enum"]
                and row["command_duration_s"] == applicability["A0_command_duration_enum"]
                and row["sentinel"] in applicability["A0_sentinel_allowed_values"]
            )
        elif row["arm"] == "A1":
            matrix_applicability_ok &= (
                row["sentinel"] == applicability["A1_sentinel_enum"]
                and isinstance(row["alpha"], (int, float))
                and not isinstance(row["alpha"], bool)
                and math.isfinite(row["alpha"])
                and row["alpha"] > 0.0
                and isinstance(row["command_duration_s"], (int, float))
                and not isinstance(row["command_duration_s"], bool)
                and math.isfinite(row["command_duration_s"])
                and row["command_duration_s"] > 0.0
            )
        else:
            matrix_applicability_ok = False
    check(
        "R2V14",
        len(matrix) == fixed["total_unique_case_count"] == 78
        and len({row["case_id"] for row in matrix}) == 78
        and applicability["null_values_forbidden"] is True
        and matrix_applicability_ok
        and matrix_hash == fixed["canonical_expanded_matrix_sha256"] == schedule["expanded_matrix_canonical_sha256"],
        matrix_hash,
    )
    schedule_hash = canonical_hash(generated_schedule)
    check(
        "R2V15",
        generated_schedule == schedule["case_ids_in_blocked_order"]
        and len(generated_schedule) == schedule["case_count"] == 78
        and schedule_hash == schedule["case_ids_canonical_sha256"]
        and set(generated_schedule) == {row["case_id"] for row in matrix},
        schedule_hash,
    )
    fresh_rows = [row for row in matrix if row["execution_family"] == "FRESH"]
    common_rows = [row for row in matrix if row["execution_family"] == "COMMON_PROP"]
    check(
        "R2V16",
        len(fresh_rows) == 60
        and len(common_rows) == 18
        and not ({row["case_id"] for row in fresh_rows} & {row["case_id"] for row in common_rows})
        and sum("FRESH_ACQ_OBSERVATION" in row["roles"] for row in matrix) == 6
        and sum("G12_FRESH_REFERENCE" in row["roles"] for row in matrix) == 36
        and all(not row["g12_credit"] and not row["selector_input"] for row in common_rows),
    )

    g04 = numerical["g04_unified_work_rule"]
    check(
        "R2V17",
        g04["rule_id"] == g04["runner_rule_id_required"] == g04["validator_rule_id_required"]
        and g04["W_act_initial_exact"] == 0.0
        and g04["sample_power_absolute_tolerance_W"] == 1e-14
        and g04["sample_power_relative_tolerance"] == 0.0
        and g04["stage_power_absolute_tolerance_W"] == 1e-14
        and g04["stage_power_relative_tolerance"] == 0.0
        and g04["cumulative_max_abs_error_limit_J"] == 1e-7
        and g04["terminal_native_abs_error_limit_J"] == 1e-7
        and g04["refinement_slack_J"] == 1e-15
        and g04["finite_removal_post_conditions"]["post_W_exactly_constant_and_equal_to_active_terminal"] is True
        and g04["finite_removal_post_conditions"]["post_actuator_work_reset_on_removal"] is False
        and g04["required_report_fields"] == g04["runner_required_report_fields"] == g04["validator_required_report_fields"] == EXPECTED_G04_FIELDS
        and "finite_removal_present==false" in g04["finite_removal_post_pass_expression"]
        and "all(post_W_act_J[j]==active_terminal_W_act_J for every saved post sample j)" in g04["finite_removal_post_pass_expression"]
        and "all(post_generalized_force_Q_14[j,k]==0.0 for every saved post sample j and k=0..13)" in g04["finite_removal_post_pass_expression"]
        and g04["pass_expression"] == g04["runner_pass_expression_required"] == g04["validator_pass_expression_required"]
        and g04["finite_removal_post_pass_expression"] in g04["pass_expression"]
        and "any_finite_removal" not in g04["pass_expression"]
        and g04["W_act_equal_to_delta_T_identity_forbidden"] is True,
    )
    comparator = numerical["total_direct_order_comparator"]
    zero_case = evaluate_direct_order_triplet((0.0, 0.0, 0.0), floor_J=2e-12, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    exact_zero_fine = evaluate_direct_order_triplet((1e-5, 0.0, 0.0), floor_J=1e-10, p_min=3.0, floor_scope="ALL_THREE")
    regression = evaluate_direct_order_triplet((0.0, 1e-5, 1e-6), floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    invalid = evaluate_direct_order_triplet((float("nan"), 1.0, 0.1), floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    check(
        "R2V18",
        comparator["rule_id"] == "B4G_R2_TOTAL_DIRECT_ERROR_RATIO_ORDER_V1"
        and comparator["nonfinite_JSON_numbers_forbidden"] is True
        and g04["empirical_order"]["comparator_rule_id"] == comparator["rule_id"]
        and g04["empirical_order"]["floor_resolution_scope"] == "FINE_AND_REFERENCE"
        and g04["empirical_order"]["floor_J"] == 2e-12
        and g04["empirical_order"]["p_min"] == 1.8
        and zero_case["category"] == "OVERALL_FLOOR_RESOLVED"
        and exact_zero_fine["CF"]["order_status"] == "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT"
        and exact_zero_fine["passed"] is True
        and regression["passed"] is False
        and invalid["category"] == "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA"
        and not contains_none((zero_case, exact_zero_fine, regression, invalid)),
    )
    g06 = numerical["g06_energy_minus_work_rule"]
    check(
        "R2V19",
        g06["active_max_abs_limit_J"] == 1e-7
        and g06["threshold_change_from_failed_B4G"] is False
        and g06["midpoint_floor_resolution_scope"] == "FINE_AND_REFERENCE"
        and g06["midpoint_p_min"] == 1.8
        and g06["rk4_floor_resolution_scope"] == "ALL_THREE"
        and g06["rk4_p_min"] == 3.0
        and g06["floor_resolved_J"] == 1e-10,
    )
    fresh_rule = numerical["fresh_alpha16_propagation_rule"]
    check(
        "R2V20",
        fresh_rule["finite_bilateral_removal_required_at_all_three_steps"] is True
        and fresh_rule["G04_and_G06_each_case_limit_J"] == 1e-7
        and fresh_rule["removal_time_D_FR_limit_s"] == 0.00025
        and set(fresh_rule["required_true_gate_ids"])
        == {
            "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
            "B4F-G04-ACTUATOR-WORK-LEDGER",
            "B4F-G05-P-H-CONSERVATION",
            "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
            "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
            "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
            "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
            "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
            "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
            "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
        },
    )
    common_rule = numerical["common_propagation_convergence_rule"]
    check(
        "R2V21",
        math.isclose(common_rule["midpoint_contraction_max"], 2.0 ** (-1.8), rel_tol=0.0, abs_tol=1e-16)
        and common_rule["midpoint_contraction_formula"] == "2^(-1.8)"
        and common_rule["midpoint_contraction_max"] < 0.3
        and common_rule["midpoint_p_min"] == 1.8
        and common_rule["rk4_contraction_max"] == 0.125
        and common_rule["rk4_p_min"] == 3.0
        and "D_FR_midpoint/(2^1.8-1)" in common_rule["finest_cross_method_rule"]
        and "D_FR_rk4/(2^3.0-1)" in common_rule["finest_cross_method_rule"]
        and 0.295 <= 0.3
        and 0.295 > common_rule["midpoint_contraction_max"]
        and common_rule["shared_removal_time_comparison"] is False
        and common_rule["G12_credit"] is False
        and common_rule["selector_input"] is False,
    )
    g12 = numerical["g12_reference_event_and_signed_work_preflight"]
    check(
        "R2V22",
        g12["level_count"] == 18
        and g12["acquisition_event_time_difference_s_max"] == 0.00025
        and g12["removal_event_time_difference_s_max"] == 0.00025
        and g12["aggregate_requires_all_scientific_predicates_true"] is False
        and g12["supports_later_decision_when_aggregate_passes"] is True
        and g12["aggregate_rule_contract_frozen"] is True,
    )
    check(
        "R2V23",
        design["scientific_matrix_review"] == {"status": "INDEPENDENT_REVIEW_FROZEN_FOR_CONTRACT_ONLY", "all_design_fields_complete": True, "matrix_may_be_executed_under_this_contract_package": False, "future_change_requires_new_version": True}
        and design["execution_readiness_status_exact"] == governance["execution_readiness_status_exact"]
        and design["r2_source_freeze_issued"] is False
        and design["rehydrator_implemented"] is False
        and design["new_preflight_executed"] is False
        and design["full_campaign_authorized"] is False,
    )
    check(
        "R2V24",
        governance["negative_control_count"] == len(governance["negative_controls"]) == 46
        and len(set(governance["negative_controls"])) == 46
        and all(governance["contract_frozen_true"].values())
        and all(value is False for value in governance["required_false"].values())
        and governance["negative_controls_implemented"] is False
        and governance["negative_controls_executed"] is False
        and governance["gate_status_exact"] == "PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY",
    )
    check(
        "R2V25",
        test_result["status"] == "PASS_PHASE_B4G_R2_PYTEST"
        and test_result["collected"] == governance["test_contract"]["expected_collected"]
        and test_result["nodeid_sha256"] == governance["test_contract"]["expected_nodeid_sha256"]
        and test_result["outcomes"] == governance["test_contract"]["required_outcome"],
        test_result,
    )
    artifact_guard = governance["recursive_artifact_guard"]
    forbidden_suffixes = set(artifact_guard["forbidden_file_suffixes"])
    forbidden_names = set(artifact_guard["forbidden_directory_names"])
    forbidden_solver_tokens = set(artifact_guard["forbidden_solver_module_tokens"])
    forbidden_filename_substrings = set(artifact_guard["forbidden_file_name_substrings"])
    package_paths = list(HERE.rglob("*"))
    imported_modules: list[str] = []
    for path in HERE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(node.module or "")
    check(
        "R2V26",
        artifact_guard["validator_audit_and_pytest_must_each_enforce"] is True
        and not any(path.suffix.lower() in forbidden_suffixes for path in package_paths if path.is_file())
        and not any(path.name in forbidden_names for path in package_paths if path.is_dir())
        and not any(token in name for token in forbidden_solver_tokens for name in imported_modules)
        and not any(token in path.name.lower() for token in forbidden_filename_substrings for path in package_paths if path.is_file())
        and not contains_none((sources, design, schedule, numerical, governance, test_result, matrix)),
    )

    failed = [row["id"] for row in checks if not row["pass"]]
    snapshot = {
        "schema": "SIM13_V4B4G_R2_CONTRACT_SNAPSHOT_V1",
        "scope": "CONTRACT_ONLY_NO_NUMERICAL_PREFLIGHT_EXECUTION",
        "source_verification": source_check,
        "parent_root_verification": parent_check,
        "preserved_raw_inventory": raw_check,
        "common_donor_verification": donor_check,
        "technical_repeat_identity_rule_sanity_anchor": {
            "case_count": len(identity_projections),
            "canonical_bytes_each": identity_projections[0]["canonical_bytes"],
            "sha256_each": identity_projections[0]["sha256"],
            "new_preflight_executed": False,
        },
        "matrix": {
            "case_count": len(matrix),
            "canonical_sha256": matrix_hash,
            "fresh_count": len(fresh_rows),
            "common_prop_count": len(common_rows),
            "g12_fresh_reference_count": sum("G12_FRESH_REFERENCE" in row["roles"] for row in matrix),
        },
        "schedule": {"seed": schedule["seed"], "case_count": len(generated_schedule), "canonical_sha256": schedule_hash},
        "contract_review_status": design["scientific_matrix_review"]["status"],
        "execution_readiness_status": design["execution_readiness_status_exact"],
        "new_preflight_executed": False,
        "full_campaign_authorized": False,
    }
    atomic_json(SNAPSHOT, snapshot)
    validation = {
        "schema": "SIM13_V4B4G_R2_VALIDATION_V1",
        "status": "PASS_R2_PREFLIGHT_CONTRACT_VALIDATION_READY_FOR_INDEPENDENT_AUDIT" if not failed else "FAIL_R2_PREFLIGHT_CONTRACT_VALIDATION",
        "scope": "CONTRACT_FREEZE_ONLY_NO_SOLVER_NO_NUMERICAL_EXECUTION",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "snapshot": record(SNAPSHOT, "B4G_R2_CONTRACT_SNAPSHOT"),
        "execution_readiness_status": design["execution_readiness_status_exact"],
        "new_preflight_executed": False,
        "full_campaign_authorized": False,
    }
    atomic_json(VALIDATION, validation)
    manifest_records = [record(HERE / relative, "B4G_R2_LOCAL_SOURCE") for relative in LOCAL_SOURCES]
    manifest_records.extend((record(TEST_RESULT, "B4G_R2_PYTEST_RESULT"), record(SNAPSHOT, "B4G_R2_CONTRACT_SNAPSHOT"), record(VALIDATION, "B4G_R2_VALIDATION")))
    manifest = {
        "schema": "SIM13_V4B4G_R2_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1",
        "self_excluded": True,
        "acyclic": True,
        "scope": "NUMERICAL_PREFLIGHT_CONTRACT_ONLY",
        "record_count": len(manifest_records),
        "records": manifest_records,
    }
    atomic_json(MANIFEST, manifest)
    return snapshot, validation, manifest


def main() -> int:
    try:
        _, validation, manifest = validate()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_VALIDATOR_EXCEPTION", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": validation["status"], "score": validation["score"], "manifest_records": manifest["record_count"], "validation_sha256": file_sha(VALIDATION)}, ensure_ascii=False))
    return 0 if validation["score"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
