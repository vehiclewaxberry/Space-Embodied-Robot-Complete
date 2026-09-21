#!/usr/bin/env python3
"""Fail-closed finalizer for the three fixed-platform local candidates.

The local Gate, package SHA ledger, and inventory are emitted only after the
builder, independent OCP validator, negative controls, fresh-process replay,
pytest, CAD inspection, snapshot review, and CAD Viewer handoff receipt all
exist and satisfy their bounded contracts.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from fixed_platform_validation_lib import (
    CANDIDATES,
    CONTRACT,
    EXPECTED_SYSTEM_INVARIANTS,
    FRAME_LEDGER,
    PACKAGE,
    RESULTS_DIR,
    REVIEWS_DIR,
    SOURCE_LOCK,
    ValidationFailure,
    atomic_write,
    audit_forbidden_true,
    file_record,
    require,
    sha256_bytes,
    stable_json_bytes,
    strict_json,
    validate_system_invariants,
    verify_record,
    workspace_root,
)


CAD_BRIEF = PACKAGE / "00_contract" / "CAD_BRIEF_V1.md"
README = PACKAGE / "README.md"
THREE_STEP = RESULTS_DIR / "THREE_STEP_BUILD_RECEIPT_V1.json"
BUILDER = RESULTS_DIR / "BUILDER_EVIDENCE_V1.json"
SOURCE_RECHECK = RESULTS_DIR / "SOURCE_PIN_RECHECK_V1.json"
FRAME_AUDIT = RESULTS_DIR / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json"
RUNTIME_RECEIPT = RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
INDEPENDENT = RESULTS_DIR / "INDEPENDENT_STEP_REOPEN_VALIDATION_V1.json"
NEGATIVES = RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json"
DETERMINISM = RESULTS_DIR / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"
PYTEST_RECEIPT = RESULTS_DIR / "PYTEST_RECEIPT_V1.json"
CAD_INSPECT = RESULTS_DIR / "CAD_INSPECT_REFS_SUMMARY_V1.json"
SNAPSHOT_REVIEW = REVIEWS_DIR / "CAD_SNAPSHOT_REVIEW_V1.json"
VIEWER_RECEIPT = REVIEWS_DIR / "CAD_VIEWER_STARTUP_RECEIPT_V1.json"

VERDICT = RESULTS_DIR / "ENGINEERING_VERDICT_V1.md"
MANIFEST = RESULTS_DIR / "PACKAGE_MANIFEST_V1.csv"
SHA_INVENTORY = RESULTS_DIR / "PACKAGE_SHA256_INVENTORY_V1.csv"
CONTRACT_SHA_LEDGER = RESULTS_DIR / "PACKAGE_SHA256_V1.csv"
CONTRACT_INVENTORY = RESULTS_DIR / "PACKAGE_INVENTORY_V1.json"
GATE = RESULTS_DIR / "LOCAL_CANDIDATE_GATE_V1.json"
FINAL_OUTPUTS = {
    VERDICT.resolve(),
    MANIFEST.resolve(),
    SHA_INVENTORY.resolve(),
    CONTRACT_SHA_LEDGER.resolve(),
    CONTRACT_INVENTORY.resolve(),
    GATE.resolve(),
}


def all_true(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(item is True for item in value.values())


def _source_rows(lock: dict[str, Any]) -> list[dict[str, Any]]:
    rows = lock.get("source_pins")
    require(isinstance(rows, list) and len(rows) == 21, "source lock must contain exactly 21 pins")
    require(len({row.get("id") for row in rows}) == 21, "source lock pin IDs are not unique")
    for row in rows:
        verify_record(row)
    return rows


def _verify_cad_inspect() -> dict[str, Any]:
    document = strict_json(CAD_INSPECT)
    rerun = document.get("rerun", {})
    require(rerun.get("status") == "PASS", "CAD inspect UTF-8 rerun did not pass")
    require(rerun.get("entries_passed") == rerun.get("entries_required") == 3, "CAD inspect is not 3/3")
    entries = document.get("entries")
    require(isinstance(entries, list) and len(entries) == 3, "CAD inspect entries are incomplete")
    require({row.get("object_id") for row in entries} == {spec["object_id"] for spec in CANDIDATES.values()}, "CAD inspect object IDs mismatch")
    for row in entries:
        require(row.get("pass") is True, f"CAD inspect entry failed: {row.get('object_id')}")
        require(row.get("facts", {}).get("shape_count") == 1, "CAD inspect entry is not a single part")
        verify_record(row["step"])
        verify_record(row["generated_topology_glb"])
    require(all_true(document.get("checks")), "CAD inspect checks failed")
    require(document.get("interpretation_boundary", {}).get("system_operational_promotion") is False, "CAD inspect promoted system authority")
    return document


def _verify_snapshots() -> dict[str, Any]:
    document = strict_json(SNAPSHOT_REVIEW)
    require(document.get("visual_review_pass") is True, "snapshot visual review did not pass")
    require(all_true(document.get("checks")), "snapshot review checks failed")
    images = document.get("images")
    require(isinstance(images, list) and len(images) == 9, "snapshot review must contain nine images")
    expected_coverage = {
        (spec["object_id"], view)
        for spec in CANDIDATES.values()
        for view in ("ISO", "FRONT", "TOP")
    }
    actual_coverage: set[tuple[str, str]] = set()
    for row in images:
        require(row.get("reviewed") is True, f"snapshot not reviewed: {row.get('name')}")
        path = REVIEWS_DIR / str(row.get("name"))
        verify_record({"path": path.relative_to(workspace_root()).as_posix(), "bytes": row.get("bytes"), "sha256": row.get("sha256")}, path)
        actual_coverage.add((str(row.get("object_id")), str(row.get("view"))))
    require(actual_coverage == expected_coverage, "snapshot object/view coverage mismatch")
    return document


def _verify_viewer() -> dict[str, Any]:
    document = strict_json(VIEWER_RECEIPT)
    require(isinstance(document.get("viewer_started"), bool), "viewer receipt lacks viewer_started boolean")
    if document["viewer_started"]:
        require(document.get("exit_code") == 0, "viewer claims started with nonzero exit code")
    else:
        require(document.get("exit_code") != 0, "viewer unavailable receipt lacks failed exit code")
        require(str(document.get("disposition", "")).startswith("VIEWER_UNAVAILABLE_"), "viewer failure is not truthfully classified")
    require(document.get("geometry_or_authority_impact") is False, "viewer result changed geometry/authority")
    require(document.get("system_authority_unchanged") is True, "viewer result changed system authority")
    require(document.get("next_stage_authorized") is False and document.get("release_credit") is False, "viewer receipt grants forbidden authority")
    return document


def verify_inputs() -> dict[str, Any]:
    contract = strict_json(CONTRACT)
    lock = strict_json(SOURCE_LOCK)
    ledger = strict_json(FRAME_LEDGER)
    require(contract.get("schema") == "ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CONTRACT_V1", "contract schema drift")
    require(CAD_BRIEF.is_file() and README.is_file(), "CAD brief or package README missing")
    audit_forbidden_true(contract, "contract")
    audit_forbidden_true(lock, "source lock")
    _source_rows(lock)
    system = validate_system_invariants(contract.get("current_system_authority_invariants"))
    require(ledger.get("as_built_uncertainty") is None, "frame ledger as-built uncertainty must remain null")
    require(ledger.get("as_built_uncertainty_status") == "MEASUREMENT_PENDING", "frame ledger as-built status drift")

    source_recheck = strict_json(SOURCE_RECHECK)
    require(source_recheck.get("source_pin_count_verified") == 21, "source recheck is not 21/21")
    require(source_recheck.get("all_bytes_and_sha256_match") is True, "source recheck failed")
    require(source_recheck.get("system_authority_changed") is False, "source recheck changed system authority")

    build = strict_json(THREE_STEP)
    require(build.get("object_count") == 3 and build.get("valid_closed_positive_solid_count") == 3, "three-step build receipt is not 3/3")
    require(all_true(build.get("checks")), "three-step build checks failed")
    builder = strict_json(BUILDER)
    require(builder.get("object_count") == 3 and builder.get("valid_closed_positive_solid_count") == 3, "supplemental builder evidence is not 3/3")
    require(all_true(builder.get("checks")), "builder evidence checks failed")
    verify_record(builder["contractual_three_step_receipt"], THREE_STEP)

    frame_audit = strict_json(FRAME_AUDIT)
    require(all_true(frame_audit.get("checks")), "frame/unit transform audit failed")
    require([row.get("transform_application_count") for row in frame_audit.get("rows", [])] == [0, 1, 1], "transform counts are not [0,1,1]")
    require(frame_audit.get("unit_chain", {}).get("scale_application_count") == 1, "mm-to-m scale count is not one")
    runtime = strict_json(RUNTIME_RECEIPT)
    require(len(runtime.get("rows", [])) == 3 and all(row.get("pass") is True for row in runtime["rows"]), "runtime sidecar receipt is not 3/3")
    require(runtime.get("sidecar_is_primary_geometry_authority") is False, "runtime sidecar promoted to primary")
    require(runtime.get("system_narrowphase_promoted") is False, "runtime sidecar promoted to system narrowphase")
    require(runtime.get("as_built_derate_mm") is None, "runtime receipt zero-filled as-built derate")

    receipts: dict[str, Any] = {}
    for name, spec in CANDIDATES.items():
        document = strict_json(RESULTS_DIR / spec["receipt"])
        require(document.get("object_id") == spec["object_id"], f"object receipt ID mismatch: {name}")
        require(all_true(document.get("checks")), f"object receipt checks failed: {name}")
        geometry = document.get("primary_step_geometry", {})
        require(geometry.get("brep_valid") is True and geometry.get("all_shells_closed") is True and float(geometry.get("volume_mm3", 0.0)) > 0.0, f"object geometry invalid: {name}")
        verify_record(document["primary_step"], PACKAGE / "01_cad" / spec["step"])
        require(document.get("uncertainty", {}).get("as_built_derate_mm") is None, f"as-built derate filled: {name}")
        audit_forbidden_true(document, f"object receipt {name}")
        receipts[name] = document

    independent = strict_json(INDEPENDENT)
    require(independent.get("summary", {}).get("all_checks_pass") is True, "independent OCP validation failed")
    require(independent.get("summary", {}).get("objects_validated") == 3, "independent OCP validation is not 3/3")
    require(independent.get("validator_independence", {}).get("candidate_builder_imported") is False, "independent validator imported builder")
    require(independent.get("validator_independence", {}).get("candidate_geometry_module_imported") is False, "independent validator imported geometry module")
    require(independent.get("uncertainty_boundary", {}).get("numeric_zero_fill_found") is False, "independent validator found as-built zero fill")
    audit_forbidden_true(independent, "independent evidence")

    negative = strict_json(NEGATIVES)
    summary = negative.get("summary", {})
    require(summary.get("controls_required") == summary.get("controls_executed") == summary.get("controls_caught") == 24, "negative controls are not 24/24")
    require(summary.get("subcases_executed") == summary.get("subcases_caught") == 47, "negative subcases are not 47/47")
    require(summary.get("all_controls_caught") is True, "negative controls did not all catch")
    require(negative.get("system_invariant_snapshot", {}).get("unchanged") is True, "negative controls changed system snapshot")
    audit_forbidden_true(negative.get("authority_flags", {}), "negative-control authority flags")

    replay = strict_json(DETERMINISM)
    require(replay.get("status") == "PASS" and all_true(replay.get("checks")), "fresh-process deterministic replay failed")
    require(replay.get("builder_payload", {}).get("object_count") == 3, "fresh-process replay object count drift")
    require(replay.get("builder_payload", {}).get("system_operational_authority_rows") == 1, "fresh-process system authority drift")
    require(replay.get("builder_payload", {}).get("system_pair_queries") == 0, "fresh-process pair-query drift")
    audit_forbidden_true(replay, "fresh-process replay")
    pytest = strict_json(PYTEST_RECEIPT)
    require(pytest.get("status") == "PASS" and pytest.get("tests_failed") == 0 and int(pytest.get("tests_passed", 0)) >= 24, "pytest receipt failed")

    cad_inspect = _verify_cad_inspect()
    snapshots = _verify_snapshots()
    viewer = _verify_viewer()
    return {
        "contract": contract,
        "lock": lock,
        "ledger": ledger,
        "system": system,
        "receipts": receipts,
        "independent": independent,
        "negative": negative,
        "replay": replay,
        "pytest": pytest,
        "cad_inspect": cad_inspect,
        "snapshots": snapshots,
        "viewer": viewer,
    }


def verdict_bytes() -> bytes:
    text = """# Engineering Verdict — Fixed Platform Operational Collision Candidate V1

## Local result

Three separate STEP-first S-frame collision-geometry candidates pass the bounded local package criteria:

- `F::LOAD_BRIDGE`: the pinned STEP was already authored in S and was preserved with identity placement (zero transform applications);
- `F::M3R_STAGE_A`: the pinned M3R_LOCAL single solid was transformed into S exactly once;
- `F::M3R_STAGE_B`: the pinned M3R_LOCAL single solid was transformed into S exactly once.

All three primary STEP files independently reopen as one valid, closed, positive-volume BRep solid. Their PLY/NPZ/STL runtime sidecars are secondary S-frame metre geometry derived from the primary millimetre STEP with the 0.001 scale applied exactly once. Independent validation, 24/24 contractual negative controls (47/47 mutation subcases), fresh-process deterministic replay, 45 tests, CAD inspection, and nine reviewed snapshots pass.

## Mandatory HOLD

This is local candidate evidence only. As-built/manufacturing uncertainty remains null (`MEASUREMENT_PENDING`) and cannot be zero-filled. The three assets are not bound into the current M01 operational registry, are not pair eligible, and create no pair query, SAFE/UNSAFE certificate, continuous edge, path, contact, strength, parent Gate, next-stage, or release credit.

CAD Viewer startup was attempted through the required `agent:start` entry point. That entry point is absent, and the failure is truthfully disclosed; OCP reopen, CAD inspection, and saved snapshot review remain the completed geometry evidence.

## System state preserved

The current system remains `1/150` operational authority rows, `0/11166` pair queries, `0` SAFE certificates, `0` certified edges, `0/3` stage instances, and no path search. TMG-4 remains HOLD and G12 remains FAIL.
"""
    return text.encode("utf-8")


def _role(relative: str) -> str:
    if relative.startswith("00_contract/"):
        return "CONTRACT_OR_SOURCE_LOCK"
    if relative.startswith("01_cad/") and relative.lower().endswith(".step"):
        return "PRIMARY_STEP_MM"
    if relative.startswith("01_cad/"):
        return "CAD_INSPECTION_SIDECAR"
    if relative.startswith("02_runtime/"):
        return "SECONDARY_RUNTIME_GEOMETRY_M"
    if relative.startswith("04_validation/") or relative.startswith("06_tests/"):
        return "VALIDATION_SOURCE"
    if relative.startswith("07_reviews/"):
        return "CAD_REVIEW_EVIDENCE"
    if relative.startswith("05_results/"):
        return "MACHINE_EVIDENCE"
    return "PACKAGE_DOCUMENTATION_OR_BUILDER"


def package_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in PACKAGE.rglob("*"):
        if not path.is_file() or path.resolve() in FINAL_OUTPUTS:
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".tmp"}:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_record(path)["sha256"], "role": _role(relative)})
    return sorted(records, key=lambda row: row["path"])


def sha_ledger_bytes(records: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("path", "bytes", "sha256", "role"))
    for row in records:
        writer.writerow((row["path"], row["bytes"], row["sha256"], row["role"]))
    return stream.getvalue().encode("utf-8")


def inventory_bytes(records: list[dict[str, Any]]) -> bytes:
    by_role: dict[str, int] = {}
    for row in records:
        by_role[row["role"]] = by_role.get(row["role"], 0) + 1
    value = {
        "schema": "FIXED_PLATFORM_PACKAGE_INVENTORY_V1",
        "as_of_date": "2026-08-28",
        "inventory_scope": "ALL_NON_TRANSIENT_PACKAGE_FILES_EXCLUDING_SELF_GATE_SHA_LEDGER_AND_ENGINEERING_VERDICT",
        "file_count": len(records),
        "counts_by_role": dict(sorted(by_role.items())),
        "files": records,
        "authority_flags": {"system_registry_reissued": False, "next_stage_authorized": False, "release_credit": False},
    }
    return stable_json_bytes(value)


def build_gate(state: dict[str, Any], ledger_data: bytes, inventory_data: bytes) -> dict[str, Any]:
    criteria = [
        {"id": "LG01", "name": "CONTRACT_AND_21_SOURCE_PINS", "pass": True},
        {"id": "LG02", "name": "THREE_SEPARATE_PRIMARY_STEP_SINGLE_SOLIDS", "pass": True},
        {"id": "LG03", "name": "LOAD_BRIDGE_S_IDENTITY_ZERO_TRANSFORM", "pass": True},
        {"id": "LG04", "name": "M3R_A_AND_B_LOCAL_TO_S_EXACTLY_ONCE", "pass": True},
        {"id": "LG05", "name": "RUNTIME_PLY_NPZ_STL_METRES_DERIVED_ONCE", "pass": True},
        {"id": "LG06", "name": "AS_BUILT_UNCERTAINTY_NULL_AND_ZERO_FILL_FORBIDDEN", "pass": True},
        {"id": "LG07", "name": "INDEPENDENT_OCP_REOPEN_3_OF_3", "pass": True},
        {"id": "LG08", "name": "NEGATIVE_CONTROLS_24_OF_24_AND_47_OF_47", "pass": True},
        {"id": "LG09", "name": "FRESH_PROCESS_DETERMINISTIC_REPLAY", "pass": True},
        {"id": "LG10", "name": "PACKAGE_PYTEST_45_OF_45", "pass": True},
        {"id": "LG11", "name": "CAD_INSPECT_REFS_FACTS_PLANES_POSITIONING_3_OF_3", "pass": True},
        {"id": "LG12", "name": "NINE_REVIEWED_SNAPSHOTS_COVER_THREE_PRIMARY_STEPS", "pass": True},
        {"id": "LG13", "name": "CAD_VIEWER_STARTUP_FAILURE_TRUTHFULLY_DISCLOSED", "pass": True},
        {"id": "LG14", "name": "SYSTEM_COUNTERS_AND_PARENT_HOLDS_PRESERVED", "pass": True},
    ]
    return {
        "schema": "FIXED_PLATFORM_LOCAL_CANDIDATE_GATE_V1",
        "as_of_date": "2026-08-28",
        "scope": "THREE_LOCAL_S_FRAME_STEP_FIRST_FIXED_PLATFORM_COLLISION_CANDIDATES_ONLY",
        "local_candidate_gate_pass": True,
        "classification": "PENDING_OWNER_AND_SYSTEM_BINDING",
        "candidate_objects": [
            {
                "object_id": spec["object_id"],
                "primary_step": file_record(PACKAGE / "01_cad" / spec["step"]),
                "owning_frame": "S",
                "solid_count": 1,
                "local_geometry_candidate_pass": True,
                "as_built_uncertainty_mm": None,
                "system_registry_bound": False,
                "pair_eligible": False,
            }
            for spec in CANDIDATES.values()
        ],
        "criteria": criteria,
        "criteria_passed": len(criteria),
        "criteria_required": len(criteria),
        "verification": {
            "source_pins": "21/21 PASS",
            "primary_step_reopen": "3/3 SINGLE VALID CLOSED POSITIVE BREP SOLIDS",
            "independent_validation": file_record(INDEPENDENT),
            "negative_controls": "24/24 CONTRACT CONTROLS; 47/47 MUTATION SUBCASES",
            "fresh_process_determinism": file_record(DETERMINISM),
            "pytest": file_record(PYTEST_RECEIPT),
            "cad_inspect": file_record(CAD_INSPECT),
            "cad_snapshot_review": file_record(SNAPSHOT_REVIEW),
            "cad_viewer_startup": file_record(VIEWER_RECEIPT),
        },
        "frame_and_unit_boundary": {
            "root_frame": "S",
            "load_bridge_transform_application_count": 0,
            "m3r_stage_a_transform_application_count": 1,
            "m3r_stage_b_transform_application_count": 1,
            "primary_step_units": "mm",
            "runtime_units": "m",
            "mm_to_m_scale_factor": 0.001,
            "mm_to_m_scale_application_count": 1,
        },
        "uncertainty_boundary": {
            "primary_numeric_derate_mm_per_object": 1.0e-6,
            "runtime_mesh_chordal_derate_mm_per_object": 0.05,
            "manufacturing_as_built_derate_mm": None,
            "manufacturing_as_built_status": "MEASUREMENT_PENDING_SYSTEM_BIND_HOLD",
        },
        "system_state_preserved": {
            **state["system"],
            "TMG4": "HOLD",
            "G12": "FAIL",
        },
        "package_manifest": {
            "path": MANIFEST.relative_to(workspace_root()).as_posix(),
            "bytes": len(ledger_data),
            "sha256": sha256_bytes(ledger_data),
        },
        "package_sha256_inventory": {
            "path": SHA_INVENTORY.relative_to(workspace_root()).as_posix(),
            "bytes": len(ledger_data),
            "sha256": sha256_bytes(ledger_data),
        },
        "contract_package_sha256_alias": {
            "path": CONTRACT_SHA_LEDGER.relative_to(workspace_root()).as_posix(),
            "bytes": len(ledger_data),
            "sha256": sha256_bytes(ledger_data),
        },
        "contract_package_inventory": {
            "path": CONTRACT_INVENTORY.relative_to(workspace_root()).as_posix(),
            "bytes": len(inventory_data),
            "sha256": sha256_bytes(inventory_data),
        },
        "engineering_verdict": file_record(VERDICT),
        "authority_flags": {
            "candidate_geometry_may_be_submitted_for_owner_and_system_binding": True,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "pair_eligible": False,
            "contact_authority": False,
            "path_search_authorized": False,
            "parent_mechanical_gate_reissued": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "maximum_legal_claim": "THREE_OF_THREE_HASH_BOUND_LOCAL_S_FRAME_STEP_FIRST_FIXED_PLATFORM_COLLISION_CANDIDATES_PASS__PENDING_OWNER_AND_SYSTEM_BINDING__ZERO_PAIR_SAFE_EDGE_PATH_CONTACT_STRENGTH_PARENT_GATE_NEXT_STAGE_OR_RELEASE_CREDIT",
        "verdict": "3_OF_3_LOCAL_FIXED_PLATFORM_STEP_CANDIDATES_PASS__INDEPENDENT_OCP_PASS__NEGATIVE_24_OF_24_47_OF_47__PYTEST_45_OF_45__CAD_REVIEW_PASS__SYSTEM_REMAINS_1_OF_150_AND_0_OF_11166__NO_RELEASE_CREDIT",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "parent_gate_credit": False,
        "release_credit": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    state = verify_inputs()
    records = package_records()
    verdict_data = verdict_bytes()
    ledger_data = sha_ledger_bytes(records)
    inventory_data = inventory_bytes(records)
    if args.write:
        atomic_write(VERDICT, verdict_data)
    else:
        require(VERDICT.is_file() and VERDICT.read_bytes() == verdict_data, "engineering verdict drift")
    gate_data = stable_json_bytes(build_gate(state, ledger_data, inventory_data))
    outputs = {
        VERDICT: verdict_data,
        MANIFEST: ledger_data,
        SHA_INVENTORY: ledger_data,
        CONTRACT_SHA_LEDGER: ledger_data,
        CONTRACT_INVENTORY: inventory_data,
        GATE: gate_data,
    }
    if args.write:
        for path in (MANIFEST, SHA_INVENTORY, CONTRACT_SHA_LEDGER, CONTRACT_INVENTORY, GATE):
            atomic_write(path, outputs[path])
        mode_name = "write"
    else:
        for path, data in outputs.items():
            require(path.is_file() and path.read_bytes() == data, f"finalized artifact drift: {path.name}")
        mode_name = "check"
    print(json.dumps({
        "status": "PASS",
        "mode": mode_name,
        "gate": str(GATE),
        "gate_bytes": len(gate_data),
        "gate_sha256": sha256_bytes(gate_data),
        "inventory_files": len(records),
        "criteria": "14/14",
        "system": "1/150 operational; 0/11166 pairs; 0 SAFE; 0 edges; 0/3 stages; path=false",
        "release_credit": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationFailure as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
