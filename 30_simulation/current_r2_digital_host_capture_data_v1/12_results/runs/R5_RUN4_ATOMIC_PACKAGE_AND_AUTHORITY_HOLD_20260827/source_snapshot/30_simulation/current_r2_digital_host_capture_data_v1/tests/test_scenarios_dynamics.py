"""S02/S03 scenario tests for protocol revisions R3/R4."""

from dh_v1.scen_dynamics import (
    S02_THRESHOLDS,
    assess_s03_refinement,
    evaluate_s02_convergence,
    evaluate_s02_gates,
    run_s02_case,
    run_s03,
)


def _metrics(rel_h=1.0e-14, rel_E=1.0e-14):
    return {"rel_h_drift_max": rel_h, "rel_E_drift_max": rel_E}


def test_s02_arm_only_passes_with_floor_semantics(arm_plant):
    r = run_s02_case(
        arm_plant,
        "base_at_rest_arm_moving",
        t_end=2.0,
        dt=1.0e-3,
        convergence_dts=(4.0e-3, 2.0e-3, 1.0e-3),
    )
    assert r["all_gates_pass"], (r["gates"], r["convergence_mode"], r["rel_drift_by_dt"])
    assert r["convergence_mode"] in (
        "PASS_AT_ROUNDOFF_FLOOR",
        "PASS_ENTERED_ROUNDOFF_FLOOR",
        "ORDER_FIT",
    )
    assert r["dt_order_valid"] and r["dt_ratio_valid"]
    assert r["metrics"]["rel_h_drift_max"] < S02_THRESHOLDS["rel_h_drift_max"]


def test_s02_t1_all_values_at_roundoff_floor_uses_production_helper():
    r = evaluate_s02_convergence([5.0e-14, 9.0e-14, 2.0e-14], [4.0e-3, 2.0e-3, 1.0e-3])
    assert r["passed"]
    assert r["mode"] == "PASS_AT_ROUNDOFF_FLOOR"


def test_s02_t2_consistent_descent_into_roundoff_floor():
    r = evaluate_s02_convergence(
        [1.6716424721733281e-12, 1.0912256304802856e-13, 2.5788020545768352e-14],
        [4.0e-3, 2.0e-3, 1.0e-3],
    )
    assert r["passed"]
    assert r["mode"] == "PASS_ENTERED_ROUNDOFF_FLOOR"

    rebound = evaluate_s02_convergence([1.0e-10, 1.0e-13, 5.0e-10], [4.0e-3, 2.0e-3, 1.0e-3])
    assert not rebound["passed"]
    assert rebound["mode"] == "FAIL_NO_ORDER_EVIDENCE_ABOVE_FLOOR"


def test_s02_t3_order_fit_uses_actual_dt_ratio():
    r = evaluate_s02_convergence([1.6e-8, 1.0e-9, 6.25e-11], [4.0e-3, 2.0e-3, 1.0e-3])
    assert r["passed"]
    assert r["mode"] == "ORDER_FIT"
    assert r["observed_orders"] == [4.0, 4.0]


def test_s02_floor_rule_does_not_mask_real_drift():
    convergence = evaluate_s02_convergence([5.0e-14, 4.0e-14, 3.0e-14], [4.0e-3, 2.0e-3, 1.0e-3])
    result = evaluate_s02_gates(_metrics(rel_h=2.0e-9), 1.0e-14, convergence)
    assert convergence["passed"] and convergence["mode"] == "PASS_AT_ROUNDOFF_FLOOR"
    assert not result["gates"]["G_h_conservation"]
    assert not result["all_gates_pass"]


def test_s02_t5_each_hard_gate_has_priority_over_semantic_pass():
    convergence = evaluate_s02_convergence([5.0e-14, 4.0e-14, 3.0e-14], [4.0e-3, 2.0e-3, 1.0e-3])
    cases = [
        (_metrics(rel_h=2.0e-9), 1.0e-14, "G_h_conservation"),
        (_metrics(rel_E=2.0e-9), 1.0e-14, "G_E_conservation"),
        (_metrics(), 2.0e-8, "G_momentum_projection_xcheck"),
    ]
    for metrics, xcheck, expected_failure in cases:
        result = evaluate_s02_gates(metrics, xcheck, convergence)
        assert expected_failure in result["hard_gate_failures"]
        assert not result["all_gates_pass"]


def test_s03_t6_persistent_torque_saturation_never_becomes_complete_pass():
    runs = [
        {"dt_s": 1.0e-3, "any_saturation": True, "internal_torque_momentum_drift_abs": 1.0e-2},
        {"dt_s": 5.0e-4, "any_saturation": True, "internal_torque_momentum_drift_abs": 1.0e-13},
    ]
    result = assess_s03_refinement(runs)
    assert result["status"] == "RUN4_PHYSICAL_OR_CONTROL_SATURATION_CONFIRMED"
    assert not result["complete_scenario_pass"]
    assert not result["control_release"]


def test_s02_t7_dt_sequence_is_never_silently_sorted():
    reversed_order = evaluate_s02_convergence([6.25e-11, 1.0e-9, 1.6e-8], [1.0e-3, 2.0e-3, 4.0e-3])
    repeated_dt = evaluate_s02_convergence([1.6e-8, 1.0e-9, 6.25e-11], [4.0e-3, 2.0e-3, 2.0e-3])
    wrong_ratio = evaluate_s02_convergence([1.6e-8, 1.0e-9, 6.25e-11], [5.0e-3, 2.0e-3, 1.0e-3])
    assert reversed_order["mode"] == "FAIL_INVALID_DT_ORDER"
    assert repeated_dt["mode"] == "FAIL_INVALID_DT_ORDER"
    assert wrong_ratio["mode"] == "FAIL_INVALID_DT_RATIO"


def test_s02_insufficient_refinement_points_fail_closed():
    one_point = evaluate_s02_convergence([5.0e-14], [1.0e-3])
    two_points = evaluate_s02_convergence([1.0e-10, 6.25e-12], [2.0e-3, 1.0e-3])
    assert not one_point["passed"]
    assert not two_points["passed"]
    assert one_point["mode"] == "FAIL_INSUFFICIENT_REFINEMENT_POINTS"
    assert two_points["mode"] == "FAIL_INSUFFICIENT_REFINEMENT_POINTS"


def test_s02_informative_pair_cannot_mask_late_rebound():
    r = evaluate_s02_convergence(
        [1.6e-8, 1.0e-9, 1.0e-13, 5.0e-10],
        [8.0e-3, 4.0e-3, 2.0e-3, 1.0e-3],
    )
    assert not r["passed"]
    assert r["mode"] == "FAIL_NONMONOTONE_REFINEMENT"


def test_s03_nominal_dt_is_stable_and_conservative(arm_plant):
    """The local nominal-step smoke run stays diagnostic and unsaturated."""
    r = run_s03(arm_plant, t_end=3.0, dt=5.0e-4)
    r.pop("samples")
    assert r["internal_torque_momentum_drift_abs"] < 1e-9
    assert not r["any_saturation"]
    assert r["claim"] == "DIAGNOSTIC_ONLY_NOT_CONTROL_PASS"
