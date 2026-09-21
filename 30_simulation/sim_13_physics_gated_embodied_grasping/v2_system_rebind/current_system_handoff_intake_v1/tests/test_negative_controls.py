from __future__ import annotations

from current_handoff.negative_controls import run_negative_controls


def test_all_31_negative_controls_pass():
    result = run_negative_controls()
    assert result["all_passed"] is True
    assert result["controls_passed"] == result["controls_total"] == 31
    assert [item["id"] for item in result["controls"]] == [f"NC{i:02d}" for i in range(1, 32)]


def test_negative_controls_generate_no_mechanical_assets():
    result = run_negative_controls()
    assert result["urdf_generator_invoked"] is False
    assert result["generated_cad_step_mesh_urdf_or_physics_assets"] is False


def test_negative_control_baseline_is_deterministic():
    first = run_negative_controls()
    second = run_negative_controls()
    assert first["baseline_sha256"] == second["baseline_sha256"]
    assert first == second


def test_nc09_and_nc22_are_real_source_mutations_and_binding_mismatches_are_registered():
    controls = {item["id"]: item for item in run_negative_controls()["controls"]}
    assert controls["NC09"] == {"id": "NC09", "stimulus": "ROUTE_B_SEED_INHERITANCE_IN_SOURCE_LINEAGE", "passed": True}
    assert controls["NC22"] == {"id": "NC22", "stimulus": "SOURCE_PAYLOAD_BYTE_AND_HASH_MUTATION", "passed": True}
    assert controls["NC27"]["stimulus"] == "PROMOTION_RECEIPT_ARTIFACT_ID_MISMATCH"
    assert controls["NC28"]["stimulus"] == "PROMOTION_RECEIPT_ACTION_DIGEST_MISMATCH"
    assert controls["NC29"]["stimulus"] == "PROMOTION_RECEIPT_CONTEXT_DIGEST_MISMATCH"
    assert controls["NC30"] == {
        "id": "NC30",
        "stimulus": "EXTRA_EVIDENCE_OR_RESULT_FILE_OUTSIDE_FROZEN_ALLOWLIST",
        "passed": True,
    }
    assert controls["NC31"] == {
        "id": "NC31",
        "stimulus": "EXTRA_PHYSICS_OR_ROBOT_FORMAT_OUTSIDE_FROZEN_ALLOWLIST",
        "passed": True,
    }
