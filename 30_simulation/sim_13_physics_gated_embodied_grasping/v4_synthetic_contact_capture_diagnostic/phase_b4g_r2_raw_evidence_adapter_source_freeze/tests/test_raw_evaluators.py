from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from r2_raw_adapter.adapter import (
    AdapterError,
    OUTCOME_A0,
    OUTCOME_COMMON,
    OUTCOME_NO_REMOVAL,
    derive_common_propagation_observation,
    derive_fresh_acquisition_observation,
    evaluate_a0_bookend_pair,
    evaluate_common_propagation_raw_triplet,
    evaluate_fresh_acquisition_raw_triplet,
    evaluate_fresh_alpha16_raw,
    evaluate_g12_raw_pair,
    load_bound_case,
)
from r2_raw_adapter.fixture_factory import write_case


def _load(root: Path, **kwargs):
    return load_bound_case(root, write_case(root, **kwargs))


def test_fresh_observation_is_derived_from_arrays_and_reverse_bound(tmp_path: Path) -> None:
    case = _load(tmp_path, horizon_s=0.0006, command_duration_s=0.01)
    observation = derive_fresh_acquisition_observation(case)
    assert observation["channels"]["service_position_m"] == case.arrays["service_state_29"][0, :3].tolist()
    assert observation["raw_binding"]["npz_sha256"] == case.npz_sha256
    assert observation["raw_binding"]["array_contract_sha256"] == case.array_contract_sha256


def test_g04_g06_recomputed_and_actual_fractional_dt_passes_candidate(tmp_path: Path) -> None:
    case = _load(tmp_path, horizon_s=0.0006)
    result = evaluate_fresh_alpha16_raw(case)
    assert result["passed"] is False
    assert result["source_only_candidate_predicate_pass"] is False
    assert result["g04_g06_raw_subpredicates_pass"] is True
    assert result["full_raw_integrity_recomputed"] is False
    assert result["g04"]["scientific_predicate"] is True
    assert result["g06"]["scientific_predicate"] is True
    assert result["g06"]["last_interval_s"] < result["g06"]["nominal_max_step_s"]


def test_g04_terminal_cancellation_and_reported_power_forgery_killed(tmp_path: Path) -> None:
    def cancel(arrays: dict[str, np.ndarray]) -> None:
        arrays["signed_W_act_J"][1] += 1e-3
    result = evaluate_fresh_alpha16_raw(_load(tmp_path, array_mutator=cancel))
    assert result["g04_g06_raw_subpredicates_pass"] is False
    other = tmp_path / "other"
    result = evaluate_fresh_alpha16_raw(_load(other, array_mutator=lambda a: a["sample_power_reported_W"].__setitem__(1, 99.0)))
    assert result["g04_g06_raw_subpredicates_pass"] is False


def test_g06_delta_t_shortcut_without_stage_work_provenance_killed(tmp_path: Path) -> None:
    result = evaluate_fresh_alpha16_raw(_load(tmp_path, array_mutator=lambda a: a["stage_augmented_W_act_J"].fill(0.0)))
    assert result["source_only_candidate_predicate_pass"] is False
    assert result["g06"]["independent_work_state_provenance_pass"] is False


def test_alpha16_no_removal_still_recomputes_active_g04_g06(tmp_path: Path) -> None:
    case = _load(tmp_path, outcome=OUTCOME_NO_REMOVAL, horizon_s=0.08)
    result = evaluate_fresh_alpha16_raw(case)
    assert result["raw_recomputation_completed"] is True
    assert result["finite_removal_present"] is False
    assert result["g04"]["scientific_predicate"] is True
    assert result["g06"]["scientific_predicate"] is True
    assert result["source_only_candidate_predicate_pass"] is False


def test_fresh_acquisition_and_common_triplets_call_frozen_metrics(tmp_path: Path) -> None:
    fresh = []
    common = []
    for index, step in enumerate((0.00025, 0.000125, 0.0000625)):
        fresh.append(_load(tmp_path / f"f{index}", step_s=step, horizon_s=0.0005, command_duration_s=0.01))
        common.append(_load(tmp_path / f"c{index}", step_s=step, horizon_s=0.005, command_duration_s=0.005, outcome=OUTCOME_COMMON))
    f_result = evaluate_fresh_acquisition_raw_triplet(fresh)
    c_result = evaluate_common_propagation_raw_triplet(common)
    assert f_result["source_only_candidate_predicate_pass"] is True and f_result["passed"] is False
    assert c_result["source_only_candidate_predicate_pass"] is True and c_result["passed"] is False
    assert len(derive_common_propagation_observation(common[0])["time_grid_s"]) == 21
    assert derive_common_propagation_observation(common[0])["time_grid_s"][0] == 0.0
    assert derive_common_propagation_observation(common[0])["time_grid_s"][-1] == 0.005


def test_common_triplet_detects_interior_common_sample_divergence(tmp_path: Path) -> None:
    common = []
    for index, step in enumerate((0.00025, 0.000125, 0.0000625)):
        mutator = None
        if step == 0.0000625:
            mutator = lambda arrays: arrays["service_state_29"].__setitem__((4, 0), 1000.0)
        common.append(_load(
            tmp_path / str(index), step_s=step, horizon_s=0.005,
            command_duration_s=0.005, outcome=OUTCOME_COMMON,
            array_mutator=mutator,
        ))
    result = evaluate_common_propagation_raw_triplet(common)
    assert result["raw_triplet_binding_evaluable"] is True
    assert result["source_only_candidate_predicate_pass"] is False


def test_common_raw_is_exactly_bound_to_frozen_donor_initial_projection(tmp_path: Path) -> None:
    relative = write_case(
        tmp_path,
        outcome=OUTCOME_COMMON,
        horizon_s=0.005,
        command_duration_s=0.005,
        array_mutator=lambda arrays: arrays["service_state_29"].__setitem__((0, 0), 100.0),
    )
    with pytest.raises(AdapterError, match="INITIAL_STATE_NOT_EXACT_FROZEN_DONOR"):
        load_bound_case(tmp_path, relative)


def test_alpha16_does_not_upgrade_partial_work_checks_to_full_integrity(tmp_path: Path) -> None:
    mutations = (
        lambda arrays: arrays["command_Q_14"].__setitem__((0, 0), 999.0),
        lambda arrays: arrays["contact_force_N"].__setitem__(0, 999.0),
        lambda arrays: arrays["total_linear_momentum_N_s"].__setitem__((1, 0), 999.0),
    )
    for index, mutation in enumerate(mutations):
        result = evaluate_fresh_alpha16_raw(_load(tmp_path / str(index), array_mutator=mutation))
        assert result["g04_g06_raw_subpredicates_pass"] is True
        assert result["source_only_candidate_predicate_pass"] is False
        assert result["full_raw_integrity_recomputed"] is False


def test_common_raw_cannot_claim_fresh_credit(tmp_path: Path) -> None:
    common = _load(tmp_path, outcome=OUTCOME_COMMON, horizon_s=0.005, command_duration_s=0.005)
    try:
        derive_fresh_acquisition_observation(common)
    except Exception as exc:
        assert "FRESH_RAW_CASE_REQUIRED" in str(exc)
    else:
        raise AssertionError("COMMON raw received fresh credit")


def test_a0_bookend_exact_zero_projection_pair(tmp_path: Path) -> None:
    pre = _load(tmp_path, outcome=OUTCOME_A0, horizon_s=0.0005, bookend_sentinel="PRE")
    post = _load(tmp_path, outcome=OUTCOME_A0, horizon_s=0.0005, bookend_sentinel="POST")
    result = evaluate_a0_bookend_pair(pre, post)
    assert result["source_only_candidate_predicate_pass"] is True
    assert result["passed"] is False


def test_a0_pair_digest_covers_gap_and_stage_arrays(tmp_path: Path) -> None:
    mutations = (
        lambda arrays: arrays["left_gap_m"].__setitem__(0, 999.0),
        lambda arrays: arrays["stage_gap_jacobian_P"].__setitem__((0, 0, 0), 999.0),
    )
    for index, mutation in enumerate(mutations):
        pre = _load(tmp_path / str(index) / "pre", outcome=OUTCOME_A0, horizon_s=0.0005, bookend_sentinel="PRE")
        post = _load(
            tmp_path / str(index) / "post", outcome=OUTCOME_A0,
            horizon_s=0.0005, bookend_sentinel="POST", array_mutator=mutation,
        )
        result = evaluate_a0_bookend_pair(pre, post)
        assert result["raw_pair_binding_evaluable"] is True
        assert result["source_only_candidate_predicate_pass"] is False


def _g12_pair(root: Path, *, rk_outcome="FINITE_BILATERAL_REMOVAL_OBSERVED", mp_outcome="FINITE_BILATERAL_REMOVAL_OBSERVED", rk_mutator=None, mp_mutator=None):
    rk_horizon = 0.08 if rk_outcome == OUTCOME_NO_REMOVAL else 0.000125
    mp_horizon = 0.08 if mp_outcome == OUTCOME_NO_REMOVAL else 0.000125
    rk = _load(root / "rk", method="rk4", step_s=0.0000625, horizon_s=rk_horizon, outcome=rk_outcome, array_mutator=rk_mutator)
    mp = _load(root / "mp", method="midpoint", step_s=0.0000625, horizon_s=mp_horizon, outcome=mp_outcome, array_mutator=mp_mutator)
    return evaluate_g12_raw_pair(rk, mp)


def test_g12_finite_pair_is_raw_candidate_but_never_source_freeze_pass(tmp_path: Path) -> None:
    result = _g12_pair(tmp_path)
    assert result["partial_post_checks_pass"] is True
    assert all(result["raw_pair_subpredicates"].values())
    assert result["source_only_candidate_predicate_pass"] is False
    assert result["full_raw_integrity_recomputed"] is False
    assert result["passed"] is False and result["eligible"] is False


def test_g12_one_side_finite_is_fail_and_both_no_event_is_not_eligible(tmp_path: Path) -> None:
    one = _g12_pair(tmp_path / "one", mp_outcome=OUTCOME_NO_REMOVAL)
    assert one["evaluation_status"] == "FAIL_G12_ONE_SIDE_FINITE_ONE_SIDE_NO_EVENT"
    both = _g12_pair(tmp_path / "both", rk_outcome=OUTCOME_NO_REMOVAL, mp_outcome=OUTCOME_NO_REMOVAL)
    assert both["evaluation_status"].startswith("NOT_APPLICABLE_G12")
    assert both["eligible"] is False


def test_g12_recomputes_post_domain_clearance_zero_jump_and_work(tmp_path: Path) -> None:
    def move_post_p_outside(arrays: dict[str, np.ndarray]) -> None:
        arrays["post_stage_P_coordinates_m"][0, 0] = 0.08
        arrays["post_stage_service_state_29"][0, 13] = 0.08

    mutations = [
        lambda a: a["post_stage_domain_and_sign_pass"].__setitem__(0, False),
        move_post_p_outside,
        lambda a: a["post_stage_gap_jacobian_P"].__setitem__((0, 0, 0), -1.0),
        lambda a: a["post_left_gap_m"].fill(-1e-4),
        lambda a: a["post_service_state_29"].__setitem__((0, 0), 99.0),
        lambda a: a["post_signed_W_act_J"].__setitem__(0, 99.0),
        lambda a: a["post_command_Q_14"].__setitem__((0, 0), 1.0),
    ]
    for index, mutation in enumerate(mutations):
        result = _g12_pair(tmp_path / str(index), rk_mutator=mutation)
        assert result["source_only_candidate_predicate_pass"] is False


def test_partial_post_subset_applies_frozen_gap_and_rate_thresholds(tmp_path: Path) -> None:
    def gap_below_threshold(arrays: dict[str, np.ndarray]) -> None:
        arrays["post_left_gap_m"].fill(5.0e-7)
        arrays["left_gap_m"][-1] = 5.0e-7

    def rate_below_threshold(arrays: dict[str, np.ndarray]) -> None:
        arrays["post_left_gap_rate_m_s"].fill(-2.0e-6)
        arrays["left_gap_rate_m_s"][-1] = -2.0e-6

    for index, mutation in enumerate((gap_below_threshold, rate_below_threshold)):
        result = _g12_pair(tmp_path / str(index), rk_mutator=mutation)
        assert result["partial_post_checks_pass"] is False
        assert result["source_only_candidate_predicate_pass"] is False
        assert result["full_raw_integrity_recomputed"] is False


def test_saved_post_P_closed_domain_endpoints_are_legal_but_stage_remains_centered(tmp_path: Path) -> None:
    def saved_endpoint_values(arrays: dict[str, np.ndarray]) -> None:
        arrays["post_service_state_29"][:, 13] = 0.0
        arrays["post_service_state_29"][:, 14] = 0.0715
        arrays["service_state_29"][-1, 13] = 0.0
        arrays["service_state_29"][-1, 14] = 0.0715

    result = _g12_pair(tmp_path, rk_mutator=saved_endpoint_values)
    assert result["rk4"]["post_raw_subset_predicates"]["saved_P_closed_domain"] is True
    assert result["rk4"]["post_raw_subset_predicates"]["stored_stage_domain_P_and_opening_sign_subset"] is True
    assert result["partial_post_checks_pass"] is True


def test_g12_missing_raw_remains_hold() -> None:
    result = evaluate_g12_raw_pair(None, None)
    assert result["evaluation_status"] == "HOLD_G12_MISSING_RAW_CASE"
