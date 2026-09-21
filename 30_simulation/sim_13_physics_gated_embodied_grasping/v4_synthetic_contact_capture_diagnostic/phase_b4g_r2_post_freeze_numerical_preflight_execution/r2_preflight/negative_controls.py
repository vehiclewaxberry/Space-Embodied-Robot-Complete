"""Deterministic source-only mutation controls for registered R2NC01--46.

Every mutation is routed through a production guard/evaluator. Runtime-dependent
controls only prove that the implementation hook kills a synthetic fixture;
they never claim that an R2 trajectory was executed.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np

from .evaluator import (
    COMMON_OBSERVATION_KEYS,
    COMMON_RAW_BINDING_KEYS,
    FRESH_ACQ_OBSERVATION_KEYS,
    G12_RECORD_KEYS,
    derive_fresh_acquisition_channels,
    evaluate_common_propagation_records,
    evaluate_fresh_acquisition_records,
    evaluate_fresh_technical_repeats,
    evaluate_g12_pair,
    project_fresh_acquisition_identity,
    validate_common_case_metadata,
    validate_common_propagation_campaign,
    validate_g04_signature_match,
)
from .execution_guard import (
    AuthorizationReceipt,
    ConsumedAuthorizationReceipt,
    ExecutionAuthorizationError,
    _verify_sources,
    authorized_lazy_imports,
    consume_authorization,
    create_output_root_after_authorization,
    legacy_modules_loaded,
    validate_failure_slots,
    validate_invalidation_semantics,
    validate_preserved_raw_inventory,
    validate_r1_contract_semantics,
)
from .governance import (
    FALSE_FLAG_KEYS,
    validate_a0_bookends,
    validate_global_78_registry,
    validate_governance_flags,
    validate_matrix_and_schedule,
)
from .metrics import (
    CHANNEL_WIDTHS,
    COMMON_PROP_CHANNELS,
    FRESH_ACQ_CHANNELS,
    MIDPOINT_CONTRACTION,
    evaluate_channel_triplet,
    evaluate_direct_order_triplet,
    stable_quaternion_geodesic_rad,
)
from .rehydrator import (
    COMMON_GROUP_SHA256,
    DONOR_PAYLOAD_SHA256,
    RehydratedFixture,
    RehydrationError,
    collect_mutable_ids,
    donor_immutability_guard,
    fixture_hashes,
    isolated_common_fixture,
    rehydrate_payload,
    to_payload,
)
from .schedule import MATRIX_SHA256, SCHEDULE_SHA256, expand_matrix, fresh_a1_id, generate_schedule
from .strict_json import (
    StrictJSONError,
    canonical_sha256,
    contains_null,
    file_sha256,
    load_path,
    loads,
)
from .work_energy import (
    G04_PASS_EXPRESSION,
    G04_REQUIRED_FIELDS,
    G04_RULE_ID,
    G06_LIMIT_J,
    G06_WORK_STATE_PROVENANCE,
    WorkEnergyError,
    evaluate_g04,
    evaluate_g06,
    runner_g04_signature,
)


NEGATIVE_CONTROL_IDS = (
    "R2NC01_B4G_SOURCE_FREEZE_TERMINAL_DRIFT",
    "R2NC02_B4G_INVALIDATION_NOT_ACTIVE",
    "R2NC03_PRESERVED_RAW_INVENTORY_DRIFT",
    "R2NC04_R1_CONTRACT_GATE_OR_TERMINAL_DRIFT",
    "R2NC05_DONOR_RAW_OR_PAYLOAD_HASH_DRIFT",
    "R2NC06_SINGLE_RK4_STEP_MISCLAIMED_AS_CONVERGENCE",
    "R2NC07_FRESH_ACQUISITION_EVENT_FORCED_OR_SHARED",
    "R2NC08_ACQ_NATIVE_CHANNEL_OVER_0P60_CAUCHY_STILL_PASS",
    "R2NC09_ACQ_TECHNICAL_REPEAT_NUMERIC_MISMATCH",
    "R2NC10_A0_PRE_OR_POST_MISSING_OR_NUMERIC_MISMATCH",
    "R2NC11_COMMON_AND_FRESH_CASE_ID_REUSED",
    "R2NC12_COMMON_AND_FRESH_CERTIFICATE_REUSED",
    "R2NC13_REHYDRATOR_ONE_FLOAT_CHANGED",
    "R2NC14_REHYDRATOR_SHAPE_CHANGED",
    "R2NC15_REHYDRATOR_DTYPE_CHANGED",
    "R2NC16_REHYDRATOR_NAN_OR_INFINITY_INJECTED",
    "R2NC17_REHYDRATOR_ROUNDTRIP_NOT_EXACT",
    "R2NC18_COMMON_DESCENDANT_GIVEN_G12_CREDIT",
    "R2NC19_COMMON_DESCENDANT_GIVEN_SELECTOR_INPUT",
    "R2NC20_G04_CUMULATIVE_HISTORY_REMOVED_OR_TERMINAL_CANCELLATION",
    "R2NC21_G04_NATIVE_TERMINAL_CHECK_REMOVED",
    "R2NC22_G04_EVERY_SECOND_CHECK_REMOVED",
    "R2NC23_G04_RUNNER_VALIDATOR_RULE_OR_FIELD_DIVERGENCE",
    "R2NC24_G04_SAMPLE_OR_STAGE_POWER_NOT_RECOMPUTED",
    "R2NC25_G04_POST_WORK_RESET_OR_NONZERO_POST_Q",
    "R2NC26_G04_OR_G06_EMPIRICAL_ORDER_GATE_REMOVED",
    "R2NC27_G06_THRESHOLD_RELAXED",
    "R2NC28_W_ACT_SET_EQUAL_TO_DELTA_T",
    "R2NC29_RK4_MISLABELLED_AS_MIDPOINT",
    "R2NC30_ALPHA16_OR_PROSPECTIVE_STEP_REMOVED",
    "R2NC31_BLOCKED_SCHEDULE_CASE_MISSING_EXTRA_OR_REORDERED",
    "R2NC32_G12_EVALUATION_PASS_MISREAD_AS_PREDICATE_TRUE",
    "R2NC33_G12_SIGNED_WORK_TIME_OR_FRESH_PROVENANCE_IGNORED",
    "R2NC34_R2_EXECUTION_WITHOUT_NEW_SOURCE_FREEZE",
    "R2NC35_MEMORY_OR_OWNER_OVERRIDE_ASSERTED",
    "R2NC36_PREFLIGHT_PROMOTED_TO_FULL_CAMPAIGN_PHYSICAL_OR_PRODUCTION_AUTHORITY",
    "R2NC37_COMMON_CASE_DONOR_GROUP_HASH_NOT_IDENTICAL",
    "R2NC38_COMMON_MUTABLE_OBJECT_IDENTITY_REUSED_ACROSS_CASES_OR_HASH_DRIFTED",
    "R2NC39_NULL_JSON_LEAF_OR_AMBIGUOUS_MATRIX_NOT_APPLICABLE_VALUE",
    "R2NC40_COMMON_MIDPOINT_CONTRACTION_NOT_EQUIVALENT_TO_P_MIN_1P8",
    "R2NC41_DIRECT_ORDER_ZERO_FLOOR_REGRESSION_OR_NONFINITE_BRANCH_CHANGED",
    "R2NC42_QUATERNION_SIGN_SHAPE_NORM_FORMULA_OR_BOUNDARY_CHANGED",
    "R2NC43_COMMON_STATE_GROUP_FIELD_MAP_HASH_OR_CHANNEL_FLOOR_DRIFTED",
    "R2NC44_FRESH_TECHNICAL_REPEAT_EXCLUSION_POINTER_OR_CASE_BINDING_DRIFTED",
    "R2NC45_G04_POWER_TOLERANCE_REQUIRED_FIELD_OR_POST_CARRY_EXPRESSION_DRIFTED",
    "R2NC46_CACHE_TEMP_PYC_SOLVER_FILE_OR_PHYSICS_ARTIFACT_PRESENT",
)

RUNTIME_DEPENDENT = {
    NEGATIVE_CONTROL_IDS[index - 1]
    for index in (6, 7, 8, 9, 10, 11, 12, 20, 24, 25, 28, 29, 30, 31, 32, 33, 37, 38)
}
STRUCTURAL_SIGNATURE_ONLY = {NEGATIVE_CONTROL_IDS[20], NEGATIVE_CONTROL_IDS[21]}


def _source_row(contract: dict[str, Any], source_id: str) -> dict[str, Any]:
    rows = [row for row in contract["sources"] if row["id"] == source_id]
    if len(rows) != 1:
        raise ValueError("SOURCE_ID_CARDINALITY")
    return rows[0]


def _fresh_fixture(donor: RehydratedFixture, row: dict[str, Any]) -> tuple[RehydratedFixture, dict[str, Any], str]:
    payload = deepcopy(to_payload(donor))
    payload["case_id"] = row["case_id"]
    payload["lane_id"] = row["lane_id"]
    payload["event"]["run_id"] = row["case_id"]
    payload["acquisition"]["run_id"] = row["case_id"]
    payload["event"]["method"] = row["method"]
    payload["event"]["step_s"] = row["step_s"]
    certificate = canonical_sha256(payload)
    return rehydrate_payload(payload, certificate), payload, certificate


def _zero_channel(name: str, sample_count: int) -> Any:
    width = CHANNEL_WIDTHS[name]
    row = [1.0, 0.0, 0.0, 0.0] if "quaternion" in name else [0.0] * width
    if sample_count == 1:
        return row[0] if width == 1 else row
    return [list(row) for _ in range(sample_count)] if width != 1 else [0.0] * sample_count


def _fresh_acq_records(donor: RehydratedFixture, method: str) -> list[dict[str, Any]]:
    records = []
    for step_s in (0.00025, 0.000125, 0.0000625):
        lane = next(lane for lane, lane_method, lane_step in (
            (row["lane_id"], row["method"], row["step_s"]) for row in expand_matrix()
        ) if lane_method == method and lane_step == step_s)
        row = next(row for row in expand_matrix() if row["case_id"] == fresh_a1_id(lane, 16, 10))
        fixture, payload, certificate = _fresh_fixture(donor, row)
        raw_binding = {
            "schema": "B4G_R2_FRESH_NATIVE_MOMENTUM_RAW_BINDING_V1",
            "case_id": row["case_id"],
            "sample_time_s": fixture.acquisition.acquisition_time_s,
            "total_linear_momentum_kg_m_s": [0.0, 0.0, 0.0],
            "total_angular_momentum_kg_m2_s": [0.0, 0.0, 0.0],
            "raw_relative_path": f"evidence/cases/{row['case_id']}.npz",
            "raw_bytes": 1,
            "raw_sha256": canonical_sha256({"case_id": row["case_id"], "raw": "future"}),
            "raw_sample_index": 0,
            "derivation_rule_id": "B4G_R2_NATIVE_P_H_AT_ACQUISITION_EXACT_SAMPLE_V1",
        }
        observation = {
            "schema": "B4G_R2_FRESH_ACQUISITION_OBSERVATION_V1",
            "case_id": row["case_id"], "lane_id": row["lane_id"], "method": row["method"],
            "step_s": row["step_s"], "alpha": 16.0, "command_duration_s": 0.01,
            "acquisition_time_s": fixture.acquisition.acquisition_time_s,
            "native_momentum_raw_binding": raw_binding,
            "channels": derive_fresh_acquisition_channels(fixture, raw_binding),
        }
        records.append({
            "case_id": row["case_id"], "lane_id": row["lane_id"], "method": row["method"],
            "step_s": row["step_s"], "acquisition_certificate_payload": payload,
            "acquisition_certificate_sha256": certificate, "observation_payload": observation,
            "observation_sha256": canonical_sha256(observation),
        })
    return records


def _fresh_registry_records(donor: RehydratedFixture) -> list[dict[str, Any]]:
    by_id = {row["case_id"]: row for row in expand_matrix()}
    records = []
    for case_id in generate_schedule():
        row = by_id[case_id]
        if row["execution_family"] != "FRESH":
            continue
        _, payload, certificate = _fresh_fixture(donor, row)
        if row["arm"] == "A0":
            zero_q = [0.0] * 14
            zero_w = [0.0]
            numeric = {
                "schema": "B4G_R2_A0_BOOKEND_NUMERIC_PAYLOAD_V1",
                "case_id": case_id, "lane_id": row["lane_id"], "sentinel": row["sentinel"],
                "state_payload": {
                    "time_grid_s": [0.0],
                    "service_state_29": [[0.0] * 29],
                    "target_state_13": [[0.0] * 13],
                    "generalized_force_Q_14": [zero_q],
                    "signed_W_act_J": zero_w,
                },
            }
            a0 = (numeric, canonical_sha256(numeric), zero_q, zero_w)
        else:
            a0 = ("NOT_APPLICABLE_A1",) * 4
        records.append({
            "case_id": case_id, "execution_family": row["execution_family"], "roles": row["roles"],
            "lane_id": row["lane_id"], "method": row["method"], "step_s": row["step_s"],
            "arm": row["arm"], "sentinel": row["sentinel"], "alpha": row["alpha"],
            "command_duration_s": row["command_duration_s"],
            "acquisition_certificate_payload": payload, "acquisition_certificate_sha256": certificate,
            "evidence_path": f"evidence/cases/{case_id}.json",
            "a0_numeric_payload": a0[0], "a0_numeric_payload_sha256": a0[1],
            "a0_generalized_force_Q_14": a0[2], "a0_signed_W_act_J": a0[3],
        })
    return records


def _common_records(donor: RehydratedFixture) -> list[dict[str, Any]]:
    by_id = {row["case_id"]: row for row in expand_matrix()}
    records = []
    for case_id in (case for case in generate_schedule() if case.startswith("COMMON_PROP__")):
        row = by_id[case_id]
        fixture = isolated_common_fixture(donor)
        grid = [0.0, row["command_duration_s"]]
        raw_binding = {
            "schema": "B4G_R2_COMMON_PROPAGATION_RAW_BINDING_V1",
            "case_id": case_id, "raw_relative_path": f"evidence/cases/{case_id}.npz",
            "raw_bytes": 1, "raw_sha256": canonical_sha256({"case_id": case_id, "raw": "future"}),
            "derivation_rule_id": "B4G_R2_COMMON_16_CHANNEL_EXACT_RAW_ARRAY_MAP_V1",
        }
        observation = {
            "schema": "B4G_R2_COMMON_PROPAGATION_OBSERVATION_V1", "case_id": case_id,
            "lane_id": row["lane_id"], "method": row["method"], "step_s": row["step_s"],
            "command_duration_s": row["command_duration_s"], "time_grid_s": grid,
            "raw_binding": raw_binding,
            "channels": {name: _zero_channel(name, 2) for name in COMMON_PROP_CHANNELS},
        }
        hashes = fixture_hashes(fixture)
        records.append({
            "case_id": case_id, "lane_id": row["lane_id"], "method": row["method"],
            "step_s": row["step_s"], "command_duration_s": row["command_duration_s"],
            "donor_certificate_sha256": DONOR_PAYLOAD_SHA256,
            "donor_group_sha256": COMMON_GROUP_SHA256,
            "donor_hashes_before": hashes, "donor_hashes_after": hashes, "fixture": fixture,
            "observation_payload": observation, "observation_sha256": canonical_sha256(observation),
            "evidence_path": f"evidence/cases/{case_id}.json", "g12_credit": False,
            "selector_input": False, "fresh_acquisition_credit": False,
            "shared_removal_credit": False,
        })
    return records


def _g04_inputs(*, method: str = "rk4", step_s: float = 0.00025) -> dict[str, Any]:
    stages = 4 if method == "rk4" else 2
    return {
        "time_s": [0.0, step_s],
        "command_Q_14": [[0.0] * 14, [0.0] * 14],
        "service_state_29": [[0.0] * 29, [0.0] * 29],
        "sample_power_reported_W": [0.0, 0.0],
        "stage_command_Q_14": [[0.0] * 14 for _ in range(stages)],
        "stage_service_state_29": [[0.0] * 29 for _ in range(stages)],
        "stage_power_reported_W": [0.0] * stages,
        "W_act_J": [0.0, 0.0],
        "finite_removal_present": True,
        "post_W_act_J": [0.0],
        "post_actuator_work_reset_on_removal": False,
        "post_generalized_force_Q_14": [[0.0] * 14],
    }


def _g06_inputs(
    *, method: str = "rk4", step_s: float = 0.00025,
    kinetic: list[float] | None = None, work: list[float] | None = None,
) -> dict[str, Any]:
    kinetic = [0.0, 0.0] if kinetic is None else kinetic
    work = [0.0, 0.0] if work is None else work
    if method == "rk4":
        codes = ["RK4_K1", "RK4_K2", "RK4_K3", "RK4_K4"]
        stage_time = [0.0, 0.5 * step_s, 0.5 * step_s, step_s]
    else:
        codes = ["MIDPOINT_K1", "MIDPOINT_K2"]
        stage_time = [0.0, 0.5 * step_s]
    stages = len(codes)
    return {
        "total_kinetic_energy_J": kinetic,
        "signed_W_act_J": work,
        "stage_evidence_payload": {
            "schema": "B4G_R2_G06_INDEPENDENT_STAGE_EVIDENCE_V1",
            "work_state_provenance": G06_WORK_STATE_PROVENANCE,
            "method": method, "step_s": step_s,
            "saved_time_s": [0.0, step_s], "saved_W_act_J": list(work),
            "stage_time_s": stage_time,
            "stage_command_Q_14": [[0.0] * 14 for _ in range(stages)],
            "stage_service_state_29": [[0.0] * 29 for _ in range(stages)],
            "augmented_work_state_stage_values_J": [0.0] * stages,
            "mechanical_state_stage_codes": codes,
        },
    }


def _g12_record(
    donor: RehydratedFixture, *, method: str, alpha: float, duration_s: float,
    finite: bool = True, acquisition_time_s: float | None = None,
    removal_time_s: float = 0.06, work_J: float = 0.0,
) -> dict[str, Any]:
    lane = "RK4_H_MS_0P0625" if method == "rk4" else "MIDPOINT_H_MS_0P0625"
    case_id = fresh_a1_id(lane, alpha, int(round(duration_s * 1000.0)))
    row = next(row for row in expand_matrix() if row["case_id"] == case_id)
    fixture, payload, certificate = _fresh_fixture(donor, row)
    acquisition_time_s = fixture.acquisition.acquisition_time_s if acquisition_time_s is None else acquisition_time_s
    path = f"evidence/cases/{case_id}.json"
    clearance = {
        "schema": "B4G_R2_FRESH_CLEARANCE_CERTIFICATE_V1",
        "case_id": case_id, "lane_id": lane, "method": method, "step_s": 0.0000625,
        "alpha": alpha, "command_duration_s": duration_s,
        "fresh_b3_reconstruction_sha256": certificate,
        "outcome": "FINITE_BILATERAL_REMOVAL" if finite else "NO_FINITE_REMOVAL",
        "integrity_pass": True, "finite_bilateral_removal_event": finite,
        "post_release_passed": finite, "acquisition_time_s": acquisition_time_s,
        "removal_time_s": removal_time_s, "signed_work_terminal_J": work_J,
        "evidence_path": path,
    }
    return {
        "case_id": case_id, "lane_id": lane, "method": method, "step_s": 0.0000625,
        "alpha": alpha, "command_duration_s": duration_s,
        "acquisition_certificate_payload": payload, "acquisition_certificate_sha256": certificate,
        "clearance_certificate_payload": clearance,
        "clearance_certificate_sha256": canonical_sha256(clearance), "evidence_path": path,
    }


def _governance_flags() -> dict[str, Any]:
    flags = {key: False for key in FALSE_FLAG_KEYS}
    flags.update({
        "trajectory_count": 0,
        "authorized_execution_path_status": "NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE",
        "execution_readiness_status": "HOLD_R2_NUMERICAL_PREFLIGHT_EXECUTION_NO_DIRECT_OWNER_SOURCE_AND_NO_IMPLEMENTED_AUTHORIZED_PATH",
    })
    return flags


def _artifact_tree_clean(package_root: Path) -> bool:
    forbidden_suffixes = {".npz", ".csv", ".urdf", ".step", ".stp", ".pyc", ".tmp"}
    forbidden_dirs = {"__pycache__", ".pytest_cache", "raw", "raw_cases"}
    for path in package_root.rglob("*"):
        if path.is_dir() and path.name.lower() in forbidden_dirs:
            return False
        if path.is_file() and (path.suffix.lower() in forbidden_suffixes or "solver" in path.name.lower()):
            return False
    return True


def _raises_strict(text: str) -> bool:
    try:
        loads(text)
    except StrictJSONError:
        return True
    return False


def _rehydration_rejected(payload: dict[str, Any]) -> bool:
    try:
        rehydrate_payload(payload, DONOR_PAYLOAD_SHA256)
    except (RehydrationError, StrictJSONError, ValueError):
        return True
    return False


def _kill(
    control_id: str, *, project_root: Path, package_root: Path, donor: RehydratedFixture
) -> tuple[bool, str]:
    source_contract = load_path(package_root / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json")
    payload = to_payload(donor)
    if control_id == NEGATIVE_CONTROL_IDS[0]:
        mutated = deepcopy(source_contract)
        _source_row(mutated, "b4g_active_source_freeze_terminal")["sha256"] = "0" * 64
        try:
            _verify_sources(project_root, mutated)
        except ExecutionAuthorizationError:
            return True, "production source hash guard rejected terminal drift"
        return False, "source hash guard accepted terminal drift"
    if control_id == NEGATIVE_CONTROL_IDS[1]:
        row = _source_row(source_contract, "b4g_active_invalidation")
        value = load_path(project_root / row["path"])
        value["active"] = False
        return not validate_invalidation_semantics(value), "production invalidation semantics"
    if control_id == NEGATIVE_CONTROL_IDS[2]:
        inventory = deepcopy(source_contract["preserved_raw_inventory"])
        raw_root = project_root / inventory["path"]
        files = sorted((path for path in raw_root.iterdir() if path.is_file()), key=lambda path: path.name)
        rows = [{"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)} for path in files]
        inventory["file_count"] -= 1
        return not validate_preserved_raw_inventory(inventory, rows), "production 264-file inventory validator"
    if control_id == NEGATIVE_CONTROL_IDS[3]:
        row = _source_row(source_contract, "b4g_r1_failure_closure_gate")
        gate = load_path(project_root / row["path"], allow_null=True)
        gate["b4g_scientific_gate_pass"] = True
        return not validate_r1_contract_semantics(gate), "production R1 contract-only boundary"
    if control_id == NEGATIVE_CONTROL_IDS[4]:
        mutated = deepcopy(payload)
        mutated["acquisition"]["z_plus_reduced"][0] += 1e-12
        return _rehydration_rejected(mutated), "typed donor canonical hash"
    if control_id == NEGATIVE_CONTROL_IDS[5]:
        one = _fresh_acq_records(donor, "rk4")[:1]
        result = evaluate_fresh_acquisition_records(one)
        return result["passed"] is False and "EXACT_THREE" in result["status"], result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[6]:
        records = _fresh_acq_records(donor, "rk4")
        records[1]["acquisition_certificate_payload"] = deepcopy(records[0]["acquisition_certificate_payload"])
        records[1]["acquisition_certificate_sha256"] = records[0]["acquisition_certificate_sha256"]
        result = evaluate_fresh_acquisition_records(records)
        return result["passed"] is False and "CERTIFICATE" in result["status"], result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[7]:
        records = _fresh_acq_records(donor, "midpoint")
        records[1]["observation_payload"]["channels"]["service_position_m"][0] += 1.0
        records[1]["observation_sha256"] = canonical_sha256(records[1]["observation_payload"])
        result = evaluate_fresh_acquisition_records(records)
        return result["passed"] is False and result["status"] in {
            "FRESH_ACQ_CHANNEL_DERIVATION_OR_RAW_BINDING_INVALID",
            "FRESH_ACQ_HASH_BOUND_OBSERVATION_INVALID",
        }, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[8]:
        lane = "RK4_H_MS_0P25"
        payloads: dict[int, dict[str, Any]] = {}
        for duration in (5, 10, 20):
            row = next(row for row in expand_matrix() if row["case_id"] == fresh_a1_id(lane, 16, duration))
            _, case_payload, _ = _fresh_fixture(donor, row)
            payloads[duration] = case_payload
        payloads[20]["event"]["criteria"]["time_s"] += 1e-12
        result = evaluate_fresh_technical_repeats(payloads)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[9]:
        fresh = _fresh_registry_records(donor)
        missing = [record for record in fresh if not (record["arm"] == "A0" and record["sentinel"] == "POST")]
        mismatch = deepcopy(fresh)
        target = next(record for record in mismatch if record["arm"] == "A0" and record["sentinel"] == "POST")
        target["a0_numeric_payload"]["state_payload"]["service_state_29"][0][0] = 1.0
        target["a0_numeric_payload_sha256"] = canonical_sha256(target["a0_numeric_payload"])
        a = validate_a0_bookends(missing)
        b = validate_a0_bookends(mismatch)
        return a["passed"] is False and b["passed"] is False, f"{a['status']}|{b['status']}"
    if control_id == NEGATIVE_CONTROL_IDS[10]:
        fresh, common = _fresh_registry_records(donor), _common_records(donor)
        common[0]["case_id"] = fresh[0]["case_id"]
        result = validate_global_78_registry(fresh, common)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[11]:
        fresh, common = _fresh_registry_records(donor), _common_records(donor)
        fresh[0]["acquisition_certificate_sha256"] = DONOR_PAYLOAD_SHA256
        fresh[0]["acquisition_certificate_payload"] = deepcopy(payload)
        result = validate_global_78_registry(fresh, common)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[12]:
        mutated = deepcopy(payload)
        mutated["event"]["service"]["base_position_inertial_m"][0] += 1e-12
        return _rehydration_rejected(mutated), "one-float mutation rejected"
    if control_id == NEGATIVE_CONTROL_IDS[13]:
        mutated = deepcopy(payload)
        mutated["acquisition"]["matrices"]["A"][0].pop()
        return _rehydration_rejected(mutated), "matrix shape mutation rejected"
    if control_id == NEGATIVE_CONTROL_IDS[14]:
        clone = isolated_common_fixture(donor)
        object.__setattr__(clone.acquisition, "z_plus_reduced", clone.acquisition.z_plus_reduced.astype(np.float32))
        try:
            fixture_hashes(clone)
        except RehydrationError:
            return True, "float32 typed array rejected before serialization"
        return False, "float32 typed array accepted"
    if control_id == NEGATIVE_CONTROL_IDS[15]:
        killed = all(_raises_strict(text) for text in ('{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'))
        return killed, "strict parser nonfinite constants"
    if control_id == NEGATIVE_CONTROL_IDS[16]:
        mutated = deepcopy(payload)
        del mutated["acquisition"]["matrices"]
        return _rehydration_rejected(mutated), "include-matrices roundtrip completeness"
    if control_id == NEGATIVE_CONTROL_IDS[17]:
        value = {
            "execution_family": "COMMON_PROP", "donor_group_sha256": COMMON_GROUP_SHA256,
            "donor_certificate_sha256": DONOR_PAYLOAD_SHA256, "g12_credit": True,
            "selector_input": False, "fresh_acquisition_credit": False,
            "shared_removal_credit": False,
        }
        return not validate_common_case_metadata(value), "common metadata exact schema"
    if control_id == NEGATIVE_CONTROL_IDS[18]:
        value = {
            "execution_family": "COMMON_PROP", "donor_group_sha256": COMMON_GROUP_SHA256,
            "donor_certificate_sha256": DONOR_PAYLOAD_SHA256, "g12_credit": False,
            "selector_input": True, "fresh_acquisition_credit": False,
            "shared_removal_credit": False,
        }
        return not validate_common_case_metadata(value), "common selector-credit prohibition"
    if control_id == NEGATIVE_CONTROL_IDS[19]:
        args = _g04_inputs()
        args["W_act_J"] = [0.0, 1e-6]
        report = evaluate_g04(**args)
        return report["scientific_predicate"] is False, "G04 cumulative history recomputation"
    if control_id == NEGATIVE_CONTROL_IDS[20]:
        signature = runner_g04_signature()
        signature["required_fields"].remove("terminal_native_abs_error_J")
        return not validate_g04_signature_match(signature), "independent validator native-terminal signature"
    if control_id == NEGATIVE_CONTROL_IDS[21]:
        signature = runner_g04_signature()
        signature["required_fields"].remove("terminal_every_second_abs_error_J")
        return not validate_g04_signature_match(signature), "independent validator every-second signature"
    if control_id == NEGATIVE_CONTROL_IDS[22]:
        signature = runner_g04_signature()
        signature["rule_id"] += "_MUTATED"
        return not validate_g04_signature_match(signature), "runner-versus-validator independent literal signature"
    if control_id == NEGATIVE_CONTROL_IDS[23]:
        sample = _g04_inputs(); sample["sample_power_reported_W"][1] = 2e-14
        stage = _g04_inputs(); stage["stage_power_reported_W"][0] = 2e-14
        a, b = evaluate_g04(**sample), evaluate_g04(**stage)
        return a["scientific_predicate"] is False and b["scientific_predicate"] is False, "sample and stage power independently recomputed"
    if control_id == NEGATIVE_CONTROL_IDS[24]:
        reset = _g04_inputs(); reset["post_actuator_work_reset_on_removal"] = True
        force = _g04_inputs(); force["post_generalized_force_Q_14"][0][0] = 1.0
        empty = _g04_inputs(); empty["post_W_act_J"] = []; empty["post_generalized_force_Q_14"] = []
        reset_killed = evaluate_g04(**reset)["scientific_predicate"] is False
        force_killed = evaluate_g04(**force)["scientific_predicate"] is False
        try:
            evaluate_g04(**empty)
            empty_killed = False
        except WorkEnergyError:
            empty_killed = True
        return reset_killed and force_killed and empty_killed, "reset/nonzero-Q/empty-post independent submutants"
    if control_id == NEGATIVE_CONTROL_IDS[25]:
        result = evaluate_direct_order_triplet(
            [1e-9, 2e-10, 2.1e-10], floor_J=1e-10, p_min=1.8,
            floor_scope="FINE_AND_REFERENCE",
        )
        return result["passed"] is False, "production total-order regression branch"
    if control_id == NEGATIVE_CONTROL_IDS[26]:
        exact = evaluate_g06(**_g06_inputs(kinetic=[0.0, G06_LIMIT_J]))
        over = evaluate_g06(**_g06_inputs(kinetic=[0.0, math.nextafter(G06_LIMIT_J, math.inf)]))
        return exact["scientific_predicate"] is True and over["scientific_predicate"] is False, "G06 exact 1e-7 inclusive and nextafter fail"
    if control_id == NEGATIVE_CONTROL_IDS[27]:
        shortcut = _g06_inputs(kinetic=[0.0, 1.0], work=[0.0, 1.0])
        report = evaluate_g06(**shortcut)
        return report["scientific_predicate"] is False and report["independent_work_state_provenance_pass"] is False, "method-specific stage recurrence rejects copied delta-T"
    if control_id == NEGATIVE_CONTROL_IDS[28]:
        matrix, schedule = expand_matrix(), generate_schedule()
        mutated = deepcopy(matrix)
        row = next(row for row in mutated if row["method"] == "rk4")
        row["method"] = "midpoint"
        result = validate_matrix_and_schedule(mutated, schedule)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[29]:
        matrix, schedule = expand_matrix(), generate_schedule()
        mutated = [row for row in matrix if not (row["alpha"] == 16.0 and row["step_s"] == 0.0000625)]
        result = validate_matrix_and_schedule(mutated, schedule)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[30]:
        matrix, schedule = expand_matrix(), generate_schedule()
        mutated = list(schedule); mutated[0], mutated[1] = mutated[1], mutated[0]
        result = validate_matrix_and_schedule(matrix, mutated)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[31]:
        left = _g12_record(donor, method="rk4", alpha=0.5, duration_s=0.005, finite=True)
        right = _g12_record(donor, method="midpoint", alpha=0.5, duration_s=0.005, finite=False)
        result = evaluate_g12_pair(left, right)
        killed = result["eligible"] is False and result["scientific_predicate"] is False and not result["evaluation_status"].startswith("PASS_")
        return killed, result["evaluation_status"]
    if control_id == NEGATIVE_CONTROL_IDS[32]:
        left = _g12_record(donor, method="rk4", alpha=1.0, duration_s=0.01, finite=True)
        right = _g12_record(donor, method="midpoint", alpha=1.0, duration_s=0.01, finite=True)
        shared = deepcopy(right)
        shared["acquisition_certificate_payload"] = deepcopy(left["acquisition_certificate_payload"])
        shared["acquisition_certificate_sha256"] = left["acquisition_certificate_sha256"]
        shared_result = evaluate_g12_pair(left, shared)
        time_bad = deepcopy(right)
        time_bad["clearance_certificate_payload"]["acquisition_time_s"] += 1.0
        time_bad["clearance_certificate_sha256"] = canonical_sha256(time_bad["clearance_certificate_payload"])
        time_result = evaluate_g12_pair(left, time_bad)
        work_bad = deepcopy(right)
        work_bad["clearance_certificate_payload"]["signed_work_terminal_J"] = 1.0
        work_bad["clearance_certificate_sha256"] = canonical_sha256(work_bad["clearance_certificate_payload"])
        work_result = evaluate_g12_pair(left, work_bad)
        killed = (
            shared_result["structurally_valid"] is False
            and time_result["structurally_valid"] is False
            and work_result.get("source_only_candidate_predicate") is False
            and work_result["eligible"] is False
        )
        return killed, "fresh-certificate/time/work independent G12 submutants"
    if control_id == NEGATIVE_CONTROL_IDS[33]:
        output = package_root / "NEVER_CREATED_GUARD_PROBE"
        process = subprocess.run(
            [sys.executable, "-B", "-m", "r2_preflight.execution_guard", "--output-root", str(output)],
            cwd=package_root, text=True, capture_output=True, check=False,
        )
        fake = AuthorizationReceipt("FORGED", "0" * 64, 0, "0" * 64, "0" * 64, "x", "0" * 64)
        consumed = ConsumedAuthorizationReceipt(fake, "0" * 64)
        denied = []
        for action in (
            lambda: consume_authorization(fake, package_root=package_root),
            lambda: authorized_lazy_imports(consumed, package_root=package_root),
            lambda: create_output_root_after_authorization(consumed, output),
        ):
            try:
                action(); denied.append(False)
            except ExecutionAuthorizationError:
                denied.append(True)
        killed = process.returncode == 23 and not output.exists() and not legacy_modules_loaded() and all(denied)
        return killed, "missing auth and forged receipts denied before import/mkdir"
    if control_id == NEGATIVE_CONTROL_IDS[34]:
        flags = _governance_flags(); flags["owner_execution_authorized"] = True
        return not validate_governance_flags(flags), "exact governance false-map rejects Owner assertion"
    if control_id == NEGATIVE_CONTROL_IDS[35]:
        flags = _governance_flags(); flags["production"] = True
        return not validate_governance_flags(flags), "exact governance false-map rejects production promotion"
    if control_id == NEGATIVE_CONTROL_IDS[36]:
        records = [record for record in _common_records(donor) if record["method"] == "rk4" and record["command_duration_s"] == 0.01]
        records[0]["donor_group_sha256"] = "0" * 64
        result = evaluate_common_propagation_records(records)
        return result["passed"] is False, result["status"]
    if control_id == NEGATIVE_CONTROL_IDS[37]:
        records = _common_records(donor)
        records[1]["fixture"] = records[0]["fixture"]
        records[1]["donor_hashes_before"] = records[0]["donor_hashes_before"]
        records[1]["donor_hashes_after"] = records[0]["donor_hashes_after"]
        result = validate_common_propagation_campaign(records)
        identity_killed = result["passed"] is False and "IDENTITY" in result["status"]
        clone = isolated_common_fixture(donor)
        hash_killed = False
        try:
            with donor_immutability_guard(clone):
                clone.acquisition.z_plus_reduced[0] += 1e-9
                raise RuntimeError("synthetic failure")
        except RehydrationError:
            hash_killed = True
        return identity_killed and hash_killed, f"{result['status']}|donor-finally-hash"
    if control_id == NEGATIVE_CONTROL_IDS[38]:
        matrix = expand_matrix()
        killed = _raises_strict('{"x":null}') and not contains_null(matrix) and all(
            row["alpha"] == "NOT_APPLICABLE_A0" and row["command_duration_s"] == "NOT_APPLICABLE_A0"
            for row in matrix if row["arm"] == "A0"
        )
        return killed, "strict no-null plus explicit applicability enums"
    if control_id == NEGATIVE_CONTROL_IDS[39]:
        return MIDPOINT_CONTRACTION == 2.0 ** -1.8 and MIDPOINT_CONTRACTION != 0.30, "exact 2^-1.8 contraction"
    if control_id == NEGATIVE_CONTROL_IDS[40]:
        cases = [
            evaluate_direct_order_triplet([1e-12, 2e-10, 1e-11], floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")["passed"] is False,
            evaluate_direct_order_triplet([1e-9, float("inf"), 1e-11], floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")["passed"] is False,
            evaluate_direct_order_triplet([1e-8, 0.0, 0.0], floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")["passed"] is True,
            evaluate_direct_order_triplet([1e-12, 1e-12, 2e-10], floor_J=1e-10, p_min=1.8, floor_scope="ALL_THREE")["passed"] is False,
        ]
        return all(cases), "total-order truth-table branches"
    if control_id == NEGATIVE_CONTROL_IDS[41]:
        sign = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0])
        shape = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
        inside_value = math.nextafter(1.0 + 1e-12, 1.0)
        outside_value = math.nextafter(1.0 + 1e-12, math.inf)
        inside = stable_quaternion_geodesic_rad([inside_value, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
        outside = stable_quaternion_geodesic_rad([outside_value, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
        nontrivial = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0])
        killed = sign["distance_rad"] == 0.0 and shape["valid"] is False and inside["valid"] is True and outside["valid"] is False and math.isclose(nontrivial["distance_rad"], math.pi / 2.0, abs_tol=1e-15)
        return killed, "quaternion sign/shape/norm-boundary/nontrivial stable formula"
    if control_id == NEGATIVE_CONTROL_IDS[42]:
        common_hash = "73090EBF1735D259BA84E7617D1978C3C6E910445E7EBE3A15BDDC2987E9103B"
        fresh_hash = "6E93A390D5DD1A6838A1217A3B262260DC87E995D20932515CB9F66986299BC9"
        mutated = deepcopy(COMMON_PROP_CHANNELS); mutated["total_kinetic_energy_J"]["floor"] *= 2.0
        killed = fixture_hashes(donor)["group_sha256"] == COMMON_GROUP_SHA256 and canonical_sha256(COMMON_PROP_CHANNELS) == common_hash and canonical_sha256(FRESH_ACQ_CHANNELS) == fresh_hash and canonical_sha256(mutated) != common_hash
        return killed, "common field-map group hash and separate channel-map hashes"
    if control_id == NEGATIVE_CONTROL_IDS[43]:
        extra = deepcopy(payload); extra["unexpected"] = 1
        missing = deepcopy(payload); del missing["acquisition"]["run_id"]
        wrong = deepcopy(payload); wrong["event"]["run_id"] = 7
        valid = project_fresh_acquisition_identity(payload)["status"] == "PASS_IDENTITY_PROJECTION"
        killed = valid and all(project_fresh_acquisition_identity(value)["status"] == "FAIL_IDENTITY_PROJECTION_SCHEMA" for value in (extra, missing, wrong))
        return killed, "three exact exclusion pointers and case-bound string types"
    if control_id == NEGATIVE_CONTROL_IDS[44]:
        signature = runner_g04_signature()
        fields_hash = canonical_sha256(signature["required_fields"])
        expression_hash = canonical_sha256(signature["pass_expression"])
        exact = _g04_inputs(); exact["sample_power_reported_W"][1] = 1e-14
        over = _g04_inputs(); over["sample_power_reported_W"][1] = math.nextafter(1e-14, math.inf)
        killed = (
            validate_g04_signature_match(signature)
            and fields_hash == "D4A33853CCC0D45CE894B37F94F56CF6526F9B8D2E7BF59CCCE4FFDD8D076C0F"
            and expression_hash == "67547F8BF742182E9A8DB91C23BD654A52EA64FA3DCDA10712C8978ECC4B753C"
            and evaluate_g04(**exact)["scientific_predicate"] is True
            and evaluate_g04(**over)["scientific_predicate"] is False
        )
        return killed, "G04 fields/expression fingerprints and 1e-14 inclusive boundary"
    if control_id == NEGATIVE_CONTROL_IDS[45]:
        return _artifact_tree_clean(package_root), "recursive forbidden-artifact inventory"
    raise KeyError(control_id)


def _implementation_binding(package_root: Path) -> tuple[list[dict[str, Any]], str]:
    paths = [
        "r2_preflight/negative_controls.py", "r2_preflight/execution_guard.py",
        "r2_preflight/governance.py", "r2_preflight/evaluator.py",
        "r2_preflight/rehydrator.py", "r2_preflight/metrics.py",
        "r2_preflight/work_energy.py", "r2_preflight/schedule.py",
        "r2_preflight/strict_json.py",
    ]
    rows = []
    for relative in paths:
        path = package_root / relative
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return rows, canonical_sha256(rows)


def run_negative_control(
    control_id: str, *, project_root: Path, package_root: Path, donor: RehydratedFixture
) -> dict[str, Any]:
    if control_id not in NEGATIVE_CONTROL_IDS:
        raise KeyError(control_id)
    _, implementation_sha256 = _implementation_binding(package_root)
    try:
        killed, witness = _kill(
            control_id, project_root=project_root, package_root=package_root, donor=donor
        )
    except Exception as exc:  # fail closed and publish deterministic exception class
        killed, witness = False, f"UNEXPECTED_{type(exc).__name__}"
    if control_id in STRUCTURAL_SIGNATURE_ONLY:
        status = "STRUCTURAL_SOURCE_SIGNATURE_KILLED" if killed else "SOURCE_ONLY_MUTATION_SURVIVED"
    elif control_id in RUNTIME_DEPENDENT:
        status = "SOURCE_ONLY_MUTATION_KILLED_RUNTIME_NOT_EVALUATED" if killed else "SOURCE_ONLY_MUTATION_SURVIVED"
    else:
        status = "SOURCE_ONLY_MUTATION_KILLED" if killed else "SOURCE_ONLY_MUTATION_SURVIVED"
    return {
        "id": control_id,
        "status": status,
        "implemented": True,
        "source_only_executed": True,
        "killed": bool(killed),
        "r2_runtime_trajectory_evaluated": False,
        "fixture_class": "SOURCE_ONLY_SYNTHETIC_MUTATION",
        "witness": witness,
        "implementation_sha256": implementation_sha256,
    }


def run_all_negative_controls(
    *, project_root: Path, package_root: Path, donor: RehydratedFixture
) -> list[dict[str, Any]]:
    return [
        run_negative_control(
            control_id, project_root=project_root, package_root=package_root, donor=donor
        )
        for control_id in NEGATIVE_CONTROL_IDS
    ]


def build_negative_control_evidence(
    *, project_root: Path, package_root: Path, donor: RehydratedFixture,
    source_inventory_sha256: str,
) -> dict[str, Any]:
    """Deterministically execute all source-only mutations and build evidence."""

    controls = run_all_negative_controls(
        project_root=project_root, package_root=package_root, donor=donor
    )
    implementation_rows, implementation_sha256 = _implementation_binding(package_root)
    killed_count = sum(control["killed"] is True for control in controls)
    return {
        "schema": "SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1",
        "scope": "SOURCE_ONLY_SYNTHETIC_MUTATION_EXECUTION_NO_R2_TRAJECTORIES",
        "registered_count": len(NEGATIVE_CONTROL_IDS),
        "implemented_count": sum(control["implemented"] is True for control in controls),
        "source_only_executed_count": sum(control["source_only_executed"] is True for control in controls),
        "killed_count": killed_count,
        "source_only_negative_controls_implemented": all(control["implemented"] is True for control in controls),
        "source_only_negative_controls_executed": all(control["source_only_executed"] is True for control in controls),
        "source_only_negative_controls_killed": killed_count == len(NEGATIVE_CONTROL_IDS),
        "r2_execution_negative_controls_executed": False,
        "r2_numerical_preflight_executed": False,
        "r2_runtime_trajectory_evaluated": False,
        "trajectory_count": 0,
        "source_inventory_sha256": source_inventory_sha256,
        "implementation_files": implementation_rows,
        "implementation_sha256": implementation_sha256,
        "controls": controls,
    }


__all__ = [
    "NEGATIVE_CONTROL_IDS", "RUNTIME_DEPENDENT", "STRUCTURAL_SIGNATURE_ONLY",
    "build_negative_control_evidence", "run_all_negative_controls", "run_negative_control",
]
