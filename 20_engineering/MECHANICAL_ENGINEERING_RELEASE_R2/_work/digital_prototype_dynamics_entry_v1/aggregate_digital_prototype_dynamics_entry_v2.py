"""Aggregate additive R2 digital-prototype and dynamics-entry evidence.

This evaluator is read-only with respect to all source gates. It recognizes
bounded diagnostic progress while retaining every physical, mechanical,
contact, consumer, and release hold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PACKAGE = Path(__file__).resolve().parent


def workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND")


ROOT = workspace_root()
OUTPUT = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2.json"
SOURCE_PINS = {
    "entry_gate_v1": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V1.json",
        "bytes": 5973,
        "sha256": "662FDCE68188AB2A4D103703FB75BDFFF2B0BA018C546A69D18F7DC92B093364",
    },
    "contact_velocity_gate": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/contact_velocity_reconciliation_v1/CONTACT_VELOCITY_RECONCILIATION_GATE_V1.json",
        "bytes": 12161,
        "sha256": "E6981B808B168C4E5442EA2573BEC0A38B7F68B4C60EF70AEC253E743D8B33A6",
    },
    "system_binding_candidate_gate": {
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/system_binding_candidate_v1/results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json",
        "bytes": 1264,
        "sha256": "43E46877A4E6CDF802FEC0545FB1B30C04CDA84E6328191474ABF43155E3F6DF",
    },
    "dg1_dg2_candidate_gate": {
        "path": "30_simulation/r2_dynamics_engineering_closure/dg1_dg2_candidate_v2/results/R2_DG1_DG2_CANDIDATE_GATE_V2.json",
        "bytes": 1582,
        "sha256": "1C3F1639018D4F7434DFB3B9E6AF086D3717B834C5E08D714A75D76C6ED2D362",
    },
}


class AggregateError(RuntimeError):
    """Raised for malformed or drifted aggregate inputs."""


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AggregateError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_sources() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    binding_rows: list[dict[str, Any]] = []
    for source_id, pin in SOURCE_PINS.items():
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == pin["bytes"]
            and actual_sha == pin["sha256"]
        )
        binding_rows.append(
            {
                "id": source_id,
                "path": pin["path"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
        if match:
            documents[source_id] = load_json(path)
    binding = {
        "pins": binding_rows,
        "matched": sum(bool(row["match"]) for row in binding_rows),
        "total": len(binding_rows),
        "all_match": all(bool(row["match"]) for row in binding_rows),
    }
    return documents, binding


def build_gate() -> dict[str, Any]:
    documents, binding = load_sources()
    if not binding["all_match"]:
        return {
            "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2",
            "technical_verdict": "SOURCE_HASH_DRIFT__FAIL_CLOSED",
            "source_binding": binding,
            "checks": {"A01_all_source_pins_exact": False},
            "summary": {
                "passed": 0,
                "total": 1,
                "failed": ["A01_all_source_pins_exact"],
            },
            "next_stage_authorized": False,
            "release_credit": False,
        }

    entry = documents["entry_gate_v1"]
    contact = documents["contact_velocity_gate"]
    binding_gate = documents["system_binding_candidate_gate"]
    dynamics = documents["dg1_dg2_candidate_gate"]
    checks = {
        "A01_all_source_pins_exact": True,
        "A02_prior_bounded_entry_remains_pass": entry.get("verdict")
        == "PASS_BOUNDED_DIAGNOSTIC_DYNAMICS_ENTRY__INTEGRATED_CAD_AND_NON_ABORT_GRASPING_HOLD",
        "A03_contact_semantic_reconciliation_9_of_9": contact.get(
            "semantic_reconciliation"
        )
        == "PASS"
        and contact.get("criteria_passed") == 9
        and contact.get("criteria_total") == 9,
        "A04_contact_0p05_rejected_0p005_bounded_only": contact.get(
            "original_0p05_current_contact_consumer"
        )
        == "REJECT"
        and contact.get("reduced_0p005_design_diagnostic_consumer")
        == "ACCEPT_BOUNDED_DIAGNOSTIC_ONLY",
        "A05_contact_physical_paths_remain_hold": contact.get(
            "physical_contact_ready"
        )
        is False
        and contact.get("production_dynamics_ready") is False
        and contact.get("non_abort_grasp_ready") is False,
        "A06_system_static_binding_candidate_pass": binding_gate.get(
            "candidate_static_gate_passed"
        )
        is True,
        "A07_system_binding_remains_abort_only": binding_gate.get(
            "maximum_operational_state"
        )
        == "ABORT_ONLY"
        and binding_gate.get("sim13_system_binding_gate_passed") is False
        and binding_gate.get("non_abort_authorized") is False,
        "A08_DG1_DG2_candidate_15_of_15": dynamics.get(
            "candidate_DG1_satisfied"
        )
        is True
        and dynamics.get("candidate_DG2_satisfied") is True
        and dynamics.get("summary")
        == {"passed": 15, "total": 15, "failed": []},
        "A09_DG3_DG4_DG5_and_parent_gate_remain_hold": dynamics.get(
            "parent_gate_update"
        )
        == "NOT_APPLIED__ADDITIVE_CANDIDATE_EVIDENCE_ONLY"
        and len(dynamics.get("remaining_parent_holds", [])) == 3
        and dynamics.get("dynamics_engineering_complete") is False,
        "A10_no_authority_escalation": all(
            document.get("next_stage_authorized") is False
            and document.get("release_credit") is False
            for document in (entry, contact, binding_gate, dynamics)
        ),
    }
    all_pass = all(checks.values())
    failed = [name for name, value in checks.items() if not value]
    return {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2",
        "technical_verdict": (
            "PASS_ADDITIVE_DIAGNOSTIC_CONVERGENCE__CONTACT_CONFLICT_RESOLVED_FOR_0P005_BOUNDED_CONSUMER__DG1_DG2_AND_STATIC_SYSTEM_BINDING_CANDIDATES_PASS__CAD_M01_ROUTE_C_NON_ABORT_AND_RELEASE_HOLD"
            if all_pass
            else "ADDITIVE_DIAGNOSTIC_CONVERGENCE_HOLD__SEE_FAILED_CHECKS"
        ),
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "source_binding": binding,
        "checks": checks,
        "summary": {
            "passed": sum(bool(value) for value in checks.values()),
            "total": len(checks),
            "failed": failed,
        },
        "progress_delta": {
            "contact_velocity_internal_contract_conflict": {
                "prior_state": "0.005_MPS_VS_0.05_MPS_UNRESOLVED",
                "current_state": "RESOLVED_FOR_BOUNDED_CURRENT_CONSUMER",
                "binding_rule": "REQUESTED_ESTIMATE_AND_UPPER_BOUND_MUST_BE_LE_0.005_MPS",
                "original_0p05_mps_record": "RETAINED_LINEAGE_AND_REJECTED_FOR_CURRENT_CONSUMER",
                "as_built_authority": "MEASUREMENT_PENDING",
            },
            "system_binding": {
                "input_hashes": "23_OF_23_MATCH",
                "static_candidate": "PASS",
                "maximum_operational_state": "ABORT_ONLY",
            },
            "dynamics": {
                "DG1_reference_metric": "PASS_CANDIDATE",
                "DG2_nonzero_momentum_full_pose": "PASS_CANDIDATE",
                "DG3_DG4_DG5": "HOLD",
                "production_dynamics": False,
            },
        },
        "m4_completion_matrix": {
            "L01_total_digital_mockup": "HOLD_FULL_INSTALLED_ARM_CANDIDATE_NOT_GENERATED",
            "L02_nine_configuration_geometry_collision": "PARTIAL_MASS_PROPERTIES_9_OF_9__GEOMETRY_COLLISION_AND_M01_OPEN",
            "L03_mass_inertia": "PASS_DESIGN_LEVEL__AS_BUILT_MEASUREMENT_PENDING",
            "L04_materials": "PARTIAL_DESIGN_FAMILIES_SELECTED__ALLOWABLES_AND_NULL_FIELDS_OPEN",
            "L05_tolerances": "PASS_M4_SPECIFIED_ANALYTIC_SCOPE__CAMERA_HDRM_AND_AS_BUILT_OPEN",
            "L06_drawings_BOM": "PARTIAL_PROTOTYPE_PACKAGE__NOT_PROCUREMENT_OR_CURRENT_UNIFIED_RELEASE",
            "L07_FEA_entry": "PASS_DESIGN_SCREENING_ENTRY__FULL_QUALIFICATION_OPEN",
            "L08_MECH_RL_V2": "PARTIAL_STATIC_CANDIDATE__ABORT_ONLY",
            "final_release_gate": "HOLD",
        },
        "authorized_now": {
            "bounded_0p005_mps_contact_velocity_design_diagnostic_consumption": all_pass,
            "hash_bound_static_system_candidate_loading": all_pass,
            "DG1_reference_metric_diagnostic_consumption": all_pass,
            "DG2_prescribed_motion_nonzero_momentum_diagnostic_consumption": all_pass,
            "integrated_candidate_CAD_generation": False,
            "M01_collision_or_path_authority": False,
            "physical_contact_or_non_abort_grasp": False,
            "production_dynamics": False,
            "flight_release": False,
        },
        "exact_remaining_blockers": [
            "FRESH_RUN_SPECIFIC_OWNER_AUTHORITY_REQUIRED_FOR_INTEGRATED_CAD_GENERATION",
            "CURRENT_AVAILABLE_MEMORY_BELOW_6_GIB_REQUIRES_FRESH_SINGLE_USE_OWNER_OVERRIDE",
            "INTEGRATED_FULL_ARM_CANDIDATE_STEP_NOT_GENERATED_OR_INSPECTED",
            "M01_SCENES_0_OF_3_CLEARANCE_0_OF_11166_MOTION_0_OF_150_ORACLE_0_OF_11166_NO_EDGE_CERTIFICATES",
            "ROUTE_C_HARNESS_MANDATORY_STATES_UNSAFE_AND_G12_11_OF_12",
            "OWNER_ROUTE_C_SYSTEM_CONSUMER_AND_CONTACT_BINDINGS_NOT_ACCEPTED",
            "CONTACT_AS_BUILT_SPEED_CLOSING_TIME_FORCE_TORQUE_AND_UNCERTAINTY_MEASUREMENT_PENDING",
            "DG3_ARM_TO_FLEX_TIME_DOMAIN_COUPLING_NOT_IMPLEMENTED",
            "DG4_CONTACT_HYBRID_AND_TARGET_ATTACHMENT_NOT_IMPLEMENTED",
            "DG5_AS_BUILT_MASS_CONTACT_ACTUATOR_UNCERTAINTY_OPEN",
            "BASELINE_MANIFEST_SELF_ENTRY_INTEGRITY_DEFECT_REMAINS_REGISTERED",
        ],
        "maximum_claim": "HASH_BOUND_BOUNDED_DIAGNOSTIC_DIGITAL_BODY_ENTRY_WITH_CONTACT_VELOCITY_SEMANTIC_RECONCILIATION_DG1_DG2_AND_STATIC_SYSTEM_BINDING_CANDIDATE_PASS__NOT_COMPLETE_CAD_NOT_M01_NOT_NON_ABORT_NOT_PRODUCTION_NOT_RELEASE",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate = build_gate()
    payload = canonical_bytes(gate)
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
            print("FAIL_OUTPUT_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 2
        print("PASS_BYTE_IDENTICAL")
    else:
        OUTPUT.write_bytes(payload)
        print(gate["technical_verdict"])
        print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
        print(f"sha256={sha256(OUTPUT)}")
    return 0 if gate["summary"]["passed"] == gate["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
