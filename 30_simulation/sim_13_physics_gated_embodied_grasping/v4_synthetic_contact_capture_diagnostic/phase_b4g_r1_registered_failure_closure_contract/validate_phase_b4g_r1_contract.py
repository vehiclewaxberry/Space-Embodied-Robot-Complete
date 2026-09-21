from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"
B4G = HERE.parent / "phase_b4g_post_freeze_synthetic_jaw_retraction_execution"

SOURCE_BINDINGS = CONTRACTS / "PHASE_B4G_R1_SOURCE_BINDINGS_V1.json"
CLOSURE_CONTRACT = CONTRACTS / "PHASE_B4G_R1_FAILURE_CLOSURE_CONTRACT_V1.json"
TEST_RESULT = RESULTS / "SIM13_V4B4G_R1_TEST_RESULT_V1.json"
RAW_RECOMPUTATION = EVIDENCE / "SIM13_V4B4G_R1_RAW_RECOMPUTATION_V1.json"
VALIDATION = RESULTS / "SIM13_V4B4G_R1_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B4G_R1_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"

STALE_B4G_FINALS = (
    "results/SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
    "results/SIM13_V4B4G_AUDITED_GATE_V1.json",
    "evidence/SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json",
    "results/SIM13_V4B4G_PREAUDIT_GATE_V1.json",
    "evidence/SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json",
    "evidence/SIM13_V4B4G_EXECUTION_VALIDATION_V1.json",
    "evidence/SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
    "evidence/SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json",
    "results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
)

LOCAL_SOURCE_PATHS = (
    "README.md",
    "pytest.ini",
    "run_phase_b4g_r1_contract_closure.py",
    "validate_phase_b4g_r1_contract.py",
    "independent_audit_phase_b4g_r1_contract.py",
    "contracts/PHASE_B4G_R1_SOURCE_BINDINGS_V1.json",
    "contracts/PHASE_B4G_R1_FAILURE_CLOSURE_CONTRACT_V1.json",
    "tests/conftest.py",
    "tests/test_failure_closure.py",
    "tests/test_governance_and_independence.py",
)


class ValidationError(RuntimeError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root is not an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def record(path: Path, role: str, base: Path = PROJECT_ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_bound_sources(bindings: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for declared in bindings["sources"]:
        path = PROJECT_ROOT / declared["path"]
        exists = path.is_file() and not path.is_symlink()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256_file(path) if exists else None
        passed = bool(
            exists
            and actual_bytes == declared["bytes"]
            and actual_sha == declared["sha256"]
        )
        rows.append(
            {
                "id": declared["id"],
                "path": declared["path"],
                "declared_bytes": declared["bytes"],
                "actual_bytes": actual_bytes,
                "declared_sha256": declared["sha256"],
                "actual_sha256": actual_sha,
                "pass": passed,
            }
        )
    return {"pass": all(row["pass"] for row in rows), "records": rows}


def recompute_raw_inventory(bindings: dict[str, Any]) -> dict[str, Any]:
    spec = bindings["raw_case_inventory"]
    raw_root = PROJECT_ROOT / spec["path"]
    if not raw_root.is_dir() or raw_root.is_symlink():
        raise ValidationError("raw root missing or linked")
    files = sorted((path for path in raw_root.iterdir() if path.is_file()), key=lambda path: path.name)
    if any(path.is_symlink() for path in files):
        raise ValidationError("linked raw evidence is forbidden")
    records = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in files
    ]
    return {
        "raw_root": spec["path"],
        "json_count": sum(path.suffix == ".json" for path in files),
        "npz_count": sum(path.suffix == ".npz" for path in files),
        "file_count": len(files),
        "canonical_sha256": canonical_sha256(records),
        "expected_canonical_sha256": spec["canonical_sha256"],
        "pass": bool(
            len(files) == spec["expected_file_count"]
            and sum(path.suffix == ".json" for path in files) == spec["expected_json_count"]
            and sum(path.suffix == ".npz" for path in files) == spec["expected_npz_count"]
            and canonical_sha256(records) == spec["canonical_sha256"]
        ),
    }


def _g06_gate(metadata: dict[str, Any]) -> dict[str, Any]:
    matches = [
        gate
        for gate in metadata["gate_records"]
        if gate["gate_id"] == "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"
    ]
    if len(matches) != 1:
        raise ValidationError(f"G06 record cardinality: {metadata.get('case_id')}")
    return matches[0]


def _read_npz_case(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {
        "time_s",
        "total_kinetic_energy_J",
        "signed_W_act_J",
        "energy_minus_work_residual_J",
        "command_Q_14",
        "service_state_29",
    }
    if not required.issubset(arrays):
        raise ValidationError(f"NPZ lacks required arrays: {path.name}")
    time = np.asarray(arrays["time_s"], dtype=np.float64)
    kinetic = np.asarray(arrays["total_kinetic_energy_J"], dtype=np.float64)
    work = np.asarray(arrays["signed_W_act_J"], dtype=np.float64)
    stored = np.asarray(arrays["energy_minus_work_residual_J"], dtype=np.float64)
    if not (time.ndim == kinetic.ndim == work.ndim == stored.ndim == 1):
        raise ValidationError(f"NPZ active arrays are not vectors: {path.name}")
    if not (len(time) == len(kinetic) == len(work) == len(stored)) or len(time) == 0:
        raise ValidationError(f"NPZ active vectors have inconsistent lengths: {path.name}")
    if not all(np.all(np.isfinite(array)) for array in (time, kinetic, work, stored)):
        raise ValidationError(f"NPZ non-finite active evidence: {path.name}")

    recomputed = (kinetic - kinetic[0]) - (work - work[0])
    q = np.asarray(arrays["command_Q_14"], dtype=np.float64)
    service = np.asarray(arrays["service_state_29"], dtype=np.float64)
    if q.shape != (len(time), 14) or service.shape != (len(time), 29):
        raise ValidationError(f"NPZ command/state shape mismatch: {path.name}")
    power = np.sum(q[:, 12:14] * service[:, 27:29], axis=1)
    cumulative = np.concatenate(
        (np.asarray([0.0]), np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time)))
    )
    return {
        "recomputed_g06_max_J": float(np.max(np.abs(recomputed))),
        "stored_g06_max_J": float(np.max(np.abs(stored))),
        "stored_recompute_max_abs_difference_J": float(np.max(np.abs(stored - recomputed))),
        "terminal_signed_work_J": float(work[-1] - work[0]),
        "cumulative_work_max_abs_difference_J": float(np.max(np.abs(cumulative - (work - work[0])))),
    }


def analyze_preserved_raw(bindings: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    schedule_contract = load_json(B4G / "contracts/PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    schedule_evidence = load_json(B4G / "evidence/SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json")
    slots = schedule_contract["slots"]
    if schedule_contract != schedule_evidence:
        raise ValidationError("contract/evidence schedule semantic divergence")
    if canonical_sha256(slots) != schedule_contract["slots_sha256"]:
        raise ValidationError("schedule embedded hash mismatch")

    raw_root = B4G / "evidence/raw_cases"
    metadata_by_slot: dict[int, dict[str, Any]] = {}
    case_numeric: dict[tuple[str, float, float], dict[str, Any]] = {}
    status_counts: dict[str, int] = {}
    failure_pairs: list[dict[str, Any]] = []
    failed_slots_from_numeric: list[int] = []
    a2_without_npz = 0
    max_stored_recompute_difference = 0.0
    max_failed_stored_recompute_difference = 0.0

    for index, slot in enumerate(slots):
        candidates = sorted(raw_root.glob(f"{index:03d}__*.json"))
        if len(candidates) != 1:
            raise ValidationError(f"slot {index} JSON cardinality is {len(candidates)}")
        json_path = candidates[0]
        metadata = load_json(json_path)
        if (
            metadata.get("slot_index") != index
            or metadata.get("case_id") != slot["case_id"]
            or metadata.get("registered_slot") != slot
        ):
            raise ValidationError(f"slot {index} metadata/schedule mismatch")
        source_hashes = metadata.get("source_hashes", {})
        if source_hashes.get("registered_slots_sha256") != schedule_contract["slots_sha256"]:
            raise ValidationError(f"slot {index} schedule hash binding mismatch")
        if (
            source_hashes.get("expected_execution_source_freeze_terminal_sha256")
            != "B22C4D5B4C0E15FF58484D252A2316E6B42458423079E2324D6455CC09EF3464"
        ):
            raise ValidationError(f"slot {index} source-freeze binding mismatch")

        status = metadata["execution_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        npz_path = json_path.with_suffix(".npz")
        metadata_by_slot[index] = metadata
        if status == "NOT_EVALUATED_NO_A1_SUCCESS":
            if slot["arm"] != "A2" or npz_path.exists():
                raise ValidationError(f"slot {index} invalid A2 non-evaluation shape")
            a2_without_npz += 1
            if source_hashes.get("a2_selection_ledger_sha256") != "1246CEC1D03EA0BF6960B0625FABD01ADA2127FF9EAD1ED66648D12B261D0CE7":
                raise ValidationError(f"slot {index} A2 ledger binding mismatch")
            if any(gate.get("evaluation_status") != "NOT_APPLICABLE" for gate in metadata["gate_records"]):
                raise ValidationError(f"slot {index} A2 gate is not NOT_APPLICABLE")
            continue
        if status != "EXECUTED_FRESH_REGISTERED_SLOT" or not npz_path.is_file():
            raise ValidationError(f"slot {index} execution status/NPZ mismatch")
        if (
            metadata.get("npz_bytes") != npz_path.stat().st_size
            or metadata.get("npz_sha256") != sha256_file(npz_path)
        ):
            raise ValidationError(f"slot {index} NPZ binding mismatch")

        numeric = _read_npz_case(npz_path)
        max_stored_recompute_difference = max(
            max_stored_recompute_difference,
            numeric["stored_recompute_max_abs_difference_J"],
        )
        gate = _g06_gate(metadata)
        if abs(gate["detail"]["active_max_residual_J"] - numeric["stored_g06_max_J"]) > 1e-18:
            raise ValidationError(f"slot {index} G06 JSON/NPZ mismatch")
        if numeric["recomputed_g06_max_J"] > contract["g06_failure_closure"]["threshold_J"]:
            failed_slots_from_numeric.append(index)
            max_failed_stored_recompute_difference = max(
                max_failed_stored_recompute_difference,
                numeric["stored_recompute_max_abs_difference_J"],
            )
        for gate_row in metadata["gate_records"]:
            if gate_row["evaluation_status"] == "FAIL":
                failure_pairs.append({"slot_index": index, "gate_id": gate_row["gate_id"]})
        if slot["arm"] == "A1":
            case_numeric[(slot["lane_id"], float(slot["alpha"]), float(slot["command_duration_s"]))] = {
                **numeric,
                "slot_index": index,
                "metadata": metadata,
            }

    g06 = contract["g06_failure_closure"]
    alpha16_rows: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    for duration in (0.005, 0.01, 0.02):
        coarse = case_numeric[("MIDPOINT_COARSE", 16.0, duration)]["recomputed_g06_max_J"]
        fine = case_numeric[("MIDPOINT_FINE", 16.0, duration)]["recomputed_g06_max_J"]
        reference = case_numeric[("MIDPOINT_REFERENCE", 16.0, duration)]["recomputed_g06_max_J"]
        alpha16_rows.append(
            {
                "command_duration_s": duration,
                "MIDPOINT_COARSE_J": coarse,
                "MIDPOINT_FINE_J": fine,
                "MIDPOINT_REFERENCE_J": reference,
            }
        )
        orders.append(
            {
                "command_duration_s": duration,
                "coarse_to_fine": math.log2(coarse / fine),
                "fine_to_reference": math.log2(fine / reference),
            }
        )

    order_values = [value for row in orders for key, value in row.items() if key != "command_duration_s"]
    fine_cumulative = [
        case_numeric[("MIDPOINT_FINE", 16.0, duration)]["cumulative_work_max_abs_difference_J"]
        for duration in (0.005, 0.01, 0.02)
    ]

    ledger = load_json(B4G / "evidence/SIM13_V4B4G_A2_SELECTION_LEDGER_V1.json")
    ledger_by_level = {
        row["detail"]["level_id"]: row for row in ledger["cross_reference_gate_records_18"]
    }
    paired_rows: list[dict[str, Any]] = []
    unpaired_count = 0
    for level_id, ledger_row in ledger_by_level.items():
        detail = ledger_row["detail"]
        alpha = float(detail["alpha"])
        duration = float(detail["T_cmd_s"])
        rk4 = case_numeric[("RK4_REFERENCE", alpha, duration)]
        midpoint = case_numeric[("MIDPOINT_REFERENCE", alpha, duration)]
        rk4_meta = rk4["metadata"]
        midpoint_meta = midpoint["metadata"]
        rk4_finite = bool(
            rk4_meta["responses"]["finite_removal_event"]
            and rk4_meta["responses"]["post_release_passed"]
        )
        midpoint_finite = bool(
            midpoint_meta["responses"]["finite_removal_event"]
            and midpoint_meta["responses"]["post_release_passed"]
        )
        if not (rk4_finite and midpoint_finite):
            unpaired_count += 1
            continue
        acquisition_delta = abs(
            rk4_meta["acquisition"]["acquisition_time_s"]
            - midpoint_meta["acquisition"]["acquisition_time_s"]
        )
        removal_delta = abs(
            rk4_meta["responses"]["removal_time_s"]
            - midpoint_meta["responses"]["removal_time_s"]
        )
        work_delta = abs(rk4["terminal_signed_work_J"] - midpoint["terminal_signed_work_J"])
        work_tolerance = max(
            1e-10,
            0.001 * max(abs(rk4["terminal_signed_work_J"]), abs(midpoint["terminal_signed_work_J"])),
        )
        provenance_pass = bool(
            rk4_meta.get("fresh_b3_reconstruction") is True
            and midpoint_meta.get("fresh_b3_reconstruction") is True
            and rk4_meta.get("acquisition_certificate_sha256")
            and midpoint_meta.get("acquisition_certificate_sha256")
        )
        predicate = bool(
            acquisition_delta <= 0.00025
            and removal_delta <= 0.00025
            and work_delta <= work_tolerance
            and provenance_pass
        )
        paired_rows.append(
            {
                "level_id": level_id,
                "acquisition_time_difference_s": acquisition_delta,
                "removal_time_difference_s": removal_delta,
                "signed_work_difference_J": work_delta,
                "signed_work_tolerance_J": work_tolerance,
                "signed_work_exceedance_factor": work_delta / work_tolerance,
                "scientific_predicate": predicate,
            }
        )

    ratios = [row["signed_work_exceedance_factor"] for row in paired_rows]
    substantive = sum(row["removal_time_difference_s"] > 0.00025 + 1e-15 for row in paired_rows)
    boundary = sum(
        row["removal_time_difference_s"] > 0.00025
        and abs(row["removal_time_difference_s"] - 0.00025) <= 1e-15
        for row in paired_rows
    )

    run_spec = load_json(B4G / "contracts/PHASE_B4G_RUN_SPEC_V1.json")
    original_validator_text = (B4G / "b4g_validation/validator.py").read_text(encoding="utf-8")
    quadrature_text = json.dumps(run_spec["work_and_ledger_audit"], sort_keys=True)
    original_finals_absent = [relative for relative in STALE_B4G_FINALS if not (B4G / relative).exists()]

    return {
        "schema": "SIM13_V4B4G_R1_RAW_RECOMPUTATION_V1",
        "scope": "READ_ONLY_RECOMPUTATION_OF_PRESERVED_FAILED_B4G_RAW_EVIDENCE",
        "no_solver_or_campaign_executed": True,
        "schedule": {
            "slot_count": len(slots),
            "slots_sha256": schedule_contract["slots_sha256"],
            "contract_and_evidence_semantically_equal": True,
        },
        "raw_execution": {
            "status_counts": status_counts,
            "a2_metadata_without_npz_count": a2_without_npz,
            "all_executed_max_stored_vs_T_minus_W_recompute_difference_J": max_stored_recompute_difference,
            "failed_cases_max_stored_vs_T_minus_W_recompute_difference_J": max_failed_stored_recompute_difference,
            "numeric_failed_slots": sorted(failed_slots_from_numeric),
            "metadata_failure_pairs": sorted(failure_pairs, key=lambda row: (row["slot_index"], row["gate_id"])),
        },
        "g06": {
            "threshold_J": g06["threshold_J"],
            "alpha16_midpoint_residuals": alpha16_rows,
            "empirical_orders": orders,
            "empirical_order_exact_min": min(order_values),
            "empirical_order_exact_max": max(order_values),
            "mechanism_classification": g06["mechanism_ruling"]["classification"],
        },
        "g04_divergence": {
            "run_spec_has_terminal_quadrature_acceptance": "quadrature_acceptance" in run_spec["work_and_ledger_audit"],
            "run_spec_mentions_cumulative_work_error": "cumulative_work_error" in quadrature_text,
            "validator_requires_cumulative_work_error": "cumulative_work_error <= 1.0e-7" in original_validator_text,
            "midpoint_fine_alpha16_worst_cumulative_discrepancy_J": max(fine_cumulative),
            "midpoint_fine_alpha16_threshold_headroom_J": 1e-7 - max(fine_cumulative),
        },
        "g12": {
            "paired_finite_count": len(paired_rows),
            "unpaired_count": unpaired_count,
            "paired_scientific_predicate_false_count": sum(not row["scientific_predicate"] for row in paired_rows),
            "signed_work_exceedance_factor_min": min(ratios),
            "signed_work_exceedance_factor_max": max(ratios),
            "removal_time_substantive_exceedance_count": substantive,
            "removal_time_binary_boundary_case_count": boundary,
            "eligible_level_count": sum(row["scientific_predicate"] for row in paired_rows),
            "selected_parent_level": ledger["selected_parent_level"],
            "paired_rows": sorted(paired_rows, key=lambda row: row["level_id"]),
        },
        "original_credit": {
            "invalidation_active": load_json(B4G / "results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json")["active"],
            "supersession_active": load_json(B4G / "results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json")["active"],
            "replacement_campaign_summary": load_json(B4G / "results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json")["replacement_campaign_summary"],
            "formal_final_artifacts_absent_count": len(original_finals_absent),
            "formal_final_artifacts_expected_absent_count": len(STALE_B4G_FINALS),
        },
    }


def validate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bindings = load_json(SOURCE_BINDINGS)
    contract = load_json(CLOSURE_CONTRACT)
    test_result = load_json(TEST_RESULT)
    source_verification = verify_bound_sources(bindings)
    inventory = recompute_raw_inventory(bindings)
    raw = analyze_preserved_raw(bindings, contract)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "pass": bool(condition), "detail": detail})

    check("R1V01", bindings["schema"] == "SIM13_V4B4G_R1_SOURCE_BINDINGS_V1")
    check("R1V02", contract["schema"] == "SIM13_V4B4G_R1_FAILURE_CLOSURE_CONTRACT_V1")
    check("R1V03", source_verification["pass"], source_verification)
    check("R1V04", inventory["pass"], inventory)
    check(
        "R1V05",
        raw["schedule"] == {
            "slot_count": 144,
            "slots_sha256": bindings["registered_schedule"]["slots_sha256"],
            "contract_and_evidence_semantically_equal": True,
        },
        raw["schedule"],
    )
    check(
        "R1V06",
        raw["raw_execution"]["status_counts"]
        == {"EXECUTED_FRESH_REGISTERED_SLOT": 120, "NOT_EVALUATED_NO_A1_SUCCESS": 24}
        and raw["raw_execution"]["a2_metadata_without_npz_count"] == 24,
        raw["raw_execution"]["status_counts"],
    )
    check(
        "R1V07",
        raw["raw_execution"]["numeric_failed_slots"] == [82, 84, 88]
        and raw["raw_execution"]["metadata_failure_pairs"]
        == [
            {"slot_index": 82, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
            {"slot_index": 84, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
            {"slot_index": 88, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
        ],
        raw["raw_execution"],
    )
    check(
        "R1V08",
        raw["raw_execution"]["failed_cases_max_stored_vs_T_minus_W_recompute_difference_J"]
        <= contract["g06_failure_closure"]["failed_case_stored_array_crosscheck_abs_tolerance_J"]
        and raw["raw_execution"]["all_executed_max_stored_vs_T_minus_W_recompute_difference_J"]
        <= contract["g06_failure_closure"]["all_executed_case_stored_array_crosscheck_abs_tolerance_J"],
        {
            "failed_cases_J": raw["raw_execution"]["failed_cases_max_stored_vs_T_minus_W_recompute_difference_J"],
            "all_executed_J": raw["raw_execution"]["all_executed_max_stored_vs_T_minus_W_recompute_difference_J"],
        },
    )
    expected_failures = {row["slot_index"]: row for row in contract["g06_failure_closure"]["failures"]}
    residual_rows = {
        int(next(
            case["slot_index"]
            for case in contract["g06_failure_closure"]["failures"]
            if case["command_duration_s"] == row["command_duration_s"]
        )): row
        for row in raw["g06"]["alpha16_midpoint_residuals"]
        if row["MIDPOINT_COARSE_J"] > contract["g06_failure_closure"]["threshold_J"]
    }
    check(
        "R1V09",
        set(residual_rows) == set(expected_failures)
        and all(
            abs(residual_rows[slot]["MIDPOINT_COARSE_J"] - expected_failures[slot]["independent_recomputed_max_residual_J"]) <= 1e-18
            for slot in expected_failures
        ),
        residual_rows,
    )
    expected_orders = contract["g06_failure_closure"]["midpoint_alpha16_empirical_orders"]
    check(
        "R1V10",
        abs(raw["g06"]["empirical_order_exact_min"] - expected_orders["exact_min"]) <= 1e-12
        and abs(raw["g06"]["empirical_order_exact_max"] - expected_orders["exact_max"]) <= 1e-12,
        raw["g06"]["empirical_orders"],
    )
    check(
        "R1V11",
        raw["g04_divergence"]["run_spec_has_terminal_quadrature_acceptance"]
        and not raw["g04_divergence"]["run_spec_mentions_cumulative_work_error"]
        and raw["g04_divergence"]["validator_requires_cumulative_work_error"]
        and contract["g04_runner_validator_divergence"]["silent_deletion_of_validator_check_authorized"] is False,
        raw["g04_divergence"],
    )
    g12_expected = contract["g12_and_a2_ruling"]
    check(
        "R1V12",
        raw["g12"]["paired_finite_count"] == g12_expected["paired_finite_reference_levels"]
        and raw["g12"]["paired_scientific_predicate_false_count"] == g12_expected["paired_finite_scientific_predicate_false"]
        and raw["g12"]["unpaired_count"] == g12_expected["unpaired_levels_not_applicable"]
        and raw["g12"]["eligible_level_count"] == 0
        and raw["g12"]["selected_parent_level"] is None,
        raw["g12"],
    )
    check(
        "R1V13",
        abs(raw["g12"]["signed_work_exceedance_factor_min"] - g12_expected["signed_work_exceedance_factor_min"]) <= 1e-9
        and abs(raw["g12"]["signed_work_exceedance_factor_max"] - g12_expected["signed_work_exceedance_factor_max"]) <= 1e-9
        and raw["g12"]["removal_time_substantive_exceedance_count"] == 2
        and raw["g12"]["removal_time_binary_boundary_case_count"] == 1,
        raw["g12"],
    )
    check(
        "R1V14",
        raw["original_credit"] == {
            "invalidation_active": True,
            "supersession_active": True,
            "replacement_campaign_summary": None,
            "formal_final_artifacts_absent_count": 9,
            "formal_final_artifacts_expected_absent_count": 9,
        },
        raw["original_credit"],
    )
    check("R1V15", all(value is False for value in contract["required_false"].values()))
    check(
        "R1V16",
        contract["prospective_remediation"]["classification"] == "PLANNED_NOT_AUTHORIZED"
        and contract["prospective_remediation"]["new_campaign_authorized"] is False
        and len(contract["prospective_remediation"]["forbidden_shortcuts"]) == 9,
    )
    check(
        "R1V17",
        contract["formal_sim13_v2_state_unchanged"]
        == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]},
    )
    check(
        "R1V18",
        contract["memory_record"]
        == {
            "memory_gate_applicable": False,
            "memory_gate_passed": False,
            "owner_override_used": False,
            "classification": "BOUNDED_DIAGNOSTIC_CONTRACT_ONLY",
        },
    )
    check(
        "R1V19",
        test_result.get("status") == "PASS_PHASE_B4G_R1_PYTEST"
        and test_result.get("collected") == contract["test_contract"]["expected_collected"]
        and test_result.get("nodeid_sha256") == contract["test_contract"]["expected_nodeid_sha256"]
        and test_result.get("outcomes") == contract["test_contract"]["required_outcome"],
        test_result,
    )
    check("R1V20", not any(path.suffix.lower() == ".urdf" for path in HERE.rglob("*")))

    failed = [row["id"] for row in checks if not row["pass"]]
    raw["source_verification"] = source_verification
    raw["raw_inventory"] = inventory
    atomic_json(RAW_RECOMPUTATION, raw)

    validation = {
        "schema": "SIM13_V4B4G_R1_VALIDATION_V1",
        "status": "PASS_FAILURE_CLOSURE_VALIDATION_PENDING_INDEPENDENT_AUDIT" if not failed else "FAIL_FAILURE_CLOSURE_VALIDATION",
        "scope": "CONTRACT_AND_PRESERVED_RAW_RECOMPUTATION_ONLY_NO_NEW_CAMPAIGN",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "raw_recomputation": record(RAW_RECOMPUTATION, "B4G_R1_RAW_RECOMPUTATION"),
        "original_b4g_final_credit": False,
        "new_campaign_executed": False,
        "scientific_gate_pass": False,
    }
    atomic_json(VALIDATION, validation)

    local_records = [record(HERE / relative, "B4G_R1_LOCAL_SOURCE") for relative in LOCAL_SOURCE_PATHS]
    manifest = {
        "schema": "SIM13_V4B4G_R1_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1",
        "self_excluded": True,
        "acyclic": True,
        "scope": "FAILURE_CLOSURE_CONTRACT_EVIDENCE_ONLY",
        "records": local_records
        + [
            record(TEST_RESULT, "B4G_R1_PYTEST_RESULT"),
            record(RAW_RECOMPUTATION, "B4G_R1_RAW_RECOMPUTATION"),
            record(VALIDATION, "B4G_R1_VALIDATION"),
        ],
    }
    manifest["record_count"] = len(manifest["records"])
    atomic_json(EVIDENCE_MANIFEST, manifest)
    return raw, validation, manifest


def main() -> int:
    try:
        _, validation, manifest = validate()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_B4G_R1_VALIDATOR_EXCEPTION", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": validation["status"],
                "score": validation["score"],
                "manifest_records": manifest["record_count"],
                "validation_sha256": sha256_file(VALIDATION),
            },
            ensure_ascii=False,
        )
    )
    return 0 if validation["score"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
