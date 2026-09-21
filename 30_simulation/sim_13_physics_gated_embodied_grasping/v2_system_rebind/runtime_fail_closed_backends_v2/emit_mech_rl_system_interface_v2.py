#!/usr/bin/env python3
"""Emit the MECH_RL_SYSTEM_INTERFACE_V2.yaml instance (9 GATE artifact slots).

The instance binds six core artifacts plus the nine gate-stage artifact slots
defined by ``MECH_RL_SYSTEM_INTERFACE_V2_SCHEMA_DEFINITION.yaml``:

- SIM13_SYSTEM_BINDING_GATE_V2: v2_loader_source, v2_loader_validation_receipt
- SIM13_RUNTIME_FAIL_CLOSED_GATE_V2: runtime_gate_adapter_source,
  runtime_evaluator_source, runtime_evaluator_receipt
- SIM13_DYNAMICS_BACKEND_GATE_V2: dynamics_backend_source,
  dynamics_backend_validation_receipt
- SIM13_CONTACT_GRASP_GATE_V2: contact_backend_source,
  contact_backend_validation_receipt

Every entry carries path/bytes/SHA-256 computed from the live files; the six
core artifacts and the two loader artifacts are additionally asserted against
their frozen pins, so emission fails closed on any drift.  Authority values
are recorded truthfully: owner acceptance and the Route-C scope disposition
remain false, so consumer load and contact grasp remain unauthorized.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v2_backends.canonical import sha256_bytes, write_canonical_json


INTERFACE_PATH = (
    PROJECT_ROOT
    / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    / "interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
)
EMISSION_RECEIPT_PATH = (
    HERE / "evidence" / "SIM13_V2_INTERFACE_EMISSION_RECEIPT_V1.json"
)

CORE_PINS = {
    "system_urdf": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
        17191,
        "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA",
    ),
    "system_frame_tree": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml",
        11828,
        "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756",
    ),
    "accepted_b601_urdf": (
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        11321,
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    ),
    "urdf_generation_receipt": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json",
        2891,
        "957CA67D7BCC2CB591DF2442F24532CA3DAE24F358FC69BF390AC1A20F6F021E",
    ),
    "unified_r2_source_gate": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SOURCE_GATE_V2.json",
        864,
        "62BF5F629DEA904D63115EEE5FE7DB718A5B5EDE73B5A78B1EBFE36BC1314D7F",
    ),
    "sim_candidate_contract": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SIM_CANDIDATE_CONTRACT_V2.yaml",
        7716,
        "6821584112B70862F0158024CB0315D7C2A49CEE0881658C7954EA09BC46DE43",
    ),
}
LOADER_PINS = {
    "v2_loader_source": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/unified_r2_urdf_source_v2.py",
        24599,
        "64AF651E928986F3492607CA74CE40F15B385357C53DD435C1A66AE6BB7A8E40",
    ),
    "v2_loader_validation_receipt": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V2.json",
        438006,
        "97DFEBD815C53EC2A04A43DBF2445508D2AC1FFAA1BAD73EBA91EF3BFD8CB0EF",
    ),
}
PACKAGE = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2"
NEW_ARTIFACTS = {
    "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2": {
        "runtime_gate_adapter_source": f"{PACKAGE}/sim13_v2_backends/runtime_gate_adapter.py",
        "runtime_evaluator_source": f"{PACKAGE}/run_negative_controls_backends_v2.py",
        "runtime_evaluator_receipt": f"{PACKAGE}/evidence/SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json",
    },
    "SIM13_DYNAMICS_BACKEND_GATE_V2": {
        "dynamics_backend_source": f"{PACKAGE}/sim13_v2_backends/dynamics_backend.py",
        "dynamics_backend_validation_receipt": f"{PACKAGE}/evidence/SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1.json",
    },
    "SIM13_CONTACT_GRASP_GATE_V2": {
        "contact_backend_source": f"{PACKAGE}/sim13_v2_backends/contact_backend.py",
        "contact_backend_validation_receipt": f"{PACKAGE}/evidence/SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1.json",
    },
}


def _record(relative: str) -> dict:
    path = PROJECT_ROOT / relative
    if not path.is_file():
        raise RuntimeError(f"INTERFACE_ARTIFACT_MISSING:{relative}")
    payload = path.read_bytes()
    return {"path": relative, "bytes": len(payload), "sha256": sha256_bytes(payload)}


def _pinned_record(name: str, pin: tuple[str, int, str]) -> dict:
    relative, expected_bytes, expected_sha = pin
    record = _record(relative)
    if record["bytes"] != expected_bytes or record["sha256"] != expected_sha:
        raise RuntimeError(f"INTERFACE_ARTIFACT_PIN_DRIFT:{name}")
    return record


def build_interface() -> dict:
    artifacts = {name: _pinned_record(name, pin) for name, pin in CORE_PINS.items()}
    gate_stages = {
        "SIM13_SYSTEM_BINDING_GATE_V2": {
            name: _pinned_record(name, pin) for name, pin in LOADER_PINS.items()
        }
    }
    for stage, slots in NEW_ARTIFACTS.items():
        gate_stages[stage] = {name: _record(path) for name, path in slots.items()}
    artifacts["gate_stages"] = gate_stages

    # Truthful authority values: owner acceptance and Route-C disposition are
    # still absent, so consumer load and contact grasp stay unauthorized even
    # though the three software backend gates now pass.
    authority_current_values = {
        "owner_accepted": False,
        "route_c_exclusion_accepted_for_this_sim_candidate": False,
        "route_c_scope_disposition_pass": False,
        "system_urdf_generated_and_validated": True,
        "urdf_generation_receipt_hash_valid": True,
        "sim13_system_binding_gate_passed": False,
        "v2_loader_validation_receipt_hash_valid": True,
        "runtime_fail_closed_gate_passed": True,
        "runtime_evaluator_receipt_hash_valid": True,
        "dynamics_backend_gate_passed": True,
        "dynamics_backend_validation_receipt_hash_valid": True,
        "contact_grasp_gate_passed": True,
        "contact_backend_validation_receipt_hash_valid": True,
        "consumer_load_all_of_passed": False,
        "contact_grasp_all_of_passed": False,
        "current_consumer_load_authorized": False,
        "current_contact_grasp_authorized": False,
    }
    return {
        "schema": "MECH_RL_SYSTEM_INTERFACE_V2",
        "configuration_id": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
        "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
        "instance_class": "INSTANTIATED_20_OF_20_NC_BACKENDS_BOUND__PENDING_OWNER_REVIEW",
        "generated_date_local": "2026-08-25",
        "artifacts": artifacts,
        "whole_system_contract": {
            "root_link": "spacecraft_bus",
            "links": 19,
            "physical_links": 16,
            "frame_only_links": 3,
            "joints": 18,
            "fixed": 10,
            "revolute": 6,
            "prismatic": 2,
            "actuated_dof": 8,
            "total_mass_kg": 31.022864807342987,
        },
        "accepted_b601_subtree": {
            "root_link": "base_link",
            "links": 10,
            "joints": 9,
            "fixed": 1,
            "revolute": 6,
            "prismatic": 2,
            "mass_kg": 4.695555949342986,
            "exact_semantic_fields": [
                "link_names",
                "joint_names",
                "parent_child",
                "joint_origin",
                "joint_axis",
                "joint_limits",
                "per_link_mass_com_inertia",
            ],
        },
        "actuation_contract": {
            "actuated_joint_names": [
                "joint1",
                "joint2",
                "joint3",
                "joint4",
                "joint5",
                "joint6",
                "gripper_joint1",
                "gripper_joint2",
            ],
            "fixed_joint_excluded_from_state": ["gripper_joint"],
        },
        "runtime_gate_contract": {
            "combined_required_gate_count": 12,
            "allowed_states": ["PASS", "FAIL", "UNKNOWN"],
            "fail_closed_rule": "FAIL or UNKNOWN permits ABORT only",
        },
        "authority": {
            "evaluation": "ALL_OF_EXACT_TRUE_FROM_HASH_BOUND_RECEIPTS",
            "caller_supplied_gate_state_is_authority": False,
            "pass_evidence_source": "hash-bound evaluator receipt only",
            "current_values": authority_current_values,
        },
        "mech_to_embodied_handoff_g12_harness": "NOT_IN_A3_SCOPE_DEPENDS_ON_MECHANICAL_ROUTE_C_LINE__REGISTERED_NOT_FORGED",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    document = build_interface()
    payload = yaml.safe_dump(document, sort_keys=True, allow_unicode=True)
    if args.check_only:
        existing = INTERFACE_PATH.read_text(encoding="utf-8")
        print("deterministic:", existing == payload)
        return 0 if existing == payload else 1
    INTERFACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    INTERFACE_PATH.write_text(payload, encoding="utf-8", newline="\n")
    receipt = {
        "schema": "SIM13_V2_INTERFACE_EMISSION_RECEIPT_V1",
        "generated_date_local": "2026-08-25",
        "interface": {
            "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
            "bytes": INTERFACE_PATH.stat().st_size,
            "sha256": sha256_bytes(INTERFACE_PATH.read_bytes()),
        },
        "core_artifact_slots": len(CORE_PINS),
        "gate_stage_slots": sum(len(slots) for slots in NEW_ARTIFACTS.values()) + len(LOADER_PINS),
        "authority_current_values": document["authority"]["current_values"],
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_canonical_json(EMISSION_RECEIPT_PATH, receipt)
    print(json.dumps(receipt["interface"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
