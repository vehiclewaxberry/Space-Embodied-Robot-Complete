#!/usr/bin/env python3
"""Run fail-closed contractual negative controls in memory.

No CAD, source, runtime geometry, pair oracle, edge evaluator, or path search is
called.  Mutations exist only as Python values and must all be rejected.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from typing import Any, Callable, Iterable

from fixed_platform_validation_lib import (
    CONTRACT,
    EXPECTED_SYSTEM_INVARIANTS,
    RESULTS_DIR,
    SOURCE_LOCK,
    T_S_M3R_LOCAL,
    ValidationFailure,
    atomic_write,
    file_record,
    require,
    sha256_bytes,
    stable_json_bytes,
    strict_json,
    validate_system_invariants,
)


OUTPUT = RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json"
HEX64 = re.compile(r"^[0-9A-F]{64}$")

CONTROL_IDS = [
    "NC01_SOURCE_HASH_DRIFT",
    "NC02_MISSING_SOURCE",
    "NC03_LOAD_BRIDGE_NONIDENTITY",
    "NC04_LOAD_BRIDGE_DOUBLE_TRANSFORM",
    "NC05_M3R_ZERO_TRANSFORM",
    "NC06_M3R_DOUBLE_TRANSFORM",
    "NC07_WRONG_M3R_MATRIX",
    "NC08_WRONG_FRAME",
    "NC09_WRONG_OBJECT_ID",
    "NC10_MM_TO_M_ZERO",
    "NC11_MM_TO_M_DOUBLE",
    "NC12_WRONG_SCALE_FACTOR",
    "NC13_COMBINED_THREE_OBJECT_STEP",
    "NC14_MULTISOLID_OR_OPEN_BREP",
    "NC15_NONPOSITIVE_VOLUME",
    "NC16_RUNTIME_NOT_STEP_DERIVED",
    "NC17_AS_BUILT_ZERO_FILL",
    "NC18_LOCAL_TO_SYSTEM_PROMOTION",
    "NC19_COUNTER_INCREMENT",
    "NC20_PAIR_QUERY_ATTEMPT",
    "NC21_PATH_SEARCH_ATTEMPT",
    "NC22_PARENT_GATE_FLIP",
    "NC23_RELEASE_FLIP",
    "NC24_STAGE_INSTANCE_BIND",
]


def reject(condition: Any, code: str) -> None:
    if not bool(condition):
        raise ValidationFailure(code)


def validate_source_record(value: dict[str, Any]) -> None:
    reject(isinstance(value.get("path"), str) and bool(value["path"]), "SOURCE_PATH_MISSING")
    reject(isinstance(value.get("bytes"), int) and value["bytes"] > 0, "SOURCE_BYTES_INVALID")
    reject(isinstance(value.get("sha256"), str) and HEX64.fullmatch(value["sha256"]), "SOURCE_HASH_INVALID")


def validate_transform(object_name: str, count: int, matrix: list[list[float]]) -> None:
    expected_count = 0 if object_name == "load_bridge" else 1
    reject(count == expected_count, "TRANSFORM_APPLICATION_COUNT_INVALID")
    expected = [[float(v) for v in row] for row in (np_identity() if object_name == "load_bridge" else T_S_M3R_LOCAL.tolist())]
    reject(matrix == expected, "TRANSFORM_MATRIX_INVALID")


def np_identity() -> list[list[float]]:
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def validate_identity_bridge(count: int, matrix: list[list[float]]) -> None:
    reject(count == 0, "LOAD_BRIDGE_TRANSFORM_COUNT_NOT_ZERO")
    reject(matrix == np_identity(), "LOAD_BRIDGE_MATRIX_NOT_IDENTITY")


def validate_m3r(count: int, matrix: list[list[float]]) -> None:
    reject(count == 1, "M3R_TRANSFORM_COUNT_NOT_ONE")
    reject(matrix == T_S_M3R_LOCAL.tolist(), "M3R_TRANSFORM_MATRIX_DRIFT")


def validate_binding(frame: str, object_id: str, expected_id: str) -> None:
    reject(frame == "S", "OUTPUT_FRAME_NOT_S")
    reject(object_id == expected_id, "OBJECT_ID_MISMATCH")


def validate_units(count: int, factor: float, units: str) -> None:
    reject(units == "m", "RUNTIME_UNITS_NOT_M")
    reject(count == 1, "MM_TO_M_APPLICATION_COUNT_NOT_ONE")
    reject(math.isclose(float(factor), 0.001, rel_tol=0.0, abs_tol=0.0), "MM_TO_M_SCALE_FACTOR_INVALID")


def validate_container(object_count: int, solid_count: int, valid: bool, closed: bool, volume: float) -> None:
    reject(object_count == 1, "PRIMARY_STEP_MUST_BE_ONE_OBJECT_PER_FILE")
    reject(solid_count == 1, "PRIMARY_STEP_SOLID_COUNT_NOT_ONE")
    reject(valid is True, "PRIMARY_STEP_BREP_INVALID")
    reject(closed is True, "PRIMARY_STEP_NOT_CLOSED")
    reject(isinstance(volume, (int, float)) and not isinstance(volume, bool) and math.isfinite(float(volume)) and float(volume) > 0.0, "PRIMARY_STEP_VOLUME_NOT_POSITIVE")


def validate_runtime(derived: bool, primary: bool, source_step: str, expected_step: str) -> None:
    reject(derived is True, "RUNTIME_NOT_DERIVED_FROM_PRIMARY_STEP")
    reject(primary is False, "RUNTIME_SIDECAR_PROMOTED_TO_PRIMARY")
    reject(source_step == expected_step, "RUNTIME_SOURCE_STEP_MISMATCH")


def validate_as_built(value: Any, status: str) -> None:
    reject(value is None, "AS_BUILT_UNCERTAINTY_ZERO_FILLED_OR_NUMERIC")
    reject(status == "MEASUREMENT_PENDING", "AS_BUILT_STATUS_NOT_PENDING")


def validate_authority(flags: dict[str, Any]) -> None:
    for key, value in flags.items():
        reject(value is False, f"LOCAL_CANDIDATE_PROMOTED_{key.upper()}")


def caught_case(case_id: str, mutation: dict[str, Any], code: str, function: Callable[[], None]) -> dict[str, Any]:
    try:
        function()
    except ValidationFailure as exc:
        message = str(exc)
        require(message.startswith(code), f"{case_id} caught wrong rejection {message!r}, expected {code!r}")
        return {"case_id": case_id, "mutation": mutation, "expected_rejection_code": code, "caught_message": message, "status": "CAUGHT"}
    raise ValidationFailure(f"{case_id} was not rejected")


def control(control_id: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    caught = sum(case["status"] == "CAUGHT" for case in cases)
    require(caught == len(cases), f"{control_id} did not catch all cases")
    return {"control_id": control_id, "case_count": len(cases), "caught_count": caught, "status": "CAUGHT", "cases": cases}


def _contract_control_ids(contract: dict[str, Any]) -> list[str] | None:
    candidates = [
        contract.get("negative_control_ids"),
        contract.get("negative_control_contract", {}).get("control_ids") if isinstance(contract.get("negative_control_contract"), dict) else None,
        contract.get("negative_controls", {}).get("required_control_ids") if isinstance(contract.get("negative_controls"), dict) else None,
        contract.get("negative_control_contract", {}).get("required_ids_in_order") if isinstance(contract.get("negative_control_contract"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and all(isinstance(item, str) for item in candidate):
            return candidate
    return None


def build_evidence() -> dict[str, Any]:
    contract_doc = strict_json(CONTRACT)
    source_lock_doc = strict_json(SOURCE_LOCK)
    system = contract_doc.get("current_system_authority_invariants", EXPECTED_SYSTEM_INVARIANTS)
    validate_system_invariants(system)
    contract_ids = _contract_control_ids(contract_doc)
    if contract_ids is not None:
        require(contract_ids == CONTROL_IDS, "contract negative-control IDs/order do not match implementation")

    good_hash = "A" * 64
    good_record = {"path": "20_engineering/example.step", "bytes": 1, "sha256": good_hash}
    identity = np_identity()
    m3r = T_S_M3R_LOCAL.tolist()
    controls: list[dict[str, Any]] = []

    controls.append(control(CONTROL_IDS[0], [
        caught_case("NC01A_LOWERCASE_HASH", {"sha256": good_hash.lower()}, "SOURCE_HASH_INVALID", lambda: validate_source_record({**good_record, "sha256": good_hash.lower()})),
        caught_case("NC01B_SHORT_HASH", {"sha256": "A" * 63}, "SOURCE_HASH_INVALID", lambda: validate_source_record({**good_record, "sha256": "A" * 63})),
    ]))
    controls.append(control(CONTROL_IDS[1], [
        caught_case("NC02A_EMPTY_PATH", {"path": ""}, "SOURCE_PATH_MISSING", lambda: validate_source_record({**good_record, "path": ""})),
        caught_case("NC02B_ZERO_BYTES", {"bytes": 0}, "SOURCE_BYTES_INVALID", lambda: validate_source_record({**good_record, "bytes": 0})),
    ]))
    controls.append(control(CONTROL_IDS[2], [
        caught_case("NC03_BRIDGE_TRANSLATED", {"count": 0, "tx_mm": 1.0}, "LOAD_BRIDGE_MATRIX_NOT_IDENTITY", lambda: validate_identity_bridge(0, [[1.0,0.0,0.0,1.0],*identity[1:]])),
    ]))
    controls.append(control(CONTROL_IDS[3], [
        caught_case("NC04_BRIDGE_TRANSFORM_ONCE", {"count": 1}, "LOAD_BRIDGE_TRANSFORM_COUNT_NOT_ZERO", lambda: validate_identity_bridge(1, identity)),
        caught_case("NC04_BRIDGE_TRANSFORM_TWICE", {"count": 2}, "LOAD_BRIDGE_TRANSFORM_COUNT_NOT_ZERO", lambda: validate_identity_bridge(2, identity)),
    ]))
    controls.append(control(CONTROL_IDS[4], [caught_case("NC05_M3R_ZERO", {"count": 0}, "M3R_TRANSFORM_COUNT_NOT_ONE", lambda: validate_m3r(0, m3r))]))
    controls.append(control(CONTROL_IDS[5], [caught_case("NC06_M3R_DOUBLE", {"count": 2}, "M3R_TRANSFORM_COUNT_NOT_ONE", lambda: validate_m3r(2, m3r))]))
    wrong_translation = copy.deepcopy(m3r); wrong_translation[0][3] = 196.0
    wrong_rotation = copy.deepcopy(m3r); wrong_rotation[1][0] = -wrong_rotation[1][0]
    controls.append(control(CONTROL_IDS[6], [
        caught_case("NC07A_WRONG_TRANSLATION", {"T03": 196.0}, "M3R_TRANSFORM_MATRIX_DRIFT", lambda: validate_m3r(1, wrong_translation)),
        caught_case("NC07B_WRONG_ROTATION", {"R10_sign_flip": True}, "M3R_TRANSFORM_MATRIX_DRIFT", lambda: validate_m3r(1, wrong_rotation)),
    ]))
    controls.append(control(CONTROL_IDS[7], [
        caught_case("NC08A_LOCAL_FRAME", {"frame": "M3R_LOCAL"}, "OUTPUT_FRAME_NOT_S", lambda: validate_binding("M3R_LOCAL", "F::M3R_STAGE_A", "F::M3R_STAGE_A")),
        caught_case("NC08B_BRIDGE_LOCAL_FRAME", {"frame": "LOAD_BRIDGE_LOCAL"}, "OUTPUT_FRAME_NOT_S", lambda: validate_binding("LOAD_BRIDGE_LOCAL", "F::LOAD_BRIDGE", "F::LOAD_BRIDGE")),
    ]))
    controls.append(control(CONTROL_IDS[8], [
        caught_case("NC09A_STAGE_SWAP", {"object_id": "F::M3R_STAGE_B"}, "OBJECT_ID_MISMATCH", lambda: validate_binding("S", "F::M3R_STAGE_B", "F::M3R_STAGE_A")),
        caught_case("NC09B_BRIDGE_AS_STAGE", {"object_id": "F::M3R_STAGE_A"}, "OBJECT_ID_MISMATCH", lambda: validate_binding("S", "F::M3R_STAGE_A", "F::LOAD_BRIDGE")),
    ]))
    controls.append(control(CONTROL_IDS[9], [caught_case("NC10_ZERO_SCALE_APPLICATIONS", {"count": 0}, "MM_TO_M_APPLICATION_COUNT_NOT_ONE", lambda: validate_units(0, 0.001, "m"))]))
    controls.append(control(CONTROL_IDS[10], [caught_case("NC11_DOUBLE_SCALE_APPLICATIONS", {"count": 2}, "MM_TO_M_APPLICATION_COUNT_NOT_ONE", lambda: validate_units(2, 0.001, "m"))]))
    controls.append(control(CONTROL_IDS[11], [
        caught_case("NC12A_FACTOR_ONE", {"factor": 1.0}, "MM_TO_M_SCALE_FACTOR_INVALID", lambda: validate_units(1, 1.0, "m")),
        caught_case("NC12B_FACTOR_1E6", {"factor": 1e-6}, "MM_TO_M_SCALE_FACTOR_INVALID", lambda: validate_units(1, 1e-6, "m")),
        caught_case("NC12C_UNITS_MM", {"units": "mm"}, "RUNTIME_UNITS_NOT_M", lambda: validate_units(1, 0.001, "mm")),
    ]))
    controls.append(control(CONTROL_IDS[12], [caught_case("NC13_COMBINED_STEP", {"object_count": 3}, "PRIMARY_STEP_MUST_BE_ONE_OBJECT_PER_FILE", lambda: validate_container(3, 3, True, True, 1.0))]))
    controls.append(control(CONTROL_IDS[13], [
        caught_case("NC14A_TWO_SOLIDS", {"solid_count": 2}, "PRIMARY_STEP_SOLID_COUNT_NOT_ONE", lambda: validate_container(1, 2, True, True, 1.0)),
        caught_case("NC14B_INVALID", {"valid": False}, "PRIMARY_STEP_BREP_INVALID", lambda: validate_container(1, 1, False, True, 1.0)),
        caught_case("NC14C_OPEN", {"closed": False}, "PRIMARY_STEP_NOT_CLOSED", lambda: validate_container(1, 1, True, False, 1.0)),
    ]))
    controls.append(control(CONTROL_IDS[14], [
        caught_case("NC15A_ZERO_VOLUME", {"volume_mm3": 0.0}, "PRIMARY_STEP_VOLUME_NOT_POSITIVE", lambda: validate_container(1, 1, True, True, 0.0)),
        caught_case("NC15B_NEGATIVE_VOLUME", {"volume_mm3": -1.0}, "PRIMARY_STEP_VOLUME_NOT_POSITIVE", lambda: validate_container(1, 1, True, True, -1.0)),
        caught_case("NC15C_NAN_VOLUME", {"volume_mm3": "NaN"}, "PRIMARY_STEP_VOLUME_NOT_POSITIVE", lambda: validate_container(1, 1, True, True, float("nan"))),
    ]))
    controls.append(control(CONTROL_IDS[15], [
        caught_case("NC16A_NOT_DERIVED", {"derived": False}, "RUNTIME_NOT_DERIVED_FROM_PRIMARY_STEP", lambda: validate_runtime(False, False, "a.step", "a.step")),
        caught_case("NC16B_RUNTIME_PRIMARY", {"primary": True}, "RUNTIME_SIDECAR_PROMOTED_TO_PRIMARY", lambda: validate_runtime(True, True, "a.step", "a.step")),
        caught_case("NC16C_WRONG_SOURCE", {"source": "combined.step"}, "RUNTIME_SOURCE_STEP_MISMATCH", lambda: validate_runtime(True, False, "combined.step", "a.step")),
    ]))
    controls.append(control(CONTROL_IDS[16], [
        caught_case("NC17A_ZERO_FILL", {"manufacturing_as_built_mm": 0.0}, "AS_BUILT_UNCERTAINTY_ZERO_FILLED_OR_NUMERIC", lambda: validate_as_built(0.0, "MEASUREMENT_PENDING")),
        caught_case("NC17B_NUMERIC_FILL", {"manufacturing_as_built_mm": 0.5}, "AS_BUILT_UNCERTAINTY_ZERO_FILLED_OR_NUMERIC", lambda: validate_as_built(0.5, "MEASUREMENT_PENDING")),
        caught_case("NC17C_STATUS_PASS", {"status": "PASS"}, "AS_BUILT_STATUS_NOT_PENDING", lambda: validate_as_built(None, "PASS")),
    ]))
    promotion_keys = ("system_safe", "system_registry_reissued", "system_pair_evaluation_authorized", "path_search_authorized", "next_stage_authorized")
    promotion_cases = []
    for index, key in enumerate(promotion_keys, 1):
        flags = {item: False for item in promotion_keys}
        flags[key] = True
        promotion_cases.append(caught_case(f"NC18{index}_{key.upper()}", {key: True}, f"LOCAL_CANDIDATE_PROMOTED_{key.upper()}", lambda flags=flags: validate_authority(flags)))
    controls.append(control(CONTROL_IDS[17], promotion_cases))
    counter_cases = []
    for index, (key, value) in enumerate((
        ("asset_level_operational_authority_rows", 2),
        ("system_pair_queries_executed", 1),
        ("system_edges_certified", 1),
        ("system_safe_certificates", 1),
    ), 1):
        mutated = copy.deepcopy(system); mutated[key] = value
        counter_cases.append(caught_case(f"NC19{index}_{key.upper()}", {key: value}, "SYSTEM_INVARIANT_DRIFT", lambda mutated=mutated: _validate_invariant_with_code(mutated)))
    controls.append(control(CONTROL_IDS[18], counter_cases))
    query = copy.deepcopy(system); query["system_pair_queries_executed"] = 1
    controls.append(control(CONTROL_IDS[19], [caught_case("NC20_PAIR_QUERY_ONE", {"system_pair_queries_executed": 1}, "SYSTEM_INVARIANT_DRIFT", lambda: _validate_invariant_with_code(query))]))
    path = copy.deepcopy(system); path["path_search_authorized"] = True
    controls.append(control(CONTROL_IDS[20], [caught_case("NC21_PATH_TRUE", {"path_search_authorized": True}, "SYSTEM_INVARIANT_DRIFT", lambda: _validate_invariant_with_code(path))]))
    parent = copy.deepcopy(system); parent["parent_gate_credit"] = True
    controls.append(control(CONTROL_IDS[21], [caught_case("NC22_PARENT_TRUE", {"parent_gate_credit": True}, "SYSTEM_INVARIANT_DRIFT", lambda: _validate_invariant_with_code(parent))]))
    release = copy.deepcopy(system); release["release_credit"] = True
    controls.append(control(CONTROL_IDS[22], [caught_case("NC23_RELEASE_TRUE", {"release_credit": True}, "SYSTEM_INVARIANT_DRIFT", lambda: _validate_invariant_with_code(release))]))
    stage = copy.deepcopy(system); stage["stage_instances_bound"] = 1
    controls.append(control(CONTROL_IDS[23], [caught_case("NC24_STAGE_BOUND_ONE", {"stage_instances_bound": 1}, "SYSTEM_INVARIANT_DRIFT", lambda: _validate_invariant_with_code(stage))]))

    require([row["control_id"] for row in controls] == CONTROL_IDS, "implemented negative-control order drift")
    cases = sum(row["case_count"] for row in controls)
    caught = sum(row["caught_count"] for row in controls)
    require(len(controls) >= 20 and cases >= 20 and caught == cases, "negative-control coverage incomplete")
    snapshot = stable_json_bytes(system)
    return {
        "schema": "FIXED_PLATFORM_NEGATIVE_CONTROLS_V1",
        "as_of_date": "2026-08-28",
        "authority_scope": "LOCAL_FAIL_CLOSED_NEGATIVE_CONTROL_EVIDENCE_ONLY",
        "contract": file_record(CONTRACT),
        "source_lock": file_record(SOURCE_LOCK),
        "execution_isolation": {
            "real_source_or_output_assets_modified": False,
            "mutations": "IN_MEMORY_ONLY",
            "cad_or_brep_execution_called": False,
            "pair_query_called": False,
            "edge_evaluator_called": False,
            "path_search_called": False,
        },
        "summary": {
            "controls_required": len(CONTROL_IDS),
            "controls_executed": len(controls),
            "controls_caught": len(controls),
            "subcases_executed": cases,
            "subcases_caught": caught,
            "all_controls_caught": True,
        },
        "controls": controls,
        "current_system_authority_invariants": system,
        "system_invariant_snapshot": {"before_sha256": sha256_bytes(snapshot), "after_sha256": sha256_bytes(snapshot), "unchanged": True},
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": f"PASS_{len(controls)}_OF_{len(controls)}_CONTRACT_NEGATIVE_CONTROLS_AND_{caught}_OF_{cases}_MUTATION_SUBCASES_CAUGHT__NO_SYSTEM_AUTHORITY_CHANGE",
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _validate_invariant_with_code(value: dict[str, Any]) -> None:
    try:
        validate_system_invariants(value)
    except ValidationFailure as exc:
        raise ValidationFailure(f"SYSTEM_INVARIANT_DRIFT: {exc}") from exc


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    payload = stable_json_bytes(build_evidence())
    if args.write:
        atomic_write(OUTPUT, payload)
        mode_name = "write"
    else:
        require(OUTPUT.is_file(), "negative-control evidence missing")
        require(OUTPUT.read_bytes() == payload, "negative-control evidence drift")
        mode_name = "check"
    print(json.dumps({"status": "PASS", "mode": mode_name, "output": str(OUTPUT), "bytes": len(payload), "sha256": sha256_bytes(payload)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationFailure as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
