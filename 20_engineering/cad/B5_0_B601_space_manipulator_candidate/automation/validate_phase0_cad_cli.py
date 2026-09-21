"""Capture and validate the mandatory CAD CLI inspection for one smoke run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


CANDIDATE = Path(__file__).resolve().parents[1]
INSPECT = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9"
    r"\skills\cad\scripts\inspect"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def inside(path: Path, root: Path) -> bool:
    return os.path.commonpath(
        [str(path.resolve(strict=False)), str(root.resolve(strict=False))]
    ) == str(root.resolve(strict=False))


def file_record(path: Path, root: Path) -> dict[str, object]:
    if not inside(path, root) or not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"invalid run artifact: {path}")
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-step-sha256", required=True)
    args = parser.parse_args()
    run_root = (CANDIDATE / "phase0_runs" / args.run_id).resolve()
    if not inside(run_root, CANDIDATE) or not run_root.is_dir():
        raise SystemExit(f"invalid run root: {run_root}")
    report_path = run_root / "evidence/phase0_cad_cli_validation.json"
    if report_path.exists():
        raise SystemExit(f"overwrite forbidden: {report_path}")
    step = run_root / "exports/PHASE0_COM_SMOKE_ASSEMBLY.step"
    hidden_glb = step.with_name(f".{step.name}.glb")
    sidecar_report_path = run_root / "evidence/phase0_sidecar_report.json"
    snapshots = sorted((run_root / "reviews").glob("phase0_smoke_iso_*.png"))
    if len(snapshots) != 1:
        raise SystemExit(f"expected exactly one reviewed snapshot, got {snapshots}")

    command = [
        sys.executable,
        str(INSPECT),
        "refs",
        step.as_posix(),
        "--facts",
        "--planes",
        "--positioning",
        "--format",
        "json",
    ]
    completed = subprocess.run(
        command,
        cwd=CANDIDATE.parents[2],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"inspect output is not JSON: exit={completed.returncode}; "
            f"stderr={completed.stderr!r}; stdout={completed.stdout[:500]!r}"
        ) from exc
    if completed.returncode != 0 or not payload.get("ok") or payload.get("errors"):
        raise SystemExit(
            f"inspect failed: exit={completed.returncode}; payload={payload}"
        )
    tokens = payload.get("tokens") or []
    if len(tokens) != 1:
        raise SystemExit(f"unexpected inspect token count: {len(tokens)}")
    summary = tokens[0]["summary"]
    expected_bounds = {"min": [-10.0, -5.0, 0.0], "max": [10.0, 5.0, 5.0]}
    checks = {
        "step_hash_match": (
            sha256(step) == args.expected_step_sha256.upper()
            and tokens[0]["stepHash"].upper() == args.expected_step_sha256.upper()
        ),
        "kind_assembly": summary["kind"] == "assembly",
        "one_leaf_occurrence": summary["leafOccurrenceCount"] == 1,
        "one_shape": summary["shapeCount"] == 1,
        "six_faces": summary["faceCount"] == 6,
        "twelve_edges": summary["edgeCount"] == 12,
        "bounds_match": summary["bounds"] == expected_bounds,
        "six_major_planes": len(tokens[0].get("planes") or []) == 6,
        "positioning_present": bool(tokens[0].get("entryPositioning")),
        "hidden_topology_glb_present": hidden_glb.is_file()
        and hidden_glb.stat().st_size > 0,
    }
    sidecar_report = json.loads(sidecar_report_path.read_text(encoding="utf-8"))
    checks["sidecar_fallback_pass"] = str(sidecar_report["verdict"]).startswith(
        "B5_0_STEP_SIDECAR_DERIVATION_PASS"
    )
    with Image.open(snapshots[0]) as image:
        snapshot_size = list(image.size)
        image.verify()
    checks["snapshot_present_and_readable"] = all(
        value > 0 for value in snapshot_size
    )

    locks = [
        path.relative_to(run_root).as_posix()
        for path in run_root.rglob("~$*")
        if path.is_file()
    ]
    checks["no_solidworks_lock_files"] = not locks
    verdict = (
        "B5_0_PHASE0_CAD_CLI_PASS_WITH_RECORDED_SIDECAR_TOOL_DEVIATION"
        if all(checks.values())
        else "B5_0_PHASE0_CAD_CLI_FAIL"
    )
    report = {
        "gate_id": "B5_0_PHASE0_G0_E_CAD_CLI",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "command": command,
        "exit_code": completed.returncode,
        "checks": checks,
        "inspect": payload,
        "step": file_record(step, run_root),
        "hidden_topology_glb": file_record(hidden_glb, run_root),
        "stl": file_record(
            run_root / "meshes/PHASE0_COM_SMOKE_ASSEMBLY.stl", run_root
        ),
        "native_glb": file_record(
            run_root / "meshes/PHASE0_COM_SMOKE_ASSEMBLY.glb", run_root
        ),
        "snapshot": {
            **file_record(snapshots[0], run_root),
            "pixels": snapshot_size,
            "visual_review": "SEE_00_AUDIT_PHASE0_SNAPSHOT_REVIEW",
        },
        "lock_files": locks,
        "verdict": verdict,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"verdict": verdict, "checks": checks}, ensure_ascii=False))
    if verdict.endswith("_FAIL"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
