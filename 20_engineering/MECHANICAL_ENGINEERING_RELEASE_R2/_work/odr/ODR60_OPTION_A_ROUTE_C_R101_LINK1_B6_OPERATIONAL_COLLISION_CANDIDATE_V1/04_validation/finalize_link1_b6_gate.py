#!/usr/bin/env python3
"""Fail-closed finalizer for the bounded link1 B6 local-candidate package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
RESULTS = PACKAGE / "05_results"
GATE = RESULTS / "LOCAL_CANDIDATE_GATE_V1.json"
INVENTORY = RESULTS / "PACKAGE_INVENTORY_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read(relative: str) -> dict[str, Any]:
    return json.loads((PACKAGE / relative).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def pin(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, document: dict[str, Any]) -> None:
    data = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def criterion(identifier: str, description: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"id": identifier, "description": description, "pass": bool(passed), "evidence": evidence}


def main() -> None:
    contract = read("00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json")
    lock = read("00_contract/SOURCE_AUTHORITY_LOCK_V1.json")
    ledger = read("00_contract/FRAME_UNIT_AND_UNCERTAINTY_LEDGER_V1.json")
    build = read("05_results/SIX_STEP_BUILD_RECEIPT_V1.json")
    geometry = read("05_results/INDEPENDENT_LINK1_B6_VALIDATION_V1.json")
    pose = read("05_results/INDEPENDENT_POSE_ADAPTER_VALIDATION_V1.json")
    runtime = read("05_results/LINK1_B6_RUNTIME_SIDECAR_RECEIPT_V1.json")
    negative = read("05_results/NEGATIVE_CONTROLS_V1.json")
    fresh = read("05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json")
    pytest = read("05_results/PYTEST_RECEIPT_V1.json")
    inspect = read("07_reviews/CAD_INSPECT_REFS_SUMMARY_V1.json")
    snapshots = read("07_reviews/CAD_SNAPSHOT_REVIEW_V1.json")
    cache = read("07_reviews/CAD_CACHE_RELOCATION_RECEIPT_V1.json")
    viewer = read("07_reviews/CAD_VIEWER_STARTUP_RECEIPT_V1.json")
    expected_status = {"operational_geometry_count": "1/150", "pair_queries": "0/11166", "safe_count": 0, "edge_count": 0, "stage_clearance": "0/3", "path_exists": False, "TMG4": "HOLD", "G12": "FAIL", "next_stage_authorized": False, "release_credit": False}
    cad_files = sorted(path for path in (PACKAGE / "01_cad").iterdir() if path.is_file())
    pycache = list(PACKAGE.rglob("__pycache__"))
    primary_steps = sorted((PACKAGE / "01_cad").glob("*.step"))
    runtime_files = sorted(path for path in (PACKAGE / "02_runtime").iterdir() if path.is_file())
    builder_core = primary_steps + runtime_files + [RESULTS / "LINK1_B6_GEOMETRY_INDEX_V1.json", RESULTS / "LINK1_B6_RUNTIME_SIDECAR_RECEIPT_V1.json", RESULTS / "LINK1_B6_POSE_ADAPTER_SAMPLES_V1.json", RESULTS / "SIX_STEP_BUILD_RECEIPT_V1.json"]
    live_pin_count = 0
    for row in lock["source_pins"]:
        path = ROOT / row["path"]
        live_pin_count += int(path.is_file() and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"])
    checks = [
        criterion("G01", "ten source authority pins are live", live_pin_count == 10, f"{live_pin_count}/10"),
        criterion("G02", "exact six registry link1 objects frozen", len(contract["objects"]) == 6, "contract.objects=6"),
        criterion("G03", "source FCStd opened read-only and Object.Placement not reapplied", build["source_document_opened_read_only"] and not build["source_document_saved_or_recomputed"] and not build["source_shape_object_placement_consumed_separately"], build["verdict"]),
        criterion("G04", "six primary STEP candidates emitted", build["objects_emitted"] == build["primary_step_files"] == 6, "6/6"),
        criterion("G05", "independent one-root valid closed positive single-solid checks pass", geometry["object_count"] == 6 and all(row["step_transfer_root_count"] == 1 and row["step_valid_closed_positive_single_solid"] for row in geometry["objects"]), geometry["verdict"]),
        criterion("G06", "independent bilateral BRep difference passes", geometry["bilateral_brep_difference_pass_count"] == 6, "6/6"),
        criterion("G07", "runtime sidecars come from cold-reopened STEP and use one mm-to-m scale", runtime["source"] == "COLD_REOPENED_PRIMARY_STEP_ONLY" and runtime["scale_application_count"] == 1 and runtime["sidecar_artifact_count"] == 18, runtime["verdict"]),
        criterion("G08", "runtime meshes are closed oriented 2-manifolds", geometry["runtime_closed_oriented_two_manifold_pass_count"] == 6, "6/6"),
        criterion("G09", "accepted URDF raw joint1 FK independently matches", pose["validator_imports_builder"] is False and len(pose["samples"]) == 3 and max(row["matrix_max_abs_residual"] for row in pose["samples"]) <= 1e-12, pose["verdict"]),
        criterion("G10", "12dp execution mount consumed directly", not pose["execution_mount_reconstructed_from_25deg"] and not pose["historical_D6_mount_used"], "canonical strings direct"),
        criterion("G11", "q0 A0-to-link1-to-S closure passes", pose["q0_source_A0_to_link1_to_S_closure_max_abs"] <= 1e-12, str(pose["q0_source_A0_to_link1_to_S_closure_max_abs"])),
        criterion("G12", "as-built uncertainty remains unknown", ledger["as_built_uncertainty"]["derate_mm"] is None and ledger["as_built_uncertainty"]["zero_fill_forbidden"], "MEASUREMENT_PENDING"),
        criterion("G13", "negative controls fail closed", negative["case_count"] == negative["pass_count"] == 44 and negative["fail_count"] == 0, negative["verdict"]),
        criterion("G14", "fresh-process replay is deterministic", fresh["artifact_count"] == 28 and fresh["artifacts_after_identical"], fresh["verdict"]),
        criterion("G15", "pytest passes", pytest["exit_code"] == 0 and pytest["passed"] == 10 and pytest["failed"] == 0, pytest["verdict"]),
        criterion("G16", "CAD CLI inspection passes", inspect["responses_ok"] == inspect["requested"] == 6 and inspect["errors_total"] == 0, inspect["verdict"]),
        criterion("G17", "mandatory snapshots are reviewed", snapshots["snapshot_count"] == 6 and snapshots["visual_review_pass"], snapshots["verdict"]),
        criterion("G18", "CAD Viewer handoff was attempted and fallback documented", viewer["attempted"] and not viewer["live_viewer_links_available"] and viewer["fallback"] == "CAD_CLI_INSPECT_AND_SIX_REVIEWED_SNAPSHOTS", viewer["verdict"]),
        criterion("G19", "CAD diagnostic caches are outside primary CAD directory", cache["cache_count"] == 6 and not cache["cache_is_primary_geometry_authority"] and not cache["cache_is_part_of_deterministic_core"], cache["verdict"]),
        criterion("G20", "01_cad contains exactly six STEP and zero other files", len(cad_files) == len(primary_steps) == 6 and all(path.suffix.lower() == ".step" for path in cad_files), f"steps={len(primary_steps)}, other={len(cad_files)-len(primary_steps)}"),
        criterion("G21", "deterministic builder core remains exactly 28 files", len(builder_core) == 28 and all(path.is_file() for path in builder_core), "28/28"),
        criterion("G22", "no Python cache directories remain in package", len(pycache) == 0, f"pycache={len(pycache)}"),
        criterion("G23", "system status remains unchanged and fail-closed", contract["system_status_invariant"] == ledger["system_status_invariant"] == build["system_status_invariant"] == expected_status, json.dumps(expected_status, sort_keys=True)),
        criterion("G24", "no system/pair/edge/path/release credit claimed", build["system_operational_credit"] is False and build["system_pair_query_credit"] == 0 and not build["safe_edge_path_credit"] and not build["release_credit"], "all false/zero"),
    ]
    require(all(row["pass"] for row in checks), f"local gate check failed: {[row['id'] for row in checks if not row['pass']]}")
    excluded = {GATE.resolve(), INVENTORY.resolve()}
    inventory_files = sorted(path for path in PACKAGE.rglob("*") if path.is_file() and path.resolve() not in excluded)
    inventory = {
        "schema": "ROUTE_C_LINK1_B6_PACKAGE_INVENTORY_V1", "generated_utc": "DETERMINISTIC_FINALIZATION_NO_WALLCLOCK",
        "file_count_excluding_inventory_and_gate": len(inventory_files), "files": [pin(path) for path in inventory_files],
        "primary_cad_file_count": len(primary_steps), "deterministic_builder_core_file_count": len(builder_core),
        "diagnostic_cad_cache_count": len(list((PACKAGE / "07_reviews/cad_cache").glob("*.glb"))),
        "diagnostic_cad_cache_is_primary": False, "verdict": "PACKAGE_INVENTORY_FROZEN__SELF_AND_GATE_EXCLUDED",
    }
    write(INVENTORY, inventory)
    gate = {
        "schema": "ROUTE_C_LINK1_B6_LOCAL_CANDIDATE_GATE_V1", "generated_utc": "DETERMINISTIC_FINALIZATION_NO_WALLCLOCK",
        "criteria": checks, "criteria_total": len(checks), "criteria_passed": sum(row["pass"] for row in checks),
        "local_candidate_gate_pass": True, "system_gate_pass": False, "pair_eligible": False,
        "system_status_invariant": expected_status, "system_registry_rows_modified": 0,
        "remaining_R95": "FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD",
        "package_inventory": pin(INVENTORY), "maximum_legal_claim": contract["maximum_legal_claim"],
        "next_stage_authorized": False, "release_credit": False,
        "verdict": "LINK1_B6_LOCAL_CANDIDATE_GATE_24_OF_24_PASS__SYSTEM_REMAINS_1_OF_150_AND_FAIL_CLOSED",
    }
    write(GATE, gate)
    print(json.dumps({"criteria": len(checks), "passed": len(checks), "inventory_files": len(inventory_files), "gate": pin(GATE), "verdict": gate["verdict"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
