"""CTRL-02 GC0-GC6 fail-closed machine adjudication."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from config_loader import MODULE, load_config
from ledger import classify_attribution
from phase_a import run_phase_a
from phase_b import run_phase_b
from run_experiments import run_all
from transient_b import run_transient


RESULTS = MODULE / "results"
GATE_PATH = RESULTS / "control_02_gate_check.json"


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _status(condition: bool) -> str:
    return "PASS" if condition else "REPEAT"


def _write(value) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    with GATE_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _blocked(reason: str) -> dict:
    out = {
        "schema_version": "control02-gate-v3",
        "task_id": "CTRL-02",
        "verdict": "BLOCKED",
        "blocked_reason": reason,
        "review_status": "PENDING_REVIEW",
        "formal_safety_classification_emitted": False,
    }
    _write(out)
    return out


def independent_propellant_audit(stage_b: list[dict], cfg: dict) -> dict:
    """Recompute the ideal propellant lower bound without upstream helpers.

    The calculation starts from each row's external angular-impulse vector and
    the frozen lever arm, Isp, and g0.  It deliberately does not trust the
    reported scalar angular impulse, total impulse, propellant, or any
    precomputed margin.
    """
    lever_m = float(cfg["stage_b"]["lever_arm_m"])
    isp_s = float(cfg["stage_b"]["isp_s"])
    g0_mps2 = float(cfg["stage_b"]["g0_mps2"])
    tolerance = float(cfg["gates"]["conservation_abs"])
    audits = []
    for row in stage_b:
        external_vector = np.asarray(
            row["external_angular_impulse_vector_Nms"], dtype=float
        )
        expected_angular_Nms = float(np.linalg.norm(external_vector))
        expected_impulse_Ns = expected_angular_Nms / lever_m
        expected_propellant_g = (
            1000.0 * expected_impulse_Ns / (isp_s * g0_mps2)
        )
        angular_diff = abs(
            float(row["external_angular_impulse_Nms"]) - expected_angular_Nms
        )
        impulse_diff = abs(
            float(row["thruster_total_impulse_Ns"]) - expected_impulse_Ns
        )
        propellant_diff = abs(
            float(row["propellant_g"]) - expected_propellant_g
        )
        passed = (
            angular_diff <= tolerance
            and impulse_diff <= tolerance
            and propellant_diff <= tolerance
        )
        audits.append(
            {
                "case": row["case"],
                "controller": row["controller"],
                "expected_external_angular_impulse_Nms": expected_angular_Nms,
                "reported_external_angular_impulse_Nms": float(
                    row["external_angular_impulse_Nms"]
                ),
                "angular_impulse_abs_difference_Nms": angular_diff,
                "expected_thruster_total_impulse_Ns": expected_impulse_Ns,
                "reported_thruster_total_impulse_Ns": float(
                    row["thruster_total_impulse_Ns"]
                ),
                "thruster_impulse_abs_difference_Ns": impulse_diff,
                "independent_propellant_lower_bound_g": expected_propellant_g,
                "reported_propellant_g": float(row["propellant_g"]),
                "reported_minus_lower_bound_g": float(row["propellant_g"])
                - expected_propellant_g,
                "propellant_abs_difference_g": propellant_diff,
                "pass": passed,
            }
        )
    return {
        "method": (
            "norm(external_angular_impulse_vector_Nms) / lever_arm_m / "
            "(isp_s * g0_mps2) * 1000"
        ),
        "inputs": {
            "lever_arm_m": lever_m,
            "isp_s": isp_s,
            "g0_mps2": g0_mps2,
        },
        "comparison_thresholds": {
            "angular_impulse_Nms": tolerance,
            "thruster_impulse_Ns": tolerance,
            "propellant_g": tolerance,
        },
        "all_match": all(row["pass"] for row in audits),
        "max_angular_impulse_abs_difference_Nms": max(
            row["angular_impulse_abs_difference_Nms"] for row in audits
        ),
        "max_thruster_impulse_abs_difference_Ns": max(
            row["thruster_impulse_abs_difference_Ns"] for row in audits
        ),
        "max_propellant_abs_difference_g": max(
            row["propellant_abs_difference_g"] for row in audits
        ),
        "minimum_reported_minus_lower_bound_g": min(
            row["reported_minus_lower_bound_g"] for row in audits
        ),
        "rows": audits,
    }


def main() -> dict:
    try:
        cfg = load_config(verify_hashes=True)
        (
            stage_a,
            timeseries,
            stage_b,
            crosschecks,
            transient,
            transient_criterion,
            experiment_summary,
        ) = run_all(cfg)
    except Exception as exc:
        return _blocked(f"{type(exc).__name__}: {exc}")

    tol = float(cfg["gates"]["conservation_abs"])
    att_tol = float(cfg["gates"]["attribution_abs"])
    evaluated_a = [r for r in stage_a if r["evaluation_status"] == "EVALUATED"]

    # GC0: conservation and machine attribution.
    a_cons = max(r["momentum_conservation_max_abs"] for r in evaluated_a)
    a_exchange = max(r["wheel_body_exchange_max_abs"] for r in evaluated_a)
    capture_eps_h = max(r["capture_eps_H"] for r in stage_b)
    capture_eps_p = max(r["capture_eps_P"] for r in stage_b)
    b_ledger_closure_Nms = max(
        r["external_ledger_closure_max_abs"] for r in stage_b
    )
    attribution_mismatch = []
    for r in evaluated_a:
        expected = (
            "MOMENTUM_STORAGE"
            if r["wheel_peak_axis_Nms"] > att_tol
            else "INTERNAL_REDISTRIBUTION"
        )
        if r["attribution"] != expected:
            attribution_mismatch.append(
                {"scenario": r["maneuver"], "controller": r["controller"]}
            )
    for r in stage_b:
        expected = classify_attribution(
            r["external_angular_impulse_vector_Nms"],
            r["wheel_h_final_Nms"],
            internal_motion=False,
            tolerance=att_tol,
        )
        if r["attribution"] != expected:
            attribution_mismatch.append(
                {"scenario": r["case"], "controller": r["controller"]}
            )
    for r in transient:
        expected = classify_attribution(
            r["external_angular_impulse_vector_Nms"],
            r["wheel_h_final_Nms"],
            internal_motion=False,
            tolerance=att_tol,
        )
        if r["attribution"] != expected:
            attribution_mismatch.append(
                {
                    "scenario": r["case"],
                    "controller": r["controller"],
                    "layer": "B_TRANSIENT",
                }
            )
    gc0_ok = (
        a_cons <= tol
        and a_exchange <= tol
        and capture_eps_h <= tol
        and capture_eps_p <= tol
        and b_ledger_closure_Nms <= tol
        and not attribution_mismatch
    )

    # GC1: exact sim_05 direct anchor plus the A2 registered reduction hypothesis.
    a0 = {r["maneuver"]: r for r in evaluated_a if r["controller"] == "A0_no_compensation"}
    a2 = {
        r["maneuver"]: r
        for r in evaluated_a
        if r["controller"] == "A2_arm_wheel_coordination"
    }
    reductions = {
        m: 1.0
        - a2[m]["peak_base_dev_angle_deg"] / a0[m]["peak_base_dev_angle_deg"]
        for m in a0
    }
    m1_direct_diff = abs(
        a0["M1_headline"]["peak_base_dev_angle_deg"]
        - float(cfg["anchors"]["sim05_direct_solver_peak_deg"])
    )
    launch_card_rel = abs(
        a0["M1_headline"]["peak_base_dev_angle_deg"]
        - float(cfg["anchors"]["launch_card_value_sim11_A1_peak_deg"])
    ) / float(cfg["anchors"]["launch_card_value_sim11_A1_peak_deg"])
    endpoint_identity_tolerance = 1.0e-6
    a1_results = []
    for r in evaluated_a:
        if r["controller"] != "A1_reaction_trajectory":
            continue
        checks = {
            "task_endpoint_completed": bool(r["task_endpoint_completed"]),
            "joint_endpoint_error_within_tolerance": (
                r["joint_endpoint_error_max_deg"] <= endpoint_identity_tolerance
            ),
            "ee_endpoint_degradation_within_tolerance": (
                r["ee_endpoint_degradation_S_mm"] <= endpoint_identity_tolerance
            ),
        }
        a1_results.append(
            {
                "maneuver": r["maneuver"],
                "method_result": r["method_result"],
                "task_endpoint_completed": r["task_endpoint_completed"],
                "joint_endpoint_error_max_deg": r[
                    "joint_endpoint_error_max_deg"
                ],
                "ee_endpoint_degradation_S_mm": r[
                    "ee_endpoint_degradation_S_mm"
                ],
                "completion_checks": checks,
                "all_completion_checks_pass": all(checks.values()),
            }
        )
    a1_all_endpoints_completed = all(
        result["all_completion_checks_pass"] for result in a1_results
    )
    m2_margin_min = min(
        r["joint_limit_margin_min_rad"]
        for r in evaluated_a
        if r["maneuver"] == "M2_limit_compliant"
    )
    gc1_ok = (
        m1_direct_diff <= float(cfg["gates"]["anchor_identity_abs"])
        and all(
            value >= float(cfg["gates"]["a2_peak_reduction_min_fraction"])
            for value in reductions.values()
        )
        and all(not r["wheel_saturated"] for r in a2.values())
        and a1_all_endpoints_completed
        and m2_margin_min
        >= float(
            cfg["stage_a"]["maneuvers"]["M2_limit_compliant"][
                "joint_limit_margin_min_rad"
            ]
        )
    )

    # GC2: independent four-case replay and frozen-domain preservation.
    cross_max = max(
        max(v["H_diff_Nms"], v["rate_diff_dps"]) for v in crosschecks.values()
    )
    b_anchor_rows = [r for r in stage_b if r["case"] == "B_anchor"]
    b_anchor_out = all(
        r["domain_status"] == "OUT_OF_FEASIBLE_REGION" for r in b_anchor_rows
    )
    physical_domain_consistent = all(
        r["domain_status"]
        == (
            "IN_FEASIBLE_REGION"
            if r["physical_control_region"]
            in ("WHEELS_ONLY_FEASIBLE", "THRUSTER_REQUIRED_FEASIBLE")
            else "OUT_OF_FEASIBLE_REGION"
        )
        for r in stage_b
    )
    gc2_ok = (
        cross_max <= float(cfg["gates"]["sim12_crosscheck_abs"])
        and b_anchor_out
        and physical_domain_consistent
    )

    # GC3: sim_08 debris budget and physical wheel box.
    b_anchor_b2 = next(
        r
        for r in stage_b
        if r["case"] == "B_anchor" and r["controller"] == "B2_thruster_removal"
    )
    propellant_audit = independent_propellant_audit(stage_b, cfg)
    b_anchor_b2_propellant_audit = next(
        row
        for row in propellant_audit["rows"]
        if row["case"] == "B_anchor"
        and row["controller"] == "B2_thruster_removal"
    )
    legacy_ratio = float(cfg["anchors"]["sim10_debris_H_Nms"]) / 0.3
    gc3_ok = (
        b_anchor_b2_propellant_audit["pass"]
        and all(
            r.get("wheel_peak_axis_Nms", 0.0) <= 0.1 + 1e-12 for r in evaluated_a
        )
        and all(
            max(abs(x) for x in r["wheel_h_final_Nms"]) <= 0.1 + 1e-12
            for r in stage_b
        )
    )

    # GC4: expected terminal outcomes and independent propellant lower-bound audit.
    lookup = {(r["case"], r["controller"]): r for r in stage_b}
    outcome_checks = {
        "A_low_B1_storage_complete": (
            lookup[("A_low", "B1_wheel_storage")]["controller_outcome"]
            == "BODY_RATE_ZERO_WITH_MOMENTUM_STORED"
        ),
        "C_transition_B2_external_complete": (
            lookup[("C_transition", "B2_thruster_removal")]["controller_outcome"]
            == "ANGULAR_MOMENTUM_TARGET_REACHED"
        ),
        "D_extreme_B2_budget_exhausted": (
            lookup[("D_extreme", "B2_thruster_removal")]["controller_outcome"]
            == "EXTERNAL_BUDGET_EXHAUSTED"
        ),
        "D_extreme_B3_budget_exhausted": (
            lookup[("D_extreme", "B3_wheel_thruster")]["controller_outcome"]
            == "EXTERNAL_BUDGET_EXHAUSTED"
        ),
    }
    gc4_ok = all(outcome_checks.values()) and propellant_audit["all_match"]

    # GC5: registry/hash lock, no widened thresholds, FLEX excluded, and the
    # PROVISIONAL actuator layer stays labeled and hardware-invalid.
    act_cfg = cfg["stage_b"]["actuator_dynamics"]
    win_cfg = cfg["stage_b"]["stability_window"]
    gc5_ok = (
        all(v["match"] for v in cfg["_hash_report"].values())
        and cfg["policy"]["thresholds_widened"] is False
        and cfg["policy"]["flex_in_absolute_criteria"] is False
        and all(r["flex_status"] == "UNKNOWN_NOT_IN_CRITERIA" for r in stage_b)
        and all(
            r["stability_status"] == "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS"
            for r in stage_b
        )
        and all(
            r["analysis_scope"] == "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY"
            for r in stage_b
        )
        and act_cfg["status"] == "PROVISIONAL"
        and win_cfg["status"] == "PROVISIONAL"
        and "PROVISIONAL" in act_cfg["wheel_max_torque_source_note"]
        and "PROVISIONAL" in act_cfg["thruster_min_pulse_source_note"]
        and all(
            r["stability_status"]
            == "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
            and r["model_fidelity"] == "PROVISIONAL_L1_MOMENTUM_ACTUATOR"
            and r["hardware_valid"] is False
            for r in transient
        )
        and cfg["repeat_revision"]["thresholds_changed"] is False
    )

    # GC6: full deterministic rerun through the same bounded fixed-grid method.
    stage_a_2, timeseries_2 = run_phase_a(cfg)
    stage_b_2, crosschecks_2 = run_phase_b(cfg)
    transient_2, _ = run_transient(cfg, stage_b_2)
    deterministic = (
        _canonical(stage_a) == _canonical(stage_a_2)
        and _canonical(timeseries) == _canonical(timeseries_2)
        and _canonical(stage_b) == _canonical(stage_b_2)
        and _canonical(crosschecks) == _canonical(crosschecks_2)
        and _canonical(transient) == _canonical(transient_2)
    )
    gc6_ok = deterministic

    # GC7: Stage-B transient stability under the frozen PROVISIONAL actuator
    # dynamics and time-window criterion (R5).
    transient_audit = independent_propellant_audit(transient, cfg)
    external_capacity = float(cfg["gates"]["external_removal_capacity_Nms"])
    gc7_checks = {
        "all_rows_evaluated": len(transient) == len(stage_b)
        and all(r["evaluation_status"] == "EVALUATED" for r in transient),
        "terminal_consistent_with_L0_all": all(
            r["terminal_consistent_with_L0"] for r in transient
        ),
        "accumulation_error_within_1e9_all": all(
            r["accumulation_error_Nms"] <= 1e-9 for r in transient
        ),
        "algebraic_prediction_matches_simulation_all": all(
            r["prediction_matches_simulation"] for r in transient
        ),
        "wheel_box_never_exceeded_in_transient": all(
            r["wheel_abs_peak_Nms"] <= 0.1 + 1e-12 for r in transient
        ),
        "external_removal_within_frozen_capacity": all(
            r["external_angular_impulse_Nms"] <= external_capacity + 1e-12
            for r in transient
        ),
        "transient_propellant_audit_all_match": transient_audit["all_match"],
    }
    gc7_ok = all(gc7_checks.values())
    stability_table = [
        {
            "case": r["case"],
            "controller": r["controller"],
            "domain_status": r["domain_status"],
            "counterfactual_only": r["counterfactual_only"],
            "stability_verdict": r["stability_verdict"],
            "t_settle_s": r["t_settle_s"],
            "completion_time_s": r["completion_time_s"],
            "rate_initial_dps": r["rate_initial_dps"],
            "rate_at_window_end_dps": r["rate_at_window_end_dps"],
            "n_pulses": r["n_pulses"],
            "unexecuted_remainder_Nms": r["unexecuted_remainder_Nms"],
            "terminal_vs_L0_diff_Nms": r["terminal_vs_L0_diff_Nms"],
            "propellant_g": r["propellant_g"],
        }
        for r in transient
    ]

    gates = {
        "GC0_momentum_attribution": {
            "status": _status(gc0_ok),
            "stage_A_generalized_momentum_residual": {
                "max_abs": a_cons,
                "threshold": tol,
                "unit": "frozen generalized-momentum SI component",
            },
            "stage_A_wheel_body_angular_exchange": {
                "max_abs_Nms": a_exchange,
                "threshold_Nms": tol,
                "unit": "N*m*s",
            },
            "capture_conservation_dimensionless": {
                "eps_H_max": capture_eps_h,
                "eps_P_max": capture_eps_p,
                "threshold_dimensionless": tol,
                "unit": "1",
            },
            "external_angular_momentum_ledger_closure": {
                "max_abs_Nms": b_ledger_closure_Nms,
                "threshold_Nms": tol,
                "unit": "N*m*s",
            },
            "attribution_mismatches": attribution_mismatch,
        },
        "GC1_stage_A_anchor_and_reduction": {
            "status": _status(gc1_ok),
            "sim05_direct_anchor_diff_deg": m1_direct_diff,
            "launch_card_sim11_value_relative_difference": launch_card_rel,
            "launch_card_anchor_resolution": cfg["anchors"]["launch_card_anchor_note"],
            "A2_reduction_fraction": reductions,
            "A2_wheel_box_utilization": {
                m: a2[m]["wheel_box_utilization_max"] for m in a2
            },
            "M2_joint_limit_margin_min_rad": m2_margin_min,
            "A1_endpoint_identity_tolerance": {
                "joint_endpoint_error_max_deg": endpoint_identity_tolerance,
                "ee_endpoint_degradation_S_mm": endpoint_identity_tolerance,
            },
            "A1_all_task_endpoints_completed": a1_all_endpoints_completed,
            "A1_bounded_results": a1_results,
            "A1_design": next(
                r["a1_design"]
                for r in evaluated_a
                if r["controller"] == "A1_reaction_trajectory"
            ),
            "M2_registered_start_deg": cfg["stage_a"]["maneuvers"][
                "M2_limit_compliant"
            ]["q_start_deg"],
            "note": (
                "GC1 requires every A1 task_endpoint_completed flag and both "
                "reported endpoint metrics to pass, plus the frozen 0.05 rad "
                "M2 margin over the realized trajectories of all evaluated "
                "controllers. This run executes the CTRL-02-R R4 pre-registered "
                "revision: interior M2 start (not the withdrawn -5 deg probe) "
                "and the two-segment task-valid A1."
            ),
        },
        "GC2_four_case_independent_replay": {
            "status": _status(gc2_ok),
            "max_H_or_rate_difference": cross_max,
            "crosschecks": crosschecks,
            "B_anchor_all_rows_out_of_feasible_region": b_anchor_out,
            "formal_domain_uses_physical_control_region": physical_domain_consistent,
            "legacy_scalar_region_role": "cross-check only",
        },
        "GC3_sim08_budget_and_wheel_box": {
            "status": _status(gc3_ok),
            "B_anchor_B2_impulse_Ns": b_anchor_b2["thruster_total_impulse_Ns"],
            "B_anchor_B2_propellant_g": b_anchor_b2["propellant_g"],
            "B_anchor_B2_independent_audit": b_anchor_b2_propellant_audit,
            "legacy_scalar_overflow_ratio": legacy_ratio,
            "legacy_scalar_role": "cross-check only; not an actuator pass criterion",
            "wheel_physical_envelope": "per-axis +/-0.1 Nms box",
        },
        "GC4_outcomes_and_propellant_lower_bound": {
            "status": _status(gc4_ok),
            "outcome_checks": outcome_checks,
            "independent_propellant_lower_bound_audit": propellant_audit,
        },
        "GC5_registry_and_claim_discipline": {
            "status": _status(gc5_ok),
            "frozen_hashes": cfg["_hash_report"],
            "thresholds_widened": cfg["policy"]["thresholds_widened"],
            "repeat_revision_thresholds_changed": cfg["repeat_revision"][
                "thresholds_changed"
            ],
            "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
            "stage_B_L0_analysis_scope": "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY",
            "stage_B_L0_stability_status": "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
            "stage_B_transient_stability_status": (
                "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
            ),
            "transient_model_fidelity": "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
        },
        "GC6_determinism": {
            "status": _status(gc6_ok),
            "full_proof_set_rerun_byte_canonical_equal": deterministic,
            "includes_stage_b_transient": True,
        },
        "GC7_transient_stability_window": {
            "status": _status(gc7_ok),
            "criterion": transient_criterion,
            "checks": gc7_checks,
            "stability_table": stability_table,
            "n_stabilized_within_window": sum(
                r["stabilized_within_window"] for r in transient
            ),
            "transient_propellant_audit": transient_audit,
            "quantization_note": (
                "The PROVISIONAL 0.1 N x 20 ms x 0.17 m pulse quantum "
                "(3.4e-4 Nms) bounds every terminal difference from the L0 "
                "plan; the resulting residual-rate floor sits near the "
                "PROVISIONAL 0.05 dps settle threshold for the lightest "
                "combined stack and must be re-evaluated when hardware values "
                "replace the placeholders."
            ),
        },
    }
    verdict = "PASS" if all(g["status"] == "PASS" for g in gates.values()) else "REPEAT"
    out = {
        "schema_version": "control02-gate-v3",
        "task_id": "CTRL-02",
        "repeat_revision": cfg["repeat_revision"],
        "verdict": verdict,
        "gates": gates,
        "experiment_summary": experiment_summary,
        "scope_resolution": {
            "legacy_task_card_title": "A0-A3 / B0-B3",
            "approved_stage_A_comparison": ["A0", "A1", "A2"],
            "A3_evaluation_status": cfg["stage_a"]["A3"]["evaluation_status"],
            "A3_verified": False,
            "basis": (
                "Frozen sim_08 and registry contain no wheel torque or minimum "
                "thruster pulse; the R5 Stage-B actuator values are PROVISIONAL "
                "placeholders scoped to the transient layer only, so A3 "
                "performance remains claim-forbidden."
            ),
        },
        "review_status": "PENDING_REVIEW",
        "loop6_independent_red_team_complete": False,
        "formal_safety_classification_emitted": False,
        "thresholds_widened": False,
        "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
        "stage_B_scope": {
            "L0_analysis": "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY",
            "L0_stability_status": "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
            "transient_analysis": "TIME_WINDOW_TRANSIENT_STABILITY",
            "transient_stability_status": (
                "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
            ),
            "transient_model_fidelity": "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
        },
        "claim_allowed": [
            "For M1 (the unchanged non-flight q2-limit-violating dynamics anchor) and the R4 pre-registered M2 (interior start, full-trajectory margin gate), L0 A2 reduces pre-capture base dev_angle while respecting the per-axis wheel box; this does not unlock a hardware-valid claim.",
            "The two-segment A1 completes the registered task endpoint exactly while reducing base reaction only in its projected segment; A1 is not reactionless.",
            "At momentum-level terminal feasibility, B2 external angular impulse and independently audited propellant are reported separately from B1 wheel momentum storage.",
            "Under the R5 PROVISIONAL wheel-torque, minimum-pulse, and time-window parameters, per-row STABILIZED/NOT_STABILIZED_WITHIN_WINDOW verdicts and the pulse-quantization residual floor are reported.",
            "B_anchor remains an out-of-feasible-region counterfactual in every controller row.",
        ],
        "claim_forbidden": [
            "A1 is a reactionless trajectory.",
            "A3 performance or feasibility.",
            "M1 is a flight-limit-compliant trajectory.",
            "Reaction wheels remove total angular momentum.",
            "The controller expands the frozen sim_10 feasible region.",
            "Hardware-valid Stage-B stability, closed-loop control performance, or any conclusion that survives replacement of the PROVISIONAL actuator placeholders without a re-run.",
            "Any absolute FLEX or hardware-valid performance statement.",
        ],
        "repro": [
            "python 30_simulation/control_02_base_attitude/tests/run_all.py",
            "python 30_simulation/control_02_base_attitude/src/run_gates.py",
        ],
    }
    _write(out)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "gates": {k: v["status"] for k, v in gates.items()},
                "review_status": out["review_status"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return out


if __name__ == "__main__":
    main()
