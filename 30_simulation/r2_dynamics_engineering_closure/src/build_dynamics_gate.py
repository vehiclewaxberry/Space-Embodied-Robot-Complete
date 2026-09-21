"""Build deterministic R2 constrained-dynamics candidate evidence."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from r2_dynamics import (
    PACKAGE_DIR,
    canonical_sha256,
    file_sha256,
    load_contracts,
    load_json_strict,
    run_all_diagnostics,
    validate_source_pins,
)


RESULTS_DIR = PACKAGE_DIR / "results"


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _pin_path(
    project_root: Path, authority: Mapping[str, Any], pin_id: str
) -> Path:
    return project_root / authority["source_pins"][pin_id]["path"]


def build_authority_boundary(
    project_root: Path, authority: Mapping[str, Any]
) -> dict[str, Any]:
    bridge_gate = load_json_strict(
        _pin_path(project_root, authority, "confirmed_mpi_bridge_gate")
    )
    e23_gate = load_json_strict(_pin_path(project_root, authority, "e23_gate"))
    contact = yaml.safe_load(
        _pin_path(project_root, authority, "design_contact_model").read_text(
            encoding="utf-8"
        )
    )
    target = yaml.safe_load(
        _pin_path(project_root, authority, "target_models").read_text(
            encoding="utf-8"
        )
    )
    actuator = load_json_strict(
        _pin_path(project_root, authority, "actuator_candidate")
    )
    checks = {
        "mpi_bridge_gate_9_of_9": bridge_gate.get("mpi_gate") == "PASS"
        and bridge_gate.get("criterion_counts")
        == {"total": 9, "pass": 9, "fail": 0},
        "mpi_bridge_does_not_authorize_next_stage": bridge_gate.get(
            "next_stage_authorized"
        )
        is False,
        "E23_18_of_18_provisional_physics": e23_gate.get("technical_verdict")
        == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
        and e23_gate.get("summary", {}).get("passed") == 18
        and e23_gate.get("summary", {}).get("total") == 18,
        "E23_credit_not_inherited": e23_gate.get("release_credit") is False,
        "contact_is_bounded_provisional_not_as_built": contact.get("class")
        == "BOUNDED_PROVISIONAL__NOT_A_MEASUREMENT__NOT_AS_BUILT"
        and contact.get("next_stage_authorized") is False,
        "target_options_bound": float(target["target_satellite_v0"]["mass_kg"])
        == 22.0
        and float(target["target_debris_v0"]["mass_kg"]) == 150.0,
        "actuator_hardware_invalid": actuator.get("hardware_model_valid") is False
        and actuator.get("zero_fill_forbidden") is True,
    }
    return {
        "schema": "R2_DYNAMICS_AUTHORITY_BOUNDARY_AUDIT_V1",
        "configuration_classes": authority["configuration_classes"],
        "contact_target_actuator_boundary": authority[
            "contact_target_actuator_boundary"
        ],
        "checks": checks,
        "all_bindings_consistent": all(checks.values()),
        "current_class": "CURRENT_R2",
        "legacy_24kg_inherited": False,
        "target_attached_plant_instantiated": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_constrained_gate(
    source_binding: Mapping[str, Any],
    authority_boundary: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    constrained = diagnostics["constrained"]
    checks = {
        "DG0_source_pins_exact": source_binding["all_match"] is True,
        "DG0_authority_boundary_consistent": authority_boundary[
            "all_bindings_consistent"
        ]
        is True,
        "DG1_8DOF_6R2P_bound": constrained["checks"]["backend_dof_8"]
        and constrained["checks"]["joint_types_6R2P"],
        "DG1_mass_symmetry_partitioned_by_units": all(
            constrained["checks"][name]
            for name in (
                "mass_symmetric_RR",
                "mass_symmetric_RP",
                "mass_symmetric_PP",
                "mass_symmetric_RR_over_short_trajectory",
                "mass_symmetric_RP_over_short_trajectory",
                "mass_symmetric_PP_over_short_trajectory",
            )
        ),
        "DG1_heterogeneous_coordinate_metric_bound": constrained["checks"][
            "heterogeneous_coordinate_metric_bound"
        ],
        "DG1_locked_2P_KKT_equilibrium": constrained["checks"][
            "kkt_equilibrium_revolute"
        ]
        and constrained["checks"]["kkt_equilibrium_prismatic"],
        "DG1_locked_2P_acceleration_constraint": constrained["checks"][
            "locked_ddqP_exact_within_tolerance"
        ],
        "DG1_explicit_constraint_reactions": constrained["checks"][
            "constraint_reaction_explicit_and_nonzero"
        ],
        "DG1_coordinate_elimination_cross": constrained["checks"][
            "KKT_vs_coordinate_elimination_revolute_acceleration"
        ]
        and constrained["checks"][
            "KKT_vs_coordinate_elimination_prismatic_acceleration"
        ]
        and constrained["checks"]["KKT_vs_coordinate_elimination_reaction"],
        "DG1_base_acceleration_cross": constrained["checks"][
            "base_acceleration_finite_and_coordinate_crossed"
        ],
        "DG1_tauP_zero_falsifier": constrained["checks"][
            "tauP_zero_not_misclassified_as_lock"
        ],
        "DG2_short_time_energy_smoke": constrained["checks"][
            "locked_short_time_energy"
        ],
        "DG2_solver_cross_partitioned_qR_dqR": constrained["checks"][
            "RK4_vs_DOP853_qR"
        ]
        and constrained["checks"]["RK4_vs_DOP853_dqR"],
        "DG2_mechanical_connection_zero_momentum_identity": constrained[
            "checks"
        ]["mechanical_connection_linear_zero_identity"]
        and constrained["checks"]["mechanical_connection_angular_zero_identity"],
        "DG2_independent_full_state_momentum_conservation": constrained[
            "checks"
        ]["independent_full_state_momentum_conservation"],
        "DG2_arm_stop_degeneration": constrained["checks"][
            "arm_stop_revolute_acceleration_zero"
        ]
        and constrained["checks"]["arm_stop_prismatic_acceleration_zero"]
        and constrained["checks"]["arm_stop_constraint_reaction_zero"]
        and constrained["checks"]["arm_stop_base_linear_twist_zero"]
        and constrained["checks"]["arm_stop_base_angular_twist_zero"],
        "DG2_constraint_maintained_over_short_trajectory": constrained["checks"][
            "locked_constraint_bounded_over_short_trajectory"
        ]
        and constrained["checks"][
            "KKT_equilibrium_revolute_bounded_over_short_trajectory"
        ]
        and constrained["checks"][
            "KKT_equilibrium_prismatic_bounded_over_short_trajectory"
        ],
        "DG5_deterministic_replay": diagnostics["determinism"][
            "constrained_exact_canonical_match"
        ]
        is True,
    }
    candidate_pass = all(checks.values())
    return {
        "schema": "R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1",
        "technical_verdict": (
            "R2_8DOF_CONSTRAINED_DYNAMICS_CANDIDATE_PASS"
            if candidate_pass
            else "R2_8DOF_CONSTRAINED_DYNAMICS_HOLD__UNIT_METRIC_AND_INDEPENDENT_CONSERVATION_UNBOUND"
        ),
        "scope": "CURRENT_R2_RIGID_ZERO_MOMENTUM_8DOF__LOCKED_2P_KKT_AND_ACTUATED_BOUNDARY",
        "checks": checks,
        "summary": {
            "passed": sum(checks.values()),
            "total": len(checks),
            "failed": [key for key, value in checks.items() if not value],
        },
        "key_metrics": {
            "total_mass_kg": constrained["model"]["total_mass_kg"],
            "mass_coordinate_metric_status": constrained["mass_matrix"][
                "coordinate_metric_status"
            ],
            "raw_unscaled_mass_min_eigenvalue_no_credit": constrained[
                "mass_matrix"
            ]["raw_unscaled_min_eigenvalue_no_credit"],
            "raw_unscaled_mass_condition_number_no_credit": constrained[
                "mass_matrix"
            ]["raw_unscaled_condition_number_no_credit"],
            "mass_symmetry_RR_max_abs_kg_m2": constrained["mass_matrix"][
                "symmetry_RR_max_abs_kg_m2"
            ],
            "mass_symmetry_RP_max_abs_kg_m": constrained["mass_matrix"][
                "symmetry_RP_max_abs_kg_m"
            ],
            "mass_symmetry_PP_max_abs_kg": constrained["mass_matrix"][
                "symmetry_PP_max_abs_kg"
            ],
            "locked_reaction_N": constrained["locked_2P"]["reaction_N"],
            "locked_reaction_norm_N": constrained["locked_2P"][
                "reaction_norm_N"
            ],
            "constraint_acceleration_max_abs_m_s2": constrained["locked_2P"][
                "constraint_acceleration_max_abs_m_s2"
            ],
            "KKT_coordinate_revolute_acceleration_cross_max_abs_rad_s2": constrained["locked_2P"][
                "coordinate_elimination_cross"
            ]["revolute_acceleration_max_abs_rad_s2"],
            "KKT_coordinate_prismatic_acceleration_cross_max_abs_m_s2": constrained["locked_2P"][
                "coordinate_elimination_cross"
            ]["prismatic_acceleration_max_abs_m_s2"],
            "KKT_coordinate_reaction_cross_max_abs_N": constrained["locked_2P"][
                "coordinate_elimination_cross"
            ]["reaction_max_abs_N"],
            "base_twist_rate_body_coordinates_mixed_m_s2_rad_s2": constrained[
                "locked_2P"
            ]["base_kinematics"][
                "base_twist_rate_body_coordinates_mixed_m_s2_rad_s2"
            ],
            "base_linear_acceleration_coordinate_cross_max_abs_m_s2": constrained["locked_2P"][
                "base_kinematics"
            ]["coordinate_elimination_linear_cross_max_abs_m_s2"],
            "base_angular_acceleration_coordinate_cross_max_abs_rad_s2": constrained["locked_2P"][
                "base_kinematics"
            ]["coordinate_elimination_angular_cross_max_abs_rad_s2"],
            "tauP_zero_free_ddqP_norm_m_s2": constrained[
                "actuated_8DOF_boundary"
            ]["same_state_tauP_zero_free_ddqP_norm_m_s2"],
            "energy_relative_drift": constrained["locked_short_time_integration"][
                "energy_relative_drift"
            ],
            "RK4_DOP853_qR_cross_relative": constrained[
                "locked_short_time_integration"
            ]["solver_cross_final_qR_relative"],
            "RK4_DOP853_dqR_cross_relative": constrained[
                "locked_short_time_integration"
            ]["solver_cross_final_dqR_relative"],
            "linear_momentum_residual_norm_Ns": constrained[
                "zero_momentum_audit"
            ]["linear_momentum_residual_norm_Ns"],
            "angular_momentum_residual_norm_Nms": constrained[
                "zero_momentum_audit"
            ]["angular_momentum_residual_norm_Nms"],
        },
        "actuated_8DOF_boundary": {
            "interface_implemented": True,
            "hardware_effort_envelope_enforced": False,
            "hardware_valid": False,
            "hold": "MEASUREMENT_PENDING__NO_HARDWARE_EFFORT_OR_RATE_ENVELOPE",
        },
        "candidate_package_complete": candidate_pass,
        "artifact_package_generated": True,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_engineering_gate(
    source_binding: Mapping[str, Any],
    authority_boundary: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    constrained_gate: Mapping[str, Any],
) -> dict[str, Any]:
    flex = diagnostics["flex"]
    dg = [
        {
            "id": "DG0",
            "name": "authority_binding",
            "status": "PASS_CANDIDATE",
            "satisfied": bool(
                source_binding["all_match"]
                and authority_boundary["all_bindings_consistent"]
            ),
            "credit": "HASH_BOUND_INPUT_AUTHORITY_ONLY",
        },
        {
            "id": "DG1",
            "name": "6R_plus_2P_constrained_dynamics",
            "status": "HOLD_HETEROGENEOUS_COORDINATE_METRIC_UNBOUND",
            "satisfied": constrained_gate["candidate_package_complete"],
            "credit": "KKT_AND_COORDINATE_ELIMINATION_COMPONENT_DIAGNOSTICS_ONLY__NO_MIXED_COORDINATE_SPECTRAL_OR_NORM_CREDIT",
        },
        {
            "id": "DG2",
            "name": "free_floating_conservation",
            "status": "HOLD_MECHANICAL_CONNECTION_IDENTITY_IS_NOT_INDEPENDENT_FULL_STATE_CONSERVATION",
            "satisfied": False,
            "algebraic_identity_diagnostic_pass": bool(
                diagnostics["constrained"]["checks"][
                    "mechanical_connection_linear_zero_identity"
                ]
                and diagnostics["constrained"]["checks"][
                    "mechanical_connection_angular_zero_identity"
                ]
            ),
            "short_time_energy_smoke_pass": diagnostics["constrained"][
                "checks"
            ]["locked_short_time_energy"],
            "credit": "ALGEBRAIC_ZERO_MOMENTUM_IDENTITY_AND_0P004S_ENERGY_SMOKE_ONLY__NO_CONSERVATION_GATE_CREDIT",
        },
        {
            "id": "DG3",
            "name": "R2_flex_coupling",
            "status": "HOLD_PARTIAL_COMPONENT_DIAGNOSTIC_ONLY",
            "satisfied": False,
            "component_diagnostic_pass": flex[
                "pass_for_bounded_component_diagnostic"
            ],
            "reason": "SOLAR_R2_14MODE_RINGDOWN_VALIDATED_BUT_ARM_TO_FLEX_TIME_DOMAIN_COUPLING_NOT_IMPLEMENTED",
        },
        {
            "id": "DG4",
            "name": "contact_hybrid_transition",
            "status": "HOLD_NOT_IMPLEMENTED",
            "satisfied": False,
            "reason": "CONTACT_PATCH_AND_AS_BUILT_PARAMETERS_OPEN__TARGET_ATTACHED_PLANT_NOT_INSTANTIATED",
        },
        {
            "id": "DG5",
            "name": "uncertainty_and_deterministic_replay",
            "status": "HOLD_PARTIAL",
            "satisfied": False,
            "deterministic_candidate_replay": bool(
                diagnostics["determinism"]["constrained_exact_canonical_match"]
                and diagnostics["determinism"]["flex_exact_canonical_match"]
            ),
            "reason": "LOW_NOMINAL_HIGH_ROM_CORNERS_BOUND_BUT_AS_BUILT_MASS_CONTACT_ACTUATOR_UNCERTAINTY_REMAINS",
        },
    ]
    candidate_complete = bool(
        all(row["satisfied"] for row in dg[:3])
        and flex["pass_for_bounded_component_diagnostic"]
        and diagnostics["determinism"]["constrained_exact_canonical_match"]
        and diagnostics["determinism"]["flex_exact_canonical_match"]
    )
    holds = [
        {
            "id": "DG1_HETEROGENEOUS_COORDINATE_METRIC",
            "state": "HOLD",
            "required_evidence": "FROZEN_REVOLUTE_PRISMATIC_NONDIMENSIONALIZATION_OR_REFERENCE_METRIC_WITH_UNIT_REPARAMETERIZATION_INVARIANCE_TEST",
        },
        {
            "id": "DG2_INDEPENDENT_FULL_STATE_CONSERVATION",
            "state": "HOLD",
            "required_evidence": "INDEPENDENT_BASE_POSE_TWIST_PLUS_JOINT_STATE_INTEGRATION_WITH_NONZERO_TOTAL_MOMENTUM_CASE_AND_SEPARATE_LINEAR_ANGULAR_RESIDUALS",
        },
        {
            "id": "DG3_ARM_FLEX_TIME_DOMAIN_COUPLING",
            "state": "HOLD",
            "required_evidence": "R2_8DOF_TO_DUAL_WING_14MODE_COUPLED_EQUATIONS_AND_RIGID_LIMIT_CROSSCHECK",
        },
        {
            "id": "DG4_CONTACT_HYBRID",
            "state": "HOLD",
            "required_evidence": "CONTACT_PATCH_FRAMES_CALIBRATION_AND_PRE_TO_POST_CAPTURE_PLANT_SWITCH",
        },
        {
            "id": "ACTUATOR_HARDWARE",
            "state": "MEASUREMENT_PENDING",
            "required_evidence": "OUTPUT_EFFORT_RATE_DELAY_THERMAL_AND_FAULT_ENVELOPES_FOR_6R2P",
        },
        {
            "id": "TARGET_ATTACHED_POST_CAPTURE",
            "state": "NOT_IMPLEMENTED",
            "required_evidence": "22KG_AND_150KG_COMBINED_MASS_CG_INERTIA_PLANT_INSTANCES",
        },
        {
            "id": "AS_BUILT_SYSTEM_PROPERTIES",
            "state": "MEASUREMENT_PENDING",
            "required_evidence": "AS_BUILT_MASS_CG_INERTIA_METROLOGY",
        },
    ]
    unknowns = [
        "HETEROGENEOUS_6R2P_COORDINATE_REFERENCE_METRIC",
        "INDEPENDENT_FULL_STATE_FREE_FLOATING_CONSERVATION",
        "AS_BUILT_6R2P_ACTUATOR_DYNAMICS",
        "AS_BUILT_CONTACT_PARAMETERS_AND_PATCH_FRAMES",
        "TARGET_INTERFACE_GEOMETRY_AND_INERTIA_CONFIDENCE",
        "ARM_TO_SOLAR_R2_14MODE_TIME_DOMAIN_COUPLING",
        "POST_CAPTURE_HYBRID_PLANT",
        "WHEEL_MOMENTUM_STATE_AND_ACTUATOR_DYNAMICS",
    ]
    return {
        "schema": "R2_DYNAMICS_ENGINEERING_GATE_V1",
        "technical_verdict": (
            "R2_DYNAMICS_ENGINEERING_CANDIDATE_BUILT__DG3_DG4_DG5_HOLD__NO_RELEASE_CREDIT"
            if candidate_complete
            else "R2_DYNAMICS_ENGINEERING_HOLD__DG1_UNIT_METRIC_DG2_INDEPENDENT_CONSERVATION_DG3_DG4_DG5_OPEN__NO_RELEASE_CREDIT"
        ),
        "scope": "R2_CONSTRAINED_DYNAMICS_ENGINEERING_CANDIDATE_NOT_CONTACT_NOT_CONTROL_NOT_FLIGHT",
        "gate_rows": dg,
        "summary": {
            "candidate_satisfied": sum(row["satisfied"] for row in dg),
            "total": len(dg),
            "engineering_pass": 0,
            "holds": [row["id"] for row in dg if not row["satisfied"]],
        },
        "configuration_class_separation": authority_boundary[
            "configuration_classes"
        ],
        "holds": holds,
        "unknowns": unknowns,
        "unknown_auto_allow_count": 0,
        "source_binding": source_binding["summary"],
        "constrained_gate": {
            "schema": constrained_gate["schema"],
            "technical_verdict": constrained_gate["technical_verdict"],
            "candidate_package_complete": constrained_gate[
                "candidate_package_complete"
            ],
        },
        "flex_diagnostic": {
            "component_diagnostic_pass": flex[
                "pass_for_bounded_component_diagnostic"
            ],
            "arm_to_flex_time_domain_coupling_evaluated": flex[
                "arm_to_flex_time_domain_coupling_evaluated"
            ],
            "E23_pass_inherited": flex["E23_pass_inherited"],
        },
        "execution_guards": diagnostics["execution_guards"],
        "candidate_package_complete": candidate_complete,
        "artifact_package_generated": True,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }


def package_artifact_paths() -> list[Path]:
    required = [
        PACKAGE_DIR / "README.md",
        PACKAGE_DIR / "contracts" / "R2_DYNAMICS_AUTHORITY_V1.yaml",
        PACKAGE_DIR / "config" / "R2_DYNAMICS_ENGINEERING_CONFIG_V1.json",
        PACKAGE_DIR / "src" / "__init__.py",
        PACKAGE_DIR / "src" / "r2_dynamics.py",
        PACKAGE_DIR / "src" / "build_dynamics_gate.py",
        PACKAGE_DIR / "tests" / "test_r2_dynamics.py",
        RESULTS_DIR / "R2_DYNAMICS_SOURCE_BINDING_V1.json",
        RESULTS_DIR / "R2_DYNAMICS_AUTHORITY_BOUNDARY_AUDIT_V1.json",
        RESULTS_DIR / "R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json",
        RESULTS_DIR / "R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json",
        RESULTS_DIR / "R2_DYNAMICS_ENGINEERING_GATE_V1.json",
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "REQUIRED_PACKAGE_ARTIFACT_MISSING:"
            + ",".join(path.as_posix() for path in missing)
        )
    return required


def build_package_manifest(project_root: Path) -> dict[str, Any]:
    rows = [
        {
            "path": path.relative_to(project_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in package_artifact_paths()
    ]
    return {
        "schema": "R2_DYNAMICS_PACKAGE_MANIFEST_V1",
        "coverage_policy": "EXPLICIT_PACKAGE_ARTIFACTS_EXCLUDING_MANIFEST_AND_SHA_CSV",
        "artifacts": rows,
        "summary": {"count": len(rows), "all_exist": True},
        "artifact_package_complete": True,
        "candidate_package_complete": False,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def write_sha_csv(project_root: Path, manifest_path: Path) -> None:
    rows = package_artifact_paths() + [manifest_path]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256"])
    for path in rows:
        writer.writerow(
            [
                path.relative_to(project_root).as_posix(),
                path.stat().st_size,
                file_sha256(path),
            ]
        )
    (RESULTS_DIR / "R2_DYNAMICS_SHA256_V1.csv").write_text(
        buffer.getvalue(), encoding="utf-8", newline="\n"
    )


def build(project_root: Path) -> dict[str, Any]:
    authority, config = load_contracts()
    source_binding = validate_source_pins(project_root, authority)
    write_json(RESULTS_DIR / "R2_DYNAMICS_SOURCE_BINDING_V1.json", source_binding)
    if not source_binding["all_match"]:
        raise RuntimeError("R2_DYNAMICS_SOURCE_HASH_DRIFT_FAIL_CLOSED")

    authority_boundary = build_authority_boundary(project_root, authority)
    write_json(
        RESULTS_DIR / "R2_DYNAMICS_AUTHORITY_BOUNDARY_AUDIT_V1.json",
        authority_boundary,
    )
    if not authority_boundary["all_bindings_consistent"]:
        raise RuntimeError("R2_DYNAMICS_AUTHORITY_BOUNDARY_INCONSISTENT")

    diagnostics = run_all_diagnostics(project_root, authority, config)
    write_json(
        RESULTS_DIR / "R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json", diagnostics
    )
    constrained_gate = build_constrained_gate(
        source_binding, authority_boundary, diagnostics
    )
    write_json(
        RESULTS_DIR / "R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json",
        constrained_gate,
    )
    engineering_gate = build_engineering_gate(
        source_binding, authority_boundary, diagnostics, constrained_gate
    )
    write_json(
        RESULTS_DIR / "R2_DYNAMICS_ENGINEERING_GATE_V1.json", engineering_gate
    )

    manifest = build_package_manifest(project_root)
    manifest_path = RESULTS_DIR / "R2_DYNAMICS_PACKAGE_MANIFEST_V1.json"
    write_json(manifest_path, manifest)
    write_sha_csv(project_root, manifest_path)
    return {
        "engineering_gate": engineering_gate,
        "constrained_gate": constrained_gate,
        "manifest_sha256": file_sha256(manifest_path),
        "canonical_engineering_gate_sha256": canonical_sha256(engineering_gate),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = build(args.repo_root.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
