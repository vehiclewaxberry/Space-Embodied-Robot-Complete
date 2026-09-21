from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parent
VALIDATOR_PATH = PACKAGE / "validate_increment_gate_v2.py"
SPEC = importlib.util.spec_from_file_location("increment_v2_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


def test_strict_json_rejects_duplicate_and_nonfinite():
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
        with pytest.raises(ValueError):
            validator.strict_json_bytes(raw)


def test_validator_source_does_not_import_builder():
    tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any("build_increment_gate_v2" in name for name in imports)
    assert validator.import_architecture_audit()["pass"] is True


def test_fixed_lock_and_all_27_upstream_pins_match():
    _, lock, _, _, pins = validator.load_frozen_inputs()
    assert validator.audit_lock_document(lock) is True
    assert len(pins) == 27
    assert all(row["match"] is True for row in pins)


def test_source_semantics_are_fieldwise_and_all_pass():
    _, lock, raws, docs, _ = validator.load_frozen_inputs()
    facts = validator.independent_source_semantics(lock, raws, docs)
    assert len(facts) == 16
    assert all(facts.values()), {key: value for key, value in facts.items() if not value}


def test_bool_is_not_accepted_as_integer_count():
    assert validator.exact_int(25, 25) is True
    assert validator.exact_int(True, 1) is False
    assert validator.exact_int(False, 0) is False


def test_source_mutation_is_detected_without_resigning_upstream():
    _, lock, raws, docs, _ = validator.load_frozen_inputs()
    trial = copy.deepcopy(docs)
    trial["m01_hardened_gate"]["counters"]["design_screening_candidate_bounds_emitted"] = 10
    facts = validator.independent_source_semantics(lock, raws, trial)
    assert facts["m01_counts_authority"] is False


def test_lock_path_hash_count_and_authority_mutations_fail_closed():
    _, lock, _, _, _ = validator.load_frozen_inputs()
    mutations = (
        lambda d: d["records"][0].__setitem__("path", "wrong"),
        lambda d: d["records"][0].__setitem__("sha256", "0" * 64),
        lambda d: d.__setitem__("record_count", True),
        lambda d: d["authority_boundaries"].__setitem__("release_credit", True),
    )
    for mutate in mutations:
        trial = copy.deepcopy(lock)
        mutate(trial)
        assert validator.audit_lock_document(trial) is False


def test_external_audit_tests_and_readme_are_directly_pinned():
    _, lock, _, _, _ = validator.load_frozen_inputs()
    records = {row["id"]: row for row in lock["records"]}
    assert records["task_metric_external_tests"] == {
        "id": "task_metric_external_tests",
        "path": "30_simulation/r2_control_engineering_closure/task_space_metric_external_audit_v1/tests/test_external_audit.py",
        "bytes": 2530,
        "sha256": "9135801797F8A635E7D7278066987321D3AD327D8A86A752099855E38347F92E",
    }
    assert records["task_metric_external_readme"] == {
        "id": "task_metric_external_readme",
        "path": "30_simulation/r2_control_engineering_closure/task_space_metric_external_audit_v1/README.md",
        "bytes": 1853,
        "sha256": "69BBDC7826C9FCB4709E989E607D1DAB2CB23F7721E19DBE91DB99CD37F6595B",
    }


def test_gate_manifest_receipt_and_negative_controls_close():
    receipt = validator.validate_all()
    assert receipt["all_pass"] is True
    assert receipt["passed"] == receipt["total"] == 7
    assert receipt["negative_controls"]["all_pass"] is True
    assert receipt["negative_controls"]["passed"] == receipt["negative_controls"]["count"] == 28
    assert all(value is False for value in receipt["authority_boundaries"].values())


def test_stored_receipt_is_exact_deterministic_replay():
    receipt = validator.validate_all()
    raw = (PACKAGE / validator.RECEIPT_NAME).read_bytes()
    assert validator.strict_json_bytes(raw) == receipt
    assert raw == validator.canonical_json(receipt)


def test_manifest_inventory_is_exact_and_cache_free():
    manifest = validator.strict_json_bytes((PACKAGE / validator.MANIFEST_NAME).read_bytes())
    audit = validator.audit_manifest(manifest)
    assert all(audit.values()), {key: value for key, value in audit.items() if not value}


def test_no_json_boolean_is_used_for_stored_counts():
    gate = validator.strict_json_bytes((PACKAGE / validator.GATE_NAME).read_bytes())
    receipt = validator.strict_json_bytes((PACKAGE / validator.RECEIPT_NAME).read_bytes())
    count_paths = (
        gate["summary"]["passed"],
        gate["summary"]["total"],
        gate["source_binding"]["matched"],
        gate["source_binding"]["total"],
        receipt["passed"],
        receipt["total"],
        receipt["negative_controls"]["passed"],
        receipt["negative_controls"]["count"],
    )
    assert all(type(value) is int for value in count_paths)


def test_stored_json_documents_are_finite_and_duplicate_free():
    for name in (validator.LOCK_NAME, validator.GATE_NAME, validator.MANIFEST_NAME, validator.RECEIPT_NAME):
        raw = (PACKAGE / name).read_bytes()
        document = validator.strict_json_bytes(raw)
        json.dumps(document, allow_nan=False)
