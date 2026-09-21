#!/usr/bin/env python3
"""Fail-closed finalizer for the local B601 gripper 2P geometry package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable


PACKAGE = Path(__file__).resolve().parents[1]
RESULTS = PACKAGE / "05_results"
REVIEWS = PACKAGE / "07_reviews"
CONTRACT = PACKAGE / "00_contract" / "GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json"
SOURCE_LOCK = PACKAGE / "00_contract" / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER = PACKAGE / "00_contract" / "URDF_FRAME_AND_STATE_LEDGER_V1.json"
CAD_BRIEF = PACKAGE / "00_contract" / "CAD_BRIEF_V1.md"

SOURCE_RECHECK = RESULTS / "SOURCE_PIN_RECHECK_V1.json"
SOLID_LEDGER = RESULTS / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
FRAME_UNIT_AUDIT = RESULTS / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json"
RUNTIME_RECEIPT = RESULTS / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
INDEPENDENT = RESULTS / "INDEPENDENT_STEP_REOPEN_VALIDATION_V1.json"
NEGATIVES = RESULTS / "NEGATIVE_CONTROLS_V1.json"
DETERMINISM = RESULTS / "FRESH_PROCESS_DETERMINISTIC_REPLAY_V1.json"
PYTEST = RESULTS / "PYTEST_RECEIPT_V1.json"
CAD_INSPECT = RESULTS / "CAD_INSPECT_REFS_SUMMARY_V1.json"
SNAPSHOT = REVIEWS / "CAD_SNAPSHOT_REVIEW_V1.json"
VIEWER = REVIEWS / "CAD_VIEWER_STARTUP_RECEIPT_V1.json"

RECEIPTS = {
    "gripper_link": RESULTS / "B601_GRIPPER_LINK_LOCAL_GEOMETRY_RECEIPT_V1.json",
    "gripper_left": RESULTS / "B601_GRIPPER_LEFT_LOCAL_GEOMETRY_RECEIPT_V1.json",
    "gripper_right": RESULTS / "B601_GRIPPER_RIGHT_LOCAL_GEOMETRY_RECEIPT_V1.json",
}

VERDICT = RESULTS / "ENGINEERING_VERDICT_V1.md"
MANIFEST = RESULTS / "PACKAGE_MANIFEST_V1.csv"
INVENTORY = RESULTS / "PACKAGE_SHA256_INVENTORY_V1.csv"
GATE = RESULTS / "LOCAL_CANDIDATE_GATE_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root was not found")


def strict_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    require(path.is_file(), f"required JSON missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def verify_record(value: dict[str, Any]) -> None:
    candidate = Path(str(value["path"]))
    path = candidate if candidate.is_absolute() else workspace_root() / candidate
    require(path.is_file(), f"recorded file missing: {value['path']}")
    require(path.stat().st_size == int(value["bytes"]), f"recorded byte drift: {value['path']}")
    require(sha256_path(path) == str(value["sha256"]), f"recorded hash drift: {value['path']}")


def all_true(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(item is True for item in value.values())


def source_pin_by_id(lock: dict[str, Any], source_id: str) -> dict[str, Any]:
    rows = [row for row in lock["source_pins"] if row["source_id"] == source_id]
    require(len(rows) == 1, f"source id pin count is not one: {source_id}")
    return rows[0]


def verify_inputs() -> dict[str, Any]:
    contract = strict_json(CONTRACT)
    lock = strict_json(SOURCE_LOCK)
    frame_ledger = strict_json(FRAME_LEDGER)
    require(CAD_BRIEF.is_file(), "CAD brief missing")
    require(len(lock["source_pins"]) == 28, "source lock no longer contains 28 pins")
    for pin in lock["source_pins"]:
        verify_record(pin)
    source_recheck = strict_json(SOURCE_RECHECK)
    require(source_recheck["source_pin_count_verified"] == 28, "source recheck count failed")
    require(source_recheck["all_bytes_and_sha256_match"] is True, "source recheck failed")

    solid_ledger = strict_json(SOLID_LEDGER)
    require(solid_ledger["container_count"] == 3, "container count is not three")
    require(solid_ledger["output_solid_count"] == 60, "output solid count is not 60")
    require(all_true(solid_ledger["checks"]), "solid ledger checks failed")
    expected = {"gripper_link": 12, "gripper_left": 24, "gripper_right": 24}
    receipts: dict[str, Any] = {}
    for name, path in RECEIPTS.items():
        receipt = strict_json(path)
        require(receipt["object_name"] == name, f"receipt object mismatch: {name}")
        require(receipt["geometry"]["solid_count"] == expected[name], f"receipt solid count mismatch: {name}")
        require(all_true(receipt["checks"]), f"receipt checks failed: {name}")
        require(len(receipt["geometry"]["solid_identity"]) == expected[name], f"solid identity count mismatch: {name}")
        require(all(row["brep_valid"] and row["all_shells_closed"] and row["volume_mm3"] > 0.0 for row in receipt["geometry"]["solid_identity"]), f"invalid solid identity row: {name}")
        for field in ("primary_step", "runtime_ply", "runtime_npz", "runtime_stl"):
            verify_record(receipt[field])
        flags = receipt["authority_flags"]
        for flag in (
            "owner_named_state_map_resolved",
            "system_registry_reissued",
            "system_pair_evaluation_authorized",
            "contact_authority",
            "path_search_authorized",
            "parent_mechanical_gate_reissued",
            "next_stage_authorized",
            "release_credit",
        ):
            require(flags[flag] is False, f"forbidden local receipt authority: {name}/{flag}")
        receipts[name] = receipt

    frame_unit = strict_json(FRAME_UNIT_AUDIT)
    require(all_true(frame_unit["checks"]), "frame/unit audit failed")
    runtime = strict_json(RUNTIME_RECEIPT)
    require(runtime["sidecar_is_primary_geometry_authority"] is False, "runtime sidecar became primary authority")
    require(runtime["owner_state_baked"] is False, "runtime sidecar baked an Owner state")
    require(runtime["system_narrowphase_promoted"] is False, "runtime sidecar was promoted")

    independent = strict_json(INDEPENDENT)
    independent_status = any(
        value is True
        for value in (
            independent.get("validation_pass"),
            independent.get("pass"),
            independent.get("formal_gate_pass"),
            independent.get("summary", {}).get("all_checks_pass"),
        )
    ) or "PASS" in str(independent.get("verdict", ""))
    require(independent_status, "independent validation did not pass")
    require(independent.get("validator_independence", {}).get("candidate_builder_imported") is False, "independent validator imported builder")
    require(independent.get("validator_independence", {}).get("candidate_geometry_module_imported") is False, "independent validator imported candidate geometry module")

    negatives = strict_json(NEGATIVES)
    summary = negatives["summary"]
    require(summary["all_controls_caught"] is True, "negative controls failed")
    require(summary["controls_caught"] == summary["controls_required"] == 20, "negative control count failed")
    require(summary["subcases_caught"] == summary["subcases_executed"] == 44, "negative mutation count failed")
    require(negatives["system_invariant_snapshot"]["unchanged"] is True, "negative controls changed system state")

    determinism = strict_json(DETERMINISM)
    require(determinism["status"] == "PASS" and all_true(determinism["checks"]), "fresh-process determinism failed")
    require(len(determinism["step_sha256"]) == 3, "determinism receipt lacks three STEP hashes")
    pytest = strict_json(PYTEST)
    require(pytest["status"] == "PASS" and pytest["tests_failed"] == 0 and pytest["tests_passed"] >= 20, "pytest receipt failed")

    cad_inspect = strict_json(CAD_INSPECT)
    require(cad_inspect["rerun"]["status"] == "PASS" and cad_inspect["rerun"]["entries_passed"] == 3, "CAD inspect failed")
    snapshot = strict_json(SNAPSHOT)
    require(snapshot["visual_review_pass"] is True and all_true(snapshot["checks"]), "CAD snapshot review failed")
    require(len(snapshot["images"]) == 9, "CAD snapshot packet is incomplete")
    for image in snapshot["images"]:
        verify_record({"path": (REVIEWS / image["name"]).relative_to(workspace_root()).as_posix(), "bytes": image["bytes"], "sha256": image["sha256"]})
    viewer = strict_json(VIEWER)
    require(viewer["viewer_started"] is False, "viewer receipt semantics changed")
    require(viewer["disposition"] == "VIEWER_UNAVAILABLE_MISSING_AGENT_START", "viewer failure not disclosed")
    require(viewer["geometry_or_authority_impact"] is False, "viewer failure incorrectly changed geometry authority")

    current = lock["current_system_authority_invariants"]
    contract_current = contract["current_system_authority_invariants"]
    require(
        all(contract_current.get(key) == value for key, value in current.items()),
        "contract/source-lock shared system invariants disagree",
    )
    require(
        contract_current["complete_system_operational_collision_asset_set_bound"] is False,
        "contract unexpectedly claims a complete system asset set",
    )
    registry = strict_json(workspace_root() / source_pin_by_id(lock, "m01_system_collision_registry")["path"])
    prebind = strict_json(workspace_root() / source_pin_by_id(lock, "m01_scene_collision_prebind_gate")["path"])
    parent = strict_json(workspace_root() / source_pin_by_id(lock, "parent_mechanical_release_gate")["path"])
    require(registry["object_summary"]["known_active_object_count"] == 150, "M01 object count drift")
    require(prebind["asset_accounting"]["operational_authority_rows"] == 1, "M01 operational count drift")
    require(prebind["system_execution_state"]["system_pair_queries_executed"] == 0, "M01 pair count drift")
    require(prebind["system_execution_state"]["system_edges_certified"] == 0, "M01 edge count drift")
    require(prebind["system_execution_state"]["path_search_executed"] is False, "M01 path execution drift")
    require(parent["gate_a_pass"] is False and parent["next_stage_authorized"] is False, "parent Gate authority drift")

    return {
        "contract": contract,
        "lock": lock,
        "frame_ledger": frame_ledger,
        "receipts": receipts,
        "independent": independent,
        "negatives": negatives,
        "determinism": determinism,
        "pytest": pytest,
        "cad_inspect": cad_inspect,
        "snapshot": snapshot,
        "viewer": viewer,
        "system": current,
    }


def verdict_bytes() -> bytes:
    text = """# Engineering Verdict — B601 Gripper 2P Operational Proxy V1

## Local result

The three STEP-first local collision-geometry candidates pass the bounded package criteria:

- palm: 12 closed, valid, positive-volume R1 solids in `gripper_link`;
- left finger: 24 frozen B50 solids re-expressed once in `gripper_left`;
- right finger: 24 frozen B50 solids re-expressed once in `gripper_right`.

All 60 output solids reopen successfully. Runtime PLY/NPZ/STL sidecars are owning-link-local metres derived from primary millimetre STEP. Independent validation, 20/20 contractual negative controls (44/44 mutation subcases), fresh-process deterministic replay, tests, CAD refs inspection, and nine-view visual review pass.

## Mandatory HOLD

This package does not resolve the Owner named-configuration-to-travel conflict and does not confirm that all 24 bodies in each finger group move rigidly with that prismatic link. As-built/manufacturing uncertainty is still null and cannot be zero-filled. Contact, strength, hardware effort/rate, system narrowphase promotion, pair evaluation, SAFE, edge, path, parent Gate, next-stage, and release credit remain false.

The CAD Viewer `agent:start` entry point is absent and is disclosed as a presentation-tool failure; it does not replace or invalidate the completed OCP/CAD inspection and snapshot evidence.

## System state preserved

`1/150` operational authority rows, `0/11166` pair queries, `0` SAFE certificates, `0` edges, `0/3` stage instances, and no path search. TMG-4 remains HOLD and G12 remains FAIL.
"""
    return text.encode("utf-8")


def _role(relative: str) -> str:
    if relative.startswith("00_contract/"):
        return "CONTRACT_OR_SOURCE_LOCK"
    if relative.startswith("01_cad/") and relative.endswith(".step"):
        return "PRIMARY_STEP"
    if relative.startswith("01_cad/"):
        return "CAD_VIEWER_SIDECAR"
    if relative.startswith("02_runtime/"):
        return "SECONDARY_RUNTIME_GEOMETRY_M"
    if relative.startswith("04_validation/") or relative.startswith("06_tests/"):
        return "VALIDATION_SOURCE"
    if relative.startswith("07_reviews/"):
        return "CAD_VISUAL_REVIEW"
    if relative.startswith("05_results/"):
        return "MACHINE_EVIDENCE"
    return "DOCUMENTATION_OR_BUILDER"


def csv_inventory(excluded: set[Path]) -> bytes:
    paths = [
        path
        for path in PACKAGE.rglob("*")
        if path.is_file()
        and path.resolve() not in excluded
        and "__pycache__" not in path.parts
        and not path.name.endswith((".pyc", ".tmp"))
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("path", "bytes", "sha256", "role"))
    for path in sorted(paths, key=lambda item: item.relative_to(PACKAGE).as_posix()):
        relative = path.relative_to(PACKAGE).as_posix()
        writer.writerow((relative, path.stat().st_size, sha256_path(path), _role(relative)))
    return stream.getvalue().encode("utf-8")


def build_gate(state: dict[str, Any], manifest_data: bytes, inventory_data: bytes) -> dict[str, Any]:
    criteria = [
        {"id": "LG01", "name": "CONTRACT_AND_28_SOURCE_PINS", "pass": True},
        {"id": "LG02", "name": "THREE_PRIMARY_STEP_CONTAINERS", "pass": True},
        {"id": "LG03", "name": "12_24_24_TOTAL_60_VALID_CLOSED_POSITIVE_SOLIDS", "pass": True},
        {"id": "LG04", "name": "EXACT_SOURCE_MEMBERSHIP_AND_SINGLE_Q0_CHILD_REFRAME", "pass": True},
        {"id": "LG05", "name": "RUNTIME_METRE_SIDECARS_AND_NONZERO_DERATE", "pass": True},
        {"id": "LG06", "name": "OWNER_NAMED_STATE_AND_24_BODY_MOTION_OWNERSHIP_HOLD", "pass": True},
        {"id": "LG07", "name": "INDEPENDENT_STEP_REOPEN_AND_FRAME_VALIDATION", "pass": True},
        {"id": "LG08", "name": "NEGATIVE_CONTROLS_20_OF_20_AND_44_OF_44", "pass": True},
        {"id": "LG09", "name": "FRESH_PROCESS_DETERMINISTIC_REPLAY", "pass": True},
        {"id": "LG10", "name": "PACKAGE_PYTEST", "pass": True},
        {"id": "LG11", "name": "CAD_REFS_PLANES_POSITIONING_AND_NINE_VIEW_REVIEW", "pass": True},
        {"id": "LG12", "name": "CAD_VIEWER_MISSING_ENTRY_POINT_TRUTHFULLY_DISCLOSED", "pass": True},
        {"id": "LG13", "name": "SYSTEM_AUTHORITY_COUNTERS_AND_PARENT_HOLDS_PRESERVED", "pass": True},
    ]
    system = state["system"]
    return {
        "schema": "B601_GRIPPER_2P_LOCAL_CANDIDATE_GATE_V1",
        "as_of_date": "2026-08-28",
        "scope": "THREE_LOCAL_STEP_FIRST_COLLISION_GEOMETRY_CANDIDATES_ONLY",
        "local_candidate_gate_pass": True,
        "classification": "PENDING_OWNER_REVIEW",
        "candidate_objects": [
            {
                "object_id": state["receipts"][name]["object_id"],
                "owning_frame": state["receipts"][name]["primary_step"]["frame"],
                "solid_count": state["receipts"][name]["geometry"]["solid_count"],
                "local_geometry_candidate_pass": True,
                "owner_motion_ownership_confirmed": False,
                "system_registry_bound": False,
            }
            for name in ("gripper_link", "gripper_left", "gripper_right")
        ],
        "criteria": criteria,
        "criteria_passed": len(criteria),
        "criteria_required": len(criteria),
        "verification": {
            "source_pins": "28/28 PASS",
            "solid_reopen": "60/60 PASS",
            "independent_validation": record(INDEPENDENT),
            "negative_controls": "20/20 CONTRACT_CONTROLS; 44/44 MUTATION_SUBCASES",
            "fresh_process_deterministic_replay": record(DETERMINISM),
            "pytest": record(PYTEST),
            "cad_inspect": record(CAD_INSPECT),
            "cad_snapshot_review": record(SNAPSHOT),
            "cad_viewer_startup": record(VIEWER),
        },
        "uncertainty_boundary": {
            "primary_nominal_brep_approximation_mm": 0.0,
            "primary_numeric_derate_mm_per_object": 1.0e-6,
            "runtime_mesh_chordal_derate_mm_per_object": 0.05,
            "runtime_mesh_pair_lower_bound_debit_mm": 0.100002,
            "manufacturing_as_built_derate_mm": None,
            "manufacturing_as_built_status": "MEASUREMENT_PENDING_SYSTEM_BIND_HOLD",
        },
        "owner_holds": {
            "named_configuration_to_2p_travel_map_resolved": False,
            "all_24_solids_per_finger_confirmed_as_one_prismatic_moving_object": False,
            "as_built_geometry_available": False,
        },
        "system_state_preserved": {
            "known_active_object_count": system["active_object_rows"],
            "system_registry_operational_authority_rows": system["asset_level_operational_authority_rows"],
            "system_required_pair_queries": system["required_pair_queries"],
            "system_pair_queries_executed": system["system_pair_queries_executed"],
            "system_safe_certificates": system["system_safe_certificates"],
            "system_edges_certified": system["system_edges_certified"],
            "stage_instances_bound": system["stage_instances_bound"],
            "stage_instances_required": system["stage_instances_required"],
            "system_pair_evaluation_authorized": system["system_pair_evaluation_authorized"],
            "path_search_authorized": system["path_search_authorized"],
            "path_search_executed": system["path_search_executed"],
            "TMG4": "HOLD",
            "G12": "FAIL",
        },
        "package_manifest": {
            "path": MANIFEST.relative_to(workspace_root()).as_posix(),
            "bytes": len(manifest_data),
            "sha256": hashlib.sha256(manifest_data).hexdigest().upper(),
        },
        "package_sha256_inventory": {
            "path": INVENTORY.relative_to(workspace_root()).as_posix(),
            "bytes": len(inventory_data),
            "sha256": hashlib.sha256(inventory_data).hexdigest().upper(),
        },
        "authority_flags": {
            "candidate_geometry_may_be_submitted_for_owner_binding": True,
            "owner_named_state_map_resolved": False,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "contact_authority": False,
            "path_search_authorized": False,
            "parent_mechanical_gate_reissued": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "maximum_legal_claim": "THREE_SOURCE_BOUND_LOCAL_B601_GRIPPER_GEOMETRY_CANDIDATES_BUILT_AND_INDEPENDENTLY_VALIDATED__OWNER_STATE_AND_24_BODY_MOTION_OWNERSHIP_SYSTEM_NARROWPHASE_PAIR_EDGE_PATH_CONTACT_STRENGTH_MANUFACTURING_AND_RELEASE_REMAIN_HELD",
        "verdict": "3_OF_3_LOCAL_STEP_FIRST_GEOMETRY_CANDIDATES_PASS__60_OF_60_BREP_SOLIDS__INDEPENDENT_VALIDATION_PASS__NEGATIVE_20_OF_20_44_OF_44__PENDING_OWNER_24_BODY_MOTION_OWNERSHIP_AND_NAMED_STATE_MAP__ZERO_SYSTEM_PAIR_EDGE_PATH_CONTACT_RELEASE_CREDIT",
    }


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def run(*, check: bool) -> dict[str, Any]:
    state = verify_inputs()
    verdict_data = verdict_bytes()
    if check:
        require(VERDICT.is_file() and VERDICT.read_bytes() == verdict_data, "engineering verdict replay mismatch")
    else:
        atomic_write(VERDICT, verdict_data)

    manifest_data = csv_inventory({MANIFEST.resolve(), INVENTORY.resolve(), GATE.resolve()})
    if check:
        require(MANIFEST.is_file() and MANIFEST.read_bytes() == manifest_data, "package manifest replay mismatch")
    else:
        atomic_write(MANIFEST, manifest_data)

    inventory_data = csv_inventory({INVENTORY.resolve(), GATE.resolve()})
    gate_data = stable_json_bytes(build_gate(state, manifest_data, inventory_data))
    if check:
        require(INVENTORY.is_file() and INVENTORY.read_bytes() == inventory_data, "SHA inventory replay mismatch")
        require(GATE.is_file() and GATE.read_bytes() == gate_data, "local Gate replay mismatch")
    else:
        atomic_write(INVENTORY, inventory_data)
        atomic_write(GATE, gate_data)
    return {
        "status": "PASS",
        "criteria": "13/13",
        "manifest_rows": len(manifest_data.decode("utf-8").splitlines()) - 1,
        "inventory_rows": len(inventory_data.decode("utf-8").splitlines()) - 1,
        "system_pair_queries": 0,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(check=args.check), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
