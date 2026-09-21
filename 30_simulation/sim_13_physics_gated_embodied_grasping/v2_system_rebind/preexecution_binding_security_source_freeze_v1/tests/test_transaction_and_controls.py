from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath

import pytest

import freeze_preexecution_security_sources as freeze_module
from freeze_preexecution_security_sources import package_asset_cache_findings, package_inventory_findings
from preexec_security.evidence_dag import FALSE_FIELDS, build_gate, build_terminal, document_receipt
from preexec_security.negative_controls import ACTION_ABORT, run_security_negative_controls
from preexec_security.transaction_contract import (
    TransactionContractError,
    canonical_transaction_contract,
    synthetic_transition_trace,
    validate_transaction_contract,
    validate_transition_trace,
)


PACKAGE = Path(__file__).resolve().parents[1]


def test_committed_transaction_contract_matches_code_and_executes_nothing() -> None:
    committed = (PACKAGE / "contracts/UNIFIED_R2_ATOMIC_GENERATION_TRANSACTION_CONTRACT_V1.json").read_bytes()
    result = validate_transaction_contract(committed)
    assert result == canonical_transaction_contract()
    assert result["source_freeze_execution_state"] == {
        "generator_invoked": False, "artifact_emitted": False, "receipt_emitted": False,
    }


def test_synthetic_transition_trace_enforces_path_order_and_no_execution() -> None:
    trace = synthetic_transition_trace()
    result = validate_transition_trace(trace)
    assert result["valid"] and result["atomic_replace_precedes_receipt"]
    for field, mutation in (
        ("target_path", "elsewhere.urdf"),
        ("temporary_path", "wrong.tmp"),
        ("events", list(reversed(trace["events"]))),
        ("generator_invoked", True),
        ("artifact_emitted", True),
    ):
        forged = copy.deepcopy(trace)
        forged[field] = mutation
        with pytest.raises(TransactionContractError):
            validate_transition_trace(forged)


def test_nc15_nc16_nc20_exact_repeated_source_only_frontier() -> None:
    assert ACTION_ABORT["grasp_candidate_id"] == ACTION_ABORT["capture_timing_id"] == "__ABORT__"
    result = run_security_negative_controls()
    assert result["all_requested_controls_passed"] is True
    assert result["controls_passed"] == ["NC15", "NC16", "NC20"]
    assert result["parent_baseline_hashes_unchanged"] is True
    assert result["parent_formal_nc_passed"] == 15
    assert result["formal_nc_promotion"] == 0
    assert result["additive_effective_source_only_frontier_passed"] == 18
    assert result["remaining_dependency_holds"] == ["NC18", "NC19"]
    assert result["contact_release_eligible"] is False
    for group in result["groups"]:
        assert group["deterministic_repeat"] is True
        assert len(group["records"]) == 2
        assert all(record["non_abort_execution_count"] == 0 for record in group["records"])


def test_actual_future_interface_and_system_urdf_remain_absent() -> None:
    project = PACKAGE.parents[3]
    interface = project / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    urdf = project / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
    assert not interface.exists()
    assert not urdf.exists()
    assert package_asset_cache_findings() == []
    assert package_inventory_findings() == []


def test_asset_scanner_detects_common_mesh_and_empty_cache_directory(monkeypatch) -> None:
    class FakeEntry:
        def __init__(self, relative: str, *, directory: bool) -> None:
            self._relative = PurePosixPath(relative)
            self._directory = directory

        @property
        def name(self) -> str:
            return self._relative.name

        @property
        def suffix(self) -> str:
            return self._relative.suffix

        def is_dir(self) -> bool:
            return self._directory

        def is_file(self) -> bool:
            return not self._directory

        def relative_to(self, _root):
            return self._relative

    class FakeRoot:
        def rglob(self, _pattern):
            return [
                FakeEntry("synthetic_package/__pycache__", directory=True),
                FakeEntry("synthetic_package/forbidden.obj", directory=False),
            ]

    root = FakeRoot()
    monkeypatch.setattr(freeze_module, "HERE", root)
    monkeypatch.setattr(freeze_module, "PROJECT", root)
    findings = freeze_module.package_asset_cache_findings()
    assert any(item.startswith("PROHIBITED_CACHE_DIRECTORY:") for item in findings)
    assert any(item.endswith("forbidden.obj") for item in findings)


def test_terminal_is_cryptographically_bound_to_recomputed_gate_document() -> None:
    manifest = {
        "source_static_pass": True,
        "source_static_findings": [],
        "package_inventory_findings": [],
    }
    negative = {
        "all_requested_controls_passed": True,
        "controls_passed": ["NC15", "NC16", "NC20"],
        "parent_formal_nc_passed": 15,
        "parent_formal_nc_total": 20,
        "formal_nc_promotion": 0,
        "additive_effective_source_only_frontier_passed": 18,
        "remaining_dependency_holds": ["NC18", "NC19"],
    }
    pytest_receipt = {
        "schema": "PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1",
        "passed": 1,
        "collected": 1,
        "failed": 0,
        "cacheprovider_disabled": True,
        "bytecode_write_disabled": True,
    }
    validation = {
        "status": "PASS_SOURCE_FREEZE_ONLY",
        "checks_passed": 1,
        "checks_total": 1,
        **{field: False for field in FALSE_FIELDS},
    }
    audit = {
        "status": "PASS_INDEPENDENT_SOURCE_FREEZE_AUDIT",
        "checks_passed": 1,
        "checks_total": 1,
        **{field: False for field in FALSE_FIELDS},
    }
    gate = build_gate(
        manifest=manifest,
        negative_controls=negative,
        pytest_receipt=pytest_receipt,
        validation=validation,
        independent_audit=audit,
    )
    assert gate["status"] == "PASS_SOURCE_FREEZE_ONLY"
    terminal = build_terminal(gate)
    assert terminal["gate"] == document_receipt(
        "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
        gate,
    )
    assert all(gate[field] is terminal[field] is False for field in FALSE_FIELDS)
    forged = copy.deepcopy(gate)
    forged["status"] = "FAIL_SOURCE_FREEZE"
    assert terminal["gate"] != document_receipt(
        "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
        forged,
    )


@pytest.mark.parametrize(
    "injected_path",
    [
        "evidence/shadow.json",
        "results/shadow.sdf",
        "manifest/shadow_dir/shadow.xacro",
    ],
)
def test_full_package_allowlist_rejects_shadow_files_in_excluded_output_domains(
    injected_path: str, monkeypatch,
) -> None:
    class FakeEntry:
        def __init__(self, relative: str, *, directory: bool) -> None:
            self._relative = PurePosixPath(relative)
            self._directory = directory

        @property
        def name(self) -> str:
            return self._relative.name

        @property
        def suffix(self) -> str:
            return self._relative.suffix

        def is_dir(self) -> bool:
            return self._directory

        def is_file(self) -> bool:
            return not self._directory

        def relative_to(self, _root):
            return self._relative

    class FakeRoot:
        def rglob(self, _pattern):
            parents = [
                FakeEntry(parent.as_posix(), directory=True)
                for parent in reversed(PurePosixPath(injected_path).parents)
                if parent.as_posix() != "."
            ]
            return parents + [FakeEntry(injected_path, directory=False)]

    root = FakeRoot()
    monkeypatch.setattr(freeze_module, "HERE", root)
    monkeypatch.setattr(freeze_module, "PROJECT", root)
    inventory = freeze_module.package_inventory_findings(set())
    assert f"UNEXPECTED_PACKAGE_FILE:{injected_path}" in inventory
    if "shadow_dir" in injected_path:
        assert "UNEXPECTED_PACKAGE_DIRECTORY:manifest/shadow_dir" in inventory
    prohibited = freeze_module.package_asset_cache_findings()
    if PurePosixPath(injected_path).suffix in {".sdf", ".xacro"}:
        assert any(item.endswith(injected_path) for item in prohibited)
