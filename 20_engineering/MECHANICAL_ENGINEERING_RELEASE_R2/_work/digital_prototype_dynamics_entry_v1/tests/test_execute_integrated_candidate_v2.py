from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "execute_integrated_candidate_v2.py"
SPEC = importlib.util.spec_from_file_location("execution_v2", SOURCE)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_failure_receipt_is_fail_closed_and_does_not_infer_memory_authority() -> None:
    payload = mod.build_failure_payload(
        run_digest="A" * 64,
        returncode=7,
        stdout="stdout",
        stderr="stderr",
    )
    assert payload["v1_wrapper_returncode"] == 7
    assert payload["memory_gate_passed_inferred"] is False
    assert payload["owner_override_status_inferred"] is False
    assert payload["next_stage_authorized"] is False
    assert payload["release_credit"] is False
    assert payload["retry_policy"].startswith("FAIL_CLOSED")


def test_tail_is_bounded() -> None:
    value = "x" * 13000
    assert len(mod.tail(value)) == 12000
    assert mod.tail("short") == "short"


def test_artifact_record_for_missing_path_is_null(tmp_path: Path) -> None:
    assert mod.artifact_record(tmp_path / "missing") is None


def test_write_exclusive_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "receipt.json"
    mod.write_exclusive(target, {"a": 1})
    try:
        mod.write_exclusive(target, {"a": 2})
    except FileExistsError:
        pass
    else:
        raise AssertionError("immutable receipt overwrite must fail")


def prepare_success_fixture(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
    digest = "A" * 64
    authority_dir = tmp_path / "authority"
    execution_dir = tmp_path / "execution"
    authority_dir.mkdir()
    execution_dir.mkdir()
    step = tmp_path / "candidate.step"
    glb = tmp_path / ".candidate.step.glb"
    step.write_bytes(b"STEP")
    glb.write_bytes(b"GLB")
    authority = {
        "run_id_sha256": digest,
        "memory_gate_passed": True,
        "owner_override_used": False,
        "available_physical_memory_gib": 6.5,
    }
    execution = {
        "run_id_sha256": digest,
        "outputs": {
            "step": {"bytes": step.stat().st_size, "sha256": mod.sha256(step)},
            "glb_topology": {"bytes": glb.stat().st_size, "sha256": mod.sha256(glb)},
        },
    }
    (authority_dir / f"{digest}.json").write_text(json.dumps(authority), encoding="utf-8")
    execution_path = execution_dir / f"{digest}.json"
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    monkeypatch.setattr(mod, "AUTHORITY_DIR", authority_dir)
    monkeypatch.setattr(mod, "EXECUTION_DIR", execution_dir)
    monkeypatch.setattr(mod, "OUTPUT_STEP", step)
    monkeypatch.setattr(mod, "OUTPUT_GLB", glb)
    monkeypatch.setattr(mod, "ACTIVE_LOCK", tmp_path / "absent.lock")
    return digest, execution_path


def test_success_chain_binds_authority_execution_and_outputs(tmp_path: Path, monkeypatch) -> None:
    digest, _ = prepare_success_fixture(tmp_path, monkeypatch)
    payload = mod.build_success_chain(digest)
    assert payload["run_id_sha256"] == digest
    assert payload["authority_receipt"]["sha256"]
    assert payload["v1_execution_receipt"]["sha256"]
    assert payload["outputs"]["step"]["sha256"] == mod.sha256(mod.OUTPUT_STEP)
    assert payload["outputs"]["glb_topology"]["sha256"] == mod.sha256(mod.OUTPUT_GLB)
    assert payload["postgeneration_validation_required"] is True
    assert payload["snapshot_review_required"] is True
    assert payload["next_stage_authorized"] is False


def test_success_chain_rejects_tampered_execution_hash(tmp_path: Path, monkeypatch) -> None:
    digest, execution_path = prepare_success_fixture(tmp_path, monkeypatch)
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["outputs"]["step"]["sha256"] = "0" * 64
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    try:
        mod.build_success_chain(digest)
    except RuntimeError as exc:
        assert str(exc) == "EXECUTION_OUTPUT_STEP_MISMATCH"
    else:
        raise AssertionError("tampered execution hash must fail closed")


def configure_main_receipt_paths(tmp_path: Path, monkeypatch) -> str:
    run_id = "unit-test-fresh-run-0001"
    monkeypatch.setenv("R2_DP_RUN_ID", run_id)
    monkeypatch.setattr(mod, "AUTHORITY_DIR", tmp_path / "authority")
    monkeypatch.setattr(mod, "EXECUTION_DIR", tmp_path / "execution")
    monkeypatch.setattr(mod, "FAILURE_DIR", tmp_path / "failure")
    monkeypatch.setattr(mod, "CHAIN_DIR", tmp_path / "chain")
    monkeypatch.setattr(mod, "OUTPUT_STEP", tmp_path / "candidate.step")
    monkeypatch.setattr(mod, "OUTPUT_GLB", tmp_path / ".candidate.step.glb")
    monkeypatch.setattr(mod, "ACTIVE_LOCK", tmp_path / "active.lock")
    return mod.hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()


def test_subprocess_invocation_exception_writes_immutable_failure_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    digest = configure_main_receipt_paths(tmp_path, monkeypatch)

    def explode(*args, **kwargs):
        raise OSError("synthetic invocation failure")

    monkeypatch.setattr(mod.subprocess, "run", explode)
    assert mod.main() == 2
    failure_path = mod.FAILURE_DIR / f"{digest}.json"
    payload = json.loads(failure_path.read_text(encoding="utf-8"))
    assert payload["v1_wrapper_returncode"] == 2
    assert "V1_WRAPPER_INVOCATION_EXCEPTION" in payload["v1_stderr_tail"]
    assert payload["next_stage_authorized"] is False


def test_success_chain_commit_exception_falls_back_to_failure_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    digest = configure_main_receipt_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    monkeypatch.setattr(mod, "build_success_chain", lambda run_digest: {"run_id_sha256": run_digest})
    original_write = mod.write_exclusive

    def fail_chain_write(path: Path, value: object) -> None:
        if path.parent == mod.CHAIN_DIR:
            raise OSError("synthetic chain commit failure")
        original_write(path, value)

    monkeypatch.setattr(mod, "write_exclusive", fail_chain_write)
    assert mod.main() == 3
    failure_path = mod.FAILURE_DIR / f"{digest}.json"
    payload = json.loads(failure_path.read_text(encoding="utf-8"))
    assert payload["v1_wrapper_returncode"] == 3
    assert "POST_V1_CHAIN_FAILURE" in payload["v1_stderr_tail"]
    assert payload["release_credit"] is False


def test_success_chain_rejects_active_writer_lock(tmp_path: Path, monkeypatch) -> None:
    digest, _ = prepare_success_fixture(tmp_path, monkeypatch)
    mod.ACTIVE_LOCK.write_text("locked", encoding="utf-8")
    with pytest.raises(RuntimeError, match="SUCCESS_CHAIN_ACTIVE_LOCK_STILL_PRESENT"):
        mod.build_success_chain(digest)
