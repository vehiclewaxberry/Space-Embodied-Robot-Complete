"""Deterministic builder for the append-only R2 increment V3."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent
VALIDATOR_PATH = PACKAGE / "validate_increment_gate_v3.py"
SPEC = importlib.util.spec_from_file_location("_increment_v3_standalone_core", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("VALIDATOR_IMPORT_SPEC_FAILED")
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def build_documents():
    lock_raw, lock, _, docs, pins = validator.load_frozen_inputs()
    facts = validator.independent_source_semantics(docs)
    if not all(facts.values()):
        raise ValueError(f"SOURCE_SEMANTICS_HOLD:{[key for key, value in facts.items() if not value]}")
    gate = validator.expected_gate_document(lock_raw, lock, pins, facts)
    if gate["gate_passed"] is not True:
        raise ValueError(f"V3_GATE_HOLD:{gate['summary']['failed']}")
    gate_raw = validator.canonical_json(gate)
    (PACKAGE / validator.GATE_NAME).write_bytes(gate_raw)
    manifest = validator.expected_manifest_document()
    manifest_raw = validator.canonical_json(manifest)
    (PACKAGE / validator.MANIFEST_NAME).write_bytes(manifest_raw)
    # Receipt is dynamically excluded from the manifest, but exact inventory
    # requires the path to exist during the first standalone validation.
    receipt_path = PACKAGE / validator.RECEIPT_NAME
    if not receipt_path.exists():
        receipt_path.write_bytes(b"{}\n")
    receipt = validator.validate_all()
    receipt_raw = validator.canonical_json(receipt)
    receipt_path.write_bytes(receipt_raw)
    return gate_raw, manifest_raw, receipt_raw


def check_documents():
    lock_raw, lock, _, docs, pins = validator.load_frozen_inputs()
    facts = validator.independent_source_semantics(docs)
    expected_gate = validator.canonical_json(validator.expected_gate_document(lock_raw, lock, pins, facts))
    if (PACKAGE / validator.GATE_NAME).read_bytes() != expected_gate:
        raise SystemExit("V3_GATE_DETERMINISTIC_REPLAY_MISMATCH")
    expected_manifest = validator.canonical_json(validator.expected_manifest_document())
    if (PACKAGE / validator.MANIFEST_NAME).read_bytes() != expected_manifest:
        raise SystemExit("V3_MANIFEST_DETERMINISTIC_REPLAY_MISMATCH")
    expected_receipt = validator.canonical_json(validator.validate_all())
    if (PACKAGE / validator.RECEIPT_NAME).read_bytes() != expected_receipt:
        raise SystemExit("V3_RECEIPT_DETERMINISTIC_REPLAY_MISMATCH")
    print("PASS V3 gate, manifest, and standalone receipt deterministic replay")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        build_documents()
        print("PASS wrote V3 gate, manifest, and standalone receipt")
    else:
        check_documents()


if __name__ == "__main__":
    main()
