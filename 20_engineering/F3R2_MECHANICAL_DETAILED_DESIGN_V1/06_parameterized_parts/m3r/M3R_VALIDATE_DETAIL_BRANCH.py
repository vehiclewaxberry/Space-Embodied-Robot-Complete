#!/usr/bin/env python3
"""Validate the M3R detailed-design branch without performing structural FEA."""

from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PROJECT = HERE.parents[3]
RECEIPT = HERE / "M3R_DETAIL_BRANCH_VALIDATION_RECEIPT.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def check_unknowns(value, path: str, failures: list[str]) -> None:
    if isinstance(value, dict):
        if value.get("classification") == "UNKNOWN" and value.get("value", None) is not None:
            failures.append(f"UNKNOWN_NOT_NULL:{path}")
        for key, child in value.items():
            check_unknowns(child, f"{path}.{key}", failures)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_unknowns(child, f"{path}[{index}]", failures)


def main() -> None:
    failures: list[str] = []
    required = [
        "02_interfaces/B601_BASE_ADAPTER_REV_C_INTERFACE.yaml",
        "02_interfaces/M3R_INTERFACE_ASSEMBLY_V2.yaml",
        "02_interfaces/M3R_INPUT_AUTHORITY_AUDIT_RECEIPT.json",
        "06_parameterized_parts/m3r/M3R_PARAMETER_DRIVER_V2.json",
        "06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
        "06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
        "06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.FCStd",
        "06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step",
        "06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.FCStd",
        "06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step",
        "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.FCStd",
        "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
        "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json",
        "06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json",
        "06_parameterized_parts/m3r/M3R_FCBAK_DISPOSITION.json",
        "09_drawings/m3r/M3R_DRAWING_REQUIREMENTS_V1.yaml",
        "09_drawings/m3r/M3R_DRAWING_RELEASE_CHECKLIST_V1.csv",
        "09_drawings/m3r/M3R_INTERFACE_REFERENCE_DRAWING_DRAFT.svg",
        "10_bom/M3R_BOM_V2.csv",
    ]
    for relative in required:
        if not (WORKSPACE / relative).is_file():
            failures.append(f"MISSING:{relative}")

    if failures:
        raise SystemExit(";".join(failures))

    json_paths = [
        WORKSPACE / "02_interfaces/M3R_INPUT_AUTHORITY_AUDIT_RECEIPT.json",
        HERE / "M3R_PARAMETER_DRIVER_V2.json",
        HERE / "M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json",
        HERE / "M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json",
        HERE / "M3R_FCBAK_DISPOSITION.json",
    ]
    parsed_json = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in json_paths}
    yaml_paths = [
        WORKSPACE / "02_interfaces/B601_BASE_ADAPTER_REV_C_INTERFACE.yaml",
        WORKSPACE / "02_interfaces/M3R_INTERFACE_ASSEMBLY_V2.yaml",
        HERE / "M3R_STAGE_A_PARAMETER_TABLE.yaml",
        HERE / "M3R_STAGE_B_PARAMETER_TABLE.yaml",
        WORKSPACE / "09_drawings/m3r/M3R_DRAWING_REQUIREMENTS_V1.yaml",
    ]
    parsed_yaml = {path.name: yaml.safe_load(path.read_text(encoding="utf-8")) for path in yaml_paths}
    for name, data in {**parsed_json, **parsed_yaml}.items():
        check_unknowns(data, name, failures)

    driver = parsed_json["M3R_PARAMETER_DRIVER_V2.json"]
    build = parsed_json["M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json"]
    geometry = parsed_json["M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json"]
    audit = parsed_json["M3R_INPUT_AUTHORITY_AUDIT_RECEIPT.json"]
    assembly = parsed_yaml["M3R_INTERFACE_ASSEMBLY_V2.yaml"]

    driver_hash = sha256(HERE / "M3R_PARAMETER_DRIVER_V2.json")
    if driver_hash != build["parameter_driver_sha256"]:
        failures.append("PARAMETER_DRIVER_BUILD_RECEIPT_HASH_MISMATCH")
    if driver_hash != assembly["parameter_authority"]["sha256"]:
        failures.append("PARAMETER_DRIVER_ASSEMBLY_HASH_MISMATCH")
    if driver_hash != audit["working_model_results"]["parameter_driver_sha256"]:
        failures.append("PARAMETER_DRIVER_AUDIT_HASH_MISMATCH")

    for source in audit["source_integrity"]:
        path = PROJECT / source["path"]
        if not path.is_file() or sha256(path) != source["sha256"]:
            failures.append(f"SOURCE_DRIFT:{source['path']}")

    for output in build["outputs"]:
        path = HERE / output["path"]
        if not path.is_file() or sha256(path) != output["sha256"]:
            failures.append(f"OUTPUT_DRIFT:{output['path']}")

    if build["geometry"]["stage_A"]["volume_mm3"] != 127784.800333:
        failures.append("STAGE_A_VOLUME_MISMATCH")
    if build["geometry"]["stage_B"]["volume_mm3"] != 161966.032228:
        failures.append("STAGE_B_VOLUME_MISMATCH")
    if build["geometry"]["assembly_contact"]["common_volume_mm3"] != 0.0:
        failures.append("ASSEMBLY_INTERPENETRATION")
    if build["mass_authority"]["active_assembly_budget_g"] != 761.9:
        failures.append("ACTIVE_MASS_BUDGET_MISMATCH")
    if build["mass_authority"]["measured"] or build["mass_authority"]["installed"]:
        failures.append("BUDGET_MISREPRESENTED_AS_HARDWARE_MASS")
    if build["formal_fea_performed"]:
        failures.append("UNAUTHORIZED_FORMAL_FEA_CLAIM")
    if geometry["verdict"] != "PASS_WORKING_GEOMETRY_EQUIVALENT_TO_PINNED_REVB2":
        failures.append("STEP_GEOMETRY_EQUIVALENCE_HOLD")
    if any(not part["geometrically_equivalent"] for part in geometry["parts"]):
        failures.append("STEP_PART_GEOMETRY_DIFFERENCE")

    with (WORKSPACE / "10_bom/M3R_BOM_V2.csv").open(encoding="utf-8-sig", newline="") as stream:
        bom = list(csv.DictReader(stream))
    if len(bom) != 7:
        failures.append("BOM_ROW_COUNT_NOT_7")
    mass_row = [row for row in bom if row["part_number"] == "M3R_INTERFACE_ASSEMBLY_V2_WORKING"]
    if len(mass_row) != 1 or mass_row[0]["active_mass_each_kg"] != "0.7619" or mass_row[0]["mass_authority"] != "BUDGETED_NOT_MEASURED_NOT_INSTALLED":
        failures.append("BOM_ACTIVE_MASS_AUTHORITY_MISMATCH")

    with (WORKSPACE / "09_drawings/m3r/M3R_DRAWING_RELEASE_CHECKLIST_V1.csv").open(encoding="utf-8-sig", newline="") as stream:
        checklist = list(csv.DictReader(stream))
    if len(checklist) != 15:
        failures.append("DRAWING_CHECKLIST_ROW_COUNT_NOT_15")
    if not any(row["status"] == "HOLD" for row in checklist):
        failures.append("DRAWING_GATE_IMPROPERLY_PASS")
    ET.parse(WORKSPACE / "09_drawings/m3r/M3R_INTERFACE_REFERENCE_DRAWING_DRAFT.svg")

    fcbak_in_workspace = [
        str(path.relative_to(WORKSPACE)).replace("\\", "/")
        for path in WORKSPACE.rglob("*.FCBak")
    ]
    if fcbak_in_workspace:
        failures.extend(f"UNCONTROLLED_FCBAK:{path}" for path in fcbak_in_workspace)

    receipt = {
        "schema": "M3R_DETAIL_BRANCH_VALIDATION_RECEIPT_V1",
        "validated_required_files": len(required),
        "json_documents_parsed": len(json_paths),
        "yaml_documents_parsed": len(yaml_paths),
        "bom_rows": len(bom),
        "drawing_checklist_rows": len(checklist),
        "source_hashes_checked": len(audit["source_integrity"]),
        "generated_output_hashes_checked": len(build["outputs"]),
        "unknown_fields_non_null_failures": [failure for failure in failures if failure.startswith("UNKNOWN_NOT_NULL")],
        "workspace_fcbak_files": fcbak_in_workspace,
        "formal_fea_performed": False,
        "failure_count": len(failures),
        "failures": failures,
        "subgate": "PASS_WORKING_DETAIL_BRANCH_WITH_RELEASE_HOLDS" if not failures else "HOLD_VALIDATION_FAILURE",
        "release_status": "HOLD_NOT_MANUFACTURING_OR_FLIGHT_RELEASE",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(";".join(failures))


if __name__ == "__main__":
    main()
