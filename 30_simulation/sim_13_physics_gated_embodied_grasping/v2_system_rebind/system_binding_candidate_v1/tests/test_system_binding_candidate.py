from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from system_binding_candidate.evaluator import (
    CONTRACT_REL,
    GATE_REL,
    MANIFEST_REL,
    PACKAGE_ROOT,
    RECEIPT_REL,
    audit_authority,
    audit_urdf,
    build_outputs,
    evaluate,
    file_record,
    find_repo_root,
    load_json,
    sha256_bytes,
)


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture(scope="module")
def contract() -> dict:
    return load_json(PACKAGE_ROOT / CONTRACT_REL)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return evaluate()


def test_all_23_hash_pins_match(receipt: dict) -> None:
    assert receipt["source_pin_audit"]["count"] == 23
    assert receipt["source_pin_audit"]["all_match"] is True
    assert all(row["match"] for row in receipt["source_pin_audit"]["records"].values())


def test_unified_urdf_topology_and_accepted_subtree(receipt: dict) -> None:
    audit = receipt["urdf_static_audit"]
    assert audit["all_checks_pass"] is True
    assert audit["facts"]["links"] == 19
    assert audit["facts"]["joints"] == 18
    assert audit["facts"]["actuated_dof"] == 8
    assert audit["facts"]["total_mass_kg"] == "31.022864807342987"
    assert audit["facts"]["accepted_b601_mass_kg"] == "4.695555949342986"
    assert audit["facts"]["accepted_b601_semantic_digest"] == audit["facts"]["system_b601_semantic_digest"]


def test_interface_hash_crossbinding_is_exact(receipt: dict) -> None:
    crosscheck = receipt["interface_pin_crosscheck"]
    assert crosscheck["all_checks_pass"] is True
    assert len(crosscheck["checks"]) == 14
    assert all(crosscheck["checks"].values())


def test_backend_passes_do_not_promote_authority(receipt: dict) -> None:
    assert receipt["backend_receipt_audit"]["all_checks_pass"] is True
    assert receipt["authority_hold_audit"]["all_checks_pass"] is True
    assert receipt["current_sim13_system_binding_gate_passed"] is False
    assert receipt["non_abort_authorized"] is False
    assert receipt["maximum_claim"] == "RESEARCH_CANDIDATE_LOAD__ABORT_ONLY"


def test_all_required_interface_authority_fields_are_false(receipt: dict) -> None:
    values = receipt["authority_hold_audit"]["interface_false_values"]
    assert len(values) == 10
    assert all(value is False for value in values.values())


def test_g12_and_m01_are_explicit_holds(receipt: dict) -> None:
    checks = receipt["authority_hold_audit"]["checks"]
    assert checks["g12_harness_remains_fail_closed_11_of_12"] is True
    assert checks["m01_registry_remains_11166_unassessed_fail_closed"] is True
    assert checks["m01_execution_remains_presearch_hold"] is True


def test_hash_mutation_is_rejected(repo_root: Path, contract: dict) -> None:
    with TemporaryDirectory(prefix="hash_nc_", dir=PACKAGE_ROOT) as directory:
        temp_root = Path(directory)
        path = temp_root / "mutated.urdf"
        path.write_bytes((repo_root / contract["input_pins"]["system_urdf"]["path"]).read_bytes() + b"\n")
        pin = deepcopy(contract["input_pins"]["system_urdf"])
        pin["path"] = path.relative_to(temp_root).as_posix()
        record = file_record(temp_root, pin)
        assert record["exists"] is True
        assert record["match"] is False


def test_accepted_subtree_semantic_mutation_is_rejected(repo_root: Path, contract: dict) -> None:
    accepted = repo_root / contract["input_pins"]["accepted_b601_urdf"]["path"]
    system = repo_root / contract["input_pins"]["system_urdf"]["path"]
    with TemporaryDirectory(prefix="semantic_nc_", dir=PACKAGE_ROOT) as directory:
        mutated = Path(directory) / "mutated.urdf"
        text = system.read_text(encoding="utf-8")
        assert '<axis xyz="0 0 -1"' in text
        mutated.write_text(text.replace('<axis xyz="0 0 -1"', '<axis xyz="0 0 1"', 1), encoding="utf-8")
        audit = audit_urdf(mutated, accepted, contract)
        assert audit["checks"]["accepted_b601_semantic_subtree_exact"] is False
        assert audit["all_checks_pass"] is False


def test_caller_supplied_owner_true_cannot_create_system_authority(repo_root: Path, contract: dict) -> None:
    pins = contract["input_pins"]
    interface = yaml.safe_load((repo_root / pins["mech_rl_system_interface_v2"]["path"]).read_text(encoding="utf-8"))
    interface["authority"]["current_values"]["owner_accepted"] = True
    g12 = load_json(repo_root / pins["g12_mech_to_embodied_handoff_gate"]["path"])
    registry = load_json(repo_root / pins["m01_collision_registry_gate"]["path"])
    execution = load_json(repo_root / pins["m01_execution_closure_gate"]["path"])
    audit = audit_authority(interface, g12, registry, execution, contract)
    assert audit["checks"]["interface_required_false_fields_are_exact_false"] is False
    assert audit["sim13_system_binding_gate_passed"] is False
    assert audit["maximum_operational_state"] == "ABORT_ONLY"


def test_outputs_are_deterministic_and_committed() -> None:
    first = build_outputs()
    second = build_outputs()
    assert first == second
    for rel, expected in zip((RECEIPT_REL, GATE_REL, MANIFEST_REL), first, strict=True):
        assert (PACKAGE_ROOT / rel).read_bytes() == expected


def test_gate_never_claims_non_abort() -> None:
    gate = load_json(PACKAGE_ROOT / GATE_REL)
    assert gate["candidate_static_gate_passed"] is True
    assert gate["sim13_system_binding_gate_passed"] is False
    assert gate["maximum_operational_state"] == "ABORT_ONLY"
    assert gate["non_abort_authorized"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_manifest_binds_local_evaluator_and_tests() -> None:
    manifest = load_json(PACKAGE_ROOT / MANIFEST_REL)
    sources = manifest["local_sources"]
    assert len(sources) == 8
    assert "system_binding_candidate/evaluator.py" in sources
    assert "tests/test_system_binding_candidate.py" in sources
    for record in sources.values():
        raw = (PACKAGE_ROOT / record["path"]).read_bytes()
        assert record["sha256"] == sha256_bytes(raw)
        assert record["bytes"] == len(raw)
