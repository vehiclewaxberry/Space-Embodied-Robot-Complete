from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load_module("aggregate_builder_under_test", "build_increment_gate.py")
validator = load_module("aggregate_validator_under_test", "validate_increment_gate.py")


def test_builder_gate_all_28_pass():
    gate = builder.evaluate()
    assert gate["summary"] == {"passed": 28, "total": 28, "failed": []}
    assert all(gate["checks"].values())


def test_builder_deterministic_bytes_match_disk():
    gate_raw = builder.canonical_json(builder.evaluate())
    assert gate_raw == (PACKAGE / builder.GATE_NAME).read_bytes()
    manifest_raw = builder.canonical_json(builder.build_manifest(gate_raw))
    assert manifest_raw == (PACKAGE / builder.MANIFEST_NAME).read_bytes()


def test_standalone_validation_all_pass():
    receipt = validator.validate_all()
    assert receipt["summary"] == {"passed": 5, "total": 5, "all_pass": True}


def test_validator_does_not_import_builder():
    assert validator.import_architecture_audit()["pass"] is True


def test_manifest_is_exact_and_has_no_cache():
    manifest = validator.strict_json_bytes((PACKAGE / validator.MANIFEST_NAME).read_bytes())
    checks = validator.audit_manifest(manifest)
    assert checks["paths_exact"] is True
    assert checks["no_unlisted_files"] is True
    assert checks["no_cache_or_bytecode"] is True
    assert all(checks.values())


def test_negative_controls_all_reject():
    lock, docs, _ = validator.load_frozen_inputs()
    gate = validator.strict_json_bytes((PACKAGE / validator.GATE_NAME).read_bytes())
    manifest = validator.strict_json_bytes((PACKAGE / validator.MANIFEST_NAME).read_bytes())
    result = validator.run_negative_controls(lock, docs, gate, manifest)
    assert result["count"] == 26
    assert result["passed"] == 26
    assert result["all_pass"] is True


@pytest.mark.parametrize(
    "key,mutated",
    [
        ("candidate_CAD_generated", True),
        ("M01_scene_complete", True),
        ("physical_contact_authority", True),
        ("parent_dynamics_complete", True),
        ("Sim13_non_abort_authority", True),
        ("release_credit", True),
    ],
)
def test_gate_system_hold_mutation_rejected(key, mutated):
    lock, docs, pins = validator.load_frozen_inputs()
    gate = validator.strict_json_bytes((PACKAGE / validator.GATE_NAME).read_bytes())
    gate["system_hold_state"][key] = mutated
    facts = validator.source_semantics(lock, docs)
    assert validator.audit_gate(gate, pins, facts)["system_holds"] is False


@pytest.mark.parametrize("bad", [True, False])
def test_bool_cannot_impersonate_m01_integer_count(bad):
    lock, docs, _ = validator.load_frozen_inputs()
    trial = copy.deepcopy(docs)
    trial["m01_base_motion_gate"]["counters"]["system_motion_certificates_bound"] = bad
    assert validator.source_semantics(lock, trial)["m01_motion_1_150"] is False


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_strict_json_rejects_invalid(raw):
    with pytest.raises(ValueError):
        validator.strict_json_bytes(raw)


def test_parent_snapshot_is_not_reissued():
    gate = builder.evaluate()
    assert gate["additive_evidence_state"]["child_base_motion_precertificate"] == "1_OF_150"
    assert gate["additive_evidence_state"]["parent_V4_motion_snapshot_unchanged"] == "0_OF_150"
    assert gate["parent_integrity"]["parent_gate_reissued"] is False


def test_maximum_claim_is_narrow_and_review_pending():
    gate = builder.evaluate()
    assert gate["maximum_claim"] == validator.EXPECTED_MAXIMUM_CLAIM
    assert gate["review_status"] == "PENDING_OWNER_REVIEW"
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False
