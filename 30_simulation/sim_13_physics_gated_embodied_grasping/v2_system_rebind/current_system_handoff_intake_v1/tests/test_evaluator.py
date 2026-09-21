from __future__ import annotations

from current_handoff.evaluator import evaluate_default_snapshot
from current_handoff.schema import FROZEN_BINDING_DIGEST, MANDATORY_FALSE, PROMOTION_STAGES, REQUIRED_ABSENT_PATHS


def test_current_status_and_ceiling_are_capped():
    result = evaluate_default_snapshot()
    assert result["current_intake_status"] == "HOLD_INCOMPLETE"
    assert result["theoretical_ceiling"] == "INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION"
    assert result["gate_ceiling"] == "PASS_SOURCE_FREEZE_ONLY"


def test_all_checks_pass_and_do_not_promote_science():
    result = evaluate_default_snapshot()
    assert result["source_only_validation_pass"] is True
    assert len(result["checks"]) == 19
    assert all(result["checks"].values())


def test_every_mandatory_output_is_false():
    flags = evaluate_default_snapshot()["flags"]
    assert tuple(flags) == MANDATORY_FALSE
    assert all(flags[name] is False for name in MANDATORY_FALSE)


def test_promotion_sequence_exact_and_unexecuted():
    sequence = evaluate_default_snapshot()["promotion_sequence"]
    assert [item["stage"] for item in sequence] == list(PROMOTION_STAGES)
    assert all(item["state"] == "HOLD_NOT_EXECUTED" and item["self_authorized"] is False for item in sequence)


def test_hard_negative_e15_preserved():
    e15 = evaluate_default_snapshot()["preserved_hard_negatives"]["e15"]
    assert e15["max_cross_solver_relative_difference"] == 0.05637349419858036
    assert e15["gate_limit"] == 0.05
    assert e15["status"] == "REPEAT_ANCF_CERTIFICATION"


def test_hard_negative_harness_g12_preserved():
    harness = evaluate_default_snapshot()["preserved_hard_negatives"]["harness"]
    assert harness == {
        "handoff_g12": "FAIL",
        "handoff_passed": 11,
        "handoff_total": 12,
        "safe_key_states": 0,
        "required_key_states": 10,
        "released_trajectories": 0,
        "required_trajectories": 8,
    }


def test_route_c_p01_p13_preserved():
    route_c = evaluate_default_snapshot()["preserved_hard_negatives"]["route_c_physical_registry"]
    assert route_c["available"] == 0
    assert route_c["non_null"] == 0
    assert route_c["hold"] == route_c["total"] == 13
    assert route_c["route_b_seed_inheritance_allowed"] is False


def test_presence_does_not_equal_eligibility():
    domains = evaluate_default_snapshot()["domains"]
    assert all(domain["presence"] is True for domain in domains.values())
    assert all(domain["eligible"] is False for domain in domains.values())


def test_exact_absent_paths_and_source_locked_binding_digest_are_emitted():
    result = evaluate_default_snapshot()
    assert tuple(result["required_absent_paths"]) == REQUIRED_ABSENT_PATHS
    assert result["frozen_binding_digest"] == FROZEN_BINDING_DIGEST
