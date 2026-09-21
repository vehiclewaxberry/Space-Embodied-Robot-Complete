from __future__ import annotations

import ast
from pathlib import Path

import validate_phase_b4g_r1_contract as validator


PHASE = Path(__file__).resolve().parent.parent


def test_active_source_freeze_terminal_chain_still_passes(bindings):
    by_id = {row["id"]: row for row in bindings["sources"]}
    terminal_path = validator.PROJECT_ROOT / by_id["b4g_active_execution_source_freeze_terminal"]["path"]
    terminal = validator.load_json(terminal_path)
    gate_record = terminal["records"][0]
    gate_path = validator.PROJECT_ROOT / gate_record["path"]
    gate = validator.load_json(gate_path)
    manifest_record = gate["execution_source_manifest"]
    manifest_path = validator.PROJECT_ROOT / manifest_record["path"]
    manifest = validator.load_json(manifest_path)
    assert validator.sha256_file(gate_path) == gate_record["sha256"]
    assert validator.sha256_file(manifest_path) == manifest_record["sha256"]
    assert terminal["self_excluded"] is True and terminal["acyclic"] is True
    assert gate["final"] is True and manifest["source_count"] == 52
    assert validator.canonical_sha256(manifest["sources"]) == "6DA4103408E07F131F554FB800886C4CEFF25BDF77453EC35CD0F478A185E457"
    assert all(
        (validator.PROJECT_ROOT / row["path"]).stat().st_size == row["bytes"]
        and validator.sha256_file(validator.PROJECT_ROOT / row["path"]) == row["sha256"]
        for row in manifest["sources"]
    )


def test_prospective_steps_are_planned_not_authorized(closure_contract):
    plan = closure_contract["prospective_remediation"]
    assert plan["classification"] == "PLANNED_NOT_AUTHORIZED"
    assert plan["new_campaign_authorized"] is False
    assert plan["candidate_midpoint_steps"]["step_s"] == [0.00025, 0.000125, 0.0000625]
    assert plan["candidate_midpoint_steps"]["step_ms"] == [0.25, 0.125, 0.0625]
    assert "no J/s power margin" in plan["candidate_midpoint_steps"]["unit_rule"]
    assert len(plan["forbidden_shortcuts"]) == 9


def test_acquisition_and_propagation_preflights_are_separate(closure_contract):
    preflight = closure_contract["prospective_remediation"]["required_preflight_before_campaign_decision"]
    assert "lane-specific" in preflight["acquisition_convergence"]
    assert "common-initial-state" in preflight["propagation_convergence"]
    assert "must not overwrite" in preflight["propagation_convergence"]
    assert closure_contract["g12_and_a2_ruling"]["g06_refinement_alone_resolves_g12"] is False


def test_all_authority_and_physical_claims_remain_false(closure_contract):
    assert all(value is False for value in closure_contract["required_false"].values())
    assert closure_contract["formal_sim13_v2_state_unchanged"] == {
        "passed": 15,
        "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
    }
    assert closure_contract["memory_record"] == {
        "memory_gate_applicable": False,
        "memory_gate_passed": False,
        "owner_override_used": False,
        "classification": "BOUNDED_DIAGNOSTIC_CONTRACT_ONLY",
    }


def test_independent_audit_does_not_import_validator_or_solver():
    source = (PHASE / "independent_audit_phase_b4g_r1_contract.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("validate_phase_b4g_r1_contract" in name for name in imported)
    assert not any("b4g_solver" in name or "b4g_validation" in name for name in imported)


def test_package_contains_no_urdf():
    assert not any(path.suffix.lower() == ".urdf" for path in PHASE.rglob("*"))
