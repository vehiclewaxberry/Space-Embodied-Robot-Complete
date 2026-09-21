from __future__ import annotations

from copy import deepcopy

from r2_preflight.evaluator import (
    aggregate_g12,
    evaluate_fresh_acquisition_records,
    evaluate_fresh_technical_repeats,
    evaluate_g12_pair,
    validate_common_propagation_campaign,
)
from r2_preflight.governance import (
    validate_a0_bookends,
    validate_global_78_registry,
    validate_governance_flags,
    validate_matrix_and_schedule,
)
from r2_preflight.negative_controls import (
    _common_records,
    _fresh_acq_records,
    _fresh_fixture,
    _fresh_registry_records,
    _g12_record,
    _governance_flags,
)
from r2_preflight.schedule import expand_matrix, fresh_a1_id, generate_schedule


def test_exact_matrix_and_schedule_production_validator() -> None:
    result = validate_matrix_and_schedule(expand_matrix(), generate_schedule())
    assert result["passed"] is True
    mutated = generate_schedule(); mutated[0], mutated[1] = mutated[1], mutated[0]
    assert validate_matrix_and_schedule(expand_matrix(), mutated)["passed"] is False


def test_fresh_acquisition_records_hold_without_future_raw(donor) -> None:
    records = _fresh_acq_records(donor, "rk4")
    result = evaluate_fresh_acquisition_records(records)
    assert result["source_only_metric_predicate_pass"] is True
    assert result["native_momentum_raw_verified"] is False
    assert result["passed"] is False
    assert result["status"] == "HOLD_FRESH_ACQ_NATIVE_MOMENTUM_RAW_NOT_VERIFIED_NO_EXECUTION"


def test_fresh_acquisition_forged_channel_or_ladder_rejected(donor) -> None:
    records = _fresh_acq_records(donor, "midpoint")
    forged = deepcopy(records)
    forged[1]["observation_payload"]["channels"]["service_position_m"][0] += 1.0
    from r2_preflight.strict_json import canonical_sha256
    forged[1]["observation_sha256"] = canonical_sha256(forged[1]["observation_payload"])
    assert evaluate_fresh_acquisition_records(forged)["passed"] is False
    assert "OBSERVATION" in evaluate_fresh_acquisition_records(forged)["status"]
    assert "EXACT_THREE" in evaluate_fresh_acquisition_records(records[:1])["status"]


def test_technical_repeat_exact_registered_binding(donor) -> None:
    lane = "RK4_H_MS_0P25"
    payloads = {}
    for duration in (5, 10, 20):
        row = next(row for row in expand_matrix() if row["case_id"] == fresh_a1_id(lane, 16, duration))
        payloads[duration] = _fresh_fixture(donor, row)[1]
    assert evaluate_fresh_technical_repeats(payloads)["passed"] is True
    same = {duration: deepcopy(payloads[10]) for duration in (5, 10, 20)}
    assert evaluate_fresh_technical_repeats(same)["passed"] is False


def test_common_eighteen_cross_case_identity_reuse_rejected(donor) -> None:
    held = validate_common_propagation_campaign(_common_records(donor))
    assert held["passed"] is False
    assert held["source_only_registry_structure_pass"] is True
    assert held["status"] == "HOLD_COMMON_PROP_EIGHTEEN_CASE_CAMPAIGN_RAW_NOT_VERIFIED_NO_EXECUTION"

    records = _common_records(donor)
    records[1]["fixture"] = records[0]["fixture"]
    records[1]["donor_hashes_before"] = records[0]["donor_hashes_before"]
    records[1]["donor_hashes_after"] = records[0]["donor_hashes_after"]
    result = validate_common_propagation_campaign(records)
    assert result["passed"] is False
    assert "IDENTITY" in result["status"]


def test_a0_fresh60_and_global78_registry(donor) -> None:
    fresh = _fresh_registry_records(donor)
    common = _common_records(donor)
    assert validate_a0_bookends(fresh)["passed"] is True
    result = validate_global_78_registry(fresh, common)
    assert result["passed"] is True
    assert result["fresh_count"] == 60 and result["common_count"] == 18
    assert result["trajectory_count"] == 0


def test_a0_numeric_mismatch_and_global_overlap_rejected(donor) -> None:
    fresh = _fresh_registry_records(donor)
    post = next(record for record in fresh if record["arm"] == "A0" and record["sentinel"] == "POST")
    post["a0_numeric_payload"]["state_payload"]["service_state_29"][0][0] = 1.0
    from r2_preflight.strict_json import canonical_sha256
    post["a0_numeric_payload_sha256"] = canonical_sha256(post["a0_numeric_payload"])
    assert validate_a0_bookends(fresh)["passed"] is False
    fresh = _fresh_registry_records(donor); common = _common_records(donor)
    common[0]["case_id"] = fresh[0]["case_id"]
    assert validate_global_78_registry(fresh, common)["passed"] is False


def test_a0_rejects_untyped_state_and_unbound_work_grid(donor) -> None:
    from r2_preflight.strict_json import canonical_sha256

    fresh = _fresh_registry_records(donor)
    first = next(record for record in fresh if record["arm"] == "A0")
    first["a0_numeric_payload"]["state_payload"] = "arbitrary-untyped-state"
    first["a0_numeric_payload_sha256"] = canonical_sha256(first["a0_numeric_payload"])
    assert validate_a0_bookends(fresh)["passed"] is False

    fresh = _fresh_registry_records(donor)
    first = next(record for record in fresh if record["arm"] == "A0")
    first["a0_signed_W_act_J"] = [0.0, 0.0]
    assert validate_a0_bookends(fresh)["passed"] is False


def test_global_registry_rejects_minimal_common_alias_records(donor) -> None:
    fresh = _fresh_registry_records(donor)
    common = _common_records(donor)
    minimal = [
        {
            "case_id": record["case_id"],
            "evidence_path": record["evidence_path"],
            "donor_certificate_sha256": record["donor_certificate_sha256"],
        }
        for record in common
    ]
    assert validate_global_78_registry(fresh, minimal)["passed"] is False


def test_g12_pair_and_aggregate_cannot_claim_runtime_pass(donor) -> None:
    left = _g12_record(donor, method="rk4", alpha=1.0, duration_s=0.01)
    right = _g12_record(donor, method="midpoint", alpha=1.0, duration_s=0.01)
    pair = evaluate_g12_pair(left, right)
    assert pair["source_only_schema_valid"] is True
    assert pair["trajectory_raw_verified"] is False
    assert pair["eligible"] is False and pair["scientific_predicate"] is False
    records = [
        _g12_record(donor, method=method, alpha=alpha, duration_s=duration)
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
        for duration in (0.005, 0.01, 0.02)
        for method in ("rk4", "midpoint")
    ]
    aggregate = aggregate_g12(records)
    assert aggregate["pair_count"] == 18
    assert aggregate["aggregate_pass"] is False
    assert aggregate["eligible_count"] == 0
    assert aggregate["recommend_A2_including_campaign_review"] is False
    assert aggregate_g12([{}] * 18)["aggregate_pass"] is False


def test_governance_exact_false_flags() -> None:
    flags = _governance_flags()
    assert validate_governance_flags(flags)
    for key in ("owner_execution_authorized", "production", "next_stage_authorized", "formal_sim13_nc19"):
        mutated = deepcopy(flags); mutated[key] = True
        assert not validate_governance_flags(mutated)
