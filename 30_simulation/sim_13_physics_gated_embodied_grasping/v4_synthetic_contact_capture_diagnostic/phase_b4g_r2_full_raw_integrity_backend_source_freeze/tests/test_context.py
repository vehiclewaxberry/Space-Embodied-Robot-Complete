from __future__ import annotations

import pytest

from r2_full_integrity.context import ContextError, load_integrity_context
from r2_full_integrity.fixture_factory import write_technical_fixture
from r2_full_integrity.source_api import SourceAPIError, verify_source_bindings


def test_acquisition_payload_mutation_is_rejected_even_when_rehashed(tmp_path) -> None:
    def mutate(acquisition):
        acquisition["event"]["target"]["position_inertial_m"][0] += 1.0e-6

    bundle = write_technical_fixture(tmp_path, acquisition_mutator=mutate)
    with pytest.raises(ContextError, match="RAW_ACTIVE_INITIAL_TARGET"):
        bundle.load()


def test_parent_file_binding_byte_mutation_is_rejected(tmp_path) -> None:
    def mutate(context):
        context["parent_trace_binding"]["bytes"] += 1

    bundle = write_technical_fixture(tmp_path, context_mutator=mutate)
    with pytest.raises(ContextError, match="PARENT_TRACE_BYTES_OR_SHA256"):
        bundle.load()


def test_authorized_evidence_class_is_fail_closed_until_owner_terminal_exists(tmp_path) -> None:
    def mutate(context):
        context["execution_evidence_class"] = "AUTHORIZED_R2_RAW_CASE"

    bundle = write_technical_fixture(tmp_path, context_mutator=mutate)
    with pytest.raises(ContextError, match="CONTEXT_IDENTITY_SCOPE_OR_RAW_BINDING_INVALID"):
        bundle.load()


def test_source_binding_drift_fails_closed(monkeypatch) -> None:
    from r2_full_integrity import source_api

    original = source_api.GEOMETRY_REPLAY_BINDING
    monkeypatch.setattr(source_api, "GEOMETRY_REPLAY_BINDING", (original[0], "0" * 64))
    with pytest.raises(SourceAPIError, match="SOURCE_BINDING_DRIFT"):
        verify_source_bindings()
