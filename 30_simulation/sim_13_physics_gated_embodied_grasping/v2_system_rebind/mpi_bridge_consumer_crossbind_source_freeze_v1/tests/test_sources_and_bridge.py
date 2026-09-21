from __future__ import annotations

from types import MappingProxyType

import pytest

from crossbind.bridge import recompute_bridge
from crossbind.constants import SOURCE_PINS
from crossbind.source_bundle import SourceBundleError, load_source_bundle


def test_all_pinned_sources_read_exactly_once(repo_root):
    observed = []
    bundle = load_source_bundle(repo_root, observed.append)
    assert len(bundle.receipts) == len(SOURCE_PINS) == 15
    assert len(observed) == len(set(observed)) == 15
    assert all(count == 1 for count in bundle.read_counts.values())


def test_source_receipts_are_immutable(bundle):
    assert isinstance(bundle.receipts, MappingProxyType)
    with pytest.raises(TypeError):
        bundle.receipts["NEW"] = object()
    with pytest.raises(TypeError):
        bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed["status"] = "FORGED"


def test_bridge_recomputation_is_exact_and_forward(bundle):
    result = recompute_bridge(bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed)
    assert result["formula"] == "inv(T_S_A0_dynamics) @ T_S_A0_physical"
    assert result["direction"] == "PHYSICAL_TO_DYNAMICS"
    assert result["exact_elementwise"] is True
    assert result["max_abs_residual"]["value"] == 0.0
    assert result["closure_max_abs"]["value"] == 0.0
    assert result["inverse_direction_max_abs_separation"]["value"] > 0.01


def test_owner_overlay_and_candidate_holds_are_preserved(record):
    payload = record.payload
    assert payload["authority_resolution"]["effective_bridge_status"] == "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE"
    assert payload["system_binding_v3"]["production_authenticated_receipt_present"] is False
    assert payload["system_binding_v3"]["production_composite_producer_status"] == "NOT_IMPLEMENTED_NO_PRODUCER"
    assert payload["parent_and_runtime_state"]["formal_parent_nc"] == {"passed": 15, "total": 20, "promoted": 0}
    assert payload["parent_and_runtime_state"]["remaining_holds"] == ("NC18", "NC19")
    assert all(value is False for value in payload["parent_and_runtime_state"]["flags"].values())


def test_crossbind_record_is_stable_and_nonempty(record):
    assert len(record.canonical_bytes) > 1000
    assert len(record.bridge_semantic_digest) == 64
    assert len(record.crossbind_record_digest) == 64
    assert record.bridge_semantic_digest != record.crossbind_record_digest
    assert len(record.source_checks) == 26
