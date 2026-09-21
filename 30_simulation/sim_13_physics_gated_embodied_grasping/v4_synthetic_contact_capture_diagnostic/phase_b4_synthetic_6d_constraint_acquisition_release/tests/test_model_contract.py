from __future__ import annotations


def test_snapshot_transform_freezes_current_pose_without_physical_alias(model_contract: dict) -> None:
    snapshot = model_contract["synthetic_snapshot_transform"]
    assert snapshot["name"] == "T_PALM_TARGET_SNAPSHOT_SYNTHETIC"
    assert snapshot["frozen_at_event"] is True
    assert snapshot["physical_lock_transform"] is False
    assert "T_gripper_target_locked" in snapshot["forbidden_aliases"]


def test_combined_and_attached_dimensions_are_exact(model_contract: dict) -> None:
    assert model_contract["pre_event_state"]["dimension"] == 20
    attached = model_contract["attached_subspace"]
    assert attached["embedding_shape"] == [20, 14]
    assert attached["constraint_shape"] == [6, 20]
    assert attached["required_rank"] == 6
    assert attached["required_identity"] == "J_c*L=0"


def test_target_twist_mapping_contains_offset_cross_product(model_contract: dict) -> None:
    mapping = model_contract["attached_subspace"]["target_twist_mapping"]
    assert "omega_target=omega_palm" in mapping
    assert "omega_palm cross r" in mapping
    assert "r=r_target_com-r_palm" in mapping


def test_projection_is_plastic_and_dual_path(model_contract: dict) -> None:
    projection = model_contract["acquisition_impulse_projection"]
    assert projection["impact_type"] == "perfectly_inelastic_ideal_constraint_acquisition"
    assert projection["restitution"] == 0.0
    assert "eta_plus=" in projection["primary_reduced_solution"]
    assert "[z_plus_kkt;lambda_bar]" in projection["independent_kkt_solution"]
    assert "without forming a Schur complement" in projection["independent_kkt_solution"]
    assert projection["required_dissipation_nonnegative"] is True


def test_projection_uses_dimensioned_scaling_without_raw_six_norm(model_contract: dict) -> None:
    projection = model_contract["acquisition_impulse_projection"]
    assert "D=diag(I_3,L_ref*I_3)" in projection["scaling"]
    assert projection["six_vector_raw_norm_forbidden"] is True
    assert projection["unscaled_mixed_unit_condition_number_forbidden"] is True
    assert projection["pseudoinverse_to_hide_rank_loss"] == "forbidden"


def test_reference_length_is_positive_contact_chord_scale(model_contract: dict) -> None:
    projection = model_contract["acquisition_impulse_projection"]
    assert projection["reference_length"] == "L_ref=0.5*norm(p_contact_right-p_contact_left) at t_a"
    assert projection["required_reference_length_positive"] is True


def test_synthetic_axial_couple_is_not_attributed_to_b3(model_contract: dict) -> None:
    semantics = model_contract["wrench_and_momentum_semantics"]
    assert "ell-r_left cross p" in semantics["synthetic_missing_sixth_wrench_scalar"]
    assert "chi_missing=0" in semantics["rank5_identity"]
    assert "not generally the rank5-unreachable scalar" in semantics["ordinary_angular_impulse_projection"]
    assert "synthetic sixth constraint" in semantics["attribution"]
    assert "audit decomposition only" in semantics["normalized_rank5_unreachable_projection"]


def test_service_impulse_includes_offset_moment(model_contract: dict) -> None:
    semantics = model_contract["wrench_and_momentum_semantics"]
    assert "ell+r_cross_p" in semantics["service_equivalent_wrench_about_palm_origin"]
    assert "shall not be added a second time" in semantics["service_equivalent_wrench_about_palm_origin"]
    assert semantics["linear_impulse_pair_sum"] == "zero N*s"
    assert semantics["angular_impulse_pair_about_same_inertial_origin"] == "zero N*m*s"


def test_contact_energy_is_absorbed_not_deleted_or_double_counted(model_contract: dict) -> None:
    switch = model_contract["contact_to_constraint_switch"]
    assert switch["b3_contact_force_after_acquisition"] == "disabled while synthetic constraint is active"
    assert switch["double_counting_contact_and_constraint"] == "forbidden"
    assert switch["reference_total_contact_potential_at_t_a_minus_j"] == switch["reference_left_contact_potential_at_t_a_minus_j"] + switch["reference_right_contact_potential_at_t_a_minus_j"]
    assert switch["contact_potential_sum"] == "U_contact_minus=U_left_minus+U_right_minus with each side counted exactly once"
    assert switch["projection_dissipation"] == "D_projection=T_minus-T_plus"
    assert switch["switch_dissipation"] == "D_switch=D_projection+U_left_minus+U_right_minus"
    assert switch["full_event_energy_identity"] == "T_plus+D_B3_minus+D_switch=T_minus+U_left_minus+U_right_minus+D_B3_minus"
    assert switch["energy_deletion"] == "forbidden"


def test_active_model_includes_target_inertia_and_recomputes_bias(model_contract: dict) -> None:
    active = model_contract["active_constraint_propagation"]
    assert active["state_dimension"] == 14
    assert "target child body" in active["mass_matrix"]
    assert "M_combined*L_dot*eta" in active["bias"]
    assert "independently agrees" in active["bias"]
    assert active["ideal_constraint_power"] == "zero"


def test_removal_is_velocity_continuous_zero_impulse_and_zero_stored_energy(model_contract: dict) -> None:
    removal = model_contract["release_contract"]
    assert "z_after=z_before" in removal["release_mapping"]
    assert removal["release_impulse_linear_N_s"] == 0.0
    assert removal["release_impulse_angular_N_m_s"] == 0.0
    assert removal["ideal_constraint_stored_energy_J"] == 0.0


def test_contact_kernel_stays_off_after_removal_in_main_branch(model_contract: dict) -> None:
    removal = model_contract["release_contract"]
    assert "remain disabled" in removal["contact_kernel_after_removal"]
    assert "g_clearance_min" in removal["recontact_rule"]
    assert "separate preregistered re-contact" in removal["future_contact_reactivation"]


def test_removal_uses_first_complete_eligible_dwell_without_cherry_pick(model_contract: dict) -> None:
    removal = model_contract["release_contract"]
    assert "tau_c=inf" in removal["earliest_eligible_event_rule"]
    assert "t_r=tau_c+clearance_dwell_s" in removal["earliest_eligible_event_rule"]
    assert "unique earliest finite t_r" in removal["event_selection"]
    assert removal["empty_eligibility_set"] == "DIAGNOSTIC_FAIL_CLOSED_NO_REMOVAL_EVENT"
    assert "independently located earliest t_r" in removal["cross_integrator_removal_event_definition"]


def test_terminal_label_alone_has_zero_gate_value(model_contract: dict) -> None:
    machine = model_contract["state_machine"]
    assert machine["success_label"] == "none"
    assert "terminal label alone has zero Gate value" in machine["qualification_rule"]
    assert "GRASP_SUCCESS" in machine["forbidden_states"]
    assert "NC19_PASS" in machine["forbidden_states"]


def test_fail_closed_inventory_covers_core_physics_mutations(model_contract: dict) -> None:
    joined = "\n".join(model_contract["fail_closed_conditions"])
    for token in (
        "rank(L_hat) not 14",
        "rank(J_hat) not 6",
        "J_hat*L_hat residual above tolerance",
        "scaled effective mass W_bar",
        "reduced and KKT projections disagree",
        "contact elastic potential omitted",
        "simultaneously active",
        "nonzero release impulse",
        "contact-kernel reactivation",
        "forbidden state authorization",
    ):
        assert token in joined
