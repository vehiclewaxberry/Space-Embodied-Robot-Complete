#!/usr/bin/env python3
"""Run two clean builder replays and two independent validations without imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
BUILDER = PACKAGE / "02_builder/build_link1_b6.py"
VALIDATOR = PACKAGE / "04_validation/validate_link1_b6_independent.py"
OUTPUT = PACKAGE / "05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def artifact_records() -> list[dict]:
    paths = sorted((PACKAGE / "01_cad").glob("*.step")) + sorted((PACKAGE / "02_runtime").glob("*.*"))
    paths += [PACKAGE / "05_results/LINK1_B6_GEOMETRY_INDEX_V1.json", PACKAGE / "05_results/LINK1_B6_RUNTIME_SIDECAR_RECEIPT_V1.json", PACKAGE / "05_results/LINK1_B6_POSE_ADAPTER_SAMPLES_V1.json", PACKAGE / "05_results/SIX_STEP_BUILD_RECEIPT_V1.json"]
    if len(paths) != 28 or any(not path.is_file() for path in paths):
        raise RuntimeError("expected exact 28 builder artifacts")
    return [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)} for path in paths]


def run(command: list[str], marker: str) -> dict:
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"fresh process failed: {command}: {completed.stdout} {completed.stderr}")
    index = completed.stdout.rfind(marker)
    if index < 0:
        raise RuntimeError(f"summary marker missing: {marker}")
    start = completed.stdout.rfind("{", 0, index + 1)
    return json.loads(completed.stdout[start:])


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); args = parser.parse_args()
    before = artifact_records()
    builder_runs = [run([sys.executable, str(BUILDER), "--check"], '"artifacts"') for _ in range(2)]
    validator_runs = [run([sys.executable, str(VALIDATOR)], '"geometry_objects"') for _ in range(2)]
    after = artifact_records()
    if before != after or builder_runs[0] != builder_runs[1] or validator_runs[0] != validator_runs[1]:
        raise RuntimeError("fresh-process deterministic replay mismatch")
    document = {
        "schema": "ROUTE_C_LINK1_B6_FRESH_PROCESS_DETERMINISM_RECEIPT_V1", "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "builder_command": [sys.executable, str(BUILDER), "--check"], "validator_command": [sys.executable, str(VALIDATOR)],
        "builder_fresh_process_runs": builder_runs, "validator_fresh_process_runs": validator_runs,
        "artifact_count": len(before), "artifacts_before": before, "artifacts_after_identical": True,
        "verdict": "TWO_BUILDER_CHECKS_AND_TWO_INDEPENDENT_VALIDATIONS_MATCH_WITH_28_ARTIFACTS_UNCHANGED",
    }
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        temporary = OUTPUT.with_suffix(".json.tmp"); temporary.write_bytes(data); temporary.replace(OUTPUT)
    print(json.dumps({"artifacts": len(before), "builder_runs": 2, "validator_runs": 2, "mode": "write" if args.write else "check", "verdict": document["verdict"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
