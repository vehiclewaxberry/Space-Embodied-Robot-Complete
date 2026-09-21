"""Build deterministic CTRL_R2_PREDEVELOPMENT evidence and aggregate Gate."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from predevelopment import (
    AUTHORITY_PATH,
    CONFIG_PATH,
    MODULE_ROOT,
    RESULTS_DIR,
    classify_ctrl01,
    load_json_strict,
    normalized_text_sha256,
    run_nominal_probe,
    sha256_file,
    validate_source_pins,
    write_json,
)
from unified_r2_adapters import (
    audit_actuator_dynamics_intake,
    run_flexibility_static_screen,
    run_unified_r2_static_probe,
)


def _source(repo_root: Path, config: dict, source_id: str) -> dict:
    pin = next(item for item in config["source_pins"] if item["id"] == source_id)
    return load_json_strict(repo_root / pin["path"])


def _validate_recorded_replay_audit(replay: dict) -> dict:
    """Validate bookkeeping only; this does not turn the replay record into a Gate."""
    runs = replay.get("runs")
    if not isinstance(runs, list) or not runs:
        raise RuntimeError("REPLAY_AUDIT_RUNS_MISSING")

    run_ids = [item.get("id") for item in runs]
    if any(not isinstance(run_id, str) or not run_id for run_id in run_ids):
        raise RuntimeError("REPLAY_AUDIT_RUN_ID_INVALID")
    if len(run_ids) != len(set(run_ids)):
        raise RuntimeError("REPLAY_AUDIT_DUPLICATE_RUN_ID")

    for item in runs:
        counts = [item.get("passed"), item.get("failed"), item.get("total")]
        if any(type(value) is not int or value < 0 for value in counts):
            raise RuntimeError(f"REPLAY_AUDIT_COUNT_INVALID:{item['id']}")
        if item["passed"] + item["failed"] != item["total"]:
            raise RuntimeError(f"REPLAY_AUDIT_ARITHMETIC_MISMATCH:{item['id']}")
        if "collected_test_count" in item:
            collected = item["collected_test_count"]
            if type(collected) is not int or collected < 0:
                raise RuntimeError(
                    f"REPLAY_AUDIT_COLLECTED_COUNT_INVALID:{item['id']}"
                )
            if collected != item["total"]:
                raise RuntimeError(
                    f"REPLAY_AUDIT_COLLECTED_TOTAL_MISMATCH:{item['id']}"
                )

    by_id = {item["id"]: item for item in runs}
    new_work_ids = ("CTRL_R2_PREDEVELOPMENT", "CURRENT_AUTHORITY_INDEX")
    missing = [run_id for run_id in new_work_ids if run_id not in by_id]
    if missing:
        raise RuntimeError(f"REPLAY_AUDIT_NEW_WORK_RUN_MISSING:{missing}")
    expected_passed = sum(by_id[run_id]["passed"] for run_id in new_work_ids)
    expected_total = sum(by_id[run_id]["total"] for run_id in new_work_ids)
    aggregate = replay.get("aggregate", {})
    if aggregate.get("new_work_tests_passed") != expected_passed:
        raise RuntimeError("REPLAY_AUDIT_NEW_WORK_PASSED_MISMATCH")
    if aggregate.get("new_work_tests_total") != expected_total:
        raise RuntimeError("REPLAY_AUDIT_NEW_WORK_TOTAL_MISMATCH")
    return {
        "bookkeeping_valid": True,
        "run_ids_unique": True,
        "per_run_arithmetic_valid": True,
        "declared_collected_counts_match_total": all(
            item.get("collected_test_count", item["total"]) == item["total"]
            for item in runs
        ),
        "new_work_run_ids": list(new_work_ids),
        "new_work_tests_passed": expected_passed,
        "new_work_tests_total": expected_total,
        "evidence_class": "RECORDED_AUDIT_NOT_GATE",
        "gate_qualified": False,
    }


def build(repo_root: Path) -> dict:
    config = load_json_strict(CONFIG_PATH)
    authority = load_json_strict(AUTHORITY_PATH)
    binding = validate_source_pins(repo_root, config)
    if not binding["pass"]:
        raise RuntimeError(f"SOURCE_PIN_MISMATCH:{binding['mismatches']}")

    ctrl01 = _source(repo_root, config, "ctrl01_gate")
    ctrl02 = _source(repo_root, config, "ctrl02_gate")
    safe00 = _source(repo_root, config, "safe00_gate")
    e23 = _source(repo_root, config, "e23_gate")
    pb00 = _source(repo_root, config, "pb00_gate")
    odr60 = _source(repo_root, config, "odr60_request")
    intake = _source(repo_root, config, "odr60_binding_intake")
    collision = _source(repo_root, config, "odr60_collision_authority")
    preflight_parse = {"valid_strict_json": True, "error": None}
    try:
        preflight = _source(repo_root, config, "odr60_preflight")
    except ValueError as exc:
        # Fail closed: the current upstream preflight contains a duplicate
        # next_stage_authorized key.  Never rely on last-key-wins semantics.
        preflight = {
            "path_search_authorized": False,
            "path_search_executed": False,
        }
        preflight_parse = {
            "valid_strict_json": False,
            "error": str(exc),
            "disposition": "FAIL_CLOSED_FALSE_VALUES_ONLY__UPSTREAM_REISSUE_REQUIRED",
        }
    mechanical = _source(repo_root, config, "mechanical_release_gate")
    sim13 = _source(repo_root, config, "sim13_20_of_20_gate")
    replay = load_json_strict(RESULTS_DIR / "CURRENT_MIGRATION_REPLAY_AUDIT_V1.json")
    replay_integrity = _validate_recorded_replay_audit(replay)
    replay_by_id = {item["id"]: item for item in replay["runs"]}

    probe = run_nominal_probe(repo_root, config)
    unified_static = run_unified_r2_static_probe(repo_root, config)
    flex_static = run_flexibility_static_screen(repo_root, config)
    actuator_contract_path = (
        MODULE_ROOT / "contracts" / "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_V1.json"
    )
    actuator_contract = load_json_strict(actuator_contract_path)
    actuator_audit = audit_actuator_dynamics_intake(actuator_contract, config)
    failure = classify_ctrl01(ctrl01)
    current_config_pin = next(
        item for item in config["source_pins"] if item["id"] == "ctrl01_current_config"
    )
    current_matrix_pin = next(
        item for item in config["source_pins"] if item["id"] == "ctrl01_current_matrix"
    )
    frozen_hashes = ctrl01["gates"]["GC1_G_hash_lock"]
    ctrl01_reproduction = {
        "status": "NOT_CLAIMED_REORG04_NORMALIZED_HASH_DRIFT",
        "current_config_normalized_sha256": normalized_text_sha256(
            repo_root / current_config_pin["path"]
        ),
        "frozen_gate_config_normalized_sha256": frozen_hashes["config"][
            "expected_normalized_semantic_sha256"
        ].upper(),
        "current_matrix_normalized_sha256": normalized_text_sha256(
            repo_root / current_matrix_pin["path"]
        ),
        "frozen_gate_matrix_normalized_sha256": frozen_hashes["matrix"][
            "expected_normalized_semantic_sha256"
        ].upper(),
        "immutable_negative_result_retained": True,
    }
    ctrl01_reproduction["config_matches_frozen_gate"] = (
        ctrl01_reproduction["current_config_normalized_sha256"]
        == ctrl01_reproduction["frozen_gate_config_normalized_sha256"]
    )
    ctrl01_reproduction["matrix_matches_frozen_gate"] = (
        ctrl01_reproduction["current_matrix_normalized_sha256"]
        == ctrl01_reproduction["frozen_gate_matrix_normalized_sha256"]
    )
    failure["reproduction"] = ctrl01_reproduction

    frontier = {
        "schema": "CURRENT_FRONTIER_ODR60_CTRL_V1",
        "as_of_date": "2026-08-27",
        "mechanical": {
            "release_verdict": mechanical["verdict"],
            "gate_a_pass": mechanical["gate_a_pass"],
            "release_credit": mechanical["release_credit"],
            "odr60_decision_absent": odr60["decision_absent"],
            "option_a_owner_selection_present": False,
            "execution_mount_numeric_spelling_bound": intake["current_readiness"]["execution_mount_numeric_spelling_bound"],
            "collision_asset_frame_registration_bound": intake["current_readiness"]["collision_asset_frame_registration_bound"],
            "scene_bound_required_binding_count": intake["current_readiness"]["scene_bound_required_binding_count"],
            "scene_required_binding_count": intake["current_readiness"]["scene_required_binding_count"],
            "known_active_object_count_structural_only": collision["system_registry"]["known_active_object_count"],
            "unassessed_fail_closed_pair_count": collision["system_registry"]["unassessed_fail_closed_pair_count"],
            "pair_evaluation_authorized": intake["current_readiness"]["pair_evaluation_authorized"],
            "edge_evaluation_authorized": intake["current_readiness"]["edge_evaluation_authorized"],
            "path_search_authorized": preflight["path_search_authorized"],
            "path_search_executed": preflight["path_search_executed"],
            "odr60_preflight_strict_json": preflight_parse,
        },
        "control": {
            "ctrl01_verdict": ctrl01["verdict"],
            "ctrl01_reproduction_status": ctrl01_reproduction["status"],
            "ctrl02_verdict": ctrl02["verdict"],
            "ctrl02_scope": "PASS_WITH_PROVISIONAL_SCOPE",
            "safe00_verdict": safe00["verdict"],
            "safe00_review_status": safe00["review_status"],
            "safe00_next_stage_authorized": safe00["next_stage_authorized"],
            "pb00_technical_characterization": pb00["technical_characterization"],
            "pb00_authority_disposition": pb00["authority_disposition"],
            "e23_technical_verdict": e23["technical_verdict"],
            "sim13_negative_control_verdict": sim13["verdict"],
            "sim13_credit_scope": "FAIL_CLOSED_BACKEND_NEGATIVE_CONTROLS_ONLY",
            "unified_r2_static_adapter": (
                "PASS_DIAGNOSTIC_ONLY" if unified_static["pass"] else "FAIL"
            ),
            "dual_wing_14mode_static_overlay": (
                "PASS_DIAGNOSTIC_ONLY" if flex_static["pass"] else "FAIL"
            ),
            "actuator_hardware_model_valid": actuator_audit["hardware_model_valid"],
        },
        "legal_operation": "CONTROL_PREDEVELOPMENT_ONLY",
        "collision_aware_execution_credit": False,
        "integrated_release_credit": False,
    }

    criteria = [
        {
            "id": "C0",
            "name": "R2 model/hash binding",
            "status": "PASS_HASH_PINNED_UNIFIED_R2_AND_FLEX_STATIC_ADAPTER_BINDING",
            "pass_for_candidate_packaging": binding["pass"]
            and unified_static["pass"]
            and flex_static["pass"],
            "unified_r2_dof": 8,
            "ctrl01_arm_dof": 6,
            "dual_wing_flex_modes_total": 14,
            "scope": "STATIC_DIAGNOSTIC_ONLY",
        },
        {
            "id": "C1",
            "name": "CTRL-01 immutable negative-result binding/classification",
            "status": "BOUND_REPEAT__CURRENT_REPLAY_HOLD__EXACT_REPRODUCTION_NOT_CLAIMED",
            "source_verdict": ctrl01["verdict"],
            "reproduction": ctrl01_reproduction,
            "current_replay": replay_by_id["CTRL01_CURRENT_TREE"],
            "current_replay_clean": replay_by_id["CTRL01_CURRENT_TREE"]["failed"] == 0,
            "exact_legacy_reproduction_available": False,
            "pass_for_candidate_packaging": ctrl01["verdict"] == "REPEAT"
            and ctrl01_reproduction["immutable_negative_result_retained"],
        },
        {
            "id": "C2",
            "name": "nominal EE DLS/resolved-rate probe",
            "status": "PASS_SINGLE_STATE_NONCONTACT_PROBE_ONLY__LOCAL_EXECUTION_CLOSURE_HASH_PINNED"
            if probe["pass"]
            else "FAIL",
            "pass_for_candidate_packaging": probe["pass"] and binding["pass"],
            "local_execution_closure_hash_pinned": binding["pass"],
            "task_performance_pass": False,
        },
        {
            "id": "C3",
            "name": "free-floating base reaction compensation",
            "status": "PASS_UNIFIED_R2_STATIC_ZERO_MOMENTUM_INTERFACE__CTRL01_C3_PERFORMANCE_REPEAT_RETAINED"
            if unified_static["pass"]
            else "FAIL_STATIC_INTERFACE",
            "pass_for_candidate_packaging": unified_static["pass"],
            "static_adapter_pass": unified_static["pass"],
            "performance_pass": False,
            "torque_level_constrained_prismatic_reaction_solver": False,
        },
        {
            "id": "C4",
            "name": "base-attitude stabilization",
            "status": "BOUND_HISTORICAL_PASS_WITH_PROVISIONAL_SCOPE__CURRENT_REPLAY_HOLD",
            "pass_for_candidate_packaging": ctrl02["verdict"] == "PASS",
            "current_replay": replay_by_id["CTRL02_CURRENT_TREE"],
            "current_replay_clean": replay_by_id["CTRL02_CURRENT_TREE"]["failed"] == 0,
            "hardware_valid": False,
        },
        {
            "id": "C5",
            "name": "momentum/resource anchors",
            "status": "PASS_E23_PROVISIONAL_DIAGNOSTIC_ANCHOR_BINDING_ONLY",
            "pass_for_candidate_packaging": True,
            "source": "E23_R2_FULL_FLEX_COUPLED_GATE_V1.key_metrics",
            "scope": "22kg_AT_0p5dps_AND_150kg_AT_3dps__NOT_SIM10_ANCHOR_EQUIVALENCE",
            "sim10_gate_inheritance": False,
            "task_control_regression_pass": False,
            "anchors": {
                "22kg_initial_target_rate_dps": 0.5,
                "22kg_nominal_omega_plus_equiv_dps": e23["key_metrics"]["22kg_nominal_omega_plus_equiv_dps"],
                "22kg_nominal_Hc_Nms": e23["key_metrics"]["22kg_nominal_Hc_Nms"],
                "150kg_initial_target_rate_dps": 3.0,
                "150kg_nominal_omega_plus_equiv_dps": e23["key_metrics"]["150kg_nominal_omega_plus_equiv_dps"],
                "150kg_nominal_Hc_Nms": e23["key_metrics"]["150kg_nominal_Hc_Nms"],
            },
        },
        {
            "id": "C6",
            "name": "dual-wing fourteen-mode provisional flex screen",
            "status": "PASS_LOW_NOMINAL_HIGH_STATIC_OVERLAY_DIAGNOSTIC_ONLY"
            if flex_static["pass"]
            else "FAIL_STATIC_OVERLAY",
            "pass_for_candidate_packaging": flex_static["pass"],
            "wing_order": ["LEFT", "RIGHT"],
            "modes_per_wing": 7,
            "total_modes": 14,
            "excitation_authority": "ARBITRARY_NONZERO_DIAGNOSTIC_NOT_TASK_BOUND",
            "mission_flex_robustness_evaluated": False,
            "e23_pass_inheritance": "NOT_INHERITED",
            "round4_gate_pass_inheritance": "NOT_INHERITED",
            "provisional_physics": True,
        },
        {
            "id": "C7",
            "name": "SAFE interface contract",
            "status": "BOUND_HISTORICAL_MODULE_PASS__CURRENT_REPLAY_HOLD__PENDING_REVIEW",
            "pass_for_candidate_packaging": safe00["verdict"] == "PASS",
            "current_replay": replay_by_id["SAFE00_CURRENT_TREE"],
            "current_replay_clean": replay_by_id["SAFE00_CURRENT_TREE"]["failed"] == 0,
            "review_approved": safe00.get("review_status") == "APPROVED",
            "execution_authorized": False,
        },
        {
            "id": "C8",
            "name": "actuator dynamics hardware intake",
            "status": "MINIMUM_INTAKE_SCHEMA_COMPLETE__SEMANTIC_REQUIREMENTS_AND_MEASUREMENTS_PENDING__HARDWARE_HOLD"
            if actuator_audit["minimum_intake_schema_complete"]
            else "FAIL_MINIMUM_INTAKE_SCHEMA",
            "pass_for_candidate_packaging": actuator_audit[
                "pass_for_candidate_packaging_minimum_schema_only"
            ],
            "minimum_intake_schema_complete": actuator_audit[
                "minimum_intake_schema_complete"
            ],
            "semantic_requirements_complete": False,
            "hardware_measurements_complete": False,
            "hardware_model_valid": False,
            "zero_fill_forbidden": True,
        },
    ]
    candidate_complete = (
        binding["pass"]
        and probe["pass"]
        and unified_static["pass"]
        and flex_static["pass"]
        and actuator_audit["minimum_intake_schema_complete"]
        and all(
        item["pass_for_candidate_packaging"] for item in criteria
        )
    )
    recorded_legacy_replay_clean = bool(
        replay["aggregate"]["legacy_current_tree_replay_clean"]
    )
    # This local replay audit is a recorded diagnostic, not an independent Gate.
    # It cannot upgrade technical completion even if its hand-authored summary is
    # later changed; a new side-effect-free, hash-bound replay Gate is required.
    replay_gate_qualified = False
    gate = {
        "schema": "CTRL_R2_PREDEVELOPMENT_GATE_V1",
        "phase": "CTRL_R2_PREDEVELOPMENT",
        "scope": "MODEL_AND_NOMINAL_TRACKING_ONLY__NO_COLLISION_AWARE_EXECUTION_CREDIT",
        "authority_source_schema": authority["schema"],
        "authorized_claim_ceiling": authority["authorized_claim_ceiling"],
        "criteria": criteria,
        "summary": {
            "candidate_packaging_criteria_satisfied": sum(
                bool(item["pass_for_candidate_packaging"]) for item in criteria
            ),
            "total": len(criteria),
            "performance_negative_results_retained": ["CTRL01", "C3_REACTION_COMPENSATION"],
            "legacy_ctrl01_exact_reproduction_claimed": False,
            "unified_r2_static_adapter_executed": True,
            "dual_wing_14mode_static_overlay_executed": True,
            "actuator_hardware_model_valid": False,
        },
        "candidate_package_complete": candidate_complete,
        "technical_predevelopment_complete": False,
        "current_replay_clean": False,
        "recorded_legacy_replay_clean": recorded_legacy_replay_clean,
        "recorded_replay_audit_integrity": replay_integrity,
        "current_replay_evidence_class": "RECORDED_AUDIT_NOT_GATE",
        "current_replay_gate_qualified": replay_gate_qualified,
        "verdict": "CONTROL_PREDEVELOPMENT_CANDIDATE_BUILT__CURRENT_REPLAY_HOLD__INTEGRATED_RELEASE_HOLD" if candidate_complete else "CONTROL_PREDEVELOPMENT_HOLD",
        "prohibited_claims": authority["prohibited_scope"],
        "remaining_holds": [
            "ODR60_EXACT_OPTION_A_OWNER_TOKEN_ABSENT",
            "EXECUTION_MOUNT_AND_COLLISION_FRAME_BINDING_INCOMPLETE",
            "M01_SCENE_CLEARANCE_MOTION_CERTIFICATES_AND_PAIR_ORACLE_INCOMPLETE",
            "CTRL01_REPEAT_TASK_AND_CONSTRAINT_FAILURES",
            "CTRL01_REORG04_CONFIG_HASH_DRIFT_BLOCKS_EXACT_LEGACY_REPRODUCTION",
            "INDEPENDENT_SIDE_EFFECT_FREE_REPLAY_GATE_ABSENT",
            "UNIFIED_R2_TORQUE_LEVEL_CONSTRAINED_PRISMATIC_REACTION_SOLVER_NOT_IMPLEMENTED",
            "DUAL_WING_14MODE_FULL_COUPLED_MISSION_TIME_HISTORY_NOT_INTEGRATED",
            "ACTUATOR_DYNAMICS_MEASUREMENTS_PENDING__ZERO_FILL_FORBIDDEN",
            "HARDWARE_VALID_ACTUATOR_DYNAMICS_ABSENT",
            "SAFE00_PENDING_REVIEW_AND_NEXT_STAGE_FALSE",
            "E23_PHYSICS_PARAMETERS_PROVISIONAL",
            "MECHANICAL_RELEASE_FALSE"
            ,"ODR60_PREFLIGHT_DUPLICATE_JSON_KEY_REISSUE_REQUIRED"
        ],
        "collision_aware_execution_credit": False,
        "non_abort_execution_credit": False,
        "integrated_control_ready": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "tests_are_not_gates": True,
    }

    write_json(RESULTS_DIR / "CTRL_R2_MODEL_BINDING_V1.json", binding)
    write_json(RESULTS_DIR / "CTRL_R2_NOMINAL_DLS_PROBE_V1.json", probe)
    write_json(RESULTS_DIR / "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1.json", unified_static)
    write_json(RESULTS_DIR / "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1.json", flex_static)
    write_json(RESULTS_DIR / "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1.json", actuator_audit)
    write_json(RESULTS_DIR / "CTRL01_FAILURE_CLASSIFICATION_V1.json", failure)
    write_json(RESULTS_DIR / "CURRENT_FRONTIER_ODR60_CTRL_V1.json", frontier)
    write_json(RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_GATE_V1.json", gate)

    manifest_paths = [
        AUTHORITY_PATH,
        actuator_contract_path,
        CONFIG_PATH,
        MODULE_ROOT / "README.md",
        Path(__file__),
        MODULE_ROOT / "src" / "__init__.py",
        MODULE_ROOT / "src" / "predevelopment.py",
        MODULE_ROOT / "src" / "unified_r2_adapters.py",
        MODULE_ROOT / "tests" / "test_predevelopment.py",
        RESULTS_DIR / "CTRL_R2_MODEL_BINDING_V1.json",
        RESULTS_DIR / "CTRL_R2_NOMINAL_DLS_PROBE_V1.json",
        RESULTS_DIR / "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1.json",
        RESULTS_DIR / "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1.json",
        RESULTS_DIR / "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1.json",
        RESULTS_DIR / "CTRL01_FAILURE_CLASSIFICATION_V1.json",
        RESULTS_DIR / "CURRENT_FRONTIER_ODR60_CTRL_V1.json",
        RESULTS_DIR / "CURRENT_MIGRATION_REPLAY_AUDIT_V1.json",
        RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_GATE_V1.json",
    ]
    manifest = RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_SHA256_V1.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        for path in sorted(manifest_paths, key=lambda value: value.as_posix()):
            writer.writerow(
                {
                    "path": path.relative_to(repo_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    gate = build(args.repo_root.resolve())
    print(gate["verdict"])
    return 0 if gate["candidate_package_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
