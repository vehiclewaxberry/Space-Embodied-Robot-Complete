from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest
import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_dynamics_gate import package_artifact_paths  # noqa: E402
from r2_dynamics import load_json_strict, solve_locked_kkt  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def result(name: str) -> dict:
    return load_json_strict(PACKAGE / "results" / name)


def test_source_pins_are_exact_and_complete() -> None:
    binding = result("R2_DYNAMICS_SOURCE_BINDING_V1.json")
    assert binding["all_match"] is True
    assert binding["summary"]["matched"] == binding["summary"]["total"]
    assert binding["summary"]["total"] == 27
    assert all(row["match"] is True for row in binding["pins"])


def test_locked_kkt_simple_system_has_explicit_reaction() -> None:
    mass = np.diag([2.0, 3.0])
    bias = np.zeros(2)
    effort = np.array([4.0, 5.0])
    jac = np.array([[0.0, 1.0]])
    solved = solve_locked_kkt(mass, bias, effort, jac)
    np.testing.assert_allclose(solved["acceleration"], [2.0, 0.0], atol=0.0)
    np.testing.assert_allclose(solved["reaction"], [-5.0], atol=0.0)
    np.testing.assert_allclose(solved["equilibrium_residual"], [0.0, 0.0])
    np.testing.assert_allclose(solved["constraint_acceleration"], [0.0])


def test_locked_kkt_rejects_malformed_inputs() -> None:
    with pytest.raises(ValueError, match="KKT_MASS_MATRIX_MALFORMED"):
        solve_locked_kkt(np.zeros((2, 3)), [0, 0], [0, 0], np.zeros((1, 2)))
    with pytest.raises(ValueError, match="KKT_CONSTRAINT_JACOBIAN_MALFORMED"):
        solve_locked_kkt(np.eye(2), [0, 0], [0, 0], np.zeros((1, 3)))


def test_constrained_gate_passes_only_candidate_scope() -> None:
    gate = result("R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json")
    assert gate["technical_verdict"].startswith(
        "R2_8DOF_CONSTRAINED_DYNAMICS_HOLD"
    )
    assert gate["summary"]["passed"] == 16
    assert gate["summary"]["total"] == 18
    assert gate["summary"]["failed"] == [
        "DG1_heterogeneous_coordinate_metric_bound",
        "DG2_independent_full_state_momentum_conservation",
    ]
    assert gate["candidate_package_complete"] is False
    assert gate["artifact_package_generated"] is True
    assert gate["dynamics_engineering_complete"] is False
    assert gate["hardware_valid"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_tauP_zero_is_not_a_lock_and_reactions_are_reported() -> None:
    gate = result("R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json")
    metrics = gate["key_metrics"]
    assert len(metrics["locked_reaction_N"]) == 2
    assert metrics["locked_reaction_norm_N"] > 0.0
    assert metrics["constraint_acceleration_max_abs_m_s2"] <= 1e-12
    assert metrics["tauP_zero_free_ddqP_norm_m_s2"] >= 1e-8
    assert len(metrics["base_twist_rate_body_coordinates_mixed_m_s2_rad_s2"]) == 6
    assert metrics["base_linear_acceleration_coordinate_cross_max_abs_m_s2"] <= 1e-10
    assert metrics["base_angular_acceleration_coordinate_cross_max_abs_rad_s2"] <= 1e-10


def test_diagnostics_conservation_cross_and_determinism() -> None:
    diagnostics = result("R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json")
    assert diagnostics["candidate_diagnostics_pass"] is False
    assert diagnostics["determinism"]["constrained_exact_canonical_match"] is True
    assert diagnostics["determinism"]["flex_exact_canonical_match"] is True
    constrained = diagnostics["constrained"]
    assert constrained["checks"]["mass_symmetric_RR"] is True
    assert constrained["checks"]["mass_symmetric_RP"] is True
    assert constrained["checks"]["mass_symmetric_PP"] is True
    assert constrained["checks"]["heterogeneous_coordinate_metric_bound"] is False
    assert constrained["checks"]["locked_short_time_energy"] is True
    assert constrained["checks"]["RK4_vs_DOP853_qR"] is True
    assert constrained["checks"]["RK4_vs_DOP853_dqR"] is True
    assert constrained["checks"]["mechanical_connection_linear_zero_identity"] is True
    assert constrained["checks"]["mechanical_connection_angular_zero_identity"] is True
    assert constrained["checks"]["independent_full_state_momentum_conservation"] is False
    assert constrained["zero_momentum_audit"]["base_pose_integrated"] is False
    assert constrained["zero_momentum_audit"]["independent_full_state_conservation_proven"] is False


def test_flex_is_bounded_component_diagnostic_without_credit_inheritance() -> None:
    flex = result("R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json")["flex"]
    assert flex["combined_modes"] == 14
    assert flex["pass_for_bounded_component_diagnostic"] is True
    assert flex["arm_to_flex_time_domain_coupling_evaluated"] is False
    assert flex["full_coupled_rigid_limit_evaluated"] is False
    assert flex["E23_pass_inherited"] is False
    assert flex["dynamics_engineering_credit"] is False
    assert [row["corner"] for row in flex["corners"]] == ["LOW", "NOMINAL", "HIGH"]
    for row in flex["corners"]:
        assert "expm_vs_DOP853_eta_relative" in row
        assert "expm_vs_DOP853_deta_relative" in row
        assert "expm_vs_DOP853_relative" not in row
        assert row["checks"]["expm_vs_DOP853_eta"] is True
        assert row["checks"]["expm_vs_DOP853_deta"] is True


def test_actuator_nulls_remain_null_and_block_hardware_credit() -> None:
    diagnostics = result("R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json")
    actuator = diagnostics["constrained"]["actuated_8DOF_boundary"][
        "actuator_contract"
    ]
    assert actuator["null_measurement_fields"] == actuator["total_measurement_fields"]
    assert actuator["hardware_effort_model_valid"] is False
    assert actuator["actuated_8dof_execution_authorized"] is False
    assert all(row["all_measurements_null"] for row in actuator["joint_records"])


def test_engineering_gate_has_native_aggregation_booleans_and_holds() -> None:
    gate = result("R2_DYNAMICS_ENGINEERING_GATE_V1.json")
    for field in (
        "candidate_package_complete",
        "dynamics_engineering_complete",
        "hardware_valid",
        "next_stage_authorized",
        "release_credit",
    ):
        assert type(gate[field]) is bool
    assert gate["candidate_package_complete"] is False
    assert gate["artifact_package_generated"] is True
    assert gate["dynamics_engineering_complete"] is False
    assert gate["hardware_valid"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False
    assert gate["unknown_auto_allow_count"] == 0
    assert len(gate["holds"]) >= 5
    assert len(gate["unknowns"]) >= 6


def test_configuration_classes_cannot_inherit_results() -> None:
    gate = result("R2_DYNAMICS_ENGINEERING_GATE_V1.json")
    classes = gate["configuration_class_separation"]
    assert classes["LEGACY_24KG"]["dynamics_result_inheritance"] == "FORBIDDEN"
    assert classes["CURRENT_R2"]["mass_kg"] == 31.022864807342987
    assert (
        classes["TARGET_ATTACHED"]["plant_instance_status"]
        == "NOT_IMPLEMENTED"
    )
    assert (
        classes["TARGET_ATTACHED"]["dynamics_result_inheritance"]
        == "FORBIDDEN"
    )


def test_execution_guards_are_all_false() -> None:
    gate = result("R2_DYNAMICS_ENGINEERING_GATE_V1.json")
    assert gate["execution_guards"]
    assert all(value is False for value in gate["execution_guards"].values())


def test_all_local_json_is_strict_and_finite() -> None:
    paths = list((PACKAGE / "config").glob("*.json")) + list(
        (PACKAGE / "results").glob("*.json")
    )
    assert paths
    for path in paths:
        document = load_json_strict(path)
        json.dumps(document, allow_nan=False)


def test_manifest_and_sha_csv_exactly_match_files() -> None:
    manifest_path = PACKAGE / "results" / "R2_DYNAMICS_PACKAGE_MANIFEST_V1.json"
    manifest = load_json_strict(manifest_path)
    assert manifest["summary"]["count"] == len(manifest["artifacts"])
    assert manifest["summary"]["all_exist"] is True
    assert manifest["artifact_package_complete"] is True
    assert manifest["candidate_package_complete"] is False
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.stat().st_size == row["bytes"]
        assert sha256(path) == row["sha256"]

    sha_path = PACKAGE / "results" / "R2_DYNAMICS_SHA256_V1.csv"
    with sha_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(manifest["artifacts"]) + 1
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.stat().st_size == int(row["bytes"])
        assert sha256(path) == row["sha256"]


def test_manifest_required_set_fails_closed_on_missing_file(monkeypatch) -> None:
    original = Path.is_file

    def missing_one(path: Path) -> bool:
        if path == PACKAGE / "src" / "__init__.py":
            return False
        return original(path)

    monkeypatch.setattr(Path, "is_file", missing_one)
    with pytest.raises(FileNotFoundError, match="REQUIRED_PACKAGE_ARTIFACT_MISSING"):
        package_artifact_paths()


def test_authority_preserves_fail_closed_semantics() -> None:
    authority = yaml.safe_load(
        (PACKAGE / "contracts" / "R2_DYNAMICS_AUTHORITY_V1.yaml").read_text(
            encoding="utf-8"
        )
    )
    invariants = authority["fail_closed_invariants"]
    assert any("tau_P equals zero" in item for item in invariants)
    assert authority["next_stage_authorized"] is False
    assert authority["release_credit"] is False
    metric = authority["coordinate_contract"]["heterogeneous_coordinate_metric"]
    assert metric["status"] == "UNBOUND"
    assert metric["mixed_mass_spectrum_or_condition_credit_allowed"] is False
    assert metric["mixed_state_or_acceleration_norm_credit_allowed"] is False
