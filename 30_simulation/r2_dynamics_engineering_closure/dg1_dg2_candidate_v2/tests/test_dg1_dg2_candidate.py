from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import numpy as np


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg1_dg2_candidate import (  # noqa: E402
    file_sha256,
    load_contract,
    load_json_strict,
    normalized_quaternion,
    quaternion_rotation_body_to_inertial,
    validate_source_pins,
)


def result(name: str) -> dict:
    return load_json_strict(PACKAGE / "results" / name)


def test_contract_and_source_pins_are_exact() -> None:
    contract = load_contract()
    binding = validate_source_pins(contract)
    assert binding["all_match"] is True
    assert binding["summary"] == {"matched": 6, "total": 6}


def test_quaternion_rotation_is_orthonormal_and_sign_invariant() -> None:
    quaternion = normalized_quaternion([0.98, 0.1, -0.08, 0.12])
    rotation = quaternion_rotation_body_to_inertial(quaternion)
    rotation_negative = quaternion_rotation_body_to_inertial(-quaternion)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-15)
    np.testing.assert_allclose(rotation, rotation_negative, atol=0.0)
    assert np.linalg.det(rotation) > 0.0


def test_dg1_reference_metric_closes_without_mixed_raw_norm_credit() -> None:
    evidence = result("DG1_DG2_CANDIDATE_EVIDENCE_V2.json")
    dg1 = evidence["dg1"]
    assert dg1["candidate_pass"] is True
    assert dg1["reference_scale_authority"].startswith("FINITE_URDF_JOINT_SPAN")
    assert dg1["condition_number_scope"].startswith("CONDITION_NUMBER_CREDIT_ONLY")
    metrics = dg1["metrics"]
    assert metrics["scale_span_max_abs_mixed_rad_m"] <= 1e-15
    assert metrics["reference_energy_relative_error"] <= 1e-12
    assert metrics["reference_virtual_power_relative_error"] <= 1e-12
    assert metrics["reference_acceleration_cross_revolute_max_abs_rad_s2"] <= 1e-10
    assert metrics["reference_acceleration_cross_prismatic_max_abs_m_s2"] <= 1e-10


def test_dg2_is_nonzero_full_pose_and_per_body_conserved() -> None:
    evidence = result("DG1_DG2_CANDIDATE_EVIDENCE_V2.json")
    dg2 = evidence["dg2"]
    assert dg2["candidate_pass"] is True
    assert dg2["torque_driven"] is False
    assert dg2["contact_evaluated"] is False
    checks = dg2["checks"]
    assert checks["nonzero_linear_momentum_case"] is True
    assert checks["nonzero_angular_momentum_case"] is True
    assert checks["base_position_integrated"] is True
    assert checks["base_attitude_integrated"] is True
    assert checks["RK4_linear_momentum_conserved_by_per_body_sum"] is True
    assert checks["RK4_angular_momentum_conserved_by_per_body_sum"] is True
    assert checks["DOP853_linear_momentum_conserved_by_per_body_sum"] is True
    assert checks["DOP853_angular_momentum_conserved_by_per_body_sum"] is True
    assert checks["matrix_vs_body_linear_cross_bounded"] is True
    assert checks["matrix_vs_body_angular_cross_bounded"] is True


def test_gate_is_15_of_15_but_parent_and_release_remain_hold() -> None:
    gate = result("R2_DG1_DG2_CANDIDATE_GATE_V2.json")
    assert gate["summary"]["passed"] == 15
    assert gate["summary"]["total"] == 15
    assert gate["summary"]["failed"] == []
    assert gate["candidate_DG1_satisfied"] is True
    assert gate["candidate_DG2_satisfied"] is True
    assert gate["candidate_package_complete"] is True
    assert gate["parent_gate_update"] == "NOT_APPLIED__ADDITIVE_CANDIDATE_EVIDENCE_ONLY"
    assert len(gate["remaining_parent_holds"]) == 3
    assert gate["dynamics_engineering_complete"] is False
    assert gate["hardware_valid"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_all_json_is_strict_and_finite() -> None:
    for path in list((PACKAGE / "contracts").glob("*.json")) + list(
        (PACKAGE / "results").glob("*.json")
    ):
        document = load_json_strict(path)
        json.dumps(document, allow_nan=False)


def test_manifest_and_checksum_rows_match() -> None:
    manifest = result("DG1_DG2_CANDIDATE_PACKAGE_MANIFEST_V2.json")
    assert manifest["summary"]["count"] == len(manifest["artifacts"])
    assert manifest["summary"]["all_exist"] is True
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.stat().st_size == row["bytes"]
        assert file_sha256(path) == row["sha256"]

    checksum_path = PACKAGE / "results" / "DG1_DG2_CANDIDATE_SHA256_V2.csv"
    with checksum_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == manifest["summary"]["count"] + 1
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.stat().st_size == int(row["bytes"])
        assert file_sha256(path) == row["sha256"]


def test_execution_guards_and_review_state_fail_closed() -> None:
    evidence = result("DG1_DG2_CANDIDATE_EVIDENCE_V2.json")
    assert all(value is False for value in evidence["execution_guards"].values())
    assert evidence["dynamics_engineering_complete"] is False
    assert evidence["hardware_valid"] is False
    assert evidence["next_stage_authorized"] is False
    assert evidence["release_credit"] is False
