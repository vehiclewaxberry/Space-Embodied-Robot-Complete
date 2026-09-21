from __future__ import annotations

from copy import deepcopy

import pytest

from crossbind.policy import PolicyError, admit_consumer, make_valid_plan, validate_consumer_plan
from crossbind.receipt import (
    PREEXEC_KINDS,
    PRODUCTION_PRODUCER_STATUS,
    SYNTHETIC_RECEIPT_KIND,
    ReceiptError,
    V3ReplayStore,
    _actual_preexec_modules,
    make_synthetic_v3_fixture,
    validate_system_binding_v3,
    verify_preexec_composition,
)


def _fixture_kwargs(fixture, store=None):
    return {
        "preexec_receipt_bytes_by_kind": fixture.preexec_receipt_bytes_by_kind,
        "expected_action": fixture.action,
        "expected_context": fixture.context,
        "trusted_now_unix_s": fixture.trusted_now_unix_s,
        "replay_store": store or V3ReplayStore(),
        "preexec_key": fixture.preexec_key,
        "v3_key": fixture.v3_key,
    }


def test_valid_plan_binds_complete_lineage_and_only_three_consumer_numeric_channels(record):
    result = validate_consumer_plan(make_valid_plan(record), record)
    assert result["valid"] is True
    assert result["bridge_lineage_applications_per_channel"] == 1
    assert result["consumer_numeric_applications"] == {
        "frame": 1, "mass": 0, "inertia": 0, "wrench": 1, "collision_geometry": 1,
    }


@pytest.mark.parametrize("channel", ["frame", "mass", "inertia", "wrench", "collision_geometry"])
def test_skip_rejected_for_every_channel(record, channel):
    plan = make_valid_plan(record)
    plan["channels"][channel]["bridge_lineage_count"] = 0
    with pytest.raises(PolicyError, match="BRIDGE_SKIPPED"):
        validate_consumer_plan(plan, record)


@pytest.fixture()
def v3_fixture(record):
    return make_synthetic_v3_fixture(record)


def test_seven_raw_preexec_receipts_are_verified_and_ordered(v3_fixture):
    composition = verify_preexec_composition(
        v3_fixture.preexec_receipt_bytes_by_kind,
        action=v3_fixture.action,
        context={key: v3_fixture.context[key] for key in ("episode_id", "configuration_id", "authority_epoch", "target_class")},
        trusted_now_unix_s=v3_fixture.trusted_now_unix_s,
        key=v3_fixture.preexec_key,
    )
    assert tuple(item["kind"] for item in composition.ordered_receipts) == PREEXEC_KINDS
    assert len(composition.receipt_set_digest) == 64
    assert composition.decision["executed_strategy"] == "ABORT"
    assert composition.decision["reason"] == "SOURCE_FREEZE_SCOPE_LOCK"


def test_signed_v3_fixture_binds_receipt_set_and_consumes_nonce(record, v3_fixture):
    store = V3ReplayStore()
    result = validate_system_binding_v3(v3_fixture.receipt_bytes, record, **_fixture_kwargs(v3_fixture, store))
    assert result["receipt_kind"] == SYNTHETIC_RECEIPT_KIND
    assert result["preexec_receipts_verified"] == 7
    assert result["v3_nonce_consumed"] is True
    assert result["production_authenticated_receipt_present"] is False
    assert result["production_composite_producer_status"] == PRODUCTION_PRODUCER_STATUS
    assert store.seen_count == 1


def test_same_v3_nonce_is_rejected_on_second_successful_verify(record, v3_fixture):
    store = V3ReplayStore()
    validate_system_binding_v3(v3_fixture.receipt_bytes, record, **_fixture_kwargs(v3_fixture, store))
    with pytest.raises(ReceiptError, match="V3_REPLAY_NONCE"):
        validate_system_binding_v3(v3_fixture.receipt_bytes, record, **_fixture_kwargs(v3_fixture, store))
    assert store.seen_count == 1


def test_plain_dict_claiming_authenticated_is_never_a_receipt(record, v3_fixture):
    with pytest.raises(ReceiptError, match="SERIALIZED_SIGNED_ENVELOPE_BYTES_REQUIRED"):
        validate_system_binding_v3({"receipt_kind": "AUTHENTICATED"}, record, **_fixture_kwargs(v3_fixture))


def test_v3_context_retains_episode_epoch_configuration_and_target(v3_fixture):
    _, strict = _actual_preexec_modules()
    body = strict.loads_strict(v3_fixture.receipt_bytes)["body"]
    assert set(body["context"]) == {
        "episode_id", "configuration_id", "authority_epoch", "target_class",
        "mission_phase_id", "reference_frame_id",
    }
    assert body["configuration_mapping"] == {
        "preexec_configuration_id": body["context"]["configuration_id"],
        "v3_configuration_id": body["context"]["configuration_id"],
    }
    assert body["preexec_action_digest"] == body["preexec_receipts"][0]["action_digest"]
    assert body["preexec_context_digest"] == body["preexec_receipts"][0]["context_digest"]


def test_legacy_v2_receipt_is_rejected_as_v3_composite(record, v3_fixture):
    with pytest.raises(ReceiptError, match="KEY_SET_MISMATCH"):
        validate_system_binding_v3(
            v3_fixture.preexec_receipt_bytes_by_kind["SYSTEM_BINDING_V2"],
            record,
            **_fixture_kwargs(v3_fixture),
        )


def test_synthetic_fixture_verification_never_admits_consumer(record, v3_fixture):
    result = admit_consumer(
        make_valid_plan(record),
        v3_fixture.receipt_bytes,
        record,
        environment={"system_urdf_available": True},
        receipt_validation_kwargs=_fixture_kwargs(v3_fixture),
    )
    assert result["allowed"] is False
    assert result["reason"] == "SYNTHETIC_SIGNED_COMPOSITION_FIXTURE_SOURCE_LOCK"
    assert result["bridge_applications_executed"] == 0
    assert result["release_credit"] is False


def test_no_receipt_is_source_locked(record):
    result = admit_consumer(make_valid_plan(record), None, record, environment={})
    assert result["allowed"] is False
    assert result["reason"] == "SYSTEM_BINDING_V3_PRODUCTION_COMPOSITE_ABSENT"


def test_bad_signature_consumes_no_nonce(record, v3_fixture):
    _, strict = _actual_preexec_modules()
    outer = strict.loads_strict(v3_fixture.receipt_bytes)
    outer["signature_hmac_sha256"] = "0" * 64
    bad = strict.canonical_json_bytes(outer)
    store = V3ReplayStore()
    with pytest.raises(ReceiptError, match="V3_SIGNATURE_INVALID"):
        validate_system_binding_v3(bad, record, **_fixture_kwargs(v3_fixture, store))
    assert store.seen_count == 0


def test_low_level_action_field_is_fail_closed(record, v3_fixture):
    _, strict = _actual_preexec_modules()
    candidate = deepcopy(strict.loads_strict(v3_fixture.receipt_bytes))
    candidate["body"]["action"]["joint_torque"] = [1.0]
    store = V3ReplayStore()
    with pytest.raises(ReceiptError):
        validate_system_binding_v3(strict.canonical_json_bytes(candidate), record, **_fixture_kwargs(v3_fixture, store))
    assert store.seen_count == 0
