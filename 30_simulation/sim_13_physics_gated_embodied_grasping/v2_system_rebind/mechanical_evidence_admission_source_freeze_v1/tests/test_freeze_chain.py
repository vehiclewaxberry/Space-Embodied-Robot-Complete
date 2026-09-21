from __future__ import annotations

import json
from pathlib import Path

from validate_mechanical_evidence_admission_source_freeze import validate


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_validator_replays_exactly_read_only():
    result = validate()
    assert result["pass"] is True
    assert result["checks_passed"] == result["checks_total"]


def test_gate_and_terminal_are_capped_and_fail_closed():
    gate = json.loads((PACKAGE_ROOT / "results" / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_GATE_V1.json").read_text(encoding="utf-8"))
    terminal = json.loads((PACKAGE_ROOT / "results" / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_TERMINAL_V1.json").read_text(encoding="utf-8"))
    ceiling = "PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY"
    assert gate["overall_status"] == terminal["terminal_status"] == ceiling
    for field in ("system_urdf_available", "current_system_bound", "physical_contact_ready", "dynamics_capture_entry_authorized", "next_stage_authorized"):
        assert gate[field] is False
        assert terminal[field] is False
    assert gate["generated_cad_step_mesh_urdf_fea_or_trajectory"] is False
