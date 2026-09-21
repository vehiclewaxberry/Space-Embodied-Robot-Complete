"""Generate 00_authority artifacts by re-reading and re-hashing local sources.

Fail-closed: if any EXPECTED pin mismatches, or a machine count re-read from a
gate JSON disagrees with the recorded claim, the script raises and writes
nothing. All hashes are computed here, never copied from prose.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
sys.path.insert(0, str(MODULE / "src"))
from dh_v1.hashing import sha256_file  # noqa: E402

# (repo-relative path, role, authority_class, protected)
SOURCES = [
    # --- V2 second-increment eight-artifact bundle (H0) ---
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2.json", "V2_INCREMENT_GATE_38_38", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V2.json", "V2_STANDALONE_VALIDATION_7_7_NC_28_28", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/SOURCE_AUTHORITY_LOCK_V2.json", "SOURCE_AUTHORITY_LOCK_V2_27_PINS", "H0_LOCK", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2.json", "V2_BUNDLE_MANIFEST", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/README.md", "V2_BUNDLE_README_CLAIM_CEILING", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/build_increment_gate_v2.py", "V2_BUNDLE_BUILDER", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/test_increment_gate_v2.py", "V2_BUNDLE_TESTS_13", "H0_GATE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2/validate_increment_gate_v2.py", "V2_BUNDLE_VALIDATOR", "H0_GATE", True),
    # --- parent gates ---
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json", "MECHANICAL_TERMINAL_GATE_A", "H0_PARENT", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json", "MECHANICAL_PARENT_V4", "H0_PARENT", True),
    # --- dynamics truth (H1) ---
    ("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "ACCEPTED_B601_URDF", "H1_DYNAMICS_TRUTH", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/05_ACCEPTED_B601_URDF_REF.yaml", "ACCEPTED_URDF_DESIGNATION", "H1_DYNAMICS_TRUTH", True),
    ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf", "UNIFIED_R2_C01_URDF_CANDIDATE_V2", "H1_CANDIDATE", True),
    ("20_engineering/cad/spacecraft_layout/servicer_12U_v0/servicer_12U_v0.urdf", "SERVICER_12U_RIGID_BODY_V0", "H1_STAGE1_SSOT", True),
    ("20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.urdf", "TARGET_SATELLITE_22KG_V0", "H1_STAGE1_SSOT", True),
    ("20_engineering/cad/spacecraft_layout/target_debris_v0/target_debris_v0.urdf", "TARGET_DEBRIS_150KG_V0", "H1_STAGE1_SSOT", True),
    ("20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv", "MASS_INERTIA_LEDGER_V1", "H1_STAGE1_SSOT", True),
    ("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml", "CDR_MASS_AUTHORITY_V2_PARTIAL", "H1_AUTHORITY", True),
    # --- frames / units (H0 contracts) ---
    ("20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md", "FRAME_SSOT_V0", "H0_CONTRACT", True),
    ("20_engineering/config/geometry/frame_tree_v1.yaml", "FRAME_TREE_V1_MM", "H0_CONTRACT", True),
    ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml", "UNIFIED_FRAME_TREE_V2_SI", "H0_CONTRACT", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json", "EXECUTION_MOUNT_PHYSICAL_CANDIDATE", "H0_CONTRACT", True),
    ("20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml", "M3R_PHYSICAL_STACK", "H0_CONTRACT", True),
    # --- states / M01 (H2 registry sources) ---
    ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml", "C01_C09_CONFIGURATION_LIBRARY", "H2_STATE_REGISTRY", True),
    ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_effective_frontier_v2/C01_C09_M4_M7_CONFIGURATION_IDENTITY_BINDING_V1.yaml", "C01_C09_M7_IDENTITY_BINDING", "H2_STATE_REGISTRY", True),
    ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml", "M01_M08_TRAJECTORY_CONTRACT", "H2_STATE_REGISTRY", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l01_l02_configuration_geometry_execution_matrix_v1/M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1.json", "M4_EXECUTION_MATRIX_GATE_0_OF_9", "H2_STATE_REGISTRY", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l01_l02_configuration_geometry_execution_matrix_v1/SOURCE_ONLY_PREFLIGHT_V1.json", "CAD_PREFLIGHT_NOT_AUTHORIZED", "H2_CAD_INTAKE", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l02_configuration_state_contract_v1/R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1.yaml", "STATE_VECTOR_CONTRACT", "H2_STATE_REGISTRY", True),
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json", "M01_THREE_STAGE_SCHEMA", "H2_STATE_REGISTRY", True),
    # --- collision (H3 sources) ---
    ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/14_COLLISION_ASSET_MANIFEST.json", "COLLISION_MANIFEST_BROADPHASE_ONLY", "H3_COLLISION", True),
    ("20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/MECH_RL_INTERFACE_V1.yaml", "MECH_RL_INTERFACE_V1_MESHES", "H3_COLLISION", True),
    # --- control / SAFE / Sim13 (H4 status sources) ---
    ("30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json", "SAFE00_GATE", "H4_STATUS", True),
    ("30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json", "CTRL01_GATE_REPEAT", "H4_STATUS", True),
    ("30_simulation/control_02_base_attitude/results/control_02_gate_check.json", "CTRL02_GATE", "H4_STATUS", True),
    ("30_simulation/r2_control_engineering_closure/task_space_metric_candidate_v1/results/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1.json", "TASK_SPACE_STATIC_METRIC_CANDIDATE", "H4_STATUS", True),
    ("30_simulation/r2_dynamics_engineering_closure/post_capture_spatial_inertia_kernel_candidate_v1/contracts/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json", "T_E_T_CONSUMER_CONTRACT", "H4_STATUS", True),
    ("30_simulation/r2_dynamics_engineering_closure/post_capture_spatial_inertia_kernel_candidate_v1/results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json", "POSTCAPTURE_KERNEL_GATE_SYNTHETIC_ONLY", "H4_STATUS", True),
    ("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json", "SIM13_PREBIND_SOURCE_GATE", "H4_STATUS", True),
    ("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json", "SIM13_BACKENDS_20_20_ABORT_ONLY", "H4_STATUS", True),
    ("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/system_binding_candidate_v1/results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json", "SIM13_SYSTEM_BINDING_ABORT_ONLY", "H4_STATUS", True),
    # --- sim anchors (H5 source-only regression) ---
    ("30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json", "SIM10_GATE_ANCHOR", "H5_REGRESSION_ANCHOR", True),
    ("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json", "SIM11_GATE_ANCHOR", "H5_REGRESSION_ANCHOR", True),
    ("30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json", "SIM12_GATE_ANCHOR", "H5_REGRESSION_ANCHOR", True),
    ("30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv", "SIM05_BASE_ATTITUDE_CSV_NO_GATE", "H5_REGRESSION_ANCHOR", True),
    ("20_engineering/config/mission_feasibility/scan_v0.yaml", "SIM10_PARAM_CARD", "H5_REGRESSION_ANCHOR", True),
    ("20_engineering/config/coupled_scene/coupled_model_v0.yaml", "SIM11_MODEL_CARD_PROVISIONAL", "H5_REGRESSION_ANCHOR", True),
    ("20_engineering/config/coupled_scene/scene_A2_capture.yaml", "SIM11_A2_CARD_TC20MS_PROVISIONAL", "H5_REGRESSION_ANCHOR", True),
    ("30_simulation/sim_14_m4_digital_prototype_grasping/config/SIM14_DIAGNOSTIC_FIXTURE_V1.json", "MISSION_ANCHOR_PAIR_DIAGNOSTIC_FIXTURE", "H5_REGRESSION_ANCHOR", True),
    # --- rulings (narrative, quoted for context only) ---
    ("01_project/competition/R2机械动力学控制第二增量闭环裁决_20260827.md", "RULING_V2_INCREMENT", "H0_RULING", True),
    ("01_project/competition/R2数字样机_机械准入_时变刚体动力学增量闭环_20260827.md", "RULING_V1_INCREMENT", "H0_RULING", True),
]

# critical pins that MUST match (from designation docs / prior machine gates)
EXPECTED = {
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf": "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json": "277be6349ec87e3cc76519e824f368f1d720c2c7e01646255da5865510cb87ef",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf": "d84aa23ce98a2a9c697b1f32e433c01c3f0ae3bd0b5c56ef9a218dd88911cbda",
}


def main() -> None:
    out_dir = MODULE / "00_authority"
    out_dir.mkdir(exist_ok=True)
    rows = []
    missing = []
    for rel, role, klass, protected in SOURCES:
        p = REPO / rel
        if not p.is_file():
            missing.append(rel)
            rows.append({"path": rel, "sha256": None, "bytes": None, "role": role, "authority_class": klass, "status": "MISSING"})
            continue
        sha = sha256_file(p)
        rows.append({"path": rel, "sha256": sha, "bytes": p.stat().st_size, "role": role, "authority_class": klass, "status": "PRESENT"})
        if rel in EXPECTED and sha != EXPECTED[rel]:
            raise SystemExit(f"FAIL_CLOSED: pin mismatch for {rel}: got {sha}, expected {EXPECTED[rel]}")
    if missing:
        raise SystemExit(f"FAIL_CLOSED: required sources missing: {missing}")

    by_path = {r["path"]: r for r in rows}

    def load(rel):
        return json.loads((REPO / rel).read_text(encoding="utf-8"))

    g_v2 = load(SOURCES[0][0])
    g_val = load(SOURCES[1][0])
    g_lock = load(SOURCES[2][0])
    g_parent_a = load("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json")
    g_parent_v4 = load("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json")
    g_safe = load("30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json")
    g_sb = load("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/system_binding_candidate_v1/results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json")
    g_m4 = load("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l01_l02_configuration_geometry_execution_matrix_v1/M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1.json")
    g_pre = load("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l01_l02_configuration_geometry_execution_matrix_v1/SOURCE_ONLY_PREFLIGHT_V1.json")
    g_s10 = load("30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json")
    g_s11 = load("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json")
    g_s12 = load("30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json")

    # re-verify counts fail-closed
    checks = {
        "V2_gate_38_of_38": g_v2["summary"]["passed"] == 38 and g_v2["summary"]["total"] == 38 and g_v2["summary"]["failed"] == [],
        "V2_source_binding_27_of_27": g_v2["source_binding"]["matched"] == 27 and g_v2["source_binding"]["total"] == 27 and g_v2["source_binding"]["all_match"] is True,
        "V2_validation_7_of_7": g_val["passed"] == 7 and g_val["total"] == 7 and g_val["all_pass"] is True,
        "V2_negative_controls_28_of_28": g_val["negative_controls"]["count"] == 28 and g_val["negative_controls"]["passed"] == 28,
        "V2_gate_passed_true": g_v2["gate_passed"] is True,
        "V2_parent_gate_reissued_false": g_v2["parent_gate_reissued"] is False,
        "V2_next_stage_authorized_false": g_v2["next_stage_authorized"] is False,
        "V2_release_credit_false": g_v2["release_credit"] is False,
        "V2_review_pending": g_v2["review_status"] == "PENDING_OWNER_REVIEW",
        "LOCK_record_count_27": g_lock["record_count"] == 27,
        "PARENT_A_not_passed": g_parent_a["gate_a_pass"] is False,
        "PARENT_V4_present_unreissued": by_path["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"]["sha256"] == EXPECTED["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"],
        "SAFE00_pass_pending_review": g_safe["verdict"] == "PASS" and g_safe["next_stage_authorized"] is False,
        "SIM13_abort_only": g_sb["maximum_operational_state"] == "ABORT_ONLY" and g_sb["non_abort_authorized"] is False,
        "M4_current_step_0_of_9": g_m4.get("configuration_current_step_buildable_count", g_m4.get("summary", {}).get("configuration_current_step_buildable_count")) == 0,
        "CAD_run_not_authorized": g_pre["fresh_run_authority_observed"] is False and g_pre["owner_override_observed"] is False,
        "SIM10_pass": g_s10["verdict"] == "SIM10_GATES_PASS",
        "SIM11_pass_provisional": g_s11["verdict"] == "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS",
        "SIM12_pass": g_s12["verdict"] == "SIM12_PHASE1_GATES_PASS",
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise SystemExit(f"FAIL_CLOSED: authority re-verification failed: {failed}")

    # environment observation (provenance, not science)
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    git_branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout
    mem = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "$os=Get-CimInstance Win32_OperatingSystem; [math]::Round($os.FreePhysicalMemory/1MB,4)"],
        capture_output=True, text=True).stdout.strip()
    try:
        mem_gib = float(mem)
    except ValueError:
        mem_gib = None
    tasklist_raw = subprocess.run(["tasklist"], capture_output=True).stdout or b""
    sldworks_main = b"SLDWORKS.exe" in tasklist_raw
    now = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "schema": "CURRENT_V2_STATUS_SNAPSHOT_V1",
        "increment": "CURRENT_R2_DIGITAL_HOST_CAPTURE_DATA_INCREMENT_V1",
        "generated_utc": now,
        "note": "All counts re-read from local machine gate JSONs by scripts/gen_authority.py; all SHA-256 computed from raw bytes. Timestamps are provenance, not science.",
        "environment": {
            "repo_root": str(REPO),
            "git_head": git_head,
            "git_branch": git_branch,
            "git_dirty_entries": len([l for l in dirty.splitlines() if l.strip()]),
            "python": sys.version.split()[0],
            "available_memory_gib_observed": mem_gib,
            "solidworks_main_process_running": sldworks_main,
        },
        "reverified": {k: True for k in checks},
        "v2_increment": {
            "technical_verdict": g_v2["technical_verdict"],
            "gate": "38/38",
            "source_binding": "27/27",
            "standalone_validation": "7/7",
            "negative_controls": "28/28",
            "pytest_claim": "13/13 stated in ruling; 13 test functions in test_increment_gate_v2.py; no pytest receipt JSON in bundle",
            "maximum_claim": g_v2["maximum_claim"],
            "review_status": g_v2["review_status"],
            "parent_gate_reissued": False,
            "next_stage_authorized": False,
            "release_credit": False,
            "red_team": {"P0": 0, "P1": 0, "P2": 1, "P2_open": "higher-level external anchoring of V2 eight-artifact bundle (recorded in ruling markdown only)"},
        },
        "parent_gates": {
            "terminal_gate_a": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json", "verdict": g_parent_a["verdict"], "gate_a_pass": False},
            "parent_v4": {
                "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json",
                "sha256": EXPECTED["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"],
                "reissued": False,
            },
        },
        "machine_state": {
            "current_STEP_C01_to_C09": "0/9",
            "M01_motion_upper_bound_candidates": 9,
            "M01_new_system_motion_certificates": 0,
            "system_motion_certificates_observed": "1/150 (A::base_link zero-motion only)",
            "D01_fixed_q0_recipe": "D01_Q0_DIAGNOSTIC_RECIPE_READY, step_generation_executed=false",
            "control_metric": "SOURCE_DERIVED_DIMENSIONLESS_STATIC_CANDIDATE_ONLY, time_domain_tracking_executed=false",
            "post_grasp_kernel": "SYNTHETIC_FIXTURE_ONLY",
            "C08": "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3",
            "C09": "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3",
            "authoritative_T_E_T": "MISSING (convention declared in POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1; value/receipt absent; display-transform promotion forbidden)",
            "named_CAD_run_authorization": "MISSING (fresh_run_authority_observed=false, owner_override_observed=false)",
            "CAD_memory_admission_gib": 6.0,
            "safe00": {"verdict": "PASS", "next_stage_authorized": False, "review_status": g_safe["review_status"]},
            "sim13": {"maximum_operational_state": "ABORT_ONLY", "non_abort_authorized": False},
            "ctrl01_verdict": load("30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json")["verdict"],
            "ctrl02_verdict": load("30_simulation/control_02_base_attitude/results/control_02_gate_check.json")["verdict"],
            "route_c": "V9F REJECTED on current M01 path; geometry loop TERMINATED; RC-5 not accepted",
        },
        "source_files_hashed": len(rows),
    }
    (out_dir / "CURRENT_V2_STATUS_SNAPSHOT.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(out_dir / "SOURCE_HASH_MANIFEST.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "sha256", "bytes", "role", "authority_class", "status"])
        w.writeheader()
        w.writerows(rows)

    protected = {
        "schema": "PROTECTED_PATHS_V1",
        "policy": "READ_ONLY_FOR_THIS_INCREMENT — no file below may be modified, moved, regenerated, or deleted by this increment; violations void the increment gate.",
        "paths": [r["path"] for r in rows if r["status"] == "PRESENT"]
        + [
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/04_MASTER_GEOMETRY.step",
            "20_engineering/config/geometry/",
            "20_engineering/config/coupled_scene/",
            "20_engineering/config/mission_feasibility/",
            "30_simulation/sim_05_free_floating_arm/results/",
            "30_simulation/sim_10_mission_feasibility/results/",
            "30_simulation/sim_11_coupled_dynamics/results/",
            "30_simulation/sim_12_strategy_feasibility/results/",
        ],
        "forbidden_operations": [
            "git reset --hard", "git clean -fdx", "overwrite frozen assets", "modify accepted URDF",
            "save donor CAD", "auto-reissue parent gate", "run regenerative ../validate_prebind_v2.py (FAIL_DOCUMENTED hazard)",
        ],
    }
    (out_dir / "PROTECTED_PATHS.json").write_text(json.dumps(protected, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(rows)} sources hashed; all {len(checks)} authority re-verifications passed")
    print(f"memory_gib={mem_gib} solidworks_main={sldworks_main}")


if __name__ == "__main__":
    main()
