"""Build deterministic DG3 evidence, gate, manifest, and checksums."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any, Mapping


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg3_arm_flex import (  # noqa: E402
    canonical_sha256,
    jsonable,
    load_json,
    sha256,
)
from dg3_candidate import evaluate  # noqa: E402


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(jsonable(value), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_gate(evidence: Mapping[str, Any], deterministic: bool) -> dict[str, Any]:
    rom = evidence["rom_structure_audit"]
    urdf = evidence["unified_urdf_mass_and_frame_audit"]
    representation = evidence["representation_compatibility_audit"]
    undamped = evidence["undamped_coupling_gate_lanes"]
    conservative = evidence["conservative_free_response_lane"]
    modes_removed = evidence["modes_removed_constrained_rigid_lane"]
    spectral = evidence["spectral_credit_policy"]
    zero_cross = evidence["zero_coupling_falsifier"]["metrics"][
        "base_cross_vs_true_modes_removed_by_declared_dimension"
    ]
    checks = {
        "G01_contract_exact_schema_authority_claim_thresholds_units_and_holds": evidence[
            "contract_semantics_audit"
        ]["pass"]
        and all(evidence["contract_semantics_audit"]["checks"].values()),
        "G02_contract_nine_class_authority_claim_threshold_unit_corner_solver_guard_q0_tamper_controls": evidence[
            "contract_tamper_negative_controls"
        ]["all_rejected"]
        and all(
            row["rejected"] and row["expected_checks_failed"]
            for row in evidence["contract_tamper_negative_controls"][
                "controls"
            ].values()
        ),
        "G03_LOW_NOMINAL_HIGH_corner_semantics_exact": evidence[
            "corner_semantics_audit"
        ]["pass"]
        and all(evidence["corner_semantics_audit"]["checks"].values()),
        "G04_all_15_source_pins_exact": evidence["source_binding"]["all_match"]
        is True
        and evidence["source_binding"]["matched"]
        == evidence["source_binding"]["total"]
        == 15,
        "G05_upstream_authorities_bound_without_release_inheritance": all(
            evidence["authority_checks"].values()
        ),
        "G06_mode_order_and_Mrom_identity_machine_verified": rom["checks"][
            "mode_order_exact"
        ]
        and rom["checks"]["Phi_and_Mrom_npz_json_exact"]
        and rom["checks"]["Mrom_mass_normalized_identity"],
        "G07_Gamma_PhiTB_mirror_and_structural_zeros_machine_verified": all(
            rom["checks"][name]
            for name in (
                "Gamma_equals_PhiT_B_all_sides",
                "left_right_mirror_exact",
                "structural_zeros_and_active_entries_exact",
                "reconstruction_contract_exact",
            )
        ),
        "G08_S_frame_and_dual_wing_root_handshake": all(
            urdf["checks"][name]
            for name in (
                "URDF_tree_is_19_link_18_joint_rooted_in_S",
                "wing_roots_match_ROM_and_frame_tree",
                "B601_current_physical_frame_handshake",
            )
        ),
        "G09_URDF_wings_each_0p78_and_total_mass_already_contains_1p56": urdf[
            "checks"
        ]["URDF_wings_each_0p78_and_total_mass_reclosed"],
        "G10_no_modal_rigid_mass_add_and_double_count_negative_control": urdf[
            "checks"
        ]["no_rigid_wing_mass_added_with_modal_coordinates"]
        and urdf["checks"]["double_count_negative_control_detected"],
        "G11_no_mixed_unit_spectral_numeric_output_or_credit": all(
            spectral["checks"].values()
        ),
        "G12_all_solved_mass_matrices_Cholesky_positive_definite_boolean": evidence[
            "mass_matrix_positive_definite_audit"
        ]["pass"]
        and all(
            evidence["mass_matrix_positive_definite_audit"]["checks"].values()
        ),
        "G13_C0_three_corner_canonical_linear_angular_momentum": all(
            row["checks"]["canonical_base_linear_momentum"]
            and row["checks"]["canonical_base_angular_momentum"]
            for row in undamped
        ),
        "G14_C0_three_corner_solver_energy_work_and_arm_modal_response": all(
            row["gate_pass"]
            and row["checks"]["energy_work_dissipation_balance"]
            and row["checks"]["arm_motion_excites_modal_energy"]
            for row in undamped
        ),
        "G15_C0_unforced_total_energy_and_momentum_conservative_lane": conservative[
            "pass"
        ]
        and all(conservative["checks"].values()),
        "G16_true_modes_removed_structure_and_four_dimension_analytic_lane": modes_removed["pass"]
        and modes_removed["definition"].startswith(
            "MODES_REMOVED_CONSTRAINED_RIGID"
        )
        and all(
            modes_removed["analytic_cross_by_declared_dimension"][dimension][
                "pass"
            ]
            for dimension in (
                "position",
                "attitude",
                "linear_rate",
                "angular_rate",
            )
        ),
        "G17_modes_removed_Radau_BDF_position_m": modes_removed[
            "Radau_BDF_cross_by_declared_dimension"
        ]["position"]["pass"],
        "G18_modes_removed_Radau_BDF_attitude_rad": modes_removed[
            "Radau_BDF_cross_by_declared_dimension"
        ]["attitude"]["pass"],
        "G19_modes_removed_Radau_BDF_linear_rate_m_s": modes_removed[
            "Radau_BDF_cross_by_declared_dimension"
        ]["linear_rate"]["pass"],
        "G20_modes_removed_Radau_BDF_angular_rate_rad_s": modes_removed[
            "Radau_BDF_cross_by_declared_dimension"
        ]["angular_rate"]["pass"],
        "G21_zero_coupling_falsifier_structure_distinct_and_modal_response_zero": all(
            value
            for name, value in evidence["falsifier_checks"].items()
            if "matches_modes_removed" not in name
        )
        and evidence["zero_coupling_falsifier"]["explicit_non_equivalence"]
        == "THIS_IS_NOT_THE_MODES_REMOVED_RIGID_LANE",
        "G22_zero_coupling_vs_modes_removed_position_m": zero_cross["position"][
            "pass"
        ],
        "G23_zero_coupling_vs_modes_removed_attitude_rad": zero_cross["attitude"][
            "pass"
        ],
        "G24_zero_coupling_vs_modes_removed_linear_rate_m_s": zero_cross[
            "linear_rate"
        ]["pass"],
        "G25_zero_coupling_vs_modes_removed_angular_rate_rad_s": zero_cross[
            "angular_rate"
        ]["pass"],
        "G26_damped_LOW_NOMINAL_HIGH_diagnostic_only": spectral["checks"][
            "damped_LOW_NOMINAL_HIGH_are_diagnostic_only"
        ]
        and all(
            row["gate_credit"] is False
            for row in evidence["damped_sensitivity_diagnostics"]
        ),
        "G27_E23_0p5153pct_root_cause_bound_no_numeric_inheritance": urdf["checks"][
            "E23_legacy_transform_use_machine_bound"
        ]
        and urdf["checks"]["E23_Hbb_mismatch_replayed_and_inheritance_denied"]
        and representation["root_cause"]
        == "E23_C07_USES_LEGACY_X_0P18525_NO_CLOCKING__UNIFIED_USES_PHYSICAL_X_0P208_PLUS_25P000014_DEG"
        and representation["E23_numerical_inheritance"] is False,
        "G28_deterministic_replay": deterministic,
        "G29_no_execution_guard_triggered": all(
            value is False for value in evidence["execution_guards"].values()
        ),
        "G30_parent_DG3_hardware_production_next_stage_release_hold": evidence[
            "parent_DG3_satisfied"
        ] is False
        and evidence["parent_DG3_complete"] is False
        and evidence["dynamics_engineering_complete"] is False
        and evidence["hardware_valid"] is False
        and evidence["production_valid"] is False
        and evidence["next_stage_authorized"] is False
        and evidence["release_credit"] is False
        and evidence["review_status"] == "PENDING_OWNER_REVIEW",
    }
    passed = all(checks.values())
    return {
        "schema": "R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1",
        "technical_verdict": (
            "DG3_BOUNDED_C0_CONSERVATION_ARM_FLEX_CANDIDATE_30_OF_30_PASS__PARENT_DG3_HOLD"
            if passed
            else "DG3_ARM_FLEX_COUPLING_CANDIDATE_HOLD__SEE_FAILED_CHECKS"
        ),
        "checks": checks,
        "summary": {
            "passed": sum(bool(value) for value in checks.values()),
            "total": len(checks),
            "failed": [name for name, value in checks.items() if not value],
        },
        "candidate_package_complete": passed,
        "maximum_claim": "BOUNDED_FROZEN_LINEAR_C0_CONSERVATION_AND_ARM_FLEX_COUPLING_CANDIDATE",
        "mixed_28x28_spectral_credit": False,
        "E23_numerical_inheritance": False,
        "parent_DG3_satisfied": False,
        "parent_DG3_complete": False,
        "remaining_DG3_scope": [
            "TIME_VARYING_UNIFIED_R2_MASS_MATRIX",
            "FULL_CORIOLIS_AND_EULER_POINCARE_ARTICULATED_FLEX_TERMS",
            "TORQUE_DRIVEN_ACTUATOR_MODEL",
            "AS_BUILT_MODAL_CORRELATION",
        ],
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }

def artifact_rows(paths: list[Path]) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in paths
    ]


def main() -> int:
    first = evaluate()
    second = evaluate()
    first_hash = canonical_sha256(first)
    second_hash = canonical_sha256(second)
    deterministic = first_hash == second_hash
    first["determinism"] = {
        "exact_canonical_match": deterministic,
        "first_sha256_before_determinism_field": first_hash,
        "second_sha256": second_hash,
    }
    evidence_path = PACKAGE / "results" / "DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json"
    gate_path = PACKAGE / "results" / "R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1.json"
    write_json(evidence_path, first)
    gate = build_gate(first, deterministic)
    write_json(gate_path, gate)
    required = [
        PACKAGE / "README.md",
        PACKAGE / "contracts" / "DG3_ARM_FLEX_COUPLING_CONTRACT_V1.json",
        PACKAGE / "src" / "__init__.py",
        PACKAGE / "src" / "dg3_arm_flex.py",
        PACKAGE / "src" / "dg3_candidate.py",
        PACKAGE / "run_validation.py",
        PACKAGE / "tests" / "test_dg3_arm_flex.py",
        evidence_path,
        gate_path,
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("REQUIRED_ARTIFACT_MISSING")
    rows = artifact_rows(required)
    manifest = {
        "schema": "DG3_ARM_FLEX_COUPLING_PACKAGE_MANIFEST_V1",
        "artifacts": rows,
        "external_input_pins": first["source_binding"]["pins"],
        "summary": {
            "count": len(rows),
            "external_pin_count": first["source_binding"]["total"],
            "all_exist": True,
            "all_external_pins_match": first["source_binding"]["all_match"],
        },
        "candidate_package_complete": gate["candidate_package_complete"],
        "parent_DG3_satisfied": False,
        "parent_DG3_complete": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_path = PACKAGE / "results" / "DG3_ARM_FLEX_COUPLING_PACKAGE_MANIFEST_V1.json"
    write_json(manifest_path, manifest)
    checksum_path = PACKAGE / "results" / "DG3_ARM_FLEX_COUPLING_SHA256_V1.csv"
    with checksum_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("path", "bytes", "sha256"))
        writer.writeheader()
        writer.writerows(artifact_rows(required + [manifest_path]))
    print(gate["technical_verdict"])
    print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
    return 0 if gate["candidate_package_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
