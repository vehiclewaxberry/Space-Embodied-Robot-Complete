"""Focused negative tests for campaign orchestration evidence guards.

This module lives beside the implementation because the campaign runner owns no
files in the frozen preregistration test tree.  Invoke it explicitly with pytest.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
import pytest

import freeze_phase_b4g_execution_sources as freeze_source_module
from . import orchestrator as orchestrator_module
from . import source_guard as source_guard_module
from .evidence import (
    ACTIVE_NPZ_ARRAYS,
    POST_NPZ_ARRAYS,
    _FRESH_B3_EVENT_SOURCE,
    _clearance_certificate_payload,
    _finite_max_abs,
    _removal_mapping_pass,
    _verified_b4e_acquisition_certificate_payload,
    case_gate_records,
    compare_a2_mirror_pair,
    not_evaluated_a2_payload,
    validate_case_npz_schema,
)
from .io import (
    EvidenceIOError,
    array_payload_sha256,
    atomic_write_json,
    atomic_write_npz,
    canonical_bytes,
    canonical_sha256,
    display_path,
    read_json,
    sha256_file,
)
from .orchestrator import (
    _A0_LANE_DEFINITION,
    _SUPERSESSION_RECEIPT_RELATIVE_PATH,
    A0_PARENT_INTERCHANGE_PATH,
    CONTRACT_ROOT,
    PHASE_ROOT,
    PROJECT_ROOT,
    B4GExecutionError,
    _STALE_FINAL_RELATIVE_PATHS,
    _ensure_runtime_evidence,
    _enforce_integrity_before_publication,
    _expected_a0_parent_event_provenance,
    _sign_aligned_unit_quaternion_geodesic_rows,
    _a0_parent_oracle_arrays,
    _assert_a0_parent_matches_oracle,
    _load_b4e_active_trace_oracle,
    _load_contracts,
    _load_resumable_case,
    _prepare_output_root,
    _publish_executed_case,
    _publish_na_a2,
    _reference_eligibility,
    _require_formal_execution_source_freeze_paths,
    _safe_orphan_recovery,
    _supersede_prior_final_credit,
    _verify_a0_parent_trace_bundle,
    _verify_raw_case_inventory,
    _verify_resumed_case_against_fresh_replay,
    _write_provisional_post_campaign_snapshot,
    execute_campaign,
    execute_smoke,
    invalidate_output_root,
)
from .source_guard import (
    SourceGuardError,
    forbidden_local_artifacts,
    local_source_inventory,
    verify_execution_source_freeze,
    verify_preregistration_source_manifest,
    verify_recursive_parents,
)
from freeze_phase_b4g_execution_sources import (
    ExecutionSourceFreezeError,
    OUTPUT_ROOT_MARKER as FREEZE_OUTPUT_ROOT_MARKER,
    REQUIRED_FORMAL_ENTRYPOINTS,
    freeze_execution_sources,
)
from publish_phase_b4g_preaudit import (
    B4GPreauditPublicationError,
    _EXCLUDED_FUTURE_OUTPUTS,
    _FIXED_ROLE_COUNTS,
    _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS,
    _cleanup_stale_audit_and_final_outputs,
    _evidence_manifest_payload,
    _formal_reverification,
    _preaudit_payload,
    _require_no_active_attempt_markers,
    _run_full_validator_subprocess,
    _validated_report_payload,
    publish_preaudit,
)


def _write_required_formal_entrypoints(phase: Path) -> None:
    for name in REQUIRED_FORMAL_ENTRYPOINTS:
        (phase / name).write_text(
            f'"""Temporary test source for {name}."""\n', encoding="utf-8",
        )


def _npz_arrays(*, finite_event: bool = False) -> dict[str, np.ndarray]:
    n, s, m, u = 3, 2, 2, 1
    shapes: dict[str, tuple[int, ...]] = {
        "time_s": (n,), "service_state_29": (n, 29), "target_state_13": (n, 13),
        "command_Q_14": (n, 14), "signed_W_act_J": (n,), "left_gap_m": (n,),
        "right_gap_m": (n,), "left_gap_rate_m_s": (n,), "right_gap_rate_m_s": (n,),
        "total_linear_momentum_N_s": (n, 3), "total_angular_momentum_N_m_s": (n, 3),
        "total_kinetic_energy_J": (n,), "energy_minus_work_residual_J": (n,),
        "ideal_constraint_power_W": (n,), "contact_force_N": (n,),
        "contact_torque_N_m": (n,), "stage_time_s": (s,), "stage_code": (s,),
        "stage_service_state_29": (s, 29), "stage_command_Q_14": (s, 14),
        "stage_power_W": (s,), "stage_P_coordinates_m": (s, 2),
        "stage_gap_jacobian_P": (s, 2, 2), "stage_mass_cholesky_min_diagonal": (s,),
        "stage_domain_and_sign_pass": (s,),
    }
    if finite_event:
        shapes.update({
            "post_time_s": (m,), "post_service_state_29": (m, 29),
            "post_target_state_13": (m, 13), "post_left_gap_m": (m,),
            "post_right_gap_m": (m,), "post_left_gap_rate_m_s": (m,),
            "post_right_gap_rate_m_s": (m,), "post_total_linear_momentum_N_s": (m, 3),
            "post_total_angular_momentum_N_m_s": (m, 3),
            "post_total_kinetic_energy_J": (m,), "post_contact_force_N": (m,),
            "post_contact_torque_N_m": (m,), "post_stage_time_s": (u,),
            "post_stage_code": (u,), "post_stage_service_state_29": (u, 29),
            "post_stage_target_state_13": (u, 13), "post_stage_P_coordinates_m": (u, 2),
            "post_stage_gap_jacobian_P": (u, 2, 2),
            "post_stage_domain_and_sign_pass": (u,),
        })
    integer = {"stage_code", "post_stage_code"}
    boolean = {"stage_domain_and_sign_pass", "post_stage_domain_and_sign_pass"}
    arrays: dict[str, np.ndarray] = {}
    for name, shape in shapes.items():
        if name in boolean:
            arrays[name] = np.ones(shape, dtype=np.bool_)
        elif name in integer:
            arrays[name] = np.zeros(shape, dtype="<i8")
        else:
            arrays[name] = np.zeros(shape, dtype="<f8")
    assert set(arrays) == set(ACTIVE_NPZ_ARRAYS) | (
        set(POST_NPZ_ARRAYS) if finite_event else set()
    )
    return arrays


def _removal_post_with_impulse(value: float) -> dict[str, Any]:
    z = [float(index) for index in range(20)]
    return {
        "mapping": {
            "native_velocity_jump_maxima": {
                "service_base_linear_m_s": 0.0,
                "service_base_angular_rad_s": 0.0,
                "service_R_joint_rad_s": 0.0,
                "service_P_joint_m_s": 0.0,
                "target_linear_m_s": 0.0,
                "target_angular_rad_s": 0.0,
            },
            "z_before": z,
            "z_after": list(z),
            "linear_impulse_N_s": [value, 0.0, 0.0],
            "angular_impulse_N_m_s": [0.0, -value, 0.0],
            "kinetic_energy_jump_J": value,
            "ideal_constraint_stored_energy_J": 0.0,
        },
    }


def test_removal_mapping_accepts_parent_roundoff_below_1e12() -> None:
    passed, detail = _removal_mapping_pass(
        _removal_post_with_impulse(2.7755575615628914e-17),
    )
    assert passed is True
    assert detail["linear_impulse_N_s"][0] == 2.7755575615628914e-17


def test_removal_mapping_rejects_impulse_or_energy_above_1e12() -> None:
    passed, _ = _removal_mapping_pass(_removal_post_with_impulse(1.1e-12))
    assert passed is False


def _npz_metadata(arrays: dict[str, np.ndarray], *, finite_event: bool = False) -> dict[str, Any]:
    return {
        "responses": {
            "finite_removal_event": finite_event,
            "sample_count": int(arrays["time_s"].shape[0]),
        },
        "npz_arrays": sorted(arrays),
        "numeric_payload_sha256": array_payload_sha256(arrays),
    }


def _acquisition_certificate_fields(lane_id: str, case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    parent_evidence = PHASE_ROOT.parent / "phase_b4_post_freeze_synthetic_6d_solver" / "evidence"
    events = read_json(parent_evidence / "SIM13_V4B4E_EVENT_INPUTS_V1.json")["runs"]
    acquisitions = read_json(
        parent_evidence / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json"
    )["runs"]
    event = dict(next(row for row in events if row["run_id"] == lane_id.lower()))
    event.update({"run_id": case_id, "source": _FRESH_B3_EVENT_SOURCE})
    acquisition = dict(acquisitions[lane_id.lower()])
    acquisition["run_id"] = case_id
    payload = _verified_b4e_acquisition_certificate_payload(
        lane_id=lane_id,
        case_id=case_id,
        event=event,
        acquisition=acquisition,
    )
    event_provenance = {
        "lane_id": lane_id,
        "acquisition_certificate_payload": payload,
        "acquisition_certificate_sha256": canonical_sha256(payload),
    }
    return payload["acquisition"], event_provenance


def _fresh_certificate_inputs(
    lane_id: str, case_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    parent_evidence = (
        PHASE_ROOT.parent / "phase_b4_post_freeze_synthetic_6d_solver" / "evidence"
    )
    events = read_json(
        parent_evidence / "SIM13_V4B4E_EVENT_INPUTS_V1.json"
    )["runs"]
    acquisitions = read_json(
        parent_evidence / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json"
    )["runs"]
    event = dict(next(row for row in events if row["run_id"] == lane_id.lower()))
    acquisition = dict(acquisitions[lane_id.lower()])
    acquisition["energy_audit"] = dict(acquisition["energy_audit"])
    event.update({"run_id": case_id, "source": _FRESH_B3_EVENT_SOURCE})
    acquisition["run_id"] = case_id
    return event, acquisition


def test_fresh_b4e_certificate_accepts_one_ulp_dissipation_difference() -> None:
    lane_id, case_id = "RK4_REFERENCE", "ONE_ULP_FRESH_CASE"
    event, acquisition = _fresh_certificate_inputs(lane_id, case_id)
    fresh = float(np.nextafter(event["b3_dissipation_J"], np.inf))
    event["b3_dissipation_J"] = fresh
    acquisition["energy_audit"]["D_B3_minus_J"] = fresh
    payload = _verified_b4e_acquisition_certificate_payload(
        lane_id=lane_id, case_id=case_id,
        event=event, acquisition=acquisition,
    )
    assert payload["event"]["b3_dissipation_J"] == fresh


def test_fresh_b4e_certificate_rejects_three_ulp_dissipation_difference() -> None:
    lane_id, case_id = "RK4_REFERENCE", "THREE_ULP_FRESH_CASE"
    event, acquisition = _fresh_certificate_inputs(lane_id, case_id)
    fresh = float(event["b3_dissipation_J"])
    for _ in range(3):
        fresh = float(np.nextafter(fresh, np.inf))
    event["b3_dissipation_J"] = fresh
    acquisition["energy_audit"]["D_B3_minus_J"] = fresh
    with pytest.raises(ValueError, match="EXCEEDS_TWO_ULP"):
        _verified_b4e_acquisition_certificate_payload(
            lane_id=lane_id, case_id=case_id,
            event=event, acquisition=acquisition,
        )


def test_fresh_b4e_certificate_rejects_any_extra_pointer_difference() -> None:
    lane_id, case_id = "RK4_REFERENCE", "EXTRA_POINTER_FRESH_CASE"
    event, acquisition = _fresh_certificate_inputs(lane_id, case_id)
    event["time_s"] = float(np.nextafter(event["time_s"], np.inf))
    with pytest.raises(ValueError, match="UNREGISTERED_TEMPLATE_DIFFERENCE"):
        _verified_b4e_acquisition_certificate_payload(
            lane_id=lane_id, case_id=case_id,
            event=event, acquisition=acquisition,
        )


def test_fresh_b4e_certificate_rejects_json_numeric_type_substitution() -> None:
    lane_id, case_id = "RK4_REFERENCE", "TYPE_SUBSTITUTION_FRESH_CASE"
    event, acquisition = _fresh_certificate_inputs(lane_id, case_id)
    event["index"] = float(event["index"])
    with pytest.raises(ValueError, match="UNREGISTERED_TEMPLATE_DIFFERENCE"):
        _verified_b4e_acquisition_certificate_payload(
            lane_id=lane_id, case_id=case_id,
            event=event, acquisition=acquisition,
        )


def _pre_run_context(root: Path) -> dict[str, Any]:
    ledger_core = {
        "schema": "SIM13_V4B4G_PRE_RUN_EXECUTION_LEDGER_V1",
        "test": True,
    }
    ledger = {**ledger_core, "ledger_payload_sha256": canonical_sha256(ledger_core)}
    ledger_path = root / "evidence" / "ledger.json"
    snapshot_path = root / "evidence" / "snapshot.json"
    atomic_write_json(ledger_path, ledger)
    atomic_write_json(snapshot_path, {"schema": "TEST_PRE_SNAPSHOT"})
    parent_root = root / "evidence" / "a0_parent_reference_traces"
    parent_root.mkdir(parents=True)
    traces: list[dict[str, Any]] = []
    active_oracle, active_oracle_binding = _load_b4e_active_trace_oracle()
    for lane, (method, step_s) in _A0_LANE_DEFINITION.items():
        parent_arrays = _a0_parent_oracle_arrays(lane, active_oracle)
        npz_path = parent_root / f"{lane}.npz"
        receipt = atomic_write_npz(npz_path, parent_arrays)
        event_provenance = _expected_a0_parent_event_provenance(
            lane, method, step_s,
        )
        traces.append({
            "lane_id": lane,
            "method": method,
            "step_s": step_s,
            "fresh_b3_reconstruction": True,
            "fresh_b4e_reference_propagation": True,
            "acquisition_time_s": event_provenance["acquisition_time_s"],
            "common_absolute_end_time_s": 0.08,
            "acquisition_certificate_payload": event_provenance[
                "acquisition_certificate_payload"
            ],
            "event_certificate_sha256": event_provenance[
                "event_certificate_sha256"
            ],
            "fixed_template_comparison_audit": event_provenance[
                "fixed_template_comparison_audit"
            ],
            "npz_path": npz_path.resolve().as_posix(),
            "npz_bytes": receipt["bytes"],
            "npz_sha256": receipt["sha256"],
            "numeric_payload_sha256": array_payload_sha256(parent_arrays),
        })
    parent_manifest_path = root / "evidence" / "parent_manifest.json"
    interchange = read_json(A0_PARENT_INTERCHANGE_PATH)
    atomic_write_json(parent_manifest_path, {
        "schema": "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1",
        "fresh_generation": True,
        "source_bindings": interchange["source_bindings_required"],
        "b4e_active_traces_binding": active_oracle_binding,
        "interchange_contract": {
            "path": A0_PARENT_INTERCHANGE_PATH.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "bytes": A0_PARENT_INTERCHANGE_PATH.stat().st_size,
            "sha256": sha256_file(A0_PARENT_INTERCHANGE_PATH),
        },
        "trace_count": 6,
        "traces": traces,
        "claim_boundary": interchange["claim_boundary"],
    })
    parent_sha = sha256_file(parent_manifest_path)
    trace_bindings = [
        {
            "lane_id": trace["lane_id"],
            "npz_path": trace["npz_path"],
            "npz_bytes": trace["npz_bytes"],
            "npz_sha256": trace["npz_sha256"],
            "numeric_payload_sha256": trace["numeric_payload_sha256"],
        }
        for trace in traces
    ]
    return {
        "pre_run_execution_ledger_path": ledger_path.resolve().as_posix(),
        "pre_run_execution_ledger_bytes": ledger_path.stat().st_size,
        "pre_run_execution_ledger_sha256": sha256_file(ledger_path),
        "pre_run_protected_snapshot_path": snapshot_path.resolve().as_posix(),
        "pre_run_protected_snapshot_bytes": snapshot_path.stat().st_size,
        "pre_run_protected_snapshot_sha256": sha256_file(snapshot_path),
        "a0_parent_reference_trace_manifest_path": parent_manifest_path.resolve().as_posix(),
        "a0_parent_reference_trace_manifest_bytes": parent_manifest_path.stat().st_size,
        "a0_parent_reference_trace_manifest_sha256": parent_sha,
        "a0_parent_reference_trace_bindings_sha256": canonical_sha256(trace_bindings),
        "runtime_identity_sha256": "A" * 64,
        "recursive_parent_identity_sha256": "B" * 64,
    }


def _a1_reference_metadata() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for lane in ("RK4_REFERENCE", "MIDPOINT_REFERENCE"):
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
            for duration in (0.005, 0.01, 0.02):
                token = f"{lane}__{alpha}__{duration}"
                records.append({
                    "arm": "A1",
                    "lane_id": lane,
                    "case_id": token,
                    "command_parameters": {
                        "left": {"alpha": alpha, "duration_s": duration},
                    },
                    "geometry_domain": {"passed": True},
                    "responses": {
                        "finite_removal_event": False,
                        "post_release_passed": False,
                        "selector_case_integrity_pass": True,
                        "signed_work_terminal_J": alpha * duration,
                    },
                    "event_provenance": {
                        "lane_id": lane,
                        "fresh_b3_reconstruction": True,
                        "acquisition_time_s": 0.1,
                        "removal_time_s": 0.2,
                        "acquisition_certificate_sha256": f"ACQ::{token}",
                        "clearance_certificate_sha256": f"CLR::{token}",
                    },
                })
    return records


def _set_finite(
    records: list[dict[str, Any]],
    lane: str,
    alpha: float,
    duration: float,
) -> None:
    item = next(
        row for row in records
        if row["lane_id"] == lane
        and row["command_parameters"]["left"]["alpha"] == alpha
        and row["command_parameters"]["left"]["duration_s"] == duration
    )
    item["responses"]["finite_removal_event"] = True
    item["responses"]["post_release_passed"] = True


def test_signed_preregistration_manifest_expands_all_19_records() -> None:
    verified = verify_preregistration_source_manifest(PROJECT_ROOT, PHASE_ROOT)
    assert verified["pass"] is True
    assert verified["record_count"] == len(verified["records"]) == 19
    assert all(row["pass"] is True for row in verified["records"])


def test_recursive_parent_dag_has_identical_pre_post_identity() -> None:
    bindings = read_json(CONTRACT_ROOT / "PHASE_B4G_SOURCE_BINDINGS_V1.json")
    before = verify_recursive_parents(PROJECT_ROOT, PHASE_ROOT, bindings)
    after = verify_recursive_parents(PROJECT_ROOT, PHASE_ROOT, bindings)
    assert before["pass"] is after["pass"] is True
    assert canonical_sha256(before) == canonical_sha256(after)
    assert before["direct_binding_count"] == 11


def test_local_inventory_excludes_derived_json_but_includes_source_contract_test(
    tmp_path: Path,
) -> None:
    phase = tmp_path / "phase"
    (phase / "b4g_mutation_execution").mkdir(parents=True)
    (phase / "contracts").mkdir()
    (phase / "tests").mkdir()
    (phase / "b4g_validation").mkdir()
    (phase / "evidence").mkdir()
    for generated_name in (
        ".pytest-tmp-long-tree",
        ".pytest_tmp_legacy",
        ".pytest_validation_worker",
        ".pytest_branch_case",
        ".pytest_cache",
    ):
        generated = phase / generated_name / "nested" / "deeper"
        generated.mkdir(parents=True)
        (generated / "must_not_enter_inventory.py").write_text(
            "RAISE_IF_INVENTORIED = True\n", encoding="utf-8",
        )
    (phase / "b4g_mutation_execution" / "runner.py").write_text("x=1\n", encoding="utf-8")
    (phase / "b4g_mutation_execution" / "derived.json").write_text("{}\n", encoding="utf-8")
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    (phase / "tests" / "test_runner.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (phase / "b4g_validation" / "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json").write_text(
        "{}\n", encoding="utf-8",
    )
    (phase / "b4g_validation" / "UNFROZEN_DERIVED.json").write_text("{}\n", encoding="utf-8")
    (phase / "evidence" / "derived.py").write_text("x=2\n", encoding="utf-8")
    (phase / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    inventory = local_source_inventory(tmp_path, phase)
    paths = {row["path"] for row in inventory}
    assert "phase/b4g_mutation_execution/runner.py" in paths
    assert "phase/contracts/frozen.json" in paths
    assert "phase/tests/test_runner.py" in paths
    assert "phase/b4g_validation/PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json" in paths
    assert "phase/pytest.ini" in paths
    assert "phase/b4g_validation/UNFROZEN_DERIVED.json" not in paths
    assert "phase/b4g_mutation_execution/derived.json" not in paths
    assert "phase/evidence/derived.py" not in paths
    assert not any("must_not_enter_inventory.py" in path for path in paths)


def test_forbidden_asset_walk_prunes_generated_long_trees_before_descent_but_scans_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase = tmp_path / "phase"
    phase.mkdir()
    visited: list[str] = []

    def guarded_walk(
        root: Path, *, topdown: bool, onerror: Any, followlinks: bool,
    ):
        assert topdown is True and followlinks is False and callable(onerror)
        directories = [
            ".pytest-tmp-path-that-would-exceed-windows-limits", "evidence",
        ]
        yield str(root), directories, []
        if any(name.startswith(".pytest") for name in directories):
            raise OSError("WINERROR_206_SIMULATED_UNPRUNED_DESCENT")
        visited.extend(directories)
        yield str(Path(root) / "evidence"), [], ["execution.lock"]

    monkeypatch.setattr(source_guard_module.os, "walk", guarded_walk)
    found = forbidden_local_artifacts(
        phase,
        {"forbidden_local_artifacts": ["*.urdf", "execution.lock"]},
    )
    assert visited == ["evidence"]
    assert found == ["evidence/execution.lock"]


@pytest.mark.parametrize("inventory", (True, False))
def test_source_walk_errors_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inventory: bool,
) -> None:
    phase = tmp_path / "phase"
    phase.mkdir()

    def failed_walk(
        root: Path, *, topdown: bool, onerror: Any, followlinks: bool,
    ):
        onerror(OSError("INJECTED_WALK_ACCESS_FAILURE"))
        if False:
            yield root, [], []

    monkeypatch.setattr(source_guard_module.os, "walk", failed_walk)
    with pytest.raises(SourceGuardError, match="WALK_ERROR"):
        if inventory:
            local_source_inventory(tmp_path, phase)
        else:
            forbidden_local_artifacts(
                phase, {"forbidden_local_artifacts": ["*.urdf"]},
            )


@pytest.mark.parametrize("inventory", (True, False))
def test_source_walk_rejects_business_directory_link_or_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inventory: bool,
) -> None:
    phase = tmp_path / "phase"
    phase.mkdir()

    def one_directory(
        root: Path, *, topdown: bool, onerror: Any, followlinks: bool,
    ):
        yield str(root), ["business_link"], []

    monkeypatch.setattr(source_guard_module.os, "walk", one_directory)
    monkeypatch.setattr(
        source_guard_module,
        "_is_directory_link_or_reparse",
        lambda path: Path(path).name == "business_link",
    )
    with pytest.raises(SourceGuardError, match="DIRECTORY_LINK_OR_REPARSE"):
        if inventory:
            local_source_inventory(tmp_path, phase)
        else:
            forbidden_local_artifacts(
                phase, {"forbidden_local_artifacts": ["*.urdf"]},
            )


@pytest.mark.parametrize("inventory", (True, False))
def test_source_walk_rejects_broken_file_link_or_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inventory: bool,
) -> None:
    phase = tmp_path / "phase"
    phase.mkdir()

    def one_file(
        root: Path, *, topdown: bool, onerror: Any, followlinks: bool,
    ):
        yield str(root), [], ["broken_source.py"]

    monkeypatch.setattr(source_guard_module.os, "walk", one_file)
    monkeypatch.setattr(
        source_guard_module,
        "_is_directory_link_or_reparse",
        lambda path: Path(path).name == "broken_source.py",
    )
    with pytest.raises(SourceGuardError, match="FILE_LINK_OR_REPARSE"):
        if inventory:
            local_source_inventory(tmp_path, phase)
        else:
            forbidden_local_artifacts(
                phase, {"forbidden_local_artifacts": ["*.urdf"]},
            )


def test_external_execution_freeze_expands_terminal_gate_manifest_and_sources(
    tmp_path: Path,
) -> None:
    phase = tmp_path / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    source = phase / "extra_source.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=tmp_path, phase_root=phase)
    terminal_path = tmp_path / receipt["terminal"]["path"]
    expected = receipt["terminal"]["sha256"]
    verified = verify_execution_source_freeze(
        tmp_path, phase, terminal_path, expected,
    )
    assert verified["pass"] is True
    assert verified["source_count"] == len(local_source_inventory(tmp_path, phase))
    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(SourceGuardError, match="EXECUTION_SOURCE_MANIFEST_RECORD_MISMATCH"):
        verify_execution_source_freeze(tmp_path, phase, terminal_path, expected)


def _rewrite_freeze_chain_after_manifest_change(
    project: Path, receipt: Mapping[str, Any], manifest: Mapping[str, Any],
) -> tuple[Path, str]:
    manifest_path = project / receipt["manifest"]["path"]
    gate_path = project / receipt["gate"]["path"]
    terminal_path = project / receipt["terminal"]["path"]
    manifest_payload = dict(manifest)
    source_count = len(manifest_payload["sources"])
    inventory_sha256 = canonical_sha256(manifest_payload["sources"])
    manifest_payload["source_count"] = source_count
    manifest_payload["source_inventory_sha256"] = inventory_sha256
    atomic_write_json(manifest_path, manifest_payload)
    gate = read_json(gate_path)
    gate["execution_source_manifest"].update({
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    })
    gate["source_count"] = source_count
    gate["source_inventory_sha256"] = inventory_sha256
    atomic_write_json(gate_path, gate)
    terminal = read_json(terminal_path)
    terminal["records"][0].update({
        "bytes": gate_path.stat().st_size,
        "sha256": sha256_file(gate_path),
    })
    terminal["source_count"] = source_count
    terminal["source_inventory_sha256"] = inventory_sha256
    atomic_write_json(terminal_path, terminal)
    return terminal_path, sha256_file(terminal_path)


def test_execution_source_freezer_is_deterministic_acyclic_and_self_verified(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    first = freeze_execution_sources(project_root=project, phase_root=phase)
    first_records = {
        name: (first[name]["bytes"], first[name]["sha256"])
        for name in ("manifest", "gate", "terminal")
    }
    second = freeze_execution_sources(project_root=project, phase_root=phase)
    assert first_records == {
        name: (second[name]["bytes"], second[name]["sha256"])
        for name in ("manifest", "gate", "terminal")
    }
    assert second["verification"]["pass"] is True
    manifest = read_json(project / second["manifest"]["path"])
    assert manifest["self_excluded"] is True
    published_names = {
        Path(second[name]["path"]).name for name in ("manifest", "gate", "terminal")
    }
    assert published_names.isdisjoint(
        {Path(row["path"]).name for row in manifest["sources"]}
    )


def test_execution_source_freezer_custom_root_is_owned_and_zero_credit(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts/frozen.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        ExecutionSourceFreezeError, match="OUTPUT_ROOT_TOO_BROAD",
    ):
        freeze_execution_sources(
            project_root=project, phase_root=phase, output_root=project.parent,
        )
    unmarked = tmp_path / "existing_unmarked_freeze"
    unmarked.mkdir()
    sentinel = unmarked / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    with pytest.raises(
        ExecutionSourceFreezeError, match="NONEMPTY_ROOT_REQUIRES_MARKER",
    ):
        freeze_execution_sources(
            project_root=project, phase_root=phase, output_root=unmarked,
        )
    assert sentinel.is_file()
    assert not (unmarked / FREEZE_OUTPUT_ROOT_MARKER).exists()

    diagnostic_root = tmp_path / "diagnostic_freeze"
    receipt = freeze_execution_sources(
        project_root=project, phase_root=phase, output_root=diagnostic_root,
    )
    assert receipt["diagnostic_only"] is True
    assert receipt["formal_publication_credit"] is False
    assert receipt["verification"]["formal_execution_source_freeze_eligible"] is False
    terminal = read_json(Path(receipt["terminal"]["path"]))
    assert terminal["diagnostic_only"] is True
    assert terminal["formal_publication_credit"] is False
    assert terminal["schema"].startswith("SIM13_V4B4G_DIAGNOSTIC_")


def test_execution_source_freezer_rejects_phase_overlap_and_reparse_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts/frozen.json").write_text("{}\n", encoding="utf-8")
    inside_phase = phase / "contracts/diagnostic_freeze"
    with pytest.raises(
        ExecutionSourceFreezeError,
        match="CUSTOM_OUTPUT_OVERLAPS_PHASE_ROOT",
    ):
        freeze_execution_sources(
            project_root=project,
            phase_root=phase,
            output_root=inside_phase,
        )
    assert not inside_phase.exists()

    custom = tmp_path / "diagnostic_freeze"
    receipt = freeze_execution_sources(
        project_root=project, phase_root=phase, output_root=custom,
    )
    marker = custom / FREEZE_OUTPUT_ROOT_MARKER
    original = freeze_source_module._is_publication_link_or_reparse
    monkeypatch.setattr(
        freeze_source_module,
        "_is_publication_link_or_reparse",
        lambda path: True if Path(path) == marker else original(path),
    )
    with pytest.raises(
        ExecutionSourceFreezeError,
        match="OUTPUT_MARKER_NOT_PLAIN_FILE",
    ):
        freeze_execution_sources(
            project_root=project, phase_root=phase, output_root=custom,
        )
    assert marker.is_file()
    assert receipt["formal_publication_credit"] is False


@pytest.mark.parametrize("linked_parent", ["evidence", "results"])
def test_execution_source_freezer_rejects_linked_publication_parent_before_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    linked_parent: str,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts/frozen.json").write_text("{}\n", encoding="utf-8")
    parent = phase / linked_parent
    parent.mkdir()
    stale_name = (
        "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1.json"
        if linked_parent == "evidence"
        else "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_"
        "SELF_EXCLUDED_MANIFEST_V1.json"
    )
    sentinel = parent / stale_name
    sentinel.write_text("sentinel-preserve\n", encoding="utf-8")
    original = freeze_source_module._is_publication_link_or_reparse
    monkeypatch.setattr(
        freeze_source_module,
        "_is_publication_link_or_reparse",
        lambda path: True if Path(path) == parent else original(path),
    )
    with pytest.raises(
        ExecutionSourceFreezeError,
        match="PUBLICATION_PARENT_LINK_REPARSE_OR_NONDIR",
    ):
        freeze_execution_sources(project_root=project, phase_root=phase)
    assert sentinel.read_text(encoding="utf-8") == "sentinel-preserve\n"


def test_fixed_execution_source_freeze_rejects_link_or_reparse_chain_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts/frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    terminal = project / receipt["terminal"]["path"]
    original = source_guard_module._is_directory_link_or_reparse
    monkeypatch.setattr(
        source_guard_module,
        "_is_directory_link_or_reparse",
        lambda path: True if Path(path) == terminal else original(path),
    )
    with pytest.raises(SourceGuardError, match="NOT_PLAIN_REGULAR_FILE"):
        verify_execution_source_freeze(
            project, phase, terminal, receipt["terminal"]["sha256"],
        )
    monkeypatch.setattr(orchestrator_module, "PROJECT_ROOT", project)
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", phase)
    with pytest.raises(B4GExecutionError, match="NOT_PLAIN_REGULAR_FILE"):
        _require_formal_execution_source_freeze_paths(phase, terminal)


@pytest.mark.parametrize(
    ("layer", "error"),
    (
        ("terminal", "EXECUTION_SOURCE_FREEZE_TERMINAL_SCHEMA_OR_FIELDS"),
        ("gate", "EXECUTION_SOURCE_FREEZE_GATE_SCHEMA_OR_FIELDS"),
        ("manifest", "EXECUTION_SOURCE_MANIFEST_SCHEMA_OR_FIELDS"),
    ),
)
def test_execution_source_freeze_rejects_extra_fields_at_every_chain_layer(
    tmp_path: Path, layer: str, error: str,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    gate_path = project / receipt["gate"]["path"]
    terminal_path = project / receipt["terminal"]["path"]

    if layer == "manifest":
        payload = read_json(manifest_path)
        payload["unexpected"] = True
        atomic_write_json(manifest_path, payload)
        gate = read_json(gate_path)
        gate["execution_source_manifest"].update({
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        })
        atomic_write_json(gate_path, gate)
    elif layer == "gate":
        gate = read_json(gate_path)
        gate["unexpected"] = True
        atomic_write_json(gate_path, gate)
    else:
        terminal = read_json(terminal_path)
        terminal["unexpected"] = True
        atomic_write_json(terminal_path, terminal)

    if layer != "terminal":
        terminal = read_json(terminal_path)
        terminal["records"][0].update({
            "bytes": gate_path.stat().st_size,
            "sha256": sha256_file(gate_path),
        })
        atomic_write_json(terminal_path, terminal)
    with pytest.raises(SourceGuardError, match=error):
        verify_execution_source_freeze(
            project, phase, terminal_path, sha256_file(terminal_path),
        )


def test_execution_source_freeze_rejects_reordered_inventory_and_cross_layer_sha(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    manifest = read_json(manifest_path)
    manifest["sources"] = list(reversed(manifest["sources"]))
    terminal_path, terminal_sha = _rewrite_freeze_chain_after_manifest_change(
        project, receipt, manifest,
    )
    with pytest.raises(
        SourceGuardError,
        match="EXECUTION_SOURCE_MANIFEST_NOT_EXACT_CURRENT_ALLOWLIST_INVENTORY",
    ):
        verify_execution_source_freeze(project, phase, terminal_path, terminal_sha)

    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    gate_path = project / receipt["gate"]["path"]
    terminal_path = project / receipt["terminal"]["path"]
    manifest = read_json(manifest_path)
    manifest["source_inventory_sha256"] = "0" * 64
    atomic_write_json(manifest_path, manifest)
    gate = read_json(gate_path)
    gate["execution_source_manifest"].update({
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    })
    gate["source_inventory_sha256"] = "0" * 64
    atomic_write_json(gate_path, gate)
    terminal = read_json(terminal_path)
    terminal["records"][0].update({
        "bytes": gate_path.stat().st_size,
        "sha256": sha256_file(gate_path),
    })
    terminal["source_inventory_sha256"] = "0" * 64
    atomic_write_json(terminal_path, terminal)
    with pytest.raises(
        SourceGuardError,
        match="EXECUTION_SOURCE_FREEZE_COUNT_OR_INVENTORY_SHA256_INCONSISTENT",
    ):
        verify_execution_source_freeze(
            project, phase, terminal_path, sha256_file(terminal_path),
        )


def test_execution_source_freeze_rejects_consistent_but_wrong_claim_boundary(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    gate_path = project / receipt["gate"]["path"]
    terminal_path = project / receipt["terminal"]["path"]
    wrong = "MUTATED_BUT_CROSS_LAYER_EQUAL"
    manifest = read_json(manifest_path)
    manifest["claim_boundary"] = wrong
    atomic_write_json(manifest_path, manifest)
    gate = read_json(gate_path)
    gate["claim_boundary"] = wrong
    gate["execution_source_manifest"].update({
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    })
    atomic_write_json(gate_path, gate)
    terminal = read_json(terminal_path)
    terminal["claim_boundary"] = wrong
    terminal["records"][0].update({
        "bytes": gate_path.stat().st_size,
        "sha256": sha256_file(gate_path),
    })
    atomic_write_json(terminal_path, terminal)
    with pytest.raises(
        SourceGuardError, match="EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY_MISMATCH",
    ):
        verify_execution_source_freeze(
            project, phase, terminal_path, sha256_file(terminal_path),
        )


def test_execution_source_freeze_rejects_manifest_self_reference(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    manifest = read_json(manifest_path)
    manifest["sources"].append({
        "id": "malicious_self_reference",
        "role": "B4G_FROZEN_CONTRACT_SOURCE_TEST_OR_WORKFLOW",
        "path": receipt["manifest"]["path"],
        "bytes": 0,
        "sha256": "0" * 64,
    })
    manifest["source_count"] = len(manifest["sources"])
    terminal_path, terminal_sha = _rewrite_freeze_chain_after_manifest_change(
        project, receipt, manifest,
    )
    with pytest.raises(
        SourceGuardError,
        match="EXECUTION_SOURCE_MANIFEST_DUPLICATE_OR_SELF_REFERENCE",
    ):
        verify_execution_source_freeze(
            project, phase, terminal_path, terminal_sha,
        )


def test_execution_source_freeze_rejects_missing_allowlisted_source(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    manifest_path = project / receipt["manifest"]["path"]
    manifest = read_json(manifest_path)
    manifest["sources"] = manifest["sources"][:-1]
    manifest["source_count"] = len(manifest["sources"])
    terminal_path, terminal_sha = _rewrite_freeze_chain_after_manifest_change(
        project, receipt, manifest,
    )
    with pytest.raises(
        SourceGuardError,
        match="EXECUTION_SOURCE_MANIFEST_NOT_EXACT_CURRENT_ALLOWLIST_INVENTORY",
    ):
        verify_execution_source_freeze(
            project, phase, terminal_path, terminal_sha,
        )


def test_execution_source_freeze_requires_complete_formal_workflow_before_write(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    (phase / "independent_audit_phase_b4g.py").unlink()
    with pytest.raises(
        ExecutionSourceFreezeError,
        match="EXECUTION_SOURCE_FREEZE_REQUIRED_FORMAL_ENTRYPOINT_MISSING",
    ):
        freeze_execution_sources(project_root=project, phase_root=phase)
    assert not (phase / "evidence" / "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1.json").exists()
    assert not (phase / "results" / "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1.json").exists()
    assert not (
        phase / "results"
        / "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
    ).exists()


def test_execution_source_freeze_injected_midchain_failure_removes_old_and_partial_chain(
    tmp_path: Path,
) -> None:
    project = tmp_path
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    _write_required_formal_entrypoints(phase)
    (phase / "contracts" / "frozen.json").write_text("{}\n", encoding="utf-8")
    receipt = freeze_execution_sources(project_root=project, phase_root=phase)
    published = [project / receipt[name]["path"] for name in (
        "manifest", "gate", "terminal",
    )]
    assert all(path.is_file() for path in published)
    calls = 0

    def failing_writer(path: Path, payload: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("INJECTED_AFTER_MANIFEST")
        atomic_write_json(path, payload)

    with pytest.raises(KeyboardInterrupt, match="INJECTED_AFTER_MANIFEST"):
        freeze_execution_sources(
            project_root=project,
            phase_root=phase,
            write_json_fn=failing_writer,
        )
    assert calls == 2
    assert all(not path.exists() for path in published)


def _passing_validator_report() -> dict[str, Any]:
    return {
        "schema": "SIM13_V4B4G_READ_ONLY_VALIDATION_REPORT_V1",
        "mode": "full",
        "status": "PASS",
        "passed": True,
        "final": False,
        "audited": False,
        "validator_pass_claimed": False,
        "campaign_or_scientific_credit": False,
        "check_count": 1,
        "failure_count": 0,
        "failures": [],
        "observations": {},
        "writes_performed": False,
        "solver_runner_mutation_modules_imported": False,
    }


def test_preaudit_publisher_orders_post_before_full_validator_and_cleans_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "publication"
    root.mkdir()
    monkeypatch.setattr("publish_phase_b4g_preaudit.PHASE_ROOT", root)
    for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")
    diagnostic = root / "results" / "KEEP_CAMPAIGN_DIAGNOSTIC.json"
    diagnostic.write_text("{}\n", encoding="utf-8")
    order: list[str] = []

    def reverify(**_: Any) -> dict[str, Any]:
        order.append("REVERIFY")
        assert all(
            not (root / relative).exists()
            for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS
        )
        return {"post_run_snapshot": {"schema": "TEST_POST", "pass": True}}

    def validator(*, mode: str) -> dict[str, Any]:
        order.append("FULL_VALIDATOR")
        assert mode == "full"
        assert (root / "evidence/SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json").is_file()
        failed = _passing_validator_report()
        failed.update({
            "status": "DIAGNOSTIC_FAIL_CLOSED", "passed": False,
            "failure_count": 1, "failures": [{"code": "TEST", "detail": None}],
        })
        return failed

    with pytest.raises(
        B4GPreauditPublicationError, match="FULL_VALIDATION_NOT_EXACT_PASS",
    ):
        publish_preaudit(
            execution_source_freeze_terminal=tmp_path / "freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
            output_root=root,
            reverify_fn=reverify,
            validator_fn=validator,
            record_builder_fn=lambda **_: [{
                "path": "test/dependency.json",
                "role": "TEST_DEPENDENCY",
                "bytes": 1,
                "sha256": "A" * 64,
            }],
        )
    assert order == ["REVERIFY", "FULL_VALIDATOR"]
    assert all(
        not (root / relative).exists()
        for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS
    )
    assert diagnostic.is_file()


def test_preaudit_public_entry_rejects_custom_root_before_cleanup(
    tmp_path: Path,
) -> None:
    custom = tmp_path / "custom_publication"
    stale_paths = []
    for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS:
        path = custom / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")
        stale_paths.append(path)
    with pytest.raises(
        B4GPreauditPublicationError,
        match="FORMAL_PREAUDIT_PUBLISHER_REQUIRES_PHASE_ROOT",
    ):
        publish_preaudit(
            execution_source_freeze_terminal=tmp_path / "freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
            output_root=custom,
            reverify_fn=lambda **_: {},
            validator_fn=lambda **_: _passing_validator_report(),
        )
    assert all(path.read_text(encoding="utf-8") == "stale\n" for path in stale_paths)


def test_preaudit_cleanup_is_consumer_first_and_best_effort_after_midpoint_failure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cleanup"
    for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")
    attempted: list[str] = []
    failed_relative = _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS[3]

    def injected_unlink(path: Path) -> None:
        attempted.append(path.relative_to(root).as_posix())
        if path == root / failed_relative:
            raise PermissionError("INJECTED_MIDPOINT_UNLINK_FAILURE")
        path.unlink()

    with pytest.raises(
        B4GPreauditPublicationError,
        match="PREAUDIT_STALE_FINAL_CLEANUP_INCOMPLETE",
    ):
        _cleanup_stale_audit_and_final_outputs(root, unlink_fn=injected_unlink)
    assert attempted == [
        relative.as_posix()
        for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS
    ]
    assert not (root / _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS[0]).exists()
    assert not (root / _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS[1]).exists()
    assert (root / failed_relative).is_file()
    assert all(
        not (root / relative).exists()
        for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS[4:]
    )


def test_preaudit_detects_validator_time_dependency_mutation_and_cleans_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "phase"
    root.mkdir()
    monkeypatch.setattr("publish_phase_b4g_preaudit.PHASE_ROOT", root)
    dependency = root / "results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    atomic_write_json(dependency, {"schema": "TEST_DEPENDENCY", "value": 1})

    def reverify(**_: Any) -> dict[str, Any]:
        return {
            "post_run_snapshot": {"schema": "TEST_POST", "pass": True},
            "dependency_sha256": sha256_file(dependency),
        }

    def records(**kwargs: Any) -> list[dict[str, Any]]:
        rows = [{
            "path": dependency.relative_to(root).as_posix(),
            "role": "TEST_DEPENDENCY",
            "bytes": dependency.stat().st_size,
            "sha256": sha256_file(dependency),
        }]
        validation_path = kwargs.get("validation_path")
        if validation_path is not None:
            rows.append({
                "path": Path(validation_path).relative_to(root).as_posix(),
                "role": "EXECUTION_VALIDATION_FULL",
                "bytes": Path(validation_path).stat().st_size,
                "sha256": sha256_file(Path(validation_path)),
            })
        return sorted(rows, key=lambda row: row["path"])

    def mutate_after_validation(*, mode: str) -> dict[str, Any]:
        assert mode == "full"
        atomic_write_json(dependency, {"schema": "TEST_DEPENDENCY", "value": 2})
        return _passing_validator_report()

    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_VALIDATOR_AUTHORITATIVE_EVIDENCE_IDENTITY_DRIFT",
    ):
        publish_preaudit(
            execution_source_freeze_terminal=tmp_path / "freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
            output_root=root,
            reverify_fn=reverify,
            validator_fn=mutate_after_validation,
            record_builder_fn=records,
        )
    assert all(
        not (root / relative).exists()
        for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS
    )
    assert read_json(dependency)["value"] == 2


def test_preaudit_rejects_negative_control_coexisting_with_incomplete_or_active_campaign_receipt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "phase"
    negative = (
        root / "b4g_mutation_execution"
        / "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json"
    )
    incomplete = (
        root / "b4g_mutation_execution"
        / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    )
    atomic_write_json(negative, {"schema": "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1"})
    atomic_write_json(incomplete, {"schema": "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1"})
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_MUTATION_INCOMPLETE_MARKER_PRESENT",
    ):
        _require_no_active_attempt_markers(root)
    incomplete.unlink()
    invalidation = root / "results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    atomic_write_json(invalidation, {
        "schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1", "active": True,
    })
    with pytest.raises(
        B4GPreauditPublicationError, match="POST_RUN_ACTIVE_CAMPAIGN_RECEIPT",
    ):
        _require_no_active_attempt_markers(root)
    invalidation_payload = read_json(invalidation)
    invalidation_payload["active"] = False
    atomic_write_json(invalidation, invalidation_payload)
    _require_no_active_attempt_markers(root)


def test_preaudit_marker_lexists_rejects_directories_malformed_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "phase"
    incomplete = (
        root / "b4g_mutation_execution"
        / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    )
    incomplete.mkdir(parents=True)
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_MUTATION_INCOMPLETE_MARKER_PRESENT",
    ):
        _require_no_active_attempt_markers(root)
    incomplete.rmdir()

    receipt = root / "results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    receipt.mkdir(parents=True)
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_CAMPAIGN_RECEIPT_NOT_PLAIN_FILE",
    ):
        _require_no_active_attempt_markers(root)
    receipt.rmdir()
    receipt.write_text("{malformed", encoding="utf-8")
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_CAMPAIGN_RECEIPT_INVALID",
    ):
        _require_no_active_attempt_markers(root)
    receipt.unlink()

    link_target = tmp_path / "outside_receipt.json"
    atomic_write_json(link_target, {
        "schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1", "active": False,
    })
    try:
        receipt.symlink_to(link_target)
    except OSError as error:
        original_lexists = __import__("os").path.lexists
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            "publish_phase_b4g_preaudit.os.path.lexists",
            lambda path: True if Path(path) == receipt else original_lexists(path),
        )
        monkeypatch.setattr(
            Path, "is_symlink",
            lambda path: True if path == receipt else original_is_symlink(path),
        )
        with pytest.raises(
            B4GPreauditPublicationError,
            match="POST_RUN_CAMPAIGN_RECEIPT_NOT_PLAIN_FILE",
        ):
            _require_no_active_attempt_markers(root)
        return
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_CAMPAIGN_RECEIPT_NOT_PLAIN_FILE",
    ):
        _require_no_active_attempt_markers(root)
    receipt.unlink()
    receipt.symlink_to(tmp_path / "missing_broken_target.json")
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_CAMPAIGN_RECEIPT_NOT_PLAIN_FILE",
    ):
        _require_no_active_attempt_markers(root)
    receipt.unlink()


def test_full_validation_report_accepts_only_exact_read_only_pass_shape() -> None:
    payload = _passing_validator_report()
    assert _validated_report_payload(payload) == payload
    for key, value in (
        ("writes_performed", True),
        ("final", True),
        ("audited", True),
        ("solver_runner_mutation_modules_imported", True),
    ):
        mutant = dict(payload)
        mutant[key] = value
        with pytest.raises(
            B4GPreauditPublicationError, match="FULL_VALIDATION_NOT_EXACT_PASS",
        ):
            _validated_report_payload(mutant)


def test_full_validator_runs_in_isolated_subprocess_and_requires_one_canonical_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _passing_validator_report()
    observed: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        observed.update({"command": command, **kwargs})
        return SimpleNamespace(
            returncode=0,
            stdout=canonical_bytes(payload) + b"\n",
            stderr=b"",
        )

    monkeypatch.setattr("publish_phase_b4g_preaudit.subprocess.run", run)
    assert _run_full_validator_subprocess(mode="full") == payload
    assert observed["command"][-2:] == ["--mode", "full"]
    assert Path(observed["cwd"]) == PHASE_ROOT
    assert observed["check"] is False

    def noisy_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=canonical_bytes(payload) + b"\n{}\n",
            stderr=b"",
        )

    monkeypatch.setattr("publish_phase_b4g_preaudit.subprocess.run", noisy_run)
    with pytest.raises(
        B4GPreauditPublicationError,
        match="FULL_VALIDATOR_STDOUT_STRICT_JSON_PARSE_FAILED",
    ):
        _run_full_validator_subprocess(mode="full")


def test_evidence_manifest_exact_roles_self_exclusion_and_hash() -> None:
    records: list[dict[str, Any]] = []
    ordinal = 0

    def append(role: str) -> None:
        nonlocal ordinal
        records.append({
            "path": f"phase/evidence/dependency_{ordinal:04d}.bin",
            "role": role,
            "bytes": ordinal + 1,
            "sha256": f"{ordinal + 1:064X}",
        })
        ordinal += 1

    for role, count in _FIXED_ROLE_COUNTS.items():
        for _ in range(count):
            append(role)
    for _ in range(120):
        append("EXECUTED_CASE_NPZ")
    append("MUTATION_ARTIFACT_DEPENDENCY")
    records.sort(key=lambda row: (row["path"].casefold(), row["path"]))
    manifest = _evidence_manifest_payload(records)
    assert set(manifest) == {
        "schema", "scope", "self_excluded", "acyclic",
        "source_freeze_terminal", "execution_validation", "records",
        "record_count", "records_canonical_sha256",
        "excluded_future_outputs", "claim_boundary",
    }
    assert manifest["record_count"] == len(records)
    assert manifest["records_canonical_sha256"] == canonical_sha256(records)
    assert manifest["excluded_future_outputs"] == _EXCLUDED_FUTURE_OUTPUTS
    assert len(_EXCLUDED_FUTURE_OUTPUTS) == 5
    assert any("PREAUDIT_GATE" in value for value in _EXCLUDED_FUTURE_OUTPUTS)
    assert all(
        Path(value).name not in {Path(row["path"]).name for row in records}
        for value in _EXCLUDED_FUTURE_OUTPUTS
    )


def test_evidence_manifest_rejects_casefold_alias() -> None:
    records: list[dict[str, Any]] = []
    ordinal = 0
    for role, count in _FIXED_ROLE_COUNTS.items():
        for _ in range(count):
            records.append({
                "path": f"phase/evidence/item_{ordinal:04d}.bin",
                "role": role, "bytes": 1, "sha256": "A" * 64,
            })
            ordinal += 1
    for _ in range(120):
        records.append({
            "path": f"phase/evidence/item_{ordinal:04d}.bin",
            "role": "EXECUTED_CASE_NPZ", "bytes": 1, "sha256": "A" * 64,
        })
        ordinal += 1
    records.append({
        "path": f"phase/evidence/item_{ordinal:04d}.bin",
        "role": "MUTATION_ARTIFACT_DEPENDENCY",
        "bytes": 1,
        "sha256": "A" * 64,
    })
    records[-2]["path"] = records[-3]["path"].upper()
    with pytest.raises(
        B4GPreauditPublicationError, match="EVIDENCE_MANIFEST_PATH_SET_INVALID",
    ):
        _evidence_manifest_payload(records)


def test_preaudit_gate_is_nonfinal_governance_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    contracts = {
        "governance": {
            "required_false": {"production_ready": False},
            "required_null_physical_inputs": ["physical_motor_current_A"],
            "formal_sim13_v2_state_unchanged": {
                "passed": 15, "declared": 20,
                "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
            },
        },
        "run_spec": {
            "memory": {
                "memory_gate_applicable": False,
                "memory_gate_passed": False,
                "owner_override_used": False,
                "classification": "DIAGNOSTIC_ONLY",
            },
        },
        "schema": {"claim_boundary": orchestrator_module.CLAIM_BOUNDARY},
    }
    monkeypatch.setattr(
        "publish_phase_b4g_preaudit._record",
        lambda path, role, project_root: {
            "path": Path(path).name, "role": role,
            "bytes": 1, "sha256": "A" * 64,
        },
    )
    payload = _preaudit_payload(
        output_root=tmp_path,
        project_root=tmp_path,
        reverified={
            "contracts": contracts,
            "source_freeze_terminal": tmp_path / "freeze.json",
        },
        validation_path=tmp_path / "validation.json",
        manifest_path=tmp_path / "manifest.json",
        post_path=tmp_path / "post.json",
    )
    assert set(payload) == {
        "schema", "scope", "status", "ready_for_independent_audit",
        "final", "audited", "inputs", "checks", "governance",
        "claim_boundary",
    }
    assert payload["status"] == "PASS_READY_FOR_INDEPENDENT_AUDIT"
    assert payload["ready_for_independent_audit"] is True
    assert payload["final"] is payload["audited"] is False
    assert all(payload["checks"].values())
    assert payload["governance"][
        "physical_current_formal_owner_production_release_next_stage_hold"
    ] is True


def test_stale_final_cleanup_is_exact_scoped_and_handles_keyboard_interrupt(
    tmp_path: Path,
) -> None:
    root = _prepare_output_root(tmp_path / "output")
    for relative in _STALE_FINAL_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")
    raw = root / "evidence" / "raw_cases" / "keep.npz"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"diagnostic")
    unrelated = root / "results" / "KEEP_DIAGNOSTIC.json"
    unrelated.write_text("{}\n", encoding="utf-8")
    receipt = invalidate_output_root(root, KeyboardInterrupt("operator stop"))
    assert receipt["active"] is True
    assert receipt["failure_type"] == "KeyboardInterrupt"
    assert len(receipt["stale_final_artifacts_removed"]) == len(_STALE_FINAL_RELATIVE_PATHS)
    assert all(not (root / relative).exists() for relative in _STALE_FINAL_RELATIVE_PATHS)
    assert raw.read_bytes() == b"diagnostic"
    assert unrelated.is_file()


def test_custom_smoke_output_requires_narrow_owned_root_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(B4GExecutionError, match="UNSAFE_B4G_OUTPUT_ROOT"):
        _prepare_output_root(Path(tmp_path.anchor))
    with pytest.raises(B4GExecutionError, match="UNSAFE_B4G_OUTPUT_ROOT"):
        _prepare_output_root(PROJECT_ROOT.parent)

    unmarked = tmp_path / "existing_unmarked"
    unmarked.mkdir()
    sentinel = unmarked / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    with pytest.raises(
        B4GExecutionError,
        match="CUSTOM_OUTPUT_ROOT_EXISTING_NONEMPTY_REQUIRES_MARKER",
    ):
        _prepare_output_root(unmarked)
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not (unmarked / ".sim13_v4b4g_execution_output_root.json").exists()

    empty = tmp_path / "existing_empty"
    empty.mkdir()
    owned = _prepare_output_root(empty)
    assert owned == empty.resolve()
    assert (owned / ".sim13_v4b4g_execution_output_root.json").is_file()

    phase = tmp_path / "phase"
    inside_phase = phase / "contracts/diagnostic"
    phase.mkdir()
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", phase)
    with pytest.raises(B4GExecutionError, match="OVERLAPS_PHASE_ROOT"):
        _prepare_output_root(inside_phase)
    assert not inside_phase.exists()

    marker = owned / ".sim13_v4b4g_execution_output_root.json"
    original = orchestrator_module._is_managed_link_or_reparse
    monkeypatch.setattr(
        orchestrator_module,
        "_is_managed_link_or_reparse",
        lambda path: True if Path(path) == marker else original(path),
    )
    with pytest.raises(B4GExecutionError, match="MARKER_NOT_PLAIN_FILE"):
        _prepare_output_root(owned)
    with pytest.raises(B4GExecutionError, match="MARKER_MISSING"):
        orchestrator_module._validated_output_root(owned)


@pytest.mark.parametrize("operation", ("supersede", "invalidate"))
def test_campaign_cleanup_is_consumer_first_and_best_effort_on_midpoint_failure(
    tmp_path: Path, operation: str,
) -> None:
    root = _prepare_output_root(tmp_path / operation)
    for relative in _STALE_FINAL_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")
    attempted: list[str] = []
    failed_relative = _STALE_FINAL_RELATIVE_PATHS[3]

    def injected_unlink(path: Path) -> None:
        attempted.append(path.relative_to(root).as_posix())
        if path == root / failed_relative:
            raise PermissionError("INJECTED_CAMPAIGN_MIDPOINT_FAILURE")
        path.unlink()

    with pytest.raises(B4GExecutionError, match="CLEANUP_INCOMPLETE"):
        if operation == "supersede":
            _supersede_prior_final_credit(root, _unlink_fn=injected_unlink)
        else:
            invalidate_output_root(
                root, RuntimeError("test failure"), _unlink_fn=injected_unlink,
            )
    assert attempted == list(_STALE_FINAL_RELATIVE_PATHS)
    assert not (root / _STALE_FINAL_RELATIVE_PATHS[0]).exists()
    assert not (root / _STALE_FINAL_RELATIVE_PATHS[1]).exists()
    assert (root / failed_relative).is_file()
    assert all(
        not (root / relative).exists()
        for relative in _STALE_FINAL_RELATIVE_PATHS[4:]
    )


@pytest.mark.parametrize("operation", ("supersede", "invalidate"))
def test_campaign_cleanup_unlinks_terminal_symlink_without_touching_target(
    tmp_path: Path, operation: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _prepare_output_root(tmp_path / operation)
    external = tmp_path / f"{operation}_external_terminal.json"
    external.write_text("external\n", encoding="utf-8")
    terminal_link = root / _STALE_FINAL_RELATIVE_PATHS[0]
    terminal_link.parent.mkdir(parents=True, exist_ok=True)
    terminal_link.write_text("SIMULATED_LINK_OBJECT\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink",
        lambda path: True if path == terminal_link else original_is_symlink(path),
    )
    if operation == "supersede":
        receipt = _supersede_prior_final_credit(root)
        removed = receipt["prior_final_artifacts_removed"]
    else:
        receipt = invalidate_output_root(root, RuntimeError("test failure"))
        removed = receipt["stale_final_artifacts_removed"]
    assert not terminal_link.exists()
    assert external.read_text(encoding="utf-8") == "external\n"
    assert removed[0]["path"] == _STALE_FINAL_RELATIVE_PATHS[0]
    assert removed[0]["object_type"] == "SYMLINK"


def test_campaign_cleanup_unlinks_non_symlink_reparse_without_reading_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _prepare_output_root(tmp_path / "reparse_cleanup")
    terminal = root / _STALE_FINAL_RELATIVE_PATHS[0]
    terminal.parent.mkdir(parents=True, exist_ok=True)
    terminal.write_text("SIMULATED_REPARSE\n", encoding="utf-8")
    lexical_object_bytes = terminal.lstat().st_size
    original = orchestrator_module._is_managed_link_or_reparse
    monkeypatch.setattr(
        orchestrator_module,
        "_is_managed_link_or_reparse",
        lambda path: True if Path(path) == terminal else original(path),
    )
    receipt = _supersede_prior_final_credit(root)
    removed = receipt["prior_final_artifacts_removed"]
    assert removed[0] == {
        "path": _STALE_FINAL_RELATIVE_PATHS[0],
        "bytes": lexical_object_bytes,
        "sha256": None,
        "object_type": "REPARSE_POINT",
    }
    assert not terminal.exists()


def test_formal_campaign_rejects_external_source_freeze_before_supersession_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal_root = tmp_path / "formal_phase"
    external_terminal = tmp_path / "external" / "terminal.json"
    atomic_write_json(external_terminal, {"schema": "EXTERNAL_TEST_FREEZE"})
    supersession_called = False

    def supersede(_root: Path) -> dict[str, Any]:
        nonlocal supersession_called
        supersession_called = True
        return {}

    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", formal_root)
    monkeypatch.setattr(orchestrator_module, "_supersede_prior_final_credit", supersede)
    with pytest.raises(
        B4GExecutionError,
        match="FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_PATH_NOT_FIXED",
    ):
        orchestrator_module._execute_campaign_impl(
            target_root=formal_root,
            execution_source_freeze_terminal=external_terminal,
            expected_execution_source_freeze_terminal_sha256="A" * 64,
        )
    assert supersession_called is False
    assert not formal_root.exists()


def test_preaudit_rejects_in_project_freeze_copy_before_contract_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    phase = project / "phase_b4g"
    phase.mkdir(parents=True)
    copied_terminal = project / "copied_freeze" / "terminal.json"
    atomic_write_json(copied_terminal, {"schema": "BYTE_IDENTICAL_COPY_TEST"})

    monkeypatch.setattr(orchestrator_module, "PROJECT_ROOT", project)
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", phase)
    monkeypatch.setattr("publish_phase_b4g_preaudit.PROJECT_ROOT", project)
    monkeypatch.setattr("publish_phase_b4g_preaudit.PHASE_ROOT", phase)

    def unexpected_contract_load() -> dict[str, Any]:
        raise AssertionError("fixed source-freeze path check must run first")

    monkeypatch.setattr(
        "publish_phase_b4g_preaudit._load_contracts", unexpected_contract_load,
    )
    with pytest.raises(
        B4GPreauditPublicationError,
        match="POST_RUN_EXECUTION_SOURCE_FREEZE_FIXED_PATH_FAILED:.*PATH_NOT_FIXED",
    ):
        _formal_reverification(
            output_root=phase,
            execution_source_freeze_terminal=copied_terminal,
            expected_execution_source_freeze_terminal_sha256="A" * 64,
        )


def test_campaign_attempt_marker_precedes_contract_load_and_any_a0_or_prerun_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _prepare_output_root(tmp_path / "campaign_attempt")

    def fail_contract_load() -> dict[str, Any]:
        receipt_path = root / _SUPERSESSION_RECEIPT_RELATIVE_PATH
        assert receipt_path.is_file()
        assert read_json(receipt_path)["active"] is True
        a0_root = root / "evidence/a0_parent_reference_traces"
        assert not a0_root.exists() or not any(a0_root.iterdir())
        assert not (
            root / "evidence/SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1.json"
        ).exists()
        assert not (
            root / "evidence/SIM13_V4B4G_PRE_RUN_EXECUTION_LEDGER_V1.json"
        ).exists()
        raise B4GExecutionError("TEST_STOP_AFTER_ATTEMPT_MARKER")

    monkeypatch.setattr(orchestrator_module, "_load_contracts", fail_contract_load)
    with pytest.raises(B4GExecutionError, match="TEST_STOP_AFTER_ATTEMPT_MARKER"):
        orchestrator_module._execute_campaign_impl(
            target_root=root,
            execution_source_freeze_terminal=tmp_path / "diagnostic_freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
        )
    receipt = read_json(root / _SUPERSESSION_RECEIPT_RELATIVE_PATH)
    assert receipt["active"] is True


def test_missing_formal_execution_freeze_invalidates_existing_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _prepare_output_root(tmp_path / "formal")
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", root)
    stale = root / "results" / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}\n", encoding="utf-8")
    with pytest.raises(B4GExecutionError, match="EXTERNAL_EXECUTION_SOURCE_FREEZE"):
        execute_campaign(output_root=root)
    assert not stale.exists()
    invalidation = read_json(root / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json")
    assert invalidation["active"] is True


def test_full_campaign_rejects_custom_root_before_marker_or_cleanup(
    tmp_path: Path,
) -> None:
    custom = tmp_path / "existing_custom"
    custom.mkdir()
    sentinel = custom / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    with pytest.raises(
        B4GExecutionError, match="FULL_CAMPAIGN_REQUIRES_FORMAL_PHASE_ROOT",
    ):
        execute_campaign(
            output_root=custom,
            execution_source_freeze_terminal=tmp_path / "freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
        )
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not (custom / ".sim13_v4b4g_execution_output_root.json").exists()
    assert not (custom / "results").exists()


def test_smoke_rejects_formal_phase_root_before_any_evidence_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase = tmp_path / "formal_phase"
    phase.mkdir()
    sentinel = phase / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", phase)
    with pytest.raises(
        B4GExecutionError, match="SMOKE_REQUIRES_CUSTOM_DIAGNOSTIC_OUTPUT_ROOT",
    ):
        execute_smoke(slot_index=0, output_root=phase)
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not (phase / "evidence").exists()
    assert not (phase / "results").exists()


def test_smoke_and_full_reject_lexical_root_reparse_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase = tmp_path / "formal_phase"
    phase.mkdir()
    alias = tmp_path / "simulated_root_reparse"
    alias.mkdir()
    sentinel = alias / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator_module, "PHASE_ROOT", phase)
    original = orchestrator_module._is_managed_link_or_reparse
    monkeypatch.setattr(
        orchestrator_module,
        "_is_managed_link_or_reparse",
        lambda path: True if Path(path) == alias else original(path),
    )
    with pytest.raises(B4GExecutionError, match="ROOT_LINK_OR_REPARSE_FORBIDDEN"):
        execute_smoke(slot_index=0, output_root=alias)
    with pytest.raises(B4GExecutionError, match="ROOT_LINK_OR_REPARSE_FORBIDDEN"):
        execute_campaign(
            output_root=alias,
            execution_source_freeze_terminal=tmp_path / "freeze.json",
            expected_execution_source_freeze_terminal_sha256="A" * 64,
        )
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not (alias / ".sim13_v4b4g_execution_output_root.json").exists()


def test_runtime_identity_is_stable_non_overwriting_and_mismatch_fails(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    identity = {"python": "test", "numpy": "test", "classification": "DIAGNOSTIC_ONLY"}
    first = _ensure_runtime_evidence(path, identity)
    first_bytes = path.read_bytes()
    second = _ensure_runtime_evidence(path, identity)
    assert first == second
    assert path.read_bytes() == first_bytes
    with pytest.raises(B4GExecutionError, match="RESUME_RUNTIME_IDENTITY_MISMATCH"):
        _ensure_runtime_evidence(path, {**identity, "numpy": "drifted"})
    assert path.read_bytes() == first_bytes


def test_g12_four_state_applicability_matrix_00_01_10_11() -> None:
    metadata = _a1_reference_metadata()
    _set_finite(metadata, "RK4_REFERENCE", 0.5, 0.01)       # 01
    _set_finite(metadata, "MIDPOINT_REFERENCE", 0.5, 0.02)  # 10
    _set_finite(metadata, "RK4_REFERENCE", 1.0, 0.005)      # 11
    _set_finite(metadata, "MIDPOINT_REFERENCE", 1.0, 0.005)
    records, eligible = _reference_eligibility(metadata)
    by_level = {row["detail"]["level_id"]: row for row in records}
    state_00 = by_level["ALPHA_0P5__TCMD_MS_5"]
    state_01 = by_level["ALPHA_0P5__TCMD_MS_10"]
    state_10 = by_level["ALPHA_0P5__TCMD_MS_20"]
    state_11 = by_level["ALPHA_1__TCMD_MS_5"]
    assert (state_00["evaluation_status"], state_00["scientific_predicate"]) == (
        "NOT_APPLICABLE", None,
    )
    assert state_01["evaluation_status"] == "PASS"
    assert state_01["scientific_predicate"] is False
    assert state_10["evaluation_status"] == "PASS"
    assert state_10["scientific_predicate"] is False
    assert state_11["evaluation_status"] == "PASS"
    assert state_11["scientific_predicate"] is True
    assert eligible[0]["level_id"] == "ALPHA_1__TCMD_MS_5"


def test_exact_npz_schema_rejects_extra_shape_dtype_nonfinite_and_payload_drift(
    tmp_path: Path,
) -> None:
    arrays = _npz_arrays()
    metadata = _npz_metadata(arrays)
    valid = tmp_path / "valid.npz"
    atomic_write_npz(valid, arrays)
    assert validate_case_npz_schema(valid, metadata)["pass"] is True

    extra = tmp_path / "extra.npz"
    atomic_write_npz(extra, {**arrays, "unexpected": np.zeros(1)})
    with pytest.raises(ValueError, match="NPZ_EXACT_ARRAY_SET_MISMATCH"):
        validate_case_npz_schema(extra, metadata)

    wrong_shape = {**arrays, "service_state_29": np.zeros((3, 28), dtype="<f8")}
    wrong_shape_path = tmp_path / "wrong_shape.npz"
    atomic_write_npz(wrong_shape_path, wrong_shape)
    with pytest.raises(ValueError, match="NPZ_NATIVE_SHAPE_MISMATCH"):
        validate_case_npz_schema(wrong_shape_path, {**metadata, "numeric_payload_sha256": array_payload_sha256(wrong_shape)})

    wrong_dtype = {**arrays, "time_s": arrays["time_s"].astype("<f4")}
    wrong_dtype_path = tmp_path / "wrong_dtype.npz"
    np.savez_compressed(wrong_dtype_path, **wrong_dtype)
    with pytest.raises(ValueError, match="NPZ_FLOAT64_NOT_LITTLE_ENDIAN"):
        validate_case_npz_schema(wrong_dtype_path, metadata)

    nonfinite = {**arrays, "time_s": arrays["time_s"].copy()}
    nonfinite["time_s"][0] = np.nan
    nonfinite_path = tmp_path / "nonfinite.npz"
    np.savez_compressed(nonfinite_path, **nonfinite)
    with pytest.raises(ValueError, match="NPZ_NONFINITE_VALUE"):
        validate_case_npz_schema(nonfinite_path, metadata)

    with pytest.raises(ValueError, match="NPZ_NUMERIC_PAYLOAD_SHA256_MISMATCH"):
        validate_case_npz_schema(valid, {**metadata, "numeric_payload_sha256": "0" * 64})


def test_a2_mirror_requires_the_full_relative_grid(tmp_path: Path) -> None:
    left_path = tmp_path / "left.npz"
    right_path = tmp_path / "right.npz"
    left_time = np.asarray([0.1, 0.2, 0.3], dtype="<f8")
    right_time = left_time.copy()

    def arrays(time_s: np.ndarray) -> dict[str, np.ndarray]:
        return {
            "time_s": time_s,
            "left_gap_m": np.asarray([1.0, 2.0, 3.0], dtype="<f8"),
            "right_gap_m": np.asarray([4.0, 5.0, 6.0], dtype="<f8"),
            "left_gap_rate_m_s": np.asarray([7.0, 8.0, 9.0], dtype="<f8"),
            "right_gap_rate_m_s": np.asarray([10.0, 11.0, 12.0], dtype="<f8"),
            "signed_W_act_J": np.asarray([0.0, 0.5, 1.0], dtype="<f8"),
        }

    left_arrays = arrays(left_time)
    right_arrays = arrays(right_time)
    right_arrays["left_gap_m"], right_arrays["right_gap_m"] = (
        left_arrays["right_gap_m"], left_arrays["left_gap_m"],
    )
    right_arrays["left_gap_rate_m_s"], right_arrays["right_gap_rate_m_s"] = (
        left_arrays["right_gap_rate_m_s"], left_arrays["left_gap_rate_m_s"],
    )
    atomic_write_npz(left_path, left_arrays)
    atomic_write_npz(right_path, right_arrays)
    left_meta = {
        "event_provenance": {"acquisition_time_s": 0.1},
        "responses": {"finite_removal_event": True},
        "terminal_status": "REMOVED",
    }
    right_meta = {
        "event_provenance": {"acquisition_time_s": 0.1},
        "responses": {"finite_removal_event": True},
        "terminal_status": "REMOVED",
    }
    equal = compare_a2_mirror_pair(left_meta, right_meta, left_path, right_path)
    assert equal["scientific_predicate"] is True
    assert equal["full_relative_grid_equal"] is True
    assert equal["left_relative_sample_count"] == equal["right_relative_sample_count"] == 3

    right_arrays["time_s"] = np.asarray([0.1, 0.2, 0.31], dtype="<f8")
    atomic_write_npz(right_path, right_arrays)
    mismatched = compare_a2_mirror_pair(left_meta, right_meta, left_path, right_path)
    assert mismatched["scientific_predicate"] is False
    assert mismatched["full_relative_grid_equal"] is False
    assert mismatched["missing_exact_common_grid"] is True


def test_finite_clearance_payload_contains_the_complete_interval_partition() -> None:
    sample_count = 3
    zeros = np.zeros(sample_count, dtype=float)
    result = SimpleNamespace(
        time_s=np.asarray([0.0, 0.001, 0.002], dtype=float),
        state_30=np.zeros((sample_count, 30), dtype=float),
        total_linear_momentum_n_s=np.zeros((sample_count, 3), dtype=float),
        total_angular_momentum_n_m_s=np.zeros((sample_count, 3), dtype=float),
        sample_ledgers={
            "energy_minus_work_residual_J": zeros,
            "ideal_constraint_power_W": zeros,
            "active_contact_force_N": zeros,
            "active_contact_torque_N_m": zeros,
        },
        command_q_14=np.zeros((sample_count, 14), dtype=float),
        event=SimpleNamespace(time_s=0.0),
        command=SimpleNamespace(end_time_s=lambda acquisition: acquisition),
        left_gap_m=np.full(sample_count, 2.0e-6),
        right_gap_m=np.full(sample_count, 2.0e-6),
        left_gap_rate_m_s=zeros,
        right_gap_rate_m_s=zeros,
        clearance={"finite_event": True, "removal_time_s": 0.002},
    )
    payload = _clearance_certificate_payload(result)
    assert payload["finite_event"] is True
    assert payload["tau_c_s"] == pytest.approx(0.001, abs=1.0e-15)
    assert payload["removal_time_s"] == pytest.approx(0.002, abs=1.0e-15)
    assert payload["certified_good_interval_s"] == pytest.approx([0.0, 0.002])
    assert np.allclose(
        np.asarray(payload["certified_good_intervals_s"]),
        np.asarray([[0.0, 0.002]]),
        rtol=0.0,
        atol=1.0e-15,
    )


def test_resume_recovers_both_orphan_directions_and_preserves_valid_a2_na(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "evidence" / "raw_cases"
    raw.mkdir(parents=True)
    pre_run = _pre_run_context(tmp_path)
    source_hashes = {"identity": "frozen"}

    npz_only_slot = {
        "slot_index": 1, "case_id": "NPZ_ONLY", "lane_id": "LANE",
        "arm": "A1", "alpha": 1.0, "command_duration_s": 0.01,
    }
    npz_only_meta = raw / "001__NPZ_ONLY.json"
    npz_only = raw / "001__NPZ_ONLY.npz"
    npz_only.write_bytes(b"orphan")
    assert _load_resumable_case(
        npz_only_meta, npz_only, slot=npz_only_slot, execution_ordinal=0,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=None,
        q_ref_n=1.0,
    ) is None
    assert not npz_only.exists()

    json_only_slot = {
        "slot_index": 2, "case_id": "JSON_ONLY", "lane_id": "LANE",
        "arm": "A1", "alpha": 1.0, "command_duration_s": 0.01,
    }
    json_only = raw / "002__JSON_ONLY.json"
    json_only_npz = raw / "002__JSON_ONLY.npz"
    atomic_write_json(json_only, {"execution_status": "EXECUTED_FRESH_REGISTERED_SLOT"})
    assert _load_resumable_case(
        json_only, json_only_npz, slot=json_only_slot, execution_ordinal=1,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=None,
        q_ref_n=1.0,
    ) is None
    assert not json_only.exists()

    na_slot = {
        "slot_index": 3, "case_id": "A2_NA", "lane_id": "LANE",
        "arm": "A2", "variant_id": "RIGHT_HALF_DELAY",
    }
    na_path = raw / "003__A2_NA.json"
    na_npz = raw / "003__A2_NA.npz"
    na_payload = not_evaluated_a2_payload(
        slot=na_slot, execution_ordinal=2, source_hashes=source_hashes,
    )
    assert na_payload["event_provenance"]["acquisition_certificate_payload"] is None
    atomic_write_json(na_path, na_payload)
    resumed = _load_resumable_case(
        na_path, na_npz, slot=na_slot, execution_ordinal=2,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=None,
        q_ref_n=None,
    )
    assert resumed == na_payload
    receipts = list((tmp_path / "evidence" / "recovery_receipts").glob("*.json"))
    assert len(receipts) == 2


def test_orphan_recovery_rejects_linked_raw_root_before_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "evidence/raw_cases"
    raw.mkdir(parents=True)
    orphan = raw / "orphan.npz"
    orphan.write_bytes(b"owned-placeholder")
    external = tmp_path / "external_target.npz"
    external.write_bytes(b"external-preserve")
    original = orchestrator_module._is_managed_link_or_reparse
    monkeypatch.setattr(
        orchestrator_module,
        "_is_managed_link_or_reparse",
        lambda path: True if Path(path) == raw else original(path),
    )
    with pytest.raises(
        B4GExecutionError,
        match="MANAGED_OUTPUT_DIRECTORY_LINK_REPARSE_OR_NONDIR",
    ):
        _safe_orphan_recovery(orphan, raw, "TEST_LINKED_RAW_ROOT")
    assert orphan.read_bytes() == b"owned-placeholder"
    assert external.read_bytes() == b"external-preserve"


def test_resume_rejects_coordinated_external_json_and_npz_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "evidence/raw_cases"
    raw.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    external_metadata = external / "case.json"
    external_npz = external / "case.npz"
    external_metadata.write_text("{}\n", encoding="utf-8")
    external_npz.write_bytes(b"external-npz-preserve")
    metadata_link = raw / "005__LINKED.json"
    npz_link = raw / "005__LINKED.npz"
    simulated_link_paths: set[Path] = set()
    try:
        metadata_link.symlink_to(external_metadata)
        npz_link.symlink_to(external_npz)
    except OSError:
        # Windows CI commonly lacks SeCreateSymbolicLinkPrivilege.  Preserve
        # the same lexical lstat branch by simulating the two reparse entries.
        for link in (metadata_link, npz_link):
            if link.is_symlink():
                link.unlink()
        metadata_link.write_bytes(external_metadata.read_bytes())
        npz_link.write_bytes(external_npz.read_bytes())
        simulated_link_paths = {metadata_link, npz_link}
        original = orchestrator_module._is_managed_link_or_reparse
        monkeypatch.setattr(
            orchestrator_module,
            "_is_managed_link_or_reparse",
            lambda path: (
                True if Path(path) in simulated_link_paths else original(path)
            ),
        )

    with pytest.raises(
        B4GExecutionError,
        match="RESUME_SHARD_NOT_PLAIN_REGULAR_FILE",
    ):
        _load_resumable_case(
            metadata_link,
            npz_link,
            slot={
                "slot_index": 5,
                "case_id": "LINKED",
                "lane_id": "LANE",
                "arm": "A1",
            },
            execution_ordinal=4,
            source_hashes={"identity": "frozen"},
            pre_run=_pre_run_context(tmp_path),
            selected_parent=None,
            q_ref_n=1.0,
        )
    assert external_metadata.read_text(encoding="utf-8") == "{}\n"
    assert external_npz.read_bytes() == b"external-npz-preserve"


def test_resume_binds_selected_a2_parent_and_external_pre_run_context(tmp_path: Path) -> None:
    raw = tmp_path / "evidence" / "raw_cases"
    raw.mkdir(parents=True)
    pre_run = _pre_run_context(tmp_path)
    source_hashes = {"identity": "frozen", "runtime_identity_sha256": "A" * 64}
    slot = {
        "slot_index": 4, "case_id": "A2_CASE", "lane_id": "RK4_COARSE",
        "arm": "A2", "variant_id": "RIGHT_HALF_DELAY",
    }
    metadata_path = raw / "004__A2_CASE.json"
    npz_path = raw / "004__A2_CASE.npz"
    arrays = _npz_arrays()
    receipt = atomic_write_npz(npz_path, arrays)
    parent = {"level_id": "LEVEL_A", "alpha": 2.0, "command_duration_s": 0.01}
    acquisition, event_provenance = _acquisition_certificate_fields(
        "RK4_COARSE", "A2_CASE",
    )
    metadata = {
        "schema": "SIM13_V4B4G_CASE_METADATA_V1",
        "slot_index": 4,
        "execution_ordinal": 3,
        "registered_slot": slot,
        "case_id": "A2_CASE",
        "lane_id": "RK4_COARSE",
        "arm": "A2",
        "execution_status": "EXECUTED_FRESH_REGISTERED_SLOT",
        "source_hashes": source_hashes,
        "acquisition": acquisition,
        "event_provenance": event_provenance,
        "command_parameters": {
            "Q_ref_per_finger_N": 1.0,
            "only_nonzero_generalized_force_indices_zero_based": [12, 13],
            "left": {"alpha": 2.0, "delay_s": 0.0, "duration_s": 0.01},
            "right": {"alpha": 1.0, "delay_s": 0.005, "duration_s": 0.01},
            "physical_actuator_force_capacity_N": None,
            "selected_parent_level": parent,
        },
        "responses": {"finite_removal_event": False, "sample_count": 3},
        "numeric_payload_sha256": array_payload_sha256(arrays),
        "npz_path": npz_path.resolve().as_posix(),
        "npz_bytes": receipt["bytes"],
        "npz_sha256": receipt["sha256"],
        "npz_arrays": receipt["arrays"],
    }
    atomic_write_json(metadata_path, metadata)
    assert _load_resumable_case(
        metadata_path, npz_path, slot=slot, execution_ordinal=3,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=parent,
        q_ref_n=1.0,
    ) == metadata
    tampered_payload = read_json(metadata_path)
    tampered_payload["event_provenance"]["acquisition_certificate_payload"]["event"]["time_s"] += 1.0e-6
    atomic_write_json(metadata_path, tampered_payload)
    with pytest.raises(B4GExecutionError, match="RESUME_ACQUISITION_CERTIFICATE_INVALID"):
        _load_resumable_case(
            metadata_path, npz_path, slot=slot, execution_ordinal=3,
            source_hashes=source_hashes, pre_run=pre_run, selected_parent=parent,
            q_ref_n=1.0,
        )
    tampered_payload["event_provenance"]["acquisition_certificate_sha256"] = canonical_sha256(
        tampered_payload["event_provenance"]["acquisition_certificate_payload"]
    )
    atomic_write_json(metadata_path, tampered_payload)
    with pytest.raises(B4GExecutionError, match="RESUME_ACQUISITION_CERTIFICATE_INVALID"):
        _load_resumable_case(
            metadata_path, npz_path, slot=slot, execution_ordinal=3,
            source_hashes=source_hashes, pre_run=pre_run, selected_parent=parent,
            q_ref_n=1.0,
        )
    atomic_write_json(metadata_path, metadata)
    with pytest.raises(B4GExecutionError, match="RESUME_A2_SELECTED_PARENT_MISMATCH"):
        _load_resumable_case(
            metadata_path, npz_path, slot=slot, execution_ordinal=3,
            source_hashes=source_hashes, pre_run=pre_run,
            selected_parent={**parent, "alpha": 4.0},
            q_ref_n=1.0,
        )
    with pytest.raises(B4GExecutionError, match="PRE_RUN_EXECUTION_LEDGER_DRIFT"):
        Path(pre_run["pre_run_execution_ledger_path"]).write_text("{}\n", encoding="utf-8")
        _load_resumable_case(
            metadata_path, npz_path, slot=slot, execution_ordinal=3,
            source_hashes=source_hashes, pre_run=pre_run, selected_parent=parent,
            q_ref_n=1.0,
        )


def test_campaign_writer_publishes_only_provisional_post_after_summary(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    summary = tmp_path / "results" / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    atomic_write_json(summary, {"schema": "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1"})
    snapshot = {"snapshot_payload_sha256": "A" * 64, "pass": True}
    recursive = {"pass": True, "direct_binding_count": 11}
    payload = _write_provisional_post_campaign_snapshot(
        evidence_root=evidence,
        post_snapshot=snapshot,
        recursive_after=recursive,
        runtime_identity={"python": "test"},
        campaign_summary_path=summary,
        a0_parent_trace_post_verification={
            "manifest": {"sha256": "B" * 64},
            "pass": True,
        },
    )
    assert payload["final_post_run"] is False
    assert payload["negative_controls_completed"] is False
    assert (evidence / "SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json").is_file()
    assert not (evidence / "SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json").exists()


def test_json_loader_rejects_duplicate_keys_at_any_depth(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"outer":{"x":1,"x":2}}\n', encoding="utf-8")
    with pytest.raises(EvidenceIOError, match="JSON_DUPLICATE_KEY:x"):
        read_json(duplicate)


def test_g06_uses_finite_maximum_absolute_residual() -> None:
    maximum, finite = _finite_max_abs(np.asarray([-2.0e-3, 1.0e-12]))
    assert finite is True
    assert maximum == pytest.approx(2.0e-3)
    result = SimpleNamespace(
        time_s=np.asarray([], dtype=float),
        command_q_14=np.zeros((0, 14), dtype=float),
        sample_ledgers={
            "energy_minus_work_residual_J": np.asarray([-2.0e-3]),
            "linear_momentum_drift_N_s": np.asarray([0.0]),
            "angular_momentum_drift_N_m_s": np.asarray([0.0]),
            "active_contact_force_N": np.asarray([0.0]),
            "active_contact_torque_N_m": np.asarray([0.0]),
        },
        post_release=None,
        geometry_domain_pass=True,
        failure=None,
        stage_audits=[],
        synthetic_removal_executed=False,
    )
    records, metrics = case_gate_records(
        result,
        arm="A1",
        q_ref_n=1.0,
        a0_comparison=None,
        clearance_payload={"finite_event": False},
    )
    g06 = next(record for record in records if record["gate_id"].startswith("B4F-G06"))
    assert g06["evaluation_status"] == "FAIL"
    assert g06["scientific_predicate"] is False
    assert g06["detail"]["active_max_residual_J"] == pytest.approx(2.0e-3)
    assert metrics["energy_minus_work_max_residual_J"] == pytest.approx(2.0e-3)


def test_a0_parent_bundle_binds_exact_lane_method_step_and_fixed_certificate(
    tmp_path: Path,
) -> None:
    pre_run = _pre_run_context(tmp_path)
    binding = {
        "path": pre_run["a0_parent_reference_trace_manifest_path"],
        "bytes": pre_run["a0_parent_reference_trace_manifest_bytes"],
        "sha256": pre_run["a0_parent_reference_trace_manifest_sha256"],
    }
    assert _verify_a0_parent_trace_bundle(binding)["pass"] is True
    manifest_path = Path(binding["path"])
    manifest = read_json(manifest_path)
    manifest["traces"][0]["step_s"] = 0.0005
    atomic_write_json(manifest_path, manifest)
    tampered_binding = {
        "path": manifest_path.resolve().as_posix(),
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    }
    with pytest.raises(B4GExecutionError, match="PROVENANCE_OR_ARRAY_INVENTORY_MISMATCH"):
        _verify_a0_parent_trace_bundle(tampered_binding)


def test_a0_active_trace_oracle_rejects_byte_and_array_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oracle, _ = _load_b4e_active_trace_oracle()
    arrays = _a0_parent_oracle_arrays("RK4_COARSE", oracle)
    changed = {name: value.copy() for name, value in arrays.items()}
    changed["left_gap_m"][0] += 1.0e-15
    with pytest.raises(B4GExecutionError, match="ORACLE_ARRAY_NOT_EXACT"):
        _assert_a0_parent_matches_oracle("RK4_COARSE", changed, arrays)

    source_path, source_bytes, source_sha256 = (
        orchestrator_module._B4E_ACTIVE_TRACES_BINDING
    )
    tampered_path = tmp_path / source_path.name
    payload = bytearray(source_path.read_bytes())
    payload[-2] = ord(" ") if payload[-2] != ord(" ") else ord("\t")
    tampered_path.write_bytes(payload)
    monkeypatch.setattr(
        orchestrator_module,
        "_B4E_ACTIVE_TRACES_BINDING",
        (tampered_path, source_bytes, source_sha256),
    )
    with pytest.raises(B4GExecutionError, match="ACTIVE_TRACES_ORACLE_DRIFT"):
        _load_b4e_active_trace_oracle()


def test_a0_quaternion_geodesic_stable_regression_matrix() -> None:
    pathological = np.asarray([
        -0.01568825063444881,
        0.8246611675132001,
        0.5249352596774691,
        -0.21007334608451503,
    ])
    assert float(np.dot(pathological, pathological)) == np.nextafter(1.0, 0.0)
    identity = np.asarray([1.0, 0.0, 0.0, 0.0])
    orthogonal = np.asarray([0.0, 1.0, 0.0, 0.0])
    theta_pass = 5.0e-13
    theta_fail = 2.0e-12
    within_g02 = np.asarray([
        np.cos(theta_pass / 2.0), np.sin(theta_pass / 2.0), 0.0, 0.0,
    ])
    outside_g02 = np.asarray([
        np.cos(theta_fail / 2.0), np.sin(theta_fail / 2.0), 0.0, 0.0,
    ])
    left = np.stack([
        pathological, identity, identity, identity, identity,
    ])
    right = np.stack([
        pathological, -identity, orthogonal, within_g02, outside_g02,
    ])

    geodesic = _sign_aligned_unit_quaternion_geodesic_rows(left, right)

    assert geodesic[0] == 0.0
    assert geodesic[0] <= 1.0e-12
    assert geodesic[1] == 0.0
    assert geodesic[2] == pytest.approx(np.pi, abs=1.0e-15)
    assert geodesic[3] == pytest.approx(theta_pass, rel=1.0e-15)
    assert geodesic[3] <= 1.0e-12
    assert geodesic[4] == pytest.approx(theta_fail, rel=1.0e-15)
    assert geodesic[4] > 1.0e-12


@pytest.mark.parametrize(
    ("left", "right", "error"),
    [
        (np.zeros((1, 4)), np.asarray([[1.0, 0.0, 0.0, 0.0]]), "NONUNIT"),
        (
            np.asarray([[1.0 + 2.0e-12, 0.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "NONUNIT",
        ),
        (
            np.asarray([[np.nan, 0.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "NONFINITE",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            np.asarray([[np.inf, 0.0, 0.0, 0.0]]),
            "NONFINITE",
        ),
        (
            np.asarray([1.0, 0.0, 0.0, 0.0]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "SHAPE_MISMATCH",
        ),
        (
            np.empty((0, 4)), np.empty((0, 4)), "SHAPE_MISMATCH",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0]]),
            "SHAPE_MISMATCH",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            np.asarray([
                [1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0],
            ]),
            "SHAPE_MISMATCH",
        ),
    ],
)
def test_a0_quaternion_geodesic_rejects_invalid_inputs(
    left: np.ndarray,
    right: np.ndarray,
    error: str,
) -> None:
    with pytest.raises(B4GExecutionError, match=error):
        _sign_aligned_unit_quaternion_geodesic_rows(left, right)


def test_six_frozen_b4e_parent_quaternion_self_geodesics_are_exact_zero() -> None:
    oracle, _ = _load_b4e_active_trace_oracle()
    observed: dict[str, float] = {}
    for lane_id in _A0_LANE_DEFINITION:
        quaternion = _a0_parent_oracle_arrays(
            lane_id, oracle,
        )["service_quaternion_wxyz"]
        geodesic = _sign_aligned_unit_quaternion_geodesic_rows(
            quaternion, quaternion,
        )
        observed[lane_id] = float(np.max(geodesic))
    assert observed == {lane_id: 0.0 for lane_id in _A0_LANE_DEFINITION}


def test_resume_fresh_replay_rejects_coordinated_raw_and_metadata_tamper(
    tmp_path: Path,
) -> None:
    npz_path = tmp_path / "case.npz"
    fresh_arrays = _npz_arrays()
    tampered_arrays = {name: value.copy() for name, value in fresh_arrays.items()}
    tampered_arrays["service_state_29"][0, 0] = 1.0
    receipt = atomic_write_npz(npz_path, tampered_arrays)
    fresh_metadata = {
        "case_id": "CASE",
        "responses": {"finite_removal_event": False},
        "numeric_payload_sha256": array_payload_sha256(fresh_arrays),
    }
    coordinated = {
        **fresh_metadata,
        "responses": {"finite_removal_event": True},
        "numeric_payload_sha256": array_payload_sha256(tampered_arrays),
        "npz_path": display_path(npz_path, PROJECT_ROOT),
        "npz_bytes": receipt["bytes"],
        "npz_sha256": receipt["sha256"],
        "npz_arrays": receipt["arrays"],
    }
    with pytest.raises(B4GExecutionError, match="FRESH_REPLAY_NUMERIC_MISMATCH"):
        _verify_resumed_case_against_fresh_replay(
            resumed=coordinated,
            npz_path=npz_path,
            fresh_metadata=fresh_metadata,
            fresh_arrays=fresh_arrays,
        )

    receipt = atomic_write_npz(npz_path, fresh_arrays)
    exact = {
        **fresh_metadata,
        "npz_path": display_path(npz_path, PROJECT_ROOT),
        "npz_bytes": receipt["bytes"],
        "npz_sha256": receipt["sha256"],
        "npz_arrays": receipt["arrays"],
    }
    _verify_resumed_case_against_fresh_replay(
        resumed=exact,
        npz_path=npz_path,
        fresh_metadata=fresh_metadata,
        fresh_arrays=fresh_arrays,
    )
    exact["responses"] = {"finite_removal_event": True}
    with pytest.raises(B4GExecutionError, match="FRESH_REPLAY_METADATA_MISMATCH"):
        _verify_resumed_case_against_fresh_replay(
            resumed=exact,
            npz_path=npz_path,
            fresh_metadata=fresh_metadata,
            fresh_arrays=fresh_arrays,
        )


def test_resumed_executed_case_still_invokes_fresh_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "raw_cases"
    raw.mkdir()
    slot = {
        "slot_index": 0,
        "case_id": "CASE",
        "lane_id": "RK4_COARSE",
        "arm": "A1",
    }
    arrays = _npz_arrays()
    npz_path = raw / "000__CASE.npz"
    receipt = atomic_write_npz(npz_path, arrays)
    fresh_metadata = {"case_id": "CASE", "derived": "fresh"}
    resumed = {
        **fresh_metadata,
        "npz_path": display_path(npz_path, PROJECT_ROOT),
        "npz_bytes": receipt["bytes"],
        "npz_sha256": receipt["sha256"],
        "npz_arrays": receipt["arrays"],
    }
    calls = {"fresh": 0}
    monkeypatch.setattr(
        orchestrator_module,
        "_load_resumable_case",
        lambda *args, **kwargs: resumed,
    )

    def fresh_candidate(**kwargs: Any) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
        calls["fresh"] += 1
        return fresh_metadata, arrays

    monkeypatch.setattr(
        orchestrator_module, "_fresh_executed_case_candidate", fresh_candidate,
    )
    returned = _publish_executed_case(
        slot=slot,
        execution_ordinal=0,
        raw_root=raw,
        source_hashes={},
        q_ref_n=1.0,
        selected_parent=None,
        pre_run={},
    )
    assert returned == resumed
    assert calls["fresh"] == 1


def test_a2_na_resume_requires_exact_deterministic_regeneration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "raw_cases"
    raw.mkdir()
    slot = {
        "slot_index": 1,
        "case_id": "A2_NA",
        "lane_id": "RK4_COARSE",
        "arm": "A2",
        "variant_id": "RIGHT_COMMAND_OFF",
    }
    expected = not_evaluated_a2_payload(
        slot=slot, execution_ordinal=1, source_hashes={"frozen": True},
    )
    tampered = {
        **expected,
        "applicability_reason": "COORDINATED_TAMPER",
    }
    monkeypatch.setattr(
        orchestrator_module,
        "_load_resumable_case",
        lambda *args, **kwargs: tampered,
    )
    with pytest.raises(B4GExecutionError, match="A2_NA_FRESH_REGENERATION_MISMATCH"):
        _publish_na_a2(
            slot=slot,
            execution_ordinal=1,
            raw_root=raw,
            source_hashes={"frozen": True},
            pre_run={},
        )


def test_raw_case_inventory_is_exact_and_rejects_unregistered_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "raw_cases"
    raw.mkdir()
    schedule = read_json(CONTRACT_ROOT / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    metadata: list[dict[str, Any]] = []
    for slot in schedule["slots"]:
        expected_json, expected_npz = orchestrator_module._case_paths(raw, slot)
        expected_json.write_text("{}\n", encoding="utf-8")
        status = (
            "NOT_EVALUATED_NO_A1_SUCCESS"
            if slot["arm"] == "A2"
            else "EXECUTED_FRESH_REGISTERED_SLOT"
        )
        if status == "EXECUTED_FRESH_REGISTERED_SLOT":
            expected_npz.write_bytes(b"inventory-only")
        metadata.append({
            "slot_index": slot["slot_index"],
            "case_id": slot["case_id"],
            "registered_slot": slot,
            "execution_status": status,
        })
    audit = _verify_raw_case_inventory(
        raw, schedule, metadata, phase="TEST_EXACT",
    )
    assert audit["registered_json_count"] == 144
    assert audit["executed_npz_count"] == 120
    (raw / "UNREGISTERED.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(B4GExecutionError, match="RAW_CASE_INVENTORY_EXACT_SET_MISMATCH"):
        _verify_raw_case_inventory(raw, schedule, metadata, phase="TEST_EXTRA")
    (raw / "UNREGISTERED.json").unlink()
    linked_entry = next(raw.iterdir())
    original = orchestrator_module._is_managed_link_or_reparse
    monkeypatch.setattr(
        orchestrator_module,
        "_is_managed_link_or_reparse",
        lambda path: True if Path(path) == linked_entry else original(path),
    )
    with pytest.raises(B4GExecutionError, match="RAW_CASE_INVENTORY_NON_PLAIN_FILE"):
        _verify_raw_case_inventory(raw, schedule, metadata, phase="TEST_LINK")


def test_pre_shard_supersession_removes_only_exact_final_allowlist(
    tmp_path: Path,
) -> None:
    root = _prepare_output_root(tmp_path / "campaign")
    for relative in _STALE_FINAL_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old-final\n", encoding="utf-8")
    preserved = root / "evidence" / "raw_cases" / "case.json"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_text("raw\n", encoding="utf-8")
    receipt = _supersede_prior_final_credit(root)
    assert receipt["active"] is True
    assert len(receipt["prior_final_artifacts_removed"]) == len(
        _STALE_FINAL_RELATIVE_PATHS
    )
    assert all(not (root / relative).exists() for relative in _STALE_FINAL_RELATIVE_PATHS)
    assert preserved.is_file()
    assert (root / _SUPERSESSION_RECEIPT_RELATIVE_PATH).is_file()


def test_scientific_negative_outcomes_are_not_integrity_failures() -> None:
    scientific_case = {
        "case_id": "NEGATIVE_OUTCOME",
        "gate_records": [
            {
                "gate_id": "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
                "evaluation_status": "PASS",
                "scientific_predicate": False,
            },
            {
                "gate_id": "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
                "evaluation_status": "PASS",
                "scientific_predicate": False,
            },
        ],
    }
    scientific_global = [{
        "gate_id": "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC",
        "evaluation_status": "FAIL",
        "scientific_predicate": False,
    }]
    assert _enforce_integrity_before_publication(
        [scientific_case], scientific_global,
    ) == ([], [])
    integrity_case = {
        "case_id": "BROKEN",
        "gate_records": [{
            "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
            "evaluation_status": "FAIL",
            "scientific_predicate": False,
        }],
    }
    with pytest.raises(B4GExecutionError, match="REGISTERED_CAMPAIGN_INTEGRITY_FAILURES"):
        _enforce_integrity_before_publication([integrity_case], [])
