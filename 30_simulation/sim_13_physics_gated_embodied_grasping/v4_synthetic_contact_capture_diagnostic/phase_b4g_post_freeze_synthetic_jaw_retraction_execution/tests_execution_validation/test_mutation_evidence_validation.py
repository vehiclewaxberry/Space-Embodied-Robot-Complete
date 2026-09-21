from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from b4g_validation.core import ValidationReport, canonical_bytes, read_json_strict
from b4g_validation import validator


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest().upper()


def _contracts() -> dict[str, dict]:
    return {
        key: read_json_strict(validator.CONTRACT_ROOT / name)
        for key, (name, _size, _digest) in validator.CONTRACT_FILES.items()
    }


def _forged_receipt_evidence(contracts: dict[str, dict]) -> dict:
    """Build the old receipt-only attack: valid-looking random SHA, no artifacts."""

    receipts = []
    summaries = []
    ordinal = 0
    for variant in contracts["mutations"]["variants"]:
        parent_id = variant["id"].split("_", 1)[0]
        count = int(variant["count"])
        for subvariant in range(1, count + 1):
            receipt_id = f"{parent_id}__SV{subvariant:02d}__FORGED_{ordinal:02d}"
            receipts.append({
                "receipt_id": receipt_id,
                "parent_id": parent_id,
                "subvariant_index": subvariant,
                "mutation_id": variant["id"],
                "target": f"/payload/forged_{ordinal}",
                "execution_detail": {"fixture": True},
                "nominal_input_sha256": _sha(f"nominal-input-{ordinal}"),
                "mutant_input_sha256": _sha(f"mutant-input-{ordinal}"),
                "real_path_hit": True,
                "expected_gate": variant["expected_gate"],
                "actual_failed_gate": variant["expected_gate"],
                "nominal_gate_sha256": _sha(f"nominal-gate-{ordinal}"),
                "mutant_gate_sha256": _sha(f"mutant-gate-{ordinal}"),
                "killed": True,
            })
            ordinal += 1
        summaries.append({
            "parent_id": parent_id,
            "expected_gate": variant["expected_gate"],
            "expected_count": count,
            "executed_count": count,
            "killed_count": count,
            "passed": True,
        })
    return {
        "schema": "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1",
        "scope": "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH_MUTATIONS_ONLY",
        "final": False,
        "audited": False,
        "validator_pass_claimed": False,
        "dictionary_flag_only_mutation_used": False,
        "campaign_or_scientific_credit_from_mutations": False,
        "memory": {"memory_gate_applicable": False, "memory_gate_passed": False, "owner_override_used": False, "classification": "DIAGNOSTIC_ONLY"},
        "source_binding": {},
        "finite_event_harness_precondition": {
            "passed": True,
            "finite_removal_event": True,
            "abs_W_act_at_removal_J": 2.0e-12,
        },
        "counts": {
            "required_parent_count": 22,
            "total_subvariants": 65,
            "executed_subvariants": 65,
            "killed_subvariants": 65,
            "unique_subvariants": 65,
        },
        "parent_summaries": summaries,
        "receipts": receipts,
        "all_65_subvariants_unique_hit_and_killed": True,
        "claim_boundary": validator.MUTATION_REPLAY_CLAIM_BOUNDARY,
    }


def test_pure_forged_65_receipts_are_rejected_without_replay_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    contracts = _contracts()
    monkeypatch.setattr(validator, "PHASE_ROOT", tmp_path)
    monkeypatch.setattr(validator, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(validator, "EVIDENCE_ROOT", tmp_path / "evidence")
    path = tmp_path / "b4g_mutation_execution" / "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(_forged_receipt_evidence(contracts)) + b"\n")

    report = ValidationReport(mode="full")
    assert validator._validate_mutations(report, contracts) is not None
    assert not report.passed
    codes = {failure["code"] for failure in report.failures}
    assert "NEGATIVE_CONTROL_RECEIPT_FIELDS" in codes
    assert "NEGATIVE_CONTROL_RECEIPT_IDS_NOT_UNIQUE" in codes
    assert "NEGATIVE_CONTROL_ARTIFACT_INVENTORY" in codes
