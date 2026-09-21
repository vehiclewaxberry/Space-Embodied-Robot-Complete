from __future__ import annotations

import numpy as np
import pytest

from b3_contact.dual_contact_kernel import evaluate_dual_contact, integrate_dual_contact
from sim13_v4a.full_floating import TargetState


def test_nonfinite_target_is_rejected_before_contact_evaluation(dual_scenario):
    model, service, target, config = dual_scenario
    bad_target = TargetState(
        target.position_inertial_m * np.nan,
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed,
    )
    with pytest.raises(ValueError):
        evaluate_dual_contact(model, service, bad_target, config)


def test_unknown_integrator_fails_closed(dual_scenario):
    model, service, target, config = dual_scenario
    history = integrate_dual_contact(
        model,
        service,
        target,
        config,
        step_s=5.0e-4,
        duration_s=5.0e-4,
        method="unknown-integrator",
    )
    assert history.aborted_safe
    assert history.state_label[-1] == "ABORTED_SAFE"
    assert any("INTEGRATION_FAILURE" in reason for reason in history.abort_reasons)


def test_initial_overpenetration_fails_closed(dual_scenario):
    model, service, target, config = dual_scenario
    left_pad = model.synthetic_pad_position_and_jacobian(
        service,
        "left",
        closed_half_gap_m=config.closed_half_gap_m,
        pad_x_palm_m=config.pad_x_palm_m,
        pad_z_palm_m=config.pad_z_palm_m,
    )[0]
    normal = left_pad - target.position_inertial_m
    normal /= np.linalg.norm(normal)
    penetration = 1.2 * config.max_penetration_abort_m
    bad_target = TargetState(
        left_pad - (config.sphere_radius_m - penetration) * normal,
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed,
    )
    with pytest.raises(ValueError, match="INITIAL_GEOMETRY_NOT_BILATERALLY_SEPARATED"):
        integrate_dual_contact(
            model,
            service,
            bad_target,
            config,
            step_s=1.0e-4,
            duration_s=1.0e-4,
        )


def test_required_soft_capture_missing_is_not_silently_accepted(dual_scenario):
    model, service, target, config = dual_scenario
    history = integrate_dual_contact(
        model,
        service,
        target,
        config,
        step_s=5.0e-4,
        duration_s=1.0e-3,
        require_soft_capture=True,
    )
    assert history.aborted_safe
    assert history.state_label[-1] == "ABORTED_SAFE"
    assert "NO_SOFT_CAPTURE_TRANSIENT_CANDIDATE" in history.abort_reasons
