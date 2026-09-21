from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


PACKAGE = Path(__file__).resolve().parent
VALIDATOR_PATH = PACKAGE / "validate_increment_gate_v3.py"
SPEC = importlib.util.spec_from_file_location("_increment_v3_test_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def test_strict_json_rejects_duplicate_and_nonfinite():
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
        with pytest.raises(ValueError):
            validator.strict_json_bytes(raw)


def test_validator_does_not_import_builder():
    tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any("build_increment_gate_v3" in name for name in imports)
    assert validator.import_architecture_audit()["pass"] is True


def test_fixed_lock_has_exact_groups_paths_and_all_pins_match():
    _, lock, _, _, pins = validator.load_frozen_inputs()
    assert validator.audit_lock_document(lock) is True
    assert len(pins) == len(validator.EXPECTED_ID_PATHS)
    assert {row["group"] for row in pins} == set(validator.GROUP_PREFIXES)
    assert all(row["match"] is True for row in pins)


def test_original_time_domain_gate_remains_19_of_20_false():
    _, _, _, docs, _ = validator.load_frozen_inputs()
    gate = docs["td_gate"]
    assert gate["gate_passed"] is False
    assert gate["summary"] == {
        "passed": 19,
        "total": 20,
        "failed": ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"],
    }
    assert all(value is False for value in gate["authority_boundaries"].values())


def test_rebind_is_16_of_16_without_reissuing_original():
    _, _, _, docs, _ = validator.load_frozen_inputs()
    gate = docs["rb_gate"]
    evidence = docs["rb_evidence"]
    assert gate["gate_passed"] is True
    assert gate["summary"] == {"passed": 16, "total": 16, "failed": []}
    assert gate["original_time_domain_gate_passed"] is False
    assert gate["original_time_domain_gate_reissued"] is False
    assert evidence["rebound_metric_gate"]["passed"] == evidence["rebound_metric_gate"]["total"] == 17
    assert all(value is False for value in gate["authority_boundaries"].values())


def test_external_audit_is_18_of_18_diagnostic_only():
    _, _, _, docs, _ = validator.load_frozen_inputs()
    receipt = docs["ext_receipt"]
    assert receipt["all_pass"] is True
    assert receipt["passed"] == receipt["total"] == 18
    assert receipt["negative_controls"]["passed"] == receipt["negative_controls"]["total"] == 12
    assert receipt["maximum_claim"] == "EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE"
    assert all(value is False for value in receipt["authority_boundaries"].values())


def test_all_source_semantics_pass_fieldwise():
    _, _, _, docs, _ = validator.load_frozen_inputs()
    facts = validator.independent_source_semantics(docs)
    assert len(facts) == 16
    assert all(facts.values()), {key: value for key, value in facts.items() if not value}


def test_source_and_authority_mutations_fail_closed():
    _, lock, _, _, _ = validator.load_frozen_inputs()
    for mutate in (
        lambda d: d["records"][0].__setitem__("sha256", "0" * 64),
        lambda d: d["records"][0].__setitem__("path", "wrong"),
        lambda d: d.__setitem__("record_count", True),
        lambda d: d["authority_boundaries"].__setitem__("release_credit", True),
    ):
        trial = copy.deepcopy(lock)
        mutate(trial)
        if validator.audit_lock_document(trial):
            with pytest.raises(ValueError):
                validator.load_frozen_inputs(trial)


def test_gate_manifest_receipt_and_negative_controls_close():
    receipt = validator.validate_all()
    assert receipt["all_pass"] is True
    assert receipt["passed"] == receipt["total"] == 7
    assert receipt["negative_controls"]["all_pass"] is True
    assert receipt["negative_controls"]["passed"] == receipt["negative_controls"]["count"] == 16
    assert all(value is False for value in receipt["authority_boundaries"].values())


def test_stored_receipt_is_deterministic_canonical_replay():
    receipt = validator.validate_all()
    raw = (PACKAGE / validator.RECEIPT_NAME).read_bytes()
    assert validator.strict_json_bytes(raw) == receipt
    assert raw == validator.canonical_json(receipt)


def test_manifest_inventory_exact_and_cache_free():
    manifest = validator.strict_json_bytes((PACKAGE / validator.MANIFEST_NAME).read_bytes())
    audit = validator.audit_manifest(manifest)
    assert all(audit.values()), {key: value for key, value in audit.items() if not value}


def test_json_counts_are_integers_not_booleans_and_all_finite():
    for name in (validator.LOCK_NAME, validator.GATE_NAME, validator.MANIFEST_NAME, validator.RECEIPT_NAME):
        document = validator.strict_json_bytes((PACKAGE / name).read_bytes())
        json.dumps(document, allow_nan=False)
    gate = validator.strict_json_bytes((PACKAGE / validator.GATE_NAME).read_bytes())
    receipt = validator.strict_json_bytes((PACKAGE / validator.RECEIPT_NAME).read_bytes())
    values = (
        gate["summary"]["passed"], gate["summary"]["total"],
        gate["source_binding"]["matched"], gate["source_binding"]["total"],
        receipt["passed"], receipt["total"],
        receipt["negative_controls"]["passed"], receipt["negative_controls"]["count"],
    )
    assert all(type(value) is int for value in values)
