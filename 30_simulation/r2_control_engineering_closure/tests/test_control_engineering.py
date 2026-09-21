from __future__ import annotations

import csv
from pathlib import Path
import sys

import numpy as np
import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_control_engineering import build  # noqa: E402
from control_engineering import (  # noqa: E402
    CONFIG_PATH,
    PHASE_CONTRACT_PATH,
    RESULTS_DIR,
    SUPERVISOR_CONTRACT_PATH,
    load_json_strict,
    loads_json_strict,
    sha256_file,
    singularity_guard,
    validate_joint_state_fail_closed,
    validate_source_pins,
)


@pytest.fixture(scope="session")
def built() -> dict:
    return build(REPO_ROOT)


def test_strict_json_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY:a"):
        loads_json_strict('{"a": 1, "a": 2}')


def test_all_source_pins_match() -> None:
    config = load_json_strict(CONFIG_PATH)
    binding = validate_source_pins(REPO_ROOT, config)
    assert binding["pin_count"] == 24
    assert binding["match_count"] == 24
    assert binding["mismatches"] == []
    assert binding["pass"] is True


def test_phase_contract_is_physical_6r_plus_2p() -> None:
    contract = load_json_strict(PHASE_CONTRACT_PATH)
    assert contract["arm_physical_dof"] == 6
    assert contract["gripper_physical_dof"] == 2
    assert contract["virtual_seventh_revolute_joint_forbidden"] is True
    assert contract["stages"]["FAR_APPROACH_5D"]["task_dimension"] == 5
    assert contract["stages"]["FINAL_ALIGNMENT_6D"]["task_dimension"] == 6
    assert contract["stages"]["GRIPPER_OPERATION_2P"]["joint_type_exact"] == "prismatic"
    assert contract["task_dimension_contract_complete"] is True
    assert contract["task_contract_complete"] is False
    assert contract["task_space_metric_contract"]["status"] == "UNBOUND"
    assert contract["task_space_metric_contract"][
        "mixed_linear_angular_svd_or_residual_credit_allowed"
    ] is False


def test_joint_limit_guard_fails_closed_at_boundary() -> None:
    limits = np.array([[-1.0, 1.0], [0.0, 0.1]])
    with pytest.raises(ValueError, match="JOINT_AT_OR_OUTSIDE_LIMIT_FAIL_CLOSED"):
        validate_joint_state_fail_closed([1.0, 0.05], limits)
    state, margins = validate_joint_state_fail_closed([0.0, 0.05], limits)
    assert state.shape == (2,)
    assert np.all(margins > 0.0)


def test_singularity_guard_fails_closed_on_rank_loss() -> None:
    matrix = np.zeros((5, 6))
    guard = singularity_guard(matrix, 5, 1e-4, 1e-9)
    assert guard["allow"] is False
    assert "TASK_RANK_MISMATCH" in guard["reason"]
    assert "SIGMA_BELOW_AUTHORIZED_THRESHOLD" in guard["reason"]


def test_precontact_generalized_jacobian_comparison_is_bounded(built: dict) -> None:
    gate = built["precontact_gate"]
    assert gate["candidate_packaging_pass"] is False
    assert gate["precontact_tracking_validated"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["determinism"]["bitwise_canonical_equal"] is True
    first = gate["first"]
    assert first["backend_advance_executed"] is False
    assert first["collision_or_path_query_executed"] is False
    assert first["checks"]["task_space_unit_metric_bound"] is False
    for task in first["tasks"]:
        assert task["command_emitted"] is False
        assert task["diagnostic_reference_rate_computed"] is True
        assert task["guard"]["allow"] is False
        assert task["guard"]["reason"] == "TASK_SPACE_UNIT_METRIC_UNBOUND_FAIL_CLOSED"
        assert task["guard"]["raw_mixed_unit_diagnostic"]["allow"] is True
        assert task["metric_semantics"]["unit_invariant"] is False
        assert task["metric_semantics"]["credit"] is False
        assert (
            task["free_floating_mass_weighted_dls"][
                "raw_mixed_unit_actual_task_residual_norm_no_credit"
            ]
            < task["fixed_base_naive"][
                "raw_mixed_unit_actual_task_residual_norm_no_credit"
            ]
        )
        assert task["hardware_rate_limit_checked"] is False
        assert task["hardware_torque_limit_checked"] is False
        assert task["base_reaction_tradeoff"][
            "selected_reduces_angular_rate_vs_naive"
        ] is False


def test_task_nullity_is_one_only_for_five_d(built: dict) -> None:
    tasks = {row["task"]: row for row in built["precontact_gate"]["first"]["tasks"]}
    assert tasks["FAR_APPROACH_5D"]["nullspace"]["dimension"] == 1
    assert tasks["FAR_APPROACH_5D"]["nullspace"]["allowed"] is True
    assert tasks["FINAL_ALIGNMENT_6D"]["nullspace"]["dimension"] == 0
    assert tasks["FINAL_ALIGNMENT_6D"]["nullspace"]["allowed"] is False
    assert tasks["FAR_APPROACH_5D"]["task_angular_semantics"].startswith(
        "TOOL_Z_AXIS_RATE"
    )
    assert tasks["FAR_APPROACH_5D"]["metric_semantics"]["angular_rows"] == "1/s"
    assert tasks["FINAL_ALIGNMENT_6D"]["metric_semantics"]["angular_rows"] == "rad/s"


def test_unbound_task_metric_cannot_grant_singularity_or_tracking_credit(
    built: dict,
) -> None:
    config = load_json_strict(CONFIG_PATH)
    assert config["task_space_metric"]["status"] == "UNBOUND"
    assert config["task_space_metric"]["characteristic_length_m"] is None
    assert config["task_space_metric"]["weighting_matrix"] is None
    gate = built["precontact_gate"]
    assert "TASK_SPACE_UNIT_METRIC_OR_CHARACTERISTIC_LENGTH_NOT_FROZEN" in gate[
        "reason_not_validated"
    ]
    assert gate["candidate_packaging_pass"] is False
    assert all(
        task["status"].startswith("HOLD_TASK_SPACE_UNIT_METRIC_UNBOUND")
        for task in gate["first"]["tasks"]
    )


def test_ctrl01_ledger_preserves_repeat_and_evidence_classes(built: dict) -> None:
    ledger = built["causal_ledger"]
    assert ledger["source_verdict"] == "REPEAT"
    assert ledger["source_negative_result_retained"] is True
    assert ledger["current_tree_replay"]["status"] == "HOLD_CURRENT_REPLAY"
    assert ledger["current_tree_replay"]["exact_legacy_reproduction_claimed"] is False
    assert ledger["causal_certification_complete"] is False
    by_cause = {row["candidate_cause"]: row for row in ledger["entries"]}
    assert by_cause["GAIN_SELECTION"]["evidence_class"] == "UNTESTED_HYPOTHESIS"
    assert by_cause["FIXED_BASE_JACOBIAN_USED_FOR_FREE_FLOATING_PLANT"]["evidence_class"] == "BOUNDED_ARCHITECTURE_INFERENCE"


def test_flex_gate_is_interface_only_and_provisional(built: dict) -> None:
    gate = built["flex_gate"]
    assert gate["candidate_packaging_pass"] is True
    assert gate["trajectory_shaper_coefficients_emitted"] is False
    assert gate["mission_time_history_executed"] is False
    assert gate["flex_robustness_validated"] is False
    assert gate["next_stage_authorized"] is False
    assert len(gate["corner_catalog"]) == 3
    assert all(row["mode_count_per_wing"] == 7 for row in gate["corner_catalog"])


def test_supervisor_is_fail_closed_interface_only(built: dict) -> None:
    contract = load_json_strict(SUPERVISOR_CONTRACT_PATH)
    assessment = built["supervisor_assessment"]
    assert contract["base_attitude_and_momentum"]["unknown_input_transition"] == "ABORT"
    assert contract["hybrid_capture"]["unknown_transition"] == "ABORT"
    assert contract["base_attitude_and_momentum"]["operational"] is False
    assert contract["hybrid_capture"]["operational"] is False
    assert assessment["operational_supervisor_complete"] is False
    assert assessment["safe"]["operational_authorization"] is False


def test_final_gate_has_native_aggregation_booleans_and_holds(built: dict) -> None:
    gate = built["control_gate"]
    expected = {
        "candidate_package_complete": False,
        "control_engineering_complete": False,
        "collision_constrained_tracking_valid": False,
        "hardware_valid": False,
        "safe_review_pass": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    for key, value in expected.items():
        assert type(gate[key]) is bool
        assert gate[key] is value
    assert gate["artifact_package_generated"] is True
    assert len(gate["hard_blockers"]) >= 8
    assert "TASK_SPACE_UNIT_METRIC_OR_CHARACTERISTIC_LENGTH_NOT_FROZEN" in gate[
        "hard_blockers"
    ]
    criteria = {row["id"]: row for row in gate["criteria"]}
    assert criteria["CG4"]["candidate_packaging_pass"] is False
    assert criteria["CG7"]["candidate_packaging_pass"] is False
    assert len(gate["unknowns"]) >= 5
    assert all(value is False for value in gate["execution_guards"].values())


def test_result_json_is_strict_and_manifest_exact(built: dict) -> None:
    json_files = sorted(RESULTS_DIR.glob("*.json"))
    assert len(json_files) == 6
    for path in json_files:
        assert isinstance(load_json_strict(path), dict)
    manifest_path = RESULTS_DIR / "R2_CONTROL_ENGINEERING_SHA256_V1.csv"
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    actual_files = sorted(
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
        and path != manifest_path
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    )
    assert [row["path"] for row in rows] == [
        path.relative_to(PACKAGE_ROOT).as_posix() for path in actual_files
    ]
    for row, path in zip(rows, actual_files, strict=True):
        assert int(row["bytes"]) == path.stat().st_size
        assert row["sha256"] == sha256_file(path)
