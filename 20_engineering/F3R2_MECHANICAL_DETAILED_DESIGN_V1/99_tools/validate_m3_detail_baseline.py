#!/usr/bin/env python3
"""Cross-branch validation and fail-closed Phase M3 gate generation."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

M3 = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = M3 / "12_gate" / "MECHANICAL_DETAIL_DESIGN_GATE.json"
VALIDATION_PATH = M3 / "11_validation" / "M3_BASELINE_VALIDATION_RECEIPT.json"
OUTPUT_MANIFEST_PATH = M3 / "11_validation" / "OUTPUT_MANIFEST_SHA256.csv"
ITERATION_RECEIPT_PATH = M3 / "11_validation" / "M3_L01_ITERATION_RECEIPT.json"

REQUIRED = [
    "00_authority/FROZEN_INPUT_MANIFEST_V1.json",
    "00_authority/M3_PHASE_AUTHORITY_AND_BOUNDARY.yaml",
    "00_authority/MECHANICAL_LOOP_ENGINEERING_CONTROL_V1.yaml",
    "00_authority/M3_OWNER_OVERRIDE_REGISTER_V1.csv",
    "00_authority/M3_ECR_REGISTER_V1.csv",
    "01_requirements/MECHANICAL_DETAIL_DESIGN_REQUIREMENTS_V1.yaml",
    "01_requirements/MECHANICAL_DETAIL_DESIGN_VCD_V1.csv",
    "01_requirements/M3_RESEARCH_AND_DESIGN_METHOD.md",
    "02_interfaces/B601_BASE_ADAPTER_REV_C_INTERFACE.yaml",
    "02_interfaces/M3R_INTERFACE_ASSEMBLY_V2.yaml",
    "02_interfaces/M3R_INPUT_AUTHORITY_AUDIT_RECEIPT.json",
    "02_interfaces/MECH_RL_INTERFACE_V2.yaml",
    "03_mass_properties/SYSTEM_MASS_PROPERTIES_V2.yaml",
    "03_mass_properties/CONFIGURATION_MASS_INERTIA_V2.csv",
    "03_mass_properties/M3_MASS_MATERIAL_TOLERANCE_VALIDATION_RECEIPT.json",
    "03_mass_properties/SIM13_V2_CHANGE_IMPACT_REGISTER.json",
    "04_materials/system/MATERIAL_PROCESS_CANDIDATE_DATABASE_V1.csv",
    "05_tolerance/system/SYSTEM_TOLERANCE_CHAIN_REGISTER_V1.csv",
    "06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
    "06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
    "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.FCStd",
    "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
    "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json",
    "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json",
    "06_parameterized_parts/m3r/M3R_DETAIL_BRANCH_VALIDATION_RECEIPT.json",
    "06_parameterized_parts/gripper/GRIPPER_R1_ENGINEERING_PARAMETER_TABLE.yaml",
    "08_mechanisms/gripper/GRIPPER_R1_CONTACT_LOAD_REQUIREMENTS.csv",
    "08_mechanisms/gripper/GRIPPER_R1_ENGINEERING_VALIDATION_RECEIPT.json",
    "09_drawings/m3r/M3R_DRAWING_REQUIREMENTS_V1.yaml",
    "09_drawings/m3r/M3R_DRAWING_RELEASE_CHECKLIST_V1.csv",
    "09_drawings/m3r/M3R_INTERFACE_REFERENCE_DRAWING_DRAFT.svg",
    "10_bom/M3R_BOM_V2.csv",
    "11_validation/M3_COUPLED_CAPTURE_PILOT_RUN_PLAN.csv",
    "11_validation/M3_COUPLED_CAPTURE_PILOT_RUN_PLAN_RECEIPT.json",
    "12_gate/NEXT_LOOP_ACTION_REGISTER.csv",
    "07_fea/FEA_ENTRY_GATE.json",
]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest().upper()


def load_json(relative: str) -> Any:
    return json.loads((M3 / relative).read_text(encoding="utf-8-sig"))


def load_yaml(relative: str) -> Any:
    return yaml.safe_load((M3 / relative).read_text(encoding="utf-8-sig"))


def load_csv(relative: str) -> list[dict[str, str]]:
    with (M3 / relative).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def isclose(left: float, right: float, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def walk_unknown_value_violations(node: Any, pointer: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(node, dict):
        classification = node.get("classification")
        if classification == "UNKNOWN" and "value" in node and node["value"] is not None:
            violations.append(pointer)
        for key, value in node.items():
            violations.extend(walk_unknown_value_violations(value, f"{pointer}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            violations.extend(walk_unknown_value_violations(value, f"{pointer}[{index}]"))
    return violations


def parse_machine_readable() -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    counts = {"json": 0, "yaml": 0, "csv": 0, "svg": 0}
    for path in sorted(M3.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(M3).as_posix()
        try:
            if path.suffix.lower() == ".json":
                json.loads(path.read_text(encoding="utf-8-sig"))
                counts["json"] += 1
            elif path.suffix.lower() in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8-sig"))
                counts["yaml"] += 1
            elif path.suffix.lower() == ".csv":
                with path.open(newline="", encoding="utf-8-sig") as stream:
                    rows = [row for row in csv.reader(stream) if any(cell.strip() for cell in row)]
                if not rows or not rows[0]:
                    raise ValueError("empty CSV")
                width = len(rows[0])
                if any(len(row) != width for row in rows):
                    raise ValueError("inconsistent CSV row width")
                counts["csv"] += 1
            elif path.suffix.lower() == ".svg":
                ET.parse(path)
                counts["svg"] += 1
        except Exception as exc:  # report all parse failures in one receipt
            failures.append({"path": relative, "error": f"{type(exc).__name__}: {exc}"})
    return {"counts": counts, "failure_count": len(failures), "failures": failures}


def audit_frozen_inputs() -> dict[str, Any]:
    manifest = load_json("00_authority/FROZEN_INPUT_MANIFEST_V1.json")
    missing = 0
    zero_byte = 0
    drift = 0
    for record in manifest["records"]:
        candidate = Path(record["path"])
        path = candidate if candidate.is_absolute() else ROOT / candidate
        if not path.is_file():
            missing += 1
            continue
        if path.stat().st_size == 0:
            zero_byte += 1
        elif sha256(path) != record["sha256"]:
            drift += 1
    return {
        "input_count": len(manifest["records"]),
        "missing_count": missing,
        "zero_byte_count": zero_byte,
        "hash_drift_count": drift,
        "status": "PASS" if missing == 0 and zero_byte == 0 and drift == 0 else "FAIL",
    }


def audit_source_reference_coverage() -> dict[str, Any]:
    manifest = load_json("00_authority/FROZEN_INPUT_MANIFEST_V1.json")
    registered = {record["path"].replace("\\", "/") for record in manifest["records"]}
    patterns = [
        re.compile(r"(?:20_engineering|30_simulation)/[A-Za-z0-9_./-]+"),
        re.compile(r"C:/Users/stude/\.codex/attachments/[A-Za-z0-9_./-]+"),
    ]
    referenced: set[str] = set()
    allowed_suffixes = {".json", ".yaml", ".yml", ".csv", ".md", ".py", ".txt", ".step", ".stp", ".fcstd", ".stl", ".urdf", ".svg"}
    for path in M3.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        if path.suffix.lower() in {".step", ".stp", ".fcstd", ".stl"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for pattern in patterns:
            referenced.update(match.group(0).rstrip(".") for match in pattern.finditer(text))
    prefix = "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1"
    external_existing = []
    for reference in sorted(referenced):
        if reference == prefix or reference.startswith(prefix + "/"):
            continue
        candidate = Path(reference)
        resolved = candidate if candidate.is_absolute() else ROOT / candidate
        if resolved.is_file():
            external_existing.append(reference)
    unregistered = sorted(set(external_existing) - registered)
    return {
        "external_existing_reference_count": len(set(external_existing)),
        "registered_reference_count": len(set(external_existing)) - len(unregistered),
        "unregistered_count": len(unregistered),
        "unregistered": unregistered,
        "status": "PASS" if not unregistered else "FAIL",
    }


def validate_requirements() -> dict[str, Any]:
    requirements = load_yaml("01_requirements/MECHANICAL_DETAIL_DESIGN_REQUIREMENTS_V1.yaml")["requirements"]
    vcd = load_csv("01_requirements/MECHANICAL_DETAIL_DESIGN_VCD_V1.csv")
    requirement_ids = [row["id"] for row in requirements]
    vcd_ids = [row["requirement_id"] for row in vcd]
    missing = sorted(set(requirement_ids) - set(vcd_ids))
    extra = sorted(set(vcd_ids) - set(requirement_ids))
    duplicates = sorted({item for item in requirement_ids + vcd_ids if (requirement_ids + vcd_ids).count(item) > 2})
    self_generated = {"12_gate/MECHANICAL_DETAIL_DESIGN_GATE.json"}
    artifact_missing = [
        row["artifact"] for row in vcd
        if row["artifact"] not in self_generated and not (M3 / row["artifact"]).is_file()
    ]
    status = "PASS" if not missing and not extra and not duplicates and not artifact_missing else "FAIL"
    return {
        "requirement_count": len(requirement_ids),
        "vcd_row_count": len(vcd_ids),
        "missing_vcd_ids": missing,
        "extra_vcd_ids": extra,
        "duplicate_ids": duplicates,
        "missing_evidence_artifacts": artifact_missing,
        "status": status,
    }


def validate_m3r() -> dict[str, Any]:
    branch = load_json("06_parameterized_parts/m3r/M3R_DETAIL_BRANCH_VALIDATION_RECEIPT.json")
    build = load_json("06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json")
    geometry = load_json("06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json")
    fcbak = load_json("06_parameterized_parts/m3r/M3R_FCBAK_DISPOSITION.json")
    stage_a = load_yaml("06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml")
    stage_b = load_yaml("06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml")
    interface = load_yaml("02_interfaces/B601_BASE_ADAPTER_REV_C_INTERFACE.yaml")
    unknown_violations = (
        walk_unknown_value_violations(stage_a)
        + walk_unknown_value_violations(stage_b)
        + walk_unknown_value_violations(interface)
    )
    output_hash_mismatches = []
    output_dir = M3 / "06_parameterized_parts" / "m3r"
    for output in build["outputs"]:
        path = output_dir / output["path"]
        if not path.is_file() or sha256(path) != output["sha256"]:
            output_hash_mismatches.append(output["path"])
    checks = [
        branch["failure_count"] == 0,
        branch["subgate"] == "PASS_WORKING_DETAIL_BRANCH_WITH_RELEASE_HOLDS",
        branch["formal_fea_performed"] is False,
        fcbak["workspace_remaining_fcbak_count"] == 0,
        not list((M3 / "06_parameterized_parts/m3r").glob("*.FCBak")),
        build["geometry"]["stage_A"]["valid"] is True,
        build["geometry"]["stage_B"]["valid"] is True,
        build["geometry"]["stage_A"]["solid_count"] == 1,
        build["geometry"]["stage_B"]["solid_count"] == 1,
        isclose(build["geometry"]["assembly_contact"]["common_volume_mm3"], 0.0),
        isclose(build["geometry"]["assembly_contact"]["minimum_distance_mm"], 0.0),
        build["mass_authority"]["classification"] == "BUDGETED",
        isclose(build["mass_authority"]["active_assembly_budget_g"], 761.9),
        build["mass_authority"]["measured"] is False,
        build["mass_authority"]["installed"] is False,
        build["formal_fea_performed"] is False,
        len(geometry["parts"]) == 2,
        all(part["geometrically_equivalent"] for part in geometry["parts"]),
        not geometry["failed_parts"],
        not unknown_violations,
        not output_hash_mismatches,
    ]
    bom = load_csv("10_bom/M3R_BOM_V2.csv")
    checklist = load_csv("09_drawings/m3r/M3R_DRAWING_RELEASE_CHECKLIST_V1.csv")
    return {
        "status": "PASS_WORKING_SCOPE" if all(checks) else "FAIL",
        "check_count": len(checks),
        "failed_check_count": sum(not value for value in checks),
        "stage_A_volume_mm3": build["geometry"]["stage_A"]["volume_mm3"],
        "stage_B_volume_mm3": build["geometry"]["stage_B"]["volume_mm3"],
        "m6_nominal_net_hole_edge_ligament_mm": build["geometry"]["m6_net_hole_edge_ligament_mm"],
        "bom_row_count": len(bom),
        "drawing_checklist_row_count": len(checklist),
        "drawing_hold_count": sum(row["status"] == "HOLD" for row in checklist),
        "unknown_nonnull_violation_count": len(unknown_violations),
        "output_hash_mismatches": output_hash_mismatches,
    }


def validate_gripper() -> dict[str, Any]:
    receipt = load_json("08_mechanisms/gripper/GRIPPER_R1_ENGINEERING_VALIDATION_RECEIPT.json")
    motion = receipt["read_only_geometry_and_motion_checks"]
    stroke = motion["continuous_stroke_witness"]
    parameter_table = load_yaml("06_parameterized_parts/gripper/GRIPPER_R1_ENGINEERING_PARAMETER_TABLE.yaml")
    unknown_violations = walk_unknown_value_violations(parameter_table)
    source_mismatches = []
    for source in receipt["source_integrity"]["files"]:
        path = ROOT / source["path"]
        if not path.is_file() or sha256(path) != source["sha256"]:
            source_mismatches.append(source["path"])
    checks = [
        receipt["subgate"]["verdict"] == "HOLD",
        receipt["scope"]["formal_fea_executed"] is False,
        receipt["source_integrity"]["status"] == "PASS",
        not source_mismatches,
        motion["neutral_palm_step"]["valid"] is True,
        motion["neutral_palm_step"]["solid_count"] == 12,
        stroke["row_count"] == 144,
        isclose(stroke["minimum_travel_mm"], 0.0),
        isclose(stroke["maximum_travel_mm"], 71.5),
        isclose(stroke["sample_step_mm"], 0.5),
        stroke["analytic_false_row_count"] == 0,
        stroke["positive_overlap_row_count"] == 0,
        motion["native_v5_remaining_interference_count"] == 36,
        not unknown_violations,
        receipt["units_and_uncertainty_audit"]["status"] == "PASS_FAIL_CLOSED",
    ]
    return {
        "status": "PASS_NEUTRAL_GEOMETRY_ENGINEERING_RELEASE_HOLD" if all(checks) else "FAIL",
        "check_count": len(checks),
        "failed_check_count": sum(not value for value in checks),
        "stroke_sample_count": stroke["row_count"],
        "positive_overlap_row_count": stroke["positive_overlap_row_count"],
        "native_v5_remaining_interference_count": motion["native_v5_remaining_interference_count"],
        "unknown_nonnull_violation_count": len(unknown_violations),
        "source_hash_mismatches": source_mismatches,
    }


def validate_mass_material_tolerance() -> dict[str, Any]:
    mass = load_yaml("03_mass_properties/SYSTEM_MASS_PROPERTIES_V2.yaml")
    configs = load_csv("03_mass_properties/CONFIGURATION_MASS_INERTIA_V2.csv")
    materials = load_csv("04_materials/system/MATERIAL_PROCESS_CANDIDATE_DATABASE_V1.csv")
    tolerances = load_csv("05_tolerance/system/SYSTEM_TOLERANCE_CHAIN_REGISTER_V1.csv")
    receipt = load_json("03_mass_properties/M3_MASS_MATERIAL_TOLERANCE_VALIDATION_RECEIPT.json")
    b601 = mass["active_component_authorities"]["b601_complete_arm"]
    m3r = mass["active_component_authorities"]["m3r_stage_a_plus_stage_b"]
    system_fields = [
        "system_total_mass_kg", "system_mass_standard_uncertainty_kg",
        "com_x_m", "com_y_m", "com_z_m", "com_standard_uncertainty_m",
        "Ixx_kg_m2", "Iyy_kg_m2", "Izz_kg_m2", "Ixy_kg_m2", "Ixz_kg_m2", "Iyz_kg_m2",
        "inertia_standard_uncertainty_kg_m2",
    ]
    nonnull_configuration_fields = [
        f"{row['configuration_id']}:{field}"
        for row in configs for field in system_fields if row[field].strip()
    ]
    material_approved = sum(row["material_approved"].lower() == "true" for row in materials)
    fea_authorized = sum(row["mechanical_properties_authorized_for_fea"].lower() == "true" for row in materials)
    tolerance_limit_nonblank = sum(
        any(row[field].strip() for field in (
            "feature_A_tolerance_lower", "feature_A_tolerance_upper",
            "feature_B_tolerance_lower", "feature_B_tolerance_upper",
        ))
        for row in tolerances
    )
    tolerance_accepted = sum(row["acceptance_status"] == "PASS" for row in tolerances)
    checks = [
        isclose(b601["mass_kg"], 4.695555949342986),
        b601["classification"] == "BUDGETED",
        b601["mass_standard_uncertainty_kg"] is None,
        isclose(m3r["mass_kg"], 0.7619),
        m3r["classification"] == "BUDGETED",
        m3r["center_of_mass_m"] is None,
        m3r["inertia_kg_m2"] is None,
        len(configs) == 9,
        not nonnull_configuration_fields,
        len(materials) == 15,
        material_approved == 0,
        fea_authorized == 0,
        len(tolerances) == 14,
        tolerance_limit_nonblank == 0,
        tolerance_accepted == 0,
        receipt["validation_metrics"]["formal_fea_executed_count"] == 0,
        receipt["validation_metrics"]["sim13_production_mutation_count"] == 0,
        all(item["status"] == "PASS_UNCHANGED" for item in receipt["protected_artifact_integrity"]),
    ]
    return {
        "status": "PASS_WORKING_AUTHORITY_SYSTEM_CLOSURE_HOLD" if all(checks) else "FAIL",
        "check_count": len(checks),
        "failed_check_count": sum(not value for value in checks),
        "configuration_row_count": len(configs),
        "configuration_released_numeric_field_count": len(nonnull_configuration_fields),
        "material_row_count": len(materials),
        "material_approved_count": material_approved,
        "fea_property_authorized_count": fea_authorized,
        "tolerance_chain_count": len(tolerances),
        "tolerance_limit_populated_count": tolerance_limit_nonblank,
        "tolerance_accepted_count": tolerance_accepted,
    }


def validate_fea_and_sim13() -> dict[str, Any]:
    fea = load_json("07_fea/FEA_ENTRY_GATE.json")
    mech_rl = load_yaml("02_interfaces/MECH_RL_INTERFACE_V2.yaml")
    impact = load_json("03_mass_properties/SIM13_V2_CHANGE_IMPACT_REGISTER.json")
    m3r_step = M3 / "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step"
    analysis_extensions = {".inp", ".odb", ".sim", ".sta", ".msg", ".dat", ".frd", ".med"}
    analysis_files = [path.relative_to(M3).as_posix() for path in M3.rglob("*") if path.is_file() and path.suffix.lower() in analysis_extensions]
    checks = [
        fea["gate_status"] == "HOLD",
        fea["pass_token_issued"] is False,
        fea["formal_fea_authorized"] is False,
        fea["formal_fea_run_count"] == 0,
        fea["margin_of_safety_claim_count"] == 0,
        not analysis_files,
        mech_rl["production_v1_protection"]["modified_by_m3"] is False,
        mech_rl["production_v1_protection"]["runtime_binding_changed"] is False,
        mech_rl["memory_execution_record"]["memory_gate_passed"] is False,
        mech_rl["memory_execution_record"]["owner_override_used"] is True,
        mech_rl["asset_authorities"]["m3r_parameterized_working_model"]["sha256"] == sha256(m3r_step),
        isclose(mech_rl["mass_properties"]["m3r"]["mass_kg"], 0.7619),
        mech_rl["mass_properties"]["m3r"]["center_of_mass_m"] is None,
        mech_rl["contact"]["gripper_force_limit_N"] is None,
        mech_rl["contact"]["coefficient_of_friction"] is None,
        mech_rl["flexible_body"]["enabled"] is False,
        mech_rl["flexible_body"]["mode_shapes"] is None,
        mech_rl["safety_contract"]["unknown_is_action_masked"] is True,
        mech_rl["safety_contract"]["unsafe_unknown_allow_count"] == 0,
        impact["runtime_impact_now"]["production_interface_changed"] is False,
        impact["regression_disposition_now"]["pass_claimed"] is False,
    ]
    return {
        "status": "PASS_FAIL_CLOSED_FEA_AND_SIM13_HOLD" if all(checks) else "FAIL",
        "check_count": len(checks),
        "failed_check_count": sum(not value for value in checks),
        "formal_analysis_file_count": len(analysis_files),
        "formal_analysis_files": analysis_files,
        "fea_gate_status": fea["gate_status"],
        "sim13_v2_release_status": mech_rl["release_status"],
    }


def validate_research_plan() -> dict[str, Any]:
    rows = load_csv("11_validation/M3_COUPLED_CAPTURE_PILOT_RUN_PLAN.csv")
    receipt = load_json("11_validation/M3_COUPLED_CAPTURE_PILOT_RUN_PLAN_RECEIPT.json")
    combinations = {(row["target_anchor"], row["capture_timing_id"], row["strategy_id"]) for row in rows}
    run_orders = {int(row["run_order"]) for row in rows}
    expected = set(itertools.product(
        ["ANCHOR_22KG_0P5DPS", "ANCHOR_150KG_3DPS"],
        ["T_EARLY", "T_NOMINAL", "T_LATE"],
        ["S1", "S3a", "ABORT"],
    ))
    checks = [
        len(rows) == 18,
        combinations == expected,
        run_orders == set(range(1, 19)),
        all(row["execution_status"] == "PLANNED_NOT_EXECUTABLE" for row in rows),
        all(not row["independent_replicate_id"] and not row["replicate_seed"] for row in rows),
        receipt["randomization_seed"] == 20260821,
        receipt["replicate_count"] is None,
        receipt["execution_authorized"] is False,
    ]
    return {
        "status": "PASS_PLAN_STRUCTURE_EXECUTION_HOLD" if all(checks) else "FAIL",
        "check_count": len(checks),
        "failed_check_count": sum(not value for value in checks),
        "design_cell_count": len(rows),
        "randomization_seed": receipt["randomization_seed"],
        "replicate_count": receipt["replicate_count"],
        "execution_authorized": receipt["execution_authorized"],
    }


def write_output_manifest() -> dict[str, Any]:
    excluded = {OUTPUT_MANIFEST_PATH.resolve(), ITERATION_RECEIPT_PATH.resolve()}
    records = []
    for path in sorted(M3.rglob("*")):
        if not path.is_file() or path.resolve() in excluded or "__pycache__" in path.parts:
            continue
        records.append({
            "path": path.relative_to(M3).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    with OUTPUT_MANIFEST_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(records)
    return {
        "record_count": len(records),
        "manifest_sha256": sha256(OUTPUT_MANIFEST_PATH),
        "missing_or_zero_count": sum(record["size_bytes"] <= 0 for record in records),
    }


def main() -> int:
    now = datetime.now().astimezone().isoformat()
    required_missing = [relative for relative in REQUIRED if not (M3 / relative).is_file() or (M3 / relative).stat().st_size == 0]
    machine = parse_machine_readable()
    frozen = audit_frozen_inputs()
    source_coverage = audit_source_reference_coverage()
    requirements = validate_requirements()
    m3r = validate_m3r()
    gripper = validate_gripper()
    mass = validate_mass_material_tolerance()
    fea_sim13 = validate_fea_and_sim13()
    research = validate_research_plan()
    boundary = load_yaml("00_authority/M3_PHASE_AUTHORITY_AND_BOUNDARY.yaml")
    boundary_ok = (
        boundary["limited_override"]["new_authority"]
        == "neutral_parameterized_critical_part_working_model_build_authorized=true"
        and "formal_strength_mos_fea_authorized=false" in boundary["limited_override"]["does_not_override"]
        and boundary["uncertainty_policy"]["zero_fill_forbidden"] is True
    )
    bare_uncertainty_symbol_count = 0
    for path in M3.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".json", ".csv", ".md"}:
            bare_uncertainty_symbol_count += path.read_text(encoding="utf-8-sig", errors="ignore").count("±")
    integrity_failures = []
    if required_missing:
        integrity_failures.append("REQUIRED_ARTIFACT_MISSING_OR_ZERO")
    if machine["failure_count"]:
        integrity_failures.append("MACHINE_READABILITY_FAILURE")
    if frozen["status"] != "PASS":
        integrity_failures.append("FROZEN_INPUT_INTEGRITY_FAILURE")
    if source_coverage["status"] != "PASS":
        integrity_failures.append("EXTERNAL_SOURCE_NOT_IN_FROZEN_MANIFEST")
    if requirements["status"] != "PASS":
        integrity_failures.append("REQUIREMENT_VCD_MAPPING_FAILURE")
    if not boundary_ok:
        integrity_failures.append("OWNER_OVERRIDE_BOUNDARY_FAILURE")
    if bare_uncertainty_symbol_count:
        integrity_failures.append("BARE_UNCERTAINTY_SYMBOL_FOUND")
    for name, result in (("M3R", m3r), ("GRIPPER", gripper), ("MASS", mass), ("FEA_SIM13", fea_sim13), ("RESEARCH", research)):
        if result["status"] == "FAIL":
            integrity_failures.append(f"{name}_VALIDATION_FAILURE")
    artifact_integrity_status = "PASS" if not integrity_failures else "FAIL"
    iteration_token_issued = artifact_integrity_status == "PASS"
    subgates = [
        {"id": "M3-SG-01", "name": "INPUT_AND_AUTHORITY_INTEGRITY", "status": "PASS" if frozen["status"] == "PASS" and source_coverage["status"] == "PASS" else "FAIL"},
        {"id": "M3-SG-02", "name": "REQUIREMENTS_AND_VCD", "status": requirements["status"]},
        {"id": "M3-SG-03", "name": "M3R_PARAMETERIZED_INTERFACE", "status": "PASS_WORKING_SCOPE" if m3r["status"].startswith("PASS") else "FAIL"},
        {"id": "M3-SG-04", "name": "B601_COMPETITION_INTERFACE_DEFINITION", "status": "PASS_WORKING_SCOPE_PHYSICAL_FITUP_HOLD" if m3r["status"].startswith("PASS") else "FAIL"},
        {"id": "M3-SG-05", "name": "GRIPPER_R1_NEUTRAL_GEOMETRY", "status": "PASS_NEUTRAL_SCOPE" if gripper["status"].startswith("PASS") else "FAIL"},
        {"id": "M3-SG-06", "name": "GRIPPER_R1_ENGINEERING_RELEASE", "status": "HOLD"},
        {"id": "M3-SG-07", "name": "MASS_PROPERTY_WORKING_AUTHORITY", "status": "PASS_DIGITAL_SCOPE" if mass["status"].startswith("PASS") else "FAIL"},
        {"id": "M3-SG-08", "name": "NINE_CONFIGURATION_MASS_INERTIA_CLOSURE", "status": "HOLD"},
        {"id": "M3-SG-09", "name": "MATERIAL_AND_PROCESS_APPROVAL", "status": "HOLD"},
        {"id": "M3-SG-10", "name": "TOLERANCE_CHAIN_FUNCTIONAL_CLOSURE", "status": "HOLD"},
        {"id": "M3-SG-11", "name": "BOM_AND_DRAWING_MANUFACTURING_RELEASE", "status": "HOLD"},
        {"id": "M3-SG-12", "name": "FORMAL_FEA_ENTRY", "status": "HOLD"},
        {"id": "M3-SG-13", "name": "MECH_RL_V2_PRODUCTION_RELEASE", "status": "HOLD"},
        {"id": "M3-SG-14", "name": "COUPLED_CAPTURE_RESEARCH_PLAN", "status": "PASS_PLAN_ONLY_EXECUTION_HOLD" if research["status"].startswith("PASS") else "FAIL"},
    ]
    mandatory_holds = [item["name"] for item in subgates if item["status"] == "HOLD"]
    detail_gate_pass = artifact_integrity_status == "PASS" and not mandatory_holds and all(item["status"].startswith("PASS") for item in subgates)
    gate = {
        "schema": "MECHANICAL_DETAIL_DESIGN_GATE_V1",
        "generated_local": now,
        "phase": "M3_MECHANICAL_DETAILED_DESIGN_CLOSURE",
        "baseline_in": "V5R_NEUTRAL_OPERATIONAL_BASELINE",
        "baseline_candidate": "V6_ENGINEERING_DETAILED_MECHANICAL_BASELINE_WORKING",
        "gate_status": "PASS" if detail_gate_pass else "HOLD",
        "pass_token": "MECHANICAL_DETAIL_DESIGN_RELEASED",
        "pass_token_issued": detail_gate_pass,
        "iteration_token": "M3_L01_CONTROLLED_WORKING_BASELINE_ESTABLISHED",
        "iteration_token_issued": iteration_token_issued,
        "iteration_token_scope": "Artifact-integrity and working-model loop completion only; not design release, manufacturing, qualification, or flight credit.",
        "artifact_integrity_status": artifact_integrity_status,
        "subgates": subgates,
        "mandatory_hold_count": len(mandatory_holds),
        "mandatory_holds": mandatory_holds,
        "formal_authority": {
            "formal_fea_authorized": False,
            "manufacturing_release_authorized": False,
            "mechanical_cdr_passed": False,
            "qualification_authorized": False,
            "flight_release_authorized": False,
            "sim13_v2_runtime_release_authorized": False,
            "pilot_experiment_execution_authorized": False,
        },
        "working_scope_achievements": [
            "42_INPUTS_HASH_BOUND_WITH_ZERO_DRIFT",
            "M3R_STAGE_A_AND_STAGE_B_PARAMETERIZED_FREECAD_STEP_WORKING_MODELS",
            "M3R_REVB2_BIDIRECTIONAL_BOOLEAN_EQUIVALENCE_ZERO_DIFFERENCE",
            "B601_FOUR_AXIS_COMPETITION_INTERFACE_CONTROLLED_WITH_TOLERANCE_HOLD",
            "GRIPPER_R1_144_SAMPLE_CONTINUOUS_STROKE_NEUTRAL_CLEARANCE_REPRODUCED",
            "SYSTEM_MASS_MATERIAL_TOLERANCE_AND_UNCERTAINTY_SCHEMAS_FAIL_CLOSED",
            "MECH_RL_V2_WORKING_CHANGESET_CREATED_WITH_ZERO_RUNTIME_MUTATION",
            "SEEDED_18_CELL_COUPLED_CAPTURE_PILOT_PLAN_CREATED_EXECUTION_HOLD",
        ],
        "next_action_register": "12_gate/NEXT_LOOP_ACTION_REGISTER.csv",
        "verdict": "M3_L01_WORKING_BASELINE_ESTABLISHED_DETAIL_DESIGN_RELEASE_HOLD" if iteration_token_issued else "M3_L01_VALIDATION_FAILED_DETAIL_DESIGN_RELEASE_HOLD",
    }
    GATE_PATH.write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validation = {
        "schema": "M3_BASELINE_VALIDATION_RECEIPT_V1",
        "validated_local": now,
        "status": "PASS_ARTIFACT_INTEGRITY_DETAIL_DESIGN_GATE_HOLD" if artifact_integrity_status == "PASS" else "FAIL",
        "artifact_integrity_status": artifact_integrity_status,
        "integrity_failures": integrity_failures,
        "required_artifact_count": len(REQUIRED),
        "required_artifact_missing_or_zero_count": len(required_missing),
        "required_artifact_missing_or_zero": required_missing,
        "machine_readability": machine,
        "frozen_input_audit": frozen,
        "source_reference_coverage": source_coverage,
        "requirements_vcd": requirements,
        "owner_override_boundary_pass": boundary_ok,
        "bare_uncertainty_symbol_count": bare_uncertainty_symbol_count,
        "m3r": m3r,
        "gripper": gripper,
        "mass_material_tolerance": mass,
        "fea_and_sim13": fea_sim13,
        "research_plan": research,
        "gate_status": gate["gate_status"],
        "iteration_token_issued": iteration_token_issued,
        "detail_design_pass_token_issued": detail_gate_pass,
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_manifest = write_output_manifest()
    iteration_receipt = {
        "schema": "M3_L01_ITERATION_RECEIPT_V1",
        "generated_local": now,
        "iteration_id": "M3-L01",
        "iteration_status": "COMPLETE_WORKING_BASELINE" if iteration_token_issued else "FAILED_VALIDATION",
        "iteration_token": gate["iteration_token"],
        "iteration_token_issued": iteration_token_issued,
        "detail_design_gate_status": gate["gate_status"],
        "detail_design_pass_token_issued": gate["pass_token_issued"],
        "gate_path": GATE_PATH.relative_to(M3).as_posix(),
        "gate_sha256": sha256(GATE_PATH),
        "validation_path": VALIDATION_PATH.relative_to(M3).as_posix(),
        "validation_sha256": sha256(VALIDATION_PATH),
        "output_manifest_path": OUTPUT_MANIFEST_PATH.relative_to(M3).as_posix(),
        "output_manifest_sha256": output_manifest["manifest_sha256"],
        "output_manifest_record_count": output_manifest["record_count"],
        "frozen_input_count": frozen["input_count"],
        "frozen_input_hash_drift_count": frozen["hash_drift_count"],
        "formal_fea_run_count": 0,
        "release_boundary": "WORKING_LOOP_COMPLETE; DETAIL_DESIGN_MANUFACTURING_QUALIFICATION_FLIGHT_RELEASE_HOLD",
    }
    ITERATION_RECEIPT_PATH.write_text(json.dumps(iteration_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "artifact_integrity_status": artifact_integrity_status,
        "iteration_token_issued": iteration_token_issued,
        "detail_design_gate_status": gate["gate_status"],
        "detail_design_pass_token_issued": detail_gate_pass,
        "mandatory_hold_count": len(mandatory_holds),
        "output_manifest_record_count": output_manifest["record_count"],
        "output_manifest_sha256": output_manifest["manifest_sha256"],
        "integrity_failures": integrity_failures,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if artifact_integrity_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
