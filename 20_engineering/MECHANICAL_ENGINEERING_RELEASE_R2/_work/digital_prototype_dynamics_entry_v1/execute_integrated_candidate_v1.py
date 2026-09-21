"""Authorized wrapper for the standard CAD STEP generator.

The generator itself owns source, memory and one-time authority checks.  This
wrapper keeps the package writer lock until the standard CAD tool has emitted
both STEP and GLB/topology artifacts and a success receipt has been committed.
On any failure the lock remains for Owner inspection.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
GENERATOR = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.py"
OUTPUT_STEP = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step"
OUTPUT_GLB = PACKAGE / ".R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step.glb"
ACTIVE_LOCK = PACKAGE / ".r2_integrated_candidate_active_run.lock"
RECEIPT_DIR = PACKAGE / "candidate_execution_receipts"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _cad_skill_root() -> Path:
    explicit = os.environ.get("CAD_SKILL_ROOT", "").strip()
    candidates = [
        Path(explicit) if explicit else None,
        Path("F:/codex_skill/AgentSkills/agents-skills/cad"),
        Path("F:/codex_skill/AgentSkills/codex-skills/cad"),
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "scripts" / "step" / "__main__.py").is_file():
            return candidate.resolve()
    raise RuntimeError("CAD_SKILL_ROOT_NOT_FOUND: set CAD_SKILL_ROOT to the active cad skill directory")


def main() -> int:
    run_id = os.environ.get("R2_DP_RUN_ID", "").strip()
    if not run_id:
        raise RuntimeError("R2_DP_RUN_ID_REQUIRED")
    skill_root = _cad_skill_root()
    command = [
        sys.executable,
        "-m",
        "scripts.step",
        GENERATOR.as_posix(),
        "-o",
        OUTPUT_STEP.as_posix(),
        "--verbose",
    ]
    if os.environ.get("R2_DP_ALLOW_OVERWRITE", "").strip().upper() == "YES":
        command.append("--force")
    completed = subprocess.run(command, cwd=skill_root, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"STANDARD_CAD_TOOL_FAILED_WITH_CODE_{completed.returncode}; active lock retained for Owner inspection"
        )
    if not OUTPUT_STEP.is_file() or not OUTPUT_GLB.is_file():
        raise RuntimeError("STANDARD_CAD_TOOL_OUTPUT_INCOMPLETE; active lock retained for Owner inspection")

    lock = json.loads(ACTIVE_LOCK.read_text(encoding="utf-8"))
    if lock.get("run_id") != run_id:
        raise RuntimeError("ACTIVE_LOCK_OWNER_MISMATCH; active lock retained")
    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    receipt = {
        "schema": "R2_INTEGRATED_CANDIDATE_EXECUTION_RECEIPT_V1",
        "run_id": run_id,
        "run_id_sha256": run_digest,
        "completed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "standard_cad_tool": "cad/scripts/step",
        "generator": {"path": GENERATOR.name, "sha256": _sha256(GENERATOR)},
        "outputs": {
            "step": {"path": OUTPUT_STEP.name, "bytes": OUTPUT_STEP.stat().st_size, "sha256": _sha256(OUTPUT_STEP)},
            "glb_topology": {"path": OUTPUT_GLB.name, "bytes": OUTPUT_GLB.stat().st_size, "sha256": _sha256(OUTPUT_GLB)},
        },
        "claim_limit": "RESEARCH_CANDIDATE_ONLY__PENDING_CAD_INSPECTION_AND_SNAPSHOT_REVIEW__NO_RELEASE_CREDIT",
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPT_DIR / f"{run_digest}.json"
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
    ACTIVE_LOCK.unlink()
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
