from __future__ import annotations

import math

import pytest

from r2_preflight.evaluator import (
    evaluate_common_propagation_triplet,
    evaluate_fresh_acquisition_triplet,
    validate_g04_signature_match,
)
from r2_preflight.metrics import (
    COMMON_PROP_CHANNELS,
    FRESH_ACQ_CHANNELS,
    MIDPOINT_CONTRACTION,
    evaluate_direct_order_triplet,
    stable_quaternion_geodesic_rad,
)
from r2_preflight.negative_controls import _g04_inputs, _g06_inputs
from r2_preflight.strict_json import canonical_sha256
from r2_preflight.work_energy import G06_LIMIT_J, WorkEnergyError, evaluate_g04, evaluate_g06, runner_g04_signature


def test_exact_channel_maps_and_midpoint_factor() -> None:
    assert canonical_sha256(COMMON_PROP_CHANNELS) == "73090EBF1735D259BA84E7617D1978C3C6E910445E7EBE3A15BDDC2987E9103B"
    assert canonical_sha256(FRESH_ACQ_CHANNELS) == "6E93A390D5DD1A6838A1217A3B262260DC87E995D20932515CB9F66986299BC9"
    assert MIDPOINT_CONTRACTION == 2.0 ** -1.8


def test_empty_sixteen_channel_histories_never_pass() -> None:
    fresh = {name: ([], [], []) for name in FRESH_ACQ_CHANNELS}
    common = {name: ([], [], []) for name in COMMON_PROP_CHANNELS}
    assert evaluate_fresh_acquisition_triplet((0.0, 0.0, 0.0), fresh)["passed"] is False
    assert evaluate_common_propagation_triplet(
        "rk4", common, time_grids_s=([0.0], [0.0], [0.0]), command_duration_s=0.005
    )["passed"] is False


def test_quaternion_sign_shape_norm_boundary_and_nontrivial_angle() -> None:
    assert stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0])["distance_rad"] == 0.0
    assert stable_quaternion_geodesic_rad([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is False
    inside = math.nextafter(1.0 + 1e-12, 1.0)
    outside = math.nextafter(1.0 + 1e-12, math.inf)
    assert stable_quaternion_geodesic_rad([inside, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is True
    assert stable_quaternion_geodesic_rad([outside, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is False
    result = stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0])
    assert math.isclose(result["distance_rad"], math.pi / 2.0, abs_tol=1e-15)


@pytest.mark.parametrize(
    ("errors", "scope", "passed", "category"),
    [
        ([1e-12, 1e-12, 1e-12], "ALL_THREE", True, "OVERALL_FLOOR_RESOLVED"),
        ([1e-12, 2e-10, 1e-11], "ALL_THREE", False, "PAIRWISE_ORDER_FAIL"),
        ([1e-8, 0.0, 0.0], "FINE_AND_REFERENCE", True, "OVERALL_FLOOR_RESOLVED"),
        ([1e-8, 2e-9, 5e-10], "ALL_THREE", True, "PAIRWISE_ORDER_PASS"),
        ([1e-8, float("inf"), 1e-10], "ALL_THREE", False, "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA"),
    ],
)
def test_total_order_truth_table(errors, scope, passed, category) -> None:
    result = evaluate_direct_order_triplet(errors, floor_J=1e-10, p_min=1.8, floor_scope=scope)
    assert result["passed"] is passed
    assert result["category"] == category


def test_g04_valid_and_empty_or_singleton_histories_fail_closed() -> None:
    valid = _g04_inputs()
    assert evaluate_g04(**valid)["scientific_predicate"] is True
    singleton = _g04_inputs()
    for key in ("time_s", "command_Q_14", "service_state_29", "sample_power_reported_W", "W_act_J"):
        singleton[key] = singleton[key][:1]
    with pytest.raises(WorkEnergyError, match="AT_LEAST_TWO"):
        evaluate_g04(**singleton)
    empty_stage = _g04_inputs()
    for key in ("stage_command_Q_14", "stage_service_state_29", "stage_power_reported_W"):
        empty_stage[key] = []
    with pytest.raises(WorkEnergyError, match="NONEMPTY_STAGE"):
        evaluate_g04(**empty_stage)
    empty_post = _g04_inputs(); empty_post["post_W_act_J"] = []; empty_post["post_generalized_force_Q_14"] = []
    with pytest.raises(WorkEnergyError, match="NONEMPTY_ALIGNED_POST"):
        evaluate_g04(**empty_post)


def test_g04_runner_validator_independent_signature() -> None:
    signature = runner_g04_signature()
    assert validate_g04_signature_match(signature)
    signature["required_fields"].pop()
    assert not validate_g04_signature_match(signature)


def test_g06_stage_recurrence_and_threshold_boundaries() -> None:
    exact = evaluate_g06(**_g06_inputs(kinetic=[0.0, G06_LIMIT_J]))
    over = evaluate_g06(**_g06_inputs(kinetic=[0.0, math.nextafter(G06_LIMIT_J, math.inf)]))
    copied = evaluate_g06(**_g06_inputs(kinetic=[0.0, 1.0], work=[0.0, 1.0]))
    assert exact["scientific_predicate"] is True
    assert over["scientific_predicate"] is False
    assert copied["scientific_predicate"] is False
    assert copied["independent_work_state_provenance_pass"] is False


def test_g06_single_point_rejected() -> None:
    value = _g06_inputs()
    value["total_kinetic_energy_J"] = [0.0]
    value["signed_W_act_J"] = [0.0]
    with pytest.raises(WorkEnergyError, match="HISTORY_LENGTH"):
        evaluate_g06(**value)
