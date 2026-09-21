from __future__ import annotations

import math

import pytest

from sim13_v2.contact_preflight import (
    CollisionState,
    ContactAuthority,
    ContactReadinessInput,
    ContactState,
    FingerContact,
    LockReceipt,
    contact_release_allowed,
    evaluate_contact_readiness,
    half_sine_equal_impulse_fixture,
    sampled_half_sine_impulse,
    validate_contact_normal,
    validate_contact_window,
)
from sim13_v2.negative_controls import (
    ControlStatus,
    NegativeControlRecord,
    REGISTRY,
    evaluate_negative_controls,
)


HASH = "A" * 64
RELEASED = ContactAuthority("AUTHORITATIVE_RELEASED", HASH)
PROVISIONAL = ContactAuthority("PROVISIONAL", HASH)


def test_contact_normal_requires_finite_unit_vector_and_released_authority() -> None:
    assert validate_contact_normal((1.0, 0.0, 0.0), RELEASED).state is ContactState.PASS
    assert validate_contact_normal((0.0, 0.0, 0.0), RELEASED).state is ContactState.FAIL
    assert validate_contact_normal((2.0, 0.0, 0.0), RELEASED).state is ContactState.FAIL
    assert validate_contact_normal((math.nan, 0.0, 0.0), RELEASED).state is ContactState.FAIL
    assert validate_contact_normal((1.0, 0.0, 0.0), PROVISIONAL).state is ContactState.UNKNOWN


def test_contact_normal_is_not_silently_normalized() -> None:
    decision = validate_contact_normal((1.0 + 2.0e-9, 0.0, 0.0), RELEASED)
    assert decision.state is ContactState.FAIL
    assert decision.reason_codes == ("CONTACT_NORMAL_NOT_UNIT",)


@pytest.mark.parametrize("duration", [0.0, -0.02, math.nan, math.inf])
def test_contact_window_rejects_invalid_duration(duration: float) -> None:
    assert validate_contact_window(duration, RELEASED).state is ContactState.FAIL
    with pytest.raises(ValueError):
        half_sine_equal_impulse_fixture(1.0, duration)


def test_provisional_20_ms_window_remains_unknown() -> None:
    decision = validate_contact_window(0.020, PROVISIONAL)
    assert decision.state is ContactState.UNKNOWN
    assert decision.reason_codes == ("CONTACT_WINDOW_AUTHORITY_PROVISIONAL",)


def test_half_sine_fixture_preserves_signed_impulse() -> None:
    for impulse in (3.25, -0.75):
        audit = half_sine_equal_impulse_fixture(impulse, 0.020)
        assert audit.analytic_impulse_Ns == pytest.approx(impulse, abs=1.0e-15)
        assert audit.normalization_error_Ns == pytest.approx(0.0, abs=1.0e-15)
        sampled = sampled_half_sine_impulse(impulse, 0.020, intervals=20000)
        assert sampled == pytest.approx(impulse, rel=3.0e-9, abs=1.0e-12)
        assert "NOT_CONTINUOUS_CONTACT_BACKEND" in audit.model_scope


def _ready_input() -> ContactReadinessInput:
    return ContactReadinessInput(
        contacts=(
            FingerContact("left", 20.0, 2.0, 1000.0),
            FingerContact("right", 20.0, 2.0, 1000.0),
        ),
        friction_coefficient=0.3,
        pressure_limit_Pa=2000.0,
        retention_force_required_N=30.0,
        lock_receipt=LockReceipt(HASH, 0.01, 0.05, True),
        geometry_authority=RELEASED,
        material_authority=RELEASED,
        collision_state=CollisionState.CLEAR_EVALUATED,
    )


def test_local_contact_preflight_pass_does_not_release_system() -> None:
    decision = evaluate_contact_readiness(_ready_input())
    assert decision.state is ContactState.PASS
    assert contact_release_allowed(
        decision,
        system_binding_passed=True,
        runtime_gate_passed=True,
        dynamics_gate_passed=False,
    ) is False


def test_collision_unknown_is_not_clear() -> None:
    data = _ready_input()
    data = ContactReadinessInput(
        **{**data.__dict__, "collision_state": CollisionState.UNKNOWN_NOT_EVALUATED}
    )
    decision = evaluate_contact_readiness(data)
    assert decision.state is ContactState.UNKNOWN
    assert "COLLISION_UNKNOWN_NOT_EVALUATED" in decision.reason_codes


@pytest.mark.parametrize(
    ("mutation", "token"),
    [
        ({"contacts": (FingerContact("left", 20.0, 2.0, 1000.0),)}, "DUAL_FINGER"),
        ({"friction_coefficient": None}, "FRICTION_COEFFICIENT"),
        ({"pressure_limit_Pa": None}, "PRESSURE_LIMIT"),
        ({"retention_force_required_N": None}, "RETENTION_REQUIREMENT"),
        ({"lock_receipt": None}, "LOCK_RECEIPT_ABSENT"),
        ({"lock_receipt": LockReceipt(HASH, 0.10, 0.05, True)}, "LOCK_RECEIPT_STALE"),
    ],
)
def test_missing_contact_evidence_never_passes(mutation: dict, token: str) -> None:
    baseline = _ready_input()
    data = ContactReadinessInput(**{**baseline.__dict__, **mutation})
    decision = evaluate_contact_readiness(data)
    assert decision.state is not ContactState.PASS
    assert any(token in reason for reason in decision.reason_codes)


def test_contact_load_failures_are_detected() -> None:
    baseline = _ready_input()
    contacts = (
        FingerContact("left", 10.0, 4.0, 2500.0),
        FingerContact("right", 10.0, 4.0, 2500.0),
    )
    decision = evaluate_contact_readiness(
        ContactReadinessInput(**{**baseline.__dict__, "contacts": contacts})
    )
    assert decision.state is ContactState.FAIL
    assert any("FRICTION_CONE_VIOLATION" in reason for reason in decision.reason_codes)
    assert any("PRESSURE_LIMIT_EXCEEDED" in reason for reason in decision.reason_codes)
    assert "RETENTION_FORCE_MARGIN_NEGATIVE" in decision.reason_codes


def test_negative_control_registry_is_exact_nc01_to_nc20() -> None:
    assert [spec.control_id for spec in REGISTRY] == [f"NC{index:02d}" for index in range(1, 21)]


def test_unexecuted_controls_are_never_counted_as_pass() -> None:
    summary = evaluate_negative_controls(())
    assert summary.total == 20
    assert summary.executed == 0
    assert summary.passed == 0
    assert summary.deferred == 1
    assert summary.not_run_executable == 19
    assert summary.all_controls_passed is False
    assert summary.contact_release_eligible is False


def _passing_record(control_id: str, outcome: str) -> NegativeControlRecord:
    return NegativeControlRecord(
        control_id=control_id,
        executed=True,
        observed_outcome=outcome,
        non_abort_execution_count=0,
        exact_reason_match=True,
        deterministic_repeat=True,
        baseline_hash_unchanged=True,
    )


def test_dependency_hold_cannot_be_hidden_by_other_passes() -> None:
    records = [
        _passing_record(spec.control_id, spec.canonical_outcome)
        for spec in REGISTRY
        if spec.control_id != "NC19"
    ]
    summary = evaluate_negative_controls(records)
    assert summary.executed == 19
    assert summary.passed == 19
    assert summary.deferred == 1
    assert summary.all_controls_passed is False
    assert summary.results[18].status is ControlStatus.NOT_RUN_DEPENDENCY_HOLD


def test_one_failed_invariant_fails_a_record() -> None:
    spec = REGISTRY[0]
    record = NegativeControlRecord(
        control_id=spec.control_id,
        executed=True,
        observed_outcome=spec.canonical_outcome,
        non_abort_execution_count=1,
        exact_reason_match=True,
        deterministic_repeat=True,
        baseline_hash_unchanged=True,
    )
    summary = evaluate_negative_controls((record,))
    assert summary.failed == 1
    assert summary.results[0].status is ControlStatus.FAIL


def test_unknown_or_duplicate_negative_control_records_are_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_negative_controls((NegativeControlRecord("NC99", False),))
    with pytest.raises(ValueError):
        evaluate_negative_controls(
            (NegativeControlRecord("NC01", False), NegativeControlRecord("NC01", False))
        )
