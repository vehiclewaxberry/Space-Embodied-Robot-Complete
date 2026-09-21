from __future__ import annotations

import pytest

from freeze_current_system_handoff_intake import build_bundle
from current_handoff.freeze_support import (
    FROZEN_PACKAGE_FILE_ALLOWLIST,
    forbidden_package_entries,
    package_file_paths,
    validate_frozen_package_file_set,
)
from current_handoff.schema import FROZEN_BINDING_DIGEST, MANDATORY_FALSE
from current_handoff.strict_io import IntakeError
from validate_current_system_handoff_intake_source_freeze import validate


def test_in_memory_gate_is_source_only_and_actual_intake_holds():
    gate = build_bundle()["gate"]
    assert gate["overall_status"] == "PASS_SOURCE_FREEZE_ONLY"
    assert gate["current_intake_status"] == "HOLD_INCOMPLETE"
    assert gate["urdf_generator_invoked"] is False
    assert gate["generated_cad_step_mesh_urdf_or_physics_assets"] is False
    assert gate["negative_controls_passed"] == gate["negative_controls_total"] == 31
    assert gate["independent_audit_checks_passed"] == gate["independent_audit_checks_total"] == 21
    assert gate["complete_package_file_allowlist_exact"] is True
    assert gate["package_files_frozen"] == 30
    assert gate["frozen_binding_digest"] == FROZEN_BINDING_DIGEST


def test_terminal_is_not_floating_and_all_twelve_flags_remain_false():
    bundle = build_bundle()
    assert bundle["terminal"]["evidence_dag_terminal_commit"] is True
    assert tuple(bundle["terminal"]["flags"]) == MANDATORY_FALSE
    assert all(value is False for value in bundle["terminal"]["flags"].values())


def test_frozen_bundle_exact_replay_validator_passes():
    result = validate()
    assert result["pass"] is True


def test_no_forbidden_geometry_or_cache_file_or_directory_exists():
    assert forbidden_package_entries() == []


def test_complete_package_file_allowlist_is_exact_and_rejects_any_extra_or_missing_file():
    assert len(FROZEN_PACKAGE_FILE_ALLOWLIST) == 30
    assert package_file_paths() == FROZEN_PACKAGE_FILE_ALLOWLIST
    validate_frozen_package_file_set()
    with pytest.raises(IntakeError, match="unexpected"):
        validate_frozen_package_file_set((*FROZEN_PACKAGE_FILE_ALLOWLIST, "evidence/ROGUE.json"))
    with pytest.raises(IntakeError, match="missing"):
        validate_frozen_package_file_set(FROZEN_PACKAGE_FILE_ALLOWLIST[1:])
