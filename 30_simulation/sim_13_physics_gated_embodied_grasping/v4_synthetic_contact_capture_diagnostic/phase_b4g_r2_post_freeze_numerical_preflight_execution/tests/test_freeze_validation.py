from __future__ import annotations

import ast
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import sys

import independent_audit_phase_b4g_r2_execution_source_freeze as independent
import verify_phase_b4g_r2_read_only_replay as read_only_replay
from freeze_phase_b4g_r2_execution_sources import _is_nc_only_partial, build_source_manifest
from r2_preflight.negative_controls import build_negative_control_evidence
from r2_preflight.rehydrator import load_donor_fixture
from r2_preflight.schedule import MATRIX_SHA256, SCHEDULE_SHA256, expand_matrix, generate_schedule
from r2_preflight.strict_json import canonical_sha256, load_path
from validate_phase_b4g_r2_execution_source_freeze import (
    HERE,
    NC_CONTRACT,
    PROJECT_ROOT,
    SOURCE_BINDINGS,
    artifact_guard,
    local_source_inventory,
    negative_control_evidence_check,
    negative_control_value_check,
)
from verify_phase_b4g_r2_read_only_replay import COMMANDS, package_snapshot, verify_published_chain


@lru_cache(maxsize=1)
def _generated_nc_evidence() -> dict:
    bindings = load_path(SOURCE_BINDINGS)
    donor_row = next(row for row in bindings["sources"] if row["id"] == "common_prop_donor_raw_slot_052")
    donor = load_donor_fixture(PROJECT_ROOT / donor_row["path"])
    inventory_sha256 = canonical_sha256(local_source_inventory(HERE))
    return build_negative_control_evidence(
        project_root=PROJECT_ROOT,
        package_root=HERE,
        donor=donor,
        source_inventory_sha256=inventory_sha256,
    )


def _valid_nc_evidence() -> dict:
    return deepcopy(_generated_nc_evidence())


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append(node.module or "")
    return result


def test_manifest_is_deterministic_and_excludes_output_chain() -> None:
    inventory = local_source_inventory(HERE)
    manifest = build_source_manifest(HERE)
    assert manifest["sources"] == inventory
    assert manifest["source_inventory_sha256"] == canonical_sha256(inventory)
    assert manifest["self_excluded"] is True
    assert manifest["acyclic"] is True
    assert manifest["terminal_excluded"] is True
    assert all(not row["path"].startswith(("evidence/", "results/")) for row in inventory)
    assert "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json" not in {row["path"] for row in inventory}


def test_validator_and_audit_are_import_independent() -> None:
    validator_imports = _imports(HERE / "validate_phase_b4g_r2_execution_source_freeze.py")
    audit_imports = _imports(HERE / "independent_audit_phase_b4g_r2_execution_source_freeze.py")
    assert not any("independent_audit" in name or name.startswith("tests") for name in validator_imports)
    assert not any("validate_phase" in name or name.startswith("tests") or name.startswith("r2_preflight") for name in audit_imports)


def test_matrix_and_schedule_have_two_independent_exact_derivations() -> None:
    production_matrix = expand_matrix()
    production_schedule = generate_schedule()
    audit_matrix = independent.independent_matrix()
    audit_schedule = independent.independent_schedule()
    assert production_matrix == audit_matrix
    assert production_schedule == audit_schedule
    assert canonical_sha256(production_matrix) == MATRIX_SHA256
    assert canonical_sha256(production_schedule) == SCHEDULE_SHA256
    assert len(production_matrix) == len(production_schedule) == 78


def test_negative_control_evidence_missing_is_fail_closed() -> None:
    result = negative_control_evidence_check(HERE / "evidence/NEVER_CREATED_MISSING_NC_EVIDENCE.json")
    assert result["passed"] is False
    assert result["reason"] == "NC_EVIDENCE_MISSING_OR_LINK"


def test_negative_control_evidence_requires_exact_46_and_execution_false() -> None:
    contract = load_path(NC_CONTRACT)
    value = _valid_nc_evidence()
    inventory_sha256 = canonical_sha256(local_source_inventory(HERE))
    assert negative_control_value_check(
        value,
        contract,
        expected_source_inventory_sha256=inventory_sha256,
        package_root=HERE,
    )["passed"] is True

    mutation = deepcopy(value)
    mutation["controls"][0]["killed"] = False
    assert negative_control_value_check(mutation, contract, expected_source_inventory_sha256=inventory_sha256, package_root=HERE)["passed"] is False

    mutation = deepcopy(value)
    mutation["r2_execution_negative_controls_executed"] = True
    assert negative_control_value_check(mutation, contract, expected_source_inventory_sha256=inventory_sha256, package_root=HERE)["passed"] is False


def test_structural_status_is_reserved_for_nc21_and_nc22() -> None:
    contract = load_path(NC_CONTRACT)
    inventory_sha256 = canonical_sha256(local_source_inventory(HERE))
    value = _valid_nc_evidence()
    value["controls"][0]["status"] = "STRUCTURAL_SOURCE_SIGNATURE_KILLED"
    assert negative_control_value_check(value, contract, expected_source_inventory_sha256=inventory_sha256, package_root=HERE)["passed"] is False

    value = _valid_nc_evidence()
    nc21 = next(row for row in value["controls"] if row["id"].startswith("R2NC21_"))
    nc21["status"] = "SOURCE_ONLY_MUTATION_KILLED"
    assert negative_control_value_check(value, contract, expected_source_inventory_sha256=inventory_sha256, package_root=HERE)["passed"] is False


def test_generated_negative_control_evidence_has_bound_witnesses() -> None:
    value = _valid_nc_evidence()
    assert value["killed_count"] == 46
    assert value["source_only_negative_controls_killed"] is True
    assert len(value["implementation_files"]) == 9
    assert canonical_sha256(value["implementation_files"]) == value["implementation_sha256"]
    assert all(row["implementation_sha256"] == value["implementation_sha256"] for row in value["controls"])
    assert all(row["fixture_class"] == "SOURCE_ONLY_SYNTHETIC_MUTATION" and row["witness"] for row in value["controls"])


def test_governance_keeps_all_execution_and_authority_flags_false() -> None:
    governance = load_path(HERE / "contracts/PHASE_B4G_R2_EXECUTION_GOVERNANCE_V1.json")
    freeze_contract = load_path(HERE / "contracts/PHASE_B4G_R2_EXECUTION_TOOLING_FREEZE_CONTRACT_V1.json")
    assert all(value is False for value in governance["required_false"].values())
    assert all(type(value) is int and value == 0 for value in governance["required_zero"].values())
    assert governance["authorized_execution_path_status_exact"] == "NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE"
    assert governance["authorization_boundary"]["bound_direct_owner_source_id"] == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY"
    assert governance["authorization_boundary"]["successful_authorization_path_implemented_in_this_version"] is False
    replay = freeze_contract["validator_and_audit_independence"]
    assert replay["standalone_default_mode"] == "READ_ONLY_RECEIPT_VERIFY"
    assert replay["receipt_write_requires_explicit_cli_flag"] == "--write-receipt"
    assert replay["receipt_write_flag_abbreviation_allowed"] is False
    assert replay["validator_audit_pytest_replay_must_preserve_all_package_bytes"] is True
    assert replay["read_only_replay_captures_after_delta_on_subcommand_failure"] is True
    assert replay["read_only_replay_revalidates_gate_and_terminal_hash_chain"] is True
    assert len(freeze_contract["publication_chain"]) == 6


def test_recursive_artifact_and_import_guard_is_clean() -> None:
    result = artifact_guard(HERE)
    assert result["passed"] is True, result


def test_partial_status_is_reserved_for_nc_evidence_only() -> None:
    validation = {
        "score": {"failed": ["R2SV09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46"]},
        "checks": [],
    }
    audit = {
        "score": {"failed": [
            "R2SA09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46",
            "R2SA10_VALIDATOR_RECEIPT_CONSISTENT_WITH_INDEPENDENT_RESULT",
        ]},
        "checks": [],
    }
    assert _is_nc_only_partial(validation, audit) is True
    validation["score"]["failed"].append("R2SV07_MATRIX_AND_BLOCKED_SCHEDULE_EXACT")
    assert _is_nc_only_partial(validation, audit) is False


def test_standalone_validator_and_audit_are_default_read_only() -> None:
    before = package_snapshot(HERE)
    for script, expected_marker in (
        ("validate_phase_b4g_r2_execution_source_freeze.py", "READ_ONLY_RECEIPT_VERIFY"),
        ("independent_audit_phase_b4g_r2_execution_source_freeze.py", "READ_ONLY_RECEIPT_VERIFY"),
    ):
        completed = subprocess.run(
            [sys.executable, "-B", script],
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert expected_marker in completed.stdout
        assert "'receipt_match': True" in completed.stdout
        abbreviated = subprocess.run(
            [sys.executable, "-B", script, "--w"],
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
        )
        assert abbreviated.returncode == 2
        assert "unrecognized arguments: --w" in abbreviated.stderr
    assert package_snapshot(HERE) == before


def test_read_only_replay_regression_covers_pytest_without_freeze() -> None:
    names = [name for name, _ in COMMANDS]
    flattened = [token for _, command in COMMANDS for token in command]
    assert names == ["validator", "independent_audit", "pytest"]
    assert "pytest" in flattened
    assert "freeze_phase_b4g_r2_execution_sources.py" not in flattened
    assert verify_published_chain()["passed"] is True


def test_read_only_replay_reports_delta_even_when_subcommand_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        read_only_replay,
        "COMMANDS",
        (("synthetic_failure", (sys.executable, "-B", "-c", "raise SystemExit(7)")),),
    )
    assert read_only_replay.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "FAIL_READ_ONLY_COMMAND"
    assert result["commands"][0]["returncode"] == 7
    assert result["delta"] == {"added": [], "changed": [], "removed": []}
    assert result["published_chain_before"]["passed"] is True
    assert result["published_chain_after"]["passed"] is True
