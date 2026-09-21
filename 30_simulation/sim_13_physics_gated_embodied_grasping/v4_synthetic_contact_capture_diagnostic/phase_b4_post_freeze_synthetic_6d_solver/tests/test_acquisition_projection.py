from __future__ import annotations

import numpy as np
import pytest


def test_frozen_trigger_is_first_qualifying_record(primary_event):
    assert primary_event.index == 205
    assert primary_event.time_s == 0.051250000000000004
    assert primary_event.criteria["soft_capture_transient_qualifies"] is True
    assert primary_event.criteria["all_ledgers_closed"] is True


def test_snapshot_translation_anchor(primary_acquisition):
    np.testing.assert_allclose(
        primary_acquisition.snapshot.translation_palm_to_target_m,
        [-0.019999987423206113, 1.0174776715202519e-6, -2.5124426879623296e-6],
        atol=1.0e-14, rtol=0.0,
    )


def test_reference_length_anchor(primary_acquisition):
    assert abs(primary_acquisition.reference_length_m - 0.03999999992105392) <= 1.0e-14


@pytest.mark.parametrize("name,shape", [
    ("M_minus", (20, 20)), ("M_attached", (14, 14)), ("A", (6, 14)),
    ("L", (20, 14)), ("J_c", (6, 20)), ("D", (6, 6)),
    ("J_bar", (6, 20)), ("S_eta", (14, 14)), ("S_z", (20, 20)),
    ("L_hat", (20, 14)), ("J_hat", (6, 20)), ("W_bar", (6, 6)),
    ("G_bar", (6, 6)),
])
def test_matrix_shape_is_exact(name, shape, primary_acquisition):
    assert primary_acquisition.matrices[name].shape == shape


def test_constraint_embedding_identity_is_exact(primary_acquisition):
    residual = primary_acquisition.matrices["J_c"] @ primary_acquisition.matrices["L"]
    assert np.linalg.norm(residual, ord=np.inf) == 0.0


@pytest.mark.parametrize("name,expected", [("L_hat", 14), ("J_hat", 6), ("G_bar", 5)])
def test_scaled_rank_is_frozen(name, expected, primary_acquisition):
    assert primary_acquisition.ranks[name] == expected


@pytest.mark.parametrize("metric,tolerance", [
    ("snapshot_translation_identity_m", 1.0e-12),
    ("snapshot_rotation_geodesic_rad", 1.0e-12),
    ("rotation_orthogonality_inf", 1.0e-12),
    ("rotation_determinant_error_abs", 1.0e-12),
    ("quaternion_unit_norm_error_abs", 1.0e-12),
    ("Jhat_Lhat_operator_inf_dimensionless", 1.0e-11),
    ("reduced_kkt_service_base_linear_component_m_s", 1.0e-10),
    ("reduced_kkt_service_base_angular_component_rad_s", 1.0e-10),
    ("reduced_kkt_R_joint_component_rad_s", 1.0e-10),
    ("reduced_kkt_P_joint_component_m_s", 1.0e-10),
    ("reduced_kkt_target_linear_component_m_s", 1.0e-10),
    ("reduced_kkt_target_angular_component_rad_s", 1.0e-10),
    ("post_constraint_linear_twist_m_s", 1.0e-10),
    ("post_constraint_angular_twist_rad_s", 1.0e-10),
    ("combined_impulse_equation_service_base_linear_N_s", 1.0e-9),
    ("combined_impulse_equation_service_base_angular_N_m_s", 1.0e-9),
    ("combined_impulse_equation_R_joint_N_m_s", 1.0e-9),
    ("combined_impulse_equation_P_joint_N_s", 1.0e-9),
    ("combined_impulse_equation_target_linear_N_s", 1.0e-9),
    ("combined_impulse_equation_target_angular_N_m_s", 1.0e-9),
    ("total_linear_momentum_jump_N_s", 1.0e-9),
    ("total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s", 1.0e-9),
    ("projection_energy_identity_J", 1.0e-9),
    ("switch_energy_identity_J", 1.0e-9),
    ("contact_potential_sum_identity_J", 1.0e-12),
    ("attached_mass_fixed_child_inf", 1.0e-10),
])
def test_each_event_metric_uses_its_native_unit_tolerance(metric, tolerance, primary_acquisition):
    assert primary_acquisition.metrics[metric] <= tolerance


def test_scaled_effective_mass_is_spd_and_conditioned(primary_acquisition):
    assert primary_acquisition.metrics["W_bar_scaled_min_eigenvalue"] > 0.0
    assert primary_acquisition.metrics["W_bar_scaled_condition_number"] <= 1.0e10


def test_projection_dissipation_is_nonnegative(primary_acquisition):
    assert primary_acquisition.energy_audit["D_projection_J"] >= -1.0e-12


def test_contact_potential_is_counted_once(primary_acquisition):
    energy = primary_acquisition.energy_audit
    assert energy["U_contact_minus_J"] == energy["U_left_minus_J"] + energy["U_right_minus_J"]
    assert energy["D_switch_J"] == energy["D_projection_J"] + energy["U_contact_minus_J"]


def test_missing_wrench_scalar_uses_full_rank5_formula(primary_acquisition):
    audit = primary_acquisition.wrench_audit
    assert np.isfinite(audit["rank5_unreachable_chi_missing_N_m_s"])
    assert audit["rank5_contact_capability_attributed"] is False
    assert audit["synthetic_sixth_constraint_attributed"] is True


def test_transverse_angular_impulse_is_a_three_vector(primary_acquisition):
    value = primary_acquisition.wrench_audit["transverse_angular_impulse_N_m_s"]
    assert len(value) == 3


def test_service_equivalent_wrench_counts_r_cross_p_once(primary_acquisition):
    wrench = primary_acquisition.momentum_audit["service_equivalent_wrench_about_palm_origin"]
    assert wrench["r_cross_p_count"] == 1


def test_acquisition_never_uses_pinv_or_lstsq(primary_acquisition):
    provenance = primary_acquisition.backend_provenance
    assert provenance["acquisition_pinv_or_lstsq"] == "FORBIDDEN_NOT_USED"
    assert provenance["pinv_whitelist"] == "G_BAR_RANK5_UNREACHABLE_PROJECTION_AUDIT_ONLY"

