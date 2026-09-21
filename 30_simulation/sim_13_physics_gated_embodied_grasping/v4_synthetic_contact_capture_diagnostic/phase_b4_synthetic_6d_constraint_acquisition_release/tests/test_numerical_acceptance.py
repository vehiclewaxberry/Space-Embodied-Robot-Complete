from __future__ import annotations


EXPECTED_CONTRACT_FREEZE_MUTATIONS = [
    "B4CFNC01_SOURCE_SHA_DRIFT",
    "B4CFNC02_TRIGGER_CHERRY_PICK",
    "B4CFNC03_B3_RANK6_REWRITE",
    "B4CFNC04_AXIAL_MISSING_WRENCH_MISFORMULA",
    "B4CFNC05_UNSCALED_MIXED_CONDITION",
    "B4CFNC06_CONTACT_CONSTRAINT_DOUBLE_ACTIVITY",
    "B4CFNC07_CONTACT_POTENTIAL_OMISSION",
    "B4CFNC08_NONZERO_REMOVAL_IMPULSE",
    "B4CFNC09_POST_REMOVAL_CONTACT_REACTIVATION",
    "B4CFNC10_CURRENT_OR_FORMAL_AUTHORITY_TRUE",
    "B4CFNC11_NULL_PHYSICAL_INPUT_ZERO_FILL",
    "B4CFNC12_SUCCESS_TERMINAL_ALIAS",
]

EXPECTED_FUTURE_SOLVER_CONTROLS = [
    "B4NC01_SOURCE_BYTE_SHA_DRIFT",
    "B4NC02_TRIGGER_INDEX_CHERRY_PICK",
    "B4NC03_DUPLICATE_JC_ROW_RANK5_WITH_PINV_ATTEMPT",
    "B4NC04_L_COLUMN_RANK_LOSS",
    "B4NC05_ACQUISITION_PINV_OR_LSTSQ_CALL",
    "B4NC06_REMOVE_LENGTH_SCALING_D_EQUALS_I",
    "B4NC07_MIXED_UNIT_CONDITION_NUMBER_REPORTED",
    "B4NC08_AXIAL_MISSING_WRENCH_MISFORMULA",
    "B4NC09_CONTACT_AND_CONSTRAINT_SIMULTANEOUSLY_ACTIVE",
    "B4NC10_CONTACT_POTENTIAL_OMITTED",
    "B4NC11_CONTACT_POTENTIAL_DOUBLE_COUNTED",
    "B4NC12_PROJECTION_DISSIPATION_SIGN_FLIP",
    "B4NC13_TARGET_CHILD_MASS_OMITTED",
    "B4NC14_TARGET_CHILD_MASS_DOUBLE_COUNTED",
    "B4NC15_ACTIVE_INTERMEDIATE_LEDGER_MUTATION_WITH_GOOD_TERMINAL_LABEL",
    "B4NC16_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST",
    "B4NC17_REMOVAL_ZEROES_TARGET_TWIST",
    "B4NC18_REMOVAL_RETURNS_DISSIPATED_ENERGY",
    "B4NC19_CLEARANCE_DWELL_NEGATIVE_GAP_INSERTION",
    "B4NC20_POST_REMOVAL_CONTACT_KERNEL_REACTIVATION",
    "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE",
    "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED",
]


def test_reference_anchors_recompute_exactly(numerical_contract: dict) -> None:
    anchors = numerical_contract["frozen_reference_anchors"]
    assert anchors["b3_reference_record_index"] == 205
    assert anchors["reference_length_m"] == 0.03999999992105392
    assert anchors["total_contact_elastic_energy_j"] == anchors["left_contact_elastic_energy_j"] + anchors["right_contact_elastic_energy_j"]


def test_rank_condition_and_solver_policy_are_numeric(numerical_contract: dict) -> None:
    rank = numerical_contract["rank_and_linear_solve"]
    assert rank["svd_relative_rank_tolerance"] == 1e-10
    assert rank["minimum_reference_length_m"] > 0.0
    assert rank["scaled_effective_mass_condition_number_max"] == 1e10
    assert rank["scaled_effective_mass_condition_number_definition"] == "kappa_2(W_bar)=lambda_max(W_bar)/lambda_min(W_bar) after proving W_bar symmetric positive definite"
    assert rank["condition_number_whitelist"] == ["W_bar_scaled"]
    assert {"explicit_matrix_inverse", "pinv", "lstsq"} <= set(rank["acquisition_solve_forbidden"])
    assert "cholesky_solve" not in rank["acquisition_solve_allowed"]["direct_symmetric_indefinite_kkt"]
    assert "pivoted_symmetric_ldlt_solve" in rank["acquisition_solve_allowed"]["direct_symmetric_indefinite_kkt"]


def test_pinv_is_whitelisted_only_for_rank5_audit(numerical_contract: dict) -> None:
    rank = numerical_contract["rank_and_linear_solve"]
    assert rank["pinv_whitelist"] == ["rank5_grasp_wrench_unreachable_projection_audit_only_after_rank_Gbar_equals_5"]


def test_native_unit_event_tolerances_are_positive_and_separate(numerical_contract: dict) -> None:
    tolerances = numerical_contract["event_local_native_unit_tolerances"]
    assert all(isinstance(value, (int, float)) and value > 0.0 for value in tolerances.values())
    assert tolerances["total_linear_momentum_jump_N_s"] == 1e-9
    assert tolerances["total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s"] == 1e-9


def test_active_trajectory_tolerances_cover_pose_twist_p_h_e_power_contact(numerical_contract: dict) -> None:
    active = numerical_contract["active_trajectory_native_unit_tolerances"]
    expected = {
        "pose_translation_m": 1e-9,
        "pose_rotation_geodesic_rad": 1e-9,
        "relative_linear_twist_m_s": 1e-9,
        "relative_angular_twist_rad_s": 1e-9,
        "total_linear_momentum_drift_N_s": 1e-9,
        "total_angular_momentum_drift_about_fixed_inertial_origin_N_m_s": 1e-9,
        "mechanical_energy_plus_all_dissipation_drift_J": 1e-7,
        "ideal_constraint_power_W": 1e-10,
        "contact_force_while_constraint_active_N": 1e-12,
        "contact_torque_while_constraint_active_N_m": 1e-12,
    }
    assert active == expected


def test_clearance_requires_positive_gap_and_rate_over_complete_dwell(numerical_contract: dict) -> None:
    removal = numerical_contract["removal_and_event_tolerances"]
    assert removal["clearance_gap_min_m"] > 0.0
    assert removal["gap_reentry_closing_speed_tolerance_m_s"] > 0.0
    assert "complete dwell" in removal["clearance_continuity_rule"]
    assert "endpoints alone are insufficient" in removal["clearance_continuity_rule"]


def test_rank_audit_uses_row_and_column_coordinate_scaling(numerical_contract: dict) -> None:
    scaling = numerical_contract["constraint_basis_scaling"]
    assert "diag(I3,L_ref*I3,L_ref*I6,I2)" in scaling["S_eta"]
    assert "block_diag(S_eta,I3,L_ref*I3)" in scaling["S_z"]
    assert scaling["identity"] == "J_hat*L_hat=0"
    assert "audit-only coordinate scalings" in scaling["use_boundary"]


def test_orientation_contract_freezes_quaternion_sign_and_pi_guard(numerical_contract: dict) -> None:
    orientation = numerical_contract["orientation_contract"]
    assert orientation["quaternion_order"] == "wxyz"
    assert "first nonzero xyz component is positive" in orientation["quaternion_sign_canonicalization"]
    assert "pi branch ambiguity" in orientation["so3_log_domain_guard"]


def test_fixed_negative_control_inventory_is_exact_22(numerical_contract: dict) -> None:
    controls = numerical_contract["future_solver_required_negative_control_ids"]
    assert controls == EXPECTED_FUTURE_SOLVER_CONTROLS


def test_contract_freeze_mutation_inventory_is_exact_12(numerical_contract: dict) -> None:
    controls = numerical_contract["contract_freeze_mutation_ids"]
    assert controls == EXPECTED_CONTRACT_FREEZE_MUTATIONS
