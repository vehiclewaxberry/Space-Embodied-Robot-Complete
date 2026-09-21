"""Run the C9 build and both validation paths in two fresh Python processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class ReplayFailure(RuntimeError):
    pass


PACKAGE = Path(__file__).resolve().parents[1]
BUILDER = PACKAGE / "02_builder/build_c9_capsules.py"
POSE = PACKAGE / "02_builder/c9_pose_adapter.py"
VALIDATOR = PACKAGE / "04_validation/validate_c9_independent.py"
RECEIPT = PACKAGE / "05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ReplayFailure("repository root not found")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayFailure(message)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def stable(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def core_paths() -> list[Path]:
    runtime = sorted((PACKAGE / "03_runtime").glob("*"), key=lambda item: item.name)
    require(len(runtime) == 18, "runtime core must contain exactly eighteen files")
    paths = runtime + [
        PACKAGE / "05_results/C9_CAPSULE_INDEX_V1.json",
        PACKAGE / "05_results/C9_BUILD_RECEIPT_V1.json",
        PACKAGE / "05_results/POSE_ADAPTER_SELF_CHECK_V1.json",
        PACKAGE / "05_results/INDEPENDENT_VALIDATION_V1.json",
        PACKAGE / "05_results/NEGATIVE_CONTROLS_V1.json",
    ]
    require(len(paths) == 23 and len(set(paths)) == 23 and all(path.is_file() for path in paths),
            "deterministic C9 core is not exactly twenty-three files")
    return paths


def snapshot(paths: list[Path]) -> list[dict[str, Any]]:
    return [{
        "path": path.relative_to(repo_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    } for path in paths]


def trailing_json(stdout: str) -> dict[str, Any]:
    for index in reversed([i for i, value in enumerate(stdout) if value == "{"]):
        try:
            parsed = json.loads(stdout[index:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ReplayFailure("subprocess stdout has no trailing JSON")


def run_script(script: Path, argument: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"})
    completed = subprocess.run(
        [sys.executable, str(script), argument],
        cwd=repo_root(),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    require(completed.returncode == 0, f"fresh process failed: {script.name}: {completed.stderr[-2000:]}")
    parsed = trailing_json(completed.stdout)
    require(parsed.get("status") == "PASS", f"fresh process did not report PASS: {script.name}")
    return {
        "script": script.relative_to(repo_root()).as_posix(),
        "script_sha256": sha(script),
        "argument": argument,
        "return_code": completed.returncode,
        "summary": parsed,
        "stderr_empty": completed.stderr == "",
    }


def make_receipt() -> dict[str, Any]:
    paths = core_paths()
    before = snapshot(paths)
    runs = []
    for replay in (1, 2):
        commands = [
            run_script(BUILDER, "--check"),
            run_script(POSE, "--check-self-check"),
            run_script(VALIDATOR, "--check"),
        ]
        after = snapshot(paths)
        require(after == before, f"deterministic core changed in replay {replay}")
        runs.append({"replay": replay, "fresh_processes": commands, "core_unchanged": True})
    require(runs[0]["fresh_processes"] == runs[1]["fresh_processes"], "fresh-process summaries differ")
    return {
        "schema": "ROUTE_C_C9_FRESH_PROCESS_DETERMINISM_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "fixed_environment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"},
        "replay_count": 2,
        "fresh_process_count": 6,
        "core_artifact_count": len(before),
        "core_before": before,
        "core_after": snapshot(paths),
        "runs": runs,
        "core_unchanged": True,
        "summaries_identical": True,
        "fresh_process_determinism_pass": True,
        "authority_boundary": {
            "J3_production_union_acceptance": "UNKNOWN",
            "current_pair_edge_path_credit": 0,
            "TMG4": "HOLD",
            "release_credit": False,
        },
        "verdict": "TWO_C9_REPLAYS_SIX_FRESH_PROCESSES_PASS__23_CORE_ARTIFACTS_UNCHANGED__NO_SYSTEM_CREDIT",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = make_receipt()
    encoded = stable(receipt)
    if args.write:
        atomic(RECEIPT, encoded)
        mode = "write"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded, "fresh-process receipt drift")
        mode = "check"
    print(json.dumps({
        "status": "PASS", "mode": mode, "replays": 2, "fresh_processes": 6,
        "core_artifacts": 23, "J3_production_union_acceptance": "UNKNOWN",
        "system_pair_credit": 0, "TMG4": "HOLD",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
