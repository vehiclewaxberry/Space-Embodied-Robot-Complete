from __future__ import annotations

import pytest

from sim13_v4a.full_floating import deterministic_scenario, run_negative_controls


@pytest.fixture(scope="module")
def controls() -> dict[str, dict[str, object]]:
    model, service, _ = deterministic_scenario()
    return run_negative_controls(model, service)


@pytest.mark.parametrize(
    "control_id",
    (
        "NC-A01_BASE_LOCK",
        "NC-A02_MISSING_COUPLING_BLOCK",
        "NC-A03_RP_UNIT_SCALE",
        "NC-A04_INVALID_QUATERNION",
        "NC-A05_JACOBIAN_SIGN",
        "NC-A06_POINT_OFFSET",
    ),
)
def test_registered_mutation_is_detected(
    controls: dict[str, dict[str, object]], control_id: str
) -> None:
    control = controls[control_id]
    assert control["detected"] is True
    if control_id == "NC-A01_BASE_LOCK":
        limits = control["guard_thresholds"]
        assert control["free_linear_momentum_defect_n_s"] < limits["free_linear_max_n_s"]
        assert control["free_angular_momentum_defect_n_m_s"] < limits["free_angular_max_n_m_s"]
        assert control["locked_linear_momentum_defect_n_s"] > limits["locked_linear_min_n_s"]
        assert control["locked_angular_momentum_defect_n_m_s"] > limits["locked_angular_min_n_m_s"]
    elif control_id == "NC-A02_MISSING_COUPLING_BLOCK":
        assert control["direct_vs_mutated_energy_error_j"] > control["guard_threshold_min_j"]
    elif control_id in {"NC-A03_RP_UNIT_SCALE", "NC-A05_JACOBIAN_SIGN", "NC-A06_POINT_OFFSET"}:
        assert control["maximum_point_jacobian_error_mixed_units"] > control["guard_threshold_min_mixed_units"]
    else:
        assert control["injected_nonunit_norm_error"] > control["guard_threshold_max_unit_norm_error"]
        assert control["nan_rejected"] is True
        assert control["nonunit_rejected"] is True
