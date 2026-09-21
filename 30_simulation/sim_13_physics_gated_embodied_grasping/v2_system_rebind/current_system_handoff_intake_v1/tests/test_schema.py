from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from current_handoff.evaluator import evaluate_default_snapshot
from current_handoff.schema import (
    EXPECTED_UNITS,
    FROZEN_BINDING_DIGEST,
    PROMOTION_RECEIPT_ARTIFACT_ID,
    REQUIRED_ABSENT_PATHS,
    compute_frozen_binding_digest,
    route_c_auto_accept,
    validate_intake_document,
    validate_mass_mode,
    validate_promotion_receipt,
)
from current_handoff.strict_io import IntakeError


def _receipt(issued, expires, nonce="NONCE_SCHEMA_TEST_0001"):
    return {
        "schema": "CURRENT_SYSTEM_PROMOTION_AUTHORITY_RECEIPT_V1",
        "artifact_id": PROMOTION_RECEIPT_ARTIFACT_ID,
        "action_digest": "A" * 64,
        "context_digest": "B" * 64,
        "issued_at_utc": issued,
        "expires_at_utc": expires,
        "nonce": nonce,
        "generation": 1,
        "authority": "OWNER_EXTERNAL_AUTHORITY",
        "decision": "ALLOW_SINGLE_USE",
    }


def test_baseline_intake_validates():
    document = evaluate_default_snapshot()
    assert document["frozen_binding_digest"] == FROZEN_BINDING_DIGEST
    validate_intake_document(document)


def test_every_quantity_has_exact_unit_contract():
    document = evaluate_default_snapshot()
    assert {key: value["unit"] for key, value in document["physical_quantities"].items()} == EXPECTED_UNITS


def test_missing_uncertainty_field_rejected():
    document = evaluate_default_snapshot()
    del document["physical_quantities"]["c01_design_mass"]["uncertainty"]["distribution"]
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_unknown_physical_value_cannot_be_zero_filled():
    document = evaluate_default_snapshot()
    document["physical_quantities"]["gripper_physical_rated_speed"]["value"] = 0.0
    with pytest.raises(IntakeError) as caught:
        validate_intake_document(document)
    assert caught.value.classification == "TEST_REQUIRED"


def test_dual_mass_mode_rejected():
    with pytest.raises(IntakeError):
        validate_mass_mode(["EXPLICIT_STRUCTURE_PLUS_RESIDUAL", "AGGREGATE_BUS"])


def test_stale_receipt_rejected():
    with pytest.raises(IntakeError) as caught:
        validate_promotion_receipt(
            _receipt("2026-08-25T10:00:00Z", "2026-08-25T10:10:00Z"),
            now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
            expected_action_digest="A" * 64,
            expected_context_digest="B" * 64,
            replay_ledger=set(),
        )
    assert caught.value.classification == "OWNER_REQUIRED"


def test_receipt_replay_rejected():
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    receipt = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z")
    ledger = set()
    validate_promotion_receipt(receipt, now=now, expected_action_digest="A" * 64, expected_context_digest="B" * 64, replay_ledger=ledger)
    with pytest.raises(IntakeError, match="replay"):
        validate_promotion_receipt(receipt, now=now, expected_action_digest="A" * 64, expected_context_digest="B" * 64, replay_ledger=ledger)


@pytest.mark.parametrize("selection", ["INCLUDED", "EXCLUDED_RESEARCH_CANDIDATE"])
def test_neither_route_c_disposition_auto_accepts(selection):
    with pytest.raises(IntakeError) as caught:
        route_c_auto_accept(
            {
                "schema": "ROUTE_C_DISPOSITION_V1",
                "disposition": selection,
                "owner_receipt_digest": None,
                "auto_accepted": False,
            }
        )
    assert caught.value.classification == "OWNER_REQUIRED"


def test_syntactic_receipt_cannot_promote_intake():
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    validate_promotion_receipt(
        _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", "NONCE_SCHEMA_TEST_0025"),
        now=now,
        expected_action_digest="A" * 64,
        expected_context_digest="B" * 64,
        replay_ledger=set(),
    )
    document = evaluate_default_snapshot()
    document["flags"]["current_system_bound"] = True
    with pytest.raises(IntakeError) as caught:
        validate_intake_document(document)
    assert caught.value.classification == "OWNER_REQUIRED"


def test_receipt_source_set_and_order_are_exact():
    document = evaluate_default_snapshot()
    document["source_receipts"][0], document["source_receipts"][1] = document["source_receipts"][1], document["source_receipts"][0]
    with pytest.raises(IntakeError):
        validate_intake_document(document)


@pytest.mark.parametrize("field", ["path", "bytes", "sha256"])
def test_receipt_cross_id_binding_swap_rejected_even_if_candidate_recomputes_digest(field):
    document = evaluate_default_snapshot()
    document["source_receipts"][0][field], document["source_receipts"][1][field] = (
        document["source_receipts"][1][field],
        document["source_receipts"][0][field],
    )
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    with pytest.raises(IntakeError):
        validate_intake_document(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [("value", 999.0), ("authority", "FABRICATED"), ("status", "PASS")],
)
def test_quantity_value_authority_status_forgery_rejected(field, value):
    document = evaluate_default_snapshot()
    document["physical_quantities"]["c01_design_mass"][field] = value
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_quantity_source_artifact_and_field_rebinding_rejected():
    document = evaluate_default_snapshot()
    quantity = document["physical_quantities"]["c01_design_mass"]
    quantity["source_artifact"] = "topology_frame_tree"
    quantity["source_field"] = "mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.total_links"
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    with pytest.raises(IntakeError):
        validate_intake_document(document)


@pytest.mark.parametrize("mutation", ["duplicate", "rebind", "presence"])
def test_domain_source_duplicate_rebinding_and_presence_drift_rejected(mutation):
    document = evaluate_default_snapshot()
    domain = document["domains"]["mass"]
    if mutation == "duplicate":
        domain["source_artifacts"] = ["mass_model", "mass_model"]
    elif mutation == "rebind":
        domain["source_artifacts"] = ["target_feasibility_gate"]
    else:
        domain["presence"] = False
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_required_absent_path_alias_or_substitution_rejected():
    document = evaluate_default_snapshot()
    assert tuple(document["required_absent_paths"]) == REQUIRED_ABSENT_PATHS
    document["required_absent_paths"][0] = "20_engineering/another_absent.urdf"
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_candidate_recomputed_digest_cannot_replace_source_constant():
    document = evaluate_default_snapshot()
    document["physical_quantities"]["c01_design_mass"]["value"] = 999.0
    attacker_digest = compute_frozen_binding_digest(document)
    assert attacker_digest != FROZEN_BINDING_DIGEST
    document["frozen_binding_digest"] = attacker_digest
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_promotion_receipt_artifact_action_and_context_are_exact_and_failure_does_not_consume():
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    for field, value in (
        ("artifact_id", "FORGED"),
        ("action_digest", "C" * 64),
        ("context_digest", "D" * 64),
    ):
        receipt = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", f"NONCE_SCHEMA_{field.upper()}_01")
        receipt[field] = value
        ledger = set()
        with pytest.raises(IntakeError):
            validate_promotion_receipt(
                receipt,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=ledger,
            )
        assert ledger == set()


def test_quantity_source_must_reference_receipt():
    document = evaluate_default_snapshot()
    document["physical_quantities"]["c01_design_mass"]["source_artifact"] = "ghost"
    with pytest.raises(IntakeError):
        validate_intake_document(document)


def test_frozen_domain_classification_cannot_self_promote():
    document = evaluate_default_snapshot()
    document["domains"]["mass"]["classification"] = "PASS"
    document["domains"]["mass"]["eligible"] = True
    with pytest.raises(IntakeError) as caught:
        validate_intake_document(document)
    assert caught.value.classification == "OWNER_REQUIRED"
