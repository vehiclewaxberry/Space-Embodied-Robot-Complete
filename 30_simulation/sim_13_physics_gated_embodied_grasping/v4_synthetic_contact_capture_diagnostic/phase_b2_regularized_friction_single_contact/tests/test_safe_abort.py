from __future__ import annotations

import numpy as np
import pytest

from b1_contact.contact_kernel import ContactError
from b2_contact import deterministic_friction_scenario, evaluate_friction_contact, integrate_friction_contact
from sim13_v4a.full_floating import TargetState


def test_nan_target_fails_closed():
    model, service, target, config = deterministic_friction_scenario()
    bad = TargetState(target.position_inertial_m * np.nan, target.quaternion_body_to_inertial_wxyz, target.twist_inertial_mixed)
    with pytest.raises((ContactError, ValueError)):
        evaluate_friction_contact(model, service, bad, config)


def test_unknown_integrator_fails_closed():
    model, service, target, config = deterministic_friction_scenario()
    history = integrate_friction_contact(
        model, service, target, config,
        step_s=5.0e-4, duration_s=5.0e-4, method="bogus",
    )
    assert history.aborted_safe
    assert any("INTEGRATION_FAILURE" in item for item in history.abort_reasons)


def test_initial_overpenetration_aborts_safe():
    model, service, target, config = deterministic_friction_scenario()
    pad = model.point_position_and_jacobian(service, config.pad_link_index, config.pad_point_local_m)[0]
    normal = pad - target.position_inertial_m
    normal /= np.linalg.norm(normal)
    bad_target = TargetState(
        pad - (config.sphere_radius_m - 1.2 * config.max_penetration_abort_m) * normal,
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed,
    )
    history = integrate_friction_contact(
        model, service, bad_target, config,
        step_s=5.0e-4, duration_s=1.0e-3,
    )
    assert history.aborted_safe
    assert "ABORTED_SAFE" in history.state_label
