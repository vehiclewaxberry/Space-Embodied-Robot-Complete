from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg3_arm_flex import (  # noqa: E402
    contract_tamper_negative_controls,
    load_contract,
    load_json,
    sha256,
    validate_contract_semantics,
    validate_source_pins,
)


def result(name: str) -> dict:
    return load_json(PACKAGE / "results" / name)


def test_all_15_source_pins_exact() -> None:
    binding = validate_source_pins(load_contract())
    assert binding["all_match"] is True
    assert binding["matched"] == binding["total"] == 15


def test_full_contract_and_all_policy_sections_are_exact() -> None:
    audit = validate_contract_semantics(load_contract())
    assert audit["pass"] is True
    assert audit["failed"] == []
    assert audit["checks"]["full_parsed_contract_canonical_sha256_exact"] is True
    assert all(audit["checks"].values())


def test_nine_contract_tamper_negative_controls_fail_closed() -> None:
    controls = contract_tamper_negative_controls(load_contract())
    assert controls["all_rejected"] is True
    assert set(controls["controls"]) == {
        "authority_promotion",
        "forbidden_claim_deletion",
        "threshold_widening",
        "unit_tamper",
        "corner_semantics_tamper",
        "excitation_authority_promotion",
        "solver_tolerance_and_step_relaxation",
        "execution_guard_key_removal",
        "frozen_q0_tamper",
    }
    assert all(
        row["rejected"] and row["expected_checks_failed"]
        for row in controls["controls"].values()
    )


def test_direct_policy_mutations_are_rejected_independently() -> None:
    contract = load_contract()
    mutations = []

    promoted = copy.deepcopy(contract)
    promoted["authority_scope"] = "PRODUCTION_RELEASE"
    mutations.append(promoted)

    forbidden_deleted = copy.deepcopy(contract)
    forbidden_deleted["claim_boundary"]["forbidden"].pop(0)
    mutations.append(forbidden_deleted)

    threshold_widened = copy.deepcopy(contract)
    threshold_widened["thresholds"][
        "zero_coupling_vs_modes_removed_position_cross_max_m"
    ] = 1.0
    mutations.append(threshold_widened)

    unit_changed = copy.deepcopy(contract)
    unit_changed["threshold_units"][
        "modes_removed_solver_position_cross_max_m"
    ] = "mm"
    mutations.append(unit_changed)

    corner_changed = copy.deepcopy(contract)
    corner_changed["corners"] = ["LOW", "HIGH"]
    mutations.append(corner_changed)

    excitation_changed = copy.deepcopy(contract)
    excitation_changed["prescribed_excitation"]["authority"] = "COMMAND"
    mutations.append(excitation_changed)

    solver_changed = copy.deepcopy(contract)
    solver_changed["solvers"]["atol"] = 1.0e-6
    mutations.append(solver_changed)

    guard_deleted = copy.deepcopy(contract)
    del guard_deleted["execution_guards"]["contact_called"]
    mutations.append(guard_deleted)

    q0_changed = copy.deepcopy(contract)
    q0_changed["frozen_linearization"]["q0_mixed_rad_m"][7] = 0.0
    mutations.append(q0_changed)

    assert all(validate_contract_semantics(row)["pass"] is False for row in mutations)


def test_mode_order_mrom_gamma_mirror_and_structural_zeros() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "rom_structure_audit"
    ]
    assert audit["mode_labels"] == [
        "BENDING_1",
        "BENDING_2",
        "BENDING_3",
        "TORSION_1",
        "TORSION_2",
        "TORSION_3",
        "TORSION_4",
    ]
    assert audit["hf_mode_indices_1based"] == [1, 4, 8, 2, 3, 5, 6]
    assert audit["Mrom_minus_identity_max_abs"] <= 1e-12
    assert all(audit["checks"].values())


def test_S_frame_and_wing_root_handshake() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "unified_urdf_mass_and_frame_audit"
    ]
    assert audit["checks"]["URDF_tree_is_19_link_18_joint_rooted_in_S"] is True
    assert audit["checks"]["wing_roots_match_ROM_and_frame_tree"] is True
    assert audit["checks"]["B601_current_physical_frame_handshake"] is True
    assert audit["frame_handshake_audit"]["S_root_link"] == "spacecraft_bus"


def test_unified_urdf_contains_both_rigid_wing_masses_once() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "unified_urdf_mass_and_frame_audit"
    ]
    mass = audit["solar_mass_audit"]
    assert mass["left_mass_kg"] == 0.78
    assert mass["right_mass_kg"] == 0.78
    assert mass["solar_total_mass_kg"] == 1.56
    assert abs(mass["urdf_all_physical_link_mass_kg"] - 31.022864807342987) <= 1e-12
    assert audit["checks"]["no_rigid_wing_mass_added_with_modal_coordinates"] is True


def test_double_count_negative_control_is_detected() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "unified_urdf_mass_and_frame_audit"
    ]
    negative = audit["solar_mass_audit"]["negative_control"]
    assert negative["injected_operation"].startswith("ADD_ALREADY_INCLUDED")
    assert abs(negative["detected_excess_kg"] - 1.56) <= 1e-12
    assert negative["detected"] is True
    assert audit["checks"]["double_count_negative_control_detected"] is True


def test_mixed_unit_28x28_spectrum_has_no_gate_credit() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    assert evidence["spectral_credit_policy"]["classification"] == (
        "DIAGNOSTIC_NO_SPECTRAL_CREDIT"
    )
    for row in (
        evidence["undamped_coupling_gate_lanes"]
        + evidence["damped_sensitivity_diagnostics"]
    ):
        diagnostic = row["matrix"]["diagnostic_no_spectral_credit"]
        assert diagnostic["classification"] == "DIAGNOSTIC_NO_SPECTRAL_CREDIT"
        assert diagnostic["numeric_spectral_values_emitted"] is False
        assert diagnostic["units"] is None
        assert diagnostic["gate_credit"] is False
        assert not any(
            key in diagnostic
            for key in (
                "raw_numeric_min_eigenvalue",
                "raw_numeric_max_eigenvalue",
                "raw_numeric_condition_number",
            )
        )


def test_all_solved_mass_matrices_have_boolean_cholesky_structure_checks() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    audit = evidence["mass_matrix_positive_definite_audit"]
    assert audit["pass"] is True
    assert all(audit["checks"].values())
    for row in (
        evidence["undamped_coupling_gate_lanes"]
        + evidence["damped_sensitivity_diagnostics"]
    ):
        structures = row["matrix"]["positive_definite_structure"]
        assert set(structures) == {
            "rigid_14x14",
            "base_Hbb_6x6",
            "modal_14x14",
            "full_28x28",
            "unknown_Muu_20x20",
        }
        for structure in structures.values():
            assert structure["positive_definite"] is True
            assert structure["cholesky_factorization_succeeded"] is True
            assert structure["eigenvalue_or_condition_number_emitted"] is False
            assert structure["spectral_numeric_credit"] is False


def test_LOW_NOMINAL_HIGH_corner_semantics_are_external_source_bound() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "corner_semantics_audit"
    ]
    assert audit["order"] == ["LOW", "NOMINAL", "HIGH"]
    assert audit["pass"] is True
    assert all(audit["checks"].values())


def test_three_C0_corners_close_canonical_linear_and_angular_momentum() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    lanes = evidence["undamped_coupling_gate_lanes"]
    assert [row["corner"] for row in lanes] == ["LOW", "NOMINAL", "HIGH"]
    for row in lanes:
        assert row["damping_scale"] == 0.0
        assert row["checks"]["canonical_base_linear_momentum"] is True
        assert row["checks"]["canonical_base_angular_momentum"] is True
        assert row["gate_pass"] is True


def test_C0_free_response_conserves_total_energy_and_momentum() -> None:
    lane = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "conservative_free_response_lane"
    ]
    assert lane["lane_class"].startswith("C0_UNFORCED_CONSERVATIVE")
    assert lane["damping_scale"] == 0.0
    assert lane["external_work_J"] == 0.0
    assert all(lane["checks"].values())
    assert lane["pass"] is True


def test_true_modes_removed_lane_has_no_modal_state() -> None:
    lane = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "modes_removed_constrained_rigid_lane"
    ]
    assert lane["lane_class"] == "TRUE_MODES_REMOVED_CONSTRAINED_RIGID_GATE_LANE"
    assert lane["definition"] == (
        "MODES_REMOVED_CONSTRAINED_RIGID__NO_MODAL_STATE_NO_K_NO_C_NO_GAMMA"
    )
    assert "Radau_BDF_base_state_max_abs" not in lane
    for field in (
        "analytic_base_displacement_max_abs",
        "analytic_base_rate_max_abs",
    ):
        assert field not in lane["primary"]
    expected_units = {
        "position": "m",
        "attitude": "rad",
        "linear_rate": "m/s",
        "angular_rate": "rad/s",
    }
    for record_name in (
        "analytic_cross_by_declared_dimension",
        "Radau_BDF_cross_by_declared_dimension",
    ):
        records = lane[record_name]
        assert set(records) == set(expected_units)
        for dimension, unit in expected_units.items():
            assert records[dimension]["unit"] == unit
            assert records[dimension]["threshold_unit_matches_contract"] is True
            assert records[dimension]["pass"] is True
    assert all(lane["checks"].values())
    assert lane["pass"] is True


def test_modes_removed_four_dimension_solver_regression_values() -> None:
    lane = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "modes_removed_constrained_rigid_lane"
    ]["Radau_BDF_cross_by_declared_dimension"]
    expected = {
        "position": 5.4794193037101386e-15,
        "attitude": 3.4805648450302006e-13,
        "linear_rate": 1.0341495980278849e-14,
        "angular_rate": 6.568989601406228e-13,
    }
    for dimension, value in expected.items():
        assert abs(lane[dimension]["value"] - value) <= 1.0e-24


def test_zero_coupling_falsifier_is_not_aliased_to_modes_removed() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    lane = evidence["zero_coupling_falsifier"]
    assert lane["modal_DOF_retained"] == 14
    assert lane["coupling_scale"] == 0.0
    assert lane["explicit_non_equivalence"] == (
        "THIS_IS_NOT_THE_MODES_REMOVED_RIGID_LANE"
    )
    records = lane["metrics"][
        "base_cross_vs_true_modes_removed_by_declared_dimension"
    ]
    assert "base_cross_vs_true_modes_removed_max_abs" not in lane["metrics"]
    expected_units = {
        "position": "m",
        "attitude": "rad",
        "linear_rate": "m/s",
        "angular_rate": "rad/s",
    }
    assert set(records) == set(expected_units)
    for dimension, unit in expected_units.items():
        assert records[dimension]["unit"] == unit
        assert records[dimension]["pass"] is True
    assert all(evidence["falsifier_checks"].values())


def test_zero_coupling_four_dimension_regression_values() -> None:
    records = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "zero_coupling_falsifier"
    ]["metrics"]["base_cross_vs_true_modes_removed_by_declared_dimension"]
    expected = {
        "position": 1.1858461261560205e-20,
        "attitude": 2.168404344971009e-19,
        "linear_rate": 5.759824041329242e-20,
        "angular_rate": 2.6020852139652106e-18,
    }
    for dimension, value in expected.items():
        assert abs(records[dimension]["value"] - value) <= 1.0e-28


def test_damped_three_corners_are_diagnostic_only() -> None:
    rows = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "damped_sensitivity_diagnostics"
    ]
    assert [row["corner"] for row in rows] == ["LOW", "NOMINAL", "HIGH"]
    assert all(row["gate_credit"] is False for row in rows)
    assert all("DIAGNOSTIC_ONLY" in row["lane_class"] for row in rows)


def test_E23_Hbb_mismatch_root_cause_and_no_inheritance() -> None:
    audit = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")[
        "representation_compatibility_audit"
    ]
    assert abs(audit["Hbb_relative_frobenius_difference"] - 0.005153002326417072) <= 1e-14
    assert audit["Unified_current_B601_base_x_S_m"] == 0.208
    assert audit["E23_legacy_B601_base_x_S_m"] == 0.18525
    assert abs(audit["Unified_current_clocking_deg"] - 25.000014) <= 1e-9
    assert audit["E23_legacy_clocking_deg"] == 0.0
    assert audit["E23_numerical_inheritance"] is False


def test_gate_30_of_30_preserves_parent_and_release_holds() -> None:
    gate = result("R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1.json")
    assert gate["summary"] == {"passed": 30, "total": 30, "failed": []}
    assert gate["candidate_package_complete"] is True
    assert gate["mixed_28x28_spectral_credit"] is False
    assert gate["E23_numerical_inheritance"] is False
    assert gate["parent_DG3_satisfied"] is False
    assert gate["parent_DG3_complete"] is False
    assert gate["dynamics_engineering_complete"] is False
    assert gate["hardware_valid"] is False
    assert gate["production_valid"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_manifest_and_checksums_match() -> None:
    manifest = result("DG3_ARM_FLEX_COUPLING_PACKAGE_MANIFEST_V1.json")
    assert manifest["summary"]["count"] == len(manifest["artifacts"])
    assert manifest["summary"]["external_pin_count"] == 15
    assert manifest["summary"]["all_external_pins_match"] is True
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert sha256(path) == row["sha256"]
    with (PACKAGE / "results" / "DG3_ARM_FLEX_COUPLING_SHA256_V1.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == manifest["summary"]["count"] + 1
    for row in rows:
        path = ROOT / row["path"]
        assert path.stat().st_size == int(row["bytes"])
        assert sha256(path) == row["sha256"]


def test_json_is_finite_deterministic_and_execution_guards_false() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    json.dumps(evidence, allow_nan=False)
    assert evidence["determinism"]["exact_canonical_match"] is True
    assert evidence["execution_guards"] == {
        "contact_called": False,
        "target_attached": False,
        "collision_query_called": False,
        "path_search_called": False,
        "control_command_issued": False,
        "hardware_authority_claimed": False,
    }


def test_legacy_mixed_unit_gate_scalars_and_spectral_numbers_are_absent() -> None:
    evidence = result("DG3_ARM_FLEX_COUPLING_EVIDENCE_V1.json")
    serialized = json.dumps(evidence, sort_keys=True, allow_nan=False)
    for forbidden in (
        "Radau_BDF_base_state_max_abs",
        "Radau_BDF_base_state_cross",
        "zero_coupling_vs_true_modes_removed_base_cross_max_abs",
        "base_cross_vs_true_modes_removed_max_abs",
        "joint_limit_minimum_margin_mixed_rad_m",
        "raw_numeric_min_eigenvalue",
        "raw_numeric_max_eigenvalue",
        "raw_numeric_condition_number",
    ):
        assert forbidden not in serialized
