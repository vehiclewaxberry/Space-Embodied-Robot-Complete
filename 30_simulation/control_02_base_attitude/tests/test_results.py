"""Scientific result checks. Test PASS is not a substitute for the gate JSON."""
import json
from pathlib import Path

from config_loader import MODULE, load_config
from ledger import classify_attribution
from phase_b import frozen_legacy_region, physical_box_feasibility


RESULTS = MODULE / "results"


def _load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def test_stage_a_registered_scope_and_task_valid_a1():
    rows = _load("stage_a_summary.json")
    assert len(rows) == 8
    assert sum(r["evaluation_status"] == "EVALUATED" for r in rows) == 6
    a3 = [r for r in rows if r["controller"] == "A3_arm_wheel_thruster"]
    assert len(a3) == 2
    assert all(
        r["evaluation_status"]
        == "NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS"
        for r in a3
    )
    # R4 redesign: the two-segment A1 must complete the registered endpoint
    # exactly for both maneuvers.
    a1 = [r for r in rows if r["controller"] == "A1_reaction_trajectory"]
    assert all(r["method_result"] == "TASK_COMPLETED" for r in a1)
    assert all(r["task_endpoint_completed"] for r in a1)
    assert all(r["joint_endpoint_error_max_deg"] <= 1e-6 for r in a1)
    assert all(r["ee_endpoint_degradation_S_mm"] <= 1e-6 for r in a1)
    assert all(r["a1_design"]["segments"] == 2 for r in a1)
    return max(r["ee_endpoint_degradation_S_mm"] for r in a1)


def test_stage_a_conservation_and_physical_wheel_box():
    rows = [
        r
        for r in _load("stage_a_summary.json")
        if r["evaluation_status"] == "EVALUATED"
    ]
    worst = max(r["momentum_conservation_max_abs"] for r in rows)
    assert worst <= 1e-12
    a2 = [r for r in rows if r["controller"] == "A2_arm_wheel_coordination"]
    assert all(r["wheel_peak_axis_Nms"] <= 0.1 + 1e-12 for r in a2)
    assert all(not r["wheel_saturated"] for r in a2)
    m2 = [r for r in rows if r["maneuver"] == "M2_limit_compliant"]
    # R4 pre-registered interior start: the frozen 0.05 rad margin gate must
    # now hold on every realized M2 trajectory (A0/A1/A2).
    assert all(r["joint_limit_margin_min_rad"] >= 0.05 for r in m2)
    return worst


def test_stage_a_a2_reduces_both_maneuvers_by_half():
    rows = [
        r
        for r in _load("stage_a_summary.json")
        if r["evaluation_status"] == "EVALUATED"
    ]
    lookup = {(r["maneuver"], r["controller"]): r for r in rows}
    worst_shortfall = 0.0
    for maneuver in ("M1_headline", "M2_limit_compliant"):
        a0 = lookup[(maneuver, "A0_no_compensation")]["peak_base_dev_angle_deg"]
        a2 = lookup[(maneuver, "A2_arm_wheel_coordination")][
            "peak_base_dev_angle_deg"
        ]
        reduction = 1.0 - a2 / a0
        assert reduction >= 0.5
        worst_shortfall = max(worst_shortfall, 0.5 - reduction)
    return worst_shortfall


def test_stage_b_four_cases_four_controllers_and_labels():
    rows = _load("stage_b_summary.json")
    assert len(rows) == 16
    for row in rows:
        expected = classify_attribution(
            row["external_angular_impulse_vector_Nms"],
            row["wheel_h_final_Nms"],
            internal_motion=False,
            tolerance=1e-12,
        )
        assert row["attribution"] == expected
        assert max(abs(x) for x in row["wheel_h_final_Nms"]) <= 0.1 + 1e-12
        assert row["analysis_scope"] == "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY"
        assert (
            row["stability_status"]
            == "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS"
        )
    return max(r["capture_eps_H"] for r in rows)


def test_physical_box_uses_each_axis_not_legacy_scalar_norm():
    cfg = load_config()
    legacy_bad, _ = frozen_legacy_region(0.2, 0.0, cfg)
    physical_bad = physical_box_feasibility([0.2, 0.0, 0.0], cfg)
    h_good = [0.09, 0.09, 0.09]
    legacy_good, _ = frozen_legacy_region(
        sum(value * value for value in h_good) ** 0.5, 0.0, cfg
    )
    physical_good = physical_box_feasibility(h_good, cfg)

    # Both fit the historical ||H|| <= 0.3 scalar, proving that this legacy
    # cross-check cannot adjudicate the physical wheel box.
    assert legacy_bad == "WHEELS_ONLY_FEASIBLE"
    assert legacy_good == "WHEELS_ONLY_FEASIBLE"
    assert physical_bad["feasible"] is False
    assert physical_bad["axis_feasible"] == [False, True, True]
    assert physical_good["feasible"] is True
    assert physical_good["axis_feasible"] == [True, True, True]
    return min(physical_good["axis_margin_Nms"])


def test_stage_b_anchor_stays_out_of_region_and_is_counterfactual():
    rows = [r for r in _load("stage_b_summary.json") if r["case"] == "B_anchor"]
    assert len(rows) == 4
    assert all(r["domain_status"] == "OUT_OF_FEASIBLE_REGION" for r in rows)
    assert all(r["counterfactual_only"] for r in rows)
    return 0.0


def test_stage_b_independent_sim12_replay_is_exact():
    values = _load("sim12_independent_crosscheck.json")
    worst = max(
        max(v["H_diff_Nms"], v["rate_diff_dps"]) for v in values.values()
    )
    assert worst <= 1e-12
    return worst


def test_stage_b_expected_resource_outcomes():
    rows = _load("stage_b_summary.json")
    lookup = {(r["case"], r["controller"]): r for r in rows}
    assert (
        lookup[("A_low", "B1_wheel_storage")]["controller_outcome"]
        == "BODY_RATE_ZERO_WITH_MOMENTUM_STORED"
    )
    assert (
        lookup[("D_extreme", "B2_thruster_removal")]["controller_outcome"]
        == "EXTERNAL_BUDGET_EXHAUSTED"
    )
    assert lookup[("B_anchor", "B1_wheel_storage")]["wheel_saturated"] is True
    assert lookup[("B_anchor", "B3_wheel_thruster")]["wheel_saturated"] is True
    worst = max(r["external_ledger_closure_max_abs"] for r in rows)
    assert worst <= 1e-12
    return worst


def test_gate_vocabulary_review_and_claim_boundaries():
    gate = _load("control_02_gate_check.json")
    assert gate["verdict"] in ("PASS", "REPEAT", "BLOCKED")
    assert set(v["status"] for v in gate["gates"].values()) <= {
        "PASS",
        "REPEAT",
        "BLOCKED",
    }
    assert gate["review_status"] == "PENDING_REVIEW"
    assert gate["loop6_independent_red_team_complete"] is False
    assert gate["formal_safety_classification_emitted"] is False
    assert gate["scope_resolution"]["A3_verified"] is False
    assert gate["thresholds_widened"] is False
    # Pre-registered CTRL-02-R expectation: with the R4 task-valid trajectories
    # and the R5 transient layer, every machine gate must adjudicate PASS; any
    # deviation is a genuine REPEAT that must not be patched post hoc.
    assert gate["verdict"] == "PASS"
    gc1 = gate["gates"]["GC1_stage_A_anchor_and_reduction"]
    assert gc1["status"] == "PASS"
    assert gc1["M2_joint_limit_margin_min_rad"] >= 0.05
    assert gc1["A1_all_task_endpoints_completed"] is True
    assert len(gc1["A1_bounded_results"]) == 2
    assert all(
        result["task_endpoint_completed"] is True
        and result["all_completion_checks_pass"] is True
        for result in gc1["A1_bounded_results"]
    )
    assert gc1["M2_registered_start_deg"][1] == -15.0
    assert gc1["M2_registered_start_deg"][2] == -15.0
    # The withdrawn post-result probe must not have been reused.
    assert gc1["M2_registered_start_deg"][1] != -5.0
    assert gate["gates"]["GC7_transient_stability_window"]["status"] in (
        "PASS",
        "REPEAT",
    )
    return 0.0


def test_gc0_keeps_dimensionless_capture_and_nms_ledger_separate():
    gc0 = _load("control_02_gate_check.json")["gates"][
        "GC0_momentum_attribution"
    ]
    capture = gc0["capture_conservation_dimensionless"]
    ledger = gc0["external_angular_momentum_ledger_closure"]
    assert capture["unit"] == "1"
    assert "threshold_dimensionless" in capture
    assert ledger["unit"] == "N*m*s"
    assert "threshold_Nms" in ledger
    assert "B_conservation_max" not in gc0
    return max(capture["eps_H_max"], capture["eps_P_max"])
