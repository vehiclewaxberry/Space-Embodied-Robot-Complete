from __future__ import annotations

import hashlib
import itertools
import json

import pytest


LANE_ORDER = [
    "RK4_COARSE",
    "RK4_FINE",
    "RK4_REFERENCE",
    "MIDPOINT_COARSE",
    "MIDPOINT_FINE",
    "MIDPOINT_REFERENCE",
]


def _key(seed: int, lane_id: str, arm: str, case_id: str) -> str:
    payload = f"{seed}|{lane_id}|{arm}|{case_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _alpha_token(alpha: float) -> str:
    if alpha == 0.5:
        return "0P5"
    assert float(alpha).is_integer()
    return str(int(alpha))


def test_registered_schedule_counts_and_global_order_are_exact(contracts):
    schedule = contracts["schedule"]
    assert schedule["lane_order"] == LANE_ORDER
    assert schedule["slot_count"] == len(schedule["slots"]) == 144
    assert schedule["a0_slot_count"] == 12
    assert schedule["a1_slot_count"] == 108
    assert schedule["a2_slot_count"] == 24
    assert [slot["slot_index"] for slot in schedule["slots"]] == list(range(144))
    assert [slot["arm"] for slot in schedule["slots"]].count("A0") == 12
    assert [slot["arm"] for slot in schedule["slots"]].count("A1") == 108
    assert [slot["arm"] for slot in schedule["slots"]].count("A2") == 24


def test_registered_counts_match_run_spec(contracts):
    registered = contracts["run_spec"]["registered_slots"]
    schedule = contracts["schedule"]
    assert registered["lane_count"] == len(LANE_ORDER) == 6
    assert registered["total_slots"] == schedule["slot_count"] == 144
    assert registered["a0_executions"] == schedule["a0_slot_count"] == 12
    assert registered["a1_executions"] == schedule["a1_slot_count"] == 108
    assert registered["a2_executions_if_parent_exists"] == schedule["a2_slot_count"] == 24
    assert registered["numerical_lanes_are_hardware_replicates"] is False


def test_schedule_slots_canonical_sha256_is_frozen(contracts):
    schedule = contracts["schedule"]
    canonical = json.dumps(
        schedule["slots"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest().upper() == schedule["slots_sha256"]
    assert schedule["slots_sha256"] == (
        "21642ED06620E589ABB854CCFE936EC2C84D9571ACACA86F690ACC5DB2D78137"
    )


@pytest.mark.parametrize("lane_id", LANE_ORDER)
def test_every_lane_has_frozen_pre_a1_a2_post_structure(contracts, lane_id):
    slots = [slot for slot in contracts["schedule"]["slots"] if slot["lane_id"] == lane_id]
    assert len(slots) == 24
    assert slots[0]["arm"] == "A0"
    assert slots[0]["sentinel_position"] == "PRE"
    assert slots[0]["case_id"] == f"{lane_id}__A0__PRE"
    assert [slot["arm"] for slot in slots[1:19]] == ["A1"] * 18
    assert [slot["arm"] for slot in slots[19:23]] == ["A2"] * 4
    assert slots[23]["arm"] == "A0"
    assert slots[23]["sentinel_position"] == "POST"
    assert slots[23]["case_id"] == f"{lane_id}__A0__POST"


@pytest.mark.parametrize("lane_id", LANE_ORDER)
def test_a1_is_exact_registered_full_factorial_per_lane(contracts, lane_id):
    slots = [
        slot
        for slot in contracts["schedule"]["slots"]
        if slot["lane_id"] == lane_id and slot["arm"] == "A1"
    ]
    expected = set(itertools.product([0.5, 1, 2, 4, 8, 16], [0.005, 0.01, 0.02]))
    assert {(slot["alpha"], slot["command_duration_s"]) for slot in slots} == expected
    for slot in slots:
        alpha = _alpha_token(slot["alpha"])
        duration_ms = int(round(1000 * slot["command_duration_s"]))
        assert slot["case_id"] == (
            f"{lane_id}__A1__ALPHA_{alpha}__TCMD_MS_{duration_ms}"
        )
        assert slot["execution_condition"] == "ALWAYS"


@pytest.mark.parametrize("lane_id", LANE_ORDER)
@pytest.mark.parametrize("arm", ["A1", "A2"])
def test_a1_and_a2_keyed_sha_values_and_sort_order(contracts, lane_id, arm):
    schedule = contracts["schedule"]
    slots = [
        slot
        for slot in schedule["slots"]
        if slot["lane_id"] == lane_id and slot["arm"] == arm
    ]
    for slot in slots:
        assert slot["permutation_key_sha256"] == _key(
            schedule["seed"], lane_id, arm, slot["case_id"]
        )
    keys = [slot["permutation_key_sha256"] for slot in slots]
    assert keys == sorted(keys)


@pytest.mark.parametrize("lane_id", LANE_ORDER)
def test_a2_variants_and_conditional_records_are_exact(contracts, lane_id):
    slots = [
        slot
        for slot in contracts["schedule"]["slots"]
        if slot["lane_id"] == lane_id and slot["arm"] == "A2"
    ]
    assert {slot["variant_id"] for slot in slots} == {
        "RIGHT_HALF_DELAY",
        "LEFT_HALF_DELAY_MIRROR",
        "RIGHT_COMMAND_OFF",
        "LEFT_COMMAND_OFF_MIRROR",
    }
    for slot in slots:
        assert slot["execution_condition"] == (
            "IF_REFERENCE_ELIGIBLE_A1_PARENT_ELSE_NOT_EVALUATED_RECORD"
        )
        assert slot["case_id"] == (
            f"{lane_id}__A2__{slot['variant_id']}__PARENT_SELECTED_BY_FROZEN_RULE"
        )


def test_lane_methods_and_steps_match_run_spec(contracts):
    expected = {
        lane["lane_id"]: (lane["method"], lane["step_s"])
        for lane in contracts["run_spec"]["lanes"]
    }
    assert list(expected) == LANE_ORDER
    for slot in contracts["schedule"]["slots"]:
        assert (slot["method"], slot["step_s"]) == expected[slot["lane_id"]]


def test_case_ids_and_permutation_keys_are_unique(contracts):
    slots = contracts["schedule"]["slots"]
    assert len({slot["case_id"] for slot in slots}) == len(slots)
    permuted = [slot["permutation_key_sha256"] for slot in slots if slot["arm"] != "A0"]
    assert len(set(permuted)) == len(permuted) == 132


def test_a0_time_disambiguation_is_explicit_and_cannot_gain_release_credit(contracts):
    time = contracts["run_spec"]["time_semantics"]
    assert time["active_duration_after_each_acquisition_s"] == 0.08
    assert time["case_end_time"] == "t_acquisition+0.08_s"
    assert time["a0_exact_replay_common_interval"] == "[t_acquisition,0.08_s_absolute]"
    assert time["a0_after_common_interval"] == (
        "continue the same zero-input forced-path implementation to t_acquisition+0.08_s"
    )
    assert time["a0_extension_is_new_release_credit"] is False
    assert time["post_result_extension_forbidden"] is True


def test_each_slot_must_reconstruct_fresh_acquisition_without_shared_times(contracts):
    freshness = contracts["run_spec"]["freshness"]
    assert freshness == {
        "every_executed_slot_reconstructs_its_own_first_qualifying_b3_event": True,
        "event_state_or_mutable_solver_state_cache_between_slots_forbidden": True,
        "common_reference_force_is_the_only_cross_slot_numeric_constant": True,
        "forced_shared_acquisition_or_removal_time_forbidden": True,
    }
    assert contracts["run_spec"]["run_order"]["hidden_state_between_runs_forbidden"] is True

