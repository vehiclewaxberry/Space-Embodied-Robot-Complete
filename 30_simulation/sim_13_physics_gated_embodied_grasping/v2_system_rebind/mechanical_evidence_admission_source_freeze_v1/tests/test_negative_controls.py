from __future__ import annotations

from mechanical_admission.negative_controls import run_negative_controls


def test_all_registered_negative_controls_pass(snapshot):
    report = run_negative_controls(snapshot)
    assert report["baseline_source_only_validation_pass"] is True
    assert report["controls_total"] == 16
    assert report["controls_passed"] == 16
    assert report["all_passed"] is True
    assert report["generated_physics_or_mechanical_assets"] is False


def test_negative_control_ids_are_exact(snapshot):
    report = run_negative_controls(snapshot)
    assert [item["id"] for item in report["controls"]] == [f"NC{i:02d}" for i in range(1, 17)]
