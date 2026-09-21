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
VALIDATION = RESULTS / "SIM13_V4B4G_R2_VALIDATION_V1.json"
MANIFEST = EVIDENCE / "SIM13_V4B4G_R2_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"
AUDIT = RESULTS / "SIM13_V4B4G_R2_INDEPENDENT_AUDIT_V1.json"

LANES = (
    ("RK4_H_MS_0P25", "rk4", 0.00025),
    ("RK4_H_MS_0P125", "rk4", 0.000125),
    ("RK4_H_MS_0P0625", "rk4", 0.0000625),
    ("MIDPOINT_H_MS_0P25", "midpoint", 0.00025),
    ("MIDPOINT_H_MS_0P125", "midpoint", 0.000125),
    ("MIDPOINT_H_MS_0P0625", "midpoint", 0.0000625),
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


class AuditError(RuntimeError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if not isinstance(result, dict):
        raise AuditError(f"expected object: {path}")
    return result


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def has_null_leaf(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(has_null_leaf(key) or has_null_leaf(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_null_leaf(item) for item in value)
    return False


def audit_direct_order(errors: Any, floor: Any, p_min: Any, scope: str) -> dict[str, Any]:
    not_evaluated = "NOT_EVALUATED_INVALID_INPUT"
    def finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    if (
        not isinstance(errors, (list, tuple))
        or len(errors) != 3
        or scope not in {"FINE_AND_REFERENCE", "ALL_THREE"}
        or not finite_number(floor)
        or floor <= 0.0
        or not finite_number(p_min)
        or p_min < 0.0
        or any(not finite_number(value) or value < 0.0 for value in errors)
    ):
        return {"pass": False, "category": "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA", "CF": not_evaluated, "FR": not_evaluated}
    coarse, fine, reference = errors
    floor_values = (fine, reference) if scope == "FINE_AND_REFERENCE" else errors
    if all(value <= floor for value in floor_values):
        marker = "NOT_EVALUATED_OVERALL_FLOOR_RESOLVED"
        return {"pass": True, "category": "OVERALL_FLOOR_RESOLVED", "CF": marker, "FR": marker}

    def compare(left: float, right: float) -> tuple[bool, str | float]:
        if left <= floor and right <= floor:
            return True, "NOT_EVALUATED_PAIR_FLOOR_RESOLVED"
        if left <= floor and right > floor:
            return False, "NOT_EVALUATED_REGRESSION_FROM_FLOOR"
        if left > floor and right == 0.0:
            return True, "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT"
        if left > floor and right <= floor:
            return True, "FINE_FLOOR_RESOLVED_POSITIVE_ORDER_LIMIT"
        order = math.log2(left) - math.log2(right)
        return order >= p_min, order

    cf_pass, cf_order = compare(coarse, fine)
    fr_pass, fr_order = compare(fine, reference)
    passed = cf_pass and fr_pass
    return {"pass": passed, "category": "PAIRWISE_ORDER_PASS" if passed else "PAIRWISE_ORDER_FAIL", "CF": cf_order, "FR": fr_order}


def audit_quaternion_distance(first: list[float], second: list[float], tolerance: float = 1e-12) -> dict[str, Any]:
    invalid = {"valid": False, "distance_rad": "NOT_EVALUATED_INVALID_QUATERNION"}
    def finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    if not isinstance(first, list) or not isinstance(second, list) or len(first) != 4 or len(second) != 4 or not finite_number(tolerance) or tolerance < 0.0 or any(not finite_number(value) for value in first + second):
        return invalid
    norm_first = math.sqrt(sum(value * value for value in first))
    norm_second = math.sqrt(sum(value * value for value in second))
    if norm_first == 0.0 or norm_second == 0.0 or abs(norm_first - 1.0) > tolerance or abs(norm_second - 1.0) > tolerance:
        return invalid
    left = [value / norm_first for value in first]
    right = [value / norm_second for value in second]
    sign = 1.0 if sum(a * b for a, b in zip(left, right)) >= 0.0 else -1.0
    chord_minus = math.sqrt(sum((a - sign * b) ** 2 for a, b in zip(left, right)))
    chord_plus = math.sqrt(sum((a + sign * b) ** 2 for a, b in zip(left, right)))
    distance = 4.0 * math.atan2(chord_minus, chord_plus)
    if not math.isfinite(distance) or distance < 0.0 or distance > math.pi:
        return invalid
    return {"valid": True, "distance_rad": distance}


def audit_identity_projection(payload: dict[str, Any]) -> dict[str, Any]:
    failure = {"pass": False, "bytes": "NOT_EVALUATED", "sha256": "NOT_EVALUATED"}
    try:
        case_id = payload["case_id"]
        if not isinstance(case_id, str) or payload["event"]["run_id"] != case_id or payload["acquisition"]["run_id"] != case_id:
            return failure
        projected = json.loads(canonical_bytes(payload).decode("utf-8"), object_pairs_hook=_pairs)
        for container, key in ((projected, "case_id"), (projected["event"], "run_id"), (projected["acquisition"], "run_id")):
            container[key] = "CASE_IDENTITY_EXCLUDED_V1"
        encoded = canonical_bytes(projected)
    except (KeyError, TypeError, ValueError, AuditError):
        return failure
    return {"pass": True, "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest().upper()}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def alpha_token(alpha: float | int) -> str:
    return "0P5" if float(alpha) == 0.5 else str(int(alpha))


def fresh_id(lane: str, alpha: float | int, duration_ms: int) -> str:
    return f"FRESH__{lane}__A1__A_{alpha_token(alpha)}__T_MS_{duration_ms}"


def independent_matrix() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for lane, method, step in LANES:
        for sentinel in ("PRE", "POST"):
            records.append(
                {
                    "case_id": f"FRESH__{lane}__A0__{sentinel}",
                    "execution_family": "FRESH",
                    "roles": ["A0_BOOKEND"],
                    "lane_id": lane,
                    "method": method,
                    "step_s": step,
                    "arm": "A0",
                    "sentinel": sentinel,
                    "alpha": "NOT_APPLICABLE_A0",
                    "command_duration_s": "NOT_APPLICABLE_A0",
                    "initial_state": "LANE_SPECIFIC_FRESH_B3",
                    "g12_credit": False,
                    "selector_input": False,
                }
            )
        for duration in (5, 10, 20):
            roles = ["FRESH_ALPHA16_PROPAGATION"]
            if duration == 10:
                roles.append("FRESH_ACQ_OBSERVATION")
            if step == 0.0000625:
                roles.append("G12_FRESH_REFERENCE")
            records.append(
                {
                    "case_id": fresh_id(lane, 16, duration),
                    "execution_family": "FRESH",
                    "roles": roles,
                    "lane_id": lane,
                    "method": method,
                    "step_s": step,
                    "arm": "A1",
                    "sentinel": "NOT_APPLICABLE_A1",
                    "alpha": 16.0,
                    "command_duration_s": duration / 1000,
                    "initial_state": "LANE_SPECIFIC_FRESH_B3",
                    "g12_credit": step == 0.0000625,
                    "selector_input": step == 0.0000625,
                }
            )
        if step == 0.0000625:
            for alpha in (0.5, 1, 2, 4, 8):
                for duration in (5, 10, 20):
                    records.append(
                        {
                            "case_id": fresh_id(lane, alpha, duration),
                            "execution_family": "FRESH",
                            "roles": ["G12_FRESH_REFERENCE"],
                            "lane_id": lane,
                            "method": method,
                            "step_s": step,
                            "arm": "A1",
                            "sentinel": "NOT_APPLICABLE_A1",
                            "alpha": float(alpha),
                            "command_duration_s": duration / 1000,
                            "initial_state": "LANE_SPECIFIC_FRESH_B3",
                            "g12_credit": True,
                            "selector_input": True,
                        }
                    )
        for duration in (5, 10, 20):
            records.append(
                {
                    "case_id": f"COMMON_PROP__{lane}__A_16__T_MS_{duration}",
                    "execution_family": "COMMON_PROP",
                    "roles": ["COMMON_PROPAGATION_DIAGNOSTIC"],
                    "lane_id": lane,
                    "method": method,
                    "step_s": step,
                    "arm": "A1",
                    "sentinel": "NOT_APPLICABLE_A1",
                    "alpha": 16.0,
                    "command_duration_s": duration / 1000,
                    "initial_state": "COMMON_STATE_GROUP_396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444",
                    "g12_credit": False,
                    "selector_input": False,
                }
            )
    return sorted(records, key=lambda record: record["case_id"])


def independent_schedule(seed: int) -> list[str]:
    def order_key(namespace: str, value: str) -> str:
        return hashlib.sha256(f"{seed}|{namespace}|{value}".encode("utf-8")).hexdigest()

    result: list[str] = []
    nonreference = sorted((lane for lane, _, step in LANES if step != 0.0000625), key=lambda lane: order_key("NONREFERENCE_LANE_ORDER", lane))
    for lane in nonreference:
        result.append(f"FRESH__{lane}__A0__PRE")
        body = [fresh_id(lane, 16, duration) for duration in (5, 10, 20)]
        result.extend(sorted(body, key=lambda item: order_key(f"FRESH_LANE__{lane}", item)))
        result.append(f"FRESH__{lane}__A0__POST")
    references = tuple(lane for lane, _, step in LANES if step == 0.0000625)
    result.extend(sorted((f"FRESH__{lane}__A0__PRE" for lane in references), key=lambda item: order_key("REFERENCE_A0_PRE", item)))
    levels = [(alpha, duration) for alpha in (0.5, 1, 2, 4, 8, 16) for duration in (5, 10, 20)]
    levels.sort(key=lambda item: order_key("G12_LEVEL", f"{item[0]}|{item[1]}"))
    for alpha, duration in levels:
        pair = [fresh_id(lane, alpha, duration) for lane in references]
        result.extend(sorted(pair, key=lambda item: order_key(f"G12_PAIR__{alpha_token(alpha)}__{duration}", item)))
    result.extend(sorted((f"FRESH__{lane}__A0__POST" for lane in references), key=lambda item: order_key("REFERENCE_A0_POST", item)))
    durations = sorted((5, 10, 20), key=lambda value: order_key("COMMON_DURATION", str(value)))
    for duration in durations:
        block = [f"COMMON_PROP__{lane}__A_16__T_MS_{duration}" for lane, _, _ in LANES]
        result.extend(sorted(block, key=lambda item: order_key(f"COMMON_DURATION__{duration}", item)))
    return result


def source_check(sources: dict[str, Any]) -> bool:
    return all(
        (PROJECT_ROOT / row["path"]).is_file()
        and not (PROJECT_ROOT / row["path"]).is_symlink()
        and (PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"]
        and sha(PROJECT_ROOT / row["path"]) == row["sha256"]
        for row in sources["sources"]
    )


def raw_inventory(sources: dict[str, Any]) -> dict[str, Any]:
    spec = sources["preserved_raw_inventory"]
    root = PROJECT_ROOT / spec["path"]
    paths = sorted((path for path in root.iterdir() if path.is_file()), key=lambda path: path.name)
    rows = [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in paths]
    return {
        "json_count": sum(path.suffix == ".json" for path in paths),
        "npz_count": sum(path.suffix == ".npz" for path in paths),
        "file_count": len(paths),
        "canonical_sha256": canonical_hash(rows),
        "no_links": not root.is_symlink() and not any(path.is_symlink() for path in paths),
    }


def parent_roots(sources: dict[str, Any]) -> bool:
    rows = {row["id"]: row for row in sources["sources"]}
    terminal = load(PROJECT_ROOT / rows["b4g_active_source_freeze_terminal"]["path"])
    gate_path = PROJECT_ROOT / terminal["records"][0]["path"]
    gate = load(gate_path)
    manifest_path = PROJECT_ROOT / gate["execution_source_manifest"]["path"]
    manifest = load(manifest_path)
    b4g_ok = (
        terminal["self_excluded"] is True
        and terminal["acyclic"] is True
        and terminal["source_count"] == 52
        and sha(gate_path) == terminal["records"][0]["sha256"]
        and sha(manifest_path) == gate["execution_source_manifest"]["sha256"]
        and canonical_hash(manifest["sources"]) == terminal["source_inventory_sha256"]
        and all((PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"] and sha(PROJECT_ROOT / row["path"]) == row["sha256"] for row in manifest["sources"])
    )
    r1_terminal = load(PROJECT_ROOT / rows["b4g_r1_terminal"]["path"])
    r1_gate = load(PROJECT_ROOT / rows["b4g_r1_failure_closure_gate"]["path"])
    r1_ok = (
        r1_terminal["self_excluded"] is True
        and r1_terminal["acyclic"] is True
        and all((PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"] and sha(PROJECT_ROOT / row["path"]) == row["sha256"] for row in r1_terminal["records"])
        and r1_gate["status"] == "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"
        and r1_gate["original_b4g_final_credit"] is False
    )
    return bool(b4g_ok and r1_ok)


def audit() -> dict[str, Any]:
    sources = load(SOURCES)
    design = load(DESIGN)
    schedule = load(SCHEDULE)
    numerical = load(NUMERICAL)
    governance = load(GOVERNANCE)
    tests = load(TEST_RESULT)
    validation = load(VALIDATION)
    manifest = load(MANIFEST)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: Any = "NO_ADDITIONAL_DETAIL") -> None:
        checks.append({"id": check_id, "pass": bool(passed), "detail": detail})

    check("R2A01", source_check(sources))
    raw = raw_inventory(sources)
    spec = sources["preserved_raw_inventory"]
    check("R2A02", raw == {"json_count": spec["json_count"], "npz_count": spec["npz_count"], "file_count": spec["file_count"], "canonical_sha256": spec["canonical_sha256"], "no_links": True}, raw)
    check("R2A03", parent_roots(sources))
    donor_source = next(row for row in sources["sources"] if row["id"] == sources["common_donor_payload_binding"]["source_id"])
    donor = load(PROJECT_ROOT / donor_source["path"])
    payload = donor["event_provenance"]["acquisition_certificate_payload"]
    donor_binding = sources["common_donor_payload_binding"]
    reduced = payload["acquisition"]["z_plus_reduced"]
    state_group = {
        "schema": "B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
        "donor_acquisition_certificate_sha256": donor["event_provenance"]["acquisition_certificate_sha256"],
        "acquisition_time_s": payload["acquisition"]["acquisition_time_s"],
        "service": {
            "base_position_inertial_m": payload["event"]["service"]["base_position_inertial_m"],
            "base_quaternion_body_to_inertial_wxyz": payload["event"]["service"]["base_quaternion_body_to_inertial_wxyz"],
            "joint_coordinates_mixed": payload["event"]["service"]["joint_coordinates_mixed"],
            "post_acquisition_eta_mixed": reduced[:14],
        },
        "target": {
            "position_inertial_m": payload["event"]["target"]["position_inertial_m"],
            "quaternion_body_to_inertial_wxyz": payload["event"]["target"]["quaternion_body_to_inertial_wxyz"],
            "post_acquisition_twist_inertial_mixed": reduced[14:20],
        },
    }
    check("R2A04", len(canonical_bytes(payload)) == donor_binding["canonical_bytes"] and canonical_hash(payload) == donor_binding["canonical_sha256"] == donor["event_provenance"]["acquisition_certificate_sha256"] and len(canonical_bytes(state_group)) == donor_binding["common_initial_state_group_canonical_bytes"] == 1317 and canonical_hash(state_group) == donor_binding["common_initial_state_group_sha256"] == "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444")

    matrix = independent_matrix()
    matrix_hash = canonical_hash(matrix)
    applicability = design["matrix_field_applicability"]
    applicability_ok = not has_null_leaf(matrix)
    for row in matrix:
        if row["arm"] == "A0":
            applicability_ok &= row["alpha"] == applicability["A0_alpha_enum"] and row["command_duration_s"] == applicability["A0_command_duration_enum"] and row["sentinel"] in applicability["A0_sentinel_allowed_values"]
        elif row["arm"] == "A1":
            applicability_ok &= row["sentinel"] == applicability["A1_sentinel_enum"] and isinstance(row["alpha"], (int, float)) and not isinstance(row["alpha"], bool) and math.isfinite(row["alpha"]) and row["alpha"] > 0.0 and isinstance(row["command_duration_s"], (int, float)) and not isinstance(row["command_duration_s"], bool) and math.isfinite(row["command_duration_s"]) and row["command_duration_s"] > 0.0
        else:
            applicability_ok = False
    check("R2A05", len(matrix) == 78 and len({row["case_id"] for row in matrix}) == 78 and applicability["null_values_forbidden"] is True and applicability_ok and matrix_hash == design["fixed_matrix"]["canonical_expanded_matrix_sha256"] == schedule["expanded_matrix_canonical_sha256"], matrix_hash)
    fresh = [row for row in matrix if row["execution_family"] == "FRESH"]
    common = [row for row in matrix if row["execution_family"] == "COMMON_PROP"]
    check("R2A06", len(fresh) == 60 and len(common) == 18 and sum("A0_BOOKEND" in row["roles"] for row in matrix) == 12 and sum("G12_FRESH_REFERENCE" in row["roles"] for row in matrix) == 36 and sum("FRESH_ACQ_OBSERVATION" in row["roles"] for row in matrix) == 6)
    check("R2A07", not ({row["case_id"] for row in fresh} & {row["case_id"] for row in common}) and all(not row["g12_credit"] and not row["selector_input"] for row in common))
    generated = independent_schedule(schedule["seed"])
    check("R2A08", generated == schedule["case_ids_in_blocked_order"] and len(generated) == 78 and canonical_hash(generated) == schedule["case_ids_canonical_sha256"] and set(generated) == {row["case_id"] for row in matrix})
    bookends_ok = True
    for lane, _, _ in LANES:
        positions = [index for index, case in enumerate(generated) if f"FRESH__{lane}__" in case]
        bookends_ok &= generated[min(positions)].endswith("__A0__PRE") and generated[max(positions)].endswith("__A0__POST")
    check("R2A09", bookends_ok)

    acq = design["tracks"]["fresh_lane_acquisition_convergence"]
    identity_rule = acq["technical_repeat_identity_projection"]
    identity_acceptance = numerical["fresh_acquisition_technical_repeat_identity_rule"]
    raw_root = PROJECT_ROOT / sources["preserved_raw_inventory"]["path"]
    identity_projections = [
        audit_identity_projection(load(raw_root / basename)["event_provenance"]["acquisition_certificate_payload"])
        for basename in identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["basenames"]
    ]
    q_rule = design["quaternion_metric_contract"]
    q_sign = audit_quaternion_distance([1.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0])
    q_pi = audit_quaternion_distance([1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0])
    q_inside = audit_quaternion_distance([1.0 + 5e-13, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    q_outside = audit_quaternion_distance([1.0 + 2e-12, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    check("R2A10", acq["observation_count"] == 6 and len(acq["registered_channels_and_floors"]) == 16 and all(row["floor"] > 0 and row["unit"] for row in acq["registered_channels_and_floors"].values()) and acq["certificates"]["valid_and_unique_per_case_required"] is True and identity_rule["allowed_different_json_pointers_exact"] == identity_acceptance["allowed_different_json_pointers_exact"] == ["/case_id", "/event/run_id", "/acquisition/run_id"] and identity_acceptance["all_unlisted_pointers_keys_lengths_types_and_values_exactly_equal_required"] is True and all(row["pass"] is True for row in identity_projections) and {row["bytes"] for row in identity_projections} == {identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["projected_canonical_bytes_each"]} == {31050} and {row["sha256"] for row in identity_projections} == {identity_rule["preserved_raw_read_only_rule_sanity_anchor"]["projected_sha256_each"]} == {"29DFA8D35BBBA4E615B583B09EBB1B32144C0FE39B740898F1A0EB7ED838511C"} and q_rule["formula"] == "d_rad=4*atan2(norm(q1-s*q2),norm(q1+s*q2))" and q_rule["unit_norm_absolute_tolerance"] == 1e-12 and q_sign == {"valid": True, "distance_rad": 0.0} and q_pi["valid"] is True and math.isclose(q_pi["distance_rad"], math.pi, rel_tol=0.0, abs_tol=1e-15) and q_inside["valid"] is True and q_outside["valid"] is False)
    common_design = design["tracks"]["common_initial_state_propagation_convergence"]
    behavior = common_design["rehydrator_and_roundtrip_behavior_contract"]
    boundary = common_design["fixture_use_boundary"]
    check("R2A11", common_design["common_initial_state_fixture"]["common_initial_state_group_canonical_bytes"] == len(canonical_bytes(state_group)) == 1317 and common_design["common_initial_state_fixture"]["common_initial_state_group_sha256"] == canonical_hash(state_group) == "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444" and common_design["common_initial_state_fixture"]["common_initial_state_group_field_map"] == EXPECTED_GROUP_FIELD_MAP and common_design["comparison_channels_and_floors"] == EXPECTED_COMMON_CHANNELS and behavior["implementation_in_this_contract_package"] is False and behavior["roundtrip_verified_in_this_contract_package"] is False and "fresh deep copy" in behavior["per_case_object_isolation"] and all(value is False for key, value in boundary.items() if key != "numerical_propagation_isolation_only"))
    g04 = numerical["g04_unified_work_rule"]
    check("R2A12", g04["rule_id"] == g04["runner_rule_id_required"] == g04["validator_rule_id_required"] and g04["W_act_initial_exact"] == 0.0 and g04["sample_power_absolute_tolerance_W"] == g04["stage_power_absolute_tolerance_W"] == 1e-14 and g04["sample_power_relative_tolerance"] == g04["stage_power_relative_tolerance"] == 0.0 and g04["cumulative_max_abs_error_limit_J"] == g04["terminal_native_abs_error_limit_J"] == 1e-7 and g04["refinement_slack_J"] == 1e-15 and g04["required_report_fields"] == g04["runner_required_report_fields"] == g04["validator_required_report_fields"] == EXPECTED_G04_FIELDS and "finite_removal_present==false" in g04["finite_removal_post_pass_expression"] and "all(post_W_act_J[j]==active_terminal_W_act_J for every saved post sample j)" in g04["finite_removal_post_pass_expression"] and "all(post_generalized_force_Q_14[j,k]==0.0 for every saved post sample j and k=0..13)" in g04["finite_removal_post_pass_expression"] and g04["pass_expression"] == g04["runner_pass_expression_required"] == g04["validator_pass_expression_required"] and g04["finite_removal_post_pass_expression"] in g04["pass_expression"] and "any_finite_removal" not in g04["pass_expression"])
    comparator = numerical["total_direct_order_comparator"]
    truth = {
        "zero": audit_direct_order((0.0, 0.0, 0.0), 2e-12, 1.8, "FINE_AND_REFERENCE"),
        "exact_zero_fine": audit_direct_order((1e-5, 0.0, 0.0), 1e-10, 3.0, "ALL_THREE"),
        "regression": audit_direct_order((0.0, 1e-5, 1e-6), 1e-10, 1.8, "FINE_AND_REFERENCE"),
        "invalid": audit_direct_order((float("nan"), 1.0, 0.1), 1e-10, 1.8, "FINE_AND_REFERENCE"),
    }
    check("R2A13", comparator["rule_id"] == "B4G_R2_TOTAL_DIRECT_ERROR_RATIO_ORDER_V1" and comparator["nonfinite_JSON_numbers_forbidden"] is True and g04["empirical_order"]["comparator_rule_id"] == comparator["rule_id"] and g04["empirical_order"]["floor_resolution_scope"] == "FINE_AND_REFERENCE" and truth["zero"]["category"] == "OVERALL_FLOOR_RESOLVED" and truth["exact_zero_fine"]["CF"] == "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT" and truth["regression"]["pass"] is False and truth["invalid"]["category"] == "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA" and not has_null_leaf(truth))
    g06 = numerical["g06_energy_minus_work_rule"]
    check("R2A14", g06["active_max_abs_limit_J"] == 1e-7 and g06["midpoint_floor_resolution_scope"] == "FINE_AND_REFERENCE" and g06["midpoint_p_min"] == 1.8 and g06["rk4_floor_resolution_scope"] == "ALL_THREE" and g06["rk4_p_min"] == 3.0 and g06["floor_resolved_J"] == 1e-10)
    common_rule = numerical["common_propagation_convergence_rule"]
    check("R2A15", math.isclose(common_rule["midpoint_contraction_max"], 2.0 ** (-1.8), rel_tol=0.0, abs_tol=1e-16) and common_rule["midpoint_contraction_formula"] == "2^(-1.8)" and common_rule["midpoint_contraction_max"] < 0.3 and common_rule["midpoint_p_min"] == 1.8 and common_rule["rk4_contraction_max"] == 0.125 and common_rule["rk4_p_min"] == 3.0 and "D_FR_midpoint/(2^1.8-1)" in common_rule["finest_cross_method_rule"] and "D_FR_rk4/(2^3.0-1)" in common_rule["finest_cross_method_rule"] and common_rule["G12_credit"] is False and common_rule["selector_input"] is False and common_rule["shared_removal_credit"] is False)
    g12 = numerical["g12_reference_event_and_signed_work_preflight"]
    check("R2A16", g12["level_count"] == 18 and g12["acquisition_event_time_difference_s_max"] == g12["removal_event_time_difference_s_max"] == 0.00025 and g12["aggregate_requires_all_scientific_predicates_true"] is False and g12["aggregate_rule_contract_frozen"] is True)
    old_ratio_counterexample = 0.295
    check("R2A17", old_ratio_counterexample <= 0.3 and old_ratio_counterexample > common_rule["midpoint_contraction_max"] and math.isclose(2.0 ** (-1.8), common_rule["midpoint_contraction_max"], rel_tol=0.0, abs_tol=1e-16) and math.isclose(2.0 ** (-3.0), 0.125, rel_tol=0.0, abs_tol=0.0))
    unresolved_marker = "PEND" + "ING"
    placeholder_marker = "TO_" + "BE_"
    package_json_no_null = all(not has_null_leaf(load(path)) for path in HERE.rglob("*.json") if path.resolve() != AUDIT.resolve())
    check("R2A18", design["scientific_matrix_review"]["all_design_fields_complete"] is True and unresolved_marker not in str(design) and placeholder_marker not in str(design) and unresolved_marker not in str(numerical) and package_json_no_null and not has_null_leaf((sources, design, schedule, numerical, governance, tests, validation, manifest, matrix)))
    check("R2A19", all(governance["contract_frozen_true"].values()) and all(value is False for value in governance["required_false"].values()) and governance["negative_control_count"] == len(governance["negative_controls"]) == 46)
    check("R2A20", governance["gate_status_exact"] == "PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY" and governance["execution_readiness_status_exact"] == "HOLD_R2_PREFLIGHT_EXECUTION_NO_IMPLEMENTED_REHYDRATOR_OR_R2_SOURCE_FREEZE")
    check("R2A21", tests["status"] == "PASS_PHASE_B4G_R2_PYTEST" and tests["collected"] == governance["test_contract"]["expected_collected"] and tests["nodeid_sha256"] == governance["test_contract"]["expected_nodeid_sha256"] and tests["outcomes"] == governance["test_contract"]["required_outcome"])
    check("R2A22", validation["status"] == "PASS_R2_PREFLIGHT_CONTRACT_VALIDATION_READY_FOR_INDEPENDENT_AUDIT" and validation["score"] == {"pass": 26, "fail": 0, "total": 26, "failed": []})
    records_ok = all((PROJECT_ROOT / row["path"]).is_file() and (PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"] and sha(PROJECT_ROOT / row["path"]) == row["sha256"] for row in manifest["records"])
    record_paths = {row["path"] for row in manifest["records"]}
    check("R2A23", manifest["self_excluded"] is True and manifest["acyclic"] is True and manifest["record_count"] == len(manifest["records"]) == 17 and records_ok and MANIFEST.relative_to(PROJECT_ROOT).as_posix() not in record_paths and AUDIT.relative_to(PROJECT_ROOT).as_posix() not in record_paths)
    artifact_guard = governance["recursive_artifact_guard"]
    forbidden = set(artifact_guard["forbidden_file_suffixes"])
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
    check("R2A24", artifact_guard["validator_audit_and_pytest_must_each_enforce"] is True and not any(path.suffix.lower() in forbidden for path in package_paths if path.is_file()) and not any(path.name in forbidden_names for path in package_paths if path.is_dir()) and not any(token in module for token in forbidden_solver_tokens for module in imported_modules) and not any(token in path.name.lower() for token in forbidden_filename_substrings for path in package_paths if path.is_file()))

    failed = [row["id"] for row in checks if not row["pass"]]
    result = {
        "schema": "SIM13_V4B4G_R2_INDEPENDENT_AUDIT_V1",
        "status": "PASS_PHASE_B4G_R2_INDEPENDENT_CONTRACT_AUDIT" if not failed else "FAIL_PHASE_B4G_R2_INDEPENDENT_CONTRACT_AUDIT",
        "scope": "INDEPENDENT_CONTRACT_AUDIT_NO_VALIDATOR_IMPORT_NO_SOLVER_NO_NUMERICAL_EXECUTION",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "matrix_sha256": matrix_hash,
        "schedule_sha256": canonical_hash(generated),
        "execution_readiness_status": governance["execution_readiness_status_exact"],
        "new_preflight_executed": False,
        "full_campaign_authorized": False,
    }
    write_json(AUDIT, result)
    return result


def main() -> int:
    try:
        result = audit()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_INDEPENDENT_AUDIT_EXCEPTION", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": result["status"], "score": result["score"], "audit_sha256": sha(AUDIT)}, ensure_ascii=False))
    return 0 if result["score"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
