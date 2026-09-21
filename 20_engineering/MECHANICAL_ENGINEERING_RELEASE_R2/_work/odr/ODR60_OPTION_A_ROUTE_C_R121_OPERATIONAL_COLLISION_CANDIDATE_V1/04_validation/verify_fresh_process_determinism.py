"""Verify the frozen R20 builder in two clean subprocesses without importing it.

Only the deterministic 83-artifact builder core is covered here: twenty primary
STEP files, sixty runtime sidecars, and the three builder receipts.  Review
images, CAD-tool caches, independent evidence, and package inventories are
deliberately outside that core.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from route_c_r20_validation_lib import (
    BUILD_RECEIPT_PATH,
    CAD_DIR,
    CONTRACT_PATH,
    DETERMINISM_PATH,
    GEOMETRY_INDEX_PATH,
    PACKAGE,
    RUNTIME_DIR,
    RUNTIME_RECEIPT_PATH,
    ValidationFailure,
    atomic_write,
    require,
    sha256_path,
    stable_json_bytes,
    strict_json,
    validate_contract_structure,
    workspace_root,
)


BUILDER = PACKAGE / "02_builder/build_route_c_root_static_r20.py"
EXPECTED_SUMMARY = {
    "artifacts": 83,
    "mode": "check",
    "objects": 20,
    "runtime_sidecars": 60,
    "source_pins": 13,
    "steps": 20,
    "verdict": "R20_PRIMARY_STEP_AND_RUNTIME_BUILD_PASS__R101_AND_SYSTEM_BINDING_REMAIN_HELD",
    "verified": 83,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def parse_trailing_json(stdout: str) -> dict[str, Any]:
    """Parse the final JSON object despite OpenCascade transfer diagnostics."""

    candidates = [index for index, character in enumerate(stdout) if character == "{"]
    for index in reversed(candidates):
        suffix = stdout[index:].strip()
        try:
            value = json.loads(suffix)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValidationFailure("fresh builder stdout has no trailing JSON object")


def core_paths() -> list[Path]:
    contract = strict_json(CONTRACT_PATH)
    specs = validate_contract_structure(contract)
    paths: list[Path] = []
    for spec in specs:
        step_name = str(spec["output"])
        require(step_name.endswith("_S_V1.step"), f"unexpected STEP name: {step_name}")
        paths.append(CAD_DIR / step_name)
        stem = step_name.removesuffix("_S_V1.step") + "_S_M_V1"
        paths.extend(RUNTIME_DIR / f"{stem}.{suffix}" for suffix in ("npz", "ply", "stl"))
    paths.extend((GEOMETRY_INDEX_PATH, RUNTIME_RECEIPT_PATH, BUILD_RECEIPT_PATH))
    require(len(paths) == 83 and len(set(paths)) == 83, "deterministic core is not exactly 83 unique artifacts")
    return sorted(paths, key=lambda path: path.as_posix())


def core_snapshot(paths: list[Path]) -> list[dict[str, Any]]:
    root = workspace_root()
    rows = []
    for path in paths:
        require(path.is_file(), f"deterministic core artifact missing: {path}")
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
        )
    return rows


def external_record(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"runtime executable missing: {path}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def run_once(index: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=workspace_root(),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    require(completed.returncode == 0, f"fresh builder run {index} failed: {completed.stderr[-2000:]}")
    summary = parse_trailing_json(completed.stdout)
    require(summary == EXPECTED_SUMMARY, f"fresh builder run {index} summary drift: {summary}")
    return {
        "run_index": index,
        "process_kind": "NEW_CPYTHON_SUBPROCESS",
        "return_code": completed.returncode,
        "parsed_summary": summary,
        "occt_transfer_diagnostic_blocks_observed": completed.stdout.count("Statistics on Transfer (Write)"),
        "stderr_empty": completed.stderr == "",
    }


def build_receipt() -> dict[str, Any]:
    paths = core_paths()
    before = core_snapshot(paths)
    runs = []
    intermediate = before
    for index in (1, 2):
        runs.append(run_once(index))
        after_run = core_snapshot(paths)
        require(after_run == intermediate, f"builder --check mutated deterministic core during run {index}")
        intermediate = after_run
    after = core_snapshot(paths)
    require(before == after, "deterministic core changed across fresh-process replay")
    require(runs[0]["parsed_summary"] == runs[1]["parsed_summary"], "fresh-process summaries differ")
    require(all(run["occt_transfer_diagnostic_blocks_observed"] == 20 for run in runs), "unexpected STEP transfer count")
    return {
        "schema": "ROUTE_C_ROOT_STATIC_R20_FRESH_PROCESS_DETERMINISM_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "scope": "BUILDER_DETERMINISTIC_CORE_83_ARTIFACTS_ONLY",
        "builder": {
            "path": BUILDER.relative_to(workspace_root()).as_posix(),
            "bytes": BUILDER.stat().st_size,
            "sha256": sha256_path(BUILDER),
            "imported_by_checker": False,
            "invocation": ["<current-python>", BUILDER.relative_to(workspace_root()).as_posix(), "--check"],
        },
        "python_runtime": external_record(Path(sys.executable)),
        "fixed_environment": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
        },
        "fresh_process_count": 2,
        "runs": runs,
        "core_artifact_count": len(before),
        "core_before": before,
        "core_after": after,
        "core_unchanged": before == after,
        "parsed_summaries_identical": runs[0]["parsed_summary"] == runs[1]["parsed_summary"],
        "fresh_process_determinism_pass": True,
        "authority_boundary": {
            "review_derivatives_in_core": False,
            "cad_cache_in_core": False,
            "system_binding_credit": False,
            "pair_edge_path_credit": False,
            "release_credit": False,
        },
        "maximum_legal_claim": "R20_BUILDER_CHECK_MODE_REPRODUCES_THE_FROZEN_83_ARTIFACT_LOCAL_CANDIDATE_CORE",
        "verdict": "TWO_FRESH_PROCESS_CHECKS_PASS__83_OF_83_CORE_ARTIFACTS_UNCHANGED__NO_SYSTEM_CREDIT",
    }


def main() -> None:
    args = parse_args()
    receipt = build_receipt()
    encoded = stable_json_bytes(receipt)
    if args.write:
        atomic_write(DETERMINISM_PATH, encoded)
    else:
        require(DETERMINISM_PATH.is_file(), f"receipt missing: {DETERMINISM_PATH}")
        require(DETERMINISM_PATH.read_bytes() == encoded, "fresh-process determinism receipt drift")
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "write" if args.write else "check",
                "fresh_processes": 2,
                "core_artifacts": 83,
                "release_credit": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
