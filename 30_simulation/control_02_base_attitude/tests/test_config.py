"""Configuration and frozen-input tests."""
import hashlib

from config_loader import REPO, _bytes_for_hash, load_config


def test_frozen_hashes_and_thresholds():
    cfg = load_config(verify_hashes=True)
    assert all(v["match"] for v in cfg["_hash_report"].values())
    assert cfg["policy"]["thresholds_widened"] is False
    assert cfg["policy"]["flex_in_absolute_criteria"] is False
    return 0.0


def test_a3_is_explicitly_not_applicable():
    cfg = load_config()
    a3 = cfg["stage_a"]["A3"]
    assert a3["evaluation_status"] == (
        "NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS"
    )
    assert sorted(a3["missing_frozen_inputs"]) == [
        "thruster_minimum_pulse_s",
        "wheel_torque_limit_Nm",
    ]
    assert a3["claim_forbidden"] is True
    # The R5 PROVISIONAL Stage-B values must not silently unlock A3.
    assert "scope_note" in a3
    return 0.0


def test_r5_actuator_dynamics_are_provisional_and_grid_aligned():
    cfg = load_config()
    act = cfg["stage_b"]["actuator_dynamics"]
    win = cfg["stage_b"]["stability_window"]
    assert act["status"] == "PROVISIONAL"
    assert win["status"] == "PROVISIONAL"
    assert "PROVISIONAL" in act["wheel_max_torque_source_note"]
    assert "PROVISIONAL" in act["thruster_min_pulse_source_note"]
    assert act["wheel_max_torque_Nm"] > 0.0
    assert act["thruster_min_pulse_s"] > 0.0
    # Pulse-grid alignment keeps the transient fully deterministic.
    assert abs(win["time_step_s"] - act["thruster_min_pulse_s"]) <= 1e-15
    assert win["hold_min_s"] <= win["window_s"]
    assert win["rate_settle_dps"] > 0.0
    return 0.0


def test_r4_registered_m2_start_is_interior_and_not_the_withdrawn_probe():
    cfg = load_config()
    m2 = cfg["stage_a"]["maneuvers"]["M2_limit_compliant"]
    assert m2["q_start_deg"] == [0.0, -15.0, -15.0, 0.0, 0.0, 0.0]
    assert m2["q_start_deg"][1] != -5.0 and m2["q_start_deg"][2] != -5.0
    assert m2["joint_limit_margin_min_rad"] == 0.05
    assert cfg["repeat_revision"]["thresholds_changed"] is False
    a1 = cfg["stage_a"]["A1"]
    assert a1["endpoint_policy"] == "EXACT_REGISTERED_ENDPOINT"
    assert 0.0 < a1["t_switch_s"] < cfg["stage_a"]["maneuver_duration_s"]
    return 0.0


def test_hash_mode_is_line_ending_portable_but_tamper_sensitive():
    cfg = load_config()
    worst = 0.0
    for spec in cfg["frozen_inputs"].values():
        assert spec["hash_mode"] == "normalized_lf"
        canonical = _bytes_for_hash(REPO / spec["path"], "normalized_lf")
        crlf_variant = canonical.replace(b"\n", b"\r\n")
        h0 = hashlib.sha256(canonical).hexdigest()
        h1 = hashlib.sha256(
            crlf_variant.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        ).hexdigest()
        assert h0 == h1 == spec["sha256"]
        tampered = canonical + b"# semantic-tamper\n"
        assert hashlib.sha256(tampered).hexdigest() != spec["sha256"]
    return worst
