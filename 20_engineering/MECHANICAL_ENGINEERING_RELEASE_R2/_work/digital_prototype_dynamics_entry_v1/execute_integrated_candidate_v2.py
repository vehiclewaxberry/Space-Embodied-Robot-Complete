"""Chain-of-custody wrapper around the guarded V1 CAD execution wrapper.

V1 owns the irreversible run/override consumption and CAD generation.  This V2
wrapper adds an immutable failure receipt on any non-zero exit and, on success,
binds the authority receipt, V1 execution receipt and generated STEP/GLB hashes
in one supplemental receipt.  It does not weaken or replace any V1 gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parent
V1_WRAPPER = PACKAGE / "execute_integrated_candidate_v1.py"
OUTPUT_STEP = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step"
OUTPUT_GLB = PACKAGE / ".R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step.glb"
ACTIVE_LOCK = PACKAGE / ".r2_integrated_candidate_active_run.lock"
AUTHORITY_DIR = PACKAGE / "candidate_authority_receipts"
EXECUTION_DIR = PACKAGE / "candidate_execution_receipts"
FAILURE_DIR = PACKAGE / "candidate_failure_receipts"
CHAIN_DIR = PACKAGE / "candidate_execution_chain_receipts"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def artifact_record(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def tail(text: str, limit: int = 12000) -> str:
    return text[-limit:]


def build_failure_payload(
    *, run_digest: str, returncode: int, stdout: str, stderr: str
) -> dict[str, Any]:
    authority_path = AUTHORITY_DIR / f"{run_digest}.json"
    execution_path = EXECUTION_DIR / f"{run_digest}.json"
    return {
        "schema": "R2_INTEGRATED_CANDIDATE_EXECUTION_FAILURE_RECEIPT_V2",
        "failed_utc": utc_now(),
        "run_id_sha256": run_digest,
        "v1_wrapper_returncode": int(returncode),
        "v1_stdout_tail": tail(stdout),
        "v1_stderr_tail": tail(stderr),
        "active_writer_lock_present": ACTIVE_LOCK.is_file(),
        "authority_receipt": artifact_record(authority_path),
        "v1_execution_receipt": artifact_record(execution_path),
        "partial_outputs": {
            "step": artifact_record(OUTPUT_STEP),
            "glb_topology": artifact_record(OUTPUT_GLB),
        },
        "retry_policy": "FAIL_CLOSED__PRESERVE_ACTIVE_LOCK__DO_NOT_REUSE_RUN_OR_OVERRIDE_ID",
        "memory_gate_passed_inferred": False,
        "owner_override_status_inferred": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "INTEGRATED_CANDIDATE_EXECUTION_FAILED__IMMUTABLE_EVIDENCE_CAPTURED__NO_RETRY_AUTHORITY",
    }


def build_success_chain(run_digest: str) -> dict[str, Any]:
    authority_path = AUTHORITY_DIR / f"{run_digest}.json"
    execution_path = EXECUTION_DIR / f"{run_digest}.json"
    required = [authority_path, execution_path, OUTPUT_STEP, OUTPUT_GLB]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"SUCCESS_CHAIN_REQUIRED_ARTIFACTS_MISSING:{missing}")
    if ACTIVE_LOCK.exists():
        raise RuntimeError("SUCCESS_CHAIN_ACTIVE_LOCK_STILL_PRESENT")

    authority = load_json(authority_path)
    execution = load_json(execution_path)
    if str(authority.get("run_id_sha256", "")).upper() != run_digest:
        raise RuntimeError("AUTHORITY_RECEIPT_RUN_DIGEST_MISMATCH")
    if str(execution.get("run_id_sha256", "")).upper() != run_digest:
        raise RuntimeError("EXECUTION_RECEIPT_RUN_DIGEST_MISMATCH")
    for key, path in (("step", OUTPUT_STEP), ("glb_topology", OUTPUT_GLB)):
        record = execution["outputs"][key]
        if int(record["bytes"]) != path.stat().st_size or str(record["sha256"]).upper() != sha256(path):
            raise RuntimeError(f"EXECUTION_OUTPUT_{key.upper()}_MISMATCH")

    return {
        "schema": "R2_INTEGRATED_CANDIDATE_EXECUTION_CHAIN_RECEIPT_V2",
        "completed_utc": utc_now(),
        "run_id_sha256": run_digest,
        "authority_receipt": artifact_record(authority_path),
        "v1_execution_receipt": artifact_record(execution_path),
        "wrappers": {
            "v1": artifact_record(V1_WRAPPER),
            "v2": artifact_record(Path(__file__).resolve()),
        },
        "outputs": {
            "step": artifact_record(OUTPUT_STEP),
            "glb_topology": artifact_record(OUTPUT_GLB),
        },
        "authority_summary": {
            "memory_gate_passed": authority.get("memory_gate_passed"),
            "owner_override_used": authority.get("owner_override_used"),
            "available_physical_memory_gib": authority.get("available_physical_memory_gib"),
        },
        "postgeneration_validation_required": True,
        "snapshot_review_required": True,
        "next_stage_authorized": False,
        "release_credit": False,
        "claim_limit": "CHAIN_OF_CUSTODY_ONLY__NO_GEOMETRY_M01_CONTACT_DYNAMICS_OR_RELEASE_CREDIT",
        "verdict": "INTEGRATED_CANDIDATE_EXECUTION_CHAIN_BOUND__POSTGEN_VALIDATION_AND_SNAPSHOT_HOLD",
    }


def main() -> int:
    run_id = os.environ.get("R2_DP_RUN_ID", "").strip()
    if not run_id:
        raise RuntimeError("R2_DP_RUN_ID_REQUIRED")
    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    failure_path = FAILURE_DIR / f"{run_digest}.json"
    chain_path = CHAIN_DIR / f"{run_digest}.json"
    if failure_path.exists() or chain_path.exists():
        raise RuntimeError("V2_RECEIPT_ALREADY_EXISTS_FOR_RUN_ID__DO_NOT_REUSE")

    try:
        completed = subprocess.run(
            [sys.executable, str(V1_WRAPPER)],
            cwd=PACKAGE,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception as exc:
        payload = build_failure_payload(
            run_digest=run_digest,
            returncode=2,
            stdout="",
            stderr=f"V1_WRAPPER_INVOCATION_EXCEPTION:{type(exc).__name__}:{exc}",
        )
        write_exclusive(failure_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False), file=sys.stderr)
        return 2
    if completed.returncode != 0:
        payload = build_failure_payload(
            run_digest=run_digest,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        write_exclusive(failure_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False), file=sys.stderr)
        return completed.returncode if completed.returncode > 0 else 1

    try:
        payload = build_success_chain(run_digest)
        write_exclusive(chain_path, payload)
    except Exception as exc:
        failure = build_failure_payload(
            run_digest=run_digest,
            returncode=3,
            stdout=completed.stdout,
            stderr=f"POST_V1_CHAIN_FAILURE:{exc}",
        )
        write_exclusive(failure_path, failure)
        print(json.dumps(failure, indent=2, ensure_ascii=False), file=sys.stderr)
        return 3
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
