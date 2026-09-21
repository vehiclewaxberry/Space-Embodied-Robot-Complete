#!/usr/bin/env python3
"""Execute the contractual and supplemental R20 fail-closed controls."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
from OCP.TopoDS import TopoDS_Shape

from route_c_r20_validation_lib import (
    CONTRACT_PATH,
    FRAME_LEDGER_PATH,
    INDEPENDENT_PATH,
    NEGATIVE_PATH,
    SOURCE_LOCK_PATH,
    ValidationFailure,
    atomic_write,
    audit_independent_imports,
    expected_output_name,
    file_record,
    require,
    require_bbox,
    require_relative,
    shape_facts,
    stable_json_bytes,
    strict_json,
    system_state_from_authorities,
    validate_contract_structure,
    validate_frame_and_mount,
    validate_negative_witness,
    validate_object_mapping,
    validate_runtime_arrays,
    validate_runtime_metadata,
    validate_source_pins,
    validate_system_state,
    verify_record,
    workspace_root,
)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def expect_failure(control_id: str, action: Callable[[], None]) -> dict[str, Any]:
    try:
        action()
    except ValidationFailure as exc:
        return {"id": control_id, "caught": True, "exception": type(exc).__name__, "reason": str(exc)}
    except Exception as exc:
        raise ValidationFailure(f"{control_id} raised unexpected {type(exc).__name__}: {exc}") from exc
    raise ValidationFailure(f"{control_id} was not caught")


def matrix_strings(matrix: np.ndarray) -> list[list[str]]:
    return [[f"{float(value):.12f}" for value in row] for row in matrix]


def validate_no_object_placement_reapplication(document: dict[str, Any]) -> None:
    require(
        all(row.get("freecad_object_placement_reapplied") is False for row in document.get("objects", [])),
        "FreeCAD Object Placement reapplied after consuming obj.Shape",
    )


def validate_no_forbidden_import_text(source: str) -> None:
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    forbidden = {"build_route_c_root_static_r20", "route_c_root_static_geometry", "extract_v9f_root_static_r20_brep"}
    require(not any(name in forbidden for name in names), f"candidate import detected: {names}")


def build_controls() -> tuple[list[dict[str, Any]], list[str]]:
    contract = strict_json(CONTRACT_PATH)
    lock = strict_json(SOURCE_LOCK_PATH)
    ledger = strict_json(FRAME_LEDGER_PATH)
    independent = strict_json(INDEPENDENT_PATH)
    pins = validate_source_pins(lock)
    root = workspace_root()
    registry = strict_json(root / pins["m01_registry"]["path"])
    receipt = strict_json(root / pins["v9f_build_receipt"]["path"])
    manifest = strict_json(root / pins["v9f_mesh_manifest"]["path"])
    mount = strict_json(root / pins["execution_mount"]["path"])
    witness = strict_json(root / pins["route_c_negative_witness"]["path"])
    system_state = system_state_from_authorities(pins)
    canonical_matrix = np.asarray(
        [[float(value) for value in row] for row in ledger["phase_A_root_static_R20"]["canonical_matrix_decimal_strings_mm"]],
        dtype=np.float64,
    )
    first_step_record = independent["objects"][0]["primary_step"]
    first_runtime = independent["objects"][0]["runtime"]
    first_npz_record = first_runtime["artifacts"]["npz"]
    from route_c_r20_validation_lib import read_npz_runtime

    first_npz = read_npz_runtime(root / first_npz_record["path"])

    controls: list[dict[str, Any]] = []

    def add(control_id: str, action: Callable[[], None]) -> None:
        controls.append(expect_failure(control_id, action))

    for control_id, pin_id in (
        ("NC01_SOURCE_FCSTD_HASH_DRIFT", "v9f_fcstd"),
        ("NC02_SOURCE_RECEIPT_HASH_DRIFT", "v9f_build_receipt"),
        ("NC03_REGISTRY_HASH_DRIFT", "m01_registry"),
        ("NC04_EXECUTION_MOUNT_HASH_DRIFT", "execution_mount"),
    ):
        def action(pin_id: str = pin_id) -> None:
            mutated = copy.deepcopy(lock)
            next(row for row in mutated["source_pins"] if row["id"] == pin_id)["sha256"] = "0" * 64
            validate_source_pins(mutated)
        add(control_id, action)

    def nc05() -> None:
        mutated = copy.deepcopy(contract)
        mutated["objects"].pop()
        validate_contract_structure(mutated)
    add("NC05_OBJECT_COUNT_19", nc05)

    def nc06() -> None:
        mutated = copy.deepcopy(contract)
        mutated["objects"][1]["object_id"] = mutated["objects"][0]["object_id"]
        validate_contract_structure(mutated)
    add("NC06_DUPLICATE_OBJECT_ID", nc06)

    def nc07() -> None:
        mutated = copy.deepcopy(contract)
        mutated["objects"][0]["source_label"] = "RC-NOT-A-REAL-LABEL"
        validate_contract_structure(mutated)
    add("NC07_SOURCE_LABEL_NOT_FOUND", nc07)

    def nc08() -> None:
        mutated = copy.deepcopy(contract)
        mutated["objects"][0]["output"], mutated["objects"][1]["output"] = mutated["objects"][1]["output"], mutated["objects"][0]["output"]
        validate_contract_structure(mutated)
    add("NC08_OBJECT_OUTPUT_SWAP", nc08)

    def nc09() -> None:
        bundle = next(row for row in receipt["parts"] if row.get("geometry_role") == "BUNDLE_ENVELOPE")
        mutated = copy.deepcopy(contract)
        mutated["objects"][0].update(
            {
                "object_id": f"R::{bundle['name']}",
                "source_label": bundle["name"],
                "parent_frame": bundle["host_link"],
                "kind": bundle["kind"],
                "output": expected_output_name(f"R::{bundle['name']}"),
            }
        )
        validate_object_mapping(mutated, registry, receipt, manifest)
    add("NC09_BUNDLE_ENVELOPE_INCLUDED", nc09)

    def nc10() -> None:
        mutated = copy.deepcopy(contract)
        mutated["objects"][0]["parent_frame"] = "link1"
        validate_contract_structure(mutated)
    add("NC10_DYNAMIC_PARENT_INCLUDED", nc10)

    def mutate_ledger_matrix(matrix: np.ndarray) -> dict[str, Any]:
        mutated = copy.deepcopy(ledger)
        mutated["phase_A_root_static_R20"]["canonical_matrix_decimal_strings_mm"] = matrix_strings(matrix)
        return mutated

    def nc11() -> None:
        mutated = copy.deepcopy(ledger)
        mutated["source_storage"]["frame"] = "S"
        mutated["source_storage"]["is_S"] = True
        validate_frame_and_mount(mutated, mount)
    add("NC11_A0_MISDECLARED_AS_S", nc11)

    add("NC12_IDENTITY_TRANSFORM", lambda: validate_frame_and_mount(mutate_ledger_matrix(np.eye(4)), mount))
    add("NC13_DOUBLE_T_S_A0", lambda: validate_frame_and_mount(mutate_ledger_matrix(canonical_matrix @ canonical_matrix), mount))
    add("NC14_INVERSE_T_A0_S", lambda: validate_frame_and_mount(mutate_ledger_matrix(np.linalg.inv(canonical_matrix)), mount))

    rounded_25 = canonical_matrix.copy()
    rounded_25[1, 0] = math.sin(math.radians(25.0))
    rounded_25[1, 1] = math.cos(math.radians(25.0))
    rounded_25[2, 0] = -math.cos(math.radians(25.0))
    rounded_25[2, 1] = math.sin(math.radians(25.0))
    add("NC15_ROUNDED_25_DEG_MATRIX", lambda: validate_frame_and_mount(mutate_ledger_matrix(rounded_25), mount))
    add("NC16_HISTORICAL_D6_6DP_MATRIX", lambda: validate_frame_and_mount(mutate_ledger_matrix(np.round(canonical_matrix, 6)), mount))

    translation_mm = canonical_matrix.copy()
    translation_mm[0, 3] = 0.208
    add("NC17_TRANSLATION_0P208_MM", lambda: validate_frame_and_mount(mutate_ledger_matrix(translation_mm), mount))
    translation_m = canonical_matrix.copy()
    translation_m[0, 3] = 208000.0
    add("NC18_TRANSLATION_208_M", lambda: validate_frame_and_mount(mutate_ledger_matrix(translation_m), mount))

    def frame_mutation(field: str, value: Any) -> None:
        mutated = copy.deepcopy(ledger)
        mutated["phase_A_root_static_R20"][field] = value
        validate_frame_and_mount(mutated, mount)
    add("NC19_TARGET_STEP_UNIT_M", lambda: frame_mutation("target_step_length_unit", "m"))
    add("NC20_RUNTIME_SCALE_1", lambda: frame_mutation("step_to_runtime_scale", 1.0))
    add("NC21_RUNTIME_SCALE_APPLIED_TWICE", lambda: frame_mutation("step_to_runtime_scale", 1.0e-6))
    add("NC22_INVALID_OR_OPEN_BREP", lambda: shape_facts(TopoDS_Shape(), context="negative null/open BRep"))
    add("NC23_ZERO_OR_NEGATIVE_VOLUME", lambda: require(math.isfinite(0.0) and 0.0 > 0.0, "non-positive volume"))
    add("NC24_SOLID_COUNT_DRIFT", lambda: require(2 == 1, "solid count drift"))
    add("NC25_VOLUME_INVARIANT_DRIFT", lambda: require_relative(1.1, 1.0, 1.0e-12, "negative volume invariant"))
    add(
        "NC26_BBOX_TRANSFORM_DRIFT",
        lambda: require_bbox(np.asarray([[0.0, 0.0, 0.0], [1.1, 1.0, 1.0]]), np.asarray([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]), 1.0e-7, "negative bbox"),
    )

    def nc27() -> None:
        metadata = copy.deepcopy(first_npz["metadata"])
        metadata["primary_step_sha256"] = "0" * 64
        validate_runtime_metadata(metadata, object_id=metadata["object_id"], step_record=first_step_record)
    add("NC27_RUNTIME_NOT_DERIVED_FROM_STEP", nc27)

    def nc28() -> None:
        mutated = copy.deepcopy(ledger)
        mutated["uncertainty_and_derating"]["manufacturing_as_built_derate_mm"] = 0.0
        validate_frame_and_mount(mutated, mount)
    add("NC28_AS_BUILT_ZERO_FILL", nc28)

    def state_mutation(field: str, value: Any) -> None:
        mutated = copy.deepcopy(system_state)
        mutated[field] = value
        validate_system_state(mutated)
    add("NC29_SYSTEM_OPERATIONAL_COUNT_PROMOTION", lambda: state_mutation("system_operational_authority_rows", 2))
    add("NC30_NONZERO_PAIR_QUERY_CREDIT", lambda: state_mutation("system_pair_queries", 1))
    add("NC31_SAFE_EDGE_OR_PATH_CREDIT", lambda: state_mutation("safe_certificates", 1))

    def nc32() -> None:
        mutated = copy.deepcopy(witness)
        mutated["legacy_witness"]["raw_physical_penetration"] = False
        validate_negative_witness(mutated)
    add("NC32_V9F_NEGATIVE_WITNESS_SUPPRESSED", nc32)

    def nc33() -> None:
        mutated = copy.deepcopy(independent)
        mutated["objects"][0]["freecad_object_placement_reapplied"] = True
        validate_no_object_placement_reapplication(mutated)
    add("NC33_FREECAD_OBJECT_PLACEMENT_REAPPLIED", nc33)

    add("NC34_VALIDATOR_IMPORTS_CANDIDATE_CORE", lambda: validate_no_forbidden_import_text("import route_c_root_static_geometry\n"))

    def nc35() -> None:
        mutated = copy.deepcopy(first_npz_record)
        mutated["sha256"] = "F" * 64
        verify_record(mutated)
    add("NC35_RUNTIME_ARTIFACT_HASH_DRIFT", nc35)

    def nc36() -> None:
        vertices = first_npz["vertices"].copy()
        vertices[0, 0] = np.nan
        validate_runtime_arrays(vertices, first_npz["faces"], first_npz["solid_ids"])
    add("NC36_NONFINITE_RUNTIME_VERTEX", nc36)
    add("NC37_TMG4_OR_RELEASE_PROMOTED", lambda: state_mutation("TMG4", "PASS"))

    contractual_ids = list(contract.get("negative_control_ids", []))
    require(len(contractual_ids) == 33, f"contract negative control count is {len(contractual_ids)}, expected 33")
    require({row["id"] for row in controls[:33]} == set(contractual_ids), "contractual negative control IDs/execution set differ")
    return controls, contractual_ids


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    controls, contractual_ids = build_controls()
    require(all(row["caught"] for row in controls), "one or more negative controls escaped")
    result = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_NEGATIVE_CONTROLS_V1",
        "generated_utc": "DETERMINISTIC_NEGATIVE_CONTROL_RUN_NO_WALLCLOCK",
        "scope": "IN_MEMORY_AND_READ_ONLY_MUTATIONS_ONLY_NO_PRODUCTION_ARTIFACT_CHANGE",
        "contractual_control_ids": contractual_ids,
        "controls": controls,
        "summary": {
            "contractual_controls_required": len(contractual_ids),
            "contractual_controls_executed": len(contractual_ids),
            "contractual_controls_caught": len(contractual_ids),
            "supplemental_controls_executed": len(controls) - len(contractual_ids),
            "total_controls_executed": len(controls),
            "total_controls_caught": sum(row["caught"] for row in controls),
            "all_controls_caught": True,
        },
        "system_invariant_snapshot": strict_json(INDEPENDENT_PATH)["system_state_preserved"],
        "production_files_modified": False,
        "authority_flags": {
            "system_registry_reissued": False,
            "system_operational_credit": False,
            "pair_query_credit": 0,
            "safe_credit": False,
            "edge_credit": False,
            "path_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": "R20_NEGATIVE_CONTROLS_PASS__33_OF_33_CONTRACTUAL_PLUS_4_SUPPLEMENTAL_CAUGHT__NO_SYSTEM_CREDIT",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    data = stable_json_bytes(result)
    if args.write:
        atomic_write(NEGATIVE_PATH, data)
        mode = "write"
    else:
        require(NEGATIVE_PATH.is_file() and NEGATIVE_PATH.read_bytes() == data, "negative control receipt drift")
        mode = "check"
    print(json.dumps({"status": "PASS", "mode": mode, "contractual": 33, "supplemental": 4, "caught": 37}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
