from __future__ import annotations

import numpy as np
import pytest

from b1_contact import ABORT_STATE, deterministic_contact_scenario, evaluate_contact, integrate_contact
from sim13_v4a.full_floating import ServiceState, TargetState


def test_nan_input_is_rejected_fail_closed():
    model, service, target, config = deterministic_contact_scenario()
    bad = ServiceState(service.base_position_inertial_m, service.base_quaternion_body_to_inertial_wxyz, service.joint_coordinates_mixed, service.nu_s_mixed.copy())
    bad.nu_s_mixed[0] = np.nan
    with pytest.raises(ValueError):
        evaluate_contact(model, bad, target, config)


def test_overpenetration_transitions_to_aborted_safe():
    model, service, target, config = deterministic_contact_scenario()
    pad, _, _ = model.point_position_and_jacobian(service, config.pad_link_index, config.pad_point_local_m)
    normal = np.array((0.91, -0.29, 0.29), dtype=float)
    normal /= np.linalg.norm(normal)
    target = TargetState(
        pad - (config.sphere_radius_m - 1.2 * config.max_penetration_abort_m) * normal,
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed,
    )
    history = integrate_contact(model, service, target, config, step_s=1.0e-4, duration_s=1.0e-4)
    assert history.aborted_safe
    assert history.state_label[-1] == ABORT_STATE
    assert any("OVERPENETRATION" in reason for reason in history.abort_reasons)
