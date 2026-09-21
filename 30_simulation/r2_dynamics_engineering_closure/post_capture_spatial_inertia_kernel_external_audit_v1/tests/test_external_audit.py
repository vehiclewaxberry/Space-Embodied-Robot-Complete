from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("external_audit_module", ROOT / "audit_external.py")
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec); sys.modules[spec.name] = audit; spec.loader.exec_module(audit)


@pytest.fixture(scope="session")
def gate():
    return audit.build_gate()


@pytest.mark.parametrize("gate_id", [f"EA{i:02d}" for i in range(1, 19)])
def test_each_external_audit_row_passes(gate, gate_id):
    row = next(item for item in gate["checks"] if item["id"] == gate_id)
    assert row["pass"] is True


def test_external_audit_summary_and_boundaries(gate):
    assert gate["passed"] == gate["total"] == 18
    assert gate["all_checks_pass"] is True
    assert gate["current_C08_status"] == gate["current_C09_status"] == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
    for key in audit.FALSE_KEYS + ("safe_gate_credit", "cad_credit", "m01_credit"):
        assert gate[key] is False


def test_fixed_pins_and_numeric_origin_recomputation(gate):
    assert gate["fixed_pin_audit"]["count"] == 10
    assert gate["fixed_pin_audit"]["all_match"] is True
    for case in gate["physics_recomputation"].values():
        assert case["direct_max_abs"] <= 2.0e-11
        assert case["spatial_max_abs"] <= 2.0e-11
        assert case["twist_max_abs"] <= 2.0e-12
        assert case["reference_translation_twist_max_abs"] <= 2.0e-12
        assert case["wrong_cross_sign_omega_delta"] > 1.0e-8


def test_runtime_forged_contract_and_receipt_are_rejected(gate):
    runtime = gate["runtime_authority_controls"]
    assert runtime["all_pass"] is True
    assert all(runtime["checks"].values())
    assert "TypeError" in runtime["observed"]["caller_supplied_contract"]
    assert "CONTRACT_CANONICAL_SHA256_DRIFT" in runtime["observed"]["forged_contract_file"]
    assert "ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING" in runtime["observed"]["forged_receipt_file"]
