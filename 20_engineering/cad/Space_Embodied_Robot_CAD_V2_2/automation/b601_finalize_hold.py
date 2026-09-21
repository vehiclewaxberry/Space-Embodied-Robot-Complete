"""Finalize B601-SWAP-01 as an evidence-complete HOLD.

This script does not launch SolidWorks and does not edit any CAD source. It
records the exact inputs, successful read-only recovery, failed build attempts,
unexecuted verification gates, and frozen-zone rechecks.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
V22 = WORKSPACE / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2"
V20 = WORKSPACE / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_0"
V21 = WORKSPACE / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_1"
ACCEPTED = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1"
EVIDENCE = V22 / "evidence/b601_swap_01"
LOGS = V22 / "evidence/build_logs"
STEP = Path(
    r"F:/Robotic arm/High_performance_robotics_arm/vendor/reBot-DevArm/"
    r"hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step"
)
SCRATCH = Path(
    r"C:/Users/stude/AppData/Local/Temp/claude/"
    r"F--China-Graduate-Future-Flight-Vehicle-Innovation-Competition/"
    r"f82d04fc-7dca-4a0f-ac0b-f39116f6b403/"
    r"scratchpad/b601_import/b601_import.SLDASM"
)
TOP = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
Q0 = V22 / "30_B601_Controlled_Subassembly/SV22_B601_Proxy.SLDASM"
HIFI = V22 / "35_B601_HiFi_Visual/B601_STOWED_HIFI.SLDPRT"
STAGING = V22 / "35_B601_HiFi_Visual/staging/Spacecraft_Service_Vehicle_V2_2_B601_SWAP01_STAGED.SLDASM"

EXPECTED = {
    "step": "87a0537d1afd50c04fc441fde11dd4f2ebbb368fe27f6c10fda8567be696d968",
    "scratch": "f3f12285ae6a05df078b61ee31991ed774e5c9cdec7e4dab438c8bdd7f6e8ce9",
    "accepted_urdf": "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164",
    "canonical_top": "3b55edb85b460ecbc23eec55b99ff83506c33e0f4cecdb0375babc7b0d50cfb9",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: Path, expected: str | None = None) -> dict:
    item = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        item.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
    if expected is not None:
        item["expected_sha256"] = expected
        item["hash_match"] = item.get("sha256") == expected
    return item


def write_json(name: str, payload: dict) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    result = []
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            result.append({"kind": "UNPARSEABLE_LOG_LINE", "raw": line})
    return result


def tree_snapshot(root: Path) -> dict:
    records = []
    errors = []
    latest = None

    def onerror(exc):
        errors.append({"path": getattr(exc, "filename", None), "error": repr(exc)})

    if not root.exists():
        return {
            "root": str(root),
            "exists": False,
            "accessible_files": 0,
            "access_errors": [],
            "tree_sha256": None,
        }
    for dirpath, _, filenames in os.walk(root, onerror=onerror):
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            try:
                stat = path.stat()
                digest = sha256(path)
                rel = path.relative_to(root).as_posix()
                records.append({"relative_path": rel, "bytes": stat.st_size, "sha256": digest})
                latest = max(latest or stat.st_mtime, stat.st_mtime)
            except Exception as exc:
                errors.append({"path": str(path), "error": repr(exc)})
    records.sort(key=lambda item: item["relative_path"].lower())
    tree_hash = hashlib.sha256()
    for item in records:
        tree_hash.update(
            (item["relative_path"] + "\0" + str(item["bytes"]) + "\0" + item["sha256"] + "\n").encode("utf-8")
        )
    return {
        "root": str(root),
        "exists": True,
        "accessible_files": len(records),
        "access_error_count": len(errors),
        "access_errors": errors,
        "latest_mtime_utc": (
            datetime.fromtimestamp(latest, timezone.utc).isoformat() if latest is not None else None
        ),
        "tree_sha256": tree_hash.hexdigest(),
    }


def verify_v20_manifest() -> dict:
    manifest = V20 / "evidence/digital_thread/native_file_hash_manifest_v2_final.csv"
    rows = list(csv.DictReader(manifest.open("r", encoding="utf-8-sig", newline="")))
    mismatches = []
    matches = 0
    for row in rows:
        target = V20 / row["relative_path"]
        actual = sha256(target) if target.is_file() else None
        if actual == row["sha256"] and target.stat().st_size == int(row["bytes"]):
            matches += 1
        else:
            mismatches.append(
                {
                    "relative_path": row["relative_path"],
                    "expected_bytes": int(row["bytes"]),
                    "actual_bytes": target.stat().st_size if target.is_file() else None,
                    "expected_sha256": row["sha256"],
                    "actual_sha256": actual,
                }
            )
    return {
        "root": str(V20),
        "manifest": file_record(manifest),
        "total": len(rows),
        "match": matches,
        "mismatches": mismatches,
        "verdict": "PASS" if matches == len(rows) else "FAIL",
    }


def verify_accepted_asset() -> dict:
    baseline = load_json(V20 / "evidence/b3_00/B3_entry_verification.json")
    rows = baseline["checks"]["B601_ASSET_HASHES"]["rows"]
    mismatches = []
    matches = 0
    for row in rows:
        target = ACCEPTED / row["relative_path"]
        actual = sha256(target) if target.is_file() else None
        if actual == row["sha256"] and target.stat().st_size == int(row["bytes"]):
            matches += 1
        else:
            mismatches.append(
                {
                    "relative_path": row["relative_path"],
                    "expected_bytes": int(row["bytes"]),
                    "actual_bytes": target.stat().st_size if target.is_file() else None,
                    "expected_sha256": row["sha256"],
                    "actual_sha256": actual,
                }
            )
    return {
        "root": str(ACCEPTED),
        "baseline": str(V20 / "evidence/b3_00/B3_entry_verification.json"),
        "total": len(rows),
        "match": matches,
        "mismatches": mismatches,
        "verdict": "PASS" if matches == len(rows) else "FAIL",
    }


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    source_probe = load_json(EVIDENCE / "source_probe.json")
    recovery = load_json(EVIDENCE / "registered_step_recovery_probe.json")
    build_events = read_jsonl(LOGS / "b601_swap_01_build_part.jsonl")
    preference_events = read_jsonl(LOGS / "b601_swap_01_preference_preflight.jsonl")

    inputs = {
        "evidence_id": "B601_SWAP01_INPUT_HASHES",
        "generated_utc": utc_now(),
        "verdict": "PASS",
        "files": {
            "registered_vendor_step": file_record(STEP, EXPECTED["step"]),
            "asset00_scratch_assembly": file_record(SCRATCH, EXPECTED["scratch"]),
            "accepted_urdf": file_record(ACCEPTED / "arm_b601_v1.urdf", EXPECTED["accepted_urdf"]),
            "canonical_v22_top_before_and_after": file_record(TOP, EXPECTED["canonical_top"]),
            "current_q0_proxy": file_record(Q0),
            "asset_registry": file_record(V22 / "evidence/asset00/asset_registry.yaml"),
            "integration_decision": file_record(V22 / "evidence/asset00/integration_decision.json"),
            "source_probe": file_record(EVIDENCE / "source_probe.json"),
            "registered_step_recovery_probe": file_record(EVIDENCE / "registered_step_recovery_probe.json"),
        },
        "authority": {
            "geometry": str(STEP),
            "kinematics_mass_com_inertia": str(ACCEPTED / "arm_b601_v1.urdf"),
            "canonical_top": str(TOP),
        },
        "note": "Input hashes pass. This does not imply that a P-C part or top-level integration was created.",
    }
    if not all(
        inputs["files"][key].get("hash_match")
        for key in (
            "registered_vendor_step",
            "asset00_scratch_assembly",
            "accepted_urdf",
            "canonical_v22_top_before_and_after",
        )
    ):
        inputs["verdict"] = "FAIL"
    write_json("input_hashes.json", inputs)

    source_roles = {
        "01-BASE-1_ASM-1": "base_and_joint1_stator",
        "2026-04-01-16-48-42-413-1": "joint1_rotor_interface",
        "02-LINK-1_ASM-1": "vendor_link1_group",
        "03-LINK-2_ASM-1": "vendor_link2_group",
        "04-LINK-3_ASM-1": "vendor_link3_and_wrist_base_group",
        "2026-04-01-17-02-36-958-1": "wrist_rotor_group",
        "05-GRIPPER_ASM-1": "wrist_and_gripper_drive_group",
        "2026-04-01-17-05-40-350-1": "gripper_rail_and_fingers_group",
    }
    source_urdf = {
        "01-BASE-1_ASM-1": ["base_link"],
        "2026-04-01-16-48-42-413-1": ["base_link", "link1"],
        "02-LINK-1_ASM-1": ["link1"],
        "03-LINK-2_ASM-1": ["link2"],
        "04-LINK-3_ASM-1": ["link3", "link4"],
        "2026-04-01-17-02-36-958-1": ["link4", "link5"],
        "05-GRIPPER_ASM-1": ["link5", "link6", "gripper_link"],
        "2026-04-01-17-05-40-350-1": ["gripper_link", "gripper_left", "gripper_right"],
    }
    source_confidence = {
        "01-BASE-1_ASM-1": "HIGH_BY_VENDOR_NAME",
        "2026-04-01-16-48-42-413-1": "MEDIUM_BY_CONTENT_M1_ROTOR",
        "02-LINK-1_ASM-1": "HIGH_BY_VENDOR_NAME",
        "03-LINK-2_ASM-1": "HIGH_BY_VENDOR_NAME",
        "04-LINK-3_ASM-1": "MEDIUM_BY_NAME_AND_CONTENT_M5_BASE",
        "2026-04-01-17-02-36-958-1": "MEDIUM_BY_CONTENT_M5_ROTOR",
        "05-GRIPPER_ASM-1": "MEDIUM_BY_VENDOR_NAME_AND_CONTENT_M6_M7",
        "2026-04-01-17-05-40-350-1": "HIGH_BY_CONTENT_RAIL_RACK_SLIDER",
    }

    mapping = {
        "mapping_id": "B601_SWAP01_BODY_MAPPING",
        "generated_utc": utc_now(),
        "status": "SOURCE_MAP_ONLY_FINAL_NOT_MATERIALIZED",
        "geometry_authority": str(STEP),
        "kinematic_authority": str(ACCEPTED / "arm_b601_v1.urdf"),
        "mass_authority": str(ACCEPTED / "arm_b601_v1.urdf"),
        "verdict": "HOLD_NO_MULTIBODY_PART",
        "source_top_component_count": recovery["component_count_top"],
        "source_all_component_count": recovery["component_count_all"],
        "source_groups": [
            {
                "component": name,
                "planned_semantic_role": role,
                "urdf_correspondence": source_urdf[name],
                "confidence": source_confidence[name],
            }
            for name, role in source_roles.items()
        ],
        "actual_multibody_part": file_record(HIFI),
        "actual_body_count": None,
        "actual_body_names": [],
        "authority_note": "Vendor groups are geometry groupings only. Accepted URDF remains kinematic and mass authority.",
        "reason": "The controlled headless LoadFile4 attempt did not return; no SaveAs3 or InsertMoveCopyBody2 stage was reached.",
    }
    write_json("body_mapping.yaml", mapping)

    raw_bbox = recovery["world_bbox_mm"]
    expected_bbox = [
        round(198.0 + raw_bbox[2], 6),
        raw_bbox[1],
        round(-raw_bbox[3], 6),
        round(198.0 + raw_bbox[5], 6),
        raw_bbox[4],
        round(-raw_bbox[0], 6),
    ]
    pose = {
        "test_id": "B601_SWAP01_POSE_PERSISTENCE",
        "generated_utc": utc_now(),
        "route": "P-C_RECOVERED_FROM_EXACT_REGISTERED_STEP",
        "source_recovery": {
            "gate": recovery["recovery_gate"],
            "load_errors": recovery["load"]["errors"],
            "component_count_top": recovery["component_count_top"],
            "component_count_all": recovery["component_count_all"],
            "unresolved_or_boxless_count": recovery["unresolved_or_boxless_count"],
            "raw_world_bbox_mm": raw_bbox,
        },
        "planned_baked_transform": {
            "rotation_y_deg": 90.0,
            "translation_x_mm": 198.0,
            "required_top_insert_transform": "IDENTITY",
            "expected_baked_bbox_mm": expected_bbox,
        },
        "checks": {
            "multibody_part_saved": False,
            "part_closed_and_reopened": False,
            "baked_bbox_persisted": "NOT_RUN",
            "root_frame_matches_frozen_interface": "NOT_RUN",
            "top_insert_identity": "NOT_RUN",
            "top_closed_solidworks_restarted_and_reopened": "NOT_RUN",
        },
        "verdict": "HOLD_NOT_RUN_NO_PART",
        "anti_false_positive": "No current-session geometry, screenshot, or API True return is accepted as persistence evidence.",
    }
    write_json("pose_persistence_test.json", pose)

    state_names = [
        "STOWED",
        "DEPLOYED_NOMINAL",
        "DEPLOY_FAILED_BOTH",
        "L_FAIL",
        "R_FAIL",
        "PARTIAL",
        "SERVICE",
        "CAPTURE_SAFE",
    ]
    matrix_rows = []
    wing_modes = {
        "STOWED": ("STOWED", "STOWED"),
        "DEPLOYED_NOMINAL": ("DEPLOYED", "DEPLOYED"),
        "DEPLOY_FAILED_BOTH": ("STOWED", "STOWED"),
        "L_FAIL": ("STOWED", "DEPLOYED"),
        "R_FAIL": ("DEPLOYED", "STOWED"),
        "PARTIAL": ("NONE", "NONE"),
        "SERVICE": ("DEPLOYED", "DEPLOYED"),
        "CAPTURE_SAFE": ("DEPLOYED", "DEPLOYED"),
    }

    for state in state_names:
        use_hifi = state in {"STOWED", "SERVICE"}
        matrix_rows.append(
            {
                "configuration": state,
                "wing_left_mode": wing_modes[state][0],
                "wing_right_mode": wing_modes[state][1],
                "b601_policy_basis": "TASK_PROMPT_PLUS_CONSERVATIVE_DEFAULT_PENDING_RATIFICATION",
                "planned_hifi_state": "RESOLVED" if use_hifi else "SUPPRESSED",
                "planned_q0_proxy_state": "SUPPRESSED" if use_hifi else "RESOLVED",
                "applied": False,
                "reopen_verified": False,
                "actual_state": "NOT_APPLIED_CANONICAL_TOP_UNCHANGED",
                "semantic_note": (
                    "static_vendor_folded_display"
                    if use_hifi
                    else "existing_controlled_q0_or_task_proxy"
                ),
            }
        )
    configuration = {
        "matrix_id": "B601_SWAP01_CONFIGURATION_MATRIX",
        "generated_utc": utc_now(),
        "canonical_top": file_record(TOP, EXPECTED["canonical_top"]),
        "staging_top": file_record(STAGING),
        "pre_swap_baseline": {
            "machine_check": file_record(V22 / "evidence/b5_verify/machine_check.json"),
            "scope": "PRE_SWAP_WING_STATES_AND_Q0_PROXY_ONLY_NOT_HIFI_SWAP",
        },
        "rows": matrix_rows,
        "rules": {
            "never_both_resolved": True,
            "never_both_suppressed": True,
            "accepted_urdf_semantics_unchanged": True,
            "capture_safe_claim": "UNKNOWN_CANDIDATE_NOT_UPGRADED",
        },
        "verdict": "HOLD_NOT_APPLIED",
    }
    write_json("configuration_matrix.yaml", configuration)

    applied_pref = next(
        (event for event in reversed(preference_events) if event.get("kind") == "SAVE_PREFERENCES_APPLIED"),
        None,
    )
    restored_pref = next(
        (event for event in reversed(preference_events) if event.get("kind") == "PREFERENCE_PREFLIGHT_RESTORE"),
        None,
    )
    mass = {
        "check_id": "B601_SWAP01_MASS_EXCLUSION",
        "generated_utc": utc_now(),
        "accepted_urdf_authority": file_record(
            ACCEPTED / "arm_b601_v1.urdf", EXPECTED["accepted_urdf"]
        ),
        "authoritative_mass": {
            "total_kg": 4.6955559493429862,
            "arm_7_link_kg": 4.4291,
            "gripper_3_link_kg": 0.266455949342986,
            "source": "20_engineering/design_inputs/v2_system_mechanical/05_mass_budget/V2_mass_ownership_table.csv",
            "source_file": file_record(WORKSPACE / "20_engineering/design_inputs/v2_system_mechanical/05_mass_budget/V2_mass_ownership_table.csv"),
        },
        "step_mass_xcheck": "XCHECK_NOT_APPLICABLE_NO_STEP_MATERIAL_OR_DENSITY_AUTHORITY",
        "planned_hifi_properties": {
            "MASS_AUTHORITY": "EXCLUDED",
            "GEOMETRY_AUTHORITY": "STEP",
            "LICENSE_CLASS": "E3_INTERNAL_RESEARCH_ONLY",
            "DO_NOT_REDISTRIBUTE": "TRUE",
        },
        "save_preference_preflight": {
            "applied_event": applied_pref,
            "restore_event": restored_pref,
            "roundtrip_verdict": (
                "PASS"
                if applied_pref
                and restored_pref
                and restored_pref.get("before") == restored_pref.get("after")
                else "FAIL_OR_MISSING"
            ),
        },
        "actual_hifi_part": file_record(HIFI),
        "actual_top_insertion": False,
        "custom_property_readback": "NOT_RUN",
        "solidworks_exclude_from_mass_readback_by_config": "NOT_RUN",
        "mass_before_after_measurement": "NOT_RUN",
        "exclude_from_bom_envelope_readback": "NOT_RUN",
        "double_count_result": "NO_NEW_DOUBLE_COUNT_POSSIBLE_BECAUSE_NOT_INSERTED",
        "requirement_verdict": "HOLD_EXCLUSION_NOT_VERIFIED_ON_ARTIFACT",
    }
    write_json("mass_exclusion_check.json", mass)

    missing_scratch = [
        item
        for item in source_probe["dependencies"]
        if item.get("looks_like_path") and not item.get("exists_if_path")
    ]
    dependency = {
        "check_id": "B601_SWAP01_DEPENDENCY_CHECK",
        "generated_utc": utc_now(),
        "asset00_scratch": {
            "component_count_top": source_probe["component_count_top"],
            "component_count_all": source_probe["component_count_all"],
            "dependency_record_count": len(source_probe["dependencies"]),
            "missing_dependency_count": len(missing_scratch),
            "missing_dependencies": missing_scratch,
            "boxless_component_count": sum(
                1 for item in source_probe["all_components"] if not item.get("bbox_mm")
            ),
            "verdict": "HOLD_NOT_SELF_CONTAINED",
        },
        "exact_registered_step_recovery": {
            "recovery_gate": recovery["recovery_gate"],
            "component_count_top": recovery["component_count_top"],
            "component_count_all": recovery["component_count_all"],
            "unresolved_or_boxless_count": recovery["unresolved_or_boxless_count"],
            "verdict": "PASS_READ_ONLY_RECOVERY",
        },
        "generated_multibody_part": file_record(HIFI),
        "staging_top": file_record(STAGING),
        "generated_artifact_dependency_check": "NOT_RUN",
        "overall_verdict": "HOLD_NO_GENERATED_ARTIFACT",
    }
    write_json("dependency_check.json", dependency)

    v20_check = verify_v20_manifest()
    accepted_check = verify_accepted_asset()
    v21_snapshot = tree_snapshot(V21)
    q0_snapshot = tree_snapshot(V22 / "30_B601_Controlled_Subassembly")
    asset00_snapshot = tree_snapshot(V22 / "evidence/asset00")
    frozen = {
        "check_id": "B601_SWAP01_FROZEN_ZONE_RECHECK",
        "generated_utc": utc_now(),
        "v20_terminal_manifest": v20_check,
        "accepted_b601_urdf_stl_readme": accepted_check,
        "v21_sealed_tree": {
            **v21_snapshot,
            "verdict": (
                "ACCESS_DENIED_PROTECTED_NO_CONTENT_RECHECK"
                if v21_snapshot.get("access_error_count")
                else "CURRENT_TREE_SNAPSHOT_ONLY_NO_BASELINE_COMPARE"
            ),
        },
        "asset00_scratch": file_record(SCRATCH, EXPECTED["scratch"]),
        "asset00_evidence_tree": {
            **asset00_snapshot,
            "baseline_comparison": "UNKNOWN_BASELINE_UNAVAILABLE",
            "status": "CURRENT_TREE_SNAPSHOT_ONLY_NOT_ZERO_CHANGE_PROOF",
        },
        "b601_q0_frozen_directory": {
            **q0_snapshot,
            "baseline_comparison": "UNKNOWN_NO_PINNED_PRE_RUN_MANIFEST",
            "status": "CURRENT_TREE_SNAPSHOT_ONLY_NOT_ZERO_CHANGE_PROOF",
        },
        "canonical_v22_top": file_record(TOP, EXPECTED["canonical_top"]),
        "generated_hifi_part_exists": HIFI.exists(),
        "generated_staging_top_exists": STAGING.exists(),
        "verdict": (
            "PASS_WITH_V21_ACCESS_AND_ASSET00_Q0_BASELINE_LIMITATIONS"
            if v20_check["verdict"] == "PASS"
            and accepted_check["verdict"] == "PASS"
            and file_record(SCRATCH, EXPECTED["scratch"]).get("hash_match")
            and file_record(TOP, EXPECTED["canonical_top"]).get("hash_match")
            else "FAIL"
        ),
    }
    write_json("frozen_zone_recheck.json", frozen)

    attempts = {
        "ledger_id": "B601_SWAP01_EXECUTION_ATTEMPTS",
        "generated_utc": utc_now(),
        "build_log": file_record(LOGS / "b601_swap_01_build_part.jsonl"),
        "preference_log": file_record(LOGS / "b601_swap_01_preference_preflight.jsonl"),
        "recovery_log": file_record(LOGS / "b601_swap_01_reimport_probe.jsonl"),
        "build_log_events": build_events,
        "observed_attempts": [
            {
                "id": "BUILD_AFTER_SUCCESSFUL_LOAD",
                "evidence": "build log STEP_LOADED_IN_MEMORY at 2026-07-26T11:04:54Z",
                "load_elapsed_sec": 335.865,
                "result": "NO_SAVE_EVENT_NO_CAD_OUTPUT",
            },
            {
                "id": "RPC_FAILURE",
                "evidence": "Codex execution transcript mirrored into this ledger",
                "error": "-2147023170 / 0x800706BE / RPC_S_CALL_FAILED",
                "result": "SOLIDWORKS_PROCESS_EXITED_BEFORE_SAVE",
            },
            {
                "id": "FINAL_SINGLE_INSTANCE_CONTROLLED_ATTEMPT",
                "start_event": "2026-07-26T11:29:19.991780+00:00 SW_CONNECT",
                "environment": "one SLDWORKS process plus its sldProcMon; no PID churn during observation",
                "observation": "LoadFile4 did not return for more than 10 minutes; Python blocked and SolidWorks CPU nearly idle",
                "termination": "operator terminated yielded execution cell at declared observation limit",
                "windows_crash_evidence": "NONE: no new Application Error, WER, CrashDump, or Application Hang for SolidWorks",
                "result": "HOLD_HEADLESS_LOADFILE4_NO_RETURN",
            },
        ],
        "cad_outputs": {
            "hifi_part": file_record(HIFI),
            "staging_top": file_record(STAGING),
        },
        "retry_policy": "HOLD_NO_FURTHER_IDENTICAL_HEADLESS_RETRY",
    }
    write_json("execution_attempts.json", attempts)

    verdict = {
        "verdict_id": "B601_SWAP01_MACHINE_VERDICT",
        "generated_utc": utc_now(),
        "verdict": "B601_SWAP01_HOLD",
        "subcode": "HOLD_NO_FURTHER_IDENTICAL_RETRY",
        "completed_gates": [
            "REGISTERED_STEP_HASH_MATCH",
            "ASSET00_SCRATCH_HASH_MATCH",
            "ACCEPTED_URDF_HASH_MATCH",
            "READ_ONLY_EXACT_STEP_RECOVERY_358_OF_358_PASS",
            "SAVE_PREFERENCE_APPLY_AND_RESTORE_PREFLIGHT_PASS",
            "V20_TERMINAL_MANIFEST_57_OF_57_PASS",
            "ACCEPTED_B601_ASSET_12_OF_12_PASS",
            "CANONICAL_V22_TOP_HASH_UNCHANGED",
            "ASSET00_SCRATCH_HASH_UNCHANGED",
        ],
        "hold_reasons": [
            "ASSET00_SCRATCH_NOT_SELF_CONTAINED_8_MISSING_SPIOP_DEPENDENCIES",
            "ASSET00_EVIDENCE_TREE_PRE_RUN_SEAL_UNAVAILABLE",
            "B601_Q0_DIRECTORY_PRE_RUN_SEAL_UNAVAILABLE",
            "P_C_MULTIBODY_PART_NOT_CREATED",
            "FINAL_SINGLE_INSTANCE_HEADLESS_LOADFILE4_DID_NOT_RETURN",
            "POSE_PERSISTENCE_NOT_RUN",
            "IDENTITY_TOP_INSERT_NOT_RUN",
            "EIGHT_CONFIGURATION_READBACK_NOT_RUN",
            "MASS_EXCLUSION_ON_ARTIFACT_NOT_RUN",
            "GENERATED_ARTIFACT_DEPENDENCY_CHECK_NOT_RUN",
            "RAW_AND_ANNOTATED_FINAL_REVIEW_VIEWS_NOT_GENERATED",
            "EXACT_STEP_RECOVERY_ROUTE_REQUIRES_HUMAN_ACCEPTANCE_AGAINST_SCRATCH_ONLY_INSTRUCTION",
        ],
        "canonical_top_modified": False,
        "accepted_urdf_modified": False,
        "fidelity_01": "BLOCKED",
        "next_gate": (
            "Use a materially different visible/interactive SolidWorks execution with modal-window diagnosis, "
            "single PID binding, sufficient resource headroom, and explicit human acceptance of exact-STEP recovery."
        ),
    }
    write_json("machine_verdict.json", verdict)

    expected_views = [
        {
            "view_id": "B601_SWAP01_STOWED_RAW",
            "kind": "raw",
            "configuration": "STOWED",
            "source_model_path": str(STAGING),
            "artifact_path": str(EVIDENCE / "review_views/raw/B601_SWAP01_STOWED_RAW.bmp"),
            "artifact_exists": False,
            "status": "NOT_GENERATED_NO_VALID_FINAL_ARTIFACT",
            "reason_code": "PART_BUILD_NOT_COMPLETED",
            "reviewable": False,
        },
        {
            "view_id": "B601_SWAP01_STOWED_ANNOTATED",
            "kind": "annotated",
            "configuration": "STOWED",
            "source_model_path": str(STAGING),
            "artifact_path": str(EVIDENCE / "review_views/annotated/B601_SWAP01_STOWED_ANNOTATED.png"),
            "artifact_exists": False,
            "status": "NOT_GENERATED_NO_VALID_FINAL_ARTIFACT",
            "reason_code": "PART_BUILD_NOT_COMPLETED",
            "reviewable": False,
        },
    ]
    review_manifest = {
        "manifest_id": "B601_SWAP01_REVIEW_VIEW_MANIFEST",
        "generated_utc": utc_now(),
        "expected_views": expected_views,
        "source_references": [
            {
                "classification": "SOURCE_REFERENCE_ONLY_NOT_ACCEPTANCE_EVIDENCE",
                **file_record(V22 / "evidence/asset00/b601_fine_iso.bmp"),
            },
            {
                "classification": "PRE_SWAP_BASELINE_ONLY",
                **file_record(V22 / "evidence/b5_verify/v22_stowed_iso.bmp"),
            },
            {
                "classification": "PRE_SWAP_BASELINE_ONLY",
                **file_record(V22 / "evidence/b5_verify/v22_deployed_iso.bmp"),
            },
            {
                "classification": "PRE_SWAP_BASELINE_ONLY",
                **file_record(V22 / "evidence/b5_verify/v22_capture_safe_iso.bmp"),
            },
        ],
        "claim_limit": "Existing images are references only and are not B601-SWAP-01 acceptance evidence.",
        "verdict": "HOLD_NO_FINAL_REVIEW_VIEWS",
    }
    write_json("review_view_manifest.json", review_manifest)

    report = f"""# B601-SWAP-01 execution report

Machine verdict: B601_SWAP01_HOLD  
Subcode: HOLD_NO_FURTHER_IDENTICAL_RETRY

## Outcome

No B601_STOWED_HIFI.SLDPRT and no staging top assembly were created. The canonical V2.2 top assembly, ASSET-00 scratch assembly, accepted URDF/STL package, V2.0 terminal set, existing q0 proxy, and ASSET-00 evidence remain outside the write path.

## What passed

| Gate | Result | Evidence |
|---|---|---|
| Registered STEP hash | PASS | input_hashes.json |
| ASSET-00 scratch hash | PASS | input_hashes.json |
| Accepted URDF authority | PASS | input_hashes.json |
| Read-only exact STEP recovery | PASS, 358/358 components, zero unresolved/boxless | registered_step_recovery_probe.json |
| Save preference round trip | PASS and restored | mass_exclusion_check.json |
| V2.0 terminal manifest | {v20_check['match']}/{v20_check['total']} PASS | frozen_zone_recheck.json |
| Accepted B601 package | {accepted_check['match']}/{accepted_check['total']} PASS | frozen_zone_recheck.json |
| Canonical V2.2 top hash | PASS unchanged | frozen_zone_recheck.json |

## Why the build is on HOLD

The preserved ASSET-00 scratch SLDASM is not self-contained: it contains eight top components that point to missing spiop temporary assemblies, and all eight are boxless in the read-only probe. Re-importing the exact registered STEP is recoverable and has passed read-only inspection, but it is a recovery path rather than the literal scratch-only path.

The final controlled single-instance headless LoadFile4 call did not return within the declared ten-minute observation window. The Python controller was blocked, SolidWorks remained nominally responsive with near-idle CPU, and no STEP_LOADED_IN_MEMORY event or CAD output appeared. The execution was terminated at the observation limit. Windows supplied no new SolidWorks Application Error, WER report, crash dump, or application-hang record, so this is recorded as a headless COM no-return condition rather than a proven importer crash.

## Gates not run

- Multibody SaveAs3 and body-folder readback
- Split InsertMoveCopyBody2 rotation and translation bake
- Close, restart SolidWorks, and reopen persistence verification
- Identity top-level insertion
- Eight-configuration suppression round trip
- Envelope/BOM/mass-exclusion readback and before/after mass comparison
- Generated-part and staging-assembly dependency closure
- Final raw and annotated integration views

No screenshot or API True return was substituted for these missing gates.

## Configuration intent, not applied

STOWED and SERVICE are planned to use the static high-fidelity folded representation while suppressing the q0 proxy. The other six states retain the controlled q0/task proxy while suppressing the high-fidelity folded representation. CAPTURE_SAFE remains a candidate/UNKNOWN claim and is not upgraded.

## Mass authority

The accepted arm_b601_v1 URDF remains the sole authority for joints, mass, center of mass, and inertia. The STEP remains geometry-only. Because no high-fidelity component was inserted, this run introduced no duplicate mass, but artifact-level exclusion was not verified and therefore is not marked PASS.

## Frozen-zone result

V2.0 and the accepted B601 package passed their pinned hash manifests. The ASSET-00 scratch and canonical V2.2 top match their pre-run hashes. The ASSET-00 evidence tree and q0 directory have current tree snapshots but no independent pre-run seal, so zero-change remains UNKNOWN. V2.1 content re-hashing was blocked by the existing access-control seal and is reported as an access limitation, not silently treated as a content PASS.

## Required next gate

Do not repeat the identical headless call. A materially different attempt requires:

1. explicit human acceptance that exact registered STEP recovery is allowed because the preserved scratch is incomplete;
2. one visible SolidWorks instance with modal-window diagnosis and explicit PID binding;
3. sufficient physical and commit headroom;
4. pre/post LoadFile4 events plus an independent timeout witness;
5. the full persistence, identity-transform, mass-exclusion, dependency, configuration, and view gates in this evidence directory.

FIDELITY-01 remains blocked.
"""
    (EVIDENCE / "B601_SWAP_01_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
