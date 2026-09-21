from __future__ import annotations

import ast
import json
from pathlib import Path

from conftest import HERE, has_null_leaf, load_contract
from validate_phase_b4g_r2_contract import expand_matrix, verify_parent_roots, verify_raw_inventory, verify_sources


def test_upstream_sources_raw_inventory_and_recursive_roots_hold() -> None:
    sources = load_contract("PHASE_B4G_R2_SOURCE_BINDINGS_V1.json")
    assert verify_sources(sources)["pass"] is True
    raw = verify_raw_inventory(sources)
    assert raw["pass"] is True
    assert (raw["json_count"], raw["npz_count"], raw["file_count"]) == (144, 120, 264)
    assert raw["canonical_sha256"] == "916F395EFEEEE3C234C7D3F361BFFB6134D060577A05ADEE0166F8F19CD43DD5"
    assert verify_parent_roots(sources) == {"b4g_source_freeze_pass": True, "r1_terminal_pass": True}


def test_all_json_artifacts_have_no_null_or_unresolved_marker() -> None:
    for path in HERE.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert not has_null_leaf(payload), path
    assert not has_null_leaf(expand_matrix())
    for name in ("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json", "PHASE_B4G_R2_NUMERICAL_ACCEPTANCE_V1.json", "PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json"):
        payload = load_contract(name)
        text = str(payload)
        assert "PEND" + "ING" not in text
        assert "TO_" + "BE_" not in text


def test_governance_freezes_contract_but_holds_execution() -> None:
    governance = load_contract("PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json")
    assert all(governance["contract_frozen_true"].values())
    assert all(value is False for value in governance["required_false"].values())
    assert governance["gate_status_exact"] == "PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY"
    assert governance["execution_readiness_status_exact"] == "HOLD_R2_PREFLIGHT_EXECUTION_NO_IMPLEMENTED_REHYDRATOR_OR_R2_SOURCE_FREEZE"


def test_negative_controls_cover_all_registered_kill_surfaces() -> None:
    governance = load_contract("PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json")
    controls = governance["negative_controls"]
    assert governance["negative_control_count"] == len(controls) == len(set(controls)) == 46
    joined = " ".join(controls)
    for token in ("SINGLE_RK4", "ACQ_NATIVE_CHANNEL", "A0_PRE_OR_POST", "REHYDRATOR_ONE_FLOAT", "REHYDRATOR_SHAPE", "REHYDRATOR_DTYPE", "NAN_OR_INFINITY", "COMMON_DESCENDANT_GIVEN_G12", "CUMULATIVE_HISTORY", "EMPIRICAL_ORDER", "SCHEDULE_CASE_MISSING", "SOURCE_FREEZE", "NULL_JSON", "CONTRACTION_NOT_EQUIVALENT", "DIRECT_ORDER_ZERO", "QUATERNION_SIGN", "STATE_GROUP_FIELD_MAP", "EXCLUSION_POINTER", "G04_POWER_TOLERANCE", "CACHE_TEMP_PYC_SOLVER"):
        assert token in joined


def test_independent_audit_does_not_import_validator_or_old_solver() -> None:
    path = HERE / "independent_audit_phase_b4g_r2_contract.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("validate_phase_b4g_r2_contract" in name for name in imported)
    assert not any("b4g_solver" in name for name in imported)


def test_package_contains_no_solver_or_physics_artifact() -> None:
    guard = load_contract("PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json")["recursive_artifact_guard"]
    paths = list(HERE.rglob("*"))
    forbidden_suffixes = set(guard["forbidden_file_suffixes"])
    forbidden_directories = set(guard["forbidden_directory_names"])
    assert not any(path.suffix.lower() in forbidden_suffixes for path in paths if path.is_file())
    assert not any(path.name in forbidden_directories for path in paths if path.is_dir())
    assert not any(token in path.name.lower() for token in guard["forbidden_file_name_substrings"] for path in paths if path.is_file())
    imported = []
    for path in HERE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
    assert not any(token in module for token in guard["forbidden_solver_module_tokens"] for module in imported)
    assert guard["validator_audit_and_pytest_must_each_enforce"] is True
