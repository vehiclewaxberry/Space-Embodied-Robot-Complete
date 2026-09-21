#!/usr/bin/env python3
"""Read-only integrity validator for the MECH-CDR Q0-Q2 working baseline."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import yaml


CDR_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CDR_ROOT.parents[1]
ERRORS: list[str] = []
CHECKS: dict[str, object] = {}


def fail(message: str) -> None:
    ERRORS.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative: str) -> dict:
    return json.loads((CDR_ROOT / relative).read_text(encoding="utf-8-sig"))


def read_yaml(relative: str) -> dict:
    return yaml.safe_load((CDR_ROOT / relative).read_text(encoding="utf-8-sig"))


def read_csv(relative: str) -> list[dict[str, str]]:
    with (CDR_ROOT / relative).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


REQUIRED_FILES = [
    "00_authority/FROZEN_BASELINE_INPUT_MANIFEST_V1.json",
    "00_authority/PRE_INPUT_HASHES_V1.csv",
    "00_authority/MECHANICAL_BASELINE_CHANGE_CONTROL_POLICY_V1.yaml",
    "00_authority/MECHANICAL_ECR_REGISTER_V1.csv",
    "01_wp0_requirements/MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml",
    "01_wp0_requirements/STANDARDS_TAILORING_MATRIX_V1.csv",
    "01_wp0_requirements/MECHANICAL_VERIFICATION_CONTROL_DOCUMENT_V1.csv",
    "01_wp0_requirements/MECHANICAL_CRITICAL_ITEMS_REGISTER_V1.csv",
    "01_wp0_requirements/HOLD_TO_REQUIREMENT_TRACEABILITY_V1.csv",
    "01_wp0_requirements/STANDARDS_SOURCE_LEDGER_V1.csv",
    "02_wp1_loads/AUTHORIZED_MECHANICAL_LOADS_V1.yaml",
    "02_wp1_loads/LOAD_CASE_MATRIX.csv",
    "02_wp1_loads/LOAD_COMBINATION_MATRIX.csv",
    "02_wp1_loads/BOUNDARY_CONDITION_AUTHORITY.json",
    "02_wp1_loads/LOAD_SOURCE_GAP_REGISTER.csv",
    "02_wp1_loads/LAUNCHER_INTERFACE_ASSUMPTION_REGISTER.csv",
    "02_wp1_loads/DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv",
    "03_wp2_mass_interface/M3R_MASS_RULING.json",
    "03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml",
    "03_wp2_mass_interface/CONFIGURATION_MASS_INERTIA.csv",
    "03_wp2_mass_interface/B601_EQUIVALENT_INERTIA_RECOMPUTED.yaml",
    "03_wp2_mass_interface/MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml",
    "03_wp2_mass_interface/MASS_GROWTH_ALLOWANCE_REGISTER.csv",
    "03_wp2_mass_interface/SIM13_INTERFACE_IMPACT_ASSESSMENT.json",
    "03_wp2_mass_interface/WP2_VALIDATION_RECEIPT.json",
    "04_gates/MECH_Q0_REQUIREMENTS_AND_TAILORING_GATE.json",
    "04_gates/MECH_Q1_LOAD_ENVIRONMENT_AUTHORITY_GATE.json",
    "04_gates/MECH_Q2_MASS_INTERFACE_AUTHORITY_GATE.json",
    "04_gates/MECHANICAL_CDR_PHASE1_GATE.json",
    "05_validation/FROZEN_BASELINE_AUDIT_RECEIPT.json",
    "05_validation/WP0_REQUIREMENTS_VALIDATION_RECEIPT.json",
    "05_validation/WP1_LOAD_ENVIRONMENT_VALIDATION_RECEIPT.json",
]


def validate_inventory() -> None:
    missing = [name for name in REQUIRED_FILES if not (CDR_ROOT / name).is_file()]
    zero = [
        name
        for name in REQUIRED_FILES
        if (CDR_ROOT / name).is_file() and (CDR_ROOT / name).stat().st_size == 0
    ]
    if missing:
        fail(f"missing required files: {missing}")
    if zero:
        fail(f"zero-byte required files: {zero}")
    CHECKS["required_file_count"] = len(REQUIRED_FILES)
    CHECKS["required_file_missing_count"] = len(missing)
    CHECKS["required_file_zero_byte_count"] = len(zero)


def validate_frozen_inputs() -> None:
    manifest = read_json("00_authority/FROZEN_BASELINE_INPUT_MANIFEST_V1.json")
    missing: list[str] = []
    zero: list[str] = []
    drift: list[str] = []
    byte_drift: list[str] = []
    for item in manifest["inputs"]:
        path = PROJECT_ROOT / item["project_relative_path"]
        if not path.is_file():
            missing.append(item["input_id"])
            continue
        if path.stat().st_size == 0:
            zero.append(item["input_id"])
        if path.stat().st_size != item["bytes"]:
            byte_drift.append(item["input_id"])
        if sha256(path) != item["expected_sha256"].upper():
            drift.append(item["input_id"])
    if missing or zero or byte_drift or drift:
        fail(
            "frozen input integrity failure: "
            f"missing={missing}, zero={zero}, byte_drift={byte_drift}, hash_drift={drift}"
        )
    CHECKS["frozen_input_count"] = len(manifest["inputs"])
    CHECKS["frozen_input_missing_count"] = len(missing)
    CHECKS["frozen_input_hash_drift_count"] = len(drift)


def validate_wp0() -> None:
    spec = read_yaml("01_wp0_requirements/MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml")
    requirements = spec["requirements"]
    ids = [row["id"] for row in requirements]
    required_fields = {
        "id",
        "text",
        "source",
        "configuration",
        "verification",
        "acceptance_criterion",
        "owner",
        "status",
        "evidence",
        "flight_applicability",
        "prototype_applicability",
    }
    if len(requirements) != 62 or len(set(ids)) != 62:
        fail(f"WP0 requirement count/uniqueness mismatch: total={len(ids)}, unique={len(set(ids))}")
    missing_fields = {
        row["id"]: sorted(required_fields - set(row))
        for row in requirements
        if required_fields - set(row)
    }
    if missing_fields:
        fail(f"WP0 requirement fields missing: {missing_fields}")
    allowed_methods = {"A", "I", "T", "D", "R"}
    invalid_methods = {
        row["id"]: row["verification"]
        for row in requirements
        if not set(row["verification"]).issubset(allowed_methods)
    }
    if invalid_methods:
        fail(f"WP0 invalid verification methods: {invalid_methods}")

    expected_tasks = {
        "LAUNCH_STOWED",
        "SEPARATION",
        "POST_SEPARATION_SAFE",
        "SOLAR_ARRAY_DEPLOYMENT",
        "ARM_RELEASE",
        "ARM_TASK_READY",
        "ARM_MANEUVER",
        "PREGRASP",
        "CAPTURE",
        "POST_CAPTURE_STABILIZATION",
        "SAFE_MODE",
        "LEFT_PANEL_FAIL",
        "RIGHT_PANEL_FAIL",
        "BOTH_PANEL_FAIL",
    }
    observed_tasks = {row["task_id"] for row in spec["owner_task_status_baseline"]["items"]}
    if observed_tasks != expected_tasks:
        fail(f"WP0 Owner task set mismatch: missing={expected_tasks-observed_tasks}, extra={observed_tasks-expected_tasks}")

    vcd = read_csv("01_wp0_requirements/MECHANICAL_VERIFICATION_CONTROL_DOCUMENT_V1.csv")
    vcd_req_ids = [row["requirement_id"] for row in vcd]
    if len(vcd) != 62 or set(vcd_req_ids) != set(ids) or len({row["vcd_id"] for row in vcd}) != 62:
        fail("WP0 VCD is not a 62-row one-to-one requirement mapping")
    requirement_by_id = {row["id"]: row for row in requirements}
    configuration_mismatches = []
    method_mismatches = []
    acceptance_reference_mismatches = []
    status_mismatches = []
    for row in vcd:
        requirement = requirement_by_id[row["requirement_id"]]
        if set(filter(None, row["configuration"].split("|"))) != set(requirement["configuration"]):
            configuration_mismatches.append(row["vcd_id"])
        if set(filter(None, row["verification_methods"].split("|"))) != set(requirement["verification"]):
            method_mismatches.append(row["vcd_id"])
        expected_reference = (
            f"MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml::{row['requirement_id']}.acceptance_criterion"
        )
        if row["acceptance_criterion_reference"] != expected_reference:
            acceptance_reference_mismatches.append(row["vcd_id"])
        if row["current_status"] != requirement["status"]:
            status_mismatches.append(row["vcd_id"])
    if configuration_mismatches or method_mismatches or acceptance_reference_mismatches or status_mismatches:
        fail(
            "WP0 requirement-to-VCD semantic mismatch: "
            f"configuration={configuration_mismatches}, methods={method_mismatches}, "
            f"acceptance_refs={acceptance_reference_mismatches}, status={status_mismatches}"
        )

    trace = read_csv("01_wp0_requirements/HOLD_TO_REQUIREMENT_TRACEABILITY_V1.csv")
    invalid_refs = []
    for row in trace:
        for reference in filter(None, re.split(r"[|;]", row["linked_requirement_ids"])):
            if reference not in set(ids):
                invalid_refs.append((row["trace_id"], reference))
    if invalid_refs:
        fail(f"WP0 HOLD traceability has invalid requirement references: {invalid_refs}")

    CHECKS["wp0_requirement_count"] = len(requirements)
    CHECKS["wp0_owner_task_count"] = len(observed_tasks)
    CHECKS["wp0_vcd_row_count"] = len(vcd)
    CHECKS["wp0_vcd_semantic_mismatch_count"] = (
        len(configuration_mismatches)
        + len(method_mismatches)
        + len(acceptance_reference_mismatches)
        + len(status_mismatches)
    )
    CHECKS["wp0_hold_traceability_row_count"] = len(trace)
    CHECKS["wp0_input_dependency_criterion_count"] = sum(
        row["acceptance_criterion"].get("type") == "input_dependency" for row in requirements
    )


def validate_wp1() -> None:
    authority = read_yaml("02_wp1_loads/AUTHORIZED_MECHANICAL_LOADS_V1.yaml")
    cases = read_csv("02_wp1_loads/LOAD_CASE_MATRIX.csv")
    combinations = read_csv("02_wp1_loads/LOAD_COMBINATION_MATRIX.csv")
    gaps = read_csv("02_wp1_loads/LOAD_SOURCE_GAP_REGISTER.csv")
    boundaries = read_json("02_wp1_loads/BOUNDARY_CONDITION_AUTHORITY.json")["boundaries"]
    capture = read_csv("02_wp1_loads/DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv")

    case_ids = {row["case_id"] for row in cases}
    yaml_families = set(authority["load_families"])
    case_families = {row["load_family"] for row in cases}
    if len(cases) != 21 or len(case_ids) != 21:
        fail("WP1 load case count or case_id uniqueness mismatch")
    if len(yaml_families) != 19 or yaml_families != case_families:
        fail(
            f"WP1 canonical load-family closure failed: yaml_only={yaml_families-case_families}, "
            f"case_only={case_families-yaml_families}"
        )
    missing_combo_refs = []
    for row in combinations:
        for case_id in filter(None, row["primary_case_ids"].split(";")):
            if case_id not in case_ids:
                missing_combo_refs.append((row["combination_id"], case_id))
    if len(combinations) != 13 or missing_combo_refs:
        fail(f"WP1 load combination closure failed: count={len(combinations)}, missing={missing_combo_refs}")
    if len(gaps) != 19 or "LG-019" not in {row["gap_id"] for row in gaps}:
        fail("WP1 gap register must contain 19 rows including LG-019")
    allowed_source_classes = {"AUTHORIZED", "DERIVED", "PROVISIONAL", "UNKNOWN"}
    bad_boundary_classes = [
        (row["boundary_id"], row["source_class"])
        for row in boundaries
        if row["source_class"] not in allowed_source_classes
    ]
    if len(boundaries) != 9 or bad_boundary_classes:
        fail(f"WP1 boundary inventory/classification failure: count={len(boundaries)}, invalid={bad_boundary_classes}")
    if len(capture) != 8:
        fail(f"WP1 derived capture anchor count is {len(capture)}, expected 8")

    receipt = read_json("05_validation/WP1_LOAD_ENVIRONMENT_VALIDATION_RECEIPT.json")
    hash_subjects = {
        "AUTHORIZED_MECHANICAL_LOADS_V1.yaml": "02_wp1_loads/AUTHORIZED_MECHANICAL_LOADS_V1.yaml",
        "BOUNDARY_CONDITION_AUTHORITY.json": "02_wp1_loads/BOUNDARY_CONDITION_AUTHORITY.json",
        "DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv": "02_wp1_loads/DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv",
        "LAUNCHER_INTERFACE_ASSUMPTION_REGISTER.csv": "02_wp1_loads/LAUNCHER_INTERFACE_ASSUMPTION_REGISTER.csv",
        "LOAD_CASE_MATRIX.csv": "02_wp1_loads/LOAD_CASE_MATRIX.csv",
        "LOAD_COMBINATION_MATRIX.csv": "02_wp1_loads/LOAD_COMBINATION_MATRIX.csv",
        "LOAD_SOURCE_GAP_REGISTER.csv": "02_wp1_loads/LOAD_SOURCE_GAP_REGISTER.csv",
    }
    for name, relative in hash_subjects.items():
        if receipt["output_hashes"][name].upper() != sha256(CDR_ROOT / relative):
            fail(f"WP1 receipt hash mismatch for {name}")
    q1 = read_json("04_gates/MECH_Q1_LOAD_ENVIRONMENT_AUTHORITY_GATE.json")
    if q1["gate_status"] != "HOLD" or q1["pass_token_issued"] or q1["next_stage_authorized"]:
        fail("Q1 Gate must remain HOLD with no pass token and no next-stage authorization")
    for flag in (
        "formal_strength_mos_fea_authorized",
        "formal_buckling_fea_authorized",
        "formal_dynamic_response_fea_authorized",
        "qualification_test_level_definition_authorized",
    ):
        if q1[flag]:
            fail(f"Q1 Gate incorrectly authorizes {flag}")
    CHECKS["wp1_canonical_load_family_count"] = len(yaml_families)
    CHECKS["wp1_load_case_count"] = len(cases)
    CHECKS["wp1_load_combination_count"] = len(combinations)
    CHECKS["wp1_open_gap_count"] = len(gaps)
    CHECKS["wp1_authorized_flight_load_case_count"] = q1["authorized_flight_load_case_count"]


def validate_wp2() -> None:
    ruling = read_json("03_wp2_mass_interface/M3R_MASS_RULING.json")
    configs = read_csv("03_wp2_mass_interface/CONFIGURATION_MASS_INERTIA.csv")
    inertia = read_yaml("03_wp2_mass_interface/B601_EQUIVALENT_INERTIA_RECOMPUTED.yaml")
    receipt = read_json("03_wp2_mass_interface/WP2_VALIDATION_RECEIPT.json")

    values = ruling["value_register"]
    active_count = sum(int(row.get("active", False)) for row in values)
    inactive_count = sum(int(not row.get("active", False)) for row in values)
    active = ruling["active_digital_authority"]
    if (
        active_count != 1
        or inactive_count != 3
        or len(values) != 4
        or active["value_kg"] != 0.7619
        or active["value_g"] != 761.9
        or active["classification"] != "BUDGETED"
    ):
        fail("WP2 M3R must contain four values with exactly one active 761.9 g BUDGETED authority")
    if active["measured"] or active["installed"]:
        fail("WP2 M3R incorrectly claims measured or installed authority")
    legacy = [row for row in values if row["value_id"] == "M3R-MASS-V002"]
    if (
        len(legacy) != 1
        or legacy[0]["value_kg"] != 0.761904197
        or legacy[0]["classification"] != "MATERIAL_DERIVED"
        or legacy[0]["active"]
    ):
        fail("WP2 M3R legacy 0.761904197 kg value is not an inactive MATERIAL_DERIVED comparison")

    expected_configs = {
        "DEPLOYED_NOMINAL",
        "LEFT_PANEL_FAIL",
        "RIGHT_PANEL_FAIL",
        "BOTH_PANEL_FAIL",
        "ARM_STOWED_ONORBIT",
        "ARM_TASK_READY",
        "PREGRASP",
        "POST_CAPTURE_22KG",
        "POST_CAPTURE_150KG",
    }
    observed_configs = {row["configuration_id"] for row in configs}
    numeric_fields = (
        "system_total_mass_kg",
        "com_x_m",
        "com_y_m",
        "com_z_m",
        "Ixx_kg_m2",
        "Iyy_kg_m2",
        "Izz_kg_m2",
        "Ixy_kg_m2",
        "Ixz_kg_m2",
        "Iyz_kg_m2",
    )
    non_null = [(row["configuration_id"], field) for row in configs for field in numeric_fields if row[field].strip()]
    bad_dispositions = [
        row["configuration_id"]
        for row in configs
        if row["evaluation_status"] != "NOT_EVALUABLE_INPUT_AUTHORITY_MISSING"
    ]
    if observed_configs != expected_configs or non_null or bad_dispositions:
        fail(
            f"WP2 nine-configuration fail-closed contract failed: missing={expected_configs-observed_configs}, "
            f"extra={observed_configs-expected_configs}, non_null={non_null}, bad_dispositions={bad_dispositions}"
        )

    matrices = [
        inertia["result"]["inertia_about_system_com"]["matrix_kg_m2"],
        inertia["result"]["inertia_about_base_link_origin"]["matrix_kg_m2"],
    ]
    for index, raw in enumerate(matrices, start=1):
        matrix = np.asarray(raw, dtype=float)
        if matrix.shape != (3, 3) or not np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-15):
            fail(f"WP2 B601 inertia matrix {index} is not symmetric 3x3")
            continue
        moments = np.linalg.eigvalsh(matrix)
        if not np.all(moments > 0.0):
            fail(f"WP2 B601 inertia matrix {index} is not positive definite: {moments.tolist()}")
        if moments[0] + moments[1] < moments[2] - 1e-12:
            fail(f"WP2 B601 inertia matrix {index} violates the rigid-body triangle inequality")

    for item in receipt["output_inventory"]["subject_files"]:
        if sha256(CDR_ROOT / "03_wp2_mass_interface" / item["name"]) != item["sha256"].upper():
            fail(f"WP2 receipt hash mismatch for {item['name']}")
    q2 = read_json("04_gates/MECH_Q2_MASS_INTERFACE_AUTHORITY_GATE.json")
    if q2["gate_status"] != "HOLD" or q2["pass_token_issued"] or q2["next_stage_authorized"]:
        fail("Q2 Gate must remain HOLD with no pass token and no next-stage authorization")
    CHECKS["wp2_m3r_total_value_count"] = len(values)
    CHECKS["wp2_m3r_inactive_comparison_count"] = inactive_count
    CHECKS["wp2_m3r_active_digital_authority_count"] = active_count
    CHECKS["wp2_configuration_count"] = len(configs)
    CHECKS["wp2_numerically_evaluable_system_configuration_count"] = len(non_null)
    CHECKS["wp2_validated_b601_inertia_matrix_count"] = len(matrices)


def validate_gates() -> None:
    q0 = read_json("04_gates/MECH_Q0_REQUIREMENTS_AND_TAILORING_GATE.json")
    q1 = read_json("04_gates/MECH_Q1_LOAD_ENVIRONMENT_AUTHORITY_GATE.json")
    q2 = read_json("04_gates/MECH_Q2_MASS_INTERFACE_AUTHORITY_GATE.json")
    phase = read_json("04_gates/MECHANICAL_CDR_PHASE1_GATE.json")
    for name, gate in (("Q0", q0), ("Q1", q1), ("Q2", q2)):
        if gate["gate_status"] != "HOLD" or gate["pass_token_issued"]:
            fail(f"{name} is not an honest HOLD gate")
    for entry in phase["subgates"]:
        path = CDR_ROOT / entry["path"]
        if sha256(path) != entry["sha256"].upper():
            fail(f"Phase Gate subgate hash mismatch for {entry['gate']}")
    if (
        phase["gate_status"] != "HOLD"
        or phase["pass_token_issued"]
        or phase["phase_pass_rule_satisfied"]
        or phase["next_stage_authorized"]
    ):
        fail("Phase Gate must remain HOLD with no pass token and no next-stage authorization")
    if any(phase["formal_analysis_and_release_authority"].values()):
        fail("Phase Gate has an unexpected true formal-analysis or release authorization")
    CHECKS["q0_status"] = q0["gate_status"]
    CHECKS["q1_status"] = q1["gate_status"]
    CHECKS["q2_status"] = q2["gate_status"]
    CHECKS["phase_status"] = phase["gate_status"]


def main() -> int:
    validate_inventory()
    if ERRORS:
        print(json.dumps({"status": "FAIL", "errors": ERRORS, "checks": CHECKS}, indent=2))
        return 1
    validate_frozen_inputs()
    validate_wp0()
    validate_wp1()
    validate_wp2()
    validate_gates()
    result = {
        "schema": "CDR_PHASE1_VALIDATOR_STDOUT_V1",
        "status": "PASS" if not ERRORS else "FAIL",
        "artifact_integrity_pass": not ERRORS,
        "programmatic_gate_status": "HOLD",
        "formal_fea_authorized": False,
        "errors": ERRORS,
        "checks": CHECKS,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
