"""NC18 backend tests: schema, nominal, malformed, missing/stale source,
phase-only fail-closed, deterministic replay, read-only."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from sim13_v2_backends.dynamics_backend import (
    BackendSourceError,
    PhaseOnlyBackend,
    UnifiedR2DynamicsBackend,
    build_validation_receipt,
    state_evolution_assessment,
    URDF_RELATIVE_PATH,
    URDF_RECEIPT_RELATIVE_PATH,
)


def _backend(project_root: Path) -> UnifiedR2DynamicsBackend:
    return UnifiedR2DynamicsBackend(project_root=project_root)


def test_schema_and_source_manifest(project_root):
    backend = _backend(project_root)
    manifest = backend.source_manifest()
    assert manifest["model"]["links"] == 19
    assert manifest["model"]["joints"] == 18
    assert manifest["model"]["movable_dof"] == 8
    assert abs(manifest["model"]["total_mass_kg"] - 31.022864807342987) <= 1.0e-12
    receipt = build_validation_receipt(backend)
    assert receipt["schema"] == "SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1"
    assert receipt["all_checks_pass"] is True
    assert receipt["next_stage_authorized"] is False
    assert receipt["release_credit"] is False


def test_nominal_state_evolution_real_and_momentum_conserved(project_root):
    backend = _backend(project_root)
    initial = backend.initial_state()
    after, assessment, audit = backend.advance(
        initial,
        generalized_effort=backend.nominal_generalized_effort(),
        step_s=1.0e-3,
        steps=10,
    )
    assert assessment["accepted"] is True
    assert assessment["reason_code"] == "REAL_NUMERICAL_STATE_EVOLUTION_DETECTED"
    assert assessment["deltas"]["revolute_q_max_abs_rad"] > 0.0
    assert assessment["deltas"]["ee_centroid_position_norm_m"] > 0.0
    assert audit["momentum_conserved_within_limit"] is True
    assert audit["linear_momentum_residual_Ns"] <= 1.0e-9
    assert audit["angular_momentum_residual_Nms"] <= 1.0e-9


def test_phase_only_step_rejected_fail_closed(project_root):
    backend = _backend(project_root)
    initial = backend.initial_state()
    phase_only = PhaseOnlyBackend(backend).advance(initial)
    assessment = state_evolution_assessment(initial, phase_only)
    assert assessment["accepted"] is False
    assert assessment["reason_code"] == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"


def test_malformed_inputs_rejected(project_root):
    backend = _backend(project_root)
    initial = backend.initial_state()
    with pytest.raises(ValueError):
        backend.advance(
            initial,
            generalized_effort=(0.0,) * 7,  # wrong width
            step_s=1.0e-3,
            steps=10,
        )
    with pytest.raises(ValueError):
        backend.advance(
            initial,
            generalized_effort=backend.nominal_generalized_effort(),
            step_s=0.0,
            steps=10,
        )
    with pytest.raises(ValueError):
        backend.advance(
            initial,
            generalized_effort=backend.nominal_generalized_effort(),
            step_s=1.0e-3,
            steps=0,
        )


def test_missing_urdf_source_rejected(tmp_path):
    with pytest.raises(BackendSourceError, match="UNIFIED_R2_URDF_SOURCE_MISSING"):
        _backend(tmp_path)


def _stage_fake_root(project_root: Path, tmp_path: Path) -> Path:
    fake = tmp_path / "fake_root"
    urdf_target = fake / URDF_RELATIVE_PATH
    receipt_target = fake / URDF_RECEIPT_RELATIVE_PATH
    urdf_target.parent.mkdir(parents=True, exist_ok=True)
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project_root / URDF_RELATIVE_PATH, urdf_target)
    shutil.copyfile(project_root / URDF_RECEIPT_RELATIVE_PATH, receipt_target)
    return fake


def test_stale_urdf_hash_rejected(project_root, tmp_path):
    fake = _stage_fake_root(project_root, tmp_path)
    urdf_path = fake / URDF_RELATIVE_PATH
    payload = bytearray(urdf_path.read_bytes())
    payload[-1] ^= 0x01
    urdf_path.write_bytes(bytes(payload))
    with pytest.raises(BackendSourceError, match="UNIFIED_R2_URDF_SOURCE_HASH_DRIFT"):
        _backend(fake)


def test_missing_and_stale_receipt_rejected(project_root, tmp_path):
    fake = _stage_fake_root(project_root, tmp_path)
    (fake / URDF_RECEIPT_RELATIVE_PATH).unlink()
    with pytest.raises(
        BackendSourceError, match="UNIFIED_R2_URDF_EXECUTION_RECEIPT_MISSING"
    ):
        _backend(fake)
    fake = _stage_fake_root(project_root, tmp_path / "second")
    receipt_path = fake / URDF_RECEIPT_RELATIVE_PATH
    payload = bytearray(receipt_path.read_bytes())
    payload[-1] ^= 0x01
    receipt_path.write_bytes(bytes(payload))
    with pytest.raises(
        BackendSourceError, match="UNIFIED_R2_URDF_EXECUTION_RECEIPT_HASH_DRIFT"
    ):
        _backend(fake)


def test_deterministic_replay_identical_states(project_root):
    backend = _backend(project_root)
    initial = backend.initial_state()
    outcomes = []
    for _ in range(2):
        after, assessment, audit = backend.advance(
            initial,
            generalized_effort=backend.nominal_generalized_effort(),
            step_s=1.0e-3,
            steps=10,
        )
        outcomes.append((after, dict(assessment), dict(audit)))
    assert outcomes[0] == outcomes[1]


def test_backend_is_read_only(project_root):
    targets = [
        project_root / URDF_RELATIVE_PATH,
        project_root / URDF_RECEIPT_RELATIVE_PATH,
    ]
    before = {path: path.read_bytes() for path in targets}
    backend = _backend(project_root)
    initial = backend.initial_state()
    backend.advance(
        initial,
        generalized_effort=backend.nominal_generalized_effort(),
        step_s=1.0e-3,
        steps=10,
    )
    build_validation_receipt(backend)
    after = {path: path.read_bytes() for path in targets}
    assert before == after
