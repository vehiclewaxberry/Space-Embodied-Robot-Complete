from __future__ import annotations

from independent_audit_current_system_handoff_intake import audit_committed_bundle, build_audit


def test_independent_audit_passes_without_production_evaluator_import():
    audit = build_audit()
    assert audit["independent_audit_pass"] is True
    assert audit["checks_passed"] == audit["checks_total"] == 21
    assert audit["imports_production_evaluator"] is False


def test_independent_audit_keeps_hold_and_false_flags():
    audit = build_audit()
    assert audit["current_intake_status"] == "HOLD_INCOMPLETE"
    assert audit["gate_ceiling"] == "PASS_SOURCE_FREEZE_ONLY"
    assert all(value is False for value in audit["flags"].values())


def test_independent_audit_treats_yaml_as_opaque_pin():
    assert build_audit()["yaml_source_handling"] == "OPAQUE_LENGTH_SHA256_PIN_PLUS_SINGLE_SCHEMA_MARKER__NOT_INTAKE_YAML"


def test_independent_audit_recomputes_complete_manifest_evidence_gate_terminal_dag():
    audit = audit_committed_bundle()
    assert audit["pass"] is True
    assert audit["checks_passed"] == audit["checks_total"] == 17
