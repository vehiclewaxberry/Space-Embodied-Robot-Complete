#!/usr/bin/env python3
"""Independently validate the Route-C root-static R20 local candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from route_c_r20_validation_lib import (
    BUILD_RECEIPT_PATH,
    CAD_DIR,
    CONTRACT_PATH,
    FRAME_LEDGER_PATH,
    GEOMETRY_INDEX_PATH,
    INDEPENDENT_PATH,
    INDEPENDENT_VALIDATOR,
    PACKAGE,
    R121_SOURCE_AUDIT_PATH,
    RUNTIME_DIR,
    RUNTIME_RECEIPT_PATH,
    SOURCE_INSPECTOR,
    SOURCE_LOCK_PATH,
    VALIDATION_LIB,
    ValidationFailure,
    atomic_write,
    audit_independent_imports,
    compare_expected_to_step,
    file_record,
    locate_freecad_python,
    read_brep,
    read_step,
    require,
    require_relative,
    run_independent_source_extractor,
    sha256_path,
    shape_facts,
    stable_json_bytes,
    strict_json,
    system_state_from_authorities,
    transform_shape_once,
    validate_build_receipts,
    validate_contract_structure,
    validate_frame_and_mount,
    validate_object_mapping,
    validate_runtime_object,
    validate_source_pins,
    verify_record,
    workspace_root,
)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def parse_json_stdout(stdout: str, label: str) -> dict[str, Any]:
    start = stdout.find("{")
    require(start >= 0, f"{label} emitted no JSON object")
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f"{label} emitted invalid JSON: {exc}") from exc


def run_full_r121_source_audit() -> tuple[dict[str, Any], dict[str, Any]]:
    freecad = locate_freecad_python()
    completed = subprocess.run(
        [str(freecad), str(SOURCE_INSPECTOR), "--audit-all"],
        cwd=str(workspace_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    require(completed.returncode == 0, f"R121 source cold-open failed:\n{completed.stdout}\n{completed.stderr}")
    require(not completed.stderr.strip(), f"R121 source cold-open wrote stderr: {completed.stderr}")
    document = parse_json_stdout(completed.stdout, "R121 source cold-open")
    require(document.get("schema") == "ROUTE_C_V9F_R121_SOURCE_TOPOLOGY_AUDIT_V1", "R121 source audit schema drift")
    counts = document.get("counts", {})
    require(counts.get("objects") == counts.get("valid_closed_positive_objects") == 121, "R121 source audit not 121/121")
    require(counts.get("single_solid_objects") == 117, "R121 single-solid count drift")
    require(counts.get("double_solid_objects") == 4 and counts.get("total_solids") == 125, "R121 multi-solid accounting drift")
    require(counts.get("nonidentity_freecad_object_placements") == 53, "R121 FreeCAD placement count drift")
    require(document.get("name_set_cross_check", {}).get("all_four_sets_exactly_equal") is True, "R121 four-source name sets differ")
    require(
        set(document.get("two_solid_source_labels", []))
        == {"RC-GDE-J6-RING-0", "RC-GDE-J6-RING-1", "RC-GDE-J6-RING-2", "RC-GDE-J6-RING-3"},
        "R121 two-solid label set drift",
    )
    require(document.get("object_placement_reapplied") is False, "R121 source audit reapplied FreeCAD Object Placement")
    runtime = {"path": str(freecad), "bytes": freecad.stat().st_size, "sha256": sha256_path(freecad)}
    return document, runtime


def _contract_file_records(build: dict[str, Any]) -> None:
    records = build.get("contract_files")
    require(isinstance(records, dict), "build receipt contract_files missing")
    expected = {
        "root_static_r20_contract": CONTRACT_PATH,
        "frame_and_unit_ledger": FRAME_LEDGER_PATH,
        "source_authority_lock": SOURCE_LOCK_PATH,
    }
    require(set(records) == set(expected), f"build contract file record keys drift: {sorted(records)}")
    for key, path in expected.items():
        verify_record(records[key], path)


def validate_all() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = strict_json(CONTRACT_PATH)
    lock = strict_json(SOURCE_LOCK_PATH)
    ledger = strict_json(FRAME_LEDGER_PATH)
    specs = validate_contract_structure(contract)
    pins = validate_source_pins(lock)
    root = workspace_root()
    registry = strict_json(root / pins["m01_registry"]["path"])
    source_receipt = strict_json(root / pins["v9f_build_receipt"]["path"])
    source_manifest = strict_json(root / pins["v9f_mesh_manifest"]["path"])
    mapping_rows = validate_object_mapping(contract, registry, source_receipt, source_manifest)
    mapping_by_id = {row["object_id"]: row for row in mapping_rows}
    mount = strict_json(root / pins["execution_mount"]["path"])
    matrix = validate_frame_and_mount(ledger, mount)
    build_receipts = validate_build_receipts(contract)
    _contract_file_records(build_receipts["build"])
    geometry_by_id = {row["object_id"]: row for row in build_receipts["geometry"]["objects"]}
    runtime_by_id = {row["object_id"]: row for row in build_receipts["runtime"]["objects"]}
    system_state = system_state_from_authorities(pins)
    independence = audit_independent_imports([INDEPENDENT_VALIDATOR, VALIDATION_LIB, SOURCE_INSPECTOR])

    fcstd_path = root / pins["v9f_fcstd"]["path"]
    source_hash_before = sha256_path(fcstd_path)
    full_audit, freecad_runtime = run_full_r121_source_audit()
    require(sha256_path(fcstd_path) == source_hash_before == pins["v9f_fcstd"]["sha256"], "FCStd changed during full source audit")

    object_rows = []
    boolean_available_count = 0
    with tempfile.TemporaryDirectory(prefix="route_c_r20_independent_source_") as directory_name:
        directory = Path(directory_name)
        extraction, extraction_runtime = run_independent_source_extractor(directory)
        require(extraction_runtime == freecad_runtime, "FreeCAD runtime changed between independent cold opens")
        require(sha256_path(fcstd_path) == source_hash_before, "FCStd changed during R20 extraction")
        extracted = {row["object_id"]: row for row in extraction["objects"]}
        require(set(extracted) == {row["object_id"] for row in specs}, "independent source extraction object set drift")
        for spec in specs:
            object_id = spec["object_id"]
            source_label = spec["source_label"]
            extraction_row = extracted[object_id]
            require(extraction_row.get("source_label") == source_label, f"source extraction label drift: {object_id}")
            require(extraction_row.get("source_frame") == "A0_Q0_REFERENCE" and extraction_row.get("source_unit") == "mm", f"source extraction frame/unit drift: {object_id}")
            require(extraction_row.get("source_shape_object_placement_consumed_separately") is False, f"FreeCAD Object Placement reapplied: {object_id}")
            brep_record = extraction_row["temporary_brep"]
            brep_path = directory / brep_record["filename"]
            require(brep_path.stat().st_size == brep_record["bytes"] and sha256_path(brep_path) == brep_record["sha256"], f"transient BREP record drift: {object_id}")
            source_shape = read_brep(brep_path)
            source_facts = shape_facts(source_shape, context=f"{object_id} independent FCStd BREP")
            source_receipt_row = mapping_by_id[object_id]["receipt"]
            source_receipt_residual = require_relative(
                source_facts["volume_mm3"],
                float(source_receipt_row["volume_mm3"]),
                float(contract["tolerances"]["source_receipt_volume_relative"]),
                f"{object_id} source/receipt volume",
            )
            expected_shape = transform_shape_once(source_shape, matrix)
            expected_facts = shape_facts(expected_shape, context=f"{object_id} independent T_S_A0")
            rigid_volume_residual = require_relative(
                expected_facts["volume_mm3"],
                source_facts["volume_mm3"],
                float(contract["tolerances"]["source_receipt_volume_relative"]),
                f"{object_id} rigid volume",
            )

            step_path = CAD_DIR / spec["output"]
            step_shape, step_roots = read_step(step_path)
            comparison = compare_expected_to_step(expected_shape, step_shape, contract, context=object_id)
            boolean_available_count += int(comparison["boolean_symmetric_difference"]["available"])
            step_record = file_record(step_path)
            geometry_row = geometry_by_id[object_id]
            require(geometry_row.get("source_label") == source_label, f"geometry index label drift: {object_id}")
            require(geometry_row.get("source_shape_object_placement_consumed_separately") is False, f"geometry index Object Placement reapplied: {object_id}")
            verify_record(geometry_row["primary_step"], step_path)
            require(geometry_row.get("transform") == "T_S_A0" and geometry_row.get("transform_application_count") == 1, f"geometry index transform drift: {object_id}")
            require(geometry_row.get("output_frame") == "S" and geometry_row.get("length_unit") == "mm", f"geometry index frame/unit drift: {object_id}")
            triangle_record = mapping_by_id[object_id]["registry"]["geometry"]["narrowphase_candidate"]
            verify_record(triangle_record)

            runtime_stem = Path(spec["output"]).stem.replace("_S_V1", "_S_M_V1")
            runtime_validation = validate_runtime_object(
                object_id=object_id,
                step_path=step_path,
                step_shape=step_shape,
                npz_path=RUNTIME_DIR / f"{runtime_stem}.npz",
                ply_path=RUNTIME_DIR / f"{runtime_stem}.ply",
                stl_path=RUNTIME_DIR / f"{runtime_stem}.stl",
                runtime_receipt_row=runtime_by_id[object_id],
                contract=contract,
            )
            object_rows.append(
                {
                    "object_id": object_id,
                    "source_label": source_label,
                    "registry_parent_frame": spec["parent_frame"],
                    "kind": spec["kind"],
                    "source_transient_brep": brep_record,
                    "source_facts": source_facts,
                    "source_receipt_volume_relative_residual": source_receipt_residual,
                    "freecad_object_placement_reapplied": False,
                    "transform": {
                        "name": "T_S_A0",
                        "application_count": 1,
                        "source_frame": "A0_Q0_REFERENCE",
                        "target_frame": "S",
                        "source_and_target_step_unit": "mm",
                        "rigid_volume_relative_residual": rigid_volume_residual,
                    },
                    "primary_step": step_record,
                    "step_root_transfer": step_roots,
                    "geometry_comparison": comparison,
                    "runtime": runtime_validation,
                    "local_geometry_candidate_pass": True,
                    "system_registry_bound": False,
                    "pair_eligible": False,
                }
            )

    require(len(object_rows) == 20, "independent validation did not complete 20 objects")
    require(boolean_available_count > 0, "Boolean symmetric difference unavailable for all R20 objects")
    checks = {
        "G01_thirteen_source_pins_match": True,
        "G02_contract_object_set_is_exact_registry_root_static_R20": True,
        "G03_four_source_name_sets_match_for_full_R121": True,
        "G04_full_R121_source_topology_is_117_single_4_double_125_solids": True,
        "G05_exact_label_R20_source_extraction_is_20_of_20": True,
        "G06_source_BReps_are_valid_closed_single_positive_20_of_20": True,
        "G07_current_execution_mount_matches_ledger_with_m_to_mm_once": True,
        "G08_T_S_A0_applied_exactly_once_per_object": True,
        "G09_primary_STEP_single_root_reopen_is_20_of_20": True,
        "G10_STEP_topology_volume_area_centroid_and_bbox_match": True,
        "G11_Boolean_symmetric_difference_passes_when_kernel_available": True,
        "G12_runtime_NPZ_is_exact_independent_STEP_tessellation": True,
        "G13_runtime_PLY_matches_NPZ_exactly": True,
        "G14_runtime_STL_matches_NPZ_with_float32_bound": True,
        "G15_runtime_meshes_are_closed_oriented_positive_and_bbox_bounded": True,
        "G16_mm_to_m_scale_is_0p001_once": True,
        "G17_as_built_derate_remains_null": True,
        "G18_builder_receipts_and_all_artifact_records_match": True,
        "G19_validator_did_not_import_or_execute_candidate_builder_core": True,
        "G20_system_1_of_150_0_of_11166_0_of_3_TMG4_G12_holds_preserved": True,
    }
    result = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_INDEPENDENT_STEP_VALIDATION_V1",
        "generated_utc": "DETERMINISTIC_INDEPENDENT_VALIDATION_NO_WALLCLOCK",
        "scope": "R121_UMBRELLA_PHASE_A_ROOT_STATIC_R20_LOCAL_S_FRAME_CANDIDATES_ONLY",
        "validation_pass": all(checks.values()),
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_required": len(checks),
        "source_pin_count": 13,
        "object_count": len(object_rows),
        "valid_closed_positive_primary_STEP_count": len(object_rows),
        "runtime_sidecar_set_count": len(object_rows),
        "runtime_sidecar_artifact_count": 3 * len(object_rows),
        "boolean_symmetric_difference_available_count": boolean_available_count,
        "freecad_runtime": freecad_runtime,
        "source_document_hash_before_after_exact": True,
        "full_R121_source_topology_audit": {
            "path": R121_SOURCE_AUDIT_PATH.relative_to(workspace_root()).as_posix(),
            "schema": full_audit["schema"],
            "objects": 121,
            "single_solid_objects": 117,
            "double_solid_objects": 4,
            "total_solids": 125,
        },
        "validator_independence": independence,
        "frame_and_unit_boundary": {
            "source_frame": "A0_Q0_REFERENCE",
            "target_frame": "S",
            "primary_STEP_unit": "mm",
            "runtime_unit": "m",
            "T_S_A0_application_count_per_object": 1,
            "step_to_runtime_scale": 0.001,
            "step_to_runtime_scale_application_count": 1,
        },
        "uncertainty_boundary": {
            "primary_numeric_derate_mm_per_object": ledger["uncertainty_and_derating"]["primary_numeric_derate_mm_per_object"],
            "runtime_mesh_chordal_derate_mm_per_object": ledger["uncertainty_and_derating"]["runtime_mesh_chordal_derate_mm_per_object"],
            "manufacturing_as_built_derate_mm": None,
            "manufacturing_as_built_status": ledger["uncertainty_and_derating"]["manufacturing_as_built_status"],
            "numeric_zero_fill_found": False,
        },
        "objects": object_rows,
        "system_state_preserved": system_state,
        "authority_flags": {
            "system_registry_reissued": False,
            "system_operational_credit": False,
            "system_pair_query_credit": 0,
            "pair_eligible": False,
            "safe_credit": False,
            "edge_credit": False,
            "path_credit": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "remaining_R101": "FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD",
        "maximum_legal_claim": "TWENTY_OF_TWENTY_LOCAL_S_FRAME_STEP_FIRST_ROOT_STATIC_ROUTE_C_COLLISION_GEOMETRY_CANDIDATES_INDEPENDENTLY_VALIDATED__NO_SYSTEM_PAIR_SAFE_EDGE_PATH_OR_RELEASE_CREDIT",
        "verdict": "R20_INDEPENDENT_LOCAL_GEOMETRY_VALIDATION_PASS__20_OF_20_STEP__60_OF_60_RUNTIME__SYSTEM_REMAINS_1_OF_150_AND_0_OF_11166__TMG4_HOLD_G12_FAIL__NO_RELEASE_CREDIT",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return result, full_audit


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result, source_audit = validate_all()
    result_data = stable_json_bytes(result)
    audit_data = stable_json_bytes(source_audit)
    if args.write:
        atomic_write(R121_SOURCE_AUDIT_PATH, audit_data)
        atomic_write(INDEPENDENT_PATH, result_data)
        mode = "write"
    else:
        require(R121_SOURCE_AUDIT_PATH.is_file() and R121_SOURCE_AUDIT_PATH.read_bytes() == audit_data, "R121 source audit drift")
        require(INDEPENDENT_PATH.is_file() and INDEPENDENT_PATH.read_bytes() == result_data, "independent validation receipt drift")
        mode = "check"
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": mode,
                "objects": 20,
                "steps": 20,
                "runtime_sidecars": 60,
                "checks": len(result["checks"]),
                "boolean_available": result["boolean_symmetric_difference_available_count"],
                "system_operational_authority_rows": 1,
                "system_pair_queries": 0,
                "release_credit": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
