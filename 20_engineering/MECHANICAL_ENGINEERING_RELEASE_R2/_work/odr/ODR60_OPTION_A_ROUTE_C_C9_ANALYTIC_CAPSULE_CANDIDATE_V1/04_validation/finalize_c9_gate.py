"""Finalize the bounded local C9 Gate and deterministic package inventory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any


class FinalizeFailure(RuntimeError):
    pass


PACKAGE = Path(__file__).resolve().parents[1]
RESULTS = PACKAGE / "05_results"
GATE = RESULTS / "LOCAL_CANDIDATE_GATE_V1.json"
MANIFEST = RESULTS / "PACKAGE_MANIFEST_V1.csv"
INVENTORY = RESULTS / "PACKAGE_INVENTORY_V1.json"


def root() -> Path:
    for item in Path(__file__).resolve().parents:
        if (item / "PROJECT_MAP.md").is_file():
            return item
    raise FinalizeFailure("root not found")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FinalizeFailure(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           parse_constant=lambda token: (_ for _ in ()).throw(FinalizeFailure(token)))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalizeFailure(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def stable(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def record(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing evidence: {path}")
    return {"path": path.relative_to(root()).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def verify_source_pin(lock: dict[str, Any], name: str) -> Path:
    source = lock.get("sources", {}).get(name)
    require(isinstance(source, dict), f"missing source pin: {name}")
    path = root() / str(source.get("path"))
    require(path.is_file(), f"missing pinned source: {name}")
    require(path.stat().st_size == source.get("bytes"), f"source byte drift: {name}")
    require(sha(path) == source.get("sha256"), f"source hash drift: {name}")
    return path


def current_external_machine_truth(lock: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    names = (
        "current_m01_registry_gate",
        "current_m01_scene_prebind_gate",
        "current_terminal_release_gate",
        "current_mech_to_embodied_handoff_gate",
    )
    paths = {name: verify_source_pin(lock, name) for name in names}
    registry = load(paths["current_m01_registry_gate"])
    prebind = load(paths["current_m01_scene_prebind_gate"])
    release = load(paths["current_terminal_release_gate"])
    handoff = load(paths["current_mech_to_embodied_handoff_gate"])
    require(registry.get("schema") == "SYSTEM_COLLISION_REGISTRY_GATE_V1", "registry schema drift")
    require(prebind.get("schema") == "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1", "prebind schema drift")
    require(release.get("schema") == "TERMINAL_MECHANICAL_GATE_A_V1", "release schema drift")
    require(handoff.get("schema") == "MECH_TO_EMBODIED_HANDOFF_GATE_TERMINAL_V1", "handoff schema drift")
    active_registry = int(registry["known_active_object_count"])
    active_prebind = int(prebind["asset_accounting"]["active_object_rows"])
    require(active_registry == active_prebind, "active-object external truth disagreement")
    pair_queries = int(prebind["system_execution_state"]["system_pair_queries_executed"])
    unassessed = int(registry["pair_coverage"]["status_counts"]["UNASSESSED_FAIL_CLOSED"])
    edges = int(prebind["system_execution_state"]["system_edges_certified"])
    path_executed = bool(prebind["system_execution_state"]["path_search_executed"])
    require(path_executed == bool(registry["path_search_executed"]), "path external truth disagreement")
    tmg4 = [row for row in release["tmg"] if row.get("id") == "TMG-4"]
    require(len(tmg4) == 1, "release Gate has no unique TMG-4")
    require(str(handoff["current_handoff_gate_v2"]["failed"]).startswith("G12 ") and
            handoff["verdict"] == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL",
            "handoff Gate does not prove G12 FAIL")
    next_stage_values = [registry["next_stage_authorized"], prebind["next_stage_authorized"],
                         release["next_stage_authorized"], handoff["next_stage_authorized"]]
    release_values = [registry["release_credit"], prebind["release_credit"],
                      release["release_credit"], handoff["release_credit"]]
    require(pair_queries == 0 and edges == 0, "safe-certificate zero cannot be derived")
    observed = {
        "system_operational_authority_rows": int(prebind["asset_accounting"]["operational_authority_rows"]),
        "known_active_objects": active_registry,
        "system_pair_queries": pair_queries,
        "required_unassessed_pairs": unassessed,
        "safe_certificates": 0,
        "system_edges_certified": edges,
        "stage_instances_bound": int(prebind["scene_accounting"]["stage_instances_bound"]),
        "stage_instances_required": int(prebind["scene_accounting"]["stage_instances_required"]),
        "path_search_executed": path_executed,
        "TMG4": str(tmg4[0]["state"]),
        "G12": "FAIL",
        "next_stage_authorized": any(bool(value) for value in next_stage_values),
        "release_credit": any(bool(value) for value in release_values),
    }
    expected = {
        "system_operational_authority_rows": 1, "known_active_objects": 150,
        "system_pair_queries": 0, "required_unassessed_pairs": 11166,
        "safe_certificates": 0, "system_edges_certified": 0,
        "stage_instances_bound": 0, "stage_instances_required": 3,
        "path_search_executed": False, "TMG4": "HOLD", "G12": "FAIL",
        "next_stage_authorized": False, "release_credit": False,
    }
    require(observed == expected, "current external system machine truth changed")
    return observed, {
        "source": "FOUR_HASH_PINNED_CURRENT_EXTERNAL_MACHINE_GATES",
        "pins": {name: record(path) for name, path in paths.items()},
        "safe_certificates_zero_derivation": "system_pair_queries=0 AND system_edges_certified=0",
        "pass": True,
    }


def make_gate() -> dict[str, Any]:
    contract = load(PACKAGE / "00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json")
    lock = load(PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json")
    index = load(RESULTS / "C9_CAPSULE_INDEX_V1.json")
    build = load(RESULTS / "C9_BUILD_RECEIPT_V1.json")
    pose = load(RESULTS / "POSE_ADAPTER_SELF_CHECK_V1.json")
    independent = load(RESULTS / "INDEPENDENT_VALIDATION_V1.json")
    negative = load(RESULTS / "NEGATIVE_CONTROLS_V1.json")
    fresh = load(RESULTS / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json")
    tests = load(RESULTS / "PYTEST_RECEIPT_V1.json")
    review = load(PACKAGE / "07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json")
    aggregate = independent["aggregate"]
    state, external_truth = current_external_machine_truth(lock)
    declaration = contract["system_truth_declaration_only"]
    declaration_values = {key: value for key, value in declaration.items()
                          if key not in {"authority", "verification_sources"}}
    require(declaration_values == state, "declaration differs from external machine truth")
    checks = {
        "G01_eighteen_hash_pinned_sources_match_including_four_current_machine_gates":
            build["verified_source_count"] == lock["source_count"] == 18,
        "G02_registry_contract_and_centerline_exact_nine_objects": index["object_count"] == 9,
        "G03_pure_analytic_builder_does_not_import_trace_or_execute_v9f_main":
            build["builder_execution_class"] == "PURE_ANALYTIC_JSON_INPUT__NO_V9F_SOURCE_IMPORT_TRACE_OR_EXECUTION",
        "G04_sixty_one_analytic_primitives_and_2355_capsules_rebuilt":
            aggregate["primitives"] == 61 and aggregate["capsules"] == 2355,
        "G05_design_radius_5mm_effective_radius_design_plus_Hausdorff_exactly_once":
            index["numeric_authority"]["design_radius_mm"] == 5.0 and
            index["numeric_authority"]["required_query_radius_field"] == "effective_radius_mm" and
            index["numeric_authority"]["double_counted_radial_increment_mm"] == 0.0 and
            aggregate["maximum_effective_radius_mm"] == 5.0 + aggregate["maximum_hausdorff_bound_mm"],
        "G06_curve_step_and_per_capsule_Hausdorff_bounds_pass":
            aggregate["maximum_curve_arclength_step_mm"] <= 1.5 and
            aggregate["maximum_hausdorff_bound_mm"] <= aggregate["uniform_conservative_reference_bound_mm"],
        "G07_fillet_actual_radius_clamp_and_tangent_continuity_pass": aggregate["clamped_fillet_count"] == 1,
        "G08_nine_JSON_and_nine_deterministic_NPZ_pairs_pass":
            all(item["npz"]["deterministic_zip"] for item in independent["objects"]),
        "G09_current_12dp_mount_and_accepted_URDF_pose_adapter_pass": pose["pose_adapter_self_check_pass"] is True,
        "G10_J4_q4_lower_zero_upper_sign_length_and_follower_closure_pass":
            pose["j4_sign_checks_pass"] is True and
            pose["j4_max_follower_closure_residual_mm"] <= 1.0e-6 and
            pose["j4_max_dynamic_exchange_length_residual_mm"] <= 1.0e-9 and
            pose["j4_section5_full_domain_topology_capsule_count"] == 139 and
            pose["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"] <= 1.5 and
            pose["j4_all_139_segments_recomputed_at_each_q4_sample"] is True,
        "G11_J3_dual_host_emitted_and_production_union_unknown":
            pose["j3"]["dual_host_capsule_count"] == 169 and
            pose["j3"]["continuous_q3_carrier_law"] == "UNKNOWN" and
            pose["j3"]["production_union_acceptance"] == "UNKNOWN",
        "G12_independent_validator_16_of_16_pass":
            independent["checks_passed"] == independent["checks_required"] == 16 and
            independent["independent_validation_pass"] is True,
        "G13_all_21_negative_controls_caught": negative["caught"] == negative["required"] == 21 and negative["all_caught"] is True,
        "G14_two_replays_six_fresh_processes_23_core_unchanged":
            fresh["replay_count"] == 2 and fresh["fresh_process_count"] == 6 and
            fresh["core_artifact_count"] == 23 and fresh["fresh_process_determinism_pass"] is True,
        "G15_pytest_at_least_45_all_pass": tests["tests_passed"] >= 45 and tests["tests_failed"] == 0,
        "G16_P11_to_centerline_offset_lineage_remains_unknown":
            index["numeric_authority"]["p11_physical_guide_to_centerline_offset_lineage"] == "UNKNOWN",
        "G17_current_system_state_read_from_four_hash_pinned_external_machine_gates":
            external_truth["pass"] is True and
            independent["authority_boundary"]["system_state_authority"]["pass"] is True,
        "G18_zero_current_pair_edge_path_parent_next_stage_or_release_credit":
            state["system_pair_queries"] == state["safe_certificates"] == state["system_edges_certified"] == 0 and
            state["path_search_executed"] is False and state["next_stage_authorized"] is False and
            state["release_credit"] is False,
        "G19_superseded_pre_repair_NOT_CLEAN_PASS_preserved_with_zero_credit":
            review["verdict"] == "SUPERSEDED_PRE_AUTHORITY_NOT_CLEAN_PASS__ZERO_CREDIT" and
            review["superseded_artifacts"]["gate"]["sha256"] ==
                "17C087BD1CB0016E08AE1DD0A55A16FB34662869C1693DBBE8B10FF4B6958628",
        "G20_raw_5mm_query_and_double_Hausdorff_debit_fail_closed":
            {case["id"] for case in negative["cases"]}.issuperset({
                "NC19_RAW_5MM_USED_AS_QUERY_RADIUS",
                "NC20_HAUSDORFF_DOUBLE_DEBIT_OR_INFLATION",
            }),
        "G21_J4_old_71_chord_under_subdivision_fail_closed":
            any(case["id"] == "NC21_J4_SECTION5_Q0_ONLY_UNDERSUBDIVISION" and case["caught"]
                for case in negative["cases"]),
    }
    require(all(checks.values()), f"local Gate failed: {[key for key, value in checks.items() if not value]}")
    evidence_paths = [
        PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json",
        PACKAGE / "00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json",
        PACKAGE / "00_contract/FRAME_UNIT_AND_MOTION_LEDGER_V1.json",
        RESULTS / "C9_CAPSULE_INDEX_V1.json",
        RESULTS / "C9_BUILD_RECEIPT_V1.json",
        RESULTS / "POSE_ADAPTER_SELF_CHECK_V1.json",
        RESULTS / "INDEPENDENT_VALIDATION_V1.json",
        RESULTS / "NEGATIVE_CONTROLS_V1.json",
        RESULTS / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json",
        RESULTS / "PYTEST_RECEIPT_V1.json",
        PACKAGE / "07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json",
    ]
    verdict = (
        "C9_LOCAL_CAPSULE_CANDIDATES_9_OF_9_PASS__"
        "ANALYTIC_HAUSDORFF_AND_SIDE_EFFECT_FREE_POSE_ADAPTER_VALIDATED__"
        "J3_PRODUCTION_UNION_ACCEPTANCE_UNKNOWN__"
        "ZERO_CURRENT_PAIR_EDGE_PATH_CREDIT__TMG4_HOLD"
    )
    return {
        "schema": "ROUTE_C_C9_LOCAL_CANDIDATE_GATE_V2_REPAIRED",
        "generated_utc": "DETERMINISTIC_FINALIZER_NO_WALLCLOCK",
        "scope": "NINE_LOGICAL_ROUTE_C_HARNESS_LOCAL_CAPSULE_CANDIDATES_ONLY",
        "decision_rule": "Authority > hash-pinned source > independent analytic reconstruction > tests > agent opinion",
        "checks": checks,
        "checks_passed": len(checks),
        "checks_required": len(checks),
        "local_candidate_gate_pass": True,
        "object_count": 9,
        "primitive_count": aggregate["primitives"],
        "capsule_count": aggregate["capsules"],
        "maximum_curve_arclength_step_mm": aggregate["maximum_curve_arclength_step_mm"],
        "maximum_hausdorff_bound_mm": aggregate["maximum_hausdorff_bound_mm"],
        "maximum_effective_radius_mm": aggregate["maximum_effective_radius_mm"],
        "narrowphase_query_contract": {
            "required_query_radius_field": "effective_radius_mm",
            "effective_radius_rule": "design_radius_mm + hausdorff_bound_mm exactly once",
            "raw_design_radius_query": "FORBIDDEN_FAIL_CLOSED",
            "second_hausdorff_debit_or_inflation": "FORBIDDEN_FAIL_CLOSED",
        },
        "j4_section5_full_domain": {
            "topology_capsule_count": aggregate["j4_section5_full_domain_topology_capsule_count"],
            "q4_samples_rad": [-1.87, 0.0, 1.57],
            "maximum_dynamic_curve_arclength_step_mm":
                aggregate["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"],
            "maximum_dynamic_hausdorff_bound_mm":
                aggregate["j4_section5_full_domain_max_dynamic_hausdorff_bound_mm"],
            "maximum_dynamic_effective_radius_mm":
                aggregate["j4_section5_full_domain_max_dynamic_effective_radius_mm"],
            "all_139_segments_recomputed_at_each_sample": True,
        },
        "uniform_conservative_reference_bound_mm": aggregate["uniform_conservative_reference_bound_mm"],
        "minimum_clamped_actual_radius_mm": aggregate["minimum_clamped_actual_radius_mm"],
        "tests_passed": tests["tests_passed"],
        "negative_controls_caught": negative["caught"],
        "fresh_process_replays": fresh["replay_count"],
        "evidence_pins": [record(path) for path in evidence_paths],
        "holds_and_unknowns": {
            "P11_physical_guide_to_centerline_offset_lineage": "UNKNOWN",
            "J3_continuous_q3_carrier_law": "UNKNOWN",
            "J3_production_union_acceptance": "UNKNOWN",
            "J4_full_hardware_annular_coverage": "DEFERRED_HOLD",
            "current_system_pair_evaluation": "NOT_EXECUTED",
            "TMG4": "HOLD",
            "G12": "FAIL",
        },
        "system_state_unchanged": state,
        "system_state_authority": external_truth,
        "contract_system_state_role": "DECLARATION_ONLY_CROSS_CHECKED_AGAINST_EXTERNAL_MACHINE_TRUTH",
        "superseded_pre_repair_gate": {
            "review_receipt": record(PACKAGE / "07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json"),
            "old_gate_sha256": "17C087BD1CB0016E08AE1DD0A55A16FB34662869C1693DBBE8B10FF4B6958628",
            "old_verdict_status": "SUPERSEDED_PRE_AUTHORITY_NOT_CLEAN_PASS__ZERO_CREDIT",
        },
        "authority_flags": {
            "local_C9_candidate_credit": True,
            "system_registry_binding_credit": False,
            "pair_query_credit": 0,
            "safe_certificate_credit": 0,
            "edge_credit": 0,
            "path_credit": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "maximum_legal_claim": verdict,
        "verdict": verdict,
    }


def classify(relative: str) -> tuple[str, str]:
    if relative.startswith("00_contract/"):
        return "FROZEN_LOCAL_CONTRACT", "LOCAL_CANDIDATE_INPUT_CONTRACT"
    if relative.startswith("02_builder/"):
        return "BUILDER_SOURCE", "IMPLEMENTATION_NO_SYSTEM_CREDIT"
    if relative.startswith("03_runtime/"):
        return "RUNTIME_CANDIDATE", "LOCAL_ANALYTIC_CAPSULE_CANDIDATE"
    if relative.startswith("04_validation/"):
        return "VALIDATION_SOURCE", "INDEPENDENT_OR_REPLAY_IMPLEMENTATION"
    if relative.startswith("05_results/"):
        return "EVIDENCE_RECEIPT", "LOCAL_CANDIDATE_EVIDENCE"
    if relative.startswith("06_tests/"):
        return "TEST_SOURCE", "LOCAL_VERIFICATION"
    if relative.startswith("07_reviews/"):
        return "SUPERSEDED_REVIEW_LINEAGE", "DIAGNOSTIC_ZERO_CREDIT"
    return "PACKAGE_DOCUMENT", "NAVIGATION_ONLY"


def payload_files() -> list[Path]:
    excluded = {MANIFEST.resolve(), INVENTORY.resolve()}
    files = []
    for path in PACKAGE.rglob("*"):
        if not path.is_file() or path.resolve() in excluded:
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name.endswith(".tmp"):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(PACKAGE).as_posix())


def make_manifest() -> tuple[bytes, list[dict[str, Any]]]:
    rows = []
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256", "role", "authority"])
    for path in payload_files():
        relative = path.relative_to(PACKAGE).as_posix()
        role, authority = classify(relative)
        row = {"path": relative, "bytes": path.stat().st_size, "sha256": sha(path),
               "role": role, "authority": authority}
        rows.append(row)
        writer.writerow([row["path"], row["bytes"], row["sha256"], role, authority])
    return stream.getvalue().encode("utf-8"), rows


def make_inventory(manifest_bytes: bytes, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "ROUTE_C_C9_PACKAGE_INVENTORY_V1",
        "generated_utc": "DETERMINISTIC_FINALIZER_NO_WALLCLOCK",
        "payload_file_count_excluding_manifest_and_inventory": len(rows),
        "payload": rows,
        "manifest": {"path": MANIFEST.relative_to(PACKAGE).as_posix(), "bytes": len(manifest_bytes),
                     "sha256": sha_bytes(manifest_bytes)},
        "gate": record(GATE),
        "runtime_file_count": sum(row["path"].startswith("03_runtime/") for row in rows),
        "system_credit": 0,
        "TMG4": "HOLD",
        "verdict": "C9_PACKAGE_INVENTORY_COMPLETE__LOCAL_CANDIDATE_SCOPE_ONLY",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    options = parse_args()
    gate_bytes = stable(make_gate())
    if options.write:
        atomic(GATE, gate_bytes)
    else:
        require(GATE.is_file() and GATE.read_bytes() == gate_bytes, "local Gate drift")
    manifest_bytes, rows = make_manifest()
    inventory_bytes = stable(make_inventory(manifest_bytes, rows))
    if options.write:
        atomic(MANIFEST, manifest_bytes)
        atomic(INVENTORY, inventory_bytes)
        mode = "write"
    else:
        require(MANIFEST.is_file() and MANIFEST.read_bytes() == manifest_bytes, "package manifest drift")
        require(INVENTORY.is_file() and INVENTORY.read_bytes() == inventory_bytes, "package inventory drift")
        mode = "check"
    gate = json.loads(gate_bytes)
    print(json.dumps({
        "status": "PASS", "mode": mode, "checks": gate["checks_passed"],
        "objects": gate["object_count"], "capsules": gate["capsule_count"],
        "maximum_hausdorff_bound_mm": gate["maximum_hausdorff_bound_mm"],
        "tests_passed": gate["tests_passed"], "manifest_payload_files": len(rows),
        "J3_production_union_acceptance": "UNKNOWN", "system_pair_credit": 0,
        "TMG4": "HOLD",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
