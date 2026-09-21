"""Stage-B transient (R5) checks: labels, consistency, criterion, tamper."""
import copy
import json

from config_loader import MODULE, load_config
from run_gates import independent_propellant_audit


RESULTS = MODULE / "results"


def _load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def test_transient_rows_scope_and_provisional_labels():
    data = _load("stage_b_transient.json")
    rows = data["rows"]
    assert len(rows) == 16
    assert data["criterion"]["status"] == "PROVISIONAL"
    for row in rows:
        assert row["evaluation_status"] == "EVALUATED"
        assert (
            row["stability_status"]
            == "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
        )
        assert row["model_fidelity"] == "PROVISIONAL_L1_MOMENTUM_ACTUATOR"
        assert row["hardware_valid"] is False
        assert row["stability_verdict"] in (
            "STABILIZED_WITHIN_WINDOW",
            "NOT_STABILIZED_WITHIN_WINDOW",
        )
    return 0.0


def test_transient_terminal_consistency_and_prediction():
    rows = _load("stage_b_transient.json")["rows"]
    worst = 0.0
    for row in rows:
        assert row["terminal_consistent_with_L0"] is True
        assert row["terminal_vs_L0_diff_Nms"] <= row["pulse_quantum_Nms"] + 1e-9
        assert row["accumulation_error_Nms"] <= 1e-9
        assert row["prediction_matches_simulation"] is True
        assert row["wheel_abs_peak_Nms"] <= 0.1 + 1e-12
        worst = max(worst, row["terminal_vs_L0_diff_Nms"])
    return worst


def test_transient_stability_pattern_follows_momentum_physics():
    rows = _load("stage_b_transient.json")["rows"]
    lookup = {(r["case"], r["controller"]): r for r in rows}
    # No-control rows can never settle (all initial rates exceed 0.05 dps).
    for case in ("A_low", "B_anchor", "C_transition", "D_extreme"):
        assert not lookup[(case, "B0_no_control")]["stabilized_within_window"]
    # Wheels alone settle only where the per-axis box holds the whole vector.
    assert lookup[("A_low", "B1_wheel_storage")]["stabilized_within_window"]
    assert not lookup[("C_transition", "B1_wheel_storage")][
        "stabilized_within_window"
    ]
    # Thruster rows settle when removal completes inside window minus hold.
    assert lookup[("C_transition", "B2_thruster_removal")][
        "stabilized_within_window"
    ]
    assert lookup[("B_anchor", "B2_thruster_removal")][
        "stabilized_within_window"
    ]
    # D_extreme exhausts the frozen external budget: nothing settles.
    for controller in (
        "B1_wheel_storage",
        "B2_thruster_removal",
        "B3_wheel_thruster",
    ):
        assert not lookup[("D_extreme", controller)]["stabilized_within_window"]
    return 0.0


def test_transient_propellant_audit_reuses_gate_path_and_rejects_tamper():
    cfg = load_config()
    rows = _load("stage_b_transient.json")["rows"]
    baseline = independent_propellant_audit(rows, cfg)
    assert baseline["all_match"] is True

    tampered = copy.deepcopy(rows)
    target = next(
        row for row in tampered if row["external_angular_impulse_Nms"] > 0.0
    )
    target["propellant_g"] += 0.001
    rejected = independent_propellant_audit(tampered, cfg)
    assert rejected["all_match"] is False
    assert rejected["max_propellant_abs_difference_g"] >= 0.001 - 1e-12
    return rejected["max_propellant_abs_difference_g"]


def test_transient_quantization_floor_is_reported_not_hidden():
    rows = _load("stage_b_transient.json")["rows"]
    fired = [r for r in rows if r["n_pulses"] > 0]
    assert fired, "at least one thruster row must fire pulses"
    for row in fired:
        assert 0.0 <= row["unexecuted_remainder_Nms"] < row["pulse_quantum_Nms"]
    # The quantization residual floor must appear in the gate JSON note.
    gate = _load("control_02_gate_check.json")
    gc7 = gate["gates"]["GC7_transient_stability_window"]
    assert "quantum" in gc7["quantization_note"].lower()
    assert gc7["criterion"]["pulse_quantum_Nms"] > 0.0
    return min(r["unexecuted_remainder_Nms"] for r in fired)
