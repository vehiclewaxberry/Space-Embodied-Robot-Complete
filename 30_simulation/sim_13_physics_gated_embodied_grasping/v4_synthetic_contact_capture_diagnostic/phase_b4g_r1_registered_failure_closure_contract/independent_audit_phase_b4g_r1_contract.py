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
B4G = HERE.parent / "phase_b4g_post_freeze_synthetic_jaw_retraction_execution"
CONTRACTS = HERE / "contracts"
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCE_BINDINGS = CONTRACTS / "PHASE_B4G_R1_SOURCE_BINDINGS_V1.json"
CLOSURE_CONTRACT = CONTRACTS / "PHASE_B4G_R1_FAILURE_CLOSURE_CONTRACT_V1.json"
TEST_RESULT = RESULTS / "SIM13_V4B4G_R1_TEST_RESULT_V1.json"
RAW_RECOMPUTATION = EVIDENCE / "SIM13_V4B4G_R1_RAW_RECOMPUTATION_V1.json"
VALIDATION = RESULTS / "SIM13_V4B4G_R1_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B4G_R1_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"
AUDIT = RESULTS / "SIM13_V4B4G_R1_INDEPENDENT_AUDIT_V1.json"
GATE = RESULTS / "SIM13_V4B4G_R1_FAILURE_CLOSURE_GATE_V1.json"
TERMINAL = RESULTS / "SIM13_V4B4G_R1_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

PASS_STATUS = "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"


class AuditError(RuntimeError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AuditError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise AuditError(f"non-object JSON: {path}")
    return value


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def identity(path: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": file_sha(path),
    }


def _matches(record: dict[str, Any], base: Path = PROJECT_ROOT) -> bool:
    path = base / record["path"]
    return bool(
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == record["bytes"]
        and file_sha(path) == record["sha256"]
    )


def independent_raw_audit(bindings: dict[str, Any]) -> dict[str, Any]:
    schedule = read_json(B4G / "contracts/PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    schedule_copy = read_json(B4G / "evidence/SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json")
    if schedule != schedule_copy or canonical_hash(schedule["slots"]) != schedule["slots_sha256"]:
        raise AuditError("schedule binding mismatch")

    raw_root = B4G / "evidence/raw_cases"
    files = sorted((path for path in raw_root.iterdir() if path.is_file()), key=lambda path: path.name)
    inventory_records = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha(path)}
        for path in files
    ]
    inventory_hash = canonical_hash(inventory_records)
    if any(path.is_symlink() for path in files):
        raise AuditError("raw inventory contains linked evidence")

    failures: list[tuple[int, str]] = []
    numeric_failed_slots: list[int] = []
    a2_without_npz = 0
    cases: dict[tuple[str, float, float], dict[str, Any]] = {}
    for index, slot in enumerate(schedule["slots"]):
        matches = sorted(raw_root.glob(f"{index:03d}__*.json"))
        if len(matches) != 1:
            raise AuditError(f"raw JSON cardinality mismatch at {index}")
        json_path = matches[0]
        metadata = read_json(json_path)
        if metadata.get("registered_slot") != slot or metadata.get("slot_index") != index:
            raise AuditError(f"raw schedule mismatch at {index}")
        if metadata["source_hashes"].get("registered_slots_sha256") != schedule["slots_sha256"]:
            raise AuditError(f"raw schedule hash mismatch at {index}")
        npz_path = json_path.with_suffix(".npz")
        if metadata["execution_status"] == "NOT_EVALUATED_NO_A1_SUCCESS":
            if slot["arm"] != "A2" or npz_path.exists():
                raise AuditError(f"A2 non-evaluation mismatch at {index}")
            a2_without_npz += 1
            continue
        if metadata["execution_status"] != "EXECUTED_FRESH_REGISTERED_SLOT" or not npz_path.is_file():
            raise AuditError(f"executed raw mismatch at {index}")
        if metadata["npz_sha256"] != file_sha(npz_path) or metadata["npz_bytes"] != npz_path.stat().st_size:
            raise AuditError(f"NPZ identity mismatch at {index}")
        with np.load(npz_path, allow_pickle=False) as archive:
            kinetic = np.asarray(archive["total_kinetic_energy_J"], dtype=np.float64)
            work = np.asarray(archive["signed_W_act_J"], dtype=np.float64)
            stored = np.asarray(archive["energy_minus_work_residual_J"], dtype=np.float64)
        recomputed = (kinetic - kinetic[0]) - (work - work[0])
        recomputed_max = float(np.max(np.abs(recomputed)))
        stored_difference = float(np.max(np.abs(recomputed - stored)))
        if stored_difference > 2e-12:
            raise AuditError(f"stored residual mismatch at {index}")
        if recomputed_max > 1e-7:
            if stored_difference > 1e-18:
                raise AuditError(f"failed-case stored residual mismatch at {index}")
            numeric_failed_slots.append(index)
        for gate in metadata["gate_records"]:
            if gate["evaluation_status"] == "FAIL":
                failures.append((index, gate["gate_id"]))
        if slot["arm"] == "A1":
            cases[(slot["lane_id"], float(slot["alpha"]), float(slot["command_duration_s"]))] = {
                "residual_J": recomputed_max,
                "work_J": float(work[-1] - work[0]),
                "metadata": metadata,
            }

    orders: list[float] = []
    for duration in (0.005, 0.01, 0.02):
        coarse = cases[("MIDPOINT_COARSE", 16.0, duration)]["residual_J"]
        fine = cases[("MIDPOINT_FINE", 16.0, duration)]["residual_J"]
        reference = cases[("MIDPOINT_REFERENCE", 16.0, duration)]["residual_J"]
        orders.extend((math.log2(coarse / fine), math.log2(fine / reference)))

    ledger = read_json(B4G / "evidence/SIM13_V4B4G_A2_SELECTION_LEDGER_V1.json")
    paired = []
    unpaired = 0
    for ledger_row in ledger["cross_reference_gate_records_18"]:
        detail = ledger_row["detail"]
        alpha = float(detail["alpha"])
        duration = float(detail["T_cmd_s"])
        rk4 = cases[("RK4_REFERENCE", alpha, duration)]
        midpoint = cases[("MIDPOINT_REFERENCE", alpha, duration)]
        rm = rk4["metadata"]
        mm = midpoint["metadata"]
        finite = bool(
            rm["responses"]["finite_removal_event"]
            and mm["responses"]["finite_removal_event"]
            and rm["responses"]["post_release_passed"]
            and mm["responses"]["post_release_passed"]
        )
        if not finite:
            unpaired += 1
            continue
        acquisition_delta = abs(
            rm["acquisition"]["acquisition_time_s"]
            - mm["acquisition"]["acquisition_time_s"]
        )
        removal_delta = abs(rm["responses"]["removal_time_s"] - mm["responses"]["removal_time_s"])
        work_delta = abs(rk4["work_J"] - midpoint["work_J"])
        tolerance = max(1e-10, 0.001 * max(abs(rk4["work_J"]), abs(midpoint["work_J"])))
        predicate = acquisition_delta <= 0.00025 and removal_delta <= 0.00025 and work_delta <= tolerance
        paired.append(
            {
                "removal_delta_s": removal_delta,
                "work_exceedance_factor": work_delta / tolerance,
                "predicate": predicate,
            }
        )

    return {
        "raw_json_count": sum(path.suffix == ".json" for path in files),
        "raw_npz_count": sum(path.suffix == ".npz" for path in files),
        "raw_file_count": len(files),
        "raw_inventory_sha256": inventory_hash,
        "numeric_failed_slots": sorted(numeric_failed_slots),
        "metadata_failures": sorted(failures),
        "a2_without_npz": a2_without_npz,
        "order_min": min(orders),
        "order_max": max(orders),
        "paired_count": len(paired),
        "paired_false_count": sum(not row["predicate"] for row in paired),
        "unpaired_count": unpaired,
        "work_factor_min": min(row["work_exceedance_factor"] for row in paired),
        "work_factor_max": max(row["work_exceedance_factor"] for row in paired),
        "substantive_removal_exceedance_count": sum(row["removal_delta_s"] > 0.00025 + 1e-15 for row in paired),
        "binary_boundary_removal_count": sum(
            row["removal_delta_s"] > 0.00025
            and abs(row["removal_delta_s"] - 0.00025) <= 1e-15
            for row in paired
        ),
        "selected_parent_level": ledger["selected_parent_level"],
    }


def audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bindings = read_json(SOURCE_BINDINGS)
    contract = read_json(CLOSURE_CONTRACT)
    validation = read_json(VALIDATION)
    manifest = read_json(EVIDENCE_MANIFEST)
    test_result = read_json(TEST_RESULT)
    raw = independent_raw_audit(bindings)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "pass": bool(condition), "detail": detail})

    source_records = bindings["sources"]
    check("R1A01", all(_matches(row) for row in source_records))
    check(
        "R1A02",
        next(row for row in source_records if row["id"] == "b4g_active_execution_source_freeze_terminal")["sha256"]
        == "B22C4D5B4C0E15FF58484D252A2316E6B42458423079E2324D6455CC09EF3464",
    )
    check(
        "R1A03",
        read_json(B4G / "results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json")["active"] is True
        and read_json(B4G / "results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json")["replacement_campaign_summary"] is None,
    )
    check(
        "R1A04",
        raw["raw_json_count"] == 144
        and raw["raw_npz_count"] == 120
        and raw["raw_file_count"] == 264
        and raw["raw_inventory_sha256"] == bindings["raw_case_inventory"]["canonical_sha256"],
        raw,
    )
    expected_failures = [(82, "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"), (84, "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"), (88, "B4F-G06-ENERGY-MINUS-WORK-IDENTITY")]
    check("R1A05", raw["numeric_failed_slots"] == [82, 84, 88] and raw["metadata_failures"] == expected_failures)
    expected_order = contract["g06_failure_closure"]["midpoint_alpha16_empirical_orders"]
    check(
        "R1A06",
        abs(raw["order_min"] - expected_order["exact_min"]) <= 1e-12
        and abs(raw["order_max"] - expected_order["exact_max"]) <= 1e-12,
        {"min": raw["order_min"], "max": raw["order_max"]},
    )
    check(
        "R1A07",
        contract["g06_failure_closure"]["mechanism_ruling"]["classification"]
        == "EXPLICIT_MIDPOINT_SECOND_ORDER_TRUNCATION_DEFECT_IN_THE_FROZEN_DISCRETE_FIRST_LAW"
        and contract["g06_failure_closure"]["mechanism_ruling"]["physical_missing_term_supported"] is False
        and contract["g06_failure_closure"]["mechanism_ruling"]["intermittent_or_nondeterministic_code_fault_supported"] is False,
    )
    run_spec_text = json.dumps(read_json(B4G / "contracts/PHASE_B4G_RUN_SPEC_V1.json")["work_and_ledger_audit"], sort_keys=True)
    old_validator_text = (B4G / "b4g_validation/validator.py").read_text(encoding="utf-8")
    check(
        "R1A08",
        "cumulative_work_error" not in run_spec_text
        and "cumulative_work_error <= 1.0e-7" in old_validator_text
        and contract["g04_runner_validator_divergence"]["silent_deletion_of_validator_check_authorized"] is False,
    )
    check(
        "R1A09",
        raw["paired_count"] == 9
        and raw["paired_false_count"] == 9
        and raw["unpaired_count"] == 9
        and raw["selected_parent_level"] is None
        and raw["a2_without_npz"] == 24,
        raw,
    )
    g12 = contract["g12_and_a2_ruling"]
    check(
        "R1A10",
        abs(raw["work_factor_min"] - g12["signed_work_exceedance_factor_min"]) <= 1e-9
        and abs(raw["work_factor_max"] - g12["signed_work_exceedance_factor_max"]) <= 1e-9
        and raw["substantive_removal_exceedance_count"] == 2
        and raw["binary_boundary_removal_count"] == 1,
    )
    check(
        "R1A11",
        validation["status"] == "PASS_FAILURE_CLOSURE_VALIDATION_PENDING_INDEPENDENT_AUDIT"
        and validation["score"] == {"pass": 20, "fail": 0, "total": 20, "failed": []}
        and validation["original_b4g_final_credit"] is False
        and validation["new_campaign_executed"] is False,
        validation["score"],
    )
    manifest_paths = {row["path"] for row in manifest["records"]}
    check(
        "R1A12",
        manifest["self_excluded"] is True
        and manifest["acyclic"] is True
        and manifest["record_count"] == len(manifest["records"])
        and len(manifest_paths) == len(manifest["records"])
        and EVIDENCE_MANIFEST.relative_to(PROJECT_ROOT).as_posix() not in manifest_paths
        and all(_matches(row) for row in manifest["records"]),
    )
    check(
        "R1A13",
        test_result["status"] == "PASS_PHASE_B4G_R1_PYTEST"
        and test_result["outcomes"] == contract["test_contract"]["required_outcome"],
    )
    remediation = contract["prospective_remediation"]
    check(
        "R1A14",
        remediation["classification"] == "PLANNED_NOT_AUTHORIZED"
        and remediation["new_campaign_authorized"] is False
        and remediation["candidate_midpoint_steps"]["step_s"] == [0.00025, 0.000125, 0.0000625]
        and "acquisition_convergence" in remediation["required_preflight_before_campaign_decision"]
        and "propagation_convergence" in remediation["required_preflight_before_campaign_decision"],
    )
    check("R1A15", all(value is False for value in contract["required_false"].values()))
    check(
        "R1A16",
        contract["memory_record"]["memory_gate_applicable"] is False
        and contract["memory_record"]["memory_gate_passed"] is False
        and contract["memory_record"]["owner_override_used"] is False,
    )

    failed = [row["id"] for row in checks if not row["pass"]]
    receipt = {
        "schema": "SIM13_V4B4G_R1_INDEPENDENT_AUDIT_V1",
        "status": "PASS_INDEPENDENT_FAILURE_CLOSURE_AUDIT" if not failed else "FAIL_INDEPENDENT_FAILURE_CLOSURE_AUDIT",
        "scope": "READ_ONLY_RAW_RECOMPUTATION_AND_CONTRACT_AUDIT_NO_NEW_CAMPAIGN",
        "independence": {
            "imports_r1_validator": False,
            "imports_original_b4g_solver": False,
            "imports_original_b4g_validator": False,
            "independently_reads_json_npz_and_recomputes_hashes": True,
        },
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "independent_raw_summary": raw,
    }
    write_json(AUDIT, receipt)
    if failed:
        return receipt, {}, {}

    gate = {
        "schema": "SIM13_V4B4G_R1_FAILURE_CLOSURE_GATE_V1",
        "status": PASS_STATUS,
        "final": True,
        "scope": "FAILURE_CLOSURE_CONTRACT_ONLY_NO_SCIENTIFIC_OR_CAMPAIGN_PASS",
        "hash_chain": {
            "test_result": identity(TEST_RESULT, "B4G_R1_PYTEST_RESULT"),
            "raw_recomputation": identity(RAW_RECOMPUTATION, "B4G_R1_RAW_RECOMPUTATION"),
            "validation": identity(VALIDATION, "B4G_R1_VALIDATION"),
            "evidence_manifest": identity(EVIDENCE_MANIFEST, "B4G_R1_SELF_EXCLUDED_EVIDENCE_MANIFEST"),
            "independent_audit": identity(AUDIT, "B4G_R1_INDEPENDENT_AUDIT"),
        },
        "failure_closure": {
            "contract_frozen": True,
            "contract_audited": True,
            "preserved_raw_inventory_sha256": raw["raw_inventory_sha256"],
            "only_failed_slots": [82, 84, 88],
            "g06_threshold_J": 1e-7,
            "empirical_order_exact_range": [raw["order_min"], raw["order_max"]],
            "mechanism": contract["g06_failure_closure"]["mechanism_ruling"]["classification"],
        },
        "open_items": {
            "g04_runner_validator_contract_divergence": True,
            "g12_paired_finite_predicates_false": "9/9",
            "g12_eligible_level_count": 0,
            "selected_parent_level": None,
            "a2_executed": False,
        },
        "prospective_only": {
            "classification": "PLANNED_NOT_AUTHORIZED",
            "candidate_midpoint_steps_s": [0.00025, 0.000125, 0.0000625],
            "preflight_required_before_campaign_decision": True,
            "full_campaign_authorized": False,
        },
        "original_b4g_final_credit": False,
        "b4g_scientific_gate_pass": False,
        "new_physics_campaign_executed": False,
        "required_false": contract["required_false"],
        "formal_sim13_v2_state_unchanged": contract["formal_sim13_v2_state_unchanged"],
        "memory_record": contract["memory_record"],
        "claim_boundary": "This PASS closes and audits the registered B4G failure contract only; it grants no original B4G final credit, scientific pass, physical, current-system, formal NC19, Owner, production or next-stage authority.",
    }
    write_json(GATE, gate)
    terminal = {
        "schema": "SIM13_V4B4G_R1_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True,
        "acyclic": True,
        "scope": "FAILURE_CLOSURE_CONTRACT_ONLY",
        "records": [
            identity(EVIDENCE_MANIFEST, "B4G_R1_SELF_EXCLUDED_EVIDENCE_MANIFEST"),
            identity(AUDIT, "B4G_R1_INDEPENDENT_AUDIT"),
            identity(GATE, "B4G_R1_FAILURE_CLOSURE_GATE"),
        ],
    }
    write_json(TERMINAL, terminal)
    return receipt, gate, terminal


def main() -> int:
    try:
        receipt, gate, terminal = audit()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_B4G_R1_AUDIT_EXCEPTION", "error": str(exc)}, ensure_ascii=False))
        return 1
    if receipt["score"]["fail"]:
        print(json.dumps({"status": receipt["status"], "score": receipt["score"]}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": gate["status"],
                "audit_score": receipt["score"],
                "gate_sha256": file_sha(GATE),
                "terminal_sha256": file_sha(TERMINAL),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
