#!/usr/bin/env python3
"""Read-only independent validator for MECH-TI-01.

Artifact identity: RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL.
This validator never writes, rebuilds, or promotes an upstream artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

import yaml


IDENTITY = "RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL"
VERDICT = "PASS_MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_ONLY"
FORBIDDEN_SUFFIXES = {
    ".step", ".stp", ".fcstd", ".sldprt", ".sldasm", ".slddrw",
    ".stl", ".obj", ".dae", ".glb", ".gltf", ".urdf", ".inp",
    ".odb", ".cae", ".npz", ".npy", ".pyc",
}
TRACKED_PACKAGE_FILES = {
    "README.md",
    "knowledge_contract.yaml",
    "source_registry.yaml",
    "MECH_TI_01_HISTORICAL_MISSING_ORIGINAL_AUDIT_V1.json",
    "MECH_TI_01_AUTHORITY_GRAPH_V1.json",
    "MECH_TI_01_BLOCKER_MATRIX_V1.json",
    "validate_mech_ti_01.py",
    "run_negative_controls.py",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def evaluate(repo_root: Path, package_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    package_root = package_root.resolve()
    checks: list[dict[str, Any]] = []

    def check(check_id: str, name: str, passed: bool, evidence: Any) -> None:
        checks.append({"id": check_id, "name": name, "pass": bool(passed), "evidence": evidence})

    contract = load_yaml(package_root / "knowledge_contract.yaml")
    registry = load_yaml(package_root / "source_registry.yaml")
    history = load_json(package_root / "MECH_TI_01_HISTORICAL_MISSING_ORIGINAL_AUDIT_V1.json")
    graph = load_json(package_root / "MECH_TI_01_AUTHORITY_GRAPH_V1.json")
    matrix = load_json(package_root / "MECH_TI_01_BLOCKER_MATRIX_V1.json")

    identity_values = [
        contract.get("artifact_identity"), registry.get("artifact_identity"),
        history.get("artifact_identity"), graph.get("artifact_identity"),
        matrix.get("artifact_identity"),
    ]
    readme = (package_root / "README.md").read_text(encoding="utf-8")
    check(
        "V01", "all reconstructed artifacts declare the non-historical identity",
        all(value == IDENTITY for value in identity_values) and IDENTITY in readme,
        identity_values,
    )

    historical_manifest = repo_root / next(
        row["path"] for row in registry["sources"] if row["id"] == "A4B2_HISTORICAL_PACKET_MANIFEST"
    )
    with historical_manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        historical_rows = [
            row for row in csv.DictReader(stream)
            if row["relative_path"].startswith("10_research/knowledge_base/spacecraft_mechanical_design/")
        ]
    expected_from_manifest = [
        {"path": row["relative_path"], "bytes": int(row["bytes"]), "sha256": row["sha256"].lower()}
        for row in historical_rows
    ]
    expected_from_audit = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"].lower()}
        for row in history["expected_entries"]
    ]
    check(
        "V02", "historical expected identities exactly match the A4-B2 manifest",
        len(expected_from_manifest) == 10 and expected_from_audit == expected_from_manifest,
        {"manifest_count": len(expected_from_manifest), "audit_count": len(expected_from_audit)},
    )

    history_ok = (
        history.get("expected_entry_count") == 10
        and history.get("exact_bytes_and_sha256_matches_found") == 0
        and history.get("original_content_recovered") is False
        and history.get("historical_text_reconstruction_attempted") is False
        and contract["historical_disposition"]["original_content_recovered"] is False
        and contract["historical_disposition"]["reconstruction_of_missing_prose_allowed"] is False
    )
    check("V03", "missing-original disposition remains fail-closed", history_ok, history.get("disposition"))

    source_results = []
    source_pins_ok = True
    for row in registry["sources"]:
        path = repo_root / row["path"]
        exists = path.is_file()
        size = path.stat().st_size if exists else None
        digest = sha256(path) if exists else None
        passed = exists and size == row["bytes"] and digest == row["sha256"].upper()
        source_pins_ok &= passed
        source_results.append({"id": row["id"], "exists": exists, "bytes": size, "sha256": digest, "pass": passed})
    check("V04", "all current external source pins match bytes and SHA-256", source_pins_ok, source_results)

    registry_ids = [row["id"] for row in registry["sources"]]
    graph_pin_ids = graph.get("source_pin_ids", [])
    check(
        "V05", "authority graph consumes the complete source registry exactly once",
        len(graph_pin_ids) == len(set(graph_pin_ids)) and set(graph_pin_ids) == set(registry_ids),
        {"registry_ids": registry_ids, "graph_pin_ids": graph_pin_ids},
    )

    by_id = {row["id"]: row for row in registry["sources"]}
    a4b2 = load_yaml(repo_root / by_id["A4B2_ENTRY_GATE"]["path"])
    check(
        "V06", "A4-B2 remains knowledge-only with every execution authority false",
        a4b2.get("delivery_class") == "TASKBOOK_AND_KNOWLEDGE_ONLY"
        and all(value is False for value in a4b2.get("authority", {}).values())
        and a4b2.get("next_gate", {}).get("authorized") is False,
        {"delivery_class": a4b2.get("delivery_class"), "authority": a4b2.get("authority"), "next_gate": a4b2.get("next_gate")},
    )

    m7_release = load_json(repo_root / by_id["M7_ENGINEERING_RELEASE_GATE"]["path"])
    hold_criterion = [row["id"] for row in m7_release["criteria"] if row["state"] == "HOLD"]
    check(
        "V07", "M7 engineering release shape and Owner hold are unchanged",
        m7_release.get("totals") == {"PASS": 5, "PASS_WITH_DECLARED_OPEN_ITEM": 12, "HOLD": 1}
        and hold_criterion == ["09"]
        and m7_release.get("review_status") == "PENDING_OWNER_REVIEW"
        and m7_release.get("next_stage_authorized") is False,
        {"totals": m7_release.get("totals"), "hold_criteria": hold_criterion, "review_status": m7_release.get("review_status")},
    )

    m7_v5 = load_json(repo_root / by_id["M7_LOOP_V5_GATE"]["path"])
    check(
        "V08", "M7 Loop V5 remains HOLD with zero released segments",
        m7_v5.get("gate") == "HOLD"
        and m7_v5.get("released_segments") == 0
        and m7_v5.get("next_stage_authorized") is False
        and m7_v5.get("release_credit") is False,
        {key: m7_v5.get(key) for key in ["gate", "released_segments", "next_stage_authorized", "release_credit", "verdict"]},
    )

    frontier = load_json(repo_root / by_id["UNIFIED_R2_EFFECTIVE_FRONTIER"]["path"])
    upstream_prb = [
        {"id": row["id"], "name": row["name"], "state": row["state"], "pass": row["pass"]}
        for row in frontier["effective_criteria"]
    ]
    check(
        "V09", "Unified R2 effective source remains 6/20",
        frontier.get("effective_summary") == {"criteria_total": 20, "pass": 6, "hold": 14}
        and len(upstream_prb) == 20
        and frontier.get("authority_flags", {}).get("next_stage_authorized") is False,
        {"effective_summary": frontier.get("effective_summary"), "technical_verdict": frontier.get("technical_verdict")},
    )
    local_prb = [
        {key: row[key] for key in ["id", "name", "state", "pass"]}
        for row in matrix["prb_matrix"]
    ]
    check(
        "V10", "PRB-01..20 matrix is an exact no-promotion projection",
        local_prb == upstream_prb
        and matrix.get("prb_summary") == {
            "source_id": "UNIFIED_R2_EFFECTIVE_FRONTIER", "criteria_total": 20,
            "pass": 6, "hold": 14, "local_delta": 0,
        },
        {"rows": len(local_prb), "pass": sum(row["pass"] for row in local_prb), "local_delta": matrix.get("prb_summary", {}).get("local_delta")},
    )

    mpi_def = load_json(repo_root / by_id["ROUTE_C_PRODUCT_INPUT_GATE"]["path"])
    mpi_audit = load_json(repo_root / by_id["ROUTE_C_MPI_EVIDENCE_GATE"]["path"])
    audit_by_id = {row["id"]: row for row in mpi_audit["criteria"]}
    upstream_mpi = [
        {
            "id": row["id"], "input": row["input"], "source_state": row["state"],
            "audit_state": audit_by_id[row["id"]]["state"],
            "controlled": audit_by_id[row["id"]]["controlled"],
        }
        for row in mpi_def["criteria"]
    ]
    check(
        "V11", "MPI source gates remain 0/8 controlled",
        mpi_def.get("criteria_total") == 8 and mpi_def.get("criteria_controlled") == 0
        and mpi_audit.get("criteria_total") == 8 and mpi_audit.get("criteria_controlled") == 0
        and mpi_audit.get("criteria_hold") == 8
        and mpi_audit.get("cad_generation_authorized") is False
        and mpi_audit.get("next_stage_authorized") is False,
        {"definition_gate": mpi_def.get("gate"), "audit_gate": mpi_audit.get("gate"), "controlled": mpi_audit.get("criteria_controlled")},
    )
    local_mpi = [
        {key: row[key] for key in ["id", "input", "source_state", "audit_state", "controlled"]}
        for row in matrix["mpi_matrix"]
    ]
    check(
        "V12", "MPI-01..08 matrix is an exact no-promotion projection",
        local_mpi == upstream_mpi
        and matrix.get("mpi_summary", {}).get("criteria_total") == 8
        and matrix.get("mpi_summary", {}).get("controlled") == 0
        and matrix.get("mpi_summary", {}).get("hold") == 8
        and matrix.get("mpi_summary", {}).get("local_delta") == 0,
        {"rows": len(local_mpi), "controlled": sum(row["controlled"] for row in local_mpi)},
    )

    p_registry = load_yaml(repo_root / by_id["ROUTE_C_PHYSICAL_REGISTRY"]["path"])
    upstream_p = [
        {
            "id": row["id"], "quantity": row["quantity"], "unit": row["unit"],
            "value": row["value"], "value_uncertainty": row["value_uncertainty"], "state": row["status"],
        }
        for row in p_registry["registry_entries"]
    ]
    check(
        "V13", "P01-P13 source registry remains 0/13 non-null and 13/13 HOLD",
        p_registry.get("summary", {}).get("entries_total") == 13
        and p_registry.get("summary", {}).get("value_non_null") == 0
        and p_registry.get("summary", {}).get("status_AVAILABLE") == 0
        and p_registry.get("summary", {}).get("status_HOLD") == 13
        and p_registry.get("next_stage_authorized") is False,
        p_registry.get("summary"),
    )
    local_p = [
        {key: row[key] for key in ["id", "quantity", "unit", "value", "value_uncertainty", "state"]}
        for row in matrix["p_matrix"]
    ]
    check(
        "V14", "P01-P13 matrix exactly preserves null values and HOLD states",
        local_p == upstream_p
        and matrix.get("p_summary") == {
            "source_id": "ROUTE_C_PHYSICAL_REGISTRY", "entries_total": 13,
            "value_non_null": 0, "status_available": 0, "status_hold": 13, "local_delta": 0,
        },
        {"rows": len(local_p), "non_null": sum(row["value"] is not None for row in local_p), "holds": sum(row["state"] == "HOLD" for row in local_p)},
    )

    checkpoint = load_json(repo_root / by_id["ROUTE_C_CHECKPOINT_B_GATE"]["path"])
    check(
        "V15", "Checkpoint-B remains HOLD at 2/8 with Route-C CAD prohibited",
        checkpoint.get("checkpoint_outcome") == "HOLD"
        and checkpoint.get("evaluation_integrity", {}).get("summary", {}).get("passed") == 8
        and checkpoint.get("admission", {}).get("summary", {}).get("pass") == 2
        and checkpoint.get("admission", {}).get("summary", {}).get("conditions_total") == 8
        and checkpoint.get("physical_registry", {}).get("value_non_null") == 0
        and checkpoint.get("physical_registry", {}).get("status_HOLD") == 13
        and checkpoint.get("authority_guards", {}).get("route_c_cad_authorized") is False
        and checkpoint.get("next_stage_authorized") is False,
        {"integrity": checkpoint.get("evaluation_integrity", {}).get("summary"), "admission": checkpoint.get("admission", {}).get("summary"), "authority_guards": checkpoint.get("authority_guards")},
    )

    sim13 = load_json(repo_root / by_id["SIM13_CURRENT_BINDING_AUDIT"]["path"])
    sim13_authority = sim13.get("current_authority", {})
    check(
        "V16", "current Sim13 production binding remains invalid and diagnostic-only",
        sim13.get("verdict") == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
        and sim13.get("baseline_mutation_authorized") is False
        and sim13.get("next_stage_authorized") is False
        and sim13_authority.get("mechanical_release") is False
        and sim13_authority.get("production_dynamics_ready") is False
        and sim13_authority.get("physical_contact_ready") is False
        and sim13_authority.get("physics_gated_rl_ready") is False
        and sim13_authority.get("diagnostic_kinematic_bootstrap_only") is True,
        {"verdict": sim13.get("verdict"), "current_authority": sim13_authority},
    )

    handoff = load_json(repo_root / by_id["CURRENT_MECHANICAL_HANDOFF_V2"]["path"])
    check(
        "V17", "current Mechanical-to-Embodied Handoff V2 remains FAIL",
        handoff.get("verdict") == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL"
        and handoff.get("review_status") == "PENDING_OWNER_REVIEW"
        and handoff.get("next_stage_authorized") is False,
        {"verdict": handoff.get("verdict"), "review_status": handoff.get("review_status"), "next_stage_authorized": handoff.get("next_stage_authorized")},
    )

    terminal = load_json(repo_root / by_id["TERMINAL_DECISION_PACK_GATE"]["path"])
    check(
        "V18", "terminal decision join grants no Owner, next-stage, or release authority",
        terminal.get("owner_accepted") is False
        and terminal.get("review_status") == "PENDING_OWNER_REVIEW"
        and terminal.get("next_stage_authorized") is False
        and terminal.get("release_credit") is False
        and terminal.get("terminal_release_candidate_generated") is False,
        {key: terminal.get(key) for key in ["outcome", "owner_accepted", "review_status", "next_stage_authorized", "release_credit", "terminal_release_candidate_generated"]},
    )

    graph_guards = graph.get("authority_guards", {})
    check(
        "V19", "authority graph contains no true promotion or execution guard",
        len(graph_guards) >= 18 and all(value is False for value in graph_guards.values()),
        graph_guards,
    )
    matrix_guards = matrix.get("guard_flags", {})
    check(
        "V20", "blocker matrix contains no true promotion or execution guard",
        len(matrix_guards) >= 18 and all(value is False for value in matrix_guards.values()),
        matrix_guards,
    )

    global_barriers = {row["id"]: row["state"] for row in matrix.get("global_barriers", [])}
    check(
        "V21", "all six global barriers remain non-PASS",
        global_barriers == {"GB-01": "HOLD", "GB-02": "HOLD", "GB-03": "HOLD", "GB-04": "INVALID", "GB-05": "FAIL", "GB-06": "PENDING"},
        global_barriers,
    )

    all_files = [path for path in package_root.rglob("*") if path.is_file()]
    forbidden_files = [str(path.relative_to(package_root)).replace("\\", "/") for path in all_files if path.suffix.lower() in FORBIDDEN_SUFFIXES]
    forbidden_dirs = [str(path.relative_to(package_root)).replace("\\", "/") for path in package_root.rglob("__pycache__") if path.is_dir()]
    check(
        "V22", "package contains no CAD, mesh, URDF, FEA, simulation array, bytecode or cache artifact",
        not forbidden_files and not forbidden_dirs,
        {"forbidden_files": forbidden_files, "forbidden_dirs": forbidden_dirs, "file_count": len(all_files)},
    )

    local_manifest_path = package_root / "MECH_TI_01_SHA256_MANIFEST_V1.csv"
    with local_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        local_rows = list(csv.DictReader(stream))
    local_row_paths = {row["path"] for row in local_rows}
    local_hash_results = []
    local_hash_ok = local_row_paths == TRACKED_PACKAGE_FILES
    for row in local_rows:
        path = package_root / row["path"]
        exists = path.is_file()
        size = path.stat().st_size if exists else None
        digest = sha256(path) if exists else None
        passed = exists and size == int(row["bytes"]) and digest == row["sha256"].upper()
        local_hash_ok &= passed
        local_hash_results.append({"path": row["path"], "bytes": size, "sha256": digest, "pass": passed})
    allowed_untracked = {
        "MECH_TI_01_SHA256_MANIFEST_V1.csv",
        "results/MECH_TI_01_VALIDATION_V1.json",
        "results/MECH_TI_01_NEGATIVE_CONTROLS_V1.json",
        "results/MECH_TI_01_GATE_CHECK_V1.json",
    }
    actual_paths = {str(path.relative_to(package_root)).replace("\\", "/") for path in all_files}
    inventory_ok = actual_paths == TRACKED_PACKAGE_FILES | allowed_untracked
    check(
        "V23", "local package inventory and SHA-256 manifest are exact",
        local_hash_ok and inventory_ok,
        {"hash_results": local_hash_results, "unexpected": sorted(actual_paths - TRACKED_PACKAGE_FILES - allowed_untracked), "missing": sorted((TRACKED_PACKAGE_FILES | allowed_untracked) - actual_paths)},
    )

    gate = load_json(package_root / "results/MECH_TI_01_GATE_CHECK_V1.json")
    false_gate_fields = [
        "historical_original_recovered", "historical_content_reconstructed",
        "m7_hold_upgraded", "unified_r2_pass_count_incremented", "mpi_promoted",
        "p_registry_value_filled", "route_c_cad_authorized", "cad_created",
        "step_created", "mesh_created", "urdf_created", "fea_executed",
        "simulation_executed", "sim13_current_production_binding_valid",
        "mechanical_to_embodied_handoff_v2_pass", "owner_accepted",
        "next_stage_authorized", "release_credit", "scientific_credit",
        "production_dynamics_ready", "physical_contact_ready", "physics_gated_rl_ready",
    ]
    check(
        "V24", "machine Gate is navigation-integrity-only with every authority field false",
        gate.get("artifact_identity") == IDENTITY
        and gate.get("verdict") == VERDICT
        and gate.get("navigation_integrity_pass") is True
        and gate.get("upstream_authority_delta") == 0
        and all(gate.get(field) is False for field in false_gate_fields),
        {"verdict": gate.get("verdict"), "false_fields": {field: gate.get(field) for field in false_gate_fields}},
    )

    validation_record = load_json(package_root / "results/MECH_TI_01_VALIDATION_V1.json")
    negative_record = load_json(package_root / "results/MECH_TI_01_NEGATIVE_CONTROLS_V1.json")
    check(
        "V25", "stored validation and negative-control receipts declare the bounded pass counts",
        validation_record.get("artifact_identity") == IDENTITY
        and validation_record.get("summary") == {"passed": 25, "total": 25, "failed": []}
        and negative_record.get("artifact_identity") == IDENTITY
        and negative_record.get("summary") == {"killed": 12, "total": 12, "survived": []},
        {"validation_summary": validation_record.get("summary"), "negative_summary": negative_record.get("summary")},
    )

    failed = [row["id"] for row in checks if not row["pass"]]
    return {
        "schema": "MECH_TI_01_READ_ONLY_VALIDATION_RESULT_V1",
        "package_id": "MECH-TI-01",
        "artifact_identity": IDENTITY,
        "mode": "READ_ONLY_INDEPENDENT_RECOMPUTATION",
        "summary": {"passed": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "verdict": VERDICT if not failed else "FAIL_MECH_TI_01_INTEGRITY",
        "upstream_files_written": 0,
        "package_files_written": 0,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    default_package = Path(__file__).resolve().parent
    parser.add_argument("--repo-root", type=Path, default=default_package.parents[2])
    parser.add_argument("--package-root", type=Path, default=default_package)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = evaluate(args.repo_root, args.package_root)
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if not result["summary"]["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
