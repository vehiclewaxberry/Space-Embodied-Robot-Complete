#!/usr/bin/env python3
"""Generate the write-once, promotion-bound Solar R2B digital-thread set.

This is a pure filesystem evidence program.  It never imports a SOLIDWORKS
automation library, never attaches to SOLIDWORKS, never opens or writes CAD,
and never modifies URDF, pose, control, mass, or quarantine evidence.  ``audit``
is read-only.  ``create`` fully serializes and validates every output before
performing any O_EXCL write.  ``verify`` reconstructs every expected byte from
the still-hash-identical inputs and performs read-only byte comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "F3R2_V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_RECEIPT_V1"
VERDICT = "V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_BOUND_WRITE_ONCE_PASS"

PROMOTION_SHA256 = "71952A7AC8761D59BB4596381C1DABD873AE2EFD0B7B8F502A0A95187349A334"
P9_FRESH_PASS_SHA256 = "1E4AC41F97317F0D16A8113CCDA79117B4AC08A026F9E5ED39E0F64E569EA753"
STATE_AUTHORITY_SHA256 = "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8"
ARCHITECTURE_SHA256 = "3CC38465A6B7FA6E91F275BAE4052E1787B5A44A6F196AFCEFA88AA7D209D545"
ORACLE_SHA256 = "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6"
OLD_STATE_MACHINE_SHA256 = "BE933183F42BD481EE2A6E905C06ED5408A2E1396EA14BA836BD61CE06D17CAB"
QUARANTINED_REGISTER_SHA256 = "EA09A55A8845DF92EFDC7C55A20BB884306BC4401AC201A269302C9900457F05"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
POSE_AUTHORITY_SHA256 = "1EB0D4CF3A7CC2B0F785B7C465C3BD89990A6F0647806B12C06BC931F0A3C326"
CONTROL_BASELINE_SHA256 = "6F10BF844B975F416FAB0B7BB02CB82D984A9CC8A5BF81D442870C7EBE554B75"
ACTION_MASK_SHA256 = "56A6DC8A8ECD907F48EBB6621771874CAE8A3A3E247D925840822A91246C77B3"

STATE_NAMES = [
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
]

STATE_ANGLES = {
    "SOLAR_STOWED": {"LEFT": [0, 0, 0], "RIGHT": [0, 0, 0]},
    "SOLAR_DEPLOY_STAGE1": {"LEFT": [90, 0, 0], "RIGHT": [90, 0, 0]},
    "SOLAR_DEPLOY_STAGE2": {"LEFT": [90, 90, 0], "RIGHT": [90, 90, 0]},
    "SOLAR_DEPLOYED_NOMINAL": {"LEFT": [90, 90, 90], "RIGHT": [90, 90, 90]},
    "SOLAR_LEFT_FAIL": {"LEFT": [0, 0, 0], "RIGHT": [90, 90, 90]},
    "SOLAR_RIGHT_FAIL": {"LEFT": [90, 90, 90], "RIGHT": [0, 0, 0]},
    "SOLAR_BOTH_FAIL": {"LEFT": [0, 0, 0], "RIGHT": [0, 0, 0]},
}

STATE_HINGES = {
    "SOLAR_STOWED": {
        "LEFT": ["STOWED_STOP", "STOWED_STOP", "STOWED_STOP"],
        "RIGHT": ["STOWED_STOP", "STOWED_STOP", "STOWED_STOP"],
    },
    "SOLAR_DEPLOY_STAGE1": {
        "LEFT": ["DEPLOYED_STOP", "STOWED_STOP", "STOWED_STOP"],
        "RIGHT": ["DEPLOYED_STOP", "STOWED_STOP", "STOWED_STOP"],
    },
    "SOLAR_DEPLOY_STAGE2": {
        "LEFT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "STOWED_STOP"],
        "RIGHT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "STOWED_STOP"],
    },
    "SOLAR_DEPLOYED_NOMINAL": {
        "LEFT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "DEPLOYED_STOP"],
        "RIGHT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "DEPLOYED_STOP"],
    },
    "SOLAR_LEFT_FAIL": {
        "LEFT": ["ROOT_RELEASE_FAIL", "BLOCKED_UPSTREAM", "BLOCKED_UPSTREAM"],
        "RIGHT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "DEPLOYED_STOP"],
    },
    "SOLAR_RIGHT_FAIL": {
        "LEFT": ["DEPLOYED_STOP", "DEPLOYED_STOP", "DEPLOYED_STOP"],
        "RIGHT": ["ROOT_RELEASE_FAIL", "BLOCKED_UPSTREAM", "BLOCKED_UPSTREAM"],
    },
    "SOLAR_BOTH_FAIL": {
        "LEFT": ["ROOT_RELEASE_FAIL", "BLOCKED_UPSTREAM", "BLOCKED_UPSTREAM"],
        "RIGHT": ["ROOT_RELEASE_FAIL", "BLOCKED_UPSTREAM", "BLOCKED_UPSTREAM"],
    },
}

TARGET_RELATIVE_PATHS = {
    "state_machine_r2": "09_digital_thread/V5_MECHANICAL_STATE_MACHINE_R2.yaml",
    "solar_annex_r2b": "09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX_R2B.yaml",
    "solar_state_register": "04_configurations/V5_SOLAR_STATE_REGISTER.csv",
    "receipt": "13_validation/V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_RECEIPT.json",
    "manifest": "14_release/V5_DIGITAL_THREAD_SOLAR_R2B_MANIFEST_SHA256.txt",
}


class DigitalThreadError(RuntimeError):
    """Fail-closed evidence or serialization error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DigitalThreadError(message)


def release_root() -> Path:
    return Path(__file__).resolve().parent.parent


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_fact(path: Path) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file(), f"required file missing: {path}")
    require(not path.is_symlink(), f"symlink is not accepted as evidence: {path}")
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


def virtual_fact(path: Path, data: bytes) -> dict[str, Any]:
    return {"path": path.resolve().as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


def require_hash(fact: dict[str, Any], expected: str, label: str) -> None:
    require(fact["sha256"] == expected, f"{label}: SHA256 mismatch; expected {expected}, got {fact['sha256']}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DigitalThreadError(f"{label}: invalid UTF-8 JSON: {exc}") from exc
    require(isinstance(value, dict), f"{label}: JSON root must be an object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    data = text.encode("utf-8")
    require(json.loads(data.decode("utf-8")) == value, "canonical JSON round trip failed")
    return data


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    raise DigitalThreadError(f"unsupported YAML scalar type: {type(value).__name__}")


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            require(isinstance(key, str) and key, "YAML mapping key must be a nonempty string")
            encoded_key = key if key.replace("_", "").replace("-", "").isalnum() else yaml_scalar(key)
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{encoded_key}:")
                lines.extend(yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}{encoded_key}: {yaml_scalar(child)}")
        return lines
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(child)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def yaml_bytes(value: dict[str, Any]) -> bytes:
    require(isinstance(value, dict) and value, "YAML root must be a nonempty mapping")
    return ("\n".join(yaml_lines(value)) + "\n").encode("utf-8")


def target_paths(root: Path) -> dict[str, Path]:
    return {name: (root / relative).resolve() for name, relative in TARGET_RELATIVE_PATHS.items()}


def parse_pose_register(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(rows, "pose authority register is empty")
    by_pose = {row.get("pose", ""): row for row in rows}
    require(len(by_pose) == len(rows), "pose authority register has duplicate pose names")
    for pose in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"):
        require(pose in by_pose and by_pose[pose].get("q_deg", "").strip(), f"authorized pose missing q: {pose}")
    require("Q_SERVICE_GRASP" in by_pose, "Q_SERVICE_GRASP authority row missing")
    require(not by_pose["Q_SERVICE_GRASP"].get("q_deg", "").strip(), "Q_SERVICE_GRASP q must remain undefined")
    require(by_pose["Q_SERVICE_GRASP"].get("source_status") == "NOT_DEFINED", "Q_SERVICE_GRASP must remain NOT_DEFINED")
    return by_pose


def validate_state_authority(authority: dict[str, Any]) -> None:
    require(authority.get("schema") == "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B", "R2B state authority schema mismatch")
    coordinate = authority.get("coordinate_contract", {})
    require(coordinate.get("logical_vector_order") == ["ROOT", "H12", "H23"], "logical vector order mismatch")
    require(coordinate.get("logical_angle_semantics") == "0=STOWED_ENDPOINT; 90=DEPLOYED_ENDPOINT", "angle semantics mismatch")
    states = authority.get("states")
    require(isinstance(states, dict) and list(states) == STATE_NAMES, "state authority must contain exactly seven states in authority order")
    for state in STATE_NAMES:
        row = states[state]
        require(row.get("LEFT") == STATE_ANGLES[state]["LEFT"], f"{state}: LEFT angles mismatch")
        require(row.get("RIGHT") == STATE_ANGLES[state]["RIGHT"], f"{state}: RIGHT angles mismatch")
        require(row.get("hinge_state_LEFT") == STATE_HINGES[state]["LEFT"], f"{state}: LEFT hinge semantics mismatch")
        require(row.get("hinge_state_RIGHT") == STATE_HINGES[state]["RIGHT"], f"{state}: RIGHT hinge semantics mismatch")
    defaults = authority.get("state_record_defaults", {})
    require(defaults.get("arm_clearance_mm") is None, "authority arm clearance default must be null")
    require(defaults.get("bus_clearance_mm") is None, "authority bus clearance default must be null")
    require(defaults.get("harness_clearance_mm") is None, "authority harness clearance default must be null")


def validate_promotion(promotion: dict[str, Any]) -> list[dict[str, Any]]:
    require(promotion.get("schema") == "F3R2_V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT_V1", "promotion schema mismatch")
    require(promotion.get("verdict") == "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION", "promotion verdict mismatch")
    scope = promotion.get("promotion_scope", {})
    require(scope.get("classification") == "COMPETITION_PROTOTYPE_BASELINE_CANDIDATE", "promotion classification mismatch")
    require(scope.get("configuration_owner") == "SIDE_SLDASM_ONLY", "configuration owner must be side SLDASM only")
    require(scope.get("top_level_allowed_operation") == "SELECT_REFERENCED_CONFIGURATION_ONLY", "top operation mismatch")
    require(scope.get("top_level_second_driver") == "PROHIBITED", "top second driver must be prohibited")
    require(scope.get("cad_write_performed") is False and scope.get("copy_performed") is False, "promotion must be reference-only")
    contract = promotion.get("configuration_contract", {})
    require(contract.get("configuration_owner") == "SIDE_SLDASM_ONLY", "promotion configuration contract owner mismatch")
    require(contract.get("exact_configuration_count_each_side") == 7, "promotion side configuration count mismatch")
    require(contract.get("exact_configurations_authority_order") == STATE_NAMES, "promotion state name order mismatch")
    require(contract.get("state_angles_deg") == STATE_ANGLES, "promotion state angle table mismatch")
    require(contract.get("top_level_second_driver") == "PROHIBITED", "promotion second driver mismatch")
    counts = promotion.get("cad_baseline", {}).get("counts", {})
    require(counts == {"rigid_panel_module_sldasm": 6, "side_state_owner_sldasm": 2, "sldprt": 38, "total": 46}, "promotion CAD counts mismatch")
    fresh_fact = promotion.get("inputs", {}).get("fresh_read_only_pass", {})
    require(fresh_fact.get("sha256") == P9_FRESH_PASS_SHA256, "promotion does not bind the authorized P9 fresh pass")
    zero = promotion.get("zero_mutation", {})
    require(zero.get("cad_write_calls") == 0, "promotion does not attest zero CAD writes")
    require(zero.get("all_46_cad_hash_pre_equals_post") is True, "promotion does not attest 46 CAD PRE=POST")
    require(zero.get("accepted_b601_urdf_pre_equals_post_equals_current") is True, "accepted URDF PRE=POST missing")
    claims = promotion.get("claims", {})
    require(claims.get("full_native_mechanical_baseline_closed") is False, "promotion must not claim final closure")
    require(claims.get("flight_ready") is False and claims.get("launch_qualified") is False, "promotion contains flight/launch claim")
    sides = promotion.get("side_assemblies")
    require(isinstance(sides, list) and len(sides) == 2, "promotion must bind exactly two side assemblies")
    side_facts = []
    for expected_side, row in zip(("L", "R"), sides):
        require(row.get("side") == expected_side, f"side assembly order mismatch at {expected_side}")
        require(row.get("configuration_count") == 7, f"{expected_side}: configuration count mismatch")
        require(row.get("configuration_names_authority_order") == STATE_NAMES, f"{expected_side}: state names mismatch")
        require(row.get("configuration_owner") == "SIDE_SLDASM_ONLY", f"{expected_side}: owner mismatch")
        require(row.get("top_level_occurrence_solving") == "RIGID", f"{expected_side}: top occurrence must be rigid")
        actual = file_fact(Path(row["path"]))
        require(actual == {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}, f"{expected_side}: promoted side file drifted")
        side_facts.append(actual)
    return side_facts


def collect_and_validate() -> dict[str, Any]:
    root = release_root()
    paths = {
        "producer": Path(__file__).resolve(),
        "promotion": root / "13_validation/V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json",
        "p9_fresh_pass": root / "13_validation/solar_r2_attempts/20260813T123100Z_P9E9/evidence/F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_PASS.json",
        "state_authority_r2b": root / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json",
        "architecture_r2b": root / "00_authority/V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION.json",
        "static_oracle_r2b": root / "13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json",
        "old_state_machine_v1": root / "09_digital_thread/V5_MECHANICAL_STATE_MACHINE.yaml",
        "quarantined_invalid_register": root / "13_validation/quarantine/V5_SOLAR_ARRAY_INVALID_CANDIDATE_20260812T162256.8949918Z/relocated/04_configurations/V5_SOLAR_STATE_REGISTER.csv",
        "accepted_b601_urdf": root.parent / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "pose_authority": root / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv",
        "control_baseline": root / "00_authority/V5_CONTROL_BASELINE.yaml",
        "action_mask": root / "09_digital_thread/V5_ACTION_MASK_RULES.yaml",
    }
    facts = {name: file_fact(path) for name, path in paths.items()}
    expected = {
        "promotion": PROMOTION_SHA256,
        "p9_fresh_pass": P9_FRESH_PASS_SHA256,
        "state_authority_r2b": STATE_AUTHORITY_SHA256,
        "architecture_r2b": ARCHITECTURE_SHA256,
        "static_oracle_r2b": ORACLE_SHA256,
        "old_state_machine_v1": OLD_STATE_MACHINE_SHA256,
        "quarantined_invalid_register": QUARANTINED_REGISTER_SHA256,
        "accepted_b601_urdf": ACCEPTED_URDF_SHA256,
        "pose_authority": POSE_AUTHORITY_SHA256,
        "control_baseline": CONTROL_BASELINE_SHA256,
        "action_mask": ACTION_MASK_SHA256,
    }
    for label, digest in expected.items():
        require_hash(facts[label], digest, label)

    state_authority = load_json(paths["state_authority_r2b"], "R2B state authority")
    validate_state_authority(state_authority)

    promotion = load_json(paths["promotion"], "R2B logical promotion")
    side_facts = validate_promotion(promotion)

    fresh = load_json(paths["p9_fresh_pass"], "P9 fresh verification pass")
    require(fresh.get("schema") == "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_RECEIPT_V1", "P9 fresh pass schema mismatch")
    require(fresh.get("verdict") == "V5_SOLAR_R2B_A_NEW_PID_READ_ONLY_ZERO_MUTATION_PASS", "P9 fresh pass verdict mismatch")
    require(fresh.get("cad_write_calls") == 0, "P9 fresh pass contains CAD writes")
    require(fresh.get("all_46_cad_hash_pre_equals_post") is True, "P9 fresh pass PRE=POST missing")
    require(fresh.get("protected_hash_pre_equals_post") is True, "P9 protected PRE=POST missing")
    require(fresh.get("different_pid_and_process_create_time") is True, "P9 fresh process separation missing")
    require(fresh.get("read_only") is True, "P9 verifier was not read-only")

    architecture = load_json(paths["architecture_r2b"], "R2B architecture decision")
    require(architecture.get("schema") == "F3R2_V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION_V1", "architecture schema mismatch")
    oracle = load_json(paths["static_oracle_r2b"], "R2B kinematic oracle")
    require("R2B" in str(oracle.get("schema", "")), "oracle is not R2B")

    old_text = paths["old_state_machine_v1"].read_text(encoding="utf-8")
    require("schema: F3R2_V5_MECHANICAL_STATE_MACHINE_V1" in old_text, "old state machine identity mismatch")
    require("no dual panel entities" in old_text, "old single-panel semantics witness missing")
    quarantine_text = paths["quarantined_invalid_register"].read_text(encoding="utf-8-sig")
    require("NO_KINEMATIC_MATE_YET" in quarantine_text, "quarantined invalid register witness mismatch")
    require("SOLAR_LEFT_FAIL,90/0/0,90/0/0" in quarantine_text, "quarantined invalid fail mapping witness missing")

    parse_pose_register(paths["pose_authority"])
    control_text = paths["control_baseline"].read_text(encoding="utf-8")
    require("joint_topology_axes_lengths_mass_inertia: DO_NOT_MODIFY" in control_text, "control immutable truth missing")
    require("Q_SERVICE_GRASP" in control_text and "not_authorized" in control_text, "control SERVICE_GRASP prohibition missing")
    action_text = paths["action_mask"].read_text(encoding="utf-8")
    require("id: AM-7" in action_text, "AM-7 missing")
    require("ground command only" in action_text, "AM-7 ground-only enforcement missing")

    require(promotion.get("zero_mutation", {}).get("accepted_b601_urdf", {}).get("sha256") == ACCEPTED_URDF_SHA256, "promotion URDF binding mismatch")

    return {
        "root": root,
        "facts": facts,
        "side_facts": side_facts,
        "promotion": promotion,
        "state_authority": state_authority,
    }


def state_rows() -> list[dict[str, Any]]:
    rows = []
    for state in STATE_NAMES:
        rows.append(
            {
                "state": state,
                "logical_vector_order": ["ROOT", "H12", "H23"],
                "panel_angle_deg": {
                    "LEFT": STATE_ANGLES[state]["LEFT"],
                    "RIGHT": STATE_ANGLES[state]["RIGHT"],
                },
                "hinge_state": {
                    "LEFT": STATE_HINGES[state]["LEFT"],
                    "RIGHT": STATE_HINGES[state]["RIGHT"],
                },
                "collision_state": None,
                "camera_visibility": None,
                "arm_clearance_mm": None,
                "bus_clearance_mm": None,
                "harness_clearance_mm": None,
                "evidence_status": "PENDING_LOOP3_NATIVE_BREP_CAMERA_LOS_HARNESS_SWEEP",
            }
        )
    return rows


def build_state_machine(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "F3R2_V5_MECHANICAL_STATE_MACHINE_R2",
        "status": "PROMOTION_BOUND_L1_SOLAR_NATIVE_BASELINE__TOP_INTEGRATION_AND_CLEARANCE_PENDING",
        "scope": "V5_NATIVE_FINALIZATION",
        "authority_vocabulary": "L1_NATIVE_SOLIDWORKS_ONLY",
        "supersedes": {
            "path": "09_digital_thread/V5_MECHANICAL_STATE_MACHINE.yaml",
            "sha256": OLD_STATE_MACHINE_SHA256,
            "preservation": "PRESERVED_AS_SINGLE_PANEL_V1_HISTORY__NOT_LIVE_SOLAR_AUTHORITY",
        },
        "evidence_bindings": {
            "logical_promotion_sha256": PROMOTION_SHA256,
            "p9_fresh_read_only_pass_sha256": P9_FRESH_PASS_SHA256,
            "solar_state_authority_r2b_sha256": STATE_AUTHORITY_SHA256,
            "solar_assembly_architecture_sha256": ARCHITECTURE_SHA256,
            "solar_static_kinematic_oracle_sha256": ORACLE_SHA256,
            "accepted_b601_urdf_sha256": ACCEPTED_URDF_SHA256,
            "pose_authority_sha256": POSE_AUTHORITY_SHA256,
            "control_baseline_sha256": CONTROL_BASELINE_SHA256,
        },
        "immutable_boundaries": {
            "accepted_b601_urdf_modified": False,
            "joint_topology_axis_link_length_mass_inertia_modified": False,
            "spacecraft_mass_truth_modified": False,
            "solar_mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
        },
        "solar_configuration_contract": {
            "configuration_owner": "SIDE_SLDASM_ONLY",
            "side_configuration_count": 7,
            "top_level_allowed_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
            "top_level_second_driver": "PROHIBITED",
            "top_level_side_occurrence_solving": "RIGID",
            "logical_angle_semantics": "0=STOWED_ENDPOINT; 90=DEPLOYED_ENDPOINT",
            "top_assembly_binding": None,
            "top_integration_status": "PENDING",
        },
        "solar_states": state_rows(),
        "arm_pose_authority": {
            "authorized_runtime_pose_names": ["Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"],
            "stow_candidate": "Q_STOW_ENGINEERING_CANDIDATE__CANDIDATE_ONLY",
            "Q_SERVICE_GRASP": "NOT_AUTHORIZED__NO_Q_DEFINED",
            "q_source": "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv",
            "solar_interference_resolution_policy": "DO_NOT_MOVE_ARM__ADJUST_SOLAR_HINGE_ANGLE_FOLD_GEOMETRY_OR_DEPLOYMENT_SEQUENCE",
        },
        "command_authority": {
            "AM-7": "STOW_HDRM_RELEASE_AND_SOLAR_DEPLOYMENT_ARE_GROUND_COMMAND_ONLY",
            "autonomous_solar_deployment": False,
            "failure_states_are_observation_and_test_configurations": True,
        },
        "release_control": {
            "current_maximum_claim": "COMPETITION_PROTOTYPE_BASELINE_CANDIDATE",
            "full_mechanical_closure": False,
            "ecr_only_activation": "AFTER_F3R2_V5_NATIVE_MECHANICAL_BASELINE_CLOSED_GATE_ONLY",
            "ecr_only_currently_active": False,
            "flight_ready": False,
            "launch_qualified": False,
            "launch_load": "HOLD",
            "thermal_vacuum": "HOLD",
            "random_vibration": "HOLD",
            "formal_fastener_mos": "HOLD",
        },
    }


def build_annex(evidence: dict[str, Any]) -> dict[str, Any]:
    promotion = evidence["promotion"]
    side_rows = []
    for row in promotion["side_assemblies"]:
        side_rows.append(
            {
                "side": row["side"],
                "path": row["path"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "configuration_count": 7,
                "configuration_owner": "SIDE_SLDASM_ONLY",
                "top_level_occurrence_solving": "RIGID",
            }
        )
    return {
        "schema": "F3R2_V5_SOLAR_ARRAY_THREAD_ANNEX_R2B",
        "status": "LOGICALLY_PROMOTED_L1_NATIVE_SIDE_ASSEMBLIES__TOP_AND_CLEARANCE_PENDING",
        "scope": "MULTI_PANEL_SOLAR_ARRAY_CANDIDATE",
        "authority_vocabulary": "L1_NATIVE_SOLIDWORKS_ONLY",
        "promotion_binding": {
            "path": "13_validation/V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json",
            "sha256": PROMOTION_SHA256,
            "verdict": "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION",
            "p9_fresh_read_only_pass_sha256": P9_FRESH_PASS_SHA256,
            "attempt_storage_id": promotion["storage_id"],
            "reference_mode": "IMMUTABLE_ATTEMPT_TREE_IN_PLACE_REFERENCE_ONLY",
        },
        "native_cad_baseline": {
            "sldprt_count": 38,
            "rigid_panel_module_sldasm_count": 6,
            "side_state_owner_sldasm_count": 2,
            "total_native_cad_count": 46,
            "all_46_pre_equals_post": True,
            "fresh_pid_read_only_zero_mutation": True,
            "side_assemblies": side_rows,
        },
        "configuration_contract": {
            "owner": "SIDE_SLDASM_ONLY",
            "states_authority_order": STATE_NAMES,
            "top_level_allowed_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
            "top_level_second_driver": "PROHIBITED",
            "top_level_side_occurrence_solving": "RIGID",
            "module_configurations": "DEFAULT_ONLY_NO_SOLAR_STATE_CONFIGURATIONS",
        },
        "hinge_contract": {
            "logical_vector_order": ["ROOT", "H12", "H23"],
            "logical_angle_semantics": "0=STOWED_ENDPOINT; 90=DEPLOYED_ENDPOINT",
            "root_axis": "X",
            "left_right_relation": "XZ_MIRROR",
            "interpanel_pin_diameter_mm": 4.0,
            "interpanel_bore_diameter_mm": 4.4,
            "interpanel_collar_outer_diameter_max_mm": 5.5,
            "interpanel_edge_relief_mm": 3.5,
            "deployment_time_speed_torque_preload_reliability_authority": None,
        },
        "state_mapping": state_rows(),
        "observability_contract": {
            "collision_state": None,
            "camera_visibility": None,
            "arm_clearance_mm": None,
            "bus_clearance_mm": None,
            "harness_clearance_mm": None,
            "null_semantics": "PENDING_NOT_MEASURED__FAIL_CLOSED__NOT_PASS",
            "required_next_evidence": "LOOP3_SOLIDWORKS_NATIVE_BREP_CLEARANCE_CAMERA_LOS_AND_HARNESS_SWEEP",
        },
        "legacy_supersession": {
            "old_single_panel_state_machine_sha256": OLD_STATE_MACHINE_SHA256,
            "quarantined_invalid_state_register_sha256": QUARANTINED_REGISTER_SHA256,
            "quarantined_register_live_use": "PROHIBITED",
            "old_single_panel_live_use": "PROHIBITED",
        },
        "mass_boundary": {
            "solar_mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
            "accepted_urdf_written": False,
            "spacecraft_mass_and_inertia_truth_changed": False,
            "cad_rollup_is_spacecraft_mass_truth": False,
        },
        "robot_integration_boundary": {
            "Q_DEPLOYED_HOME": "AUTHORIZED_INPUT__CLEARANCE_PENDING",
            "Q_SERVICE_READY": "AUTHORIZED_INPUT__CLEARANCE_PENDING",
            "Q_RELEASE_CLEAR": "AUTHORIZED_INPUT__CLEARANCE_PENDING",
            "Q_SERVICE_GRASP": "NOT_AUTHORIZED__NO_Q_DEFINED",
            "arm_motion_as_solar_interference_fix": "PROHIBITED",
        },
        "release_boundary": {
            "AM-7": "GROUND_COMMAND_ONLY_FOR_STOW_HDRM_RELEASE_AND_SOLAR_DEPLOYMENT",
            "allowed_claim": "COMPETITION_PROTOTYPE_BASELINE_CANDIDATE",
            "full_mechanical_closure": False,
            "ecr_only": "ACTIVATE_AFTER_FINAL_MECHANICAL_GATE_ONLY",
            "flight_ready": False,
            "launch_qualified": False,
        },
    }


def build_register_csv() -> bytes:
    columns = [
        "state",
        "panel_angle_deg_L[3]",
        "panel_angle_deg_R[3]",
        "hinge_state_left[3]",
        "hinge_state_right[3]",
        "collision_state",
        "camera_visibility",
        "arm_clearance_mm",
        "bus_clearance_mm",
        "harness_clearance_mm",
        "evidence_status",
        "evidence_ref",
        "owner",
        "configuration_owner",
        "top_level_operation",
        "top_level_second_driver",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for state in STATE_NAMES:
        writer.writerow(
            {
                "state": state,
                "panel_angle_deg_L[3]": "/".join(str(v) for v in STATE_ANGLES[state]["LEFT"]),
                "panel_angle_deg_R[3]": "/".join(str(v) for v in STATE_ANGLES[state]["RIGHT"]),
                "hinge_state_left[3]": "/".join(STATE_HINGES[state]["LEFT"]),
                "hinge_state_right[3]": "/".join(STATE_HINGES[state]["RIGHT"]),
                "collision_state": "",
                "camera_visibility": "",
                "arm_clearance_mm": "",
                "bus_clearance_mm": "",
                "harness_clearance_mm": "",
                "evidence_status": "PENDING_LOOP3_NATIVE_BREP_CAMERA_LOS_HARNESS_SWEEP",
                "evidence_ref": f"13_validation/V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json#sha256={PROMOTION_SHA256}",
                "owner": "V5_NATIVE_FINALIZATION_L1_SOLAR_R2B",
                "configuration_owner": "SIDE_SLDASM_ONLY",
                "top_level_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
                "top_level_second_driver": "PROHIBITED",
            }
        )
    data = stream.getvalue().encode("utf-8")
    with io.StringIO(data.decode("utf-8"), newline="") as check:
        rows = list(csv.DictReader(check))
    require([row["state"] for row in rows] == STATE_NAMES, "serialized CSV state order mismatch")
    for row in rows:
        for field in ("collision_state", "camera_visibility", "arm_clearance_mm", "bus_clearance_mm", "harness_clearance_mm"):
            require(row[field] == "", f"serialized CSV pending field must be empty/null: {field}")
    return data


def manifest_label(root: Path, path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "ABS::" + path.as_posix()


def build_receipt(
    evidence: dict[str, Any], generated_core_facts: dict[str, dict[str, Any]], producer_fact: dict[str, Any]
) -> dict[str, Any]:
    facts = evidence["facts"]
    promotion = evidence["promotion"]
    bound_labels = [
        "promotion",
        "p9_fresh_pass",
        "state_authority_r2b",
        "architecture_r2b",
        "static_oracle_r2b",
        "old_state_machine_v1",
        "quarantined_invalid_register",
        "accepted_b601_urdf",
        "pose_authority",
        "control_baseline",
        "action_mask",
    ]
    return {
        "schema": SCHEMA,
        "verdict": VERDICT,
        "execution_class": "PURE_FILESYSTEM_NO_SOLIDWORKS_NO_CAD_NO_URDF_NO_Q_WRITE",
        "determinism": "DERIVED_ONLY_FROM_HASH_BOUND_EVIDENCE__NO_WALL_CLOCK_FIELD",
        "evidence_epoch_utc": promotion["timestamp_utc"],
        "producer": producer_fact,
        "bound_inputs": {label: facts[label] for label in bound_labels},
        "promoted_side_assemblies_read_only": evidence["side_facts"],
        "generated_core_artifacts": generated_core_facts,
        "manifest_contract": {
            "path": TARGET_RELATIVE_PATHS["manifest"],
            "includes_receipt_hash": True,
            "self_hash_excluded_to_avoid_recursion": True,
        },
        "semantic_checks": {
            "exact_seven_states": True,
            "state_names_authority_order": STATE_NAMES,
            "state_angles_match_r2b_authority": True,
            "hinge_semantics_match_r2b_authority": True,
            "configuration_owner": "SIDE_SLDASM_ONLY",
            "top_level_allowed_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
            "top_level_second_driver": "PROHIBITED",
            "l1_vocabulary_only": True,
            "quarantined_invalid_register_explicitly_superseded_sha256": QUARANTINED_REGISTER_SHA256,
            "old_v1_state_machine_preserved_sha256": OLD_STATE_MACHINE_SHA256,
            "service_grasp_q_defined": False,
            "am_7_ground_only": True,
            "ecr_only_activation_after_final_gate": True,
        },
        "pending_measurements": {
            "collision_state": None,
            "camera_visibility": None,
            "arm_clearance_mm": None,
            "bus_clearance_mm": None,
            "harness_clearance_mm": None,
            "null_means": "PENDING_NOT_PASS",
        },
        "zero_mutation_and_claim_boundary": {
            "solidworks_connection_attempted": False,
            "cad_files_written": 0,
            "accepted_urdf_written": False,
            "pose_q_written": False,
            "mass_truth_changed": False,
            "solar_mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
            "full_native_mechanical_baseline_closed": False,
            "flight_ready": False,
            "launch_qualified": False,
            "launch_load": "HOLD",
            "thermal_vacuum": "HOLD",
            "random_vibration": "HOLD",
            "formal_fastener_mos": "HOLD",
        },
    }


def build_manifest(
    root: Path,
    evidence: dict[str, Any],
    producer_fact: dict[str, Any],
    generated_facts: Iterable[dict[str, Any]],
) -> bytes:
    entries = [producer_fact]
    entries.extend(evidence["facts"][label] for label in evidence["facts"] if label != "producer")
    entries.extend(evidence["side_facts"])
    entries.extend(generated_facts)
    by_label: dict[str, dict[str, Any]] = {}
    for fact in entries:
        label = manifest_label(root, Path(fact["path"]))
        if label in by_label:
            require(by_label[label] == fact, f"manifest duplicate path disagrees: {label}")
        by_label[label] = fact
    lines = [
        "# F3R2_V5_DIGITAL_THREAD_SOLAR_R2B_MANIFEST_SHA256_V1",
        "# promotion_bound=71952A7AC8761D59BB4596381C1DABD873AE2EFD0B7B8F502A0A95187349A334",
        "# manifest_self_hash=EXCLUDED_TO_AVOID_RECURSION",
        "# format=SHA256__TWO_SPACES__PATH",
    ]
    for label in sorted(by_label, key=str.casefold):
        lines.append(f"{by_label[label]['sha256']}  {label}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def validate_serialized_outputs(outputs: dict[str, bytes], paths: dict[str, Path]) -> None:
    require(list(outputs) == ["state_machine_r2", "solar_annex_r2b", "solar_state_register", "receipt", "manifest"], "output order mismatch")
    for name, data in outputs.items():
        require(isinstance(data, bytes) and data, f"{name}: output did not fully serialize")
        require(b"NaN" not in data and b"Infinity" not in data, f"{name}: non-finite token prohibited")
    state_text = outputs["state_machine_r2"].decode("utf-8")
    annex_text = outputs["solar_annex_r2b"].decode("utf-8")
    for text, label in ((state_text, "state machine"), (annex_text, "solar annex")):
        require("L1_NATIVE_SOLIDWORKS_ONLY" in text, f"{label}: L1 vocabulary marker missing")
        require("SIDE_SLDASM_ONLY" in text, f"{label}: side-only owner missing")
        require("SELECT_REFERENCED_CONFIGURATION_ONLY" in text, f"{label}: top operation missing")
        require("PROHIBITED" in text, f"{label}: prohibition marker missing")
        require("FLIGHT_READY: TRUE" not in text.upper(), f"{label}: flight claim prohibited")
        require("LAUNCH_QUALIFIED: TRUE" not in text.upper(), f"{label}: launch claim prohibited")
    receipt = json.loads(outputs["receipt"].decode("utf-8"))
    require(receipt.get("schema") == SCHEMA and receipt.get("verdict") == VERDICT, "receipt identity mismatch")
    manifest_text = outputs["manifest"].decode("utf-8")
    require(receipt["generated_core_artifacts"]["state_machine_r2"]["sha256"] in manifest_text, "manifest misses state machine hash")
    require(receipt["generated_core_artifacts"]["solar_annex_r2b"]["sha256"] in manifest_text, "manifest misses annex hash")
    require(receipt["generated_core_artifacts"]["solar_state_register"]["sha256"] in manifest_text, "manifest misses register hash")
    require(virtual_fact(paths["receipt"], outputs["receipt"])["sha256"] in manifest_text, "manifest misses receipt hash")


def build_all_outputs(evidence: dict[str, Any]) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    root = evidence["root"]
    paths = target_paths(root)
    producer_fact = evidence["facts"]["producer"]

    state_data = yaml_bytes(build_state_machine(evidence))
    annex_data = yaml_bytes(build_annex(evidence))
    register_data = build_register_csv()
    core_data = {
        "state_machine_r2": state_data,
        "solar_annex_r2b": annex_data,
        "solar_state_register": register_data,
    }
    core_facts = {name: virtual_fact(paths[name], data) for name, data in core_data.items()}
    receipt_data = canonical_json_bytes(build_receipt(evidence, core_facts, producer_fact))
    receipt_fact = virtual_fact(paths["receipt"], receipt_data)
    manifest_data = build_manifest(root, evidence, producer_fact, [*core_facts.values(), receipt_fact])
    outputs = {
        "state_machine_r2": state_data,
        "solar_annex_r2b": annex_data,
        "solar_state_register": register_data,
        "receipt": receipt_data,
        "manifest": manifest_data,
    }
    validate_serialized_outputs(outputs, paths)
    return outputs, {name: virtual_fact(paths[name], data) for name, data in outputs.items()}


def create_exclusive_bytes(path: Path, data: bytes) -> dict[str, Any]:
    require(path.parent.is_dir(), f"target parent directory missing: {path.parent}")
    require(not path.exists(), f"write-once target already exists: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, 0o444)
    try:
        view = memoryview(data)
        written = 0
        while written < len(data):
            count = os.write(fd, view[written:])
            require(count > 0, f"zero-byte write while creating {path}")
            written += count
        os.fsync(fd)
    finally:
        os.close(fd)
    actual = file_fact(path)
    require(actual == virtual_fact(path, data), f"created target differs from pre-serialized bytes: {path}")
    return actual


def audit_mode() -> dict[str, Any]:
    evidence = collect_and_validate()
    outputs, facts = build_all_outputs(evidence)
    paths = target_paths(evidence["root"])
    existing = [path.as_posix() for path in paths.values() if path.exists()]
    require(not existing, f"audit-for-create requires all targets absent: {existing}")
    return {
        "mode": "audit",
        "ready_for_exclusive_create": True,
        "read_only": True,
        "solidworks_connection_attempted": False,
        "target_count": len(paths),
        "all_targets_absent": True,
        "pre_serialized_bytes": {name: len(data) for name, data in outputs.items()},
        "expected_output_facts": facts,
        "promotion_sha256": PROMOTION_SHA256,
        "p9_fresh_pass_sha256": P9_FRESH_PASS_SHA256,
        "exact_states": STATE_NAMES,
    }


def create_mode() -> dict[str, Any]:
    evidence = collect_and_validate()
    outputs, expected_facts = build_all_outputs(evidence)
    paths = target_paths(evidence["root"])
    existing = [path.as_posix() for path in paths.values() if path.exists()]
    require(not existing, f"write-once targets already exist: {existing}")
    # All five output byte strings have been fully serialized and validated at
    # this point.  No target is opened until after the global absence check.
    created: dict[str, dict[str, Any]] = {}
    for name in outputs:
        created[name] = create_exclusive_bytes(paths[name], outputs[name])
        require(created[name] == expected_facts[name], f"{name}: created fact mismatch")
    return {
        "mode": "create",
        "created": True,
        "write_once": True,
        "solidworks_connection_attempted": False,
        "cad_files_written": 0,
        "targets": created,
        "verdict": VERDICT,
    }


def verify_mode() -> dict[str, Any]:
    evidence = collect_and_validate()
    expected_outputs, expected_facts = build_all_outputs(evidence)
    paths = target_paths(evidence["root"])
    before = {name: file_fact(path) for name, path in paths.items()}
    for name, path in paths.items():
        require(path.read_bytes() == expected_outputs[name], f"{name}: byte content differs from independently reconstructed output")
        require(before[name] == expected_facts[name], f"{name}: file fact mismatch")
    after = {name: file_fact(path) for name, path in paths.items()}
    require(before == after, "output set changed during read-only verification")
    return {
        "mode": "verify",
        "verified": True,
        "read_only": True,
        "solidworks_connection_attempted": False,
        "cad_files_written": 0,
        "targets_pre_equals_post": True,
        "targets": after,
        "promotion_sha256": PROMOTION_SHA256,
        "p9_fresh_pass_sha256": P9_FRESH_PASS_SHA256,
        "state_count": 7,
        "configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
        "top_level_second_driver": "PROHIBITED",
        "verdict": VERDICT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "create", "verify"))
    args = parser.parse_args()
    try:
        if args.mode == "audit":
            result = audit_mode()
        elif args.mode == "create":
            result = create_mode()
        else:
            result = verify_mode()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except DigitalThreadError as exc:
        print(json.dumps({"mode": args.mode, "ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True, indent=2))
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {"mode": args.mode, "ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
