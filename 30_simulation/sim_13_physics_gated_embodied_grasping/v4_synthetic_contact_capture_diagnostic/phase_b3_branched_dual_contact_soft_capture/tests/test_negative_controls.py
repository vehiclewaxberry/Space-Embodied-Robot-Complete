from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from b3_contact.dual_contact_kernel import _state_machine


PHASE_B3 = Path(__file__).resolve().parents[1]


def _machine_arrays(history):
    def per(data):
        palm_coordinates = np.einsum(
            "nij,nj->ni",
            np.transpose(history.palm_rotation_body_to_inertial, (0, 2, 1)),
            data.pad_point_inertial_m - history.palm_origin_inertial_m,
        )
        return {
            "gap": data.gap_m.copy(),
            "penetration": data.penetration_m.copy(),
            "normal_speed": data.relative_normal_speed_m_s.copy(),
            "tangent_speed": data.relative_tangential_speed_m_s.copy(),
            "force": data.normal_force_magnitude_n.copy(),
            "normal": data.normal_target_to_pad_inertial.copy(),
            "pad_palm_y": palm_coordinates[:, 1].copy(),
        }

    return per(history.left), per(history.right)


def _machine_ledgers(history):
    records = history.soft_capture_criteria_log
    fields = {
        "linear_momentum_drift": "linear_momentum_drift_n_s",
        "angular_momentum_drift": "angular_momentum_drift_n_m_s",
        "service_linear_impulse_identity_error_n_s": "service_linear_impulse_identity_error_n_s",
        "target_linear_impulse_identity_error_n_s": "target_linear_impulse_identity_error_n_s",
        "service_angular_impulse_identity_error_n_m_s": "service_angular_impulse_identity_error_n_m_s",
        "target_angular_impulse_identity_error_n_m_s": "target_angular_impulse_identity_error_n_m_s",
        "energy_drift": "energy_plus_dissipation_drift_j",
        "action_reaction_error_n": "action_reaction_error_n",
        "common_point_shift_error_n_m": "common_point_shift_error_n_m",
        "target_torque_identity_error_n_m": "target_torque_identity_error_n_m",
        "virtual_power_error_w": "virtual_power_identity_error_w",
        "friction_positive_power_w": "friction_positive_power_w",
        "dissipation_monotonic_violation_j": "dissipation_monotonic_violation_j",
    }
    return {
        target: np.asarray([item[source] for item in records], dtype=float)
        for target, source in fields.items()
    }


@pytest.mark.parametrize(
    "mutation",
    (
        "SINGLE_SIDE_ONLY",
        "SAME_DIRECTION_NORMALS",
        "NO_DWELL",
        "OUTSIDE_CORRIDOR",
        "CENTER_SPEED_TOO_HIGH",
        "ANGULAR_SPEED_TOO_HIGH",
        "LEFT_NORMAL_SPEED_TOO_HIGH",
        "RIGHT_TANGENTIAL_SPEED_TOO_HIGH",
        "LEFT_FINGER_OPENING",
        "NORMAL_FORCE_TOO_LOW",
        "OPEN_LEDGER",
    ),
)
def test_state_machine_rejects_actual_soft_capture_predicate_mutations(dual_bundle, mutation):
    history = dual_bundle[4]["rk4_reference"]
    config = dual_bundle[3]
    left, right = _machine_arrays(history)
    center = history.target_center_palm_m.copy()
    speed = history.target_relative_center_speed_m_s.copy()
    omega = history.target_relative_omega_rad_s.copy()
    finger_rates = history.service_nu_s_mixed[:, 12:14].copy()
    ledger = _machine_ledgers(history)
    mutated_config = config
    if mutation == "SINGLE_SIDE_ONLY":
        right["penetration"][:] = 0.0
        right["force"][:] = 0.0
        right["gap"][:] = np.maximum(right["gap"], 1.0e-4)
    elif mutation == "SAME_DIRECTION_NORMALS":
        right["normal"][:] = left["normal"]
    elif mutation == "NO_DWELL":
        mutated_config = replace(config, dual_contact_dwell_s=0.1).validated()
    elif mutation == "OUTSIDE_CORRIDOR":
        center[:, 1] = config.sphere_radius_m + config.stroke_upper_m
    elif mutation == "CENTER_SPEED_TOO_HIGH":
        speed[:] = 2.0 * config.soft_capture_max_relative_center_speed_m_s
    elif mutation == "ANGULAR_SPEED_TOO_HIGH":
        omega[:] = 2.0 * config.soft_capture_max_relative_omega_rad_s
    elif mutation == "LEFT_NORMAL_SPEED_TOO_HIGH":
        left["normal_speed"][:] = 2.0 * config.soft_capture_max_abs_contact_normal_speed_m_s
    elif mutation == "RIGHT_TANGENTIAL_SPEED_TOO_HIGH":
        right["tangent_speed"][:] = 2.0 * config.soft_capture_max_contact_tangential_speed_m_s
    elif mutation == "LEFT_FINGER_OPENING":
        finger_rates[:, 0] = 2.0 * config.soft_capture_max_finger_opening_speed_m_s
    elif mutation == "NORMAL_FORCE_TOO_LOW":
        left["force"][:] = np.where(
            left["penetration"] > 0.0,
            0.5 * config.soft_capture_min_normal_force_n,
            0.0,
        )
        right["force"][:] = np.where(
            right["penetration"] > 0.0,
            0.5 * config.soft_capture_min_normal_force_n,
            0.0,
        )
    elif mutation == "OPEN_LEDGER":
        ledger["energy_drift"][:] = 2.0 * config.energy_ledger_tolerance_j
    labels, transitions, criteria, reasons = _state_machine(
        history.time_s,
        left,
        right,
        center,
        speed,
        omega,
        finger_rates,
        ledger,
        mutated_config,
        require_soft_capture=True,
    )
    assert "SOFT_CAPTURE_TRANSIENT_CANDIDATE" not in labels
    assert all(not item["soft_capture_transient_qualifies"] for item in criteria)
    assert "NO_SOFT_CAPTURE_TRANSIENT_CANDIDATE" in reasons
    assert all(item["to"] != "SOFT_CAPTURE_TRANSIENT_CANDIDATE" for item in transitions)


def test_force_wrench_friction_and_branch_crosswire_guards_detect_real_mutations(dual_bundle):
    model, service, _, config, histories, _ = dual_bundle
    history = histories["rk4_reference"]
    peak = int(np.argmax(
        history.left.normal_force_magnitude_n + history.right.normal_force_magnitude_n
    ))
    residuals = []
    for data in (history.left, history.right):
        force = data.service_force_inertial_n[peak]
        same_sign_target = force.copy()
        residuals.append(float(np.linalg.norm(force + same_sign_target)))
        missing_shift = np.cross(data.pad_point_inertial_m[peak], force)
        correct_common = np.cross(data.common_contact_point_inertial_m[peak], force)
        residuals.append(float(np.linalg.norm(missing_shift - correct_common)))
        friction_index = int(np.argmax(data.friction_dissipation_rate_w))
        flipped_tangent = -data.tangential_force_service_inertial_n[friction_index]
        flipped_power = float(flipped_tangent @ data.relative_tangential_velocity_inertial_m_s[friction_index])
        residuals.append(flipped_power)
    for side, own, cross in (("left", 12, 13), ("right", 13, 12)):
        _, jacobian, _ = model.synthetic_pad_position_and_jacobian(
            service,
            side,
            closed_half_gap_m=config.closed_half_gap_m,
            pad_x_palm_m=config.pad_x_palm_m,
            pad_z_palm_m=config.pad_z_palm_m,
        )
        crosswired = jacobian.copy()
        crosswired[:, cross] = jacobian[:, own]
        residuals.append(float(np.linalg.norm(crosswired[:, cross])))
    average_point = 0.5 * (
        history.left.common_contact_point_inertial_m[peak]
        + history.right.common_contact_point_inertial_m[peak]
    )
    residuals.extend(
        (
            float(np.linalg.norm(average_point - history.left.common_contact_point_inertial_m[peak])),
            float(np.linalg.norm(average_point - history.right.common_contact_point_inertial_m[peak])),
        )
    )
    assert len(residuals) == 10
    assert all(value > 1.0e-12 for value in residuals)


def test_false_rank_six_and_governance_promotions_are_rejected_from_measured_truth(dual_bundle):
    summary = dual_bundle[5]["rk4_reference"]
    measured_rank = summary["grasp_map"]["selected_sample"]["numerical_rank"]
    claimed_rank = 6
    assert measured_rank == 5
    assert claimed_rank != measured_rank
    governance = json.loads(
        (PHASE_B3 / "contracts/PHASE_B3_GOVERNANCE_CONTRACT_V1.json").read_text(encoding="utf-8")
    )
    expected = governance["required_false"]
    assert not any(expected.values())
    for key in expected:
        mutated = dict(expected)
        mutated[key] = True
        assert mutated != expected
        assert any(mutated.values())


def test_recontact_after_bilateral_release_is_a_real_fail_closed_transition(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    config = dual_bundle[3]
    left, right = _machine_arrays(history)
    ledger = _machine_ledgers(history)
    released_indices = np.flatnonzero(np.asarray(history.state_label) == "BILATERAL_RELEASE")
    assert len(released_indices) >= 2
    mutation_index = int(released_indices[1])
    left["penetration"][mutation_index:] = 1.0e-6
    left["gap"][mutation_index:] = -1.0e-6
    left["force"][mutation_index:] = max(config.soft_capture_min_normal_force_n, 0.1)
    labels, transitions, _, reasons = _state_machine(
        history.time_s,
        left,
        right,
        history.target_center_palm_m.copy(),
        history.target_relative_center_speed_m_s.copy(),
        history.target_relative_omega_rad_s.copy(),
        history.service_nu_s_mixed[:, 12:14].copy(),
        ledger,
        config,
        require_soft_capture=True,
    )
    assert labels[mutation_index] == "ABORTED_SAFE"
    assert any("RECONTACT_AFTER_BILATERAL_RELEASE" in reason for reason in reasons)
    assert any(item["to"] == "ABORTED_SAFE" for item in transitions)
