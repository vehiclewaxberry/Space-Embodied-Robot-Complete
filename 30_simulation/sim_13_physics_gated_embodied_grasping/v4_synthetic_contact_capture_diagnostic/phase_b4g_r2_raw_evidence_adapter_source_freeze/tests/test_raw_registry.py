from __future__ import annotations

from pathlib import Path

import numpy as np

from r2_raw_adapter.adapter import (
    OUTCOME_A0,
    OUTCOME_COMMON,
    OUTCOME_FINITE,
    derive_fresh_acquisition_observation,
    evaluate_fresh_acquisition_raw_triplet,
    evaluate_fresh_alpha16_raw,
    evaluate_g12_raw_pair,
    load_bound_case,
    validate_raw_registry_structure,
)
from r2_raw_adapter.fixture_factory import write_case
from r2_raw_adapter.schedule_binding import schedule_records


def _unique_nonphysical_tag(value: float):
    """Make fixture archives byte-unique without claiming physical execution."""

    def mutate(arrays: dict[str, np.ndarray]) -> None:
        arrays["target_state_13"][:, 0] += value
        arrays["post_target_state_13"][:, 0] += value
        arrays["post_stage_target_state_13"][:, 0] += value

    return mutate


def _write_registered_row(root: Path, row: dict, position: int):
    common = row["execution_family"] == "COMMON_PROP"
    a0 = row["arm"] == "A0"
    outcome = OUTCOME_A0 if a0 else OUTCOME_COMMON if common else OUTCOME_FINITE
    horizon = (
        2.0 * row["step_s"]
        if a0
        else row["command_duration_s"]
        if common
        else 2.0 * row["step_s"]
    )
    kwargs = {
        "case_id": row["case_id"],
        "method": row["method"],
        "step_s": row["step_s"],
        "outcome": outcome,
        "horizon_s": horizon,
        "bookend_sentinel": row["sentinel"] if a0 else "PRE",
        "array_mutator": None if a0 or common else _unique_nonphysical_tag((position + 1) * 1e-9),
    }
    if not a0:
        kwargs["alpha"] = row["alpha"]
        kwargs["command_duration_s"] = row["command_duration_s"]
    return load_bound_case(root, write_case(root, **kwargs))


def _full_registry(root: Path):
    rows, order = schedule_records()
    lookup = {row["case_id"]: row for row in rows}
    return [_write_registered_row(root, lookup[case_id], index) for index, case_id in enumerate(order)]


def test_full_78_registry_forms_every_frozen_analysis_view(tmp_path: Path) -> None:
    cases = _full_registry(tmp_path)
    result = validate_raw_registry_structure(cases)
    assert result["source_only_registry_valid"] is True
    assert result["case_count"] == 78
    assert result["a0_pair_count"] == 6
    assert result["fresh_acquisition_triplet_count"] == 2
    assert result["common_triplet_count"] == 6
    assert result["fresh_alpha16_raw_interface_count"] == 18
    assert result["g12_pair_count"] == 18
    assert result["trajectory_count"] == 0
    assert result["r2_numerical_preflight_executed"] is False

    multi = next(
        case for case in cases
        if case.sidecar["method"] == "rk4"
        and case.sidecar["step_s"] == 0.0000625
        and case.sidecar["alpha"] == 16.0
        and case.sidecar["command_duration_s"] == 0.01
    )
    counterpart = next(
        case for case in cases
        if case.sidecar["method"] == "midpoint"
        and case.sidecar["step_s"] == 0.0000625
        and case.sidecar["alpha"] == 16.0
        and case.sidecar["command_duration_s"] == 0.01
    )
    assert derive_fresh_acquisition_observation(multi)["case_id"] == multi.sidecar["case_id"]
    assert evaluate_fresh_alpha16_raw(multi)["raw_recomputation_completed"] is True
    assert evaluate_g12_raw_pair(multi, counterpart)["raw_pair_binding_evaluable"] is True


def test_full_registry_input_order_is_not_permutation_tolerant(tmp_path: Path) -> None:
    cases = _full_registry(tmp_path)
    cases[0], cases[1] = cases[1], cases[0]
    result = validate_raw_registry_structure(cases)
    assert result.get("source_only_registry_valid") is not True
    assert result["status"] == "HOLD_78_CASE_SET_ORDER_OR_PATH_UNIQUENESS_INVALID"


def test_triplet_rejects_same_case_reused_three_times(tmp_path: Path) -> None:
    case = load_bound_case(tmp_path, write_case(tmp_path, command_duration_s=0.01))
    result = evaluate_fresh_acquisition_raw_triplet([case, case, case])
    assert result.get("raw_triplet_binding_evaluable") is not True


def test_full_registry_rejects_a0_numeric_projection_or_zero_work_failure(tmp_path: Path) -> None:
    cases = _full_registry(tmp_path / "registry")
    rows, order = schedule_records()
    lookup = {row["case_id"]: row for row in rows}
    position = next(index for index, case_id in enumerate(order) if case_id.endswith("__A0__POST"))
    row = lookup[order[position]]
    replacement = load_bound_case(
        tmp_path / "mutant",
        write_case(
            tmp_path / "mutant",
            case_id=row["case_id"],
            method=row["method"],
            step_s=row["step_s"],
            outcome=OUTCOME_A0,
            horizon_s=2.0 * row["step_s"],
            bookend_sentinel="POST",
            array_mutator=lambda arrays: arrays["signed_W_act_J"].__setitem__(0, 1.0),
        ),
    )
    cases[position] = replacement
    result = validate_raw_registry_structure(cases)
    assert result["source_only_registry_valid"] is False
