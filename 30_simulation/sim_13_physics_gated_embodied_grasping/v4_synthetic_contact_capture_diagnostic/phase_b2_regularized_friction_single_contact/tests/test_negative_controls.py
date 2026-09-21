from __future__ import annotations

from b2_contact import run_negative_controls


def test_all_ten_negative_controls_are_registered(friction_bundle):
    controls = run_negative_controls(friction_bundle[-1]["rk4_reference"], friction_bundle[3])
    assert len(controls) == 10
    assert len({item["control_id"] for item in controls}) == 10


def test_every_raw_mutation_crosses_its_guard(friction_bundle):
    controls = run_negative_controls(friction_bundle[-1]["rk4_reference"], friction_bundle[3])
    assert all(item["raw_error_exceeds_threshold"] for item in controls)


def test_every_mutation_is_rejected(friction_bundle):
    controls = run_negative_controls(friction_bundle[-1]["rk4_reference"], friction_bundle[3])
    assert all(item["mutation_rejected"] and item["result"] == "PASS_NEGATIVE_CONTROL" for item in controls)
